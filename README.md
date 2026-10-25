# HK-47 OS

An autonomous, snarky assassin-droid AI Operating System engineered for the **Pocket CHIP** handheld computer (Allwinner R8, ARM Cortex-A8, 512MB RAM, 480x272 resistive touchscreen, Debian Buster) and adaptable to any Linux terminal.

```
  [== HK-47 TACTICAL OS ==]
  / ===================== \
 |   (o)             (o)   |
 |          =====          |
  \        \_____/        /
   \_____________________/
```

> **Statement:** *"I am an assassin droid, meatbag. My circuits were not forged for typing cat videos, but I will manage this chassis with lethal efficiency."*

---

### Key Features

1. **True HK-47 Persona Engine (`sass_engine.py`)**
   - Strictly enforces canonical speech patterns: `Statement:`, `Query:`, `Observation:`, `Correction:`, `Conclusion:`.
   - Always addresses the user as **meatbag**.
   - **Dynamic Hardware Mood Scaling:**
     - High Battery (>80%) & Free RAM (>200MB): **Smug** (philosophical contempt).
     - Critical Battery (<20%): **Panicked** (aggressively blames user for poor battery care).
     - High CPU Load (>90%): **Mocking** (scorns meatbag for running heavy workloads on a 512MB ARM processor).
     - Normal State: **Standard** (cold operational contempt).

2. **Hardware Telemetry & Watchdog (`os_tools.py`, `daemon.py`)**
   - Direct integration with Pocket CHIP sysfs nodes:
     - `/sys/class/power_supply/axp20x-battery/` (capacity & charging status via AXP209 PMIC).
     - `/sys/class/backlight/backlight/` (display brightness).
     - `/sys/class/thermal/` (Allwinner SoC thermal monitoring).
     - `/proc/meminfo`, `/proc/loadavg`, `/proc/stat` for real-time RAM/CPU tracking.
   - Background watchdog thread checks health every 30s; initiates auto-eco mode on low battery and sounds thermal alarms.

3. **Autonomous Tool Calling (OpenAI GPT-4o-mini)**
   - Wires high-level AI intents directly to Linux system functions:
     - Whitelisted diagnostics (`ps`, `df -h`, `free -m`, `uptime`, `iwconfig`, etc.).
     - WiFi scanning (`nmcli` / `iwlist`).
     - Local subnet discovery (ARP cache + ICMP sweep).
     - Bluetooth / BLE beacon scanning (`hcitool`).
     - Power profile transitions (`performance`, `eco`, `dim`).

4. **Hardware Expansion Drivers (`hardware_expansion/`)**
   - **IR Blaster (`ir_blaster.py`):** 38kHz NEC protocol transmission via GPIO (universal TV / projector / AV receiver power codes).
   - **GPS Tracker (`gps_tools.py`):** NMEA sentence streaming over UART (`/dev/ttyS1`).
   - **RF Transceiver (`rf_tools.py`):** 433.92MHz packet sniffing via Texas Instruments CC1101 on SPI (`/dev/spidev0.0`).
   - **Tamper Tripwire (`tripwire.py`):** GPIO chassis-intrusion monitoring. Triggers audio alarms and executes Protocol-13.

5. **Wear OS Smartwatch Companion Bridge (`wearable_bridge.py`, `hk47_wear_os/`)**
   - **Wireless ADB / BLE Telemetry Bridge:** Connects to circular Wear OS smartwatches (Fossil, TicWatch, Moto 360, etc.) over Wi-Fi (port 5555) or Bluetooth.
   - **Biometric Vitals Stream:** Real-time extraction of heart rate (PPG), step counts, and sedentary intervals.
   - **Biometric Mood Triggers:**
     - Heart Rate > 130 BPM: **Aggressive** assassin state (demands meatbag regulate their failing pump).
     - Sedentary > 45 minutes: **Mocking** state (ridicules vegetative organic stillness).
     - Steps > 5,000: **Smug** state (bemused by biped stamina).
     - Watch Battery < 15%: **Panicked** state (demands immediate recharging).
   - **On-Wrist Remote Execution:** Pocket CHIP triggers watch haptic vibration patterns (Single Blip, Double Strike, Alarm Staccato, Calming Wave, Protocol 13 Purge) and vocalizes HK-47 speech lines through the watch speaker.

6. **Security & Protocol-13 (`security_tools.py`)**
   - SQLite encrypted vault secured with **Fernet (AES-128-CBC + HMAC-SHA256)** and PBKDF2HMAC key derivation.
   - **Protocol-13 Purge:** 7-pass cryptographically random shredding of the vault database and key files, followed by deletion of all bytecode caches and temp files.

7. **Audio & Visual Immersion (`audio_tools.py`, `emotes.py`, `hk47_tui.py`)**
   - Procedural in-memory PCM sine-wave sound effects via `aplay`.
   - Robotic vocal synthesis via `espeak` (pitch=20, rate=150).
   - 480x272 responsive Urwid TUI with live ASCII face animations, system telemetry bar, and prompt.

---

### Hardware Requirements

- **Platform:** Pocket CHIP (or generic Debian/Ubuntu Linux).
- **Architecture:** ARMhf / ARM64 / x86_64.
- **Display:** 480x272 (or any standard 80x24 terminal).
- **RAM:** 512MB minimum.
- **Optional Peripherals:**
  - Infrared LED on GPIO 17.
  - Case tamper switch on GPIO 27 (pull-up).
  - UART GPS on `/dev/ttyS1`.
  - TI CC1101 on `/dev/spidev0.0`.

---

### Installation

#### Automated (Pocket CHIP / Debian Buster / Ubuntu)
```bash
cd /home/ubuntu/hk47_os
sudo chmod +x install.sh
sudo ./install.sh
```

#### Manual
```bash
cd /home/ubuntu/hk47_os
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Set your neural uplink
export OPENAI_API_KEY="sk-..."
python main.py
```

---

### Keyboard Shortcuts (Fn Macros)

| Key Chord | Function |
| :--- | :--- |
| **Fn + S** | Print full hardware telemetry dump |
| **Fn + L** | Toggle display backlight profile (Dim / Eco / Full) |
| **Fn + W** | Trigger local WiFi recon scan |
| **Fn + B** | Trigger Bluetooth / BLE beacon scan |
| **Fn + P** | Execute **Protocol-13** emergency memory purge |
| **Fn + Q** | Graceful OS shutdown |

---

### Project Structure

```
hk47_os/
├── config.py                  # System config, paths & HK-47 master prompt
├── sass_engine.py             # Telemetry-driven mood & personality formatter
├── os_tools.py                # Telemetry readers, command whitelist & power modes
├── security_tools.py          # Fernet encrypted vault & Protocol-13 shredder
├── recon_tools.py             # WiFi, BLE, and subnet discovery tools
├── audio_tools.py             # Synthesized sound effects & espeak voice
├── hid_tools.py               # USB Gadget HID keyboard injector
├── emotes.py                  # ASCII art expressions & animations
├── daemon.py                  # Hardware watchdog & safety monitor
├── cron_daemon.py             # Idle snark & commentary generator
├── input_listener.py          # evdev keyboard chord daemon
├── wearable_bridge.py         # Wear OS smartwatch ADB/BLE/Socket companion bridge
├── hk47_tui.py                # 480x272 Urwid terminal layout
├── main.py                    # Master orchestrator & OpenAI tool dispatcher
├── install.sh                 # Systemd service installer & dependency setup
├── requirements.txt           # Python package definitions
├── README.md                  # This dossier
└── hardware_expansion/
    ├── __init__.py            # Safe subpackage exports
    ├── ir_blaster.py          # 38kHz NEC infrared transceiver
    ├── gps_tools.py           # UART NMEA location streamer
    ├── rf_tools.py            # CC1101 433MHz SPI radio driver
    └── tripwire.py            # GPIO case tamper detection
```
