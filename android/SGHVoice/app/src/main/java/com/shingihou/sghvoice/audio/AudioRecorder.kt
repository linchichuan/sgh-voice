package com.shingihou.sghvoice.audio

import android.Manifest
import android.content.pm.PackageManager
import android.media.AudioFormat
import android.media.AudioRecord
import android.media.MediaRecorder
import androidx.core.content.ContextCompat
import com.shingihou.sghvoice.SGHVoiceApp
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.isActive
import kotlinx.coroutines.withContext
import java.io.ByteArrayOutputStream
import java.nio.ByteBuffer
import java.nio.ByteOrder

/**
 * 音訊錄製器
 * 使用 AudioRecord API 錄製 16kHz 16bit Mono PCM 音訊
 * 錄製完成後轉換為 WAV 格式（含 44 byte 標頭）
 */
class AudioRecorder {

    companion object {
        // 錄音參數：16kHz、16bit、單聲道
        private const val SAMPLE_RATE = 16000
        private const val CHANNEL_CONFIG = AudioFormat.CHANNEL_IN_MONO
        private const val AUDIO_FORMAT = AudioFormat.ENCODING_PCM_16BIT
        private const val WAV_HEADER_SIZE = 44
        private const val BITS_PER_SAMPLE = 16
        private const val NUM_CHANNELS = 1
    }

    private var audioRecord: AudioRecord? = null
    private var isRecording = false
    private val pcmBuffer = ByteArrayOutputStream()

    /** 目前是否正在錄音 */
    val recording: Boolean get() = isRecording

    /**
     * 開始錄音
     * 在背景協程中持續讀取 PCM 資料
     *
     * @throws AudioRecordException 當權限不足或裝置不支援時拋出
     */
    suspend fun startRecording() {
        // 檢查錄音權限
        val context = SGHVoiceApp.instance
        if (ContextCompat.checkSelfPermission(context, Manifest.permission.RECORD_AUDIO)
            != PackageManager.PERMISSION_GRANTED
        ) {
            throw AudioRecordException("未取得錄音權限，請先授予麥克風權限")
        }

        val bufferSize = AudioRecord.getMinBufferSize(SAMPLE_RATE, CHANNEL_CONFIG, AUDIO_FORMAT)
        if (bufferSize == AudioRecord.ERROR_BAD_VALUE || bufferSize == AudioRecord.ERROR) {
            throw AudioRecordException("裝置不支援指定的錄音格式")
        }

        pcmBuffer.reset()

        audioRecord = AudioRecord(
            MediaRecorder.AudioSource.MIC,
            SAMPLE_RATE,
            CHANNEL_CONFIG,
            AUDIO_FORMAT,
            bufferSize * 2 // 使用雙倍緩衝區以避免掉幀
        ).also { recorder ->
            if (recorder.state != AudioRecord.STATE_INITIALIZED) {
                recorder.release()
                throw AudioRecordException("AudioRecord 初始化失敗，請檢查麥克風是否被佔用")
            }

            isRecording = true
            recorder.startRecording()

            // 在 IO 執行緒持續讀取 PCM 資料
            withContext(Dispatchers.IO) {
                val buffer = ByteArray(bufferSize)
                while (isRecording && isActive) {
                    val bytesRead = recorder.read(buffer, 0, buffer.size)
                    if (bytesRead > 0) {
                        synchronized(pcmBuffer) {
                            pcmBuffer.write(buffer, 0, bytesRead)
                        }
                    }
                }
            }
        }
    }

    /**
     * 停止錄音並取得 WAV 格式音訊
     *
     * @return WAV 格式的音訊資料（含 44 byte 標頭），若未錄音則回傳 null
     */
    fun stopRecording(): ByteArray? {
        isRecording = false

        audioRecord?.let { recorder ->
            try {
                if (recorder.recordingState == AudioRecord.RECORDSTATE_RECORDING) {
                    recorder.stop()
                }
            } catch (_: IllegalStateException) {
                // 忽略：錄音器可能已停止
            }
            recorder.release()
        }
        audioRecord = null

        val pcmData: ByteArray
        synchronized(pcmBuffer) {
            pcmData = pcmBuffer.toByteArray()
            pcmBuffer.reset()
        }

        if (pcmData.isEmpty()) return null

        return createWavData(pcmData)
    }

    /**
     * 將 PCM 原始資料加上 WAV 標頭
     * WAV 格式：44 byte RIFF 標頭 + PCM 資料
     */
    private fun createWavData(pcmData: ByteArray): ByteArray {
        val totalDataLen = pcmData.size + WAV_HEADER_SIZE - 8
        val byteRate = SAMPLE_RATE * NUM_CHANNELS * BITS_PER_SAMPLE / 8
        val blockAlign = NUM_CHANNELS * BITS_PER_SAMPLE / 8

        val header = ByteBuffer.allocate(WAV_HEADER_SIZE).apply {
            order(ByteOrder.LITTLE_ENDIAN)

            // RIFF 區塊
            put("RIFF".toByteArray(Charsets.US_ASCII))
            putInt(totalDataLen)
            put("WAVE".toByteArray(Charsets.US_ASCII))

            // fmt 子區塊
            put("fmt ".toByteArray(Charsets.US_ASCII))
            putInt(16) // fmt 區塊大小
            putShort(1) // PCM 格式
            putShort(NUM_CHANNELS.toShort())
            putInt(SAMPLE_RATE)
            putInt(byteRate)
            putShort(blockAlign.toShort())
            putShort(BITS_PER_SAMPLE.toShort())

            // data 子區塊
            put("data".toByteArray(Charsets.US_ASCII))
            putInt(pcmData.size)
        }

        return header.array() + pcmData
    }

    /** 釋放資源 */
    fun release() {
        isRecording = false
        audioRecord?.release()
        audioRecord = null
        pcmBuffer.reset()
    }
}

/** 錄音例外類別 */
class AudioRecordException(message: String) : Exception(message)
