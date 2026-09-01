package com.shingihou.sghvoice.audio

import kotlin.math.ln
import kotlin.math.sqrt

/** Converts live PCM/RMS samples into ephemeral 0..1 waveform intensity. */
object AudioLevelMeter {
    private const val NOISE_FLOOR_RMS = 0.001f
    private const val SPEECH_CEILING_RMS = 0.12f

    fun normalizedRms(rms: Float): Float {
        if (!rms.isFinite() || rms <= NOISE_FLOOR_RMS) return 0f
        if (rms >= SPEECH_CEILING_RMS) return 1f
        return (
            ln(rms / NOISE_FLOOR_RMS) /
                ln(SPEECH_CEILING_RMS / NOISE_FLOOR_RMS)
            ).coerceIn(0f, 1f)
    }

    fun normalizedPcm16(buffer: ByteArray, bytesRead: Int): Float {
        val usableBytes = (bytesRead.coerceIn(0, buffer.size) / 2) * 2
        if (usableBytes == 0) return 0f

        var sumSquares = 0.0
        var index = 0
        while (index < usableBytes) {
            val low = buffer[index].toInt() and 0xff
            val high = buffer[index + 1].toInt()
            val sample = ((high shl 8) or low).toShort().toInt()
            val normalized = sample / 32768.0
            sumSquares += normalized * normalized
            index += 2
        }

        return normalizedRms(
            sqrt(sumSquares / (usableBytes / 2)).toFloat()
        )
    }
}
