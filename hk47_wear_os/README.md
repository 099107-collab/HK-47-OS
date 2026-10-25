# HK-47 Wear OS Companion App & Watch Face

A custom Android Wear OS 2.x/3.x companion application, custom watch face, and biometric telemetry bridge designed to integrate circular Wear OS smartwatches with the Pocket CHIP HK-47 Operating System.

```
       .---.
      /     \
     | () () |  <-- "Observation: Organic cardiac telemetry is pitifully fragile, meatbag."
      \  =  /
       '---'
   HK-47 WEAR OS
```

---

### Hardware Profile
- **Target Platform**: Wear OS by Google (Fossil Gen 4/5/6, TicWatch C2/E2/S2/Pro, Moto 360, Skagen Falster, etc.)
- **Display**: Circular OLED/AMOLED (390x390, 400x400, 454x454) with anti-burn-in ambient mode
- **Sensors**: PPG Optical Heart Rate (`TYPE_HEART_RATE`), 3D Accelerometer / Step Counter (`TYPE_STEP_COUNTER`)
- **Actuators**: Linear Haptic Motor (`Vibrator` / `VibrationEffect`), Onboard Speaker / Bluetooth TTS
- **Connectivity**: Bluetooth 4.2/5.0 LE (GATT Server/Client), Wi-Fi 802.11 b/g/n, Wireless ADB (TCP 5555)

---

### Key Capabilities
1. **HK-47 Assassin Droid Watch Face**:
   - Titanium armor faceplate with twin glowing orange/red photoreceptor eye slits.
   - Live biometric HUD: Current Heart Rate (BPM), Step count, Active mood status.
   - AMOLED Ambient Mode: Energy-efficient monochrome wireframe with 1Hz refresh and pixel burn-in shifting.
2. **Biometric Telemetry Streaming**:
   - Streams live pulse and step counts to Pocket CHIP via BLE GATT or TCP Socket (port 4747).
   - Dynamically triggers HK-47 moods:
     - `AGGRESSIVE`: Heart rate spikes >130 BPM.
     - `MOCKING`: Sedentary meatbag inactive for >45 minutes.
     - `SMUG`: Step goal (>5,000 steps) achieved.
     - `PANICKED`: Watch battery drops below 15%.
3. **HK-47 Haptic Feedback Engine**:
   - 5 calibrated vibration profiles: Single Blip (80ms), Double Strike (confirmations), Alarm Staccato (critical alerts), Calming Wave, and Protocol 13 Purge (violent rumble).
4. **On-Wrist Vocalization**:
   - Robotic Android TTS engine tuned to 0.75 pitch, enforcing mandatory prefixes (`Statement:`, `Observation:`, `Query:`, `Threat:`).
5. **Pocket CHIP Wireless ADB Remote Control**:
   - Pocket CHIP can send notifications, trigger voice alerts, and query sensors directly via ADB shell commands.

---

### Setup Guide: From Pairing Screen to HK-47 Companion

The watch display currently shows:
> **"On your phone, download & open: Wear OS by Google"**

Follow these steps to activate the watch and deploy HK-47:

#### Method A: Standard Phone Pairing (Recommended)
1. Install **Wear OS by Google** on your Android smartphone (or iPhone).
2. Open the app, turn on Bluetooth, and follow the pairing prompts to pair the watch.
3. Once completed and on the home watch face:
   - Swipe down -> **Settings** (gear icon) -> **System** -> **About**.
   - Tap **Build number** 7 times until it says *"You are now a developer!"*.
   - Go back to **Settings** -> **Developer options**.
   - Enable **ADB debugging** and **Debug over Wi-Fi**.
   - Note the IP address displayed under "Debug over Wi-Fi" (e.g., `192.168.1.150:5555`).

#### Method B: Standalone Setup Bypass (Without Phone / Direct to Pocket CHIP)
Wear OS watches allow bypassing the phone pairing wizard directly via ADB:
1. Connect the watch charging cradle to your Pocket CHIP or computer USB port.
2. Verify connection:
   ```bash
   adb devices
   ```
3. Bypass the setup wizard and jump straight to the home screen:
   ```bash
   adb shell am start -a android.bluetooth.adapter.action.REQUEST_ENABLE
   adb shell settings put secure user_setup_complete 1
   adb shell settings put global device_provisioned 1
   adb shell am start -n com.google.android.wearable.setupwizard/.HomeActivity
   ```
4. Enable Wi-Fi and Developer Options directly on the watch.

---

### Sideloading HK-47 to the Watch
From the Pocket CHIP or development machine:
```bash
cd /home/ubuntu/hk47_wear_os
./scripts/deploy_to_watch.sh <WATCH_IP>
```
Or manually via ADB:
```bash
adb connect <WATCH_IP>:5555
adb install -r app/build/outputs/apk/debug/app-debug.apk
adb shell pm grant com.abacusai.hk47wear android.permission.BODY_SENSORS
adb shell pm grant com.abacusai.hk47wear android.permission.ACTIVITY_RECOGNITION
adb shell am start -n com.abacusai.hk47wear/.ui.MainActivity
```

---

### Remote ADB Commands from Pocket CHIP
Once connected, Pocket CHIP can command the watch without any cloud services:
- **Make watch speak**:
  ```bash
  adb shell am broadcast -a com.abacusai.hk47wear.ACTION_SPEAK --es text "Statement: Cease squirming, meatbag."
  ```
- **Trigger Haptic Rumble**:
  ```bash
  adb shell am broadcast -a com.abacusai.hk47wear.ACTION_HAPTIC --es pattern "DOUBLE_STRIKE"
  ```
- **Read Battery**:
  ```bash
  adb shell dumpsys battery | grep level
  ```
- **Take Screenshot of Watch Display**:
  ```bash
  adb shell screencap -p /sdcard/watch_screen.png
  adb pull /sdcard/watch_screen.png .
  ```
