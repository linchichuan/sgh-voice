package com.shingihou.sghvoice.api

import android.content.Context
import android.content.SharedPreferences
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey

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

    /** 偏好語言：auto / zh / ja / en */
    var languagePreference: String
        get() = prefs.getString(KEY_LANGUAGE_PREF, "auto") ?: "auto"
        set(value) = prefs.edit().putString(KEY_LANGUAGE_PREF, value).apply()

    /** 是否已完成初始設定 */
    var isSetupComplete: Boolean
        get() = prefs.getBoolean(KEY_SETUP_COMPLETE, false)
        set(value) = prefs.edit().putBoolean(KEY_SETUP_COMPLETE, value).apply()

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
