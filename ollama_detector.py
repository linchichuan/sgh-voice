"""
ollama_detector.py — Ollama 本地服務偵測與診斷
支援 Dual-Stack (127.0.0.1 / 0.0.0.0)、CORS 診斷、快取連線路徑
"""
import os
import socket
import threading
import time
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError


class OllamaStatus:
    """Ollama 偵測結果"""
    CONNECTED = "connected"          # 正常連線
    CORS_BLOCKED = "cors_blocked"    # 偵測到服務但被 CORS 擋住
    REFUSED = "refused"              # 連線被拒（防火牆）
    NOT_RUNNING = "not_running"      # Ollama 未啟動
    UNKNOWN = "unknown"              # 未偵測


class OllamaDetector:
    """
    Ollama 本地服務深度偵測器

    功能：
    1. Dual-Stack 非同步偵測 (127.0.0.1 + 0.0.0.0)
    2. CORS / 防火牆 診斷
    3. 快取成功的連線 URL，避免重複偵測
    4. 提供使用者友善的診斷訊息
    """

    # 要測試的位址（優先順序）
    _PROBE_HOSTS = ["127.0.0.1", "0.0.0.0", "localhost"]
    _DEFAULT_PORT = 11434
    _PROBE_TIMEOUT = 2.0  # 偵測超時秒數

    def __init__(self):
        self._lock = threading.Lock()
        self._cached_url: str | None = None       # 成功的 base URL
        self._status = OllamaStatus.UNKNOWN
        self._diagnosis: str = ""
        self._last_check: float = 0
        self._check_interval = 30.0  # 每 30 秒重新偵測一次
        self._models: list[str] = []

    @property
    def status(self) -> str:
        return self._status

    @property
    def base_url(self) -> str | None:
        """回傳已確認可用的 Ollama base URL（含 /v1），或 None"""
        return self._cached_url

    @property
    def diagnosis(self) -> str:
        return self._diagnosis

    @property
    def available_models(self) -> list[str]:
        return self._models

    def detect(self, force=False) -> str:
        """
        執行偵測，回傳 OllamaStatus 值。
        有快取機制，30 秒內不重複偵測（除非 force=True）。
        """
        now = time.time()
        if not force and (now - self._last_check) < self._check_interval:
            return self._status

        with self._lock:
            self._last_check = now
            return self._do_detect()

    def _do_detect(self) -> str:
        """核心偵測邏輯：並行測試多個位址"""
        results = {}
        threads = []

        for host in self._PROBE_HOSTS:
            t = threading.Thread(
                target=self._probe_host,
                args=(host, self._DEFAULT_PORT, results),
                daemon=True
            )
            threads.append(t)
            t.start()

        # 等待所有探測完成（最多等 PROBE_TIMEOUT 秒）
        for t in threads:
            t.join(timeout=self._PROBE_TIMEOUT + 0.5)

        # 分析結果：優先選用成功的連線
        for host in self._PROBE_HOSTS:
            result = results.get(host, {})
            if result.get("status") == "ok":
                base = f"http://{host}:{self._DEFAULT_PORT}/v1"
                if self._status != OllamaStatus.CONNECTED:
                    print(f" ✅ Ollama 偵測成功: {base}")
                self._cached_url = base
                self._status = OllamaStatus.CONNECTED
                self._diagnosis = f"Ollama 連線正常 ({host}:{self._DEFAULT_PORT})"
                self._models = result.get("models", [])
                return self._status

        # 沒有成功，分析失敗原因
        any_cors = any(r.get("status") == "cors" for r in results.values())
        any_refused = any(r.get("status") == "refused" for r in results.values())
        any_reachable = any(r.get("status") in ("cors", "error_response") for r in results.values())

        new_status = self._status
        if any_cors:
            new_status = OllamaStatus.CORS_BLOCKED
            self._diagnosis = (
                "偵測到 Ollama 正在運行，但連線被 CORS 政策擋住。\n"
                "請設定環境變數後重啟 Ollama：\n"
                "  export OLLAMA_ORIGINS=\"*\"\n"
                "  ollama serve"
            )
            self._cached_url = None
        elif any_refused:
            new_status = OllamaStatus.REFUSED
            self._diagnosis = (
                "Ollama 連接埠被拒絕。可能原因：\n"
                "1. 防火牆封鎖了 11434 端口\n"
                "2. Ollama 只綁定了特定 IP\n"
                "請確認 Ollama 是否正在運行：ollama serve"
            )
            self._cached_url = None
        elif any_reachable:
            new_status = OllamaStatus.REFUSED
            self._diagnosis = "Ollama 服務回應異常，請重啟 Ollama。"
            self._cached_url = None
        else:
            new_status = OllamaStatus.NOT_RUNNING
            self._diagnosis = (
                "未偵測到 Ollama 服務。\n"
                "請安裝並啟動 Ollama：https://ollama.com\n"
                "啟動後執行：ollama pull qwen2.5:3b"
            )
            self._cached_url = None

        if new_status != self._status:
            print(f" ⚠️ Ollama 偵測狀態改變: {new_status} — {self._diagnosis.split(chr(10))[0]}")
        self._status = new_status
        return self._status

    def _probe_host(self, host: str, port: int, results: dict):
        """探測單一位址"""
        url = f"http://{host}:{port}"
        result = {"status": "unknown", "models": []}

        # Step 1: TCP Socket 快速檢查端口是否開放
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self._PROBE_TIMEOUT)
            err = sock.connect_ex((host, port))
            sock.close()
            if err != 0:
                result["status"] = "refused"
                results[host] = result
                return
        except Exception:
            result["status"] = "refused"
            results[host] = result
            return

        # Step 2: HTTP 請求 /api/tags（取得模型列表，同時驗證 HTTP 正常）
        try:
            req = Request(
                f"{url}/api/tags",
                headers={
                    "Origin": "http://localhost:7865",
                    "User-Agent": "SGH-Voice/1.0",
                }
            )
            with urlopen(req, timeout=self._PROBE_TIMEOUT) as resp:
                if resp.status == 200:
                    import json
                    data = json.loads(resp.read().decode())
                    models = [m.get("name", "") for m in data.get("models", [])]
                    result["status"] = "ok"
                    result["models"] = models
                else:
                    result["status"] = "error_response"
        except HTTPError as e:
            # 403/405 等 → 服務在但有限制
            if e.code in (403, 405):
                result["status"] = "cors"
            else:
                result["status"] = "error_response"
        except URLError as e:
            reason = str(e.reason) if hasattr(e, 'reason') else str(e)
            if "refused" in reason.lower():
                result["status"] = "refused"
            else:
                result["status"] = "error"
        except Exception:
            result["status"] = "error"

        results[host] = result

    def get_status_dict(self) -> dict:
        """回傳結構化狀態（供 Dashboard API 使用）"""
        return {
            "ollama_status": self._status,
            "ollama_url": self._cached_url,
            "ollama_diagnosis": self._diagnosis,
            "ollama_models": self._models,
            "ollama_available": self._status == OllamaStatus.CONNECTED,
        }

    def check_environment(self) -> dict:
        """檢查與 Ollama 相關的環境變數"""
        ollama_origins = os.environ.get("OLLAMA_ORIGINS", "")
        ollama_host = os.environ.get("OLLAMA_HOST", "")

        issues = []
        if not ollama_origins:
            issues.append("OLLAMA_ORIGINS 未設定（建議設為 '*'）")
        elif "*" not in ollama_origins and "localhost" not in ollama_origins:
            issues.append(f"OLLAMA_ORIGINS='{ollama_origins}'，可能不包含 App 來源")

        if ollama_host and "0.0.0.0" not in ollama_host and "127.0.0.1" not in ollama_host:
            issues.append(f"OLLAMA_HOST='{ollama_host}'，可能綁定到非本地位址")

        return {
            "OLLAMA_ORIGINS": ollama_origins or "(未設定)",
            "OLLAMA_HOST": ollama_host or "(未設定，預設 127.0.0.1:11434)",
            "issues": issues,
            "healthy": len(issues) == 0,
        }


# 全域單例
_detector = OllamaDetector()


def get_detector() -> OllamaDetector:
    """取得全域 OllamaDetector 實例"""
    return _detector
