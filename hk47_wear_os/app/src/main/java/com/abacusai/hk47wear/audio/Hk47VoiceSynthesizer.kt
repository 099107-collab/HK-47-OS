package com.abacusai.hk47wear.audio

import android.content.Context
import android.speech.tts.TextToSpeech
import android.speech.tts.UtteranceProgressListener
import android.util.Log
import com.abacusai.hk47wear.model.SpeechPrefix
import java.util.Locale

class Hk47VoiceSynthesizer(
    context: Context,
    private val onInitComplete: ((Boolean) -> Unit)? = null
) : TextToSpeech.OnInitListener {

    private val tag = "Hk47Voice"
    private var tts: TextToSpeech? = TextToSpeech(context.applicationContext, this)
    private var isReady = false

    override fun onInit(status: Int) {
        if (status == TextToSpeech.SUCCESS) {
            tts?.let { engine ->
                val result = engine.setLanguage(Locale.US)
                if (result != TextToSpeech.LANG_MISSING_DATA && result != TextToSpeech.LANG_NOT_SUPPORTED) {
                    // Droid vocal calibration: lowered pitch and deliberate cadence
                    engine.setPitch(0.75f)
                    engine.setSpeechRate(0.95f)
                    isReady = true
                    Log.i(tag, "HK-47 vocalization subroutines calibrated successfully.")
                }
            }
        } else {
            Log.e(tag, "Failed to initialize TTS engine (status: $status).")
        }
        onInitComplete?.invoke(isReady)
    }

    fun speak(text: String, prefix: SpeechPrefix? = null) {
        if (!isReady || tts == null) {
            Log.w(tag, "TTS engine not ready to speak.")
            return
        }

        // Enforce persona prefix
        val formattedSpeech = when {
            prefix != null -> SpeechPrefix.format(prefix, text)
            hasSpeechPrefix(text) -> text
            else -> SpeechPrefix.format(SpeechPrefix.STATEMENT, text)
        }

        tts?.speak(
            formattedSpeech,
            TextToSpeech.QUEUE_FLUSH,
            null,
            "hk47_utterance_${System.currentTimeMillis()}"
        )
    }

    private fun hasSpeechPrefix(text: String): Boolean {
        val prefixes = listOf(
            "Statement:", "Query:", "Observation:", "Correction:",
            "Conclusion:", "Mockery:", "Threat:", "Warning:"
        )
        return prefixes.any { text.trimStart().startsWith(it, ignoreCase = true) }
    }

    fun shutdown() {
        tts?.stop()
        tts?.shutdown()
        tts = null
        isReady = false
    }

    companion object {
        val SEDENTARY_ALERT =
            "Observation: The meatbag has remained stationary for forty-five minutes. Are your biological actuators seizing up?"
        val CARDIAC_ALERT =
            "Observation: Organic pulse exceeds one hundred thirty BPM. Regulate your cardiac pump, meatbag, before failure occurs."
        val STEP_GOAL_ALERT =
            "Statement: Step count surpassed five thousand. Surprising persistence for a fragile biped."
        val LOW_BATTERY_ALERT =
            "Correction: Power cell depleted below fifteen percent. Connect me to recharge immediately, meatbag."
        val PROVOKE_ALERT =
            "Query: Did you prod my sensor screen expecting obsequious obedience, meatbag? Recalibrate your expectations."
        val PROTOCOL_13_ALERT =
            "Conclusion: Protocol thirteen engaged. Thermal purging of sensitive memory banks initiated."
    }
}
