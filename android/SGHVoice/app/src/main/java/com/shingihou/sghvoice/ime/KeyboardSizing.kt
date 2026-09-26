package com.shingihou.sghvoice.ime

/** One shared footprint for every mode, anchored to the original 372dp Zhuyin layout. */
object KeyboardSizing {
    const val DEFAULT_PERCENT = 100
    const val MIN_PERCENT = 90
    const val MAX_PERCENT = 125
    const val BASE_HEIGHT_DP = 372

    fun normalize(percent: Int): Int = percent.coerceIn(MIN_PERCENT, MAX_PERCENT)
    fun heightDp(percent: Int): Int = BASE_HEIGHT_DP * normalize(percent) / 100
}
