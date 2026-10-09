package com.shingihou.sghvoice.ime

import android.view.inputmethod.ExtractedTextRequest
import android.view.inputmethod.InputConnection

/** One in-memory, same-editor undo; never searches/replaces words in a document. */
internal class ZhuyinReselection {
    private data class Snapshot(val cursor: Int, val before: String, val after: String)
    private data class Choice(
        val connection: InputConnection, val session: Long, val reading: String,
        val text: String, val snapshot: Snapshot
    )
    private var choice: Choice? = null
    fun clear() { choice = null }

    fun remember(connection: InputConnection, session: Long, reading: String, text: String) {
        clear()
        if (text.isBlank() || text.length > 96 || reading.length > 256) return
        val snapshot = snapshot(connection) ?: return
        if (!snapshot.before.endsWith(text)) return
        choice = Choice(connection, session, reading, text, snapshot)
    }

    fun isAvailable(connection: InputConnection?, session: Long): Boolean {
        val saved = choice ?: return false
        if (connection !== saved.connection || session != saved.session) return false
        return snapshot(saved.connection) == saved.snapshot
    }

    fun restore(connection: InputConnection?, session: Long): String? {
        val saved = choice ?: return null
        if (!isAvailable(connection, session)) { clear(); return null }
        // The cursor, selection and bounded text on both sides must be unchanged.
        // If the editor cannot provide a trustworthy snapshot, do nothing.
        if (!saved.connection.deleteSurroundingTextInCodePoints(saved.text.codePointCount(0, saved.text.length), 0)) return null
        clear()
        return saved.reading
    }

    private fun snapshot(connection: InputConnection): Snapshot? {
        val extracted = connection.getExtractedText(ExtractedTextRequest().apply {
            hintMaxChars = 256
            hintMaxLines = 3
        }, 0) ?: return null
        if (extracted.selectionStart < 0 || extracted.selectionStart != extracted.selectionEnd) return null
        val before = connection.getTextBeforeCursor(128, 0)?.toString() ?: return null
        val after = connection.getTextAfterCursor(32, 0)?.toString() ?: return null
        return Snapshot(extracted.startOffset + extracted.selectionStart, before, after)
    }
}
