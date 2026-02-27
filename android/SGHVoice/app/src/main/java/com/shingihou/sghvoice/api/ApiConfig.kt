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
        private const val KEY_WHISPER_MODEL = "whisper_model"
        private const val KEY_CLAUDE_MODEL = "claude_model"
        private const val KEY_LANGUAGE_PREF = "language_preference"
        private const val KEY_SETUP_COMPLETE = "setup_complete"

        // 預設模型
        const val DEFAULT_WHISPER_MODEL = "whisper-1"
        const val DEFAULT_CLAUDE_MODEL = "claude-haiku-4-5-20251001"
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

    /** OpenAI API 金鑰 */
    var openAiApiKey: String
        get() = prefs.getString(KEY_OPENAI_API_KEY, "") ?: ""
        set(value) = prefs.edit().putString(KEY_OPENAI_API_KEY, value).apply()

    /** Anthropic API 金鑰 */
    var anthropicApiKey: String
        get() = prefs.getString(KEY_ANTHROPIC_API_KEY, "") ?: ""
        set(value) = prefs.edit().putString(KEY_ANTHROPIC_API_KEY, value).apply()

    /** Whisper 模型名稱 */
    var whisperModel: String
        get() = prefs.getString(KEY_WHISPER_MODEL, DEFAULT_WHISPER_MODEL) ?: DEFAULT_WHISPER_MODEL
        set(value) = prefs.edit().putString(KEY_WHISPER_MODEL, value).apply()

    /** Claude 模型名稱 */
    var claudeModel: String
        get() = prefs.getString(KEY_CLAUDE_MODEL, DEFAULT_CLAUDE_MODEL) ?: DEFAULT_CLAUDE_MODEL
        set(value) = prefs.edit().putString(KEY_CLAUDE_MODEL, value).apply()

    /** 偏好語言：auto / zh / ja / en */
    var languagePreference: String
        get() = prefs.getString(KEY_LANGUAGE_PREF, "auto") ?: "auto"
        set(value) = prefs.edit().putString(KEY_LANGUAGE_PREF, value).apply()

    /** 是否已完成初始設定 */
    var isSetupComplete: Boolean
        get() = prefs.getBoolean(KEY_SETUP_COMPLETE, false)
        set(value) = prefs.edit().putBoolean(KEY_SETUP_COMPLETE, value).apply()

    /** 檢查 API 金鑰是否已設定 */
    fun hasApiKeys(): Boolean {
        return openAiApiKey.isNotBlank() && anthropicApiKey.isNotBlank()
    }

    /** 清除所有設定 */
    fun clearAll() {
        prefs.edit().clear().apply()
    }
}
