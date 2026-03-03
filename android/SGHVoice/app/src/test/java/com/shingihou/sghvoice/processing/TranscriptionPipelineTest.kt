package com.shingihou.sghvoice.processing

import com.shingihou.sghvoice.api.ClaudeClient
import com.shingihou.sghvoice.api.WhisperClient
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Before
import org.junit.Test
import org.mockito.Mock
import org.mockito.Mockito.`when`
import org.mockito.MockitoAnnotations
import org.mockito.kotlin.any
import org.mockito.kotlin.whenever

/**
 * 處理管線單元測試
 */
class TranscriptionPipelineTest {

    @Mock
    private lateinit var whisperClient: WhisperClient
    @Mock
    private lateinit var claudeClient: ClaudeClient
    @Mock
    private lateinit var dictionaryManager: DictionaryManager
    
    private lateinit var openCCConverter: OpenCCConverter
    private lateinit var pipeline: TranscriptionPipeline

    @Before
    fun setup() {
        MockitoAnnotations.openMocks(this)
        openCCConverter = OpenCCConverter() // 使用真實物件測試轉換邏輯
        pipeline = TranscriptionPipeline(whisperClient, claudeClient, dictionaryManager, openCCConverter)
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
        
        // 3. 模擬 Claude 潤稿：加上標點、去填充詞
        `when`(claudeClient.postProcess("我的公司是新義豊，在fukuoka。")).thenReturn("我的公司是新義豊，在 Fukuoka。")

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
}
