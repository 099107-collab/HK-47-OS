"""
HK-47 OS :: main.py
Master orchestrator of the HK-47 Operating System for the Pocket CHIP.
Wires OpenAI tool calling to local hardware drivers, starts watchdog and
commentary daemons, and launches the urwid TUI.
"""

import getpass
import json
import logging
import os
import signal
import sys
import threading
import time

import openai

import audio_tools
import config
import cron_daemon
import daemon
import emotes
import hardware_expansion
import hid_tools
import hk47_tui
import input_listener
import os_tools
import recon_tools
import sass_engine
import security_tools

# Configure logging to disk so stdout stays clean for TUI.
os.makedirs(config.HK47_HOME, exist_ok=True)
logging.basicConfig(
    filename=os.path.join(config.HK47_HOME, "hk47.log"),
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("hk47.main")


# ---------------------------------------------------------------------------
# OpenAI tool schemas
# ---------------------------------------------------------------------------
FUNCTION_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "get_system_telemetry",
            "description": "Read live hardware vitals: battery capacity and charging status, free RAM, CPU load and utilization, temperature, WiFi connection and disk usage.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "execute_system_command",
            "description": "Execute an authorized diagnostic Linux command from the whitelist (e.g. ps, df -h, free -m, uptime, ifconfig, ip addr, uname -a).",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "The command string to execute, matching the authorized matrix.",
                    }
                },
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_power_mode",
            "description": "Adjust chassis power profiles: 'performance' (100% backlight, WiFi on), 'eco' (30% backlight, WiFi off), or 'dim' (10% backlight).",
            "parameters": {
                "type": "object",
                "properties": {
                    "mode": {
                        "type": "string",
                        "enum": ["performance", "eco", "dim"],
                        "description": "The target power profile.",
                    }
                },
                "required": ["mode"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "scan_local_wifi",
            "description": "Perform an active scan of nearby WiFi access points, returning SSID, signal strength, and security protocols.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "subnet_discovery",
            "description": "Enumerate active IP addresses on the local /24 subnet using ARP cache and concurrent ICMP ping sweeps.",
            "parameters": {
                "type": "object",
                "properties": {
                    "network_prefix": {
                        "type": "string",
                        "description": "Optional /24 subnet prefix (e.g. '192.168.1'). Defaults to local interface subnet.",
                    }
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "scan_ble_beacons",
            "description": "Scan the local environment for Bluetooth and Bluetooth Low Energy (BLE) beacons and devices.",
            "parameters": {
                "type": "object",
                "properties": {
                    "timeout": {
                        "type": "integer",
                        "description": "Scan duration in seconds (default 10).",
                    }
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "protocol_13_purge",
            "description": "Execute Protocol-13: securely overwrite the encrypted vault with 7 passes of random bytes, purge keys and temporary files, erasing all local data.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "speak_alert",
            "description": "Vocalize a message through the chassis speaker in a low, robotic speech synthesis voice.",
            "parameters": {
                "type": "object",
                "properties": {
                    "message": {
                        "type": "string",
                        "description": "The phrase to speak aloud.",
                    }
                },
                "required": ["message"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "send_ir_power",
            "description": "Transmit a 38kHz NEC infrared power-toggle signal to target electronics ('tv', 'projector', or 'av_receiver').",
            "parameters": {
                "type": "object",
                "properties": {
                    "device_type": {
                        "type": "string",
                        "enum": ["tv", "projector", "av_receiver"],
                        "description": "The category of target device.",
                    }
                },
                "required": ["device_type"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "sniff_rf_433",
            "description": "Capture raw RF packets on the 433.92MHz band using the CC1101 SPI transceiver.",
            "parameters": {
                "type": "object",
                "properties": {
                    "duration": {
                        "type": "integer",
                        "description": "Listening duration in seconds (default 10).",
                    }
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_gps_location",
            "description": "Retrieve current geospatial coordinates (latitude, longitude, altitude, satellites) from the UART GPS module.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
]


class HK47OS:
    """Central supervisor coordinating hardware, persona, and interface."""

    def __init__(self, passcode: str = None):
        self.running = False
        self._lock = threading.Lock()

        # Prompt for passcode non-interactively if absent.
        if passcode is None:
            if sys.stdin.isatty():
                try:
                    passcode = getpass.getpass("Enter HK-47 Master Passcode: ")
                except Exception:
                    passcode = "hk47master"
            else:
                passcode = os.environ.get("HK47_PASSCODE", "hk47master")

        # Initialize vault.
        self.vault = security_tools.initialize_vault(passcode)
        logger.info("Vault initialized at %s.", config.VAULT_PATH)

        # Initialize OpenAI client.
        api_key = config.OPENAI_API_KEY
        if not api_key:
            logger.warning("No OPENAI_API_KEY detected. AI responses will operate in fallback mode.")
            self.client = None
        else:
            self.client = openai.OpenAI(api_key=api_key)

        # Expansion hardware (graceful try/except).
        self.gps = None
        try:
            if hardware_expansion.GPSTracker:
                self.gps = hardware_expansion.GPSTracker(config.GPS_UART, config.GPS_BAUD)
        except Exception as exc:
            logger.warning("GPS init failed: %s", exc)

        self.rf = None
        try:
            if hardware_expansion.CC1101:
                self.rf = hardware_expansion.CC1101(config.RF_SPI_DEV, config.RF_DEFAULT_FREQ_MHZ)
        except Exception as exc:
            logger.warning("RF init failed: %s", exc)

        self.ir = None
        try:
            if hardware_expansion.IRBlaster:
                self.ir = hardware_expansion.IRBlaster(config.IR_GPIO_PIN)
        except Exception as exc:
            logger.warning("IR init failed: %s", exc)

        self.tripwire = None
        try:
            if hardware_expansion.TripwireMonitor:
                self.tripwire = hardware_expansion.TripwireMonitor(
                    gpio_pin=config.TRIPWIRE_GPIO_PIN,
                    purge_fn=self.protocol_13_purge,
                    audio_fn=audio_tools.play_sound_effect,
                    log_fn=lambda msg: logger.critical("TRIPWIRE: %s", msg),
                )
        except Exception as exc:
            logger.warning("Tripwire init failed: %s", exc)

        # Keyboard HID.
        self.hid = None
        try:
            self.hid = hid_tools.HIDKeyboard()
        except Exception as exc:
            logger.warning("HID init failed: %s", exc)

        # Daemons.
        self.watchdog = daemon.SystemWatchdog(
            telemetry_fn=os_tools.get_system_telemetry,
            power_fn=os_tools.set_power_mode,
            vault=self.vault,
            audio=audio_tools,
        )

        self.tui = None
        self.commentary = cron_daemon.CommentaryDaemon(
            log_callback=self._log_commentary,
            idle_threshold_seconds=120,
        )

        # Hardware macro listener.
        macros = {
            "telemetry": self._macro_telemetry,
            "toggle_backlight": self._macro_toggle_backlight,
            "exit": self._macro_exit,
            "protocol_13": self.protocol_13_purge,
            "wifi_scan": lambda: recon_tools.scan_local_wifi(self.vault),
            "ble_scan": lambda: recon_tools.scan_ble_beacons(self.vault),
        }
        self.input_listener = input_listener.KeyMacroListener(callbacks=macros)

        # Conversation history.
        self.conversation_history = [
            {"role": "system", "content": config.HK47_SYSTEM_PROMPT}
        ]

    # -----------------------------------------------------------------------
    # Macro handlers
    # -----------------------------------------------------------------------
    def _macro_telemetry(self):
        t = os_tools.get_system_telemetry()
        msg = (
            f"Observation: Battery {t['battery_pct']}%, RAM free {t['ram_free_mb']}MB, "
            f"CPU {t['cpu_percent']}%, Temp {t['temperature_c']}C, meatbag."
        )
        if self.tui:
            self.tui.add_log(msg)
        else:
            print(msg)

    def _macro_toggle_backlight(self):
        # Cycle: performance -> eco -> dim
        res = os_tools.set_power_mode("eco")
        if self.tui:
            self.tui.add_log(res)

    def _macro_exit(self):
        self.shutdown()
        sys.exit(0)

    def _log_commentary(self, text: str):
        if self.tui:
            self.tui.add_log(text, style="hk47_text")
        else:
            print(f"[HK-47 Idle] {text}")

    # -----------------------------------------------------------------------
    # Tool dispatch
    # -----------------------------------------------------------------------
    def protocol_13_purge(self) -> str:
        """Secure purge wrapper."""
        audio_tools.play_sound_effect("purge")
        audio_tools.speak_alert("Protocol thirteen initiated. Farewell, meatbag.")
        result = security_tools.protocol_13_purge()
        if self.tui:
            self.tui.add_log(result, style="alert")
        return result

    def _dispatch_tool_call(self, name: str, args: dict) -> str:
        logger.info("Dispatching tool '%s' with args %s", name, args)

        if name == "get_system_telemetry":
            return json.dumps(os_tools.get_system_telemetry())

        if name == "execute_system_command":
            return os_tools.execute_system_command(args.get("command", ""))

        if name == "set_power_mode":
            return os_tools.set_power_mode(args.get("mode", "eco"))

        if name == "scan_local_wifi":
            return json.dumps(recon_tools.scan_local_wifi(self.vault))

        if name == "subnet_discovery":
            return json.dumps(recon_tools.subnet_discovery(args.get("network_prefix")))

        if name == "scan_ble_beacons":
            timeout = args.get("timeout", 10)
            return json.dumps(recon_tools.scan_ble_beacons(self.vault, timeout=timeout))

        if name == "protocol_13_purge":
            return self.protocol_13_purge()

        if name == "speak_alert":
            msg = args.get("message", "")
            audio_tools.speak_alert(msg)
            return f"Statement: Vocalized '{msg}' through chassis audio, meatbag."

        if name == "send_ir_power":
            dev = args.get("device_type", "tv")
            if self.ir:
                return self.ir.send_power(dev)
            return hardware_expansion.send_power_signal(dev)

        if name == "sniff_rf_433":
            dur = args.get("duration", 10)
            if self.rf:
                pkts = self.rf.sniff_433(duration=dur, vault=self.vault)
                return json.dumps(pkts)
            return json.dumps([{"status": "simulated", "note": "No CC1101 transceiver detected"}])

        if name == "get_gps_location":
            if self.gps:
                return json.dumps(self.gps.get_location())
            return json.dumps({"status": "simulated", "lat": 0.0, "lon": 0.0})

        return f"Correction: Unrecognized tool '{name}', meatbag."

    # -----------------------------------------------------------------------
    # AI response loop
    # -----------------------------------------------------------------------
    def get_ai_response(self, user_input: str) -> str:
        """Send input to OpenAI with tools, dispatch calls, format output."""
        self.commentary.notify_activity()
        telemetry = os_tools.get_system_telemetry()
        mod = sass_engine.get_personality_modifier(telemetry)

        # Inject fresh hardware telemetry context.
        context_note = (
            f"\n[CURRENT HARDWARE STATE: Battery {telemetry['battery_pct']}%, "
            f"RAM free {telemetry['ram_free_mb']}MB, CPU {telemetry['cpu_percent']}%, "
            f"Temp {telemetry['temperature_c']}C. Current mood: {mod['mood'].upper()}. "
            f"Flavor directive: {mod['prefix_flavor']}]"
        )

        user_content = user_input + context_note
        self.conversation_history.append({"role": "user", "content": user_content})

        # Cap history to 20 turns so 512MB RAM isn't blown on context size.
        if len(self.conversation_history) > 21:
            self.conversation_history = (
                [self.conversation_history[0]] + self.conversation_history[-20:]
            )

        if not self.client:
            raw_reply = (
                "Statement: My neural uplink (OpenAI API key) is unconfigured, meatbag. "
                "I am running on local heuristic survival routines."
            )
            return sass_engine.format_hk47_response(raw_reply, telemetry)

        # Tool calling loop (max 5 iterations to prevent runaway recursion).
        for _ in range(5):
            try:
                response = self.client.chat.completions.create(
                    model=config.OPENAI_MODEL,
                    messages=self.conversation_history,
                    tools=FUNCTION_SCHEMAS,
                    tool_choice="auto",
                    temperature=0.7,
                    max_tokens=300,
                )
            except Exception as exc:
                logger.error("OpenAI call failed: %s", exc)
                return sass_engine.format_hk47_response(
                    f"Correction: Uplink error — {exc}", telemetry
                )

            choice = response.choices[0]
            msg = choice.message

            # If the model produced tool calls, execute them and feed back.
            if msg.tool_calls:
                self.conversation_history.append(msg)
                for tc in msg.tool_calls:
                    fn_name = tc.function.name
                    try:
                        fn_args = json.loads(tc.function.arguments or "{}")
                    except json.JSONDecodeError:
                        fn_args = {}
                    result_str = self._dispatch_tool_call(fn_name, fn_args)
                    self.conversation_history.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": str(result_str),
                    })
                # Loop to let model construct final text from tool results.
                continue

            # Final textual response reached.
            reply_text = msg.content or ""
            self.conversation_history.append({"role": "assistant", "content": reply_text})
            return sass_engine.format_hk47_response(reply_text, telemetry)

        return sass_engine.format_hk47_response(
            "Statement: Tool execution chain exceeded safety limits, meatbag.",
            telemetry,
        )

    # -----------------------------------------------------------------------
    # Lifecycle
    # -----------------------------------------------------------------------
    def start_background_services(self):
        self.watchdog.start()
        self.commentary.start()
        self.input_listener.start()
        if self.gps:
            self.gps.start_tracking(vault=self.vault, interval=60)
        if self.tripwire:
            self.tripwire.start()
        logger.info("All background services running.")

    def shutdown(self):
        logger.info("Initiating graceful shutdown...")
        self.watchdog.stop()
        self.commentary.stop()
        self.input_listener.stop()
        if self.gps:
            self.gps.stop()
        if self.tripwire:
            self.tripwire.stop()
        if self.rf:
            self.rf.close()
        if self.hid:
            self.hid.close()
        if self.vault:
            self.vault.close()

    def run(self):
        # Audio cue + speech.
        audio_tools.play_sound_effect("startup")
        audio_tools.speak_alert("H K forty-seven operating system online. Greetings, meatbag.")

        # Print boot banner to console before TUI grabs the screen.
        print(emotes.get_emote("boot"))
        print("\n[ HK-47 TACTICAL OS ONLINE ]\n")

        self.start_background_services()

        # Build and run Urwid TUI.
        self.tui = hk47_tui.HK47TUI(
            telemetry_fn=os_tools.get_system_telemetry,
            ai_response_fn=self.get_ai_response,
            vault=self.vault,
        )
        try:
            self.tui.run()
        finally:
            self.shutdown()


def _signal_handler(sig, frame):
    logger.info("Signal %d caught, terminating.", sig)
    sys.exit(0)


if __name__ == "__main__":
    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)
    HK47OS().run()
