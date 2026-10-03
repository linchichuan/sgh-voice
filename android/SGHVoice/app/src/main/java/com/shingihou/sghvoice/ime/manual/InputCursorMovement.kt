package com.shingihou.sghvoice.ime.manual

import android.view.KeyEvent
import android.view.inputmethod.ExtractedTextRequest
import android.view.inputmethod.InputConnection

/** Moves the editor caret, with DPAD fallback for editors that cannot expose text. */
internal object InputCursorMovement {
    fun move(connection: InputConnection, toRight: Boolean) {
        val extracted = connection.getExtractedText(ExtractedTextRequest().apply {
            hintMaxChars = 2048
            hintMaxLines = 10
        }, 0)
        val text = extracted?.text?.toString()
        if (extracted != null && text != null &&
            extracted.selectionStart in 0..text.length &&
            extracted.selectionEnd in 0..text.length
        ) {
            val start = minOf(extracted.selectionStart, extracted.selectionEnd)
            val end = maxOf(extracted.selectionStart, extracted.selectionEnd)
            val target = when {
                start != end -> if (toRight) end else start
                toRight && end < text.length -> text.offsetByCodePoints(end, 1)
                !toRight && start > 0 -> text.offsetByCodePoints(start, -1)
                else -> null // The snapshot may end before the document does.
            }
            if (target != null && connection.setSelection(
                    extracted.startOffset + target, extracted.startOffset + target
                )) return
        }
        val keyCode = if (toRight) KeyEvent.KEYCODE_DPAD_RIGHT else KeyEvent.KEYCODE_DPAD_LEFT
        connection.sendKeyEvent(KeyEvent(KeyEvent.ACTION_DOWN, keyCode))
        connection.sendKeyEvent(KeyEvent(KeyEvent.ACTION_UP, keyCode))
    }
}
