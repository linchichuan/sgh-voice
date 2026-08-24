package com.shingihou.sghvoice.api

/**
 * Model IDs exposed by the Android settings screen.
 *
 * Keep provider and model separate: the same API key can often access several
 * models with different speed, accuracy, and cost characteristics.
 */
object ApiModelCatalog {
    const val OPENAI_STT_WHISPER = "whisper-1"
    const val OPENAI_STT_GPT_4O_MINI = "gpt-4o-mini-transcribe"
    const val OPENAI_STT_GPT_4O = "gpt-4o-transcribe"

    const val GROQ_STT_TURBO = "whisper-large-v3-turbo"
    const val GROQ_STT_LARGE = "whisper-large-v3"

    const val CLAUDE_HAIKU_4_5 = "claude-haiku-4-5-20251001"
    const val CLAUDE_SONNET_5 = "claude-sonnet-5"
    const val CLAUDE_OPUS_5 = "claude-opus-5"
    const val CLAUDE_OPUS_4_8 = "claude-opus-4-8"
    const val CLAUDE_FABLE_5 = "claude-fable-5"

    const val OPENAI_LLM_GPT_4O_MINI = "gpt-4o-mini"
    const val OPENAI_LLM_GPT_4O = "gpt-4o"

    const val GROQ_LLM_GPT_OSS_20B = "openai/gpt-oss-20b"
    const val GROQ_LLM_GPT_OSS_120B = "openai/gpt-oss-120b"

    const val DEFAULT_OPENAI_STT_MODEL = OPENAI_STT_WHISPER
    const val DEFAULT_GROQ_STT_MODEL = GROQ_STT_TURBO
    const val DEFAULT_CLAUDE_MODEL = CLAUDE_HAIKU_4_5
    const val DEFAULT_OPENAI_LLM_MODEL = OPENAI_LLM_GPT_4O
    const val DEFAULT_GROQ_LLM_MODEL = GROQ_LLM_GPT_OSS_120B

    val openAiSttModels = listOf(
        OPENAI_STT_GPT_4O_MINI,
        OPENAI_STT_GPT_4O,
        OPENAI_STT_WHISPER
    )

    val groqSttModels = listOf(
        GROQ_STT_TURBO,
        GROQ_STT_LARGE
    )

    val claudeModels = listOf(
        CLAUDE_HAIKU_4_5,
        CLAUDE_SONNET_5,
        CLAUDE_OPUS_5,
        CLAUDE_OPUS_4_8,
        CLAUDE_FABLE_5
    )

    val openAiLlmModels = listOf(
        OPENAI_LLM_GPT_4O_MINI,
        OPENAI_LLM_GPT_4O
    )

    val groqLlmModels = listOf(
        GROQ_LLM_GPT_OSS_20B,
        GROQ_LLM_GPT_OSS_120B
    )

    val selectableModels: Set<String> =
        (
            openAiSttModels +
                groqSttModels +
                claudeModels +
                openAiLlmModels +
                groqLlmModels
            ).toSet()
}
