package com.shingihou.sghvoice.ime

import android.text.InputType
import android.view.View
import android.view.inputmethod.BaseInputConnection
import android.view.inputmethod.EditorInfo
import android.widget.LinearLayout
import android.widget.TextView
import com.shingihou.sghvoice.R
import com.shingihou.sghvoice.ime.japanese.*
import com.shingihou.sghvoice.ime.manual.*
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith
import org.mockito.kotlin.doReturn
import org.mockito.kotlin.spy
import org.mockito.kotlin.mock
import android.view.inputmethod.InputConnection
import org.robolectric.Robolectric
import org.robolectric.RobolectricTestRunner
import org.robolectric.RuntimeEnvironment
import org.robolectric.annotation.Config

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35])
class AndroidInputUsabilityTest {
    private fun fixture(): Pair<VoiceInputIME, BaseInputConnection> {
        val ime = spy(Robolectric.buildService(VoiceInputIME::class.java).get())
        val connection = BaseInputConnection(View(RuntimeEnvironment.getApplication()), true)
        doReturn(connection).`when`(ime).currentInputConnection
        return ime to connection
    }
    private fun set(ime: VoiceInputIME, name: String, value: Any) =
        VoiceInputIME::class.java.getDeclaredField(name).apply { isAccessible = true }.set(ime, value)
    private fun get(ime: VoiceInputIME, name: String): Any? =
        VoiceInputIME::class.java.getDeclaredField(name).apply { isAccessible = true }.get(ime)
    private fun editor(id: Int = 42, password: Boolean = false) = EditorInfo().apply {
        packageName = "test.editor"
        fieldId = id
        inputType = InputType.TYPE_CLASS_TEXT or
            if (password) InputType.TYPE_TEXT_VARIATION_PASSWORD else InputType.TYPE_TEXT_FLAG_MULTI_LINE
    }

    @Test fun `same editor restart keeps active recording and operation tokens`() {
        for (state in listOf(VoiceInputIME.ImeState.STARTING, VoiceInputIME.ImeState.RECORDING)) {
            val (ime, _) = fixture()
            ime.onStartInput(editor(), false)
            set(ime, "currentState", state)
            val session = get(ime, "inputSessionId")
            val operation = get(ime, "voiceOperationId")
            ime.onStartInput(editor(), true)
            assertEquals(state, get(ime, "currentState"))
            assertEquals(session, get(ime, "inputSessionId"))
            assertEquals(operation, get(ime, "voiceOperationId"))
        }
    }

    @Test fun `different or sensitive editor and real view hide still stop recording`() {
        for (next in listOf(editor(43), editor(password = true))) {
            val (ime, _) = fixture()
            ime.onStartInput(editor(), false)
            set(ime, "currentState", VoiceInputIME.ImeState.RECORDING)
            ime.onStartInput(next, true)
            assertEquals(VoiceInputIME.ImeState.IDLE, get(ime, "currentState"))
        }
        val (ime, _) = fixture()
        ime.onStartInput(editor(), false)
        set(ime, "currentState", VoiceInputIME.ImeState.RECORDING)
        ime.onFinishInputView(false)
        assertEquals(VoiceInputIME.ImeState.IDLE, get(ime, "currentState"))
        ime.onStartInput(editor(), true)
        assertEquals(VoiceInputIME.ImeState.IDLE, get(ime, "currentState"))
    }

    @Test fun `new session even in same field cannot inherit recording and processing cannot rebind`() {
        for ((state, restarting) in listOf(VoiceInputIME.ImeState.RECORDING to false, VoiceInputIME.ImeState.PROCESSING to true)) {
            val (ime, _) = fixture()
            ime.onStartInput(editor(), false)
            set(ime, "currentState", state)
            ime.onStartInput(editor(), restarting)
            assertEquals(VoiceInputIME.ImeState.IDLE, get(ime, "currentState"))
        }
    }

    @Test fun `anonymous editor with a new connection fails closed on restart`() {
        for (id in listOf(0, View.NO_ID)) {
            val (ime, _) = fixture()
            ime.onStartInput(editor(id), false)
            set(ime, "currentState", VoiceInputIME.ImeState.RECORDING)
            doReturn(mock<InputConnection>()).`when`(ime).currentInputConnection
            ime.onStartInput(editor(id), true)
            assertEquals(VoiceInputIME.ImeState.IDLE, get(ime, "currentState"))
        }
    }

    @Test fun `active microphone keeps visible keyboard awake only until session ends`() {
        val (ime, _) = fixture()
        ime.onStartInput(editor(), false)
        set(ime, "currentState", VoiceInputIME.ImeState.RECORDING)
        val view = ime.onCreateInputView()
        assertTrue(view.keepScreenOn)
        ime.onFinishInputView(false)
        assertFalse(view.keepScreenOn)
    }

    @Test fun `Japanese Enter commits each plain vowel even with kanji candidates`() {
        for ((roman, kana) in listOf("a" to "あ", "i" to "い", "u" to "う", "e" to "え", "o" to "お")) {
            val (ime, connection) = fixture()
            set(ime, "currentInputMode", KeyboardView.InputMode.JAPANESE)
            set(ime, "japaneseComposer", JapaneseComposer(JapaneseLexicon { listOf(JapaneseLexiconEntry("漢字", 999)) }))
            ime.onKeyAction(KeyAction.InsertText(roman))
            ime.onKeyAction(KeyAction.Enter)
            assertEquals(kana, connection.editable.toString())
        }
    }

    @Test fun `emoji follows Japanese raw kana and English composition without breaking ZWJ`() {
        for (mode in listOf(KeyboardView.InputMode.JAPANESE, KeyboardView.InputMode.ENGLISH)) {
            val (ime, connection) = fixture()
            set(ime, "currentInputMode", mode)
            set(ime, "japaneseComposer", JapaneseComposer(JapaneseLexicon { listOf(JapaneseLexiconEntry("漢字", 999)) }))
            set(ime, "englishComposer", EnglishComposer())
            ime.onKeyAction(KeyAction.InsertText("a"))
            ime.onKeyAction(KeyAction.InsertEmoji("👨‍👩‍👧‍👦"))
            assertEquals((if (mode == KeyboardView.InputMode.JAPANESE) "あ" else "a") + "👨‍👩‍👧‍👦", connection.editable.toString())
        }
    }

    @Test fun `rejected emoji or raw kana commit retains pending input for retry`() {
        val (ime, connection) = fixture()
        val composer = JapaneseComposer(JapaneseLexicon { emptyList() })
        set(ime, "japaneseComposer", composer)
        set(ime, "currentInputMode", KeyboardView.InputMode.JAPANESE)
        ime.onKeyAction(KeyAction.InsertText("a"))
        doReturn(mock<InputConnection>()).`when`(ime).currentInputConnection
        ime.onKeyAction(KeyAction.Enter)
        assertTrue(composer.hasComposition)
        ime.onKeyAction(KeyAction.InsertEmoji("👍"))
        assertTrue(composer.hasComposition)
        doReturn(connection).`when`(ime).currentInputConnection
        ime.onKeyAction(KeyAction.InsertEmoji("👍"))
        assertEquals("あ👍", connection.editable.toString())
        assertFalse(composer.hasComposition)
    }

    @Test fun `production English provider shows suggestions and commits only explicit choice`() {
        val (ime, connection) = fixture()
        ime.onStartInput(editor(), false)
        set(ime, "currentInputMode", KeyboardView.InputMode.ENGLISH)
        val method = VoiceInputIME::class.java.getDeclaredMethod("buildEnglishCandidates", String::class.java, Int::class.javaPrimitiveType).apply { isAccessible = true }
        set(ime, "englishComposer", EnglishComposer(EnglishCandidateProvider { prefix, limit ->
            @Suppress("UNCHECKED_CAST")
            (method.invoke(ime, prefix, limit) as List<EnglishCandidate>)
        }))
        val view = ime.onCreateInputView()
        "hel".forEach { ime.onKeyAction(KeyAction.InsertText(it.toString())) }
        assertEquals("hel", connection.editable.toString())
        val candidates = view.findViewById<LinearLayout>(R.id.candidate_container)
        val hello = (0 until candidates.childCount).map { candidates.getChildAt(it) as TextView }.firstOrNull { it.text.toString() == "hello" }
        assertNotNull("Common words must appear without initializing a custom dictionary", hello)
        hello!!.performClick()
        assertEquals("hello ", connection.editable.toString())

        set(ime, "englishLexicon", AndroidEnglishCandidateProvider(RuntimeEnvironment.getApplication()))
        "infrastruc".forEach { ime.onKeyAction(KeyAction.InsertText(it.toString())) }
        val infrastructure = (0 until candidates.childCount).map { candidates.getChildAt(it) as TextView }
            .firstOrNull { it.text.toString() == "infrastructure" }
        assertNotNull("The packaged English dictionary must reach the real IME", infrastructure)
        infrastructure!!.performClick()
        assertEquals("hello infrastructure ", connection.editable.toString())

        for (privateEditor in listOf(editor(password = true), editor().apply { inputType = inputType or InputType.TYPE_TEXT_FLAG_NO_SUGGESTIONS })) {
            ime.onStartInput(privateEditor, false)
            "hel".forEach { ime.onKeyAction(KeyAction.InsertText(it.toString())) }
            assertFalse((0 until candidates.childCount).any { candidates.getChildAt(it).isClickable })
            if (privateEditor.inputType and InputType.TYPE_MASK_VARIATION == InputType.TYPE_TEXT_VARIATION_PASSWORD) {
                assertEquals("", view.findViewById<TextView>(R.id.tv_composition).text.toString())
            }
            val before = connection.editable.toString()
            ime.onCandidateSelected("hello")
            assertEquals(before, connection.editable.toString())
        }
    }
}
