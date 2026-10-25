package com.abacusai.hk47wear.service

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.content.Context
import android.content.Intent
import android.os.Binder
import android.os.Build
import android.os.IBinder
import android.util.Log
import androidx.core.app.NotificationCompat
import com.abacusai.hk47wear.R
import com.abacusai.hk47wear.audio.Hk47VoiceSynthesizer
import com.abacusai.hk47wear.ble.Hk47BleGattServer
import com.abacusai.hk47wear.haptics.Hk47HapticController
import com.abacusai.hk47wear.model.BiometricPacket
import com.abacusai.hk47wear.model.HapticPattern
import com.abacusai.hk47wear.model.Mood
import com.abacusai.hk47wear.model.SpeechPrefix
import com.abacusai.hk47wear.net.Hk47SocketBridge
import com.abacusai.hk47wear.sensor.BiometricSensorManager

class Hk47CompanionService : Service() {

    private val tag = "Hk47Service"
    private val binder = LocalBinder()

    lateinit var hapticController: Hk47HapticController
        private set
    lateinit var voiceSynthesizer: Hk47VoiceSynthesizer
        private set
    lateinit var sensorManager: BiometricSensorManager
        private set
    private lateinit var bleServer: Hk47BleGattServer
    private lateinit var socketBridge: Hk47SocketBridge

    private var latestPacket = BiometricPacket()
    private var telemetryListeners = mutableListOf<(BiometricPacket) -> Unit>()
    private var speechListeners = mutableListOf<(String) -> Unit>()

    inner class LocalBinder : Binder() {
        fun getService(): Hk47CompanionService = this@Hk47CompanionService
    }

    override fun onCreate() {
        super.onCreate()
        instance = this
        startForegroundNotification()

        hapticController = Hk47HapticController(this)
        voiceSynthesizer = Hk47VoiceSynthesizer(this)

        sensorManager = BiometricSensorManager(
            this,
            onTelemetryUpdated = { packet ->
                latestPacket = packet
                bleServer.notifyTelemetry(packet)
                socketBridge.sendTelemetry(packet)
                telemetryListeners.forEach { it(packet) }
            },
            onMoodChanged = { oldMood, newMood ->
                handleMoodTransition(oldMood, newMood)
            }
        )

        bleServer = Hk47BleGattServer(this) { incomingNotif ->
            hapticController.triggerPattern(HapticPattern.DOUBLE_STRIKE)
            voiceSynthesizer.speak(incomingNotif)
            speechListeners.forEach { it(incomingNotif) }
        }

        socketBridge = Hk47SocketBridge { incomingJson ->
            Log.i(tag, "Incoming socket command: $incomingJson")
            hapticController.triggerPattern(HapticPattern.SINGLE_BLIP)
            speechListeners.forEach { it(incomingJson) }
        }

        sensorManager.startListening()
        bleServer.start()
        socketBridge.start()
    }

    private fun handleMoodTransition(oldMood: Mood, newMood: Mood) {
        when (newMood) {
            Mood.AGGRESSIVE -> {
                hapticController.triggerPattern(HapticPattern.ALARM_STACCATO)
                voiceSynthesizer.speak(Hk47VoiceSynthesizer.CARDIAC_ALERT)
            }
            Mood.MOCKING -> {
                hapticController.triggerPattern(HapticPattern.SINGLE_BLIP)
                voiceSynthesizer.speak(Hk47VoiceSynthesizer.SEDENTARY_ALERT)
            }
            Mood.SMUG -> {
                hapticController.triggerPattern(HapticPattern.DOUBLE_STRIKE)
                voiceSynthesizer.speak(Hk47VoiceSynthesizer.STEP_GOAL_ALERT)
            }
            Mood.PANICKED -> {
                hapticController.triggerPattern(HapticPattern.ALARM_STACCATO)
                voiceSynthesizer.speak(Hk47VoiceSynthesizer.LOW_BATTERY_ALERT)
            }
            Mood.STANDARD -> {
                hapticController.triggerPattern(HapticPattern.CALMING_WAVE)
            }
        }
    }

    fun registerTelemetryListener(listener: (BiometricPacket) -> Unit) {
        telemetryListeners.add(listener)
        listener(latestPacket)
    }

    fun unregisterTelemetryListener(listener: (BiometricPacket) -> Unit) {
        telemetryListeners.remove(listener)
    }

    fun registerSpeechListener(listener: (String) -> Unit) {
        speechListeners.add(listener)
    }

    fun getLatestTelemetry(): BiometricPacket = latestPacket

    override fun onBind(intent: Intent?): IBinder = binder

    override fun onDestroy() {
        super.onDestroy()
        sensorManager.stopListening()
        bleServer.stop()
        socketBridge.stop()
        voiceSynthesizer.shutdown()
        instance = null
    }

    private fun startForegroundNotification() {
        val channelId = "hk47_companion_channel"
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                channelId,
                "HK-47 Wearable Core",
                NotificationManager.IMPORTANCE_LOW
            )
            val manager = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
            manager.createNotificationChannel(channel)
        }

        val notification: Notification = NotificationCompat.Builder(this, channelId)
            .setContentTitle("HK-47 Companion Active")
            .setContentText("Monitoring organic biometrics and Pocket CHIP bridge")
            .setSmallIcon(R.drawable.ic_launcher)
            .setOngoing(true)
            .build()

        startForeground(4747, notification)
    }

    companion object {
        var instance: Hk47CompanionService? = null
            private set
    }
}
