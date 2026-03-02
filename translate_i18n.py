import json
import openai

def translate(text):
    client = openai.OpenAI()
    prompt = """
    Please translate the following JSON object containing UI strings from Traditional Chinese to Korean, Thai, and Vietnamese.
    Maintain the JSON format perfectly. Do not translate the keys, only the values.
    Output only the raw JSON. No markdown backticks.

    {
        "nav_overview": "總覽", "nav_history": "歷史紀錄", "nav_dictionary": "詞庫記憶", "nav_settings": "設定",
        "card_audio": "總口述時間", "card_audio_sub": "累計錄音",
        "card_words": "口述字數", "card_words_sub": "語音輸入",
        "card_saved": "節省時間", "card_saved_sub": "比打字更快",
        "card_speed": "平均口述速度", "card_speed_unit": "每分鐘字數",
        "card_count": "總聽寫次數", "card_count_sub": "累計使用",
        "card_cost": "本月估算費用",
        "history_title": "歷史紀錄", "history_search": "搜尋紀錄...",
        "col_time": "時間", "col_mode": "模式", "col_raw": "原始辨識", "col_final": "最終文字", "col_duration": "耗時",
        "export_txt": "匯出 TXT", "export_csv": "匯出 CSV", "clear_all": "清除全部",
        "history_empty": "尚無歷史紀錄。開始使用語音輸入後，紀錄會顯示在這裡。",
        "dict_title": "詞庫記憶", "dict_words": "自訂詞彙", "dict_words_desc": "新增專業術語、人名、公司名，提高語音辨識準確度。",
        "dict_add": "新增", "dict_word_placeholder": "輸入新詞彙...",
        "dict_corrections": "修正規則（自動學習 + 手動）", "dict_corrections_desc": "語音辨識常見錯誤 → 正確詞的對應表。手動修正時會自動新增。",
        "dict_wrong": "錯誤詞...", "dict_right": "正確詞...",
        "col_wrong": "錯誤", "col_right": "→ 正確",
        "settings_title": "設定", "save_settings": "💾 儲存設定",
        "personalization": "個人化進度", "quick_voice": "快速語音輸入"
    }

    Expected Output Format:
    {
        "ko": { ... translations ... },
        "th": { ... translations ... },
        "vi": { ... translations ... }
    }
    """
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.0
    )
    return response.choices[0].message.content

print(translate(""))
