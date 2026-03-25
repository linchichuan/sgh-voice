import json
import traceback
from transcriber import Transcriber

class DummyMemory:
    def add_to_history(self, entry): pass

with open("/Users/lin/voice-input/config.json", "r") as f:
    config = json.load(f)

# Mock voiceprint manager directly
class FakeVPMgr:
    is_enrolled = True
    def verify(self, a): return 0.99

t = Transcriber(config, DummyMemory())
t._voiceprint_mgr = FakeVPMgr()

import numpy as np
fake_audio = np.random.normal(0, 0.1, 16000) # RMS ~ 0.1

t._local_stt = lambda x: "這是一個測試句子，有點長，需要修正，加上嗯啊啊。"
t._has_filler_words = lambda x: True

try:
    res = t.transcribe(fake_audio, audio_duration=1, mode="dictate")
    print("final output:", res)
except Exception as e:
    traceback.print_exc()
