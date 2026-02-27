package com.shingihou.sghvoice.ui

import android.Manifest
import android.content.pm.PackageManager
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.ui.Modifier
import androidx.core.content.ContextCompat
import com.shingihou.sghvoice.api.ApiConfig
import com.shingihou.sghvoice.ui.theme.SGHVoiceTheme

/**
 * 主畫面 Activity
 * 提供 API 金鑰設定、權限授予、輸入法啟用等初始設定功能
 */
class MainActivity : ComponentActivity() {

    private lateinit var apiConfig: ApiConfig

    // 錄音權限請求
    private val requestPermissionLauncher =
        registerForActivityResult(ActivityResultContracts.RequestPermission()) { isGranted ->
            if (!isGranted) {
                // 權限被拒絕時的處理（使用者仍可手動至設定開啟）
            }
        }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        apiConfig = ApiConfig(this)

        // 請求錄音權限
        requestMicrophonePermission()

        setContent {
            SGHVoiceTheme {
                Surface(
                    modifier = Modifier.fillMaxSize(),
                    color = MaterialTheme.colorScheme.background
                ) {
                    SetupScreen(apiConfig = apiConfig)
                }
            }
        }
    }

    /** 請求麥克風權限（若尚未授予） */
    private fun requestMicrophonePermission() {
        if (ContextCompat.checkSelfPermission(
                this,
                Manifest.permission.RECORD_AUDIO
            ) != PackageManager.PERMISSION_GRANTED
        ) {
            requestPermissionLauncher.launch(Manifest.permission.RECORD_AUDIO)
        }
    }
}
