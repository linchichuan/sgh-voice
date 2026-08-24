package com.shingihou.sghvoice.processing

import com.shingihou.sghvoice.api.LlmClient
import com.shingihou.sghvoice.api.WhisperClient
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Before
import org.junit.Test
import org.mockito.Mock
import org.mockito.Mockito.`when`
import org.mockito.MockitoAnnotations
import org.mockito.kotlin.any
import org.mockito.kotlin.times
import org.mockito.kotlin.verify

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

    @Before
    fun setup() {
        MockitoAnnotations.openMocks(this)
        openCCConverter = OpenCCConverter() // 使用真實物件測試轉換邏輯
        pipeline = TranscriptionPipeline(whisperClient, llmClient, dictionaryManager, openCCConverter)
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
        
        // 3. 模擬 LLM 潤稿：加上標點、去填充詞
        `when`(llmClient.postProcess("我的公司是新義豊，在fukuoka。", "")).thenReturn("我的公司是新義豊，在 Fukuoka。")

        // 執行管線
        val result = pipeline.process(rawWav)

        // 4. 驗證結果 (OpenCC 會將 "Fukuoka" 保持原樣，並確保中文部分正確)
        assertEquals("我的公司是新義豊，在 Fukuoka。", result.text)
        assertEquals(true, result.success)
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

            val result = pipeline.process(
                rawWav,
                VoiceTask.Translation(request)
            )

            assertEquals(true, result.success)
            assertEquals("請確認明天的時間", result.translations[0].text)
            assertEquals("明日の時間をご確認ください", result.translations[1].text)
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
}
