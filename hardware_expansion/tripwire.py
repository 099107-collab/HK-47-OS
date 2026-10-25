"""
HK-47 OS :: hardware_expansion/tripwire.py
Anti-tamper continuity tripwire monitor for the Pocket CHIP chassis. Watches
a GPIO pin (default GPIO27) with an internal pull-up. A continuity break
(case opened / wire cut) triggers audio alarms, emergency logging, and executes
Protocol-13 to scrub sensitive data from the vault.
"""

import logging

try:
    import config
    _TRIPWIRE_PIN = getattr(config, "TRIPWIRE_GPIO_PIN", 27)
except ImportError:
    _TRIPWIRE_PIN = 27

logger = logging.getLogger("hk47.tripwire")

try:
    import RPi.GPIO as GPIO
    _GPIO_AVAILABLE = True
except (ImportError, RuntimeError):
    GPIO = None
    _GPIO_AVAILABLE = False


class TripwireMonitor:
    """Watches a tamper switch on a GPIO pin."""

    def __init__(self, gpio_pin: int = _TRIPWIRE_PIN, purge_fn=None, audio_fn=None, log_fn=None):
        self.gpio_pin = gpio_pin
        self.purge_fn = purge_fn
        self.audio_fn = audio_fn
        self.log_fn = log_fn

        self.armed = False
        self.running = False

    def setup(self):
        """Configure the GPIO pin with internal pull-up."""
        if not _GPIO_AVAILABLE:
            logger.info("Tripwire running in simulation mode (GPIO%d).", self.gpio_pin)
            return
        try:
            GPIO.setwarnings(False)
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(self.gpio_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            logger.info("Tripwire configured on GPIO%d with PULL_UP.", self.gpio_pin)
        except Exception as exc:
            logger.warning("Tripwire GPIO setup failed: %s", exc)

    def _trigger(self, channel=None):
        """Dispatched when the loop breaks."""
        if not self.armed:
            logger.info("Tripwire edge detected on GPIO%d but monitor is disarmed.", self.gpio_pin)
            return

        logger.critical("TRIPWIRE TRIGGERED ON GPIO%d — CHASSIS TAMPER DETECTED!", self.gpio_pin)

        if self.log_fn:
            try:
                self.log_fn("TRIPWIRE TRIGGERED - CASE OPENED / WIRE CUT")
            except Exception as exc:
                logger.warning("Tripwire log failed: %s", exc)

        if self.audio_fn:
            try:
                self.audio_fn("tamper")
            except Exception as exc:
                logger.warning("Tripwire audio failed: %s", exc)

        if self.purge_fn:
            try:
                logger.critical("Initiating Protocol-13 emergency purge...")
                self.purge_fn()
            except Exception as exc:
                logger.critical("Protocol-13 execution failed: %s", exc)

    def arm(self):
        self.armed = True
        logger.info("Tripwire armed.")

    def disarm(self):
        self.armed = False
        logger.info("Tripwire disarmed.")

    def start(self):
        """Attach hardware interrupt and arm the monitor."""
        if self.running:
            return
        self.setup()
        self.armed = True
        self.running = True

        if _GPIO_AVAILABLE:
            try:
                GPIO.add_event_detect(
                    self.gpio_pin,
                    GPIO.FALLING,
                    callback=self._trigger,
                    bouncetime=200,
                )
                logger.info("Tripwire interrupt attached to GPIO%d.", self.gpio_pin)
            except Exception as exc:
                logger.warning("add_event_detect failed on GPIO%d: %s", self.gpio_pin, exc)

    def stop(self):
        """Detach hardware interrupt."""
        self.armed = False
        self.running = False
        if _GPIO_AVAILABLE:
            try:
                GPIO.remove_event_detect(self.gpio_pin)
            except Exception:
                pass
        logger.info("Tripwire stopped.")
