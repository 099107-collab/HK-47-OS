"""
HK-47 OS :: input_listener.py
Background evdev keyboard listener for Pocket CHIP hardware key macros:
  Fn + S -> Telemetry dump
  Fn + L -> Backlight toggle (dim/eco/full)
  Fn + Q -> Graceful shutdown
  Fn + P -> Protocol-13 purge
  Fn + W -> WiFi scan
  Fn + B -> BLE scan

Degrades gracefully to a no-op loop when evdev or input devices are absent.
"""

import asyncio
import glob
import logging
import threading

logger = logging.getLogger("hk47.input")

try:
    import evdev
    from evdev import ecodes
    _EVDEV_AVAILABLE = True
except ImportError:
    evdev = None
    ecodes = None
    _EVDEV_AVAILABLE = False


class KeyMacroListener:
    """Listens for hardware keyboard chords on /dev/input/event*."""

    def __init__(self, callbacks: dict):
        self.callbacks = callbacks or {}
        self.running = False
        self.device = None
        self.thread = None
        self.loop = None
        self._fn_down = False

    def _find_keyboard_device(self):
        if not _EVDEV_AVAILABLE:
            return None
        # Enumerate event nodes.
        nodes = sorted(glob.glob("/dev/input/event*"))
        for node in nodes:
            try:
                dev = evdev.InputDevice(node)
                caps = dev.capabilities()
                # Check for EV_KEY capability and standard alphanumeric keys.
                if ecodes.EV_KEY in caps:
                    keys = caps[ecodes.EV_KEY]
                    if ecodes.KEY_A in keys and ecodes.KEY_ENTER in keys:
                        logger.info("Found keyboard device: %s (%s)", dev.name, node)
                        return dev
            except (PermissionError, OSError) as exc:
                logger.debug("Cannot inspect %s: %s", node, exc)
        return None

    def _fire(self, macro_name):
        cb = self.callbacks.get(macro_name)
        if not cb:
            return
        try:
            cb()
        except Exception as exc:
            logger.warning("Macro callback '%s' failed: %s", macro_name, exc)

    def _handle_key_event(self, event):
        # event.value: 0=up, 1=down, 2=hold
        code = event.code
        val = event.value

        # On Pocket CHIP, Fn often maps to KEY_FN, KEY_COMPOSE, KEY_LEFTALT, or KEY_F1.
        fn_keys = {
            getattr(ecodes, "KEY_FN", -1),
            getattr(ecodes, "KEY_COMPOSE", -1),
            getattr(ecodes, "KEY_LEFTALT", -1),
            getattr(ecodes, "KEY_F1", -1),
        }

        if code in fn_keys:
            self._fn_down = (val != 0)
            return

        if val == 1 and self._fn_down:
            if code == getattr(ecodes, "KEY_S", -1):
                self._fire("telemetry")
            elif code == getattr(ecodes, "KEY_L", -1):
                self._fire("toggle_backlight")
            elif code == getattr(ecodes, "KEY_Q", -1):
                self._fire("exit")
            elif code == getattr(ecodes, "KEY_P", -1):
                self._fire("protocol_13")
            elif code == getattr(ecodes, "KEY_W", -1):
                self._fire("wifi_scan")
            elif code == getattr(ecodes, "KEY_B", -1):
                self._fire("ble_scan")

    async def _reader(self):
        if self.device is None:
            return
        try:
            async for event in self.device.async_read_loop():
                if not self.running:
                    break
                if event.type == ecodes.EV_KEY:
                    self._handle_key_event(event)
        except (OSError, asyncio.CancelledError):
            pass

    def _thread_target(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        try:
            self.loop.run_until_complete(self._reader())
        finally:
            try:
                self.loop.close()
            except Exception:
                pass

    def start(self):
        if self.running:
            return
        if not _EVDEV_AVAILABLE:
            logger.warning("evdev not available; hardware macro listener inactive.")
            return

        self.device = self._find_keyboard_device()
        if self.device is None:
            logger.warning("No keyboard input device found; running without hardware macros.")
            return

        self.running = True
        self.thread = threading.Thread(
            target=self._thread_target, name="HK47InputListener", daemon=True
        )
        self.thread.start()
        logger.info("Keyboard macro listener active.")

    def stop(self):
        self.running = False
        if self.loop and self.loop.is_running():
            self.loop.call_soon_threadsafe(self.loop.stop)
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=2)
        if self.device:
            try:
                self.device.close()
            except Exception:
                pass
            self.device = None
        self.thread = None
        logger.info("Keyboard macro listener stopped.")
