package com.shingihou.sghvoice.ime

import android.animation.ValueAnimator
import android.content.Context
import android.graphics.Canvas
import android.graphics.Paint
import android.graphics.RadialGradient
import android.graphics.Shader
import android.os.SystemClock
import android.util.AttributeSet
import android.view.View
import androidx.core.content.ContextCompat
import androidx.core.graphics.ColorUtils
import com.shingihou.sghvoice.R
import kotlin.math.exp
import kotlin.math.min

/**
 * A quiet microphone halo driven only by live PCM levels. The legacy view name
 * and API remain stable for the IME. Silence is a still circle, never a pulse.
 */
class AudioWaveformView @JvmOverloads constructor(
    context: Context,
    attrs: AttributeSet? = null,
    defStyleAttr: Int = 0
) : View(context, attrs, defStyleAttr) {

    private val density = resources.displayMetrics.density
    private val activeColor = ContextCompat.getColor(context, R.color.waveform_active)
    private val baselineColor = ContextCompat.getColor(context, R.color.waveform_baseline)
    private val haloPaint = Paint(Paint.ANTI_ALIAS_FLAG)
    private val corePaint = Paint(Paint.ANTI_ALIAS_FLAG)
    private val ringPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        style = Paint.Style.STROKE
        strokeWidth = density
    }
    private val microphone = ContextCompat.getDrawable(context, R.drawable.ic_mic)?.mutate()
        ?.apply { setTint(activeColor) }
    private val envelope = AudioHaloEnvelope()
    private var recordingActive = false
    private var reducedMotion = !ValueAnimator.areAnimatorsEnabled()
    private var maximumRadius = 0f

    // A single bounded reset also handles a stalled microphone callback. It
    // does not reschedule itself or keep an animation running during silence.
    private val clearStaleLevel = Runnable {
        envelope.reset()
        invalidate()
    }

    fun setRecordingActive(active: Boolean) {
        if (!active || !recordingActive) {
            removeCallbacks(clearStaleLevel)
            envelope.reset()
        }
        recordingActive = active
        visibility = if (active) VISIBLE else INVISIBLE
        invalidate()
    }

    fun setAudioLevel(level: Float) {
        if (!recordingActive) return
        reducedMotion = !ValueAnimator.areAnimatorsEnabled()
        envelope.update(level, SystemClock.uptimeMillis())
        removeCallbacks(clearStaleLevel)
        if (envelope.level > 0f) postDelayed(clearStaleLevel, 250L)
        postInvalidateOnAnimation()
    }

    override fun onSizeChanged(w: Int, h: Int, oldw: Int, oldh: Int) {
        super.onSizeChanged(w, h, oldw, oldh)
        maximumRadius = (min(w, h) / 2f - 2f * density).coerceAtLeast(0f)
        if (maximumRadius > 0f) {
            haloPaint.shader = RadialGradient(
                0f,
                0f,
                maximumRadius,
                intArrayOf(
                    ColorUtils.setAlphaComponent(activeColor, 40),
                    ColorUtils.setAlphaComponent(activeColor, 18),
                    ColorUtils.setAlphaComponent(activeColor, 0)
                ),
                floatArrayOf(0f, 0.66f, 1f),
                Shader.TileMode.CLAMP
            )
        }
    }

    override fun onDraw(canvas: Canvas) {
        super.onDraw(canvas)
        if (maximumRadius <= 0f) return

        val level = envelope.level
        // Keep the microphone fixed. Even loud speech only grows the ring by
        // 12%; with Android animations disabled only color/opacity changes.
        val movement = if (reducedMotion) 0f else level
        val coreRadius = maximumRadius * (0.63f + 0.075f * movement)
        val ringRadius = maximumRadius * (0.76f + 0.09f * movement)
        corePaint.color = ColorUtils.setAlphaComponent(activeColor, (18 + 24 * level).toInt())
        ringPaint.color = ColorUtils.blendARGB(baselineColor, activeColor, 0.45f * level)
        haloPaint.alpha = (90 + 165 * level).toInt()

        val checkpoint = canvas.save()
        canvas.translate(width / 2f, height / 2f)
        canvas.drawCircle(0f, 0f, maximumRadius, haloPaint)
        canvas.drawCircle(0f, 0f, coreRadius, corePaint)
        canvas.drawCircle(0f, 0f, ringRadius, ringPaint)
        val iconHalfSize = min(9f * density, maximumRadius * 0.38f).toInt()
        microphone?.setBounds(-iconHalfSize, -iconHalfSize, iconHalfSize, iconHalfSize)
        microphone?.draw(canvas)
        canvas.restoreToCount(checkpoint)
    }

    override fun onDetachedFromWindow() {
        removeCallbacks(clearStaleLevel)
        envelope.reset()
        super.onDetachedFromWindow()
    }
}

/** Smooth changes between real samples; never manufactures a sample or a beat. */
internal class AudioHaloEnvelope {
    var level = 0f
        private set
    private var lastSampleTime: Long? = null

    fun update(input: Float, timestampMillis: Long): Float {
        val sample = if (input.isFinite()) input.coerceIn(0f, 1f) else 0f
        if (sample <= 0.015f) {
            reset()
            return level
        }
        val elapsed = lastSampleTime?.let { (timestampMillis - it).coerceIn(0L, 250L) } ?: 50L
        lastSampleTime = timestampMillis
        val timeConstant = if (sample > level) 140f else 220f
        val fraction = 1f - exp(-elapsed / timeConstant)
        level += (sample - level) * fraction
        return level
    }

    fun reset() {
        level = 0f
        lastSampleTime = null
    }
}
