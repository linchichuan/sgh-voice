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
import androidx.compose.ui.res.stringResource
import com.shingihou.sghvoice.R

/**
 * 設定畫面
 * 包含三個分頁：基本設定、個人詞庫、使用說明
 */
@Composable
fun SetupScreen(apiConfig: ApiConfig) {
    val context = LocalContext.current
    val dictionaryManager = remember { DictionaryManager(context) }
    
    var selectedTab by remember { mutableIntStateOf(0) }
    val tabs = listOf(
        stringResource(R.string.tab_basic_settings),
        stringResource(R.string.tab_dictionary),
        stringResource(R.string.tab_usage_guide)
    )

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
    var groqKey by remember { mutableStateOf(apiConfig.groqApiKey) }
    var elevenLabsKey by remember { mutableStateOf(apiConfig.elevenlabsApiKey) }
    
    var showOpenAiKey by remember { mutableStateOf(false) }
    var showAnthropicKey by remember { mutableStateOf(false) }
    var showGroqKey by remember { mutableStateOf(false) }
    var showElevenLabsKey by remember { mutableStateOf(false) }
    var saveMessage by remember { mutableStateOf("") }
    val msgSaved = stringResource(R.string.msg_keys_saved)
    var selectedStyle by remember { mutableStateOf(apiConfig.outputStyle) }
    var selectedSttEngine by remember { mutableStateOf(apiConfig.sttEngine) }
    var selectedLlmEngine by remember { mutableStateOf(apiConfig.llmEngine) }

    Column(
        modifier = Modifier.fillMaxSize().verticalScroll(scrollState),
        verticalArrangement = Arrangement.spacedBy(16.dp)
    ) {
        Text(stringResource(R.string.title_basic_settings), style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold)

        // === 步驟一：引擎選擇 ===
        StepCard(stepNumber = 1, title = "選擇服務引擎") {
            Text(stringResource(R.string.label_stt_engine), fontWeight = FontWeight.SemiBold)
            val sttEngines = listOf("openai" to stringResource(R.string.engine_openai), "groq" to stringResource(R.string.engine_groq))
            sttEngines.forEach { (id, name) ->
                Row(verticalAlignment = Alignment.CenterVertically) {
                    RadioButton(selected = selectedSttEngine == id, onClick = { selectedSttEngine = id })
                    Text(text = name)
                }
            }
            
            Spacer(modifier = Modifier.height(8.dp))
            Text(stringResource(R.string.label_llm_engine), fontWeight = FontWeight.SemiBold)
            val llmEngines = listOf(
                "claude" to stringResource(R.string.engine_claude),
                "openai" to "OpenAI (GPT-4o)",
                "groq" to "Groq (Llama 3)",
                "none" to stringResource(R.string.engine_none)
            )
            llmEngines.forEach { (id, name) ->
                Row(verticalAlignment = Alignment.CenterVertically) {
                    RadioButton(selected = selectedLlmEngine == id, onClick = { selectedLlmEngine = id })
                    Text(text = name)
                }
            }
        }

        // === 步驟二：API 金鑰 ===
        StepCard(stepNumber = 2, title = stringResource(R.string.step_api_keys)) {
            OutlinedTextField(
                value = openAiKey,
                onValueChange = { openAiKey = it },
                label = { Text(stringResource(R.string.openai_key_label)) },
                modifier = Modifier.fillMaxWidth(),
                visualTransformation = if (showOpenAiKey) VisualTransformation.None else PasswordVisualTransformation(),
                trailingIcon = {
                    TextButton(onClick = { showOpenAiKey = !showOpenAiKey }) {
                        Text(if (showOpenAiKey) stringResource(R.string.btn_hide) else stringResource(R.string.btn_show))
                    }
                }
            )
            Spacer(modifier = Modifier.height(8.dp))
            OutlinedTextField(
                value = anthropicKey,
                onValueChange = { anthropicKey = it },
                label = { Text(stringResource(R.string.anthropic_key_label)) },
                modifier = Modifier.fillMaxWidth(),
                visualTransformation = if (showAnthropicKey) VisualTransformation.None else PasswordVisualTransformation(),
                trailingIcon = {
                    TextButton(onClick = { showAnthropicKey = !showAnthropicKey }) {
                        Text(if (showAnthropicKey) stringResource(R.string.btn_hide) else stringResource(R.string.btn_show))
                    }
                }
            )
            Spacer(modifier = Modifier.height(8.dp))
            OutlinedTextField(
                value = groqKey,
                onValueChange = { groqKey = it },
                label = { Text(stringResource(R.string.groq_key_label)) },
                modifier = Modifier.fillMaxWidth(),
                visualTransformation = if (showGroqKey) VisualTransformation.None else PasswordVisualTransformation(),
                trailingIcon = {
                    TextButton(onClick = { showGroqKey = !showGroqKey }) {
                        Text(if (showGroqKey) stringResource(R.string.btn_hide) else stringResource(R.string.btn_show))
                    }
                }
            )
            Spacer(modifier = Modifier.height(8.dp))
            OutlinedTextField(
                value = elevenLabsKey,
                onValueChange = { elevenLabsKey = it },
                label = { Text(stringResource(R.string.elevenlabs_key_label)) },
                modifier = Modifier.fillMaxWidth(),
                visualTransformation = if (showElevenLabsKey) VisualTransformation.None else PasswordVisualTransformation(),
                trailingIcon = {
                    TextButton(onClick = { showElevenLabsKey = !showElevenLabsKey }) {
                        Text(if (showElevenLabsKey) stringResource(R.string.btn_hide) else stringResource(R.string.btn_show))
                    }
                }
            )
            Spacer(modifier = Modifier.height(16.dp))
            
            Text(stringResource(R.string.output_style_label), fontWeight = FontWeight.SemiBold)
            Spacer(modifier = Modifier.height(8.dp))
            
            val styles = listOf("normal" to stringResource(R.string.style_normal), "line" to stringResource(R.string.style_line), "email" to stringResource(R.string.style_email))
            styles.forEach { (styleId, styleName) ->
                Row(verticalAlignment = Alignment.CenterVertically) {
                    RadioButton(
                        selected = selectedStyle == styleId,
                        onClick = { selectedStyle = styleId }
                    )
                    Text(text = styleName)
                }
            }

            Spacer(modifier = Modifier.height(12.dp))
            Button(
                onClick = {
                    apiConfig.openAiApiKey = openAiKey.trim()
                    apiConfig.anthropicApiKey = anthropicKey.trim()
                    apiConfig.groqApiKey = groqKey.trim()
                    apiConfig.elevenlabsApiKey = elevenLabsKey.trim()
                    apiConfig.outputStyle = selectedStyle
                    apiConfig.sttEngine = selectedSttEngine
                    apiConfig.llmEngine = selectedLlmEngine
                    saveMessage = msgSaved
                },
                modifier = Modifier.fillMaxWidth()
            ) { Text(stringResource(R.string.btn_save_keys)) }
            if (saveMessage.isNotBlank()) {
                Text(saveMessage, color = MaterialTheme.colorScheme.primary, style = MaterialTheme.typography.bodySmall)
            }
        }

        // === 步驟三：啟用輸入法 ===
        StepCard(stepNumber = 3, title = stringResource(R.string.step_enable_ime)) {
            Text(stringResource(R.string.desc_enable_ime), style = MaterialTheme.typography.bodyMedium)
            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedButton(onClick = {
                    context.startActivity(Intent(Settings.ACTION_INPUT_METHOD_SETTINGS))
                }, modifier = Modifier.weight(1f)) { Text(stringResource(R.string.btn_enable_settings)) }
                OutlinedButton(onClick = {
                    val imm = context.getSystemService(InputMethodManager::class.java)
                    imm?.showInputMethodPicker()
                }, modifier = Modifier.weight(1f)) { Text(stringResource(R.string.btn_switch_ime)) }
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
        Text(stringResource(R.string.title_dictionary_manage), style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold)

        // 自訂詞彙卡片
        Card(modifier = Modifier.fillMaxWidth()) {
            Column(modifier = Modifier.padding(16.dp)) {
                Text(stringResource(R.string.title_custom_words), fontWeight = FontWeight.Bold, style = MaterialTheme.typography.titleMedium)
                Spacer(modifier = Modifier.height(8.dp))
                Row(verticalAlignment = Alignment.CenterVertically) {
                    OutlinedTextField(
                        value = newWord,
                        onValueChange = { newWord = it },
                        label = { Text(stringResource(R.string.label_add_proper_noun)) },
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
                Text(stringResource(R.string.title_corrections), fontWeight = FontWeight.Bold, style = MaterialTheme.typography.titleMedium)
                Spacer(modifier = Modifier.height(8.dp))
                Row(verticalAlignment = Alignment.CenterVertically) {
                    OutlinedTextField(
                        value = wrongText,
                        onValueChange = { wrongText = it },
                        label = { Text(stringResource(R.string.label_wrong_word)) },
                        modifier = Modifier.weight(1f),
                        singleLine = true
                    )
                    Text(" → ", modifier = Modifier.padding(horizontal = 4.dp))
                    OutlinedTextField(
                        value = correctText,
                        onValueChange = { correctText = it },
                        label = { Text(stringResource(R.string.label_correct_word)) },
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
        Text(stringResource(R.string.usage_title), style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold)
        Card(modifier = Modifier.fillMaxWidth()) {
            Column(modifier = Modifier.padding(16.dp)) {
                Text(stringResource(R.string.usage_step1), style = MaterialTheme.typography.bodyMedium)
                Spacer(modifier = Modifier.height(8.dp))
                Text(stringResource(R.string.usage_step2), style = MaterialTheme.typography.bodyMedium)
                Spacer(modifier = Modifier.height(8.dp))
                Text(stringResource(R.string.usage_step3), style = MaterialTheme.typography.bodyMedium)
                Spacer(modifier = Modifier.height(8.dp))
                Text(stringResource(R.string.usage_step4), style = MaterialTheme.typography.bodyMedium)
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
            Text(text = "$stepNumber. $title", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
            Spacer(modifier = Modifier.height(8.dp))
            content()
        }
    }
}
