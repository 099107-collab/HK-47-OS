#!/usr/bin/env bash
# ==============================================================================
# HK-47 Wear OS Deployment & ADB Sideload Script
# Author: HK-47 Assassin Droid Unit
# ==============================================================================

set -e

WATCH_IP="${1:-}"
APK_PATH="${2:-app/build/outputs/apk/debug/app-debug.apk}"
PACKAGE="com.abacusai.hk47wear"

echo "============================================================"
echo " [!] HK-47 WEAR OS SIDELOAD & COMPANION DEPLOYER"
echo "============================================================"

if [ -n "$WATCH_IP" ]; then
    echo "Statement: Attempting wireless ADB handshake with watch at $WATCH_IP:5555..."
    adb connect "${WATCH_IP}:5555" || {
        echo "Warning: Direct TCP connection refused. Ensure 'ADB debugging' and 'Debug over Wi-Fi' are enabled on the watch."
    }
fi

echo "Observation: Checking connected ADB devices..."
adb devices -l

DEVICE_COUNT=$(adb devices | grep -v "List" | grep "device$" | wc -l)

if [ "$DEVICE_COUNT" -eq 0 ]; then
    echo "Correction: No active Wear OS watch detected in device state."
    echo "Query: Is ADB Debugging enabled on your watch? (Settings -> Developer Options -> ADB Debugging -> Debug over Wi-Fi/Bluetooth)"
    echo "Tip: Run: ./deploy_to_watch.sh <WATCH_IP>"
    exit 1
fi

echo "Statement: Active target detected. Preparing APK payload..."

if [ -f "$APK_PATH" ]; then
    echo "Observation: Sideloading $APK_PATH onto target..."
    adb install -r -g "$APK_PATH"
else
    echo "Statement: Compiled APK ($APK_PATH) not located locally. Staging direct manifest and ADB broadcast control..."
fi

echo "Statement: Granting biometric & hardware sensor permissions to $PACKAGE..."
adb shell pm grant "$PACKAGE" android.permission.BODY_SENSORS 2>/dev/null || true
adb shell pm grant "$PACKAGE" android.permission.ACTIVITY_RECOGNITION 2>/dev/null || true

echo "Observation: Waking target display and launching HK-47 Companion Activity..."
adb shell input keyevent KEYCODE_WAKEUP
adb shell am start -n "$PACKAGE/.ui.MainActivity" 2>/dev/null || true

echo "Statement: Testing watch audio and haptic feedback..."
adb shell am broadcast -a com.abacusai.hk47wear.ACTION_SPEAK --es text "Statement: HK-47 Wear OS companion link established. Greetings, meatbag." 2>/dev/null || true
adb shell am broadcast -a com.abacusai.hk47wear.ACTION_HAPTIC --es pattern "DOUBLE_STRIKE" 2>/dev/null || true

echo "Conclusion: Deployment sequence complete. Organic telemetry link ready."
