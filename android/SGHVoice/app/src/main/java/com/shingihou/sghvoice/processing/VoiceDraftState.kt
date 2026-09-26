package com.shingihou.sghvoice.processing

/** In-memory only: never auto-insert a draft after the editor changes. */
class VoiceDraftState {
    enum class PendingOrigin { DICTATION, TRANSLATION, COMPOSED_DRAFT, COMPOSE_OVERFLOW }

    data class PendingDraft(val text: String, val origin: PendingOrigin)

    companion object {
        const val MAX_COMPOSE_CHARACTERS = 8_000
        const val MAX_PENDING_CHARACTERS = 12_000
    }

    private val composeSegments = mutableListOf<String>()
    private var pendingDraft: PendingDraft? = null

    val hasComposeNotes: Boolean get() = composeSegments.isNotEmpty()
    val composeSegmentCount: Int get() = composeSegments.size
    val hasPendingText: Boolean get() = pendingDraft != null
    val pendingPreview: String get() = pendingDraft?.text.orEmpty().take(80)

    fun appendComposeSegment(text: String): Boolean {
        val normalized = text.trim()
        if (normalized.isBlank()) return false
        val proposedLength = composeNotes().length + normalized.length +
            if (composeSegments.isEmpty()) 0 else 1
        if (proposedLength > MAX_COMPOSE_CHARACTERS) return false
        composeSegments += normalized
        return true
    }

    fun composeNotes(): String = composeSegments.joinToString("\n")

    fun clearCompose() = composeSegments.clear()

    fun savePending(text: String, origin: PendingOrigin): Boolean {
        val normalized = text.trim()
        if (normalized.isBlank() || normalized.length > MAX_PENDING_CHARACTERS) return false
        pendingDraft = PendingDraft(normalized, origin)
        return true
    }

    fun peekPending(): PendingDraft? = pendingDraft

    fun clearPending() {
        pendingDraft = null
    }
}
