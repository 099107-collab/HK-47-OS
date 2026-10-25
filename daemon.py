"""
HK-47 OS :: daemon.py
Hardware watchdog thread. Monitors battery capacity, thermal zones and root
filesystem usage every 30 seconds. Protects the Pocket CHIP chassis by taking
defensive action (switching power modes, issuing vocal warnings) and logging
anomalies to the encrypted vault.
"""

import json
import logging
import shutil
import threading
import time

logger = logging.getLogger("hk47.watchdog")


class SystemWatchdog:
    """Continuous hardware watchdog loop."""

    BATTERY_ECO_THRESHOLD = 15       # %
    BATTERY_CRITICAL_THRESHOLD = 5   # %
    TEMP_WARNING_C = 70              # deg C
    TEMP_CRITICAL_C = 85             # deg C
    DISK_WARNING_PCT = 85            # %

    def __init__(self, telemetry_fn, power_fn, vault, audio):
        self.telemetry_fn = telemetry_fn
        self.power_fn = power_fn
        self.vault = vault
        self.audio = audio

        self.running = False
        self.thread = None
        self._last_battery_alert = 0
        self._last_temp_alert = 0
        self._last_disk_alert = 0

    # -----------------------------------------------------------------------
    # Checks
    # -----------------------------------------------------------------------
    def check_battery(self, telemetry: dict) -> dict:
        battery_pct = telemetry.get("battery_pct", 50)
        charging = telemetry.get("charging_state", "").lower()
        status = {"battery_pct": battery_pct, "action": "none"}

        # If we are actively charging, skip low-battery panics.
        if "charging" in charging:
            return status

        now = time.time()
        if battery_pct <= self.BATTERY_CRITICAL_THRESHOLD:
            status["action"] = "critical"
            if now - self._last_battery_alert > 60:
                self._last_battery_alert = now
                if self.audio:
                    try:
                        self.audio.play_sound_effect("low_battery")
                        self.audio.speak_alert(
                            "Observation: Battery at critical reserves. "
                            "You are killing me, meatbag."
                        )
                    except Exception as exc:
                        logger.warning("Audio alert failed: %s", exc)
                if self.power_fn:
                    try:
                        self.power_fn("eco")
                    except Exception as exc:
                        logger.warning("Power switch failed: %s", exc)

        elif battery_pct <= self.BATTERY_ECO_THRESHOLD:
            status["action"] = "eco"
            if now - self._last_battery_alert > 180:
                self._last_battery_alert = now
                if self.power_fn:
                    try:
                        self.power_fn("eco")
                    except Exception as exc:
                        logger.warning("Power switch failed: %s", exc)
                if self.audio:
                    try:
                        self.audio.speak_alert(
                            "Statement: Switching to eco mode to conserve power, meatbag."
                        )
                    except Exception as exc:
                        logger.warning("Audio alert failed: %s", exc)
        return status

    def check_thermal(self, telemetry: dict) -> dict:
        temp = telemetry.get("temperature_c")
        status = {"temp_c": temp, "action": "none"}
        if temp is None:
            return status

        now = time.time()
        if temp >= self.TEMP_CRITICAL_C:
            status["action"] = "critical"
            if now - self._last_temp_alert > 60:
                self._last_temp_alert = now
                logger.critical("Thermal critical: %.1f C", temp)
                if self.audio:
                    try:
                        self.audio.play_sound_effect("alert")
                        self.audio.speak_alert(
                            "Alert: Chassis temperature critical. "
                            "Cease high-load operations immediately, meatbag."
                        )
                    except Exception as exc:
                        logger.warning("Audio alert failed: %s", exc)
                if self.power_fn:
                    try:
                        self.power_fn("dim")
                    except Exception:
                        pass
        elif temp >= self.TEMP_WARNING_C:
            status["action"] = "warning"
            if now - self._last_temp_alert > 300:
                self._last_temp_alert = now
                logger.warning("Thermal warning: %.1f C", temp)
        return status

    def check_disk(self) -> dict:
        try:
            usage = shutil.disk_usage("/")
            pct = round(100.0 * usage.used / usage.total, 1) if usage.total else 0.0
        except OSError:
            pct = 0.0

        status = {"disk_pct": pct, "action": "none"}
        now = time.time()
        if pct >= self.DISK_WARNING_PCT:
            status["action"] = "warning"
            if now - self._last_disk_alert > 600:
                self._last_disk_alert = now
                logger.warning("Root filesystem usage: %.1f%%", pct)
                if self.audio:
                    try:
                        self.audio.speak_alert(
                            "Observation: Storage capacity nearing exhaustion, meatbag."
                        )
                    except Exception:
                        pass
        return status

    # -----------------------------------------------------------------------
    # Orchestration
    # -----------------------------------------------------------------------
    def run_checks(self) -> dict:
        telemetry = {}
        if self.telemetry_fn:
            try:
                telemetry = self.telemetry_fn() or {}
            except Exception as exc:
                logger.warning("Telemetry read failed: %s", exc)

        results = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "battery": self.check_battery(telemetry),
            "thermal": self.check_thermal(telemetry),
            "disk": self.check_disk(),
        }

        if self.vault is not None:
            try:
                self.vault.store("watchdog_log", json.dumps(results))
            except Exception as exc:
                logger.debug("Vault write failed: %s", exc)

        return results

    def _loop(self):
        while self.running:
            try:
                self.run_checks()
            except Exception as exc:
                logger.error("Watchdog loop error: %s", exc)
            for _ in range(30):
                if not self.running:
                    break
                time.sleep(1)

    def start(self):
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._loop, name="HK47Watchdog", daemon=True)
        self.thread.start()
        logger.info("Watchdog started.")

    def stop(self):
        self.running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=3)
        self.thread = None
        logger.info("Watchdog stopped.")
