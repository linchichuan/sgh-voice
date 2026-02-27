package com.shingihou.sghvoice.ui

import android.content.Intent
import android.provider.Settings
import android.view.inputmethod.InputMethodManager
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.input.VisualTransformation
import androidx.compose.ui.unit.dp
import com.shingihou.sghvoice.api.ApiConfig
import com.shingihou.sghvoice.processing.DictionaryManager

/**
 * 設定畫面
 * 包含三個分頁：基本設定、個人詞庫、使用說明
 */
@Composable
fun SetupScreen(apiConfig: ApiConfig) {
    val context = LocalContext.current
    val dictionaryManager = remember { DictionaryManager(context) }
    
    var selectedTab by remember { mutableIntStateOf(0) }
    val tabs = listOf("基本設定", "個人詞庫", "使用說明")

    Column(modifier = Modifier.fillMaxSize()) {
        TabRow(selectedTabIndex = selectedTab) {
            tabs.forEachIndexed { index, title ->
                Tab(
                    selected = selectedTab == index,
                    onClick = { selectedTab = index },
                    text = { Text(title) }
                )
            }
        }

        Box(modifier = Modifier.fillMaxSize().padding(16.dp)) {
            when (selectedTab) {
                0 -> BasicSettingsTab(apiConfig)
                1 -> DictionaryTab(dictionaryManager)
                2 -> UsageTab()
            }
        }
    }
}

@Composable
private fun BasicSettingsTab(apiConfig: ApiConfig) {
    val context = LocalContext.current
    val scrollState = rememberScrollState()
    
    var openAiKey by remember { mutableStateOf(apiConfig.openAiApiKey) }
    var anthropicKey by remember { mutableStateOf(apiConfig.anthropicApiKey) }
    var showOpenAiKey by remember { mutableStateOf(false) }
    var showAnthropicKey by remember { mutableStateOf(false) }
    var saveMessage by remember { mutableStateOf("") }

    Column(
        modifier = Modifier.fillMaxSize().verticalScroll(scrollState),
        verticalArrangement = Arrangement.spacedBy(16.dp)
    ) {
        Text("SGH Voice 基本設定", style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold)

        // === 步驟一：API 金鑰 ===
        StepCard(stepNumber = 1, title = "設定 API 金鑰") {
            OutlinedTextField(
                value = openAiKey,
                onValueChange = { openAiKey = it },
                label = { Text("OpenAI API 金鑰") },
                modifier = Modifier.fillMaxWidth(),
                visualTransformation = if (showOpenAiKey) VisualTransformation.None else PasswordVisualTransformation(),
                trailingIcon = {
                    TextButton(onClick = { showOpenAiKey = !showOpenAiKey }) {
                        Text(if (showOpenAiKey) "隱藏" else "顯示")
                    }
                }
            )
            Spacer(modifier = Modifier.height(8.dp))
            OutlinedTextField(
                value = anthropicKey,
                onValueChange = { anthropicKey = it },
                label = { Text("Anthropic API 金鑰") },
                modifier = Modifier.fillMaxWidth(),
                visualTransformation = if (showAnthropicKey) VisualTransformation.None else PasswordVisualTransformation(),
                trailingIcon = {
                    TextButton(onClick = { showAnthropicKey = !showAnthropicKey }) {
                        Text(if (showAnthropicKey) "隱藏" else "顯示")
                    }
                }
            )
            Spacer(modifier = Modifier.height(12.dp))
            Button(
                onClick = {
                    apiConfig.openAiApiKey = openAiKey.trim()
                    apiConfig.anthropicApiKey = anthropicKey.trim()
                    saveMessage = "金鑰已儲存"
                },
                modifier = Modifier.fillMaxWidth()
            ) { Text("儲存金鑰") }
            if (saveMessage.isNotBlank()) {
                Text(saveMessage, color = MaterialTheme.colorScheme.primary, style = MaterialTheme.typography.bodySmall)
            }
        }

        // === 步驟二：啟用輸入法 ===
        StepCard(stepNumber = 2, title = "啟用輸入法") {
            Text("請在系統設定中啟用 SGH Voice，並手動切換至該輸入法。", style = MaterialTheme.typography.bodyMedium)
            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedButton(onClick = {
                    context.startActivity(Intent(Settings.ACTION_INPUT_METHOD_SETTINGS))
                }, modifier = Modifier.weight(1f)) { Text("啟用設定") }
                OutlinedButton(onClick = {
                    val imm = context.getSystemService(InputMethodManager::class.java)
                    imm?.showInputMethodPicker()
                }, modifier = Modifier.weight(1f)) { Text("切換輸入法") }
            }
        }
    }
}

@OptIn(ExperimentalLayoutApi::class, ExperimentalMaterial3Api::class)
@Composable
private fun DictionaryTab(dictionaryManager: DictionaryManager) {
    val scrollState = rememberScrollState()
    var newWord by remember { mutableStateOf("") }
    var customWords by remember { mutableStateOf(dictionaryManager.getCustomWords()) }
    
    var wrongText by remember { mutableStateOf("") }
    var correctText by remember { mutableStateOf("") }
    var corrections by remember { mutableStateOf(dictionaryManager.getCorrections()) }

    Column(
        modifier = Modifier.fillMaxSize().verticalScroll(scrollState),
        verticalArrangement = Arrangement.spacedBy(16.dp)
    ) {
        Text("個人詞庫管理", style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold)

        // 自訂詞彙卡片
        Card(modifier = Modifier.fillMaxWidth()) {
            Column(modifier = Modifier.padding(16.dp)) {
                Text("自訂詞彙 (提升辨識率)", fontWeight = FontWeight.Bold, style = MaterialTheme.typography.titleMedium)
                Spacer(modifier = Modifier.height(8.dp))
                Row(verticalAlignment = Alignment.CenterVertically) {
                    OutlinedTextField(
                        value = newWord,
                        onValueChange = { newWord = it },
                        label = { Text("新增專有名詞") },
                        modifier = Modifier.weight(1f),
                        singleLine = true
                    )
                    IconButton(onClick = {
                        if (newWord.isNotBlank()) {
                            dictionaryManager.addCustomWord(newWord)
                            customWords = dictionaryManager.getCustomWords()
                            newWord = ""
                        }
                    }) { Icon(Icons.Default.Add, contentDescription = "Add") }
                }
                
                Spacer(modifier = Modifier.height(8.dp))
                // 顯示已加入的詞彙
                FlowRow(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    customWords.forEach { word ->
                        InputChip(
                            selected = false,
                            onClick = { 
                                dictionaryManager.removeCustomWord(word)
                                customWords = dictionaryManager.getCustomWords()
                            },
                            label = { Text(word) },
                            trailingIcon = { Icon(Icons.Default.Delete, null, modifier = Modifier.size(16.dp)) }
                        )
                    }
                }
            }
        }

        // 錯誤修正卡片
        Card(modifier = Modifier.fillMaxWidth()) {
            Column(modifier = Modifier.padding(16.dp)) {
                Text("錯誤修正規則", fontWeight = FontWeight.Bold, style = MaterialTheme.typography.titleMedium)
                Spacer(modifier = Modifier.height(8.dp))
                Row(verticalAlignment = Alignment.CenterVertically) {
                    OutlinedTextField(
                        value = wrongText,
                        onValueChange = { wrongText = it },
                        label = { Text("原字") },
                        modifier = Modifier.weight(1f),
                        singleLine = true
                    )
                    Text(" → ", modifier = Modifier.padding(horizontal = 4.dp))
                    OutlinedTextField(
                        value = correctText,
                        onValueChange = { correctText = it },
                        label = { Text("修正") },
                        modifier = Modifier.weight(1f),
                        singleLine = true
                    )
                    IconButton(onClick = {
                        if (wrongText.isNotBlank() && correctText.isNotBlank()) {
                            dictionaryManager.addCorrection(wrongText, correctText)
                            corrections = dictionaryManager.getCorrections()
                            wrongText = ""; correctText = ""
                        }
                    }) { Icon(Icons.Default.Add, contentDescription = "Add") }
                }
                
                Spacer(modifier = Modifier.height(8.dp))
                corrections.forEach { (wrong, correct) ->
                    Row(
                        modifier = Modifier.fillMaxWidth().padding(vertical = 4.dp),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Text("$wrong → $correct", style = MaterialTheme.typography.bodyMedium)
                        IconButton(onClick = {
                            dictionaryManager.removeCorrection(wrong)
                            corrections = dictionaryManager.getCorrections()
                        }) { Icon(Icons.Default.Delete, null, modifier = Modifier.size(20.dp)) }
                    }
                }
            }
        }
    }
}

@Composable
private fun UsageTab() {
    val scrollState = rememberScrollState()
    Column(
        modifier = Modifier.fillMaxSize().verticalScroll(scrollState),
        verticalArrangement = Arrangement.spacedBy(16.dp)
    ) {
        Text("使用說明", style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold)
        Card(modifier = Modifier.fillMaxWidth()) {
            Column(modifier = Modifier.padding(16.dp)) {
                Text("1. 按住藍色麥克風說話，放開即停止並開始辨識。", style = MaterialTheme.typography.bodyMedium)
                Spacer(modifier = Modifier.height(8.dp))
                Text("2. 系統會自動處理中、日、英三語混合，並修正口語填充詞。", style = MaterialTheme.typography.bodyMedium)
                Spacer(modifier = Modifier.height(8.dp))
                Text("3. 所有的簡體字都會在最後一步自動轉為繁體中文（台灣慣用詞）。", style = MaterialTheme.typography.bodyMedium)
                Spacer(modifier = Modifier.height(8.dp))
                Text("4. 若有專有名詞辨識不準，請在「個人詞庫」中新增該詞彙。", style = MaterialTheme.typography.bodyMedium)
            }
        }
    }
}

@Composable
private fun StepCard(stepNumber: Int, title: String, content: @Composable () -> Unit) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        elevation = CardDefaults.cardElevation(defaultElevation = 2.dp)
    ) {
        Column(modifier = Modifier.padding(16.dp)) {
            Text(text = "步驟 $stepNumber: $title", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
            Spacer(modifier = Modifier.height(8.dp))
            content()
        }
    }
}
