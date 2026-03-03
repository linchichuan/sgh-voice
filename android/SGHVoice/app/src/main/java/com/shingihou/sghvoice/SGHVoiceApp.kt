package com.shingihou.sghvoice

import android.app.Application

/**
 * SGH Voice 應用程式類別
 * 全域初始化：OpenCC、詞庫等
 */
class SGHVoiceApp : Application() {

    companion object {
        lateinit var instance: SGHVoiceApp
            private set
    }

    override fun onCreate() {
        super.onCreate()
        instance = this
    }
}
