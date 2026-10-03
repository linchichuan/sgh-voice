package com.shingihou.sghvoice.processing

/**
 * 使用者可控制的語音辨識語言。
 *
 * [apiCode] 使用 OpenAI／Groq transcription endpoint 接受的 ISO-639-1
 * 代碼；舊模型自動偵測時不送 singular language，新模型改用 transcriptionLanguages。
 */
enum class RecognitionLanguage(
    val preferenceValue: String,
    val apiCode: String?
) {
    AUTO("auto", null),
    TRADITIONAL_CHINESE("zh", "zh"),
    JAPANESE("ja", "ja"),
    ENGLISH("en", "en"),
    KOREAN("ko", "ko");

    /** File transcription supports multiple expected input languages instead of singular language. */
    val transcriptionLanguages: List<String>
        get() = apiCode?.let(::listOf) ?: listOf("zh", "ja", "en")

    companion object {
        fun fromPreference(value: String?): RecognitionLanguage =
            entries.firstOrNull {
                it.preferenceValue == value?.trim()?.lowercase()
            } ?: AUTO
    }
}
