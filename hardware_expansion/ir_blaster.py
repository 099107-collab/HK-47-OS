"""
HK-47 OS :: hardware_expansion/ir_blaster.py
Infrared blaster supporting the NEC protocol modulated on a 38kHz carrier.
Drives an IR LED connected to a GPIO pin (default GPIO17). Gracefully mocks
GPIO operations when RPi.GPIO is absent or unprivileged.
"""

import logging
import time

try:
    import config
    _IR_PIN = getattr(config, "IR_GPIO_PIN", 17)
except ImportError:
    _IR_PIN = 17

logger = logging.getLogger("hk47.ir")

# Attempt RPi.GPIO import; mock on failure.
try:
    import RPi.GPIO as GPIO
    _GPIO_AVAILABLE = True
except (ImportError, RuntimeError):
    GPIO = None
    _GPIO_AVAILABLE = False


# ---------------------------------------------------------------------------
# NEC protocol timings (in microseconds)
# ---------------------------------------------------------------------------
NEC_CARRIER_HZ = 38000
NEC_HDR_MARK_US = 9000
NEC_HDR_SPACE_US = 4500
NEC_BIT_MARK_US = 560
NEC_ONE_SPACE_US = 1690
NEC_ZERO_SPACE_US = 560
NEC_TRAIL_MARK_US = 560


def encode_nec(address: int, command: int) -> list:
    """
    Encode an 8-bit address and 8-bit command into NEC pulse/space durations (us).
    The standard NEC packet sends:
      - 9ms mark + 4.5ms space (header)
      - address (8 bits LSB first) + ~address (8 bits)
      - command (8 bits LSB first) + ~command (8 bits)
      - 560us trailing mark
    Returns a list of integer microsecond durations: [mark, space, mark, space, ...].
    """
    address &= 0xFF
    command &= 0xFF
    addr_inv = (~address) & 0xFF
    cmd_inv = (~command) & 0xFF

    payload = (
        f"{address:08b}"[::-1]
        + f"{addr_inv:08b}"[::-1]
        + f"{command:08b}"[::-1]
        + f"{cmd_inv:08b}"[::-1]
    )

    durations = [NEC_HDR_MARK_US, NEC_HDR_SPACE_US]
    for bit in payload:
        durations.append(NEC_BIT_MARK_US)
        if bit == "1":
            durations.append(NEC_ONE_SPACE_US)
        else:
            durations.append(NEC_ZERO_SPACE_US)
    durations.append(NEC_TRAIL_MARK_US)
    return durations


def transmit_ir(pulse_durations: list, gpio_pin: int = _IR_PIN) -> None:
    """
    Transmit an IR waveform. When RPi.GPIO is present, uses software PWM at 38kHz.
    Otherwise logs the waveform for simulation mode.
    """
    if not _GPIO_AVAILABLE:
        logger.info(
            "IR (simulated): %d pulses on GPIO%d (38kHz carrier).",
            len(pulse_durations),
            gpio_pin,
        )
        return

    try:
        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(gpio_pin, GPIO.OUT, initial=GPIO.LOW)
        pwm = GPIO.PWM(gpio_pin, NEC_CARRIER_HZ)

        # Iterate alternating mark (PWM 50%) and space (PWM 0%).
        is_mark = True
        for duration_us in pulse_durations:
            seconds = duration_us / 1_000_000.0
            if is_mark:
                pwm.start(50.0)
            else:
                pwm.ChangeDutyCycle(0.0)
            time.sleep(seconds)
            is_mark = not is_mark

        pwm.stop()
        GPIO.output(gpio_pin, GPIO.LOW)
    except Exception as exc:
        logger.warning("IR transmit failed on GPIO%d: %s", gpio_pin, exc)


# Well-known universal power toggle codes (address, command).
UNIVERSAL_CODES = {
    "tv": (0x04, 0x08),            # Standard NEC TV power
    "projector": (0x4D, 0x0A),     # Common projector power toggle
    "av_receiver": (0x20, 0x12),   # Common audio receiver power toggle
}


def send_power_signal(device_type: str, gpio_pin: int = _IR_PIN) -> str:
    """Transmit a power-toggle NEC code for the requested device category."""
    device_type = (device_type or "").strip().lower()
    if device_type not in UNIVERSAL_CODES:
        return (
            f"Correction: Target '{device_type}' unknown. "
            f"Valid targets: tv, projector, av_receiver, meatbag."
        )

    addr, cmd = UNIVERSAL_CODES[device_type]
    pulses = encode_nec(addr, cmd)
    transmit_ir(pulses, gpio_pin=gpio_pin)
    return (
        f"Statement: Power signal dispatched to {device_type} "
        f"(addr 0x{addr:02X}, cmd 0x{cmd:02X}) via GPIO{gpio_pin}, meatbag."
    )


class IRBlaster:
    """High-level wrapper around the GPIO IR blaster."""

    def __init__(self, gpio_pin: int = _IR_PIN):
        self.gpio_pin = gpio_pin
        if _GPIO_AVAILABLE:
            try:
                GPIO.setwarnings(False)
                GPIO.setmode(GPIO.BCM)
                GPIO.setup(self.gpio_pin, GPIO.OUT, initial=GPIO.LOW)
                logger.info("IRBlaster initialised on GPIO%d.", self.gpio_pin)
            except Exception as exc:
                logger.warning("IRBlaster GPIO setup failed: %s", exc)
        else:
            logger.info("IRBlaster initialised in simulation mode.")

    def send_power(self, device_type: str) -> str:
        return send_power_signal(device_type, gpio_pin=self.gpio_pin)

    def send_custom(self, address: int, command: int) -> str:
        pulses = encode_nec(address, command)
        transmit_ir(pulses, gpio_pin=self.gpio_pin)
        return (
            f"Statement: Custom NEC packet sent (0x{address:02X}:0x{command:02X}), "
            "meatbag."
        )
