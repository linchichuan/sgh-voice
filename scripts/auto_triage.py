import json
import os
import time
from collections import Counter
import openai
from config import load_config, DATA_DIR

HISTORY_FILE = os.path.join(DATA_DIR, "history.json")
REPORT_FILE = os.path.join(DATA_DIR, "auto_triage_report.md")

def analyze_history():
    if not os.path.exists(HISTORY_FILE):
        print("No history found.")
        return

    with open(HISTORY_FILE, "r", encoding="utf-8") as f:
        try:
            history = json.load(f)
        except:
            print("Failed to load history.")
            return

    edited_items = [h for h in history if h.get("edited", False)]
    
    print(f"Total history records: {len(history)}")
    print(f"Total edited records: {len(edited_items)}")

    if not edited_items:
        print("No user edits found. No triage needed.")
        return

    config = load_config()
    
    # Generate a prompt to analyze errors
    prompt = "你是一個語音辨識系統的優化助理。請分析以下使用者修改過的歷史紀錄，找出最常被辨識錯誤的「名詞」或「短語」，並給出建議的字典替換規則 (A -> B)。只回傳 Markdown 格式的整理表格與原因分析。\n\n"
    
    samples = []
    for h in edited_items[-50:]:  # Take the last 50 edits
        raw = h.get("whisper_raw", "")
        final = h.get("final_text", "")
        if raw and final and raw != final:
            samples.append(f"- 原始辨識: {raw}\n- 使用者修正後: {final}\n")
    
    prompt += "\n".join(samples)

    if not samples:
        print("No valid edit samples to analyze.")
        return

    print("Analyzing with LLM...")
    
    # Try Anthropic first, then OpenAI, then Ollama
    report_content = ""
    try:
        if config.get("anthropic_api_key"):
            import anthropic
            client = anthropic.Anthropic(api_key=config["anthropic_api_key"])
            response = client.messages.create(
                model="claude-3-5-haiku-20241022",
                max_tokens=1000,
                system="你是一個專精於繁體中文語音辨識錯誤分析的語言學專家。找出系統性的錯誤。",
                messages=[{"role": "user", "content": prompt}]
            )
            report_content = response.content[0].text
        elif config.get("openai_api_key"):
            import openai
            client = openai.OpenAI(api_key=config["openai_api_key"])
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "你是一個專精於繁體中文語音辨識錯誤分析的語言學專家。找出系統性的錯誤。"},
                    {"role": "user", "content": prompt}
                ]
            )
            report_content = response.choices[0].message.content
        else:
            # Fallback to Ollama
            import requests
            model = config.get("local_llm_model", "qwen2.5:3b")
            resp = requests.post("http://localhost:11434/api/generate", json={
                "model": model,
                "prompt": "系統：你是一個專精於繁體中文語音辨識錯誤分析的語言學專家。\n\n用戶：" + prompt,
                "stream": False
            })
            if resp.status_code == 200:
                report_content = resp.json().get("response", "")
    except Exception as e:
        print(f"LLM Error: {e}")
        return

    if report_content:
        report_text = f"# 語音辨識自動優化報告 (Auto-Triage)\n\n**產生時間**: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n{report_content}\n"
        with open(REPORT_FILE, "w", encoding="utf-8") as f:
            f.write(report_text)
        print(f"Report generated at {REPORT_FILE}")

if __name__ == "__main__":
    analyze_history()
