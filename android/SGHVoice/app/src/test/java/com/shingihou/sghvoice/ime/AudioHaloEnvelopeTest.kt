package com.shingihou.sghvoice.ime

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class AudioHaloEnvelopeTest {
    @Test
    fun silenceAndReducedMotionProduceOnlyFlatLines() {
        for (line in 0..2) {
            for (point in 0..20) {
                val position = point / 20f
                assertEquals(0f, GentleWaveGeometry.offsetAt(position, line, 0f, 1.4f, false), 0f)
                assertEquals(0f, GentleWaveGeometry.offsetAt(position, line, 1f, 1.4f, true), 0f)
            }
        }
    }

    @Test
    fun audibleWavesStayGentleAndLeaveTheCaptionAreaClear() {
        for (line in 0..2) {
            val loud = (0..40).map { point ->
                GentleWaveGeometry.offsetAt(point / 40f, line, 1f, 0.9f, false)
            }
            val quiet = (0..40).map { point ->
                GentleWaveGeometry.offsetAt(point / 40f, line, 0.2f, 0.9f, false)
            }
            assertTrue(loud.maxOf { kotlin.math.abs(it) } > 0.015f)
            assertTrue(loud.maxOf { kotlin.math.abs(it) } > quiet.maxOf { kotlin.math.abs(it) })
            assertTrue(loud.all { it in -GentleWaveGeometry.MAX_AMPLITUDE_FRACTION..GentleWaveGeometry.MAX_AMPLITUDE_FRACTION })
            assertTrue(loud.all { GentleWaveGeometry.BASELINE_Y_FRACTION + it < 0.62f })
            assertEquals(0f, loud.first(), 0f)
            assertEquals(0f, loud.last(), 0f)
        }
    }

    @Test
    fun wavesProgressOnlyWhenAudibleSamplesArriveAndResetWithSilence() {
        val envelope = AudioHaloEnvelope()
        envelope.update(0.7f, 100L)
        val firstPhase = envelope.phase
        assertTrue(firstPhase > 0f)
        envelope.update(0.7f, 150L)
        assertTrue(envelope.phase > firstPhase)
        envelope.update(0f, 200L)
        assertEquals(0f, envelope.phase, 0f)
        envelope.update(0f, 1200L)
        assertEquals(0f, envelope.phase, 0f)
        envelope.update(0.7f, 1250L)
        envelope.reset()
        assertEquals(0f, envelope.phase, 0f)
        assertEquals(0f, envelope.level, 0f)
    }

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
