package com.shingihou.sghvoice.processing

/** One bounded, memory-only capture. The owner must wipe every taken buffer. */
class RetryableVoiceCapture {
    data class Capture(val wav: ByteArray, val task: VoiceTask, val includePersonalization: Boolean)

    companion object {
        // The 120-second watchdog may drain a final recorder buffer. Allow a
        // fixed five-second tail; never retain an unbounded recording.
        const val MAX_BYTES = 125 * 16_000 * 2 + 44
    }

    private var capture: Capture? = null
    val isAvailable: Boolean get() = capture != null

    fun retain(wav: ByteArray, task: VoiceTask, includePersonalization: Boolean): Boolean {
        if (wav.size !in 8_044..MAX_BYTES) return false
        clear()
        capture = Capture(wav.copyOf(), task, includePersonalization)
        return true
    }

    fun take(): Capture? = capture.also { capture = null }

    fun clear() {
        capture?.wav?.fill(0)
        capture = null
    }
}
