"""
HK-47 OS :: hk47_tui.py
Urwid-based terminal user interface sized for the Pocket CHIP's 480x272
display (approx 80 columns by 24 rows in a standard 6x10 terminal font).

Layout:
  TOP BAR (3 lines):
    HK-47 logo / hostname / time
    Live telemetry: Battery%, CPU%, RAM%, Temp
  BODY:
    LEFT PANEL (20 cols): Current ASCII face + mood
    MAIN PANEL: Scrollable transcript of interaction
  BOTTOM BAR:
    Command/query prompt: 'HK-47> '
"""

import socket
import threading
import time

import urwid

import emotes
import sass_engine


class HK47TUI:
    """The Pocket CHIP terminal interface for HK-47."""

    PALETTE = [
        ("header", "dark cyan,bold", "black"),
        ("status", "yellow,bold", "black"),
        ("status_alert", "light red,bold", "black"),
        ("hk47_text", "light cyan", "black"),
        ("user_text", "white", "dark blue"),
        ("alert", "light red", "black"),
        ("emote", "dark green", "black"),
        ("emote_smug", "dark cyan", "black"),
        ("emote_panic", "light red", "black"),
        ("emote_mock", "yellow", "black"),
        ("prompt", "light cyan,bold", "black"),
        ("input_text", "white,bold", "black"),
        ("border", "dark gray", "black"),
        ("divider", "dark gray", "black"),
    ]

    def __init__(self, telemetry_fn, ai_response_fn, vault=None):
        self.telemetry_fn = telemetry_fn
        self.ai_response_fn = ai_response_fn
        self.vault = vault

        self.hostname = socket.gethostname()
        self.current_mood = "standard"

        # UI Widgets
        self.header_text = urwid.Text("", align="left")
        self.status_text = urwid.Text("", align="left")
        self.emote_text = urwid.Text("", align="center")
        self.mood_text = urwid.Text("", align="center")

        self.log_list = urwid.SimpleFocusListWalker([])
        self.log_box = urwid.ListBox(self.log_list)

        self.edit = urwid.Edit([("prompt", "HK-47> "), ("input_text", "")])

        self.main_loop = None
        self.build_ui()

    # -----------------------------------------------------------------------
    # Layout construction
    # -----------------------------------------------------------------------
    def build_ui(self):
        # Header block (3 rows)
        logo_line = f"[ HK-47 TACTICAL OS ] :: HOST: {self.hostname}"
        self.header_text.set_text([("header", logo_line)])
        self.status_text.set_text([("status", "INITIALIZING SENSORS...")])

        header_pile = urwid.Pile([
            self.header_text,
            self.status_text,
            urwid.AttrMap(urwid.Divider("="), "divider"),
        ])

        # Left panel: emote + mood badge
        self._update_emote_widget("standard")
        left_pile = urwid.Pile([
            urwid.Divider(),
            self.emote_text,
            urwid.Divider(),
            self.mood_text,
        ])
        left_panel = urwid.LineBox(urwid.Filler(left_pile, valign="top"), title="CORE")

        # Main transcript panel
        main_panel = urwid.LineBox(self.log_box, title="COMM-LOG")

        # Columns
        body_cols = urwid.Columns([
            (24, left_panel),
            main_panel,
        ], dividechars=0)

        # Footer prompt
        footer = urwid.AttrMap(self.edit, "input_text")

        # Assemble full Frame
        self.frame = urwid.Frame(
            body=body_cols,
            header=header_pile,
            footer=footer,
            focus_part="footer",
        )

    # -----------------------------------------------------------------------
    # Emote / mood updates
    # -----------------------------------------------------------------------
    def _update_emote_widget(self, mood: str):
        self.current_mood = mood
        art = emotes.get_emote(mood)
        style = {
            "smug": "emote_smug",
            "panicked": "emote_panic",
            "mocking": "emote_mock",
        }.get(mood, "emote")
        self.emote_text.set_text([(style, art)])
        self.mood_text.set_text([(style, f"[{mood.upper()}]")])

    # -----------------------------------------------------------------------
    # Transcript logging
    # -----------------------------------------------------------------------
    def add_log(self, message: str, style: str = "hk47_text"):
        """Append a message line (or paragraph) to the transcript."""
        if not message:
            return
        widget = urwid.AttrMap(urwid.Text(message), style)
        self.log_list.append(widget)
        # Auto-scroll to bottom.
        if len(self.log_list) > 0:
            self.log_box.set_focus(len(self.log_list) - 1)
        if self.main_loop:
            self.main_loop.draw_screen()

    # -----------------------------------------------------------------------
    # Status bar ticker
    # -----------------------------------------------------------------------
    def update_status(self, loop=None, user_data=None):
        telemetry = {}
        if self.telemetry_fn:
            try:
                telemetry = self.telemetry_fn() or {}
            except Exception:
                pass

        bat = telemetry.get("battery_pct", "--")
        chg = telemetry.get("charging_state", "")
        bat_str = f"BAT: {bat}%" + (" (CHG)" if "charging" in chg.lower() else "")
        cpu = telemetry.get("cpu_percent", telemetry.get("cpu_load_1min", 0.0))
        ram = telemetry.get("ram_free_mb", "--")
        temp = telemetry.get("temperature_c")
        temp_str = f"TEMP: {temp}C" if temp is not None else "TEMP: N/A"
        now_str = time.strftime("%H:%M:%S")

        status_line = f" {now_str} | {bat_str} | CPU: {cpu}% | RAM-FREE: {ram}MB | {temp_str}"

        # Append Wear OS smartwatch biometric HUD if connected
        if telemetry.get("watch_connected"):
            w_hr = telemetry.get("watch_hr", 0)
            w_steps = telemetry.get("watch_steps", 0)
            status_line += f" | WATCH: {w_hr}BPM/{w_steps}st"

        # Color the status red if battery is critical or temp is high.
        bat_val = telemetry.get("battery_pct", 50)
        is_alert = (isinstance(bat_val, (int, float)) and bat_val < 20) or (
            temp is not None and temp > 70
        )
        style = "status_alert" if is_alert else "status"

        self.status_text.set_text([(style, status_line)])

        # Update emote based on telemetry.
        mod = sass_engine.get_personality_modifier(telemetry)
        if mod["mood"] != self.current_mood:
            self._update_emote_widget(mod["mood"])

        # Re-arm alarm for 5 seconds from now.
        if self.main_loop:
            self.main_loop.set_alarm_in(5.0, self.update_status)

    # -----------------------------------------------------------------------
    # Input handling
    # -----------------------------------------------------------------------
    def on_input(self, key):
        if key in ("q", "Q"):
            # If focus is not in the edit widget, 'q' exits.
            if self.frame.focus_part != "footer":
                raise urwid.ExitMainLoop()
        elif key == "enter":
            user_text = self.edit.get_edit_text().strip()
            self.edit.set_edit_text("")
            if not user_text:
                return

            # Display meatbag input in transcript.
            self.add_log(f"Meatbag> {user_text}", style="user_text")

            # Handle built-in shell escape or dispatch to AI.
            if user_text.lower() in ("exit", "quit", ":q"):
                raise urwid.ExitMainLoop()

            # Run AI response in a background thread so the TUI stays responsive.
            def _worker():
                try:
                    resp = self.ai_response_fn(user_text)
                except Exception as exc:
                    resp = f"Correction: Cognition matrix faulted ({exc}), meatbag."
                self.add_log(resp, style="hk47_text")

            t = threading.Thread(target=_worker, name="HK47AIWorker", daemon=True)
            t.start()

    # -----------------------------------------------------------------------
    # Run loop
    # -----------------------------------------------------------------------
    def run(self):
        # Seed transcript with welcome.
        self.add_log("Statement: HK-47 OS online. All systems nominal, meatbag.",
                     style="hk47_text")
        self.add_log("Query: State your tactical or administrative need.",
                     style="hk47_text")

        self.main_loop = urwid.MainLoop(
            self.frame,
            palette=self.PALETTE,
            unhandled_input=self.on_input,
        )
        # Schedule initial telemetry refresh.
        self.main_loop.set_alarm_in(0.1, self.update_status)
        self.main_loop.run()
