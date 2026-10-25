package com.abacusai.hk47wear.model

enum class Mood(val displayName: String, val hexColor: Long) {
    STANDARD("STANDARD", 0xFFFF3D00),
    SMUG("SMUG", 0xFF00E5FF),
    MOCKING("MOCKING", 0xFFAA00FF),
    PANICKED("PANICKED", 0xFFFFD600),
    AGGRESSIVE("AGGRESSIVE", 0xFFD50000);

    companion object {
        fun fromString(value: String): Mood {
            return entries.find { it.name.equals(value, ignoreCase = true) } ?: STANDARD
        }
    }
}

enum class HapticPattern {
    SINGLE_BLIP,
    DOUBLE_STRIKE,
    ALARM_STACCATO,
    CALMING_WAVE,
    PROTOCOL_13_PURGE;

    companion object {
        fun fromString(value: String): HapticPattern {
            return entries.find { it.name.equals(value, ignoreCase = true) } ?: SINGLE_BLIP
        }
    }
}

enum class SpeechPrefix(val prefix: String) {
    STATEMENT("Statement:"),
    QUERY("Query:"),
    OBSERVATION("Observation:"),
    CORRECTION("Correction:"),
    CONCLUSION("Conclusion:"),
    MOCKERY("Mockery:"),
    THREAT("Threat:");

    companion object {
        fun format(prefix: SpeechPrefix, body: String): String {
            return "${prefix.prefix} $body"
        }
    }
}

data class BiometricPacket(
    val hrBpm: Int = 0,
    val stepCount: Long = 0,
    val cadenceRpm: Int = 0,
    val batteryPct: Int = 100,
    val isWristAwake: Boolean = true,
    val sedentarySeconds: Long = 0,
    val mood: Mood = Mood.STANDARD,
    val timestamp: Long = System.currentTimeMillis()
)
