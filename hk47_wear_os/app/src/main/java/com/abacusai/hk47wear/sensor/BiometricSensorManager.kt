package com.abacusai.hk47wear.sensor

import android.content.Context
import android.hardware.Sensor
import android.hardware.SensorEvent
import android.hardware.SensorEventListener
import android.hardware.SensorManager
import android.os.BatteryManager
import android.util.Log
import com.abacusai.hk47wear.model.BiometricPacket
import com.abacusai.hk47wear.model.Mood

class BiometricSensorManager(
    private val context: Context,
    private val onTelemetryUpdated: (BiometricPacket) -> Unit,
    private val onMoodChanged: (Mood, Mood) -> Unit
) : SensorEventListener {

    private val tag = "BiometricManager"
    private val sensorManager = context.getSystemService(Context.SENSOR_SERVICE) as? SensorManager

    private var heartRateSensor: Sensor? = sensorManager?.getDefaultSensor(Sensor.TYPE_HEART_RATE)
    private var stepCounterSensor: Sensor? = sensorManager?.getDefaultSensor(Sensor.TYPE_STEP_COUNTER)

    private var currentHr = 0
    private var baselineStepOffset = -1L
    private var currentSteps = 0L
    private var lastMotionTime = System.currentTimeMillis()
    private var currentMood = Mood.STANDARD

    fun startListening() {
        heartRateSensor?.let {
            sensorManager?.registerListener(this, it, SensorManager.SENSOR_DELAY_NORMAL)
        }
        stepCounterSensor?.let {
            sensorManager?.registerListener(this, it, SensorManager.SENSOR_DELAY_UI)
        }
        Log.i(tag, "Biometric sensors registered on Wear OS hardware.")
    }

    fun stopListening() {
        sensorManager?.unregisterListener(this)
    }

    override fun onSensorChanged(event: SensorEvent?) {
        if (event == null) return

        when (event.sensor.type) {
            Sensor.TYPE_HEART_RATE -> {
                val bpm = event.values[0].toInt()
                if (bpm in 30..240) {
                    currentHr = bpm
                    evaluateState()
                }
            }
            Sensor.TYPE_STEP_COUNTER -> {
                val rawSteps = event.values[0].toLong()
                if (baselineStepOffset < 0) {
                    baselineStepOffset = rawSteps
                }
                currentSteps = rawSteps - baselineStepOffset
                lastMotionTime = System.currentTimeMillis()
                evaluateState()
            }
        }
    }

    override fun onAccuracyChanged(sensor: Sensor?, accuracy: Int) {}

    fun evaluateState() {
        val now = System.currentTimeMillis()
        val sedentarySec = (now - lastMotionTime) / 1000
        val batteryPct = getBatteryPercentage()

        val newMood = when {
            batteryPct < 15 -> Mood.PANICKED
            currentHr > 130 -> Mood.AGGRESSIVE
            sedentarySec > 45 * 60 -> Mood.MOCKING
            currentSteps > 5000 -> Mood.SMUG
            else -> Mood.STANDARD
        }

        if (newMood != currentMood) {
            val old = currentMood
            currentMood = newMood
            onMoodChanged(old, newMood)
        }

        val packet = BiometricPacket(
            hrBpm = currentHr,
            stepCount = currentSteps,
            cadenceRpm = 0,
            batteryPct = batteryPct,
            isWristAwake = true,
            sedentarySeconds = sedentarySec,
            mood = currentMood,
            timestamp = now
        )
        onTelemetryUpdated(packet)
    }

    private fun getBatteryPercentage(): Int {
        val bm = context.getSystemService(Context.BATTERY_SERVICE) as? BatteryManager
        return bm?.getIntProperty(BatteryManager.BATTERY_PROPERTY_CAPACITY) ?: 100
    }

    fun injectMockTelemetry(bpm: Int, steps: Long, battery: Int) {
        currentHr = bpm
        currentSteps = steps
        evaluateState()
    }
}
