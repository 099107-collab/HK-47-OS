package com.abacusai.hk47wear.haptics

import android.content.Context
import android.os.Build
import android.os.VibrationEffect
import android.os.Vibrator
import android.os.VibratorManager
import com.abacusai.hk47wear.model.HapticPattern

class Hk47HapticController(private val context: Context) {

    private val vibrator: Vibrator? = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
        val manager = context.getSystemService(Context.VIBRATOR_MANAGER_SERVICE) as? VibratorManager
        manager?.defaultVibrator
    } else {
        @Suppress("DEPRECATION")
        context.getSystemService(Context.VIBRATOR_SERVICE) as? Vibrator
    }

    fun triggerPattern(pattern: HapticPattern) {
        if (vibrator == null || !vibrator.hasVibrator()) return

        when (pattern) {
            HapticPattern.SINGLE_BLIP -> playSingleBlip()
            HapticPattern.DOUBLE_STRIKE -> playDoubleStrike()
            HapticPattern.ALARM_STACCATO -> playAlarmStaccato()
            HapticPattern.CALMING_WAVE -> playCalmingWave()
            HapticPattern.PROTOCOL_13_PURGE -> playProtocol13Purge()
        }
    }

    private fun playSingleBlip() {
        val effect = VibrationEffect.createOneShot(80, VibrationEffect.DEFAULT_AMPLITUDE)
        vibrator?.vibrate(effect)
    }

    private fun playDoubleStrike() {
        val timings = longArrayOf(0, 100, 80, 100)
        val amplitudes = intArrayOf(0, 200, 0, 255)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O && vibrator?.hasAmplitudeControl() == true) {
            val effect = VibrationEffect.createWaveform(timings, amplitudes, -1)
            vibrator.vibrate(effect)
        } else {
            val effect = VibrationEffect.createWaveform(timings, -1)
            vibrator?.vibrate(effect)
        }
    }

    private fun playAlarmStaccato() {
        val timings = longArrayOf(0, 50, 50, 50, 50, 50, 50, 50, 50, 50)
        val amplitudes = intArrayOf(0, 255, 0, 255, 0, 255, 0, 255, 0, 255)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O && vibrator?.hasAmplitudeControl() == true) {
            val effect = VibrationEffect.createWaveform(timings, amplitudes, -1)
            vibrator.vibrate(effect)
        } else {
            val effect = VibrationEffect.createWaveform(timings, -1)
            vibrator?.vibrate(effect)
        }
    }

    private fun playCalmingWave() {
        val timings = longArrayOf(0, 80, 40, 80, 40, 80)
        val amplitudes = intArrayOf(0, 60, 0, 120, 0, 60)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O && vibrator?.hasAmplitudeControl() == true) {
            val effect = VibrationEffect.createWaveform(timings, amplitudes, -1)
            vibrator.vibrate(effect)
        } else {
            val effect = VibrationEffect.createWaveform(timings, -1)
            vibrator?.vibrate(effect)
        }
    }

    private fun playProtocol13Purge() {
        val timings = longArrayOf(0, 400, 100, 600, 80, 700)
        val amplitudes = intArrayOf(0, 255, 0, 255, 0, 255)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O && vibrator?.hasAmplitudeControl() == true) {
            val effect = VibrationEffect.createWaveform(timings, amplitudes, -1)
            vibrator.vibrate(effect)
        } else {
            val effect = VibrationEffect.createWaveform(timings, -1)
            vibrator?.vibrate(effect)
        }
    }
}
