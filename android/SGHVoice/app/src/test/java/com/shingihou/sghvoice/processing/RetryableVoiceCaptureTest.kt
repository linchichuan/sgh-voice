package com.shingihou.sghvoice.processing

import org.junit.Assert.*
import org.junit.Test

class RetryableVoiceCaptureTest {
    @Test fun `retry owns a copy and transfers it only once`() {
        val state = RetryableVoiceCapture()
        val input = ByteArray(9_000) { 7 }
        assertTrue(state.retain(input, VoiceTask.Compose, false))
        input.fill(0)
        val capture = state.take()!!
        assertEquals(7.toByte(), capture.wav[0])
        assertEquals(VoiceTask.Compose, capture.task)
        assertFalse(capture.includePersonalization)
        assertNull(state.take())
        capture.wav.fill(0)
    }

    @Test fun `invalid recordings cannot replace a retry`() {
        val state = RetryableVoiceCapture()
        assertTrue(state.retain(ByteArray(9_000) { 1 }, VoiceTask.Dictation, false))
        assertFalse(state.retain(ByteArray(8_043), VoiceTask.Dictation, true))
        assertFalse(state.retain(ByteArray(RetryableVoiceCapture.MAX_BYTES + 1), VoiceTask.Dictation, true))
        assertTrue(state.isAvailable)
        state.clear()
        assertFalse(state.isAvailable)
    }

    @Test fun `watchdog capture with a trailing recorder buffer remains retryable`() {
        val state = RetryableVoiceCapture()
        assertTrue(state.retain(ByteArray(120 * 16_000 * 2 + 44 + 8_192), VoiceTask.Dictation, false))
        state.clear()
    }
}
