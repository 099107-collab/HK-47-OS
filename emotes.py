"""
HK-47 OS :: emotes.py
ASCII art faces and mood indicators tailored for HK-47's rusted-bronze chassis
and the Pocket CHIP's 480x272 display.
"""

# Base ASCII faces for each mood (approx 6 lines x 24 chars).
EMOTES = {
    "smug": (
        "  [== HK-47 ==]  \n"
        "  / ---------- \\ \n"
        " |  (o)    (-)  | \n"
        " |      ==      | \n"
        "  \\   \\____/   /  \n"
        "   \\__________/   "
    ),
    "panicked": (
        "  [!! ALERT !!]  \n"
        "  / !!======!! \\ \n"
        " |  (O)    (O)  | \n"
        " |     ;;;;     | \n"
        "  \\   < || >   /  \n"
        "   \\__/__\\____/   "
    ),
    "mocking": (
        "  [-- HA-HA --]  \n"
        "  / ~~~~~~~~~~ \\ \n"
        " |  (>)    (<)  | \n"
        " |      __      | \n"
        "  \\    \\___/   /  \n"
        "   \\__________/   "
    ),
    "standard": (
        "  [== HK-47 ==]  \n"
        "  / ========== \\ \n"
        " |  [o]    [o]  | \n"
        " |     ====     | \n"
        "  \\    |--|    /  \n"
        "   \\__________/   "
    ),
    "alert": (
        "  [<< THREAT >>] \n"
        "  / /\\/\\/\\/\\/\\ \\ \n"
        " |  <!>    <!>  | \n"
        " |     /\\/\\     | \n"
        "  \\   [####]   /  \n"
        "   \\__________/   "
    ),
    "purge": (
        "  [XX PROTOCOL XX]\n"
        "  / XXXXXXXXXX \\ \n"
        " |  (X)    (X)  | \n"
        " |     \\\\//     | \n"
        "  \\    ====    /  \n"
        "   \\__________/   "
    ),
    "boot": (
        "  [.. ONLINE ..] \n"
        "  / .......... \\ \n"
        " |  [*]    [*]  | \n"
        " |     ....     | \n"
        "  \\   |____|   /  \n"
        "   \\__________/   "
    ),
}

# Alternate frames for simple 2-frame animation.
_EMOTES_ALT = {
    "smug": (
        "  [== HK-47 ==]  \n"
        "  / ---------- \\ \n"
        " |  (-)    (o)  | \n"
        " |      ==      | \n"
        "  \\   /____\\   /  \n"
        "   \\__________/   "
    ),
    "panicked": (
        "  [! CRITICAL !] \n"
        "  / !!======!! \\ \n"
        " |  (0)    (0)  | \n"
        " |     ;;;;;    | \n"
        "  \\   < || >   /  \n"
        "   \\__\\__/__/   "
    ),
    "mocking": (
        "  [-- HA-HA --]  \n"
        "  / ~~~~~~~~~~ \\ \n"
        " |  (^)    (^)  | \n"
        " |     \\__/     | \n"
        "  \\   /____\\   /  \n"
        "   \\__________/   "
    ),
    "standard": (
        "  [== HK-47 ==]  \n"
        "  / ========== \\ \n"
        " |  [*]    [*]  | \n"
        " |     ====     | \n"
        "  \\    |--|    /  \n"
        "   \\__________/   "
    ),
    "alert": (
        "  [>> TARGET <<] \n"
        "  / \\/\\/\\/\\/\\/ \\ \n"
        " |  <?>    <?>  | \n"
        " |     \\/\\/     | \n"
        "  \\   [####]   /  \n"
        "   \\__________/   "
    ),
    "purge": (
        "  [13 PURGING 13]\n"
        "  / XXXXXXXXXX \\ \n"
        " |  (-)    (-)  | \n"
        " |     //\\\\     | \n"
        "  \\    ====    /  \n"
        "   \\__________/   "
    ),
    "boot": (
        "  [** READY! **] \n"
        "  / .......... \\ \n"
        " |  [+]    [+]  | \n"
        " |     ....     | \n"
        "  \\   |____|   /  \n"
        "   \\__________/   "
    ),
}

MOOD_COLORS = {
    "smug": "cyan",
    "panicked": "red",
    "mocking": "yellow",
    "standard": "white",
    "alert": "bright_red",
    "purge": "red",
    "boot": "green",
}


def get_emote(mood: str) -> str:
    """Return the ASCII art string for a given mood."""
    mood = (mood or "standard").lower()
    return EMOTES.get(mood, EMOTES["standard"])


def get_color(mood: str) -> str:
    """Return the color name for a given mood."""
    mood = (mood or "standard").lower()
    return MOOD_COLORS.get(mood, "white")


def animate_emote(mood: str, cycles: int = 3) -> list:
    """Generate alternating frame strings for simple TUI animation."""
    mood = (mood or "standard").lower()
    f1 = EMOTES.get(mood, EMOTES["standard"])
    f2 = _EMOTES_ALT.get(mood, f1)
    frames = []
    for _ in range(max(1, cycles)):
        frames.append(f1)
        frames.append(f2)
    return frames


def render_emote_rich(mood: str, console=None):
    """Print the colored emote to a rich console (falls back to plain print)."""
    text = get_emote(mood)
    color = get_color(mood)
    if console is not None:
        try:
            from rich.text import Text
            t = Text(text, style=color)
            console.print(t)
            return
        except Exception:
            pass
    print(text)
