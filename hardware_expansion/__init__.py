"""
HK-47 OS :: hardware_expansion/__init__.py
Hardware expansion submodules (IR blaster, GPS tracker, CC1101 RF, tripwire).
All submodules degrade gracefully when peripheral hardware is absent.
"""

# Gracefully import each expansion module.
try:
    from .ir_blaster import IRBlaster, send_power_signal, encode_nec, transmit_ir
except Exception:
    IRBlaster = None
    send_power_signal = None
    encode_nec = None
    transmit_ir = None

try:
    from .gps_tools import GPSTracker
except Exception:
    GPSTracker = None

try:
    from .rf_tools import CC1101
except Exception:
    CC1101 = None

try:
    from .tripwire import TripwireMonitor
except Exception:
    TripwireMonitor = None

__all__ = [
    "IRBlaster",
    "send_power_signal",
    "encode_nec",
    "transmit_ir",
    "GPSTracker",
    "CC1101",
    "TripwireMonitor",
]
