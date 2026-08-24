package com.shingihou.sghvoice.ime

/**
 * 長按退格的純資料策略，與 View callback 分離以便做 JVM 回歸測試。
 */
internal object BackspaceRepeatPolicy {
    const val INITIAL_DELAY_MS = 420L
    const val NORMAL_INTERVAL_MS = 85L
    const val FAST_INTERVAL_MS = 42L
    const val ACCELERATE_AFTER = 12

    fun intervalAfter(repeatCount: Int): Long =
        if (repeatCount >= ACCELERATE_AFTER) {
            FAST_INTERVAL_MS
        } else {
            NORMAL_INTERVAL_MS
        }
}
