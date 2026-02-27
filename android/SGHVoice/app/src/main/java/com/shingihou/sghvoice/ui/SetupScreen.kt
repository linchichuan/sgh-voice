package com.shingihou.sghvoice.ui

import android.content.Intent
import android.provider.Settings
import android.view.inputmethod.InputMethodManager
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.input.VisualTransformation
import androidx.compose.ui.unit.dp
import com.shingihou.sghvoice.api.ApiConfig

/**
 * 設定畫面
 * 包含三個步驟：
 * 1. API 金鑰輸入（OpenAI + Anthropic）
 * 2. 權限授予（麥克風）
 * 3. 啟用輸入法
 */
@Composable
fun SetupScreen(apiConfig: ApiConfig) {
    val context = LocalContext.current
    val scrollState = rememberScrollState()

    var openAiKey by remember { mutableStateOf(apiConfig.openAiApiKey) }
    var anthropicKey by remember { mutableStateOf(apiConfig.anthropicApiKey) }
    var showOpenAiKey by remember { mutableStateOf(false) }
    var showAnthropicKey by remember { mutableStateOf(false) }
    var saveMessage by remember { mutableStateOf("") }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(16.dp)
            .verticalScroll(scrollState),
        verticalArrangement = Arrangement.spacedBy(16.dp)
    ) {
        // 標題
        Text(
            text = "SGH Voice 設定",
            style = MaterialTheme.typography.headlineMedium,
            fontWeight = FontWeight.Bold
        )

        Text(
            text = "AI 語音輸入法 — 新義豊株式会社",
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant
        )

        Spacer(modifier = Modifier.height(8.dp))

        // === 步驟一：API 金鑰 ===
        StepCard(
            stepNumber = 1,
            title = "設定 API 金鑰"
        ) {
            // OpenAI API Key
            OutlinedTextField(
                value = openAiKey,
                onValueChange = { openAiKey = it },
                label = { Text("OpenAI API 金鑰") },
                placeholder = { Text("sk-...") },
                modifier = Modifier.fillMaxWidth(),
                singleLine = true,
                visualTransformation = if (showOpenAiKey) {
                    VisualTransformation.None
                } else {
                    PasswordVisualTransformation()
                },
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password),
                trailingIcon = {
                    OutlinedButton(onClick = { showOpenAiKey = !showOpenAiKey }) {
                        Text(if (showOpenAiKey) "隱藏" else "顯示")
                    }
                }
            )

            Spacer(modifier = Modifier.height(8.dp))

            // Anthropic API Key
            OutlinedTextField(
                value = anthropicKey,
                onValueChange = { anthropicKey = it },
                label = { Text("Anthropic API 金鑰") },
                placeholder = { Text("sk-ant-...") },
                modifier = Modifier.fillMaxWidth(),
                singleLine = true,
                visualTransformation = if (showAnthropicKey) {
                    VisualTransformation.None
                } else {
                    PasswordVisualTransformation()
                },
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password),
                trailingIcon = {
                    OutlinedButton(onClick = { showAnthropicKey = !showAnthropicKey }) {
                        Text(if (showAnthropicKey) "隱藏" else "顯示")
                    }
                }
            )

            Spacer(modifier = Modifier.height(12.dp))

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                Button(
                    onClick = {
                        apiConfig.openAiApiKey = openAiKey.trim()
                        apiConfig.anthropicApiKey = anthropicKey.trim()
                        saveMessage = if (apiConfig.hasApiKeys()) {
                            apiConfig.isSetupComplete = true
                            "金鑰已安全儲存"
                        } else {
                            "請輸入兩組 API 金鑰"
                        }
                    },
                    modifier = Modifier.weight(1f)
                ) {
                    Text("儲存金鑰")
                }
            }

            if (saveMessage.isNotBlank()) {
                Text(
                    text = saveMessage,
                    style = MaterialTheme.typography.bodySmall,
                    color = if (apiConfig.hasApiKeys()) {
                        MaterialTheme.colorScheme.primary
                    } else {
                        MaterialTheme.colorScheme.error
                    }
                )
            }
        }

        // === 步驟二：權限設定 ===
        StepCard(
            stepNumber = 2,
            title = "授予麥克風權限"
        ) {
            Text(
                text = "語音輸入需要麥克風權限。首次使用時系統會自動詢問。",
                style = MaterialTheme.typography.bodyMedium
            )
        }

        // === 步驟三：啟用輸入法 ===
        StepCard(
            stepNumber = 3,
            title = "啟用 SGH Voice 輸入法"
        ) {
            Text(
                text = "請在系統設定中啟用 SGH Voice 輸入法，並將其設為目前使用的輸入法。",
                style = MaterialTheme.typography.bodyMedium
            )

            Spacer(modifier = Modifier.height(8.dp))

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                OutlinedButton(
                    onClick = {
                        // 開啟系統輸入法設定頁面
                        val intent = Intent(Settings.ACTION_INPUT_METHOD_SETTINGS)
                        intent.flags = Intent.FLAG_ACTIVITY_NEW_TASK
                        context.startActivity(intent)
                    },
                    modifier = Modifier.weight(1f)
                ) {
                    Text("啟用輸入法")
                }

                OutlinedButton(
                    onClick = {
                        // 開啟輸入法選擇器
                        val imm = context.getSystemService(InputMethodManager::class.java)
                        imm?.showInputMethodPicker()
                    },
                    modifier = Modifier.weight(1f)
                ) {
                    Text("切換輸入法")
                }
            }
        }

        // === 使用說明 ===
        StepCard(
            stepNumber = 0,
            title = "使用說明"
        ) {
            Text(
                text = """在任何文字輸入框切換至 SGH Voice 輸入法後：

1. 按住麥克風按鈕開始說話
2. 放開按鈕停止錄音
3. 系統自動辨識並輸入文字

支援中文、日語、英語混合語音輸入，中文部分自動轉換為繁體中文。""",
                style = MaterialTheme.typography.bodyMedium
            )
        }

        Spacer(modifier = Modifier.height(32.dp))
    }
}

/**
 * 步驟卡片元件
 *
 * @param stepNumber 步驟編號（0 表示非步驟卡片，不顯示編號）
 * @param title 卡片標題
 * @param content 卡片內容
 */
@Composable
private fun StepCard(
    stepNumber: Int,
    title: String,
    content: @Composable () -> Unit
) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        elevation = CardDefaults.cardElevation(defaultElevation = 2.dp)
    ) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            Text(
                text = if (stepNumber > 0) "步驟 $stepNumber: $title" else title,
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.SemiBold
            )
            content()
        }
    }
}
