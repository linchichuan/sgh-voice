package com.shingihou.sghvoice.audio

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class AudioLevelMeterTest {

    @Test
    fun `silence stays flat while audible pcm produces a visible level`() {
        val silence = ByteArray(320)
        val speech = pcm16LittleEndian(sample = 4_000, sampleCount = 160)

        assertEquals(0f, AudioLevelMeter.normalizedPcm16(silence, silence.size), 0f)
        assertTrue(AudioLevelMeter.normalizedPcm16(speech, speech.size) > 0.2f)
    }

    @Test
    fun `level normalization is monotonic and clamped`() {
        assertEquals(0f, AudioLevelMeter.normalizedRms(0.001f), 0f)
        assertTrue(
            AudioLevelMeter.normalizedRms(0.05f) >
                AudioLevelMeter.normalizedRms(0.01f)
        )
        assertEquals(1f, AudioLevelMeter.normalizedRms(0.2f), 0f)
    }

    private fun pcm16LittleEndian(sample: Int, sampleCount: Int): ByteArray =
        ByteArray(sampleCount * 2).also { bytes ->
            repeat(sampleCount) { index ->
                bytes[index * 2] = (sample and 0xff).toByte()
                bytes[index * 2 + 1] = ((sample ushr 8) and 0xff).toByte()
            }
        }
}
