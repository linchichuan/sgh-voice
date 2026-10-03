package com.shingihou.sghvoice.learning

/** One verified voice insertion in one editor. Never persisted, never a document scrape. */
class RecentVoiceContext(private val clock: () -> Long = { System.nanoTime() / 1_000_000L }) {
    private var session: Long? = null
    private var text = ""
    private var createdAt = 0L

    fun remember(sessionId: Long, insertedText: String, allowed: Boolean) {
        clear()
        if (!allowed || insertedText.isBlank()) return
        session = sessionId
        text = tail(insertedText)
        createdAt = clock()
    }

    fun corrected(sessionId: Long, original: String, edited: String) {
        if (session != sessionId || text != tail(original)) {
            clear()
            return
        }
        text = tail(edited) // Keep the original expiry; edits cannot prolong retention.
    }

    fun get(sessionId: Long, allowed: Boolean): String {
        val age = clock() - createdAt
        if (!allowed || session != sessionId || age !in 0..60_000L) clear()
        return text
    }

    fun clear() { session = null; text = ""; createdAt = 0L }

    private fun tail(value: String): String = value.substring(value.offsetByCodePoints(
        value.length, -minOf(512, value.codePointCount(0, value.length))))
}
