"""
HK-47 OS :: hardware_expansion/gps_tools.py
NMEA sentence parser and continuous location tracker for UART GPS modules
(default /dev/ttyS1 at 9600 baud). Degrades to simulation mode with fallback
coordinates if the serial device is absent.
"""

import json
import logging
import threading
import time

try:
    import serial
    _SERIAL_AVAILABLE = True
except ImportError:
    serial = None
    _SERIAL_AVAILABLE = False

try:
    import config
    _DEFAULT_PORT = getattr(config, "GPS_UART", "/dev/ttyS1")
    _DEFAULT_BAUD = getattr(config, "GPS_BAUD", 9600)
except ImportError:
    _DEFAULT_PORT = "/dev/ttyS1"
    _DEFAULT_BAUD = 9600

logger = logging.getLogger("hk47.gps")


class GPSTracker:
    """NMEA GPS receiver reader with background track logging."""

    def __init__(self, port: str = _DEFAULT_PORT, baud: int = _DEFAULT_BAUD):
        self.port = port
        self.baud = baud
        self.ser = None
        self.running = False
        self.thread = None

        if _SERIAL_AVAILABLE:
            try:
                self.ser = serial.Serial(self.port, self.baud, timeout=1.0)
                logger.info("GPS opened on %s @ %d baud.", self.port, self.baud)
            except Exception as exc:
                logger.warning("GPS port %s unavailable (%s); using simulation mode.",
                               self.port, exc)
                self.ser = None
        else:
            logger.warning("pyserial not installed; GPS running in simulation mode.")

    # -----------------------------------------------------------------------
    # NMEA conversions
    # -----------------------------------------------------------------------
    @staticmethod
    def _convert_nmea_coord(coord: str, direction: str) -> float:
        """Convert DDMM.MMMM or DDDMM.MMMM string into signed decimal degrees."""
        if not coord or not direction:
            return 0.0
        try:
            val = float(coord)
            degrees = int(val / 100)
            minutes = val - (degrees * 100)
            decimal = degrees + (minutes / 60.0)
            if direction.upper() in ("S", "W"):
                decimal = -decimal
            return round(decimal, 6)
        except (ValueError, TypeError):
            return 0.0

    def _parse_gprmc(self, sentence: str) -> dict:
        """Parse $GPRMC: status, lat, lon, speed (knots), date."""
        parts = sentence.split(",")
        if len(parts) < 10 or parts[2] != "A":
            return None
        return {
            "status": "valid",
            "lat": self._convert_nmea_coord(parts[3], parts[4]),
            "lon": self._convert_nmea_coord(parts[5], parts[6]),
            "speed_knots": float(parts[7]) if parts[7] else 0.0,
            "date": parts[9],
        }

    def _parse_gpgga(self, sentence: str) -> dict:
        """Parse $GPGGA: lat, lon, fix_quality, satellites, altitude."""
        parts = sentence.split(",")
        if len(parts) < 10:
            return None
        fix_q = int(parts[6]) if parts[6] else 0
        if fix_q == 0:
            return None
        return {
            "fix_quality": fix_q,
            "satellites": int(parts[7]) if parts[7] else 0,
            "altitude": float(parts[9]) if parts[9] else 0.0,
            "lat": self._convert_nmea_coord(parts[2], parts[3]),
            "lon": self._convert_nmea_coord(parts[4], parts[5]),
        }

    # -----------------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------------
    def get_location(self) -> dict:
        """
        Read until GPRMC and GPGGA sentences have been observed, or timeout.
        Returns a dictionary with lat, lon, altitude, speed_knots, satellites, etc.
        """
        # Simulation fallback if no real hardware is connected.
        if self.ser is None:
            return {
                "lat": 0.0,
                "lon": 0.0,
                "altitude": 0.0,
                "speed_knots": 0.0,
                "satellites": 0,
                "fix_quality": 0,
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "status": "simulated",
            }

        rmc = None
        gga = None
        deadline = time.time() + 3.0

        try:
            while time.time() < deadline and (rmc is None or gga is None):
                line = self.ser.readline().decode("ascii", errors="ignore").strip()
                if line.startswith(("$GPRMC", "$GNRMC")):
                    parsed = self._parse_gprmc(line)
                    if parsed:
                        rmc = parsed
                elif line.startswith(("$GPGGA", "$GNGGA")):
                    parsed = self._parse_gpgga(line)
                    if parsed:
                        gga = parsed
        except Exception as exc:
            logger.warning("Error reading GPS stream: %s", exc)

        lat = (rmc and rmc.get("lat")) or (gga and gga.get("lat")) or 0.0
        lon = (rmc and rmc.get("lon")) or (gga and gga.get("lon")) or 0.0
        return {
            "lat": lat,
            "lon": lon,
            "altitude": (gga and gga.get("altitude")) or 0.0,
            "speed_knots": (rmc and rmc.get("speed_knots")) or 0.0,
            "satellites": (gga and gga.get("satellites")) or 0,
            "fix_quality": (gga and gga.get("fix_quality")) or 0,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "status": "fix" if (rmc or gga) else "no_fix",
        }

    def start_tracking(self, vault=None, interval: int = 30):
        """Continuously collect coordinates and persist them to the vault."""
        if self.running:
            return
        self.running = True

        def _track_loop():
            while self.running:
                loc = self.get_location()
                if vault is not None:
                    try:
                        raw = vault.retrieve("gps_track")
                        history = json.loads(raw) if raw else []
                        history.append(loc)
                        if len(history) > 200:
                            history = history[-200:]
                        vault.store("gps_track", json.dumps(history))
                    except Exception as exc:
                        logger.debug("GPS vault store failed: %s", exc)
                for _ in range(interval):
                    if not self.running:
                        break
                    time.sleep(1)

        self.thread = threading.Thread(
            target=_track_loop, name="HK47GPSTracker", daemon=True
        )
        self.thread.start()
        logger.info("GPS tracking started (interval=%ds).", interval)

    def stop(self):
        self.running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=2)
        self.thread = None
        if self.ser:
            try:
                self.ser.close()
            except Exception:
                pass
            self.ser = None
        logger.info("GPS tracker stopped.")
