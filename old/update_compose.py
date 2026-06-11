import re

with open("android/SGHVoice/app/src/main/java/com/shingihou/sghvoice/ui/SetupScreen.kt", "r", encoding="utf-8") as f:
    content = f.read()

# Add imports
if "androidx.compose.ui.res.stringResource" not in content:
    content = content.replace("import com.shingihou.sghvoice.processing.DictionaryManager",
                              "import com.shingihou.sghvoice.processing.DictionaryManager\nimport androidx.compose.ui.res.stringResource\nimport com.shingihou.sghvoice.R")

# Main Screen
content = content.replace('val tabs = listOf("基本設定", "個人詞庫", "使用說明")',
                          '''val tabs = listOf(
        stringResource(R.string.tab_basic_settings),
        stringResource(R.string.tab_dictionary),
        stringResource(R.string.tab_usage_guide)
    )''')

# BasicSettingsTab
content = content.replace('var saveMessage by remember { mutableStateOf("") }',
                          'var saveMessage by remember { mutableStateOf("") }\n    val msgSaved = stringResource(R.string.msg_keys_saved)')
content = content.replace('Text("SGH Voice 基本設定"', 'Text(stringResource(R.string.title_basic_settings)')
content = content.replace('title = "設定 API 金鑰"', 'title = stringResource(R.string.step_api_keys)')
content = content.replace('Text("OpenAI API 金鑰")', 'Text(stringResource(R.string.openai_key_label))')
content = content.replace('if (showOpenAiKey) "隱藏" else "顯示"', 'if (showOpenAiKey) stringResource(R.string.btn_hide) else stringResource(R.string.btn_show)')
content = content.replace('Text("Anthropic API 金鑰")', 'Text(stringResource(R.string.anthropic_key_label))')
content = content.replace('if (showAnthropicKey) "隱藏" else "顯示"', 'if (showAnthropicKey) stringResource(R.string.btn_hide) else stringResource(R.string.btn_show)')
content = content.replace('saveMessage = "金鑰已儲存"', 'saveMessage = msgSaved')
content = content.replace('Text("儲存金鑰")', 'Text(stringResource(R.string.btn_save_keys))')

content = content.replace('title = "啟用輸入法"', 'title = stringResource(R.string.step_enable_ime)')
content = content.replace('Text("請在系統設定中啟用 SGH Voice，並手動切換至該輸入法。"', 'Text(stringResource(R.string.desc_enable_ime)')
content = content.replace('Text("啟用設定")', 'Text(stringResource(R.string.btn_enable_settings))')
content = content.replace('Text("切換輸入法")', 'Text(stringResource(R.string.btn_switch_ime))')

# DictionaryTab
content = content.replace('Text("個人詞庫管理"', 'Text(stringResource(R.string.title_dictionary_manage)')
content = content.replace('Text("自訂詞彙 (提升辨識率)"', 'Text(stringResource(R.string.title_custom_words)')
content = content.replace('Text("新增專有名詞")', 'Text(stringResource(R.string.label_add_proper_noun))')
content = content.replace('Text("錯誤修正規則"', 'Text(stringResource(R.string.title_corrections)')
content = content.replace('Text("原字")', 'Text(stringResource(R.string.label_wrong_word))')
content = content.replace('Text("修正")', 'Text(stringResource(R.string.label_correct_word))')

# UsageTab
content = content.replace('Text("使用說明"', 'Text(stringResource(R.string.usage_title)')
content = content.replace('Text("1. 按住藍色麥克風說話，放開即停止並開始辨識。"', 'Text(stringResource(R.string.usage_step1)')
content = content.replace('Text("2. 系統會自動處理中、日、英三語混合，並修正口語填充詞。"', 'Text(stringResource(R.string.usage_step2)')
content = content.replace('Text("3. 所有的簡體字都會在最後一步自動轉為繁體中文（台灣慣用詞）。"', 'Text(stringResource(R.string.usage_step3)')
content = content.replace('Text("4. 若有專有名詞辨識不準，請在「個人詞庫」中新增該詞彙。"', 'Text(stringResource(R.string.usage_step4)')

# StepCard
content = content.replace('Text(text = "步驟 $stepNumber: $title"', 'Text(text = "$stepNumber. $title"')

with open("android/SGHVoice/app/src/main/java/com/shingihou/sghvoice/ui/SetupScreen.kt", "w", encoding="utf-8") as f:
    f.write(content)

