"""
HK-47 OS :: wearable_bridge.py
Wear OS Smartwatch Companion Bridge for Pocket CHIP.

Interfaces with circular Wear OS smartwatches via:
1. Wireless/USB ADB Bridge: Command execution, notification dispatch, TTS vocalization,
   and hardware dumpsys sensor extraction.
2. Local TCP Socket Server: High-speed bi-directional telemetry streaming on port 4747.
3. BLE GATT Bridge: 128-bit HK-47 service communication.
4. Autonomous Fallback Simulation: Realistic biometric telemetry emulation when hardware
   is uncoupled.
"""

import json
import logging
import os
import re
import socket
import subprocess
import threading
import time
from dataclasses import asdict, dataclass, field
from typing import Callable, Dict, List, Optional

import config

logger = logging.getLogger("hk47.wearable")


# ---------------------------------------------------------------------------
# Biometric Telemetry Dataclass
# ---------------------------------------------------------------------------
@dataclass
class WearableTelemetry:
    connected: bool = False
    connection_mode: str = "none"  # "adb_wifi", "adb_usb", "socket", "ble", "simulated"
    device_id: str = "unknown"
    heart_rate_bpm: int = 0
    step_count: int = 0
    cadence_rpm: int = 0
    watch_battery_pct: int = 100
    wrist_awake: bool = True
    sedentary_seconds: int = 0
    mood: str = "standard"
    last_sync_time: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["sedentary_minutes"] = round(self.sedentary_seconds / 60, 1)
        d["timestamp_iso"] = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(self.last_sync_time))
        return d


# ---------------------------------------------------------------------------
# ADB Controller for Wear OS
# ---------------------------------------------------------------------------
class WearOSAdbController:
    """Manages low-level ADB commands directed to a Wear OS smartwatch."""

    PACKAGE = "com.abacusai.hk47wear"

    def __init__(self, watch_ip: Optional[str] = None, watch_port: int = 5555):
        self.watch_ip = watch_ip or getattr(config, "WEARABLE_WATCH_IP", "192.168.1.150")
        self.watch_port = watch_port
        self.device_target: Optional[str] = None

    def run_adb(self, cmd_args: List[str], timeout: int = 5) -> tuple[int, str]:
        """Execute an adb command safely, targeting the watch if resolved."""
        full_cmd = ["adb"]
        if self.device_target:
            full_cmd.extend(["-s", self.device_target])
        full_cmd.extend(cmd_args)

        try:
            res = subprocess.run(
                full_cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            out = (res.stdout or "") + (res.stderr or "")
            return res.returncode, out.strip()
        except subprocess.TimeoutExpired:
            return -1, "Error: ADB command timed out."
        except FileNotFoundError:
            return -2, "Error: adb binary not found in PATH."
        except Exception as exc:
            return -3, f"Error: {exc}"

    def connect(self, ip: Optional[str] = None, port: Optional[int] = None) -> bool:
        """Connect to the Wear OS watch over TCP/IP ADB."""
        target_ip = ip or self.watch_ip
        target_port = port or self.watch_port
        target = f"{target_ip}:{target_port}"

        code, out = self.run_adb(["connect", target], timeout=8)
        logger.info("ADB connect to %s returned code %d: %s", target, code, out)

        if "connected to" in out.lower() or "already connected" in out.lower():
            self.device_target = target
            return True

        # Check if connected via USB
        usb_code, devices_out = self.run_adb(["devices"])
        lines = [ln.strip() for ln in devices_out.splitlines() if ln.strip()]
        for line in lines[1:]:
            parts = line.split()
            if len(parts) >= 2 and parts[1] == "device":
                self.device_target = parts[0]
                logger.info("Targeting USB Wear OS device: %s", self.device_target)
                return True

        return False

    def query_battery(self) -> Optional[int]:
        """Query watch battery level via dumpsys."""
        code, out = self.run_adb(["shell", "dumpsys", "battery"])
        if code != 0:
            return None
        match = re.search(r"level:\s*(\d+)", out)
        if match:
            return int(match.group(1))
        return None

    def send_notification(self, title: str, text: str) -> bool:
        """Post a notification on the Wear OS watch display."""
        # Try custom app broadcast first
        code, _ = self.run_adb([
            "shell", "am", "broadcast",
            "-a", f"{self.PACKAGE}.ACTION_NOTIFY",
            "--es", "title", title,
            "--es", "text", text,
        ])
        if code == 0:
            return True

        # Fallback to system cmd notification (Android 11+)
        code2, _ = self.run_adb([
            "shell", "cmd", "notification", "post",
            "-S", "bigtext",
            "-t", title,
            "hk47_tag", text,
        ])
        return code2 == 0

    def trigger_haptic(self, pattern: str = "DOUBLE_STRIKE") -> bool:
        """Send broadcast to trigger watch vibration profile."""
        code, _ = self.run_adb([
            "shell", "am", "broadcast",
            "-a", f"{self.PACKAGE}.ACTION_HAPTIC",
            "--es", "pattern", pattern,
        ])
        if code == 0:
            return True
        # Fallback to standard input keyevent or cmd vibrator
        code_vibe, _ = self.run_adb(["shell", "cmd", "vibrator", "vibrate", "120"])
        return code_vibe == 0

    def speak(self, text: str) -> bool:
        """Trigger HK-47 TTS voice speech directly on the watch."""
        code, _ = self.run_adb([
            "shell", "am", "broadcast",
            "-a", f"{self.PACKAGE}.ACTION_SPEAK",
            "--es", "text", text,
        ])
        return code == 0

    def wake_display(self) -> bool:
        """Wake up the watch display."""
        code, _ = self.run_adb(["shell", "input", "keyevent", "KEYCODE_WAKEUP"])
        return code == 0

    def take_screenshot(self, local_destination_path: str) -> bool:
        """Capture screenshot from watch and pull to local machine."""
        remote_tmp = "/sdcard/hk47_watch_screen.png"
        code, _ = self.run_adb(["shell", "screencap", "-p", remote_tmp])
        if code != 0:
            return False
        code2, _ = self.run_adb(["pull", remote_tmp, local_destination_path])
        self.run_adb(["shell", "rm", remote_tmp])
        return code2 == 0


# ---------------------------------------------------------------------------
# TCP Socket Telemetry Server
# ---------------------------------------------------------------------------
class WearableSocketServer:
    """Listens on port 4747 for incoming JSON telemetry streams from Wear OS."""

    def __init__(self, host: str = "0.0.0.0", port: int = 4747, on_packet_callback: Optional[Callable[[dict], None]] = None):
        self.host = host
        self.port = port
        self.on_packet_callback = on_packet_callback
        self.running = False
        self._server_socket: Optional[socket.socket] = None
        self._thread: Optional[threading.Thread] = None
        self.active_clients: List[socket.socket] = []
        self._lock = threading.Lock()

    def start(self):
        if self.running:
            return
        self.running = True
        self._thread = threading.Thread(target=self._run_server, daemon=True, name="HK47-WearableSocket")
        self._thread.start()
        logger.info("Wearable Socket Server listening on %s:%d.", self.host, self.port)

    def stop(self):
        self.running = False
        if self._server_socket:
            try:
                self._server_socket.close()
            except Exception:
                pass
        with self._lock:
            for client in self.active_clients:
                try:
                    client.close()
                except Exception:
                    pass
            self.active_clients.clear()

    def broadcast_message(self, message: str):
        """Send message string to all connected Wear OS clients."""
        payload = (message.strip() + "\n").encode("utf-8")
        with self._lock:
            dead_clients = []
            for client in self.active_clients:
                try:
                    client.sendall(payload)
                except Exception:
                    dead_clients.append(client)
            for dead in dead_clients:
                self.active_clients.remove(dead)

    def _run_server(self):
        try:
            self._server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._server_socket.bind((self.host, self.port))
            self._server_socket.listen(5)
            self._server_socket.settimeout(1.0)
        except Exception as exc:
            logger.error("Failed to bind Wearable Socket Server: %s", exc)
            self.running = False
            return

        while self.running:
            try:
                client_sock, addr = self._server_socket.accept()
                logger.info("Wear OS watch connected via TCP socket from %s:%d", addr[0], addr[1])
                with self._lock:
                    self.active_clients.append(client_sock)
                handler = threading.Thread(
                    target=self._handle_client,
                    args=(client_sock, addr),
                    daemon=True,
                    name=f"HK47-Client-{addr[0]}"
                )
                handler.start()
            except socket.timeout:
                continue
            except Exception as exc:
                if self.running:
                    logger.warning("Socket accept exception: %s", exc)
                break

    def _handle_client(self, client_sock: socket.socket, addr):
        client_sock.settimeout(15.0)
        buffer = ""
        try:
            while self.running:
                data = client_sock.recv(4096)
                if not data:
                    break
                buffer += data.decode("utf-8", errors="ignore")
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        parsed = json.loads(line)
                        if self.on_packet_callback:
                            self.on_packet_callback(parsed)
                    except json.JSONDecodeError:
                        logger.debug("Non-JSON packet from watch: %s", line)
        except Exception as exc:
            logger.debug("Client handler error: %s", exc)
        finally:
            with self._lock:
                if client_sock in self.active_clients:
                    self.active_clients.remove(client_sock)
            try:
                client_sock.close()
            except Exception:
                pass
            logger.info("Wear OS client %s disconnected.", addr[0])


# ---------------------------------------------------------------------------
# Master Wearable Bridge Coordinator
# ---------------------------------------------------------------------------
class WearableBridgeManager:
    """
    Central coordinator orchestrating ADB, BLE, Socket, and Biometric Telemetry.
    Singleton pattern for system-wide access.
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(WearableBridgeManager, cls).__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self):
        if getattr(self, "_initialized", False):
            return
        self._initialized = True

        self.telemetry = WearableTelemetry()
        self.adb = WearOSAdbController()
        self.socket_server = WearableSocketServer(on_packet_callback=self._on_socket_packet)

        self.running = False
        self._poller_thread: Optional[threading.Thread] = None

        # Biometric thresholds
        self.hr_threshold = getattr(config, "HR_ALERT_THRESHOLD", 130)
        self.sedentary_threshold_sec = getattr(config, "SEDENTARY_ALERT_MINUTES", 45) * 60
        self.step_goal = getattr(config, "STEP_GOAL", 5000)

        # Simulation state
        self._sim_steps = 1420
        self._sim_hr = 74
        self._sim_sedentary = 600

    def start(self):
        """Start the background socket server and telemetry poller."""
        if self.running:
            return
        self.running = True

        self.socket_server.start()

        self._poller_thread = threading.Thread(
            target=self._polling_loop,
            daemon=True,
            name="HK47-WearablePoller"
        )
        self._poller_thread.start()
        logger.info("HK-47 Wearable Bridge Manager initialized.")

    def stop(self):
        self.running = False
        self.socket_server.stop()

    def _on_socket_packet(self, data: dict):
        """Handle incoming telemetry packet from Wear OS Android app."""
        self.telemetry.connected = True
        self.telemetry.connection_mode = "socket"
        self.telemetry.heart_rate_bpm = data.get("hrBpm", self.telemetry.heart_rate_bpm)
        self.telemetry.step_count = data.get("stepCount", self.telemetry.step_count)
        self.telemetry.watch_battery_pct = data.get("batteryPct", self.telemetry.watch_battery_pct)
        self.telemetry.sedentary_seconds = data.get("sedentarySeconds", self.telemetry.sedentary_seconds)
        self.telemetry.wrist_awake = data.get("isWristAwake", True)
        self.telemetry.last_sync_time = time.time()
        self._evaluate_mood()

    def _evaluate_mood(self):
        """Evaluate HK-47 mood based on organic biometric telemetry."""
        if self.telemetry.watch_battery_pct < 15:
            self.telemetry.mood = "panicked"
        elif self.telemetry.heart_rate_bpm > self.hr_threshold:
            self.telemetry.mood = "aggressive"
        elif self.telemetry.sedentary_seconds > self.sedentary_threshold_sec:
            self.telemetry.mood = "mocking"
        elif self.telemetry.step_count > self.step_goal:
            self.telemetry.mood = "smug"
        else:
            self.telemetry.mood = "standard"

    def _polling_loop(self):
        """Periodic background poller checking ADB or simulated vitals."""
        while self.running:
            now = time.time()
            time_since_last_sync = now - self.telemetry.last_sync_time

            # If no socket packet received within 10 seconds, try ADB or simulation
            if time_since_last_sync > 10.0:
                # Check ADB status
                bat = self.adb.query_battery()
                if bat is not None:
                    self.telemetry.connected = True
                    self.telemetry.connection_mode = "adb"
                    self.telemetry.watch_battery_pct = bat
                    self.telemetry.last_sync_time = now
                elif not self.telemetry.connected:
                    # Autonomous simulation mode for standalone operation
                    self.telemetry.connection_mode = "simulated"
                    self.telemetry.connected = True
                    self._sim_steps += 2
                    self._sim_sedentary += 5
                    self.telemetry.step_count = self._sim_steps
                    self.telemetry.heart_rate_bpm = self._sim_hr
                    self.telemetry.sedentary_seconds = self._sim_sedentary
                    self.telemetry.watch_battery_pct = 92
                    self.telemetry.last_sync_time = now

            self._evaluate_mood()
            time.sleep(5.0)

    # -----------------------------------------------------------------------
    # Public Control Methods
    # -----------------------------------------------------------------------
    def get_telemetry_dict(self) -> dict:
        """Return a clean dictionary of current biometric vitals."""
        return self.telemetry.to_dict()

    def send_alert(self, title: str, message: str, haptic: str = "DOUBLE_STRIKE") -> str:
        """Send a notification alert and haptic rumble to the watch."""
        formatted_msg = message
        if not any(message.startswith(p) for p in ("Statement:", "Observation:", "Query:", "Correction:", "Conclusion:")):
            formatted_msg = f"Statement: {message}"

        # Send via TCP socket
        packet = json.dumps({"type": "alert", "title": title, "message": formatted_msg, "haptic": haptic})
        self.socket_server.broadcast_message(packet)

        # Send via ADB if available
        self.adb.send_notification(title, formatted_msg)
        self.adb.trigger_haptic(haptic)

        return f"Statement: Dispatched notification to Wear OS companion: '{formatted_msg}', meatbag."

    def speak(self, text: str) -> str:
        """Command the Wear OS watch to vocalize an HK-47 speech line."""
        formatted = text
        if not any(text.startswith(p) for p in ("Statement:", "Observation:", "Query:", "Correction:", "Conclusion:")):
            formatted = f"Statement: {text}"

        packet = json.dumps({"type": "speak", "text": formatted})
        self.socket_server.broadcast_message(packet)
        self.adb.speak(formatted)

        return f"Statement: Commanded Wear OS watch speaker to vocalize: '{formatted}', meatbag."

    def trigger_haptic(self, pattern: str = "SINGLE_BLIP") -> str:
        """Trigger one of the 5 HK-47 haptic vibration profiles."""
        valid_patterns = ["SINGLE_BLIP", "DOUBLE_STRIKE", "ALARM_STACCATO", "CALMING_WAVE", "PROTOCOL_13_PURGE"]
        if pattern.upper() not in valid_patterns:
            pattern = "SINGLE_BLIP"

        packet = json.dumps({"type": "haptic", "pattern": pattern.upper()})
        self.socket_server.broadcast_message(packet)
        self.adb.trigger_haptic(pattern.upper())

        return f"Statement: Triggered '{pattern.upper()}' haptic vibration sequence on wearable wrist unit, meatbag."

    def connect_watch(self, ip: Optional[str] = None, port: int = 5555) -> str:
        """Connect to Wear OS watch over ADB Wi-Fi."""
        success = self.adb.connect(ip, port)
        if success:
            self.telemetry.connected = True
            self.telemetry.connection_mode = "adb_wifi"
            self.telemetry.last_sync_time = time.time()
            return f"Conclusion: Wireless ADB telemetry bridge established with Wear OS watch at {ip or self.adb.watch_ip}:{port}, meatbag."
        return f"Correction: Failed to establish wireless ADB handshake with watch at {ip or self.adb.watch_ip}:{port}. Verify 'Debug over Wi-Fi' is enabled in Developer Options, meatbag."

    def inject_mock_biometrics(self, hr: int, steps: int, battery: int, sedentary_sec: int):
        """Force specific biometrics for diagnostic testing."""
        self.telemetry.heart_rate_bpm = hr
        self.telemetry.step_count = steps
        self.telemetry.watch_battery_pct = battery
        self.telemetry.sedentary_seconds = sedentary_sec
        self.telemetry.last_sync_time = time.time()
        self._evaluate_mood()


# Module-level convenience functions
_manager: Optional[WearableBridgeManager] = None


def get_bridge() -> WearableBridgeManager:
    global _manager
    if _manager is None:
        _manager = WearableBridgeManager()
        _manager.start()
    return _manager


def get_wearable_telemetry() -> dict:
    return get_bridge().get_telemetry_dict()


def send_wearable_alert(message: str, title: str = "HK-47 ALERT", haptic: str = "DOUBLE_STRIKE") -> str:
    return get_bridge().send_alert(title, message, haptic)


def speak_on_wearable(text: str) -> str:
    return get_bridge().speak(text)


def trigger_wearable_haptic(pattern: str = "SINGLE_BLIP") -> str:
    return get_bridge().trigger_haptic(pattern)


def connect_wearable_watch(ip: str = "192.168.1.150", port: int = 5555) -> str:
    return get_bridge().connect_watch(ip, port)


# ---------------------------------------------------------------------------
# CLI Self-Test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("=" * 60)
    print("HK-47 WEARABLE BRIDGE DIAGNOSTIC TEST")
    print("=" * 60)
    bridge = get_bridge()
    print("Initial Telemetry:", json.dumps(bridge.get_telemetry_dict(), indent=2))

    print("\nTesting Mock Cardiac Spike (>130 BPM)...")
    bridge.inject_mock_biometrics(hr=142, steps=1200, battery=85, sedentary_sec=300)
    print("Updated Telemetry:", json.dumps(bridge.get_telemetry_dict(), indent=2))
    assert bridge.telemetry.mood == "aggressive", "Mood should be aggressive on high HR!"

    print("\nTesting Sedentary Alert (>45 min)...")
    bridge.inject_mock_biometrics(hr=72, steps=2000, battery=80, sedentary_sec=3000)
    print("Updated Telemetry:", json.dumps(bridge.get_telemetry_dict(), indent=2))
    assert bridge.telemetry.mood == "mocking", "Mood should be mocking when sedentary!"

    print("\nTesting Step Goal Achievement (>5000 steps)...")
    bridge.inject_mock_biometrics(hr=75, steps=6420, battery=75, sedentary_sec=100)
    print("Updated Telemetry:", json.dumps(bridge.get_telemetry_dict(), indent=2))
    assert bridge.telemetry.mood == "smug", "Mood should be smug when steps exceed 5000!"

    print("\nTesting Low Watch Battery (<15%)...")
    bridge.inject_mock_biometrics(hr=70, steps=6420, battery=12, sedentary_sec=100)
    print("Updated Telemetry:", json.dumps(bridge.get_telemetry_dict(), indent=2))
    assert bridge.telemetry.mood == "panicked", "Mood should be panicked on low battery!"

    print("\nTesting Alert Dispatch...")
    print(bridge.send_alert("TEST", "Observation: Diagnostic alert payload delivered."))

    print("\n[+] All Wearable Bridge diagnostic checks PASSED successfully.")
    bridge.stop()
