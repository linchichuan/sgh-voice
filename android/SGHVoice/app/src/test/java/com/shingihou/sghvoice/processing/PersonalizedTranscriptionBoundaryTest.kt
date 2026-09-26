package com.shingihou.sghvoice.processing

import android.content.SharedPreferences
import com.shingihou.sghvoice.api.LlmClient
import com.shingihou.sghvoice.api.WhisperClient
import com.shingihou.sghvoice.learning.LearningLanguage
import com.shingihou.sghvoice.learning.LearningStorage
import com.shingihou.sghvoice.learning.PersonalizationRepository
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
        it.recordVoiceCorrection(LearningLanguage.MIXED, wrong, corrected, highConfidence = true)
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
        whenever(llm.refineDictation(any(), any(), any(), any())).thenAnswer {
            LlmClient.RefinementResult(it.getArgument(0), LlmClient.RefinementStatus.APPLIED)
        }
        val pipeline = TranscriptionPipeline(whisper, llm, dictionary, OpenCCConverter()) { true }

        val denied = pipeline.process(ByteArray(1), includePersonalization = false)
        assertEquals(wrong, denied.text)
        val sttHint = argumentCaptor<String>()
        val llmHint = argumentCaptor<String>()
        verify(whisper).transcribe(any(), sttHint.capture())
        verify(llm).refineDictation(eq(wrong), any(), llmHint.capture(), any())
        assertFalse(sttHint.firstValue.contains(corrected))
        assertFalse(llmHint.firstValue.contains(corrected))

        val allowed = pipeline.process(ByteArray(1), includePersonalization = true)
        assertEquals(corrected, allowed.text)
        val allowedHint = argumentCaptor<String>()
        verify(llm).refineDictation(eq(corrected), any(), allowedHint.capture(), any())
        assertTrue(allowedHint.firstValue.contains(corrected))
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
