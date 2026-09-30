package com.shingihou.sghvoice.ime

import android.graphics.Canvas
import android.graphics.ColorFilter
import android.graphics.Matrix
import android.graphics.Paint
import android.graphics.PixelFormat
import android.graphics.RadialGradient
import android.graphics.Rect
import android.graphics.Shader
import android.graphics.drawable.Drawable
import androidx.core.graphics.ColorUtils

/** A wide borderless pool, fading from its centre to every edge of the oval. */
class SoftVoiceCircleDrawable(private val color: Int) : Drawable() {
    private val paint = Paint(Paint.ANTI_ALIAS_FLAG)
    private val shaderMatrix = Matrix()

    override fun onBoundsChange(bounds: Rect) {
        paint.shader = if (bounds.width() > 0 && bounds.height() > 0) RadialGradient(
            0f, 0f, 1f,
            intArrayOf(color, ColorUtils.setAlphaComponent(color, 230),
                ColorUtils.setAlphaComponent(color, 100), ColorUtils.setAlphaComponent(color, 0)),
            floatArrayOf(0f, 0.48f, 0.78f, 1f), Shader.TileMode.CLAMP
        ).apply {
            shaderMatrix.setScale(bounds.width() / 2f, bounds.height() / 2f)
            shaderMatrix.postTranslate(bounds.exactCenterX(), bounds.exactCenterY())
            setLocalMatrix(shaderMatrix)
        } else null
    }

    override fun draw(canvas: Canvas) {
        if (!bounds.isEmpty) canvas.drawOval(bounds.left.toFloat(), bounds.top.toFloat(),
            bounds.right.toFloat(), bounds.bottom.toFloat(), paint)
    }

    override fun setAlpha(alpha: Int) { paint.alpha = alpha; invalidateSelf() }
    override fun setColorFilter(colorFilter: ColorFilter?) { paint.colorFilter = colorFilter; invalidateSelf() }
    @Suppress("DEPRECATION")
    override fun getOpacity(): Int = PixelFormat.TRANSLUCENT
}
