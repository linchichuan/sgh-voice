package com.shingihou.sghvoice.processing

/**
 * 使用者可控制的語音辨識語言。
 *
 * [apiCode] 使用 OpenAI／Groq transcription endpoint 接受的 ISO-639-1
 * 代碼；自動偵測時為 null，請求不送出 language 欄位，保留混合語言能力。
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

    companion object {
        fun fromPreference(value: String?): RecognitionLanguage =
            entries.firstOrNull {
                it.preferenceValue == value?.trim()?.lowercase()
            } ?: AUTO
    }
}
