package com.shingihou.sghvoice.ime

import android.view.View
import android.view.inputmethod.BaseInputConnection
import android.view.inputmethod.ExtractedText
import android.view.inputmethod.ExtractedTextRequest
import android.view.inputmethod.EditorInfo
import android.text.Selection
import com.shingihou.sghvoice.ime.japanese.JapaneseComposer
import com.shingihou.sghvoice.ime.japanese.JapaneseInputStyle
import com.shingihou.sghvoice.ime.manual.EnglishComposer
import com.shingihou.sghvoice.ime.manual.KeyAction
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.mockito.kotlin.doReturn
import org.mockito.kotlin.spy
import org.mockito.kotlin.verify
import org.robolectric.Robolectric
import org.robolectric.RobolectricTestRunner
import org.robolectric.RuntimeEnvironment
import org.robolectric.annotation.Config

/** Drives the real IME handlers against an editable Android InputConnection. */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35])
class ManualInputConnectionTest {
    private fun fixture(): Pair<VoiceInputIME, BaseInputConnection> {
        // Do not start onCreate: this test needs no audio, keys, dictionaries or network.
        val service = spy(Robolectric.buildService(VoiceInputIME::class.java).get())
        val connection = object : BaseInputConnection(View(RuntimeEnvironment.getApplication()), true) {
            override fun getExtractedText(request: ExtractedTextRequest?, flags: Int): ExtractedText =
                ExtractedText().apply {
                    text = editable.toString()
                    selectionStart = Selection.getSelectionStart(editable)
                    selectionEnd = Selection.getSelectionEnd(editable)
                    startOffset = 0
                }
        }
        doReturn(connection).`when`(service).currentInputConnection
        setField(service, "currentInputMode", KeyboardView.InputMode.ENGLISH)
        setField(service, "englishComposer", EnglishComposer())
        return service to connection
    }

    private fun setField(service: VoiceInputIME, name: String, value: Any) {
        VoiceInputIME::class.java.getDeclaredField(name).apply { isAccessible = true }.set(service, value)
    }

    private fun press(service: VoiceInputIME, connection: BaseInputConnection, action: KeyAction) {
        val editable = requireNotNull(connection.editable)
        val oldStart = Selection.getSelectionStart(editable)
        val oldEnd = Selection.getSelectionEnd(editable)
        service.onKeyAction(action)
        // Deliver the same selection/composition update an editor sends to an IME.
        service.onUpdateSelection(
            oldStart, oldEnd,
            Selection.getSelectionStart(editable),
            Selection.getSelectionEnd(editable),
            BaseInputConnection.getComposingSpanStart(editable),
            BaseInputConnection.getComposingSpanEnd(editable)
        )
    }

    private fun type(service: VoiceInputIME, connection: BaseInputConnection, word: String) {
        word.forEach { press(service, connection, KeyAction.InsertText(it.toString())) }
    }

    private fun assertEditor(connection: BaseInputConnection, text: String, cursor: Int) {
        assertEquals(text, connection.editable.toString())
        assertEquals(cursor, Selection.getSelectionStart(connection.editable))
        assertEquals(cursor, Selection.getSelectionEnd(connection.editable))
    }

    @Test fun `English space advances cursor then a new word types after the space`() {
        val (service, connection) = fixture()
        type(service, connection, "hello")
        assertEditor(connection, "hello", 5)
        press(service, connection, KeyAction.Space)
        assertEditor(connection, "hello ", 6)
        type(service, connection, "world")
        assertEditor(connection, "hello world", 11)
    }

    @Test fun `English enter advances cursor then a new word types on the next line`() {
        val (service, connection) = fixture()
        type(service, connection, "hello")
        press(service, connection, KeyAction.Enter)
        assertEditor(connection, "hello\n", 6)
        type(service, connection, "world")
        assertEditor(connection, "hello\nworld", 11)
    }

    @Test fun `consecutive English spaces each advance cursor before continuing typing`() {
        val (service, connection) = fixture()
        type(service, connection, "hello")
        repeat(3) { index ->
            press(service, connection, KeyAction.Space)
            assertEditor(connection, "hello" + " ".repeat(index + 1), 6 + index)
        }
        type(service, connection, "world")
        assertEditor(connection, "hello   world", 13)
    }

    @Test fun `space or enter replaces selected text and typing follows the new cursor`() {
        listOf(KeyAction.Space to " ", KeyAction.Enter to "\n").forEach { (action, separator) ->
            val (service, connection) = fixture()
            type(service, connection, "hello")
            connection.setSelection(1, 4)
            service.onUpdateSelection(5, 5, 1, 4, 0, 5)
            press(service, connection, action)
            assertEditor(connection, "h${separator}o", 2)
            type(service, connection, "world")
            assertEditor(connection, "h${separator}worldo", 7)
        }
    }

    @Test fun `multiline host enter flag keeps Enter as newline even when an action is present`() {
        val (service, connection) = fixture()
        doReturn(EditorInfo().apply {
            imeOptions = EditorInfo.IME_ACTION_SEND or EditorInfo.IME_FLAG_NO_ENTER_ACTION
        }).`when`(service).currentInputEditorInfo
        type(service, connection, "hello")
        press(service, connection, KeyAction.Enter)
        assertEditor(connection, "hello\n", 6)
        type(service, connection, "world")
        assertEditor(connection, "hello\nworld", 11)
    }

    @Test fun `explicit host send action still runs after committing the English word`() {
        val (service, baseConnection) = fixture()
        val connection = spy(baseConnection)
        doReturn(connection).`when`(service).currentInputConnection
        doReturn(true).`when`(connection).performEditorAction(EditorInfo.IME_ACTION_SEND)
        doReturn(EditorInfo().apply {
            imeOptions = EditorInfo.IME_ACTION_SEND
        }).`when`(service).currentInputEditorInfo
        type(service, connection, "hello")
        press(service, connection, KeyAction.Enter)
        verify(connection).performEditorAction(EditorInfo.IME_ACTION_SEND)
        assertEditor(connection, "hello", 5)
        assertEquals(-1, BaseInputConnection.getComposingSpanStart(requireNotNull(connection.editable)))
    }

    @Test fun `moving cursor while English is composing preserves word and inserts at new position`() {
        val (service, connection) = fixture()
        "hello".forEach { service.onKeyAction(KeyAction.InsertText(it.toString())) }
        connection.setSelection(0, 0)
        service.onUpdateSelection(5, 5, 0, 0, 0, 5)
        service.onKeyAction(KeyAction.InsertText("x"))
        assertEquals("xhello", connection.editable.toString())
    }

    @Test fun `English enter commits the word and performs newline in one press`() {
        val (service, connection) = fixture()
        "hello".forEach { service.onKeyAction(KeyAction.InsertText(it.toString())) }
        service.onKeyAction(KeyAction.Enter)
        assertEquals("hello\n", connection.editable.toString())
    }

    @Test fun `normal composing selection callback keeps the current English word`() {
        val (service, connection) = fixture()
        service.onKeyAction(KeyAction.InsertText("h"))
        service.onUpdateSelection(0, 0, 1, 1, 0, 1)
        service.onKeyAction(KeyAction.InsertText("i"))
        assertEquals("hi", connection.editable.toString())
    }

    @Test fun `selecting text while English is composing replaces only the selected text`() {
        val (service, connection) = fixture()
        "hello".forEach { service.onKeyAction(KeyAction.InsertText(it.toString())) }
        connection.setSelection(1, 4)
        service.onUpdateSelection(5, 5, 1, 4, 0, 5)
        service.onKeyAction(KeyAction.InsertText("x"))
        assertEquals("hxo", connection.editable.toString())
    }

    @Test fun `host ending composition starts a new English token without replaying the old word`() {
        val (service, connection) = fixture()
        "hi".forEach { service.onKeyAction(KeyAction.InsertText(it.toString())) }
        connection.finishComposingText()
        service.onUpdateSelection(2, 2, 2, 2, -1, -1)
        service.onKeyAction(KeyAction.InsertText("x"))
        assertEquals("hix", connection.editable.toString())
    }

    @Test fun `cursor controls move inside host text and next English key follows caret`() {
        val (service, connection) = fixture()
        "hello".forEach { service.onKeyAction(KeyAction.InsertText(it.toString())) }
        service.onKeyAction(KeyAction.CursorLeft)
        service.onKeyAction(KeyAction.CursorLeft)
        assertEquals(3, Selection.getSelectionStart(connection.editable))
        service.onKeyAction(KeyAction.CursorRight)
        assertEquals(4, Selection.getSelectionStart(connection.editable))
        service.onKeyAction(KeyAction.InsertText("x"))
        assertEquals("hellxo", connection.editable.toString())
    }

    @Test fun `Japanese cursor control commits pending kana and moves within the actual editor`() {
        val (service, connection) = fixture()
        val composer = JapaneseComposer().apply { setInputStyle(JapaneseInputStyle.KANA_12_KEY) }
        setField(service, "currentInputMode", KeyboardView.InputMode.JAPANESE)
        setField(service, "japaneseComposer", composer)
        setField(service, "japaneseInputStyle", JapaneseInputStyle.KANA_12_KEY)
        connection.commitText("前後", 1)
        connection.setSelection(1, 1)
        service.onKeyAction(KeyAction.TapJapaneseKana("na"))
        service.onKeyAction(KeyAction.TapJapaneseKana("na"))
        service.onKeyAction(KeyAction.CursorLeft)
        assertEquals("前に後", connection.editable.toString())
        assertEquals(1, Selection.getSelectionStart(connection.editable))
        assertTrue(!composer.hasComposition)
        service.onKeyAction(KeyAction.CursorRight)
        assertEquals(2, Selection.getSelectionStart(connection.editable))
    }
}
