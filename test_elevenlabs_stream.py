import os
import sys
import json
import time
from typing import Iterator

try:
    from openai import OpenAI
    import elevenlabs
    from elevenlabs.client import ElevenLabs
    from elevenlabs import stream
except ImportError:
    print("⚠️ 缺少必要的套件，請執行:")
    print("pip install openai 'elevenlabs<1.0' (或最新版)")
    sys.exit(1)

def load_keys():
    """從 voice-input/config.json 讀取 OpenAI Key，並嘗試從環境變數讀取 ElevenLabs Key"""
    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
    openai_key = None
    if os.path.exists(config_path):
        with open(config_path, "r") as f:
            config = json.load(f)
            openai_key = config.get("openai_api_key")
            
    elevenlabs_key = os.environ.get("ELEVENLABS_API_KEY")
    if not elevenlabs_key:
         elevenlabs_key = input("🔑 請輸入 ElevenLabs API Key (不會儲存, 或設定 ELEVENLABS_API_KEY): ").strip()
         
    return openai_key, elevenlabs_key

def main():
    openai_key, elevenlabs_key = load_keys()
    
    if not openai_key or not elevenlabs_key:
        print("⚠️ OpenAI API Key 或 ElevenLabs API Key 缺失！")
        return

    # 1. 建立 Clients
    oai = OpenAI(api_key=openai_key)
    el = ElevenLabs(api_key=elevenlabs_key)

    # 2. 定義文字產生器 (Generator) 
    # LLM 每生出一個字，就 yield 給 TTS
    def text_stream_generator(prompt: str) -> Iterator[str]:
        print(f"\n🗣️ [使用者要求]: {prompt}")
        print("🧠 [LLM 思考中... 即時輸出] ", end="", flush=True)
        
        t0 = time.time()
        first_chunk_time = None
        
        # 開啟 OpenAI Streaming 模式
        response = oai.chat.completions.create(
            model="gpt-4o-mini", # 為了速度展示，可以用 mini 或 GPT-4o
            messages=[
                {"role": "system", "content": "你是一個講話簡潔扼要、帶一點日語風格的中日雙語助手。兩句話內回答完畢。"},
                {"role": "user", "content": prompt}
            ],
            stream=True
        )
        
        for chunk in response:
            content = chunk.choices[0].delta.content
            if content:
                if first_chunk_time is None:
                    first_chunk_time = time.time()
                    print(f"\n⚡ LLM 首字延遲: {first_chunk_time - t0:.2f} 秒")
                    
                # 印在畫面上
                sys.stdout.write(content)
                sys.stdout.flush()
                # 同時即時交由 ElevenLabs 合成
                yield content
                
        print() # 斷行

    print("🎙️ ElevenLabs x OpenAI 流式對話展示 (Streaming TTS)")
    print("=" * 60)
    print("注意：播放需要安裝 'mpv' 播放器 (macOS: brew install mpv)")
    
    user_input = "請你推薦福岡一家好吃的拉麵店！"

    # 3. 觸發雙管齊下的 Streaming
    # LLM 發脾氣 (Generator) -> ElevenLabs 合成 (WebSocket) -> mpv 播放
    try:
        # ElevenLabs v1 API streaming 寫法
        # (v2 版本為: convert_as_stream)
        # 這裡的 voice_id 找一個順耳的 (例如 Rachel: 21m00Tcm4TlvDq8ikWAM, 你也可以換自己的)
        
        # 建立 Audio Iterator
        audio_stream = el.text_to_speech.convert_as_stream(
            text=text_stream_generator(user_input),
            voice_id="21m00Tcm4TlvDq8ikWAM", # Default 'Rachel' Voice ID
            model_id="eleven_multilingual_v2" 
        )
        
        # 即時串流播放 (這行不會卡著等全部產生，會邊抓邊播)
        print("🔊 TTS 語音發送中...")
        stream(audio_stream)
        print("\n✅ 完成播放！")
        
    except Exception as e:
        print(f"\n❌ 錯誤發生: {e}")

if __name__ == "__main__":
    main()
