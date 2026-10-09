package com.shingihou.sghvoice.ime

import android.view.View
import android.view.inputmethod.BaseInputConnection
import android.view.inputmethod.ExtractedText
import android.view.inputmethod.ExtractedTextRequest
import android.text.Selection
import android.view.inputmethod.InputConnection
import com.shingihou.sghvoice.ime.manual.KeyAction
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith
import org.mockito.kotlin.doReturn
import org.mockito.kotlin.spy
import org.mockito.kotlin.mock
import org.robolectric.Robolectric
import org.robolectric.RobolectricTestRunner
import org.robolectric.RuntimeEnvironment
import org.robolectric.annotation.Config

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35])
class ZhuyinPartialSelectionTest {
    private val lexicon = ZhuyinLexicon { reading ->
        when (reading) {
            "ㄅㄨˋ" -> listOf(ZhuyinLexiconEntry("不", 100), ZhuyinLexiconEntry("部", 90))
            "ㄓ" -> listOf(ZhuyinLexiconEntry("知", 100), ZhuyinLexiconEntry("之", 90))
            "ㄉㄠˋ" -> listOf(ZhuyinLexiconEntry("道", 100))
            "ㄅㄨˋ ㄓ" -> listOf(ZhuyinLexiconEntry("不知", 100))
            "ㄓ ㄉㄠˋ" -> listOf(ZhuyinLexiconEntry("知道", 100))
            "ㄅㄨˋ ㄓ ㄉㄠˋ" -> listOf(ZhuyinLexiconEntry("不知道", 100))
            else -> emptyList()
        }
    }
    private fun field(ime: VoiceInputIME, name: String, value: Any) =
        VoiceInputIME::class.java.getDeclaredField(name).apply { isAccessible = true }.set(ime, value)
    private fun fixture(composer: ZhuyinComposer): Pair<VoiceInputIME, BaseInputConnection> {
        val ime = spy(Robolectric.buildService(VoiceInputIME::class.java).get())
        val connection = object : BaseInputConnection(View(RuntimeEnvironment.getApplication()), true) {
            override fun getExtractedText(request: ExtractedTextRequest?, flags: Int) = ExtractedText().apply {
                text = editable.toString()
                selectionStart = Selection.getSelectionStart(editable)
                selectionEnd = Selection.getSelectionEnd(editable)
                startOffset = 0
            }
        }
        doReturn(connection).`when`(ime).currentInputConnection
        field(ime, "currentInputMode", KeyboardView.InputMode.ZHUYIN)
        field(ime, "zhuyinComposer", composer)
        return ime to connection
    }

    @Test fun `one accidental trailing sound does not hide the correct leading phrase`() {
        val composer = ZhuyinComposer(lexicon)
        assertTrue(composer.setComposition("ㄅㄨˋ ㄓ ㄉㄠˋ ㄅ"))
        assertEquals("不知道", composer.getCandidates(48).first().text)
        assertTrue(composer.getCandidates(48).any { it.text == "不" })
    }

    @Test fun `head word selection preserves unselected reading instead of clearing it`() {
        val composer = ZhuyinComposer(lexicon)
        composer.setComposition("ㄅㄨˋ ㄓ ㄉㄠˋ")
        val candidates = composer.getCandidates(48)
        assertEquals("不知道", candidates.first().text)
        val index = candidates.indexOfFirst { it.text == "不" }
        assertTrue("The head character must remain independently selectable", index >= 0)
        assertEquals("不", composer.selectCandidate(index, 48)?.text)
        assertEquals("ㄓ ㄉㄠˋ", composer.normalizedReading)
    }

    @Test fun `real IME can choose head then remaining word without losing or duplicating sounds`() {
        val composer = ZhuyinComposer(lexicon)
        composer.setComposition("ㄅㄨˋ ㄓ ㄉㄠˋ")
        val (ime, connection) = fixture(composer)
        ime.onCandidateSelected("不")
        assertEquals("不", connection.editable.toString())
        assertEquals("ㄓ ㄉㄠˋ", composer.normalizedReading)
        ime.onCandidateSelected("知道")
        assertEquals("不知道", connection.editable.toString())
        assertFalse(composer.hasComposition)
    }

    @Test fun `extra tail remains editable after choosing leading phrase`() {
        val composer = ZhuyinComposer(lexicon)
        composer.setComposition("ㄅㄨˋ ㄓ ㄉㄠˋ ㄅ")
        val (ime, connection) = fixture(composer)
        ime.onCandidateSelected("不知道")
        assertEquals("不知道", connection.editable.toString())
        assertEquals("ㄅ", composer.normalizedReading)
        ime.onKeyAction(KeyAction.Backspace)
        assertFalse(composer.hasComposition)
        assertEquals("不知道", connection.editable.toString())
    }

    @Test fun `wrong head can be reselected once without losing its remaining reading`() {
        val composer = ZhuyinComposer(lexicon)
        composer.setComposition("ㄅㄨˋ ㄓ ㄉㄠˋ")
        val (ime, connection) = fixture(composer)
        ime.onCandidateSelected("部")
        assertEquals("部", connection.editable.toString())
        ime.onZhuyinReselectRequested()
        assertEquals("", connection.editable.toString())
        assertEquals("ㄅㄨˋ ㄓ ㄉㄠˋ", composer.normalizedReading)
        ime.onCandidateSelected("不知道")
        assertEquals("不知道", connection.editable.toString())
        ime.onZhuyinReselectRequested()
        ime.onZhuyinReselectRequested()
        assertEquals("", connection.editable.toString())
    }

    @Test fun `reselection does not delete after cursor move or another typed key`() {
        for (moveCursor in listOf(true, false)) {
            val composer = ZhuyinComposer(lexicon)
            composer.setComposition("ㄅㄨˋ ㄓ ㄉㄠˋ")
            val (ime, connection) = fixture(composer)
            ime.onCandidateSelected("不")
            if (moveCursor) connection.setSelection(0, 0) else ime.onKeyAction(KeyAction.InsertText("ㄅ"))
            val remaining = composer.composition
            ime.onZhuyinReselectRequested()
            assertEquals("不", connection.editable.toString())
            assertEquals(remaining, composer.composition)
        }
    }

    @Test fun `failed head commit keeps complete reading for a later retry`() {
        val composer = ZhuyinComposer(lexicon)
        composer.setComposition("ㄅㄨˋ ㄓ ㄉㄠˋ")
        val (ime, connection) = fixture(composer)
        doReturn(mock<InputConnection>()).`when`(ime).currentInputConnection
        ime.onCandidateSelected("不")
        assertEquals("ㄅㄨˋ ㄓ ㄉㄠˋ", composer.normalizedReading)
        doReturn(connection).`when`(ime).currentInputConnection
        ime.onCandidateSelected("不")
        assertEquals("不", connection.editable.toString())
        assertEquals("ㄓ ㄉㄠˋ", composer.normalizedReading)
    }

    @Test fun `emoji confirmation cannot discard the tail of a partial candidate`() {
        val composer = ZhuyinComposer(lexicon)
        composer.setComposition("ㄅㄨˋ ㄓ ㄉㄠˋ ㄅ")
        val (ime, connection) = fixture(composer)
        ime.onKeyAction(KeyAction.InsertEmoji("🙂"))
        assertTrue(connection.editable.toString().contains("ㄅ"))
        assertTrue(connection.editable.toString().endsWith("🙂"))
        assertFalse(composer.hasComposition)
    }

    @Test fun `reselection refuses another connection session or edited nearby text`() {
        for (change in listOf("connection", "session", "text")) {
            val composer = ZhuyinComposer(lexicon)
            composer.setComposition("ㄅㄨˋ ㄓ ㄉㄠˋ")
            val (ime, connection) = fixture(composer)
            ime.onCandidateSelected("不")
            when (change) {
                "connection" -> doReturn(mock<InputConnection>()).`when`(ime).currentInputConnection
                "session" -> field(ime, "inputSessionId", 999L)
                "text" -> { connection.setSelection(0, 1); connection.commitText("另", 1) }
            }
            val before = connection.editable.toString()
            ime.onZhuyinReselectRequested()
            assertEquals(before, connection.editable.toString())
            assertEquals("ㄓ ㄉㄠˋ", composer.normalizedReading)
        }
    }
}
