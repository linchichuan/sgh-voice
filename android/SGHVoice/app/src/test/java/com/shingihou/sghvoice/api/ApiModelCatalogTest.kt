package com.shingihou.sghvoice.api

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class ApiModelCatalogTest {
    @Test
    fun `upgrade preserves explicit model choices and legacy implicit defaults`() {
        assertEquals("gpt-transcribe", ApiModelCatalog.openAiSttModelForInstallation(null, false))
        assertEquals("whisper-1", ApiModelCatalog.openAiSttModelForInstallation(null, true))
        for (model in listOf("whisper-1", "gpt-4o-transcribe", "gpt-transcribe")) {
            assertEquals(model, ApiModelCatalog.openAiSttModelForInstallation(model, true))
        }
    }
    @Test
    fun `new installations offer the current file transcription model`() {
        assertTrue("gpt-transcribe" in ApiModelCatalog.openAiSttModels)
        assertEquals("gpt-transcribe", ApiModelCatalog.DEFAULT_OPENAI_STT_MODEL)
    }

    @Test
    fun `every selectable model id is nonblank and unique`() {
        val all = listOf(
            ApiModelCatalog.openAiSttModels,
            ApiModelCatalog.groqSttModels,
            ApiModelCatalog.claudeModels,
            ApiModelCatalog.openAiLlmModels,
            ApiModelCatalog.groqLlmModels
        ).flatten()

        assertTrue(all.all(String::isNotBlank))
        assertEquals(all.size, all.distinct().size)
        assertEquals(all.toSet(), ApiModelCatalog.selectableModels)
    }

    @Test
    fun `every default is present in its provider catalog`() {
        assertTrue(
            ApiModelCatalog.DEFAULT_OPENAI_STT_MODEL in ApiModelCatalog.openAiSttModels
        )
        assertTrue(
            ApiModelCatalog.DEFAULT_GROQ_STT_MODEL in ApiModelCatalog.groqSttModels
        )
        assertTrue(
            ApiModelCatalog.DEFAULT_CLAUDE_MODEL in ApiModelCatalog.claudeModels
        )
        assertTrue(
            ApiModelCatalog.DEFAULT_OPENAI_LLM_MODEL in ApiModelCatalog.openAiLlmModels
        )
        assertTrue(
            ApiModelCatalog.DEFAULT_GROQ_LLM_MODEL in ApiModelCatalog.groqLlmModels
        )
    }
}
