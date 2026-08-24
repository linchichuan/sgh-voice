package com.shingihou.sghvoice.processing

/**
 * 第一版翻譯模式支援的固定目標語言。
 *
 * 使用 BCP-47 tag 作為跨 UI、儲存與 API 回應的穩定識別值。
 */
enum class TranslationLanguage(val tag: String) {
    TRADITIONAL_CHINESE("zh-Hant"),
    JAPANESE("ja"),
    ENGLISH("en"),
    KOREAN("ko");

    companion object {
        fun fromTag(tag: String): TranslationLanguage? =
            entries.firstOrNull { it.tag == tag }
    }
}

/**
 * 一次翻譯請求。輸入順序會保留，重複語言會先去除，最終必須有 1–4 種。
 */
class TranslationRequest private constructor(
    val targets: List<TranslationLanguage>
) {
    companion object {
        const val MAX_TARGETS = 4

        fun create(targets: Iterable<TranslationLanguage>): TranslationRequest {
            val normalized = targets.distinct()
            require(normalized.isNotEmpty()) { "At least one translation target is required." }
            require(normalized.size <= MAX_TARGETS) {
                "At most $MAX_TARGETS translation targets are allowed."
            }
            return TranslationRequest(normalized)
        }

        fun fromTags(tags: Iterable<String>): TranslationRequest =
            create(tags.mapNotNull(TranslationLanguage::fromTag))
    }

    override fun equals(other: Any?): Boolean =
        other is TranslationRequest && targets == other.targets

    override fun hashCode(): Int = targets.hashCode()

    override fun toString(): String = "TranslationRequest(targets=$targets)"
}

data class TranslationOutput(
    val language: TranslationLanguage,
    val text: String
)

sealed interface VoiceTask {
    data object Dictation : VoiceTask

    data class Translation(
        val request: TranslationRequest
    ) : VoiceTask
}
