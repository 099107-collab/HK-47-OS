"""
HK-47 OS :: recon_tools.py
Reconnaissance of the local electromagnetic battlefield: WiFi scanning, subnet
discovery and Bluetooth/BLE beacon enumeration. Results can be stashed in the
encrypted vault for later analysis.
"""

import concurrent.futures
import json
import re
import socket
import subprocess
import time


def _run(cmd, timeout=20):
    """Run a command list, returning (stdout, ok)."""
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout
        )
        return (proc.stdout or "") + (proc.stderr or ""), proc.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return "", False


# ---------------------------------------------------------------------------
# WiFi
# ---------------------------------------------------------------------------
def _scan_wifi_nmcli():
    out, ok = _run(
        ["nmcli", "-t", "-f", "SSID,SIGNAL,SECURITY", "dev", "wifi", "list"],
        timeout=25,
    )
    if not ok and not out:
        return None
    networks = []
    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        # nmcli -t escapes ':' inside fields as '\:'; split on unescaped colons.
        parts = re.split(r"(?<!\\):", line)
        parts = [p.replace("\\:", ":") for p in parts]
        if len(parts) < 3:
            continue
        ssid, signal, security = parts[0], parts[1], parts[2]
        try:
            signal = int(signal)
        except ValueError:
            signal = None
        networks.append(
            {
                "ssid": ssid or "<hidden>",
                "signal": signal,
                "security": security or "OPEN",
            }
        )
    return networks


def _scan_wifi_iwlist():
    out, ok = _run(["iwlist", "scan"], timeout=25)
    if not out:
        return []
    networks = []
    current = {}
    for raw in out.splitlines():
        line = raw.strip()
        if line.startswith("Cell "):
            if current:
                networks.append(current)
            current = {"ssid": None, "signal": None, "security": "OPEN"}
        elif line.startswith("ESSID:"):
            current["ssid"] = line.split("ESSID:", 1)[1].strip().strip('"') or "<hidden>"
        elif "Signal level" in line:
            m = re.search(r"Signal level[=:]\s*(-?\d+)", line)
            if m:
                current["signal"] = int(m.group(1))
        elif "Encryption key:on" in line:
            current["security"] = "WEP/WPA"
    if current:
        networks.append(current)
    return [n for n in networks if n.get("ssid")]


def scan_local_wifi(vault=None) -> list:
    """Scan for nearby WiFi networks (nmcli preferred, iwlist fallback)."""
    networks = _scan_wifi_nmcli()
    if networks is None:
        networks = _scan_wifi_iwlist()
    networks = networks or []

    if vault is not None:
        try:
            vault.store("wifi_scan_latest", json.dumps(networks))
        except Exception:
            pass
    return networks


# ---------------------------------------------------------------------------
# Subnet discovery
# ---------------------------------------------------------------------------
def _local_ip():
    # Try `hostname -I` first.
    out, ok = _run(["hostname", "-I"], timeout=5)
    if ok and out.strip():
        return out.strip().split()[0]
    # Fallback: UDP socket trick (no packets actually sent).
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except OSError:
        return "127.0.0.1"


def _ping(host, timeout=0.5):
    out, ok = _run(
        ["ping", "-c", "1", "-W", str(max(1, int(timeout))), host],
        timeout=timeout + 2,
    )
    return host if ok else None


def _neighbors():
    out, _ = _run(["ip", "neighbor", "show"], timeout=10)
    found = []
    for line in out.splitlines():
        parts = line.split()
        if parts and re.match(r"\d+\.\d+\.\d+\.\d+", parts[0]):
            if "FAILED" not in line and "INCOMPLETE" not in line:
                found.append(parts[0])
    return found


def subnet_discovery(network_prefix: str = None) -> list:
    """Enumerate live hosts on the local /24 subnet."""
    if network_prefix is None:
        ip = _local_ip()
        network_prefix = ".".join(ip.split(".")[:3])

    # Fast path: ARP/neighbor cache.
    neighbors = [ip for ip in _neighbors() if ip.startswith(network_prefix + ".")]
    if neighbors:
        return sorted(set(neighbors))

    # Slow path: concurrent ping sweep.
    hosts = [f"{network_prefix}.{i}" for i in range(1, 255)]
    alive = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=64) as pool:
        for result in pool.map(_ping, hosts):
            if result:
                alive.append(result)
    return sorted(set(alive))


# ---------------------------------------------------------------------------
# Bluetooth / BLE
# ---------------------------------------------------------------------------
def _parse_hci_lines(text):
    beacons = []
    for line in text.splitlines():
        line = line.strip()
        m = re.match(r"([0-9A-Fa-f:]{17})\s*(.*)", line)
        if m:
            mac = m.group(1)
            name = m.group(2).strip() or "<unknown>"
            beacons.append({"mac": mac, "name": name})
    return beacons


def scan_ble_beacons(vault=None, timeout: int = 10) -> list:
    """Enumerate classic Bluetooth and BLE devices via hcitool."""
    beacons = {}

    # Classic inquiry scan.
    out, _ = _run(["hcitool", "scan"], timeout=timeout + 5)
    for b in _parse_hci_lines(out):
        beacons[b["mac"]] = b

    # BLE scan — must be launched and killed after `timeout` seconds.
    try:
        proc = subprocess.Popen(
            ["hcitool", "lescan"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        time.sleep(timeout)
        proc.terminate()
        try:
            le_out, _ = proc.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            le_out, _ = proc.communicate()
        for b in _parse_hci_lines(le_out or ""):
            beacons.setdefault(b["mac"], b)
    except (FileNotFoundError, OSError):
        pass

    result = list(beacons.values())
    if vault is not None:
        try:
            vault.store("ble_scan_latest", json.dumps(result))
        except Exception:
            pass
    return result
