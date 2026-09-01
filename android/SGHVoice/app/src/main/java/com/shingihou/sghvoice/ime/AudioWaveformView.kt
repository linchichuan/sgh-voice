package com.shingihou.sghvoice.ime

import android.content.Context
import android.graphics.Canvas
import android.graphics.Paint
import android.util.AttributeSet
import android.view.View
import androidx.core.content.ContextCompat
import com.shingihou.sghvoice.R

/**
 * A data-driven microphone waveform. It never loops on its own: PCM levels
 * append bars while speech arrives, and silence renders as a flat center line.
 */
class AudioWaveformView @JvmOverloads constructor(
    context: Context,
    attrs: AttributeSet? = null,
    defStyleAttr: Int = 0
) : View(context, attrs, defStyleAttr) {

    companion object {
        private const val BAR_COUNT = 25
        private const val MIN_VISIBLE_LEVEL = 0.015f
    }

    private val samples = FloatArray(BAR_COUNT)
    private val density = resources.displayMetrics.density
    private val baselinePaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        color = ContextCompat.getColor(context, R.color.waveform_baseline)
        strokeWidth = density
    }
    private val barPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        color = ContextCompat.getColor(context, R.color.waveform_active)
    }
    private var recordingActive = false

    fun setRecordingActive(active: Boolean) {
        recordingActive = active
        if (!active) samples.fill(0f)
        visibility = if (active) VISIBLE else INVISIBLE
        invalidate()
    }

    fun setAudioLevel(level: Float) {
        if (!recordingActive) return
        samples.copyInto(samples, destinationOffset = 0, startIndex = 1)
        samples[samples.lastIndex] = level.coerceIn(0f, 1f)
        postInvalidateOnAnimation()
    }

    override fun onDraw(canvas: Canvas) {
        super.onDraw(canvas)
        val centerY = height / 2f
        val horizontalPadding = 4f * density
        canvas.drawLine(
            horizontalPadding,
            centerY,
            width - horizontalPadding,
            centerY,
            baselinePaint
        )

        val availableWidth = (width - horizontalPadding * 2).coerceAtLeast(1f)
        val slotWidth = availableWidth / BAR_COUNT
        val barWidth = (slotWidth * 0.46f).coerceAtLeast(1.5f * density)
        val maxHalfHeight = (height / 2f - 2f * density).coerceAtLeast(1f)
        val radius = barWidth / 2f

        samples.forEachIndexed { index, sample ->
            if (sample <= MIN_VISIBLE_LEVEL) return@forEachIndexed
            val envelope = 0.62f + 0.38f * kotlin.math.abs(
                kotlin.math.sin(((index + 1) * 0.79f).toDouble()).toFloat()
            )
            val halfHeight = (sample * envelope * maxHalfHeight)
                .coerceAtLeast(1.5f * density)
            val centerX = horizontalPadding + slotWidth * (index + 0.5f)
            canvas.drawRoundRect(
                centerX - barWidth / 2f,
                centerY - halfHeight,
                centerX + barWidth / 2f,
                centerY + halfHeight,
                radius,
                radius,
                barPaint
            )
        }
    }
}
