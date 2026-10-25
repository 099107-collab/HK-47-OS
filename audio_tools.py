"""
HK-47 OS :: audio_tools.py
Procedural sound effects (via aplay) and robotic speech (via espeak). Tones are
synthesized in-memory as PCM WAV so no asset files are required.
"""

import math
import os
import struct
import subprocess

# Mapping of event types to optional on-disk WAV assets. If the file is absent a
# tone is synthesized instead (see _EVENT_TONES below).
_ASSET_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sounds")
SOUND_EFFECTS = {
    "startup": os.path.join(_ASSET_DIR, "startup.wav"),
    "alert": os.path.join(_ASSET_DIR, "alert.wav"),
    "error": os.path.join(_ASSET_DIR, "error.wav"),
    "success": os.path.join(_ASSET_DIR, "success.wav"),
    "purge": os.path.join(_ASSET_DIR, "purge.wav"),
    "tamper": os.path.join(_ASSET_DIR, "tamper.wav"),
    "low_battery": os.path.join(_ASSET_DIR, "low_battery.wav"),
}

# Synthesized tone recipes: list of (frequency_hz, duration_ms) segments.
_EVENT_TONES = {
    "startup": [(330, 120), (440, 120), (554, 200)],
    "alert": [(880, 150), (0, 60), (880, 150)],
    "error": [(220, 400), (185, 400)],
    "success": [(523, 120), (659, 120), (784, 220)],
    "purge": [(400, 150), (300, 150), (200, 400)],
    "tamper": [(1000, 80), (0, 40)] * 6,
    "low_battery": [(330, 300), (0, 250), (330, 300)],
}


def generate_tone_wav(frequency: int, duration_ms: int, sample_rate: int = 22050) -> bytes:
    """Synthesize a mono 16-bit PCM WAV for a sine wave and return raw bytes."""
    num_samples = int(sample_rate * duration_ms / 1000.0)
    amplitude = 0.4 * 32767  # headroom to avoid clipping
    pcm = bytearray()
    for n in range(num_samples):
        if frequency <= 0:
            sample = 0
        else:
            # Simple linear fade in/out to avoid clicks.
            env = 1.0
            fade = int(sample_rate * 0.005)
            if fade > 0:
                if n < fade:
                    env = n / fade
                elif n > num_samples - fade:
                    env = max(0.0, (num_samples - n) / fade)
            sample = int(amplitude * env * math.sin(2 * math.pi * frequency * n / sample_rate))
        pcm += struct.pack("<h", sample)

    data_size = len(pcm)
    byte_rate = sample_rate * 2  # mono, 2 bytes/sample
    header = b"RIFF"
    header += struct.pack("<I", 36 + data_size)
    header += b"WAVE"
    header += b"fmt "
    header += struct.pack("<I", 16)       # PCM chunk size
    header += struct.pack("<H", 1)        # audio format = PCM
    header += struct.pack("<H", 1)        # channels = mono
    header += struct.pack("<I", sample_rate)
    header += struct.pack("<I", byte_rate)
    header += struct.pack("<H", 2)        # block align
    header += struct.pack("<H", 16)       # bits per sample
    header += b"data"
    header += struct.pack("<I", data_size)
    return bytes(header) + bytes(pcm)


def _build_event_wav(event_type: str) -> bytes:
    """Concatenate the tone segments for an event into one WAV."""
    segments = _EVENT_TONES.get(event_type, [(440, 150)])
    sample_rate = 22050
    pcm = bytearray()
    for freq, dur in segments:
        wav = generate_tone_wav(freq, dur, sample_rate)
        pcm += wav[44:]  # strip header, keep PCM
    data_size = len(pcm)
    byte_rate = sample_rate * 2
    header = b"RIFF" + struct.pack("<I", 36 + data_size) + b"WAVE"
    header += b"fmt " + struct.pack("<IHHIIHH", 16, 1, 1, sample_rate, byte_rate, 2, 16)
    header += b"data" + struct.pack("<I", data_size)
    return bytes(header) + bytes(pcm)


def play_sound_effect(event_type: str) -> None:
    """Play a sound effect for an event, non-blocking. Silent on failure."""
    path = SOUND_EFFECTS.get(event_type)
    try:
        if path and os.path.exists(path):
            subprocess.Popen(
                ["aplay", "-q", path],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return
        # Synthesize and pipe into aplay via stdin.
        wav = _build_event_wav(event_type)
        proc = subprocess.Popen(
            ["aplay", "-q"],
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        # Write without blocking the caller for long.
        try:
            proc.stdin.write(wav)
            proc.stdin.close()
        except (BrokenPipeError, OSError):
            pass
    except (FileNotFoundError, OSError):
        # aplay not installed / no audio hardware — fail silently.
        pass


def speak_alert(message: str, rate: int = 150, pitch: int = 20) -> None:
    """Speak a message in a low, robotic voice via espeak, non-blocking."""
    if not message:
        return
    try:
        subprocess.Popen(
            ["espeak", "-r", str(rate), "-p", str(pitch), "-v", "en", message],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except (FileNotFoundError, OSError):
        pass
