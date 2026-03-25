"""
voiceprint.py — 聲紋辨識模組
使用 MFCC 特徵提取 + Cosine Similarity 進行說話人驗證。
純 numpy/scipy 實作，不依賴 PyTorch/ONNX，打包體積零增長。

使用方式：
  # 建立聲紋（只需執行一次）
  mgr = VoiceprintManager()
  mgr.enroll_from_directory('/Volumes/Satechi_SSD/voice-input/voice-data-lin')

  # 驗證音訊
  is_me = mgr.is_owner(audio_array)  # True/False
  score = mgr.verify(audio_array)     # 0.0 ~ 1.0
"""
import os
import glob
import numpy as np


def _dct_ii(x, norm="ortho"):
    """DCT-II (pure numpy, no scipy dependency)"""
    N = x.shape[-1]
    k = np.arange(N)
    n = np.arange(N)
    cos_matrix = np.cos(np.pi * (2 * n[None, :] + 1) * k[:, None] / (2 * N))
    result = x @ cos_matrix.T
    if norm == "ortho":
        result[..., 0] *= np.sqrt(1 / (4 * N))
        result[..., 1:] *= np.sqrt(1 / (2 * N))
        result *= 2
    return result

# ─── Constants ───────────────────────────────────────────
VOICEPRINT_FILE = os.path.expanduser("~/.voice-input/voiceprint.npy")
DEFAULT_THRESHOLD = 0.97
N_MFCC = 40
N_FFT = 512
HOP_LENGTH = 160
N_MELS = 40
DEFAULT_SR = 16000


# ─── MFCC Feature Extraction (Pure numpy/scipy) ─────────

def _compute_mfcc(audio, sr=DEFAULT_SR):
    """計算 MFCC 特徵（不依賴 librosa/torchaudio）"""
    if len(audio) < N_FFT:
        return None

    # Pre-emphasis
    audio = np.append(audio[0], audio[1:] - 0.97 * audio[:-1])

    # Frame the signal
    num_frames = 1 + (len(audio) - N_FFT) // HOP_LENGTH
    if num_frames < 1:
        return None
    frames = np.zeros((num_frames, N_FFT))
    for i in range(num_frames):
        frames[i] = audio[i * HOP_LENGTH : i * HOP_LENGTH + N_FFT]

    # Hamming window
    frames *= np.hamming(N_FFT)

    # FFT → Power spectrum
    mag = np.abs(np.fft.rfft(frames, n=N_FFT))
    power = mag ** 2 / N_FFT

    # Mel filterbank
    low_freq, high_freq = 0, sr / 2
    mel_low = 2595 * np.log10(1 + low_freq / 700)
    mel_high = 2595 * np.log10(1 + high_freq / 700)
    mel_points = np.linspace(mel_low, mel_high, N_MELS + 2)
    hz_points = 700 * (10 ** (mel_points / 2595) - 1)
    bins = np.floor((N_FFT + 1) * hz_points / sr).astype(int)

    fbank = np.zeros((N_MELS, N_FFT // 2 + 1))
    for m in range(1, N_MELS + 1):
        for k in range(bins[m - 1], bins[m]):
            fbank[m - 1, k] = (k - bins[m - 1]) / max(1, bins[m] - bins[m - 1])
        for k in range(bins[m], bins[m + 1]):
            fbank[m - 1, k] = (bins[m + 1] - k) / max(1, bins[m + 1] - bins[m])

    mel_spec = np.dot(power, fbank.T)
    mel_spec = np.where(mel_spec == 0, np.finfo(float).eps, mel_spec)
    log_mel = np.log(mel_spec)

    # DCT → MFCC
    mfcc = _dct_ii(log_mel, norm="ortho")[:, :N_MFCC]
    return mfcc


def _get_embedding(audio, sr=DEFAULT_SR):
    """從音訊提取 speaker embedding (mean + std of MFCC)"""
    mfcc = _compute_mfcc(audio, sr)
    if mfcc is None or len(mfcc) < 5:
        return None
    return np.concatenate([mfcc.mean(axis=0), mfcc.std(axis=0)])


def _cosine_similarity(a, b):
    """計算 cosine similarity"""
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))


# ─── VoiceprintManager ──────────────────────────────────

class VoiceprintManager:
    """聲紋管理器：建立、儲存、驗證"""

    def __init__(self, voiceprint_path=VOICEPRINT_FILE):
        self.voiceprint_path = voiceprint_path
        self._voiceprint = None  # lazy load

    @property
    def voiceprint(self):
        """Lazy load voiceprint from file"""
        if self._voiceprint is None:
            if os.path.exists(self.voiceprint_path):
                self._voiceprint = np.load(self.voiceprint_path)
        return self._voiceprint

    @property
    def is_enrolled(self) -> bool:
        """是否已經建立聲紋"""
        return self.voiceprint is not None

    def enroll_from_directory(self, wav_dir, min_rms=0.001):
        """
        從目錄中的 WAV 檔建立聲紋。
        Args:
            wav_dir: 包含 WAV 檔案的目錄
            min_rms: 最低音量閾值（跳過靜音）
        Returns:
            dict: { valid_files, total_files, self_similarity_mean, self_similarity_min }
        """
        import soundfile as sf

        wavs = sorted(glob.glob(os.path.join(wav_dir, "*.wav")))
        if not wavs:
            raise FileNotFoundError(f"No WAV files found in {wav_dir}")

        embeddings = []
        for w in wavs:
            try:
                data, sr = sf.read(w)
                if data.ndim > 1:
                    data = data[:, 0]  # Mono
                if sr != DEFAULT_SR:
                    # Simple resample
                    ratio = sr / DEFAULT_SR
                    indices = np.round(np.arange(0, len(data), ratio)).astype(int)
                    indices = indices[indices < len(data)]
                    data = data[indices]
                rms = np.sqrt(np.mean(data ** 2))
                if rms < min_rms:
                    continue
                embed = _get_embedding(data.astype(np.float32))
                if embed is not None:
                    embeddings.append(embed)
            except Exception as e:
                print(f"  Skip {os.path.basename(w)}: {e}")

        if not embeddings:
            raise ValueError("No valid audio files found for enrollment")

        # Average embedding = voiceprint
        self._voiceprint = np.mean(embeddings, axis=0).astype(np.float32)

        # Save
        os.makedirs(os.path.dirname(self.voiceprint_path), exist_ok=True)
        np.save(self.voiceprint_path, self._voiceprint)

        # Calculate self-similarity stats
        sims = [_cosine_similarity(self._voiceprint, emb) for emb in embeddings]

        return {
            "valid_files": len(embeddings),
            "total_files": len(wavs),
            "self_similarity_mean": float(np.mean(sims)),
            "self_similarity_min": float(np.min(sims)),
        }

    def enroll_from_audio(self, audio_arrays, sample_rate=DEFAULT_SR):
        """
        從多段音訊陣列建立聲紋。
        Args:
            audio_arrays: list of numpy arrays
            sample_rate: 取樣率
        """
        embeddings = []
        for audio in audio_arrays:
            embed = _get_embedding(audio.astype(np.float32), sample_rate)
            if embed is not None:
                embeddings.append(embed)
        if not embeddings:
            raise ValueError("No valid audio for enrollment")

        self._voiceprint = np.mean(embeddings, axis=0).astype(np.float32)
        os.makedirs(os.path.dirname(self.voiceprint_path), exist_ok=True)
        np.save(self.voiceprint_path, self._voiceprint)

    def verify(self, audio_array, sample_rate=DEFAULT_SR) -> float:
        """
        驗證音訊與已註冊聲紋的相似度。
        Args:
            audio_array: numpy array (float32, mono)
            sample_rate: 取樣率
        Returns:
            float: cosine similarity (0.0 ~ 1.0)，越高越像
        """
        if not self.is_enrolled:
            return 1.0  # 未註冊聲紋時，放行所有音訊

        embed = _get_embedding(audio_array.astype(np.float32), sample_rate)
        if embed is None:
            return 0.0  # 音訊太短，無法提取特徵

        return _cosine_similarity(self.voiceprint, embed)

    def is_owner(self, audio_array, sample_rate=DEFAULT_SR, threshold=DEFAULT_THRESHOLD) -> bool:
        """
        判斷音訊是否為聲紋擁有者。
        Args:
            audio_array: numpy array
            sample_rate: 取樣率
            threshold: 相似度閾值（預設 0.97）
        Returns:
            bool: True = 是本人, False = 不是
        """
        return self.verify(audio_array, sample_rate) >= threshold

    def delete_voiceprint(self):
        """刪除已儲存的聲紋"""
        if os.path.exists(self.voiceprint_path):
            os.remove(self.voiceprint_path)
        self._voiceprint = None

    def get_info(self) -> dict:
        """取得聲紋資訊（供 Dashboard 顯示）"""
        if not self.is_enrolled:
            return {"enrolled": False}
        return {
            "enrolled": True,
            "embedding_dim": len(self.voiceprint),
            "file_path": self.voiceprint_path,
            "file_size": os.path.getsize(self.voiceprint_path),
        }


# ─── CLI 測試 ────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    mgr = VoiceprintManager()

    if len(sys.argv) > 1 and sys.argv[1] == "enroll":
        wav_dir = sys.argv[2] if len(sys.argv) > 2 else "/Volumes/Satechi_SSD/voice-input/voice-data-lin"
        print(f"🎙️ Enrolling from: {wav_dir}")
        result = mgr.enroll_from_directory(wav_dir)
        print(f"✅ Enrolled: {result['valid_files']}/{result['total_files']} files")
        print(f"   Self-similarity: mean={result['self_similarity_mean']:.4f}, min={result['self_similarity_min']:.4f}")
    elif len(sys.argv) > 1 and sys.argv[1] == "test":
        if not mgr.is_enrolled:
            print("❌ No voiceprint enrolled. Run: python voiceprint.py enroll")
            sys.exit(1)
        # Test with live recording
        import sounddevice as sd
        print("🎤 Recording 3 seconds... Speak now!")
        audio = sd.rec(int(3 * DEFAULT_SR), samplerate=DEFAULT_SR, channels=1, dtype="float32")
        sd.wait()
        audio = audio.flatten()
        score = mgr.verify(audio)
        is_me = mgr.is_owner(audio)
        print(f"Score: {score:.4f} → {'✅ Owner' if is_me else '❌ Not owner'}")
    else:
        print("Usage:")
        print("  python voiceprint.py enroll [wav_dir]  # Build voiceprint")
        print("  python voiceprint.py test              # Test with live mic")
        print(f"\nStatus: {'✅ Enrolled' if mgr.is_enrolled else '❌ Not enrolled'}")
        if mgr.is_enrolled:
            info = mgr.get_info()
            print(f"  Embedding dim: {info['embedding_dim']}")
            print(f"  File: {info['file_path']} ({info['file_size']} bytes)")
