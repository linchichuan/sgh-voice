package com.shingihou.sghvoice.processing

import com.shingihou.sghvoice.api.LlmClient
import com.shingihou.sghvoice.api.WhisperClient
import com.shingihou.sghvoice.api.CloudProcessingConsentException
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertThrows
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertSame
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import org.mockito.Mock
import org.mockito.Mockito.`when`
import org.mockito.MockitoAnnotations
import org.mockito.kotlin.any
import org.mockito.kotlin.times
import org.mockito.kotlin.verify
import org.mockito.Mockito.verifyNoInteractions

/**
 * 處理管線單元測試
 */
class TranscriptionPipelineTest {

    @Mock
    private lateinit var whisperClient: WhisperClient
    @Mock
    private lateinit var llmClient: LlmClient
    @Mock
    private lateinit var dictionaryManager: DictionaryManager
    
    private lateinit var openCCConverter: OpenCCConverter
    private lateinit var pipeline: TranscriptionPipeline
    private var cloudConsent = true

    @Before
    fun setup() {
        MockitoAnnotations.openMocks(this)
        openCCConverter = OpenCCConverter() // 使用真實物件測試轉換邏輯
        pipeline = TranscriptionPipeline(
            whisperClient, llmClient, dictionaryManager, openCCConverter,
            cloudProcessingAllowed = { cloudConsent }
        )
    }

    @Test
    fun `測試完整管線流程 - 包含詞庫修正與繁簡轉換`() = runBlocking {
        val rawWav = ByteArray(100)
        val whisperRawResult = "我的公司是新义丰，在fukuoka。"
        val whisperPrompt = "新義豊、福岡"
        
        // 1. 模擬 Whisper 回傳
        `when`(dictionaryManager.buildWhisperPrompt()).thenReturn(whisperPrompt)
        `when`(whisperClient.transcribe(any(), any())).thenReturn(whisperRawResult)
        
        // 2. 模擬詞庫修正：新义丰 -> 新義豊
        `when`(dictionaryManager.applyCorrections(whisperRawResult)).thenReturn("我的公司是新義豊，在fukuoka。")
        `when`(dictionaryManager.applyCorrections("我的公司是新義豊，在 Fukuoka。"))
            .thenReturn("我的公司是新義豊，在 Fukuoka。")
        `when`(dictionaryManager.getSceneSystemPromptExtra()).thenReturn("")
        `when`(dictionaryManager.buildLlmVocabularyHint(any(), any())).thenReturn("[]")
        
        // 3. 模擬 LLM 潤稿：加上標點、去填充詞
        `when`(llmClient.refineDictation("我的公司是新義豊，在fukuoka。", "", "[]"))
            .thenReturn(LlmClient.RefinementResult("我的公司是新義豊，在 Fukuoka。", LlmClient.RefinementStatus.APPLIED))

        // 執行管線
        val result = pipeline.process(rawWav)

        // 4. 驗證結果 (OpenCC 會將 "Fukuoka" 保持原樣，並確保中文部分正確)
        assertEquals("我的公司是新義豊，在 Fukuoka。", result.text)
        assertEquals(true, result.success)
        assertEquals(LlmClient.RefinementStatus.APPLIED, result.refinementStatus)
        assertNotNull(result.timings)
        assertTrue(result.timings!!.recognitionMs >= 0)
        assertTrue(result.timings.textProcessingMs >= 0)
        assertTrue(result.timings.totalMs >= result.timings.recognitionMs + result.timings.textProcessingMs)
    }

    @Test
    fun `測試 OpenCC 轉換邏輯`() {
        val input = "语音输入法测试，日本人，English test."
        val expected = "語音輸入法測試，日本人，English test."
        val actual = openCCConverter.convert(input)
        assertEquals(expected, actual)
    }

    @Test
    fun `translation converts only zh-Hant and does not apply final source corrections`() =
        runBlocking {
            val rawWav = ByteArray(100)
            val rawText = "请确认明天的时间"
            val correctedSource = "请确认明天的时间"
            val request = TranslationRequest.create(
                listOf(
                    TranslationLanguage.TRADITIONAL_CHINESE,
                    TranslationLanguage.JAPANESE
                )
            )

            `when`(dictionaryManager.buildWhisperPrompt()).thenReturn("")
            `when`(whisperClient.transcribe(any(), any())).thenReturn(rawText)
            `when`(dictionaryManager.applyCorrections(rawText)).thenReturn(correctedSource)
            `when`(llmClient.translate(correctedSource, request)).thenReturn(
                listOf(
                    TranslationOutput(
                        TranslationLanguage.TRADITIONAL_CHINESE,
                        "请确认明天的时间"
                    ),
                    TranslationOutput(
                        TranslationLanguage.JAPANESE,
                        "明日の時間をご確認ください"
                    )
                )
            )

            var completed: TranscriptionPipeline.Result? = null
            val callback = object : TranscriptionPipeline.ProgressCallback {
                override fun onWhisperStarted() = Unit
                override fun onWhisperCompleted(text: String) = Unit
                override fun onLlmStarted() = Unit
                override fun onCompleted(result: TranscriptionPipeline.Result) { completed = result }
                override fun onError(error: String) = Unit
            }
            val result = pipeline.process(
                rawWav,
                VoiceTask.Translation(request), callback
            )

            assertEquals(true, result.success)
            assertEquals("請確認明天的時間", result.translations[0].text)
            assertEquals("明日の時間をご確認ください", result.translations[1].text)
            assertSame(result, completed)
            assertNotNull(result.timings)
            assertTrue(result.timings!!.totalMs >= result.timings.recognitionMs + result.timings.textProcessingMs)
            verify(whisperClient, times(1)).transcribe(any(), any())
            verify(llmClient, times(1)).translate(correctedSource, request)
            verify(llmClient, times(0)).refineDictation(any(), any(), any(), any(), any())
            verify(dictionaryManager, times(1)).applyCorrections(rawText)
            Unit
        }

    @Test
    fun `translation failure does not fall back to the source text`() = runBlocking {
        val rawWav = ByteArray(100)
        val rawText = "你好"
        val request = TranslationRequest.create(listOf(TranslationLanguage.JAPANESE))

        `when`(dictionaryManager.buildWhisperPrompt()).thenReturn("")
        `when`(whisperClient.transcribe(any(), any())).thenReturn(rawText)
        `when`(dictionaryManager.applyCorrections(rawText)).thenReturn(rawText)
        `when`(llmClient.translate(rawText, request))
            .thenThrow(IllegalStateException("malformed translation"))

        val result = pipeline.process(
            rawWav,
            VoiceTask.Translation(request)
        )

        assertEquals(false, result.success)
        assertEquals("", result.text)
        assertEquals(emptyList<TranslationOutput>(), result.translations)
    }

    @Test
    fun `compose audio captures a brief without using dictation or auto-generating`() = runBlocking {
        val wav = ByteArray(100)
        val raw = "幫我寫一封信給 Emma，週五約時間。"
        `when`(dictionaryManager.buildWhisperPrompt()).thenReturn("")
        `when`(whisperClient.transcribe(any(), any())).thenReturn(raw)
        `when`(dictionaryManager.applyCorrections(raw)).thenReturn(raw)

        val captured = pipeline.process(wav, VoiceTask.Compose)

        assertEquals(true, captured.success)
        assertEquals(raw, captured.text)
        verifyNoInteractions(llmClient)
        Unit
    }

    @Test
    fun `compose happens only after explicit final action`() = runBlocking {
        val notes = "第一段：詢問週五下午。\n第二段：署名 Will。"
        `when`(llmClient.compose(notes)).thenReturn("Emma 您好：\n請問週五下午方便嗎？\nWill")

        assertEquals(
            "Emma 您好：\n請問週五下午方便嗎？\nWill",
            pipeline.composeNotes(notes)
        )
        verify(llmClient, times(1)).compose(notes)
        Unit
    }

    @Test
    fun `compose preserves Japanese characters without traditional Chinese conversion`() = runBlocking {
        val notes = "発表会の案内を書いてください。"
        val draft = "日本語の発表会、医療資料を送信します。"
        `when`(llmClient.compose(notes)).thenReturn(draft)

        assertEquals(draft, pipeline.composeNotes(notes))
        Unit
    }

    @Test
    fun `revoked consent blocks STT before reading vocabulary or sending audio`() = runBlocking {
        cloudConsent = false

        val result = pipeline.process(ByteArray(100))
        val sttOnly = pipeline.transcribeOnly(ByteArray(100))

        assertEquals(false, result.success)
        assertEquals(CloudProcessingConsentException.MESSAGE, result.error)
        assertEquals(false, sttOnly.success)
        verifyNoInteractions(whisperClient, llmClient, dictionaryManager)
        Unit
    }

    @Test
    fun `consent withdrawn during STT blocks corrections and follow up LLM`() = runBlocking {
        `when`(dictionaryManager.buildWhisperPrompt()).thenReturn("")
        `when`(whisperClient.transcribe(any(), any())).thenAnswer {
            cloudConsent = false
            "synthetic private spoken content"
        }

        val result = pipeline.process(ByteArray(100))

        assertEquals(false, result.success)
        assertEquals("", result.text)
        assertEquals("", result.rawText)
        assertEquals(CloudProcessingConsentException.MESSAGE, result.error)
        verify(dictionaryManager, times(0)).applyCorrections(any(), any())
        verifyNoInteractions(llmClient)
        Unit
    }

    @Test
    fun `consent is checked at LLM boundary after progress callback`() = runBlocking {
        val raw = "synthetic content"
        `when`(dictionaryManager.buildWhisperPrompt()).thenReturn("")
        `when`(whisperClient.transcribe(any(), any())).thenReturn(raw)
        `when`(dictionaryManager.applyCorrections(raw)).thenReturn(raw)
        `when`(dictionaryManager.getSceneSystemPromptExtra()).thenReturn("")
        `when`(dictionaryManager.buildLlmVocabularyHint(any(), any())).thenReturn("[]")
        val callback = object : TranscriptionPipeline.ProgressCallback {
            override fun onWhisperStarted() = Unit
            override fun onWhisperCompleted(text: String) = Unit
            override fun onLlmStarted() { cloudConsent = false }
            override fun onCompleted(result: TranscriptionPipeline.Result) = Unit
            override fun onError(error: String) = Unit
        }

        val result = pipeline.process(ByteArray(100), callback)

        assertEquals(false, result.success)
        assertEquals(CloudProcessingConsentException.MESSAGE, result.error)
        verifyNoInteractions(llmClient)
        Unit
    }

    @Test
    fun `compose cannot generate after consent is withdrawn`() {
        cloudConsent = false
        assertThrows(CloudProcessingConsentException::class.java) {
            runBlocking { pipeline.composeNotes("synthetic private brief") }
        }
        verifyNoInteractions(llmClient)
    }

    @Test
    fun `LLM boundary consent failure cannot become successful dictation fallback`() = runBlocking {
        val raw = "synthetic private words"
        `when`(dictionaryManager.buildWhisperPrompt()).thenReturn("")
        `when`(whisperClient.transcribe(any(), any())).thenReturn(raw)
        `when`(dictionaryManager.applyCorrections(raw)).thenReturn(raw)
        `when`(dictionaryManager.getSceneSystemPromptExtra()).thenReturn("")
        `when`(dictionaryManager.buildLlmVocabularyHint(any(), any())).thenReturn("[]")
        `when`(llmClient.refineDictation(raw, "", "[]"))
            .thenAnswer { throw CloudProcessingConsentException() }

        val result = pipeline.process(ByteArray(100))

        assertEquals(false, result.success)
        assertEquals("", result.text)
        assertEquals(CloudProcessingConsentException.MESSAGE, result.error)
    }

    @Test
    fun `disabled unavailable and rejected cleanup preserve raw paragraphs with honest status`() = runBlocking {
        val raw = "啊，我我還不確定。\n\n先不要部署。"
        `when`(dictionaryManager.buildWhisperPrompt()).thenReturn("")
        `when`(whisperClient.transcribe(any(), any())).thenReturn(raw)
        `when`(dictionaryManager.applyCorrections(raw)).thenReturn(raw)
        `when`(dictionaryManager.getSceneSystemPromptExtra()).thenReturn("")
        `when`(dictionaryManager.buildLlmVocabularyHint(any(), any())).thenReturn("[]")
        for (status in listOf(LlmClient.RefinementStatus.DISABLED,
            LlmClient.RefinementStatus.UNAVAILABLE, LlmClient.RefinementStatus.REJECTED)) {
            `when`(llmClient.refineDictation(raw, "", "[]"))
                .thenReturn(LlmClient.RefinementResult(raw, status))
            val result = pipeline.process(ByteArray(100))
            assertEquals(true, result.success)
            assertEquals(raw, result.text)
            assertEquals(raw, result.rawText)
            assertEquals(status, result.refinementStatus)
        }
    }

    @Test
    fun `STT only explicitly bypasses cleanup without claiming applied refinement`() = runBlocking {
        val raw = "啊，我我還不確定。\n\n先不要部署。"
        `when`(dictionaryManager.buildWhisperPrompt()).thenReturn("")
        `when`(whisperClient.transcribe(any(), any())).thenReturn(raw)
        val result = pipeline.transcribeOnly(ByteArray(100))
        assertEquals(raw, result.text)
        assertEquals(raw, result.rawText)
        assertEquals(null, result.refinementStatus)
        verifyNoInteractions(llmClient)
        Unit
    }
}
