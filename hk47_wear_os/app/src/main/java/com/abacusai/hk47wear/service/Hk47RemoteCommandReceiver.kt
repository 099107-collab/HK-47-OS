package com.abacusai.hk47wear.service

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.util.Log
import com.abacusai.hk47wear.model.HapticPattern
import com.abacusai.hk47wear.model.Mood

class Hk47RemoteCommandReceiver : BroadcastReceiver() {

    private val tag = "Hk47RemoteReceiver"

    override fun onReceive(context: Context?, intent: Intent?) {
        if (intent == null) return
        val action = intent.action ?: return
        val service = Hk47CompanionService.instance

        Log.i(tag, "Received remote command intent action: $action")

        when (action) {
            "com.abacusai.hk47wear.ACTION_SPEAK" -> {
                val text = intent.getStringExtra("text") ?: "Statement: Organic meatbag detected."
                service?.voiceSynthesizer?.speak(text)
            }
            "com.abacusai.hk47wear.ACTION_HAPTIC" -> {
                val patternStr = intent.getStringExtra("pattern") ?: "SINGLE_BLIP"
                val pattern = HapticPattern.fromString(patternStr)
                service?.hapticController?.triggerPattern(pattern)
            }
            "com.abacusai.hk47wear.ACTION_SET_MOOD" -> {
                val moodStr = intent.getStringExtra("mood") ?: "STANDARD"
                val mood = Mood.fromString(moodStr)
                Log.i(tag, "Set mood forced to: $mood")
            }
            "com.abacusai.hk47wear.ACTION_SYNC" -> {
                service?.sensorManager?.evaluateState()
            }
        }
    }
}
