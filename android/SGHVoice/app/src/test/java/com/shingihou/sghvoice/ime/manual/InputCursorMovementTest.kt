package com.shingihou.sghvoice.ime.manual

import android.view.KeyEvent
import android.view.inputmethod.ExtractedText
import android.view.inputmethod.InputConnection
import org.junit.Assert.assertEquals
import org.junit.Test
import org.junit.runner.RunWith
import org.mockito.kotlin.any
import org.mockito.kotlin.argumentCaptor
import org.mockito.kotlin.eq
import org.mockito.kotlin.mock
import org.mockito.kotlin.times
import org.mockito.kotlin.verify
import org.mockito.kotlin.whenever
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35])
class InputCursorMovementTest {
    private fun connection(text: String, start: Int, end: Int = start, offset: Int = 0): InputConnection =
        mock<InputConnection>().also { connection ->
            whenever(connection.getExtractedText(any(), eq(0))).thenReturn(ExtractedText().apply {
                this.text = text
                selectionStart = start
                selectionEnd = end
                startOffset = offset
            })
            whenever(connection.setSelection(any(), any())).thenReturn(true)
        }

    @Test fun `cursor crosses emoji without splitting a surrogate pair`() {
        val left = connection("a😀b", 3)
        InputCursorMovement.move(left, toRight = false)
        verify(left).setSelection(1, 1)
        val right = connection("a😀b", 1)
        InputCursorMovement.move(right, toRight = true)
        verify(right).setSelection(3, 3)
    }

    @Test fun `selection collapses in movement direction and honors extracted offset`() {
        val left = connection("abcd", 3, 1, offset = 100)
        InputCursorMovement.move(left, toRight = false)
        verify(left).setSelection(101, 101)
        val right = connection("abcd", 1, 3, offset = 100)
        InputCursorMovement.move(right, toRight = true)
        verify(right).setSelection(103, 103)
    }

    @Test fun `editor without extracted text receives a paired arrow key event`() {
        val connection = mock<InputConnection>()
        InputCursorMovement.move(connection, toRight = true)
        val events = argumentCaptor<KeyEvent>()
        verify(connection, times(2)).sendKeyEvent(events.capture())
        assertEquals(listOf(KeyEvent.ACTION_DOWN, KeyEvent.ACTION_UP), events.allValues.map { it.action })
        assertEquals(listOf(KeyEvent.KEYCODE_DPAD_RIGHT, KeyEvent.KEYCODE_DPAD_RIGHT), events.allValues.map { it.keyCode })
    }
}
