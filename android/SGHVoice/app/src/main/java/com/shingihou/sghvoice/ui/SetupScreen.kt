package com.shingihou.sghvoice.ui

import android.content.Intent
import android.net.Uri
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
import com.shingihou.sghvoice.api.ApiModelCatalog
import com.shingihou.sghvoice.learning.PersonalizationRepository
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
    val personalization = remember { PersonalizationRepository.getInstance(context) }
    
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
                1 -> DictionaryTab(dictionaryManager, personalization)
                2 -> UsageTab()
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
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
    var selectedOpenAiSttModel by remember { mutableStateOf(apiConfig.whisperModel) }
    var selectedGroqSttModel by remember { mutableStateOf(apiConfig.groqSttModel) }
    var selectedClaudeModel by remember { mutableStateOf(apiConfig.claudeModel) }
    var selectedOpenAiLlmModel by remember { mutableStateOf(apiConfig.openAiLlmModel) }
    var selectedGroqLlmModel by remember { mutableStateOf(apiConfig.groqLlmModel) }

    val openAiSttModels = listOf(
        UiModelOption(
            ApiModelCatalog.OPENAI_STT_GPT_4O_MINI,
            stringResource(R.string.model_openai_stt_mini),
            stringResource(R.string.price_openai_stt_mini)
        ),
        UiModelOption(
            ApiModelCatalog.OPENAI_STT_GPT_4O,
            stringResource(R.string.model_openai_stt_full),
            stringResource(R.string.price_openai_stt_full)
        ),
        UiModelOption(
            ApiModelCatalog.OPENAI_STT_WHISPER,
            stringResource(R.string.model_openai_stt_whisper),
            stringResource(R.string.price_openai_stt_whisper)
        )
    )
    val groqSttModels = listOf(
        UiModelOption(
            ApiModelCatalog.GROQ_STT_TURBO,
            stringResource(R.string.model_groq_stt_turbo),
            stringResource(R.string.price_groq_stt_turbo)
        ),
        UiModelOption(
            ApiModelCatalog.GROQ_STT_LARGE,
            stringResource(R.string.model_groq_stt_large),
            stringResource(R.string.price_groq_stt_large)
        )
    )
    val claudeModels = listOf(
        UiModelOption(
            ApiModelCatalog.CLAUDE_HAIKU_4_5,
            stringResource(R.string.model_claude_haiku),
            stringResource(R.string.price_claude_haiku)
        ),
        UiModelOption(
            ApiModelCatalog.CLAUDE_SONNET_5,
            stringResource(R.string.model_claude_sonnet),
            stringResource(R.string.price_claude_sonnet)
        ),
        UiModelOption(
            ApiModelCatalog.CLAUDE_OPUS_4_8,
            stringResource(R.string.model_claude_opus),
            stringResource(R.string.price_claude_opus)
        ),
        UiModelOption(
            ApiModelCatalog.CLAUDE_FABLE_5,
            stringResource(R.string.model_claude_fable),
            stringResource(R.string.price_claude_fable)
        )
    )
    val openAiLlmModels = listOf(
        UiModelOption(
            ApiModelCatalog.OPENAI_LLM_GPT_4O_MINI,
            stringResource(R.string.model_openai_llm_mini),
            stringResource(R.string.price_openai_llm_mini)
        ),
        UiModelOption(
            ApiModelCatalog.OPENAI_LLM_GPT_4O,
            stringResource(R.string.model_openai_llm_full),
            stringResource(R.string.price_openai_llm_full)
        )
    )
    val groqLlmModels = listOf(
        UiModelOption(
            ApiModelCatalog.GROQ_LLM_GPT_OSS_20B,
            stringResource(R.string.model_groq_llm_small),
            stringResource(R.string.price_groq_llm_small)
        ),
        UiModelOption(
            ApiModelCatalog.GROQ_LLM_GPT_OSS_120B,
            stringResource(R.string.model_groq_llm_large),
            stringResource(R.string.price_groq_llm_large)
        )
    )

    Column(
        modifier = Modifier.fillMaxSize().verticalScroll(scrollState),
        verticalArrangement = Arrangement.spacedBy(16.dp)
    ) {
        Text(stringResource(R.string.title_basic_settings), style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold)

        // === 步驟一：引擎選擇 ===
        StepCard(stepNumber = 1, title = stringResource(R.string.step_engine_selection)) {
            Text(stringResource(R.string.label_stt_engine), fontWeight = FontWeight.SemiBold)
            val sttEngines = listOf("openai" to stringResource(R.string.engine_openai), "groq" to stringResource(R.string.engine_groq))
            sttEngines.forEach { (id, name) ->
                Row(verticalAlignment = Alignment.CenterVertically) {
                    RadioButton(selected = selectedSttEngine == id, onClick = { selectedSttEngine = id })
                    Text(text = name)
                }
            }

            when (selectedSttEngine) {
                "groq" -> ModelSelector(
                    label = stringResource(R.string.label_stt_model),
                    selectedModel = selectedGroqSttModel,
                    options = groqSttModels,
                    onModelSelected = { selectedGroqSttModel = it }
                )
                else -> ModelSelector(
                    label = stringResource(R.string.label_stt_model),
                    selectedModel = selectedOpenAiSttModel,
                    options = openAiSttModels,
                    onModelSelected = { selectedOpenAiSttModel = it }
                )
            }
            
            Spacer(modifier = Modifier.height(8.dp))
            Text(stringResource(R.string.label_llm_engine), fontWeight = FontWeight.SemiBold)
            val llmEngines = listOf(
                "claude" to stringResource(R.string.engine_claude),
                "openai" to stringResource(R.string.engine_openai),
                "groq" to stringResource(R.string.engine_groq),
                "none" to stringResource(R.string.engine_none)
            )
            llmEngines.forEach { (id, name) ->
                Row(verticalAlignment = Alignment.CenterVertically) {
                    RadioButton(selected = selectedLlmEngine == id, onClick = { selectedLlmEngine = id })
                    Text(text = name)
                }
            }

            when (selectedLlmEngine) {
                "claude" -> ModelSelector(
                    label = stringResource(R.string.label_llm_model),
                    selectedModel = selectedClaudeModel,
                    options = claudeModels,
                    onModelSelected = { selectedClaudeModel = it }
                )
                "openai" -> ModelSelector(
                    label = stringResource(R.string.label_llm_model),
                    selectedModel = selectedOpenAiLlmModel,
                    options = openAiLlmModels,
                    onModelSelected = { selectedOpenAiLlmModel = it }
                )
                "groq" -> ModelSelector(
                    label = stringResource(R.string.label_llm_model),
                    selectedModel = selectedGroqLlmModel,
                    options = groqLlmModels,
                    onModelSelected = { selectedGroqLlmModel = it }
                )
            }

            if (selectedLlmEngine == "groq") {
                Text(
                    text = stringResource(R.string.groq_reasoning_notice),
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.primary
                )
            }
            Text(
                text = stringResource(R.string.model_cost_notice),
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
            Text(
                text = stringResource(R.string.model_price_reference),
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
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
                    apiConfig.whisperModel = selectedOpenAiSttModel
                    apiConfig.groqSttModel = selectedGroqSttModel
                    apiConfig.claudeModel = selectedClaudeModel
                    apiConfig.openAiLlmModel = selectedOpenAiLlmModel
                    apiConfig.groqLlmModel = selectedGroqLlmModel
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

private data class UiModelOption(
    val id: String,
    val label: String,
    val pricing: String
)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun ModelSelector(
    label: String,
    selectedModel: String,
    options: List<UiModelOption>,
    onModelSelected: (String) -> Unit
) {
    var expanded by remember { mutableStateOf(false) }
    val selectedOption = options.firstOrNull { it.id == selectedModel }
    val selectedLabel = selectedOption?.label
        ?: selectedModel

    Spacer(modifier = Modifier.height(6.dp))
    ExposedDropdownMenuBox(
        expanded = expanded,
        onExpandedChange = { expanded = !expanded }
    ) {
        OutlinedTextField(
            value = selectedLabel,
            onValueChange = {},
            readOnly = true,
            label = { Text(label) },
            trailingIcon = {
                ExposedDropdownMenuDefaults.TrailingIcon(expanded = expanded)
            },
            modifier = Modifier
                .menuAnchor()
                .fillMaxWidth()
        )
        ExposedDropdownMenu(
            expanded = expanded,
            onDismissRequest = { expanded = false }
        ) {
            options.forEach { option ->
                DropdownMenuItem(
                    text = {
                        Column {
                            Text(option.label)
                            Text(
                                text = option.pricing,
                                style = MaterialTheme.typography.labelSmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant
                            )
                        }
                    },
                    onClick = {
                        onModelSelected(option.id)
                        expanded = false
                    }
                )
            }
        }
    }
    Text(
        text = stringResource(R.string.model_id_format, selectedModel),
        style = MaterialTheme.typography.labelSmall,
        color = MaterialTheme.colorScheme.onSurfaceVariant,
        modifier = Modifier.padding(start = 16.dp, top = 3.dp)
    )
    selectedOption?.let { option ->
        Text(
            text = option.pricing,
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.primary,
            modifier = Modifier.padding(start = 16.dp, top = 2.dp)
        )
    }
}

@OptIn(ExperimentalLayoutApi::class, ExperimentalMaterial3Api::class)
@Composable
private fun DictionaryTab(
    dictionaryManager: DictionaryManager,
    personalization: PersonalizationRepository
) {
    val scrollState = rememberScrollState()
    var newWord by remember { mutableStateOf("") }
    var customWords by remember { mutableStateOf(dictionaryManager.getCustomWords()) }
    
    var wrongText by remember { mutableStateOf("") }
    var correctText by remember { mutableStateOf("") }
    var corrections by remember { mutableStateOf(dictionaryManager.getCorrections()) }
    var learningEnabled by remember { mutableStateOf(personalization.isEnabled()) }
    var learningStats by remember { mutableStateOf(personalization.getStats()) }
    var learningMessage by remember { mutableStateOf("") }
    var showClearLearningDialog by remember { mutableStateOf(false) }
    val learningClearedMessage = stringResource(R.string.msg_learning_cleared)

    Column(
        modifier = Modifier.fillMaxSize().verticalScroll(scrollState),
        verticalArrangement = Arrangement.spacedBy(16.dp)
    ) {
        Text(stringResource(R.string.title_dictionary_manage), style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold)

        Card(modifier = Modifier.fillMaxWidth()) {
            Column(
                modifier = Modifier.padding(16.dp),
                verticalArrangement = Arrangement.spacedBy(10.dp)
            ) {
                Text(
                    stringResource(R.string.title_personalized_learning),
                    fontWeight = FontWeight.Bold,
                    style = MaterialTheme.typography.titleMedium
                )
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.SpaceBetween
                ) {
                    Text(
                        stringResource(R.string.label_personalized_learning),
                        modifier = Modifier.weight(1f)
                    )
                    Switch(
                        checked = learningEnabled,
                        onCheckedChange = { enabled ->
                            personalization.setEnabled(enabled)
                            learningEnabled = enabled
                            learningStats = personalization.getStats()
                            learningMessage = ""
                        }
                    )
                }
                Text(
                    stringResource(R.string.desc_personalized_learning),
                    style = MaterialTheme.typography.bodySmall
                )
                Text(
                    stringResource(
                        R.string.learning_stats,
                        learningStats.candidateRecordCount,
                        learningStats.activeCorrectionRuleCount
                    ),
                    style = MaterialTheme.typography.bodyMedium,
                    fontWeight = FontWeight.SemiBold
                )
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    OutlinedButton(
                        onClick = {
                            if (personalization.undoLast()) {
                                learningStats = personalization.getStats()
                                learningMessage = ""
                            }
                        },
                        modifier = Modifier.weight(1f)
                    ) {
                        Text(stringResource(R.string.btn_undo_learning))
                    }
                    OutlinedButton(
                        onClick = { showClearLearningDialog = true },
                        modifier = Modifier.weight(1f)
                    ) {
                        Text(stringResource(R.string.btn_clear_learning))
                    }
                }
                if (learningMessage.isNotBlank()) {
                    Text(
                        learningMessage,
                        color = MaterialTheme.colorScheme.primary,
                        style = MaterialTheme.typography.bodySmall
                    )
                }
            }
        }

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

    if (showClearLearningDialog) {
        AlertDialog(
            onDismissRequest = { showClearLearningDialog = false },
            title = { Text(stringResource(R.string.btn_clear_learning)) },
            text = { Text(stringResource(R.string.confirm_clear_learning)) },
            confirmButton = {
                TextButton(
                    onClick = {
                        personalization.clearAll()
                        learningStats = personalization.getStats()
                        learningMessage = learningClearedMessage
                        showClearLearningDialog = false
                    }
                ) {
                    Text(stringResource(R.string.btn_clear_learning))
                }
            },
            dismissButton = {
                TextButton(onClick = { showClearLearningDialog = false }) {
                    Text(stringResource(android.R.string.cancel))
                }
            }
        )
    }
}

@Composable
private fun UsageTab() {
    val context = LocalContext.current
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
        Card(modifier = Modifier.fillMaxWidth()) {
            Column(modifier = Modifier.padding(16.dp)) {
                Text(
                    stringResource(R.string.jmdict_attribution),
                    style = MaterialTheme.typography.bodySmall
                )
                TextButton(
                    onClick = {
                        context.startActivity(
                            Intent(
                                Intent.ACTION_VIEW,
                                Uri.parse("https://www.edrdg.org/edrdg/licence.html")
                            )
                        )
                    }
                ) {
                    Text(stringResource(R.string.btn_dictionary_license))
                }
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
