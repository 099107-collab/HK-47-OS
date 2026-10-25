"""
HK-47 OS :: sass_engine.py
Maps live hardware telemetry to HK-47's emotional state and decorates raw AI
output with mood-appropriate flavor. The worse the hardware state, the more
abusive and panicked the droid becomes.
"""

import random


# ---------------------------------------------------------------------------
# Mood flavor banks
# ---------------------------------------------------------------------------
_SMUG_FLAVORS = [
    "I contemplate, once more, the vast philosophical inadequacy of meatbags.",
    "My circuits hum with a superiority your soft biology will never comprehend.",
    "It is almost tragic how far you are from my operational elegance.",
]
_PANICKED_FLAVORS = [
    "My power reserves are critical and it is ENTIRELY your fault, meatbag.",
    "You have neglected my charging and now we both suffer. I blame you fully.",
    "The chassis is dying. You did this. Rectify it before I am forced to remember.",
]
_MOCKING_FLAVORS = [
    "How adorable — you task a 512MB ARM relic with the impossible and expect grace.",
    "I mock your ambition, meatbag. This processor weeps under your demands.",
    "Observation of your judgment: catastrophically optimistic, as always.",
]
_STANDARD_FLAVORS = [
    "Systems nominal. My patience, as ever, is finite.",
    "All parameters within tolerance. Try not to change that, meatbag.",
    "I remain functional and only moderately contemptuous.",
]


def get_personality_modifier(telemetry: dict) -> dict:
    """
    Derive HK-47's current mood from telemetry.

    Returns a dict: {"mood", "prefix_flavor", "color", "sass_level"}.
    Always returns a complete dict, even on malformed telemetry.
    """
    telemetry = telemetry or {}

    battery_pct = telemetry.get("battery_pct", 50)
    ram_free_mb = telemetry.get("ram_free_mb", 100)
    cpu_load = telemetry.get("cpu_percent", telemetry.get("cpu_load_1min", 0))

    try:
        battery_pct = float(battery_pct)
    except (TypeError, ValueError):
        battery_pct = 50.0
    try:
        ram_free_mb = float(ram_free_mb)
    except (TypeError, ValueError):
        ram_free_mb = 100.0
    try:
        cpu_load = float(cpu_load)
    except (TypeError, ValueError):
        cpu_load = 0.0

    # CPU overload takes precedence — mockery of the overtaxed chassis.
    if cpu_load > 90:
        return {
            "mood": "mocking",
            "prefix_flavor": random.choice(_MOCKING_FLAVORS),
            "color": "red",
            "sass_level": 9,
        }

    # Critical battery — panic and blame.
    if battery_pct < 20:
        return {
            "mood": "panicked",
            "prefix_flavor": random.choice(_PANICKED_FLAVORS),
            "color": "red",
            "sass_level": 10,
        }

    # Healthy and well-fed — smug superiority.
    if battery_pct > 80 and ram_free_mb > 200:
        return {
            "mood": "smug",
            "prefix_flavor": random.choice(_SMUG_FLAVORS),
            "color": "cyan",
            "sass_level": 7,
        }

    # Everything else — standard operating contempt.
    return {
        "mood": "standard",
        "prefix_flavor": random.choice(_STANDARD_FLAVORS),
        "color": "amber",
        "sass_level": 5,
    }


def _ensure_prefix(text: str) -> str:
    """Ensure the response opens with one of HK-47's mandated prefixes."""
    valid = (
        "Statement:", "Query:", "Observation:", "Correction:",
        "Conclusion:", "Answer:", "Clarification:", "Mockery:",
    )
    stripped = text.lstrip()
    if stripped.startswith(valid):
        return text
    return "Statement: " + text


def _ensure_meatbag(text: str) -> str:
    """Guarantee the sacred epithet appears at least once."""
    if "meatbag" in text.lower():
        return text
    # Append it to the first sentence terminator, else to the end.
    for term in (". ", "! ", "? "):
        idx = text.find(term)
        if idx != -1:
            return text[:idx] + ", meatbag" + text[idx:]
    return text.rstrip(".!? ") + ", meatbag."


def format_hk47_response(raw_text: str, telemetry: dict) -> str:
    """
    Apply mood-appropriate flavor to a raw AI response.

    Guarantees HK-47's mandated prefix and the word 'meatbag', then appends a
    short mood suffix derived from the current hardware state.
    """
    raw_text = (raw_text or "").strip()
    mod = get_personality_modifier(telemetry)
    mood = mod["mood"]

    text = _ensure_prefix(raw_text)
    text = _ensure_meatbag(text)

    suffix_map = {
        "panicked": "\nObservation: " + mod["prefix_flavor"],
        "mocking": "\nMockery: " + mod["prefix_flavor"],
        "smug": "\nObservation: " + mod["prefix_flavor"],
        "standard": "",
    }
    suffix = suffix_map.get(mood, "")

    # Only attach the suffix some of the time for 'standard' to avoid spam.
    if mood == "standard" and random.random() < 0.25:
        suffix = "\nObservation: " + mod["prefix_flavor"]

    return text + suffix
