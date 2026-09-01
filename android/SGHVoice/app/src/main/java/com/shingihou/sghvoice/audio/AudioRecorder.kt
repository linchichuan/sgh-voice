package com.shingihou.sghvoice.audio

import android.Manifest
import android.content.pm.PackageManager
import android.media.AudioFormat
import android.media.AudioRecord
import android.media.MediaRecorder
import androidx.core.content.ContextCompat
import com.shingihou.sghvoice.SGHVoiceApp
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withTimeoutOrNull
import java.io.ByteArrayOutputStream
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.util.concurrent.atomic.AtomicBoolean

/**
 * 16kHz / 16-bit / mono WAV 錄音器。
 *
 * [startRecording] 在麥克風真正啟動後立即返回，PCM 讀取由內部 IO job 處理。
 * [stopRecording] 會先解除 blocking read、等待讀取 job 收尾，再建立 WAV，
 * 因此可安全支援「點一下開始、再點一下停止」而不依賴按住手勢。
 */
class AudioRecorder {

    companion object {
        private const val SAMPLE_RATE = 16000
        private const val CHANNEL_CONFIG = AudioFormat.CHANNEL_IN_MONO
        private const val AUDIO_FORMAT = AudioFormat.ENCODING_PCM_16BIT
        private const val WAV_HEADER_SIZE = 44
        private const val BITS_PER_SAMPLE = 16
        private const val NUM_CHANNELS = 1
        private const val READER_SHUTDOWN_TIMEOUT_MS = 1_500L
    }

    private val recorderScope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private val lifecycleMutex = Mutex()
    private val resourceLock = Any()
    private val recordingFlag = AtomicBoolean(false)
    private val pcmBuffer = ByteArrayOutputStream()

    @Volatile
    private var released = false

    @Volatile
    private var audioRecord: AudioRecord? = null

    @Volatile
    private var readJob: Job? = null

    @Volatile
    private var levelListener: ((Float) -> Unit)? = null

    val recording: Boolean
        get() = recordingFlag.get()

    fun setLevelListener(listener: ((Float) -> Unit)?) {
        levelListener = listener
    }

    private fun publishLevel(level: Float) {
        try {
            levelListener?.invoke(level.coerceIn(0f, 1f))
        } catch (_: Exception) {
            // The visual meter is best-effort and must never break recording.
        }
    }

    /**
     * 初始化並啟動麥克風。重複開始會明確失敗，避免產生兩個讀取 job。
     */
    suspend fun startRecording() = lifecycleMutex.withLock {
        if (released) {
            throw AudioRecordException("錄音器已關閉")
        }
        if (recordingFlag.get()) {
            throw AudioRecordException("錄音已經開始")
        }

        val context = SGHVoiceApp.instance
        if (ContextCompat.checkSelfPermission(context, Manifest.permission.RECORD_AUDIO)
            != PackageManager.PERMISSION_GRANTED
        ) {
            throw AudioRecordException("未取得錄音權限，請先授予麥克風權限")
        }

        val bufferSize = AudioRecord.getMinBufferSize(
            SAMPLE_RATE,
            CHANNEL_CONFIG,
            AUDIO_FORMAT
        )
        if (bufferSize <= 0) {
            throw AudioRecordException("裝置不支援指定的錄音格式")
        }

        synchronized(pcmBuffer) {
            pcmBuffer.reset()
        }

        val recorder = AudioRecord(
            MediaRecorder.AudioSource.MIC,
            SAMPLE_RATE,
            CHANNEL_CONFIG,
            AUDIO_FORMAT,
            bufferSize * 2
        )

        if (recorder.state != AudioRecord.STATE_INITIALIZED) {
            recorder.release()
            throw AudioRecordException("AudioRecord 初始化失敗，請檢查麥克風是否被佔用")
        }

        try {
            recorder.startRecording()
        } catch (error: Exception) {
            recorder.release()
            throw AudioRecordException("麥克風啟動失敗：${error.message}")
        }

        synchronized(resourceLock) {
            if (released) {
                try {
                    recorder.stop()
                } catch (_: IllegalStateException) {
                    // Service 結束與啟動交錯時可能已停止。
                } finally {
                    recorder.release()
                }
                throw AudioRecordException("錄音器已關閉")
            }

            audioRecord = recorder
            recordingFlag.set(true)
            readJob = recorderScope.launch {
                val buffer = ByteArray(bufferSize)
                try {
                    while (recordingFlag.get() && isActive) {
                        val bytesRead = try {
                            recorder.read(buffer, 0, buffer.size)
                        } catch (_: IllegalStateException) {
                            break
                        }

                        if (bytesRead > 0) {
                            synchronized(pcmBuffer) {
                                pcmBuffer.write(buffer, 0, bytesRead)
                            }
                            publishLevel(
                                AudioLevelMeter.normalizedPcm16(buffer, bytesRead)
                            )
                        } else if (bytesRead < 0) {
                            break
                        }
                    }
                } finally {
                    publishLevel(0f)
                }
            }
        }
    }

    /**
     * 停止錄音並回傳完整 WAV。若尚未開始或沒有音訊則回傳 null。
     */
    suspend fun stopRecording(): ByteArray? = lifecycleMutex.withLock {
        stopLocked(discard = false)
    }

    /**
     * IME 隱藏、切換欄位或 service 結束時使用；停止並丟棄尚未送出的音訊。
     */
    suspend fun abortAndDiscard() = lifecycleMutex.withLock {
        stopLocked(discard = true)
    }

    private suspend fun stopLocked(discard: Boolean): ByteArray? {
        publishLevel(0f)
        val (recorder, reader) = synchronized(resourceLock) {
            recordingFlag.set(false)
            val activeRecorder = audioRecord
            val activeReader = readJob
            audioRecord = null
            readJob = null
            activeRecorder to activeReader
        }

        if (recorder != null) {
            try {
                if (recorder.recordingState == AudioRecord.RECORDSTATE_RECORDING) {
                    recorder.stop()
                }
            } catch (_: IllegalStateException) {
                // 已停止或裝置在 lifecycle 切換時先回收。
            } finally {
                recorder.release()
            }
        }

        if (reader != null) {
            val finished = withTimeoutOrNull(READER_SHUTDOWN_TIMEOUT_MS) {
                reader.join()
                true
            } ?: false
            if (!finished) {
                reader.cancel()
            }
        }

        val pcmData = synchronized(pcmBuffer) {
            val snapshot = pcmBuffer.toByteArray()
            pcmBuffer.reset()
            snapshot
        }

        if (discard || pcmData.isEmpty()) return null
        return createWavData(pcmData)
    }

    private fun createWavData(pcmData: ByteArray): ByteArray {
        val totalDataLen = pcmData.size + WAV_HEADER_SIZE - 8
        val byteRate = SAMPLE_RATE * NUM_CHANNELS * BITS_PER_SAMPLE / 8
        val blockAlign = NUM_CHANNELS * BITS_PER_SAMPLE / 8

        val header = ByteBuffer.allocate(WAV_HEADER_SIZE).apply {
            order(ByteOrder.LITTLE_ENDIAN)
            put("RIFF".toByteArray(Charsets.US_ASCII))
            putInt(totalDataLen)
            put("WAVE".toByteArray(Charsets.US_ASCII))
            put("fmt ".toByteArray(Charsets.US_ASCII))
            putInt(16)
            putShort(1)
            putShort(NUM_CHANNELS.toShort())
            putInt(SAMPLE_RATE)
            putInt(byteRate)
            putShort(blockAlign.toShort())
            putShort(BITS_PER_SAMPLE.toShort())
            put("data".toByteArray(Charsets.US_ASCII))
            putInt(pcmData.size)
        }

        return header.array() + pcmData
    }

    /**
     * 最終同步防線；onDestroy 可立即解除麥克風，不等待 coroutine。
     */
    fun release() {
        publishLevel(0f)
        val (recorder, reader) = synchronized(resourceLock) {
            released = true
            recordingFlag.set(false)
            val activeRecorder = audioRecord
            val activeReader = readJob
            audioRecord = null
            readJob = null
            activeRecorder to activeReader
        }

        reader?.cancel()
        recorder?.let {
            try {
                if (it.recordingState == AudioRecord.RECORDSTATE_RECORDING) {
                    it.stop()
                }
            } catch (_: IllegalStateException) {
                // 已停止。
            } finally {
                it.release()
            }
        }

        synchronized(pcmBuffer) {
            pcmBuffer.reset()
        }
        levelListener = null
        recorderScope.cancel()
    }
}

class AudioRecordException(message: String) : Exception(message)
