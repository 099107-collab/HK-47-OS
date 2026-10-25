"""
HK-47 OS :: hid_tools.py
USB HID keyboard injection via the Linux USB Gadget subsystem (/dev/hidg0).
Includes a full ASCII->HID keycode map, named payloads and a configfs-based
gadget setup routine. Degrades to no-op logging when hardware is absent.
"""

import logging
import os
import time

logger = logging.getLogger("hk47.hid")

HID_DEVICE = "/dev/hidg0"
USB_GADGET_PATH = "/sys/kernel/config/usb_gadget/hk47_hid"

# USB HID modifier byte flags.
MOD_NONE = 0x00
MOD_LCTRL = 0x01
MOD_LSHIFT = 0x02
MOD_LALT = 0x04
MOD_LGUI = 0x08  # "Windows"/Super key

# Base (unshifted) keycodes keyed by character.
_BASE_KEYS = {
    "a": 0x04, "b": 0x05, "c": 0x06, "d": 0x07, "e": 0x08, "f": 0x09,
    "g": 0x0A, "h": 0x0B, "i": 0x0C, "j": 0x0D, "k": 0x0E, "l": 0x0F,
    "m": 0x10, "n": 0x11, "o": 0x12, "p": 0x13, "q": 0x14, "r": 0x15,
    "s": 0x16, "t": 0x17, "u": 0x18, "v": 0x19, "w": 0x1A, "x": 0x1B,
    "y": 0x1C, "z": 0x1D,
    "1": 0x1E, "2": 0x1F, "3": 0x20, "4": 0x21, "5": 0x22, "6": 0x23,
    "7": 0x24, "8": 0x25, "9": 0x26, "0": 0x27,
    "\n": 0x28, "\r": 0x28, "\t": 0x2B, " ": 0x2C,
    "-": 0x2D, "=": 0x2E, "[": 0x2F, "]": 0x30, "\\": 0x31,
    ";": 0x33, "'": 0x34, "`": 0x35, ",": 0x36, ".": 0x37, "/": 0x38,
}

# Shifted symbols -> base character (shift modifier is applied).
_SHIFT_SYMBOLS = {
    "!": "1", "@": "2", "#": "3", "$": "4", "%": "5", "^": "6",
    "&": "7", "*": "8", "(": "9", ")": "0",
    "_": "-", "+": "=", "{": "[", "}": "]", "|": "\\",
    ":": ";", '"': "'", "~": "`", "<": ",", ">": ".", "?": "/",
}


def _keycode_for_char(ch):
    """Return (modifier, keycode) for a character, or None if unsupported."""
    if ch in _BASE_KEYS:
        return (MOD_NONE, _BASE_KEYS[ch])
    if ch.isalpha() and ch.lower() in _BASE_KEYS:
        return (MOD_LSHIFT, _BASE_KEYS[ch.lower()])
    if ch in _SHIFT_SYMBOLS:
        return (MOD_LSHIFT, _BASE_KEYS[_SHIFT_SYMBOLS[ch]])
    return None


# Pre-built complete map for inspection/debugging.
KEYCODE_MAP = {}
for _c in _BASE_KEYS:
    KEYCODE_MAP[_c] = (MOD_NONE, _BASE_KEYS[_c])
for _c, _base in _SHIFT_SYMBOLS.items():
    KEYCODE_MAP[_c] = (MOD_LSHIFT, _BASE_KEYS[_base])
for _c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
    KEYCODE_MAP[_c] = (MOD_LSHIFT, _BASE_KEYS[_c.lower()])

_ENTER = _BASE_KEYS["\n"]

# Named utility payloads. Each is a list of actions:
#   ("type", "text")      -> type the literal string
#   ("key", mod, keycode) -> send a raw key chord
#   ("delay", seconds)    -> wait
PAYLOADS = {
    "admin_shell": [
        ("key", MOD_LGUI, _BASE_KEYS["r"]),   # Win+R (Run dialog)
        ("delay", 0.5),
        ("type", "cmd"),
        ("key", MOD_NONE, _ENTER),
        ("delay", 0.5),
    ],
    "info_dump": [
        ("type", "systeminfo"),
        ("key", MOD_NONE, _ENTER),
        ("delay", 0.2),
        ("type", "uname -a"),
        ("key", MOD_NONE, _ENTER),
    ],
    "network_scan": [
        ("type", "ipconfig /all"),
        ("key", MOD_NONE, _ENTER),
        ("delay", 0.2),
        ("type", "ip addr"),
        ("key", MOD_NONE, _ENTER),
    ],
}


class HIDKeyboard:
    """A USB HID keyboard that writes 8-byte reports to /dev/hidg0."""

    def __init__(self, device=HID_DEVICE, inter_key_delay=0.01):
        self.device = device
        self.inter_key_delay = inter_key_delay
        self.fh = None
        try:
            self.fh = open(self.device, "wb", buffering=0)
            logger.info("HID device %s opened.", self.device)
        except (FileNotFoundError, PermissionError, OSError) as exc:
            logger.warning("HID device %s unavailable (%s); running in no-op mode.",
                           self.device, exc)
            self.fh = None

    @property
    def available(self):
        return self.fh is not None

    def _write_report(self, report: bytes):
        if self.fh is None:
            logger.debug("HID (no-op) report: %s", report.hex())
            return
        try:
            self.fh.write(report)
            self.fh.flush()
        except (BrokenPipeError, OSError) as exc:
            logger.warning("HID write failed: %s", exc)

    def _send_key(self, modifier: int, keycode: int):
        # Press.
        self._write_report(bytes([modifier & 0xFF, 0, keycode & 0xFF, 0, 0, 0, 0, 0]))
        # Release.
        self._write_report(bytes([0, 0, 0, 0, 0, 0, 0, 0]))
        time.sleep(self.inter_key_delay)

    def type_string(self, text: str):
        for ch in text or "":
            mapped = _keycode_for_char(ch)
            if mapped is None:
                logger.debug("Skipping unsupported char: %r", ch)
                continue
            modifier, keycode = mapped
            self._send_key(modifier, keycode)

    def type_payload(self, payload_name: str):
        actions = PAYLOADS.get(payload_name)
        if actions is None:
            logger.warning("Unknown payload: %s", payload_name)
            return f"Correction: Payload '{payload_name}' is not defined, meatbag."
        for action in actions:
            kind = action[0]
            if kind == "type":
                self.type_string(action[1])
            elif kind == "key":
                self._send_key(action[1], action[2])
            elif kind == "delay":
                time.sleep(action[1])
        return f"Statement: Payload '{payload_name}' delivered, meatbag."

    def close(self):
        if self.fh is not None:
            try:
                self.fh.close()
            finally:
                self.fh = None


def _w(path, value):
    """Write a value to a configfs node, raising on failure."""
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(value)


# Standard 65-byte USB HID keyboard report descriptor.
_HID_REPORT_DESCRIPTOR = bytes([
    0x05, 0x01,  # Usage Page (Generic Desktop)
    0x09, 0x06,  # Usage (Keyboard)
    0xA1, 0x01,  # Collection (Application)
    0x05, 0x07,  # Usage Page (Key Codes)
    0x19, 0xE0,  # Usage Minimum (224)
    0x29, 0xE7,  # Usage Maximum (231)
    0x15, 0x00,  # Logical Minimum (0)
    0x25, 0x01,  # Logical Maximum (1)
    0x75, 0x01,  # Report Size (1)
    0x95, 0x08,  # Report Count (8)
    0x81, 0x02,  # Input (Data, Variable, Absolute) ; modifier byte
    0x95, 0x01,  # Report Count (1)
    0x75, 0x08,  # Report Size (8)
    0x81, 0x03,  # Input (Constant) ; reserved byte
    0x95, 0x05,  # Report Count (5)
    0x75, 0x01,  # Report Size (1)
    0x05, 0x08,  # Usage Page (LEDs)
    0x19, 0x01,  # Usage Minimum (1)
    0x29, 0x05,  # Usage Maximum (5)
    0x91, 0x02,  # Output (Data, Variable, Absolute) ; LED report
    0x95, 0x01,  # Report Count (1)
    0x75, 0x03,  # Report Size (3)
    0x91, 0x03,  # Output (Constant) ; LED padding
    0x95, 0x06,  # Report Count (6)
    0x75, 0x08,  # Report Size (8)
    0x15, 0x00,  # Logical Minimum (0)
    0x25, 0x65,  # Logical Maximum (101)
    0x05, 0x07,  # Usage Page (Key Codes)
    0x19, 0x00,  # Usage Minimum (0)
    0x29, 0x65,  # Usage Maximum (101)
    0x81, 0x00,  # Input (Data, Array) ; key array (6 keys)
    0xC0,        # End Collection
])


def setup_usb_gadget() -> bool:
    """
    Configure a USB HID keyboard gadget via configfs. Must run as root with a
    UDC (USB Device Controller) available. Returns True on success.
    """
    configfs = "/sys/kernel/config"
    if not os.path.ismount(configfs) and not os.path.isdir(os.path.join(configfs, "usb_gadget")):
        logger.warning("configfs not mounted at %s; cannot create USB gadget.", configfs)
        return False

    g = USB_GADGET_PATH
    try:
        os.makedirs(g, exist_ok=True)
        _w(os.path.join(g, "idVendor"), "0x1d6b")
        _w(os.path.join(g, "idProduct"), "0x0104")
        _w(os.path.join(g, "bcdDevice"), "0x0100")
        _w(os.path.join(g, "bcdUSB"), "0x0200")

        strings = os.path.join(g, "strings", "0x409")
        os.makedirs(strings, exist_ok=True)
        _w(os.path.join(strings, "serialnumber"), "HK47-0001")
        _w(os.path.join(strings, "manufacturer"), "HK-47 Systems")
        _w(os.path.join(strings, "product"), "HK-47 HID Interface")

        func = os.path.join(g, "functions", "hid.usb0")
        os.makedirs(func, exist_ok=True)
        _w(os.path.join(func, "protocol"), "1")       # keyboard
        _w(os.path.join(func, "subclass"), "1")       # boot interface
        _w(os.path.join(func, "report_length"), "8")
        with open(os.path.join(func, "report_desc"), "wb") as fh:
            fh.write(_HID_REPORT_DESCRIPTOR)

        cfg = os.path.join(g, "configs", "c.1")
        cfg_strings = os.path.join(cfg, "strings", "0x409")
        os.makedirs(cfg_strings, exist_ok=True)
        _w(os.path.join(cfg_strings, "configuration"), "HK-47 HID Config")
        _w(os.path.join(cfg, "MaxPower"), "250")

        link = os.path.join(cfg, "hid.usb0")
        if not os.path.exists(link):
            os.symlink(func, link)

        # Bind to the first available UDC.
        udc_dir = "/sys/class/udc"
        udcs = os.listdir(udc_dir) if os.path.isdir(udc_dir) else []
        if not udcs:
            logger.warning("No UDC available; gadget created but not enabled.")
            return False
        _w(os.path.join(g, "UDC"), udcs[0])
        logger.info("USB HID gadget enabled on UDC %s.", udcs[0])
        return True
    except (OSError, PermissionError) as exc:
        logger.warning("USB gadget setup failed: %s", exc)
        return False
