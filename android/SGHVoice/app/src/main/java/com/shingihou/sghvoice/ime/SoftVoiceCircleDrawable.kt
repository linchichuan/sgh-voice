package com.shingihou.sghvoice.ime

import android.graphics.Canvas
import android.graphics.ColorFilter
import android.graphics.Paint
import android.graphics.PixelFormat
import android.graphics.RadialGradient
import android.graphics.Rect
import android.graphics.Shader
import android.graphics.drawable.Drawable
import androidx.core.graphics.ColorUtils

/** A borderless pool of color, fading to transparent without an outer card or shadow. */
class SoftVoiceCircleDrawable(private val color: Int) : Drawable() {
    private val paint = Paint(Paint.ANTI_ALIAS_FLAG)
    private var radius = 0f

    override fun onBoundsChange(bounds: Rect) {
        radius = minOf(bounds.width(), bounds.height()) / 2f
        paint.shader = if (radius > 0f) RadialGradient(
            bounds.exactCenterX(), bounds.exactCenterY(), radius,
            intArrayOf(color, ColorUtils.setAlphaComponent(color, 230),
                ColorUtils.setAlphaComponent(color, 100), ColorUtils.setAlphaComponent(color, 0)),
            floatArrayOf(0f, 0.48f, 0.78f, 1f), Shader.TileMode.CLAMP
        ) else null
    }

    override fun draw(canvas: Canvas) {
        if (radius > 0f) canvas.drawCircle(bounds.exactCenterX(), bounds.exactCenterY(), radius, paint)
    }

    override fun setAlpha(alpha: Int) { paint.alpha = alpha; invalidateSelf() }
    override fun setColorFilter(colorFilter: ColorFilter?) { paint.colorFilter = colorFilter; invalidateSelf() }
    @Suppress("DEPRECATION")
    override fun getOpacity(): Int = PixelFormat.TRANSLUCENT
}
