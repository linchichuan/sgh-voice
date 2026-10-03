package com.shingihou.sghvoice.processing

import android.content.SharedPreferences
import com.shingihou.sghvoice.api.LlmClient
import com.shingihou.sghvoice.api.WhisperClient
import com.shingihou.sghvoice.learning.LearningLanguage
import com.shingihou.sghvoice.learning.LearningStorage
import com.shingihou.sghvoice.learning.PersonalizationRepository
import com.shingihou.sghvoice.learning.RecentVoiceContext
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.async
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Assert.fail
import org.junit.Test
import org.mockito.kotlin.any
import org.mockito.kotlin.argumentCaptor
import org.mockito.kotlin.eq
import org.mockito.kotlin.mock
import org.mockito.kotlin.verify
import org.mockito.kotlin.verifyNoInteractions
import org.mockito.kotlin.whenever

/** Real dictionary/repository/pipeline, synthetic storage and network boundaries only. */
class PersonalizedTranscriptionBoundaryTest {
    private val wrong = "SyntheticWrong"
    private val corrected = "SyntheticCorrected"

    private fun repository() = PersonalizationRepository(BoundaryLearningStorage()).also {
        // A learned rule is 已生效 only after two voice turns (learning package spec 2).
        it.recordVoiceCorrection(LearningLanguage.MIXED, wrong, corrected, highConfidence = true, turnId = 1L)
        it.recordVoiceCorrection(LearningLanguage.MIXED, wrong, corrected, highConfidence = true, turnId = 2L)
    }

    @Test
    fun `context expiring while STT waits is omitted from both LLM tasks`() = runBlocking {
        val request = TranslationRequest.create(listOf(TranslationLanguage.ENGLISH))
        for (task in listOf(VoiceTask.Dictation, VoiceTask.Translation(request))) {
            var now = 0L
            val context = RecentVoiceContext { now }
            context.remember(1L, "Previous private voice segment.", true)
            now = 59_000L
            assertEquals("Previous private voice segment.", context.get(1L, true))
            val whisper = mock<WhisperClient>()
            val llm = mock<LlmClient>()
            whenever(whisper.transcribe(any(), any())).thenAnswer {
                now = 61_000L
                wrong
            }
            whenever(llm.refineDictation(any(), any(), any(), any(), any())).thenAnswer {
                LlmClient.RefinementResult(it.getArgument(0), LlmClient.RefinementStatus.APPLIED)
            }
            whenever(llm.translate(any(), any(), any())).thenAnswer {
                listOf(TranslationOutput(TranslationLanguage.ENGLISH, it.getArgument(0)))
            }
            val pipeline = TranscriptionPipeline(whisper, llm,
                DictionaryManager(mock<SharedPreferences>()) { repository() }, OpenCCConverter()) { true }
            assertTrue(pipeline.process(ByteArray(1), task, includePersonalization = true,
                recentContext = { context.get(1L, true) }).success)
            if (task == VoiceTask.Dictation) {
                verify(llm).refineDictation(eq(corrected), any(), any(), any(), eq(""))
            } else {
                verify(llm).translate(corrected, request, "")
            }
        }
    }

    @Test
    fun `context cleared or corrected during STT is read afresh for both tasks`() = runBlocking {
        val request = TranslationRequest.create(listOf(TranslationLanguage.ENGLISH))
        for (task in listOf(VoiceTask.Dictation, VoiceTask.Translation(request))) {
            for (edited in listOf("", "Please use Kotlin.")) {
                val context = RecentVoiceContext { 1L }
                context.remember(1L, "Please use Kotlun.", true)
                val whisper = mock<WhisperClient>()
                val llm = mock<LlmClient>()
                whenever(whisper.transcribe(any(), any())).thenAnswer {
                    if (edited.isEmpty()) context.clear()
                    else context.corrected(1L, "Please use Kotlun.", edited)
                    wrong
                }
                whenever(llm.refineDictation(any(), any(), any(), any(), any())).thenAnswer {
                    LlmClient.RefinementResult(it.getArgument(0), LlmClient.RefinementStatus.APPLIED)
                }
                whenever(llm.translate(any(), any(), any())).thenAnswer {
                    listOf(TranslationOutput(TranslationLanguage.ENGLISH, it.getArgument(0)))
                }
                val pipeline = TranscriptionPipeline(whisper, llm,
                    DictionaryManager(mock<SharedPreferences>()) { repository() }, OpenCCConverter()) { true }
                assertTrue(pipeline.process(ByteArray(1), task, includePersonalization = true,
                    recentContext = { context.get(1L, true) }).success)
                if (task == VoiceTask.Dictation) {
                    verify(llm).refineDictation(eq(corrected), any(), any(), any(), eq(edited))
                } else {
                    verify(llm).translate(corrected, request, edited)
                }
            }
        }
    }

    @Test
    fun `forbidden field never reads learned vocabulary or applies learned corrections`() {
        val dictionary = DictionaryManager(mock<SharedPreferences>()) {
            error("Forbidden field must not load the personalization repository")
        }

        assertFalse(dictionary.buildWhisperPrompt(includePersonalization = false).contains(corrected))
        assertFalse(dictionary.buildLlmVocabularyHint(wrong, includePersonalization = false).contains(corrected))
        assertEquals(wrong, dictionary.applyCorrections(wrong, includePersonalization = false))
        // Callers without an explicit field decision fail closed as well.
        assertFalse(dictionary.buildWhisperPrompt().contains(corrected))
        assertEquals(wrong, dictionary.applyCorrections(wrong))
    }

    @Test
    fun `allowed field can use learned terms but global disable immediately suppresses them`() {
        val repository = repository()
        val dictionary = DictionaryManager(mock<SharedPreferences>()) { repository }

        assertTrue(dictionary.buildWhisperPrompt(includePersonalization = true).contains(corrected))
        assertTrue(dictionary.buildLlmVocabularyHint(wrong, includePersonalization = true).contains(corrected))
        assertEquals(corrected, dictionary.applyCorrections(wrong, includePersonalization = true))

        repository.setEnabled(false)
        assertFalse(dictionary.buildWhisperPrompt(includePersonalization = true).contains(corrected))
        assertFalse(dictionary.buildLlmVocabularyHint(wrong, includePersonalization = true).contains(corrected))
        assertEquals(wrong, dictionary.applyCorrections(wrong, includePersonalization = true))
    }

    @Test
    fun `dictation field decision reaches both network hints and both correction stages`() = runBlocking {
        val dictionary = DictionaryManager(mock<SharedPreferences>()) { repository() }
        val whisper = mock<WhisperClient>()
        val llm = mock<LlmClient>()
        whenever(whisper.transcribe(any(), any())).thenReturn(wrong)
        whenever(llm.refineDictation(any(), any(), any(), any(), any())).thenAnswer {
            LlmClient.RefinementResult(it.getArgument(0), LlmClient.RefinementStatus.APPLIED)
        }
        val pipeline = TranscriptionPipeline(whisper, llm, dictionary, OpenCCConverter()) { true }

        val context = "先前提到的專案，今天繼續處理。"
        val denied = pipeline.process(ByteArray(1), includePersonalization = false,
            recentContext = { error("Forbidden field must not read recent context") })
        assertEquals(wrong, denied.text)
        val sttHint = argumentCaptor<String>()
        val llmHint = argumentCaptor<String>()
        verify(whisper).transcribe(any(), sttHint.capture())
        verify(llm).refineDictation(eq(wrong), any(), llmHint.capture(), any(), eq(""))
        assertFalse(sttHint.firstValue.contains(corrected))
        assertFalse(llmHint.firstValue.contains(corrected))

        val allowed = pipeline.process(ByteArray(1), includePersonalization = true, recentContext = { context })
        assertEquals(corrected, allowed.text)
        val allowedHint = argumentCaptor<String>()
        verify(llm).refineDictation(eq(corrected), any(), allowedHint.capture(), any(), eq(context))
        assertTrue(allowedHint.firstValue.contains(corrected))
    }

    @Test
    fun `translation previous context requires the same explicit field opt in`() = runBlocking<Unit> {
        val dictionary = DictionaryManager(mock<SharedPreferences>()) { repository() }
        val whisper = mock<WhisperClient>()
        val llm = mock<LlmClient>()
        val request = TranslationRequest.create(listOf(TranslationLanguage.ENGLISH))
        whenever(whisper.transcribe(any(), any())).thenReturn(wrong)
        whenever(llm.translate(any(), any(), any())).thenAnswer {
            listOf(TranslationOutput(TranslationLanguage.ENGLISH, it.getArgument(0)))
        }
        val pipeline = TranscriptionPipeline(whisper, llm, dictionary, OpenCCConverter()) { true }
        val context = "Previous voice segment."
        pipeline.process(ByteArray(1), VoiceTask.Translation(request),
            recentContext = { error("Forbidden field must not read recent context") })
        verify(llm).translate(wrong, request, "")
        val translated = pipeline.process(ByteArray(1), VoiceTask.Translation(request),
            includePersonalization = true, recentContext = { context })
        assertEquals(corrected, translated.sourceText)
        verify(llm).translate(corrected, request, context)
    }

    @Test
    fun `translation and stt only default to no learned terms`() = runBlocking {
        val dictionary = DictionaryManager(mock<SharedPreferences>()) {
            error("Default field policy must not read learned data")
        }
        val whisper = mock<WhisperClient>()
        val llm = mock<LlmClient>()
        val request = TranslationRequest.create(listOf(TranslationLanguage.ENGLISH))
        whenever(whisper.transcribe(any(), any())).thenReturn(wrong)
        whenever(llm.translate(wrong, request)).thenReturn(listOf(TranslationOutput(TranslationLanguage.ENGLISH, wrong)))
        val pipeline = TranscriptionPipeline(whisper, llm, dictionary, OpenCCConverter()) { true }

        assertEquals(wrong, pipeline.process(ByteArray(1), VoiceTask.Translation(request)).text)
        assertEquals(wrong, pipeline.transcribeOnly(ByteArray(1)).text)
    }

    @Test
    fun `context revoked during STT never reaches dictation or translation`() = runBlocking {
        val request = TranslationRequest.create(listOf(TranslationLanguage.ENGLISH))
        for (task in listOf(VoiceTask.Dictation, VoiceTask.Translation(request))) {
            var contextAllowed = true
            val dictionary = DictionaryManager(mock<SharedPreferences>()) { repository() }
            val whisper = mock<WhisperClient>()
            val llm = mock<LlmClient>()
            whenever(whisper.transcribe(any(), any())).thenAnswer {
                contextAllowed = false // The host changes field or the user disables recent context.
                wrong
            }
            whenever(llm.refineDictation(any(), any(), any(), any(), any())).thenAnswer {
                LlmClient.RefinementResult(it.getArgument(0), LlmClient.RefinementStatus.APPLIED)
            }
            whenever(llm.translate(any(), any(), any())).thenAnswer {
                listOf(TranslationOutput(TranslationLanguage.ENGLISH, it.getArgument(0)))
            }
            val pipeline = TranscriptionPipeline(whisper, llm, dictionary, OpenCCConverter()) { true }
            val result = pipeline.process(ByteArray(1), task, includePersonalization = true,
                recentContext = { if (contextAllowed) "Prior private field context." else "" })
            assertTrue(result.success)
            if (task == VoiceTask.Dictation) {
                verify(llm).refineDictation(eq(corrected), any(), any(), any(), eq(""))
            } else {
                verify(llm).translate(corrected, request, "")
            }
        }
    }

    @Test
    fun `context revoked by LLM progress callback is rechecked at the request boundary`() = runBlocking<Unit> {
        var contextAllowed = true
        val dictionary = DictionaryManager(mock<SharedPreferences>()) { repository() }
        val whisper = mock<WhisperClient>()
        val llm = mock<LlmClient>()
        whenever(whisper.transcribe(any(), any())).thenReturn(wrong)
        whenever(llm.refineDictation(any(), any(), any(), any(), any())).thenAnswer {
            LlmClient.RefinementResult(it.getArgument(0), LlmClient.RefinementStatus.APPLIED)
        }
        val callback = object : TranscriptionPipeline.ProgressCallback {
            override fun onWhisperStarted() = Unit
            override fun onWhisperCompleted(text: String) = Unit
            override fun onLlmStarted() { contextAllowed = false }
            override fun onCompleted(result: TranscriptionPipeline.Result) = Unit
            override fun onError(error: String) = Unit
        }
        val pipeline = TranscriptionPipeline(whisper, llm, dictionary, OpenCCConverter()) { true }
        val result = pipeline.process(ByteArray(1), callback, includePersonalization = true,
            recentContext = { if (contextAllowed) "Prior private field context." else "" })
        assertTrue(result.success)
        verify(llm).refineDictation(eq(corrected), any(), any(), any(), eq(""))
    }

    @Test
    fun `cancelled editor operation cannot send a follow up llm request after late stt completion`() = runBlocking {
        val dictionary = DictionaryManager(mock<SharedPreferences>()) {
            error("No field opt-in must mean no learned data")
        }
        val whisper = mock<WhisperClient>()
        val llm = mock<LlmClient>()
        val pipeline = TranscriptionPipeline(whisper, llm, dictionary, OpenCCConverter()) { true }
        val operation = async(start = CoroutineStart.LAZY) { pipeline.process(ByteArray(1)) }
        whenever(whisper.transcribe(any(), any())).thenAnswer {
            operation.cancel()
            wrong // Simulate an STT transport completing while the editor is replaced.
        }

        operation.start()
        try {
            operation.await()
            fail("The obsolete editor operation must remain cancelled")
        } catch (_: CancellationException) {
            // Cancellation must propagate instead of turning into fallback text.
        }
        verifyNoInteractions(llm)
    }
}

private class BoundaryLearningStorage : LearningStorage {
    private val values = mutableMapOf<String, Any?>()
    override fun getString(key: String, defaultValue: String?) = values[key] as? String ?: defaultValue
    override fun getInt(key: String, defaultValue: Int) = values[key] as? Int ?: defaultValue
    override fun getBoolean(key: String, defaultValue: Boolean) = values[key] as? Boolean ?: defaultValue
    override fun update(values: Map<String, Any?>) { this.values.putAll(values) }
}
