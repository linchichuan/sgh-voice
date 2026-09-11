package com.shingihou.sghvoice.ime

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class AudioHaloEnvelopeTest {
    @Test
    fun silenceAndInvalidSamplesNeverProduceMotion() {
        val envelope = AudioHaloEnvelope()
        listOf(0f, -1f, 0.01f, Float.NaN, Float.POSITIVE_INFINITY).forEachIndexed { index, sample ->
            assertEquals(0f, envelope.update(sample, index * 50L), 0f)
        }
    }

    @Test
    fun loudSpeechRisesGentlyAndSilenceImmediatelyReturnsToRest() {
        val envelope = AudioHaloEnvelope()
        val first = envelope.update(1f, 100L)
        assertTrue(first > 0f && first < 0.4f)
        val next = envelope.update(1f, 150L)
        assertTrue(next > first && next < 1f)
        assertEquals(0f, envelope.update(0f, 200L), 0f)
    }

    @Test
    fun smoothingDoesNotDependOnMicrophoneCallbackRate() {
        val frequent = AudioHaloEnvelope()
        val slower = AudioHaloEnvelope()
        frequent.update(0.8f, 100L)
        slower.update(0.8f, 100L)
        frequent.update(0.8f, 125L)
        frequent.update(0.8f, 150L)
        slower.update(0.8f, 150L)
        assertEquals(slower.level, frequent.level, 0.0001f)
    }

    @Test
    fun sessionResetDropsPreviousLevelAndOutOfRangeInputStaysBounded() {
        val envelope = AudioHaloEnvelope()
        repeat(30) { envelope.update(10f, it * 50L) }
        assertTrue(envelope.level in 0f..1f)
        envelope.reset()
        assertEquals(0f, envelope.level, 0f)
        assertEquals(AudioHaloEnvelope().update(0.5f, 5000L), envelope.update(0.5f, 5000L), 0f)
    }
}
