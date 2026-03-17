# SGH Voice 模型基準測試

## 目錄結構

```
test/
├── audio/           # 測試音檔（.wav/.mp3/.m4a/.flac）
├── ground_truth/    # 人工標註正確答案（同檔名 .txt）
├── results/         # 測試結果輸出
└── README.md
```

## 建議測試音檔

| 檔名 | 語言 | 內容描述 |
|------|------|---------|
| zh_01.wav | 純繁中 | 一般口語句子 |
| zh_02.wav | 純繁中 | 較長段落 |
| ja_01.wav | 純日語 | 日常會話 |
| ja_02.wav | 純日語 | 商務用語 |
| en_01.wav | 純英語 | 一般英語 |
| mix_zhen_01.wav | 中英混用 | 技術討論（中文夾雜英文術語） |
| mix_jaen_01.wav | 日英混用 | 醫療場景 |
| medical_01.wav | 醫療術語 | 藥品名、診療科目 |

## 使用方式

```bash
# 跑全部模型
python3 scripts/benchmark_models.py

# 只測特定模型
python3 scripts/benchmark_models.py --models breeze-asr-25-4bit

# Claude Code /loop 持續跑
# /loop "cd ~/voice-input && python3 scripts/benchmark_models.py"
```

## 結果

測試完成後，報告輸出至 `results/MODEL_BENCHMARK.md`。
