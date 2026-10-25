"""
Test suite for HK-47 OS Wear OS Smartwatch Integration.
Validates:
1. WearableBridgeManager telemetry collection and format
2. Biometric threshold triggers (heart rate, sedentary timer, step count, battery)
3. Personality mood shifts in sass_engine based on biometric telemetry
4. System telemetry integration in os_tools
5. Tool dispatch in main.py
"""

import json
import unittest
import config
import emotes
import os_tools
import sass_engine
import wearable_bridge
from main import HK47OS


class TestWearableIntegration(unittest.TestCase):

    def setUp(self):
        self.bridge = wearable_bridge.get_bridge()

    def test_01_telemetry_defaults(self):
        telem = self.bridge.get_telemetry_dict()
        self.assertIn("heart_rate_bpm", telem)
        self.assertIn("step_count", telem)
        self.assertIn("watch_battery_pct", telem)
        self.assertIn("sedentary_seconds", telem)
        self.assertIn("mood", telem)

    def test_02_cardiac_spike_triggers_aggressive_mood(self):
        self.bridge.inject_mock_biometrics(hr=145, steps=1000, battery=90, sedentary_sec=120)
        telem = self.bridge.get_telemetry_dict()
        self.assertEqual(telem["mood"], "aggressive")

        # Verify sass engine returns aggressive mood
        mod = sass_engine.get_personality_modifier({"wearable": telem})
        self.assertEqual(mod["mood"], "aggressive")
        self.assertEqual(mod["color"], "red")
        self.assertEqual(mod["sass_level"], 10)
        self.assertTrue(any(f in mod["prefix_flavor"] for f in ["pulse", "cardiac", "cardiovascular"]))

    def test_03_sedentary_meatbag_triggers_mocking_mood(self):
        # 50 minutes sedentary (> 45 min threshold)
        self.bridge.inject_mock_biometrics(hr=70, steps=1200, battery=85, sedentary_sec=3000)
        telem = self.bridge.get_telemetry_dict()
        self.assertEqual(telem["mood"], "mocking")

        mod = sass_engine.get_personality_modifier({"wearable": telem})
        self.assertEqual(mod["mood"], "mocking")
        self.assertIn(mod["color"], ["magenta", "yellow"])

    def test_04_step_goal_triggers_smug_mood(self):
        # 6,500 steps (> 5000 threshold)
        self.bridge.inject_mock_biometrics(hr=75, steps=6500, battery=85, sedentary_sec=60)
        telem = self.bridge.get_telemetry_dict()
        self.assertEqual(telem["mood"], "smug")

        mod = sass_engine.get_personality_modifier({"wearable": telem})
        self.assertEqual(mod["mood"], "smug")
        self.assertEqual(mod["color"], "cyan")

    def test_05_critical_watch_battery_triggers_panicked_mood(self):
        # 10% watch battery (< 15% threshold)
        self.bridge.inject_mock_biometrics(hr=72, steps=2000, battery=10, sedentary_sec=60)
        telem = self.bridge.get_telemetry_dict()
        self.assertEqual(telem["mood"], "panicked")

        mod = sass_engine.get_personality_modifier({"wearable": telem})
        self.assertEqual(mod["mood"], "panicked")

    def test_06_os_tools_telemetry_contains_wearable(self):
        sys_telem = os_tools.get_system_telemetry()
        self.assertIn("wearable", sys_telem)
        self.assertIn("watch_connected", sys_telem)
        self.assertIn("watch_hr", sys_telem)
        self.assertIn("watch_steps", sys_telem)
        self.assertIn("watch_battery", sys_telem)

    def test_07_emotes_have_aggressive_face(self):
        art = emotes.get_emote("aggressive")
        self.assertIn("ASSASSIN", art)
        color = emotes.get_color("aggressive")
        self.assertIn("red", color)

    def test_08_alert_dispatch(self):
        res = self.bridge.send_alert("TEST ALERT", "Heart rate erratic.")
        self.assertIn("Statement:", res)
        self.assertIn("meatbag", res)

    def test_09_haptic_dispatch(self):
        res = self.bridge.trigger_haptic("DOUBLE_STRIKE")
        self.assertIn("DOUBLE_STRIKE", res)
        self.assertIn("meatbag", res)

    def test_10_speech_dispatch(self):
        res = self.bridge.speak("Observe this command.")
        self.assertIn("Statement:", res)
        self.assertIn("meatbag", res)


if __name__ == "__main__":
    unittest.main()
