"""
HK-47 OS :: security_tools.py
Encrypted local vault (Fernet + PBKDF2) and the infamous Protocol-13 secure
purge. Keeps the meatbag's secrets — or destroys them utterly on tamper.
"""

import base64
import glob
import os
import sqlite3
import time

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

import config

_PBKDF2_SALT = b"HK47SALT01"
_PBKDF2_ITERATIONS = 100000


def _derive_key(passcode: str) -> bytes:
    """Derive a URL-safe base64 Fernet key from a passcode via PBKDF2-HMAC-SHA256."""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=_PBKDF2_SALT,
        iterations=_PBKDF2_ITERATIONS,
    )
    raw = kdf.derive((passcode or "").encode("utf-8"))
    return base64.urlsafe_b64encode(raw)


class EncryptedVault:
    """A tiny encrypted key/value store backed by SQLite + Fernet."""

    def __init__(self, vault_path, key_path, passcode: str):
        self.vault_path = vault_path
        self.key_path = key_path
        self.fernet = Fernet(_derive_key(passcode))
        self.conn = None

    # -- connection -------------------------------------------------------
    def _connect(self):
        if self.conn is not None:
            return self.conn
        os.makedirs(os.path.dirname(self.vault_path), exist_ok=True)
        self.conn = sqlite3.connect(self.vault_path)
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS vault_data (
                id INTEGER PRIMARY KEY,
                key TEXT UNIQUE,
                encrypted_value BLOB,
                timestamp TEXT
            )
            """
        )
        self.conn.commit()
        return self.conn

    # -- CRUD -------------------------------------------------------------
    def store(self, key: str, value: str):
        conn = self._connect()
        token = self.fernet.encrypt((value or "").encode("utf-8"))
        conn.execute(
            "INSERT OR REPLACE INTO vault_data (key, encrypted_value, timestamp) "
            "VALUES (?, ?, ?)",
            (key, token, time.strftime("%Y-%m-%dT%H:%M:%S")),
        )
        conn.commit()

    def retrieve(self, key: str):
        conn = self._connect()
        cur = conn.execute(
            "SELECT encrypted_value FROM vault_data WHERE key = ?", (key,)
        )
        row = cur.fetchone()
        if not row:
            return None
        try:
            return self.fernet.decrypt(row[0]).decode("utf-8")
        except (InvalidToken, ValueError):
            return None

    def list_keys(self):
        conn = self._connect()
        cur = conn.execute("SELECT key FROM vault_data ORDER BY key")
        return [r[0] for r in cur.fetchall()]

    def delete(self, key: str):
        conn = self._connect()
        conn.execute("DELETE FROM vault_data WHERE key = ?", (key,))
        conn.commit()

    def close(self):
        if self.conn is not None:
            try:
                self.conn.close()
            finally:
                self.conn = None


def _secure_overwrite(path, passes=7):
    """Overwrite a file with random bytes `passes` times, then unlink it."""
    if not os.path.exists(path):
        return False
    try:
        size = os.path.getsize(path)
        with open(path, "r+b", buffering=0) as fh:
            for _ in range(passes):
                fh.seek(0)
                fh.write(os.urandom(max(size, 1)))
                fh.flush()
                os.fsync(fh.fileno())
        os.unlink(path)
        return True
    except (OSError, PermissionError):
        # Last-ditch: attempt a plain unlink.
        try:
            os.unlink(path)
            return True
        except OSError:
            return False


def protocol_13_purge(vault_path=None, key_path=None) -> str:
    """
    Scorched-earth data destruction. Overwrites and deletes the vault, key,
    pycache artifacts and temp files. Named for HK-47's memory-wipe directive.
    """
    vault_path = vault_path or config.VAULT_PATH
    key_path = key_path or config.KEY_PATH

    _secure_overwrite(vault_path)
    _secure_overwrite(key_path)

    # Remove pycache in ~/.hk47 and compiled artifacts next to the package.
    hk47_dir = os.path.dirname(os.path.abspath(__file__))
    for pyc in glob.glob(os.path.join(hk47_dir, "**", "*.pyc"), recursive=True):
        try:
            os.unlink(pyc)
        except OSError:
            pass
    for cache_dir in glob.glob(os.path.join(hk47_dir, "**", "__pycache__"), recursive=True):
        try:
            for f in glob.glob(os.path.join(cache_dir, "*")):
                os.unlink(f)
            os.rmdir(cache_dir)
        except OSError:
            pass
    home_cache = os.path.join(config.HK47_HOME, "__pycache__")
    if os.path.isdir(home_cache):
        try:
            for f in glob.glob(os.path.join(home_cache, "*")):
                os.unlink(f)
            os.rmdir(home_cache)
        except OSError:
            pass

    for tmp in glob.glob("/tmp/hk47_*.tmp"):
        try:
            os.unlink(tmp)
        except OSError:
            pass

    return ("Conclusion: Protocol-13 executed. All local data purged, meatbag. "
            "Your secrets die with me.")


def initialize_vault(passcode: str) -> EncryptedVault:
    """Create the HK-47 home directory and return a ready vault instance."""
    os.makedirs(config.HK47_HOME, exist_ok=True)
    vault = EncryptedVault(config.VAULT_PATH, config.KEY_PATH, passcode)
    # Touch the connection so the DB/table exist immediately.
    vault._connect()
    return vault
