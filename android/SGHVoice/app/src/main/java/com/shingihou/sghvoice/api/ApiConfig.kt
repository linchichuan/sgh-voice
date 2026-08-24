package com.shingihou.sghvoice.api

import android.content.Context
import android.content.SharedPreferences
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey
import com.shingihou.sghvoice.processing.RecognitionLanguage
import com.shingihou.sghvoice.processing.TranslationLanguage
import com.shingihou.sghvoice.processing.TranslationRequest
import com.shingihou.sghvoice.privacy.CloudProcessingConsent

/**
 * API 金鑰管理
 * 使用 EncryptedSharedPreferences 安全儲存 API 金鑰與設定
 */
class ApiConfig(context: Context) {

    companion object {
        private const val PREF_NAME = "sgh_voice_secure_prefs"
        private const val KEY_OPENAI_API_KEY = "openai_api_key"
        private const val KEY_ANTHROPIC_API_KEY = "anthropic_api_key"
        private const val KEY_GROQ_API_KEY = "groq_api_key"
        private const val KEY_ELEVENLABS_API_KEY = "elevenlabs_api_key"
        private const val KEY_WHISPER_MODEL = "whisper_model"
        private const val KEY_GROQ_STT_MODEL = "groq_stt_model"
        private const val KEY_CLAUDE_MODEL = "claude_model"
        private const val KEY_OPENAI_LLM_MODEL = "openai_llm_model"
        private const val KEY_GROQ_LLM_MODEL = "groq_llm_model"
        private const val KEY_LANGUAGE_PREF = "language_preference"
        private const val KEY_SETUP_COMPLETE = "setup_complete"
        private const val KEY_OUTPUT_STYLE = "output_style"
        private const val KEY_STT_ENGINE = "stt_engine"
        private const val KEY_LLM_ENGINE = "llm_engine"
        private const val KEY_TRANSLATION_TARGETS = "translation_targets"
        private const val KEY_CLOUD_PROCESSING_CONSENT_VERSION =
            "cloud_processing_consent_version"

        // 預設模型
        const val DEFAULT_WHISPER_MODEL = ApiModelCatalog.DEFAULT_OPENAI_STT_MODEL
        const val DEFAULT_GROQ_STT_MODEL = ApiModelCatalog.DEFAULT_GROQ_STT_MODEL
        const val DEFAULT_CLAUDE_MODEL = ApiModelCatalog.DEFAULT_CLAUDE_MODEL
        const val DEFAULT_OPENAI_LLM_MODEL = ApiModelCatalog.DEFAULT_OPENAI_LLM_MODEL
        const val DEFAULT_GROQ_LLM_MODEL = ApiModelCatalog.DEFAULT_GROQ_LLM_MODEL
    }

    private val masterKey = MasterKey.Builder(context)
        .setKeyScheme(MasterKey.KeyScheme.AES256_GCM)
        .build()

    private val prefs: SharedPreferences = EncryptedSharedPreferences.create(
        context,
        PREF_NAME,
        masterKey,
        EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
        EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM
    )

    /** 語音辨識引擎 (openai / groq) */
    var sttEngine: String
        get() = prefs.getString(KEY_STT_ENGINE, "openai") ?: "openai"
        set(value) = prefs.edit().putString(KEY_STT_ENGINE, value).apply()

    /** 後處理引擎 (claude / openai / groq / none) */
    var llmEngine: String
        get() = prefs.getString(KEY_LLM_ENGINE, "claude") ?: "claude"
        set(value) = prefs.edit().putString(KEY_LLM_ENGINE, value).apply()

    /** OpenAI API 金鑰 */
    var openAiApiKey: String
        get() = prefs.getString(KEY_OPENAI_API_KEY, "") ?: ""
        set(value) = prefs.edit().putString(KEY_OPENAI_API_KEY, value).apply()

    /** Anthropic API 金鑰 */
    var anthropicApiKey: String
        get() = prefs.getString(KEY_ANTHROPIC_API_KEY, "") ?: ""
        set(value) = prefs.edit().putString(KEY_ANTHROPIC_API_KEY, value).apply()

    /** Groq API 金鑰 */
    var groqApiKey: String
        get() = prefs.getString(KEY_GROQ_API_KEY, "") ?: ""
        set(value) = prefs.edit().putString(KEY_GROQ_API_KEY, value).apply()

    /** ElevenLabs API 金鑰 */
    var elevenlabsApiKey: String
        get() = prefs.getString(KEY_ELEVENLABS_API_KEY, "") ?: ""
        set(value) = prefs.edit().putString(KEY_ELEVENLABS_API_KEY, value).apply()

    /** Whisper 模型名稱 */
    var whisperModel: String
        get() = prefs.getString(KEY_WHISPER_MODEL, DEFAULT_WHISPER_MODEL) ?: DEFAULT_WHISPER_MODEL
        set(value) = prefs.edit().putString(KEY_WHISPER_MODEL, value).apply()

    /** Groq 語音辨識模型名稱 */
    var groqSttModel: String
        get() = prefs.getString(KEY_GROQ_STT_MODEL, DEFAULT_GROQ_STT_MODEL)
            ?: DEFAULT_GROQ_STT_MODEL
        set(value) = prefs.edit().putString(KEY_GROQ_STT_MODEL, value).apply()

    /** Claude 模型名稱 */
    var claudeModel: String
        get() = prefs.getString(KEY_CLAUDE_MODEL, DEFAULT_CLAUDE_MODEL) ?: DEFAULT_CLAUDE_MODEL
        set(value) = prefs.edit().putString(KEY_CLAUDE_MODEL, value).apply()

    /** OpenAI 後處理模型名稱 */
    var openAiLlmModel: String
        get() = prefs.getString(KEY_OPENAI_LLM_MODEL, DEFAULT_OPENAI_LLM_MODEL)
            ?: DEFAULT_OPENAI_LLM_MODEL
        set(value) = prefs.edit().putString(KEY_OPENAI_LLM_MODEL, value).apply()

    /** Groq 後處理模型名稱 */
    var groqLlmModel: String
        get() = prefs.getString(KEY_GROQ_LLM_MODEL, DEFAULT_GROQ_LLM_MODEL)
            ?: DEFAULT_GROQ_LLM_MODEL
        set(value) = prefs.edit().putString(KEY_GROQ_LLM_MODEL, value).apply()

    /** 輸出風格 (normal / line / email) */
    var outputStyle: String
        get() = prefs.getString(KEY_OUTPUT_STYLE, "normal") ?: "normal"
        set(value) = prefs.edit().putString(KEY_OUTPUT_STYLE, value).apply()

    /** 語音辨識語言；auto 會保留中／日／英／韓混合輸入的自動偵測。 */
    var recognitionLanguage: RecognitionLanguage
        get() = RecognitionLanguage.fromPreference(
            prefs.getString(KEY_LANGUAGE_PREF, RecognitionLanguage.AUTO.preferenceValue)
        )
        set(value) = prefs.edit()
            .putString(KEY_LANGUAGE_PREF, value.preferenceValue)
            .apply()

    /**
     * 舊版設定欄位相容層。寫入時一律正規化，避免未知值直接送進 transcription API。
     */
    var languagePreference: String
        get() = recognitionLanguage.preferenceValue
        set(value) {
            recognitionLanguage = RecognitionLanguage.fromPreference(value)
        }

    /**
     * 長按翻譯的預設目標語言。保留使用者排序，遇到舊版或損壞資料時安全回復日文。
     */
    var translationTargets: List<TranslationLanguage>
        get() {
            val saved = prefs.getString(KEY_TRANSLATION_TARGETS, null)
                ?.split(",")
                ?.mapNotNull(TranslationLanguage::fromTag)
                .orEmpty()
            return try {
                TranslationRequest.create(saved).targets
            } catch (_: IllegalArgumentException) {
                listOf(TranslationLanguage.JAPANESE)
            }
        }
        set(value) {
            val normalized = TranslationRequest.create(value).targets
            prefs.edit()
                .putString(KEY_TRANSLATION_TARGETS, normalized.joinToString(",") { it.tag })
                .apply()
        }

    /** 是否已完成初始設定 */
    var isSetupComplete: Boolean
        get() = prefs.getBoolean(KEY_SETUP_COMPLETE, false)
        set(value) = prefs.edit().putBoolean(KEY_SETUP_COMPLETE, value).apply()

    /** Every cloud recording path must check this before accessing the microphone. */
    var hasCloudProcessingConsent: Boolean
        get() = CloudProcessingConsent.isAccepted(
            if (prefs.contains(KEY_CLOUD_PROCESSING_CONSENT_VERSION)) {
                prefs.getInt(KEY_CLOUD_PROCESSING_CONSENT_VERSION, 0)
            } else {
                null
            }
        )
        set(value) {
            if (value) {
                prefs.edit()
                    .putInt(
                        KEY_CLOUD_PROCESSING_CONSENT_VERSION,
                        CloudProcessingConsent.CURRENT_VERSION
                    )
                    .apply()
            } else {
                prefs.edit().remove(KEY_CLOUD_PROCESSING_CONSENT_VERSION).apply()
            }
        }

    /** 檢查 API 金鑰是否已設定 (支援 OpenAI, Anthropic 或 Groq) */
    fun hasApiKeys(): Boolean {
        val hasStt = openAiApiKey.isNotBlank() || groqApiKey.isNotBlank()
        val hasLlm = anthropicApiKey.isNotBlank() || openAiApiKey.isNotBlank() || groqApiKey.isNotBlank()
        return hasStt && hasLlm
    }

    /** 清除所有設定 */
    fun clearAll() {
        prefs.edit().clear().apply()
    }
}
