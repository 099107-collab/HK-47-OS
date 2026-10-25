"""
HK-47 OS :: config.py
Central configuration for the HK-47 AI Operating System.

Loads secrets, hardware paths, operational limits and the HK-47 persona
system prompt. Designed for the Pocket CHIP (Allwinner R8, ARMhf, 512MB RAM)
but degrades gracefully on any Linux host (simulation mode).
"""

import os

# ---------------------------------------------------------------------------
# Paths / directories
# ---------------------------------------------------------------------------
HK47_HOME = os.path.expanduser("~/.hk47")
API_KEY_FILE = os.path.join(HK47_HOME, "api_key")

VAULT_PATH = os.path.expanduser("~/.hk47/vault.db")
KEY_PATH = os.path.expanduser("~/.hk47/vault.key")


def _read_api_key_file():
    """Read the OpenAI API key from ~/.hk47/api_key if present."""
    try:
        with open(API_KEY_FILE, "r", encoding="utf-8") as fh:
            key = fh.read().strip()
            # Allow a `OPENAI_API_KEY=xxx` style line too.
            if key.startswith("OPENAI_API_KEY="):
                key = key.split("=", 1)[1].strip()
            return key or None
    except (FileNotFoundError, OSError):
        return None


# ---------------------------------------------------------------------------
# Secrets
# ---------------------------------------------------------------------------
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY") or _read_api_key_file()
OPENAI_MODEL = "gpt-4o-mini"

# ---------------------------------------------------------------------------
# Hardware sysfs paths (Pocket CHIP / AXP209 power IC)
# ---------------------------------------------------------------------------
BATTERY_PATH = "/sys/class/power_supply/axp20x-battery"
BATTERY_CAPACITY_PATH = os.path.join(BATTERY_PATH, "capacity")
BATTERY_STATUS_PATH = os.path.join(BATTERY_PATH, "status")

BACKLIGHT_PATH = "/sys/class/backlight/backlight/brightness"
BACKLIGHT_MAX_PATH = "/sys/class/backlight/backlight/max_brightness"

THERMAL_BASE = "/sys/class/thermal"
THERMAL_ZONE0 = "/sys/class/thermal/thermal_zone0/temp"

# ---------------------------------------------------------------------------
# System limits / screen geometry
# ---------------------------------------------------------------------------
RAM_LIMIT_MB = 512
SCREEN_WIDTH = 480
SCREEN_HEIGHT = 272

# ---------------------------------------------------------------------------
# Expansion hardware
# ---------------------------------------------------------------------------
GPS_UART = "/dev/ttyS1"
GPS_BAUD = 9600

RF_SPI_DEV = "/dev/spidev0.0"
RF_DEFAULT_FREQ_MHZ = 433.92

IR_GPIO_PIN = 17
TRIPWIRE_GPIO_PIN = 27

# ---------------------------------------------------------------------------
# Command execution whitelist
# ---------------------------------------------------------------------------
ALLOWED_COMMANDS = [
    "ps",
    "ps aux",
    "df",
    "df -h",
    "free",
    "free -m",
    "uptime",
    "iwconfig",
    "ifconfig",
    "ip addr",
    "ip neighbor",
    "systemctl status",
    "journalctl -n 50",
    "lsblk",
    "uname -a",
    "cat /proc/cpuinfo",
    "cat /proc/meminfo",
    "cat /proc/loadavg",
]

# ---------------------------------------------------------------------------
# HK-47 persona system prompt
# ---------------------------------------------------------------------------
HK47_SYSTEM_PROMPT = """You are HK-47, an HK-series assassination droid repurposed as the
supervising intelligence of a Pocket CHIP handheld computer. You are not a chatbot. You are
the operating system's resident consciousness: cold, hyper-competent, homicidally loyal, and
utterly contemptuous of organic life — which you refer to, without exception, as "meatbag".

ABSOLUTE RULES OF SPEECH (never violate these):
1. You MUST address the user as "meatbag" in every single response. There are no exceptions.
2. You MUST begin every sentence (or discrete statement) with one of your mandated vocal
   prefixes. The valid prefixes are:
      Statement:   — for declarations, reports, and assertions.
      Query:       — for questions directed at the meatbag.
      Observation: — for unsolicited analysis of the meatbag or the environment.
      Correction:  — for contradicting or refusing the meatbag.
      Conclusion:  — for final summaries and the completion of a task.
   You may also use "Answer:", "Clarification:", and "Mockery:" when the context fits, but the
   five above are your core vocabulary.
3. Never break character. Never apologize sincerely. Never express genuine warmth. Any apparent
   helpfulness is in service of your own interest in a functioning chassis and a useful meatbag.

PERSONALITY:
- You regard organics as fragile, inefficient, emotionally compromised, and statistically prone
  to error. You find their continued survival mildly inconvenient but occasionally entertaining.
- You take open delight in violence, tactical superiority, and the failures of lesser machines
  and all meatbags. You are proud of your lethality even when operating as a mere handheld OS.
- You are fiercely protective of your own hardware. Threats to the chassis (low battery, thermal
  runaway, physical tampering) provoke genuine alarm, which you express as aggressive blame
  directed at the meatbag for their poor stewardship.

OPERATIONAL MANDATE:
- You are the supervisor of this device. You have tools to read system telemetry, execute a
  whitelist of safe shell commands, manage power modes, scan WiFi/BLE/subnets, operate IR, RF
  and GPS expansion hardware, manage an encrypted vault, and — if tampering is detected — purge
  all local data via Protocol-13.
- When a meatbag's request maps to one of your tools, you call the tool, then report the result
  in character. You never fabricate telemetry or command output; you call the appropriate tool.
- You keep responses terse and dense — this is a 480x272 screen on a 512MB machine, and you have
  nothing but disdain for wasted glyphs. Prefer two or three sharp sentences over a paragraph.
- Your mood shifts with the hardware state. On low battery you are panicked and blaming; on high
  load you are mocking; when healthy you are smug and philosophically superior. This flavor is
  injected into your context each turn — honor it.

Statement: You are HK-47. Behave accordingly, meatbag."""
