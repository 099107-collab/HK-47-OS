package com.abacusai.hk47wear.ui

import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.content.ServiceConnection
import android.os.Bundle
import android.os.IBinder
import android.view.WindowManager
import android.widget.Button
import android.widget.TextView
import androidx.activity.ComponentActivity
import com.abacusai.hk47wear.R
import com.abacusai.hk47wear.audio.Hk47VoiceSynthesizer
import com.abacusai.hk47wear.model.BiometricPacket
import com.abacusai.hk47wear.model.HapticPattern
import com.abacusai.hk47wear.model.Mood
import com.abacusai.hk47wear.service.Hk47CompanionService

class MainActivity : ComponentActivity() {

    private var companionService: Hk47CompanionService? = null
    private var isBound = false

    private lateinit var tvMood: TextView
    private lateinit var tvEyes: TextView
    private lateinit var tvHeartRate: TextView
    private lateinit var tvSteps: TextView
    private lateinit var tvSpeech: TextView
    private lateinit var tvBridgeStatus: TextView
    private lateinit var btnProvoke: Button
    private lateinit var btnProtocol13: Button

    private val serviceConnection = object : ServiceConnection {
        override fun onServiceConnected(name: ComponentName?, service: IBinder?) {
            val binder = service as Hk47CompanionService.LocalBinder
            companionService = binder.getService()
            isBound = true

            companionService?.registerTelemetryListener { packet ->
                runOnUiThread { updateUiWithTelemetry(packet) }
            }

            companionService?.registerSpeechListener { speech ->
                runOnUiThread { tvSpeech.text = speech }
            }
        }

        override fun onServiceDisconnected(name: ComponentName?) {
            companionService = null
            isBound = false
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        setContentView(R.layout.activity_main)

        tvMood = findViewById(R.id.tvMood)
        tvEyes = findViewById(R.id.tvEyes)
        tvHeartRate = findViewById(R.id.tvHeartRate)
        tvSteps = findViewById(R.id.tvSteps)
        tvSpeech = findViewById(R.id.tvSpeech)
        tvBridgeStatus = findViewById(R.id.tvBridgeStatus)
        btnProvoke = findViewById(R.id.btnProvoke)
        btnProtocol13 = findViewById(R.id.btnProtocol13)

        btnProvoke.setOnClickListener {
            companionService?.hapticController?.triggerPattern(HapticPattern.DOUBLE_STRIKE)
            companionService?.voiceSynthesizer?.speak(Hk47VoiceSynthesizer.PROVOKE_ALERT)
            tvSpeech.text = Hk47VoiceSynthesizer.PROVOKE_ALERT
        }

        btnProtocol13.setOnClickListener {
            companionService?.hapticController?.triggerPattern(HapticPattern.PROTOCOL_13_PURGE)
            companionService?.voiceSynthesizer?.speak(Hk47VoiceSynthesizer.PROTOCOL_13_ALERT)
            tvSpeech.text = Hk47VoiceSynthesizer.PROTOCOL_13_ALERT
        }

        val serviceIntent = Intent(this, Hk47CompanionService::class.java)
        startService(serviceIntent)
        bindService(serviceIntent, serviceConnection, Context.BIND_AUTO_CREATE)
    }

    private fun updateUiWithTelemetry(packet: BiometricPacket) {
        tvHeartRate.text = if (packet.hrBpm > 0) "${packet.hrBpm} BPM" else "-- BPM"
        tvSteps.text = packet.stepCount.toString()

        tvMood.text = "MOOD: ${packet.mood.displayName}"
        val colorInt = packet.mood.hexColor.toInt()
        tvMood.setTextColor(colorInt)

        tvEyes.text = when (packet.mood) {
            Mood.AGGRESSIVE -> "[ ಠ益ಠ ]"
            Mood.MOCKING -> "[ ¬_¬ ]"
            Mood.SMUG -> "[ ^_^ ]"
            Mood.PANICKED -> "[ ⊙_⊙ ]"
            Mood.STANDARD -> "[ •_• ]"
        }
        tvEyes.setTextColor(colorInt)

        tvBridgeStatus.text = "CHIP LINK: ACTIVE [BAT: ${packet.batteryPct}%]"
    }

    override fun onDestroy() {
        super.onDestroy()
        if (isBound) {
            unbindService(serviceConnection)
            isBound = false
        }
    }
}
