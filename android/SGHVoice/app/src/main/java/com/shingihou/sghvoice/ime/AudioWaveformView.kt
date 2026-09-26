package com.shingihou.sghvoice.ime

import android.animation.ValueAnimator
import android.content.Context
import android.graphics.Canvas
import android.graphics.Paint
import android.graphics.Path
import android.os.SystemClock
import android.util.AttributeSet
import android.view.View
import androidx.core.content.ContextCompat
import androidx.core.graphics.ColorUtils
import com.shingihou.sghvoice.R
import kotlin.math.PI
import kotlin.math.exp
import kotlin.math.sin

/**
 * Gentle, transparent voice contours inside the single microphone control.
 * Only live PCM callbacks advance them; silence is a still horizontal line.
 * The parent owns the circular surface and the caption below these contours.
 */
class AudioWaveformView @JvmOverloads constructor(
    context: Context,
    attrs: AttributeSet? = null,
    defStyleAttr: Int = 0
) : View(context, attrs, defStyleAttr) {

    private val density = resources.displayMetrics.density
    private var activeColor = ContextCompat.getColor(context, R.color.waveform_active)
    private var baselineColor = ContextCompat.getColor(context, R.color.waveform_baseline)
    private val wavePaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        style = Paint.Style.STROKE
        strokeCap = Paint.Cap.ROUND
        strokeJoin = Paint.Join.ROUND
    }
    private val wavePath = Path()
    private val envelope = AudioHaloEnvelope()
    private var recordingActive = false
    private var reducedMotion = !ValueAnimator.areAnimatorsEnabled()

    // A single bounded reset also handles a stalled microphone callback. It
    // does not reschedule itself or keep an animation running during silence.
    private val clearStaleLevel = Runnable {
        envelope.reset()
        invalidate()
    }

    fun setPaletteColors(active: Int, baseline: Int) {
        activeColor = active
        baselineColor = baseline
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

    override fun onDraw(canvas: Canvas) {
        super.onDraw(canvas)
        if (!recordingActive || width <= 0 || height <= 0) return

        val level = envelope.level
        val startX = width * 0.18f
        val endX = width * 0.82f
        val centerY = height * 0.42f
        wavePaint.color = ColorUtils.blendARGB(baselineColor, activeColor, 0.4f + 0.6f * level)
        if (level <= 0.015f || reducedMotion) {
            // No displacement in silence or Android's reduced-motion mode.
            // Audible samples still darken this line when motion is disabled.
            wavePaint.alpha = 220
            wavePaint.strokeWidth = 2f * density
            canvas.drawLine(startX, centerY, endX, centerY, wavePaint)
            return
        }

        for (line in 2 downTo 0) {
            wavePaint.alpha = when (line) {
                0 -> 245
                1 -> 145
                else -> 85
            }
            wavePaint.strokeWidth = (if (line == 0) 2.2f else 1.6f) * density
            wavePath.rewind()
            for (point in 0..48) {
                val position = point / 48f
                val x = startX + (endX - startX) * position
                val y = centerY + height * GentleWaveGeometry.offsetAt(
                    position, line, level, envelope.phase, reducedMotion
                )
                if (point == 0) wavePath.moveTo(x, y) else wavePath.lineTo(x, y)
            }
            canvas.drawPath(wavePath, wavePaint)
        }
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
    var phase = 0f
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
        // A slow contour shift exists only while genuine audible samples arrive.
        phase = (phase + elapsed * 0.0022f) % (2f * PI.toFloat())
        return level
    }

    fun reset() {
        level = 0f
        phase = 0f
        lastSampleTime = null
    }
}

/** Normalized vertical displacement within the microphone control. */
internal object GentleWaveGeometry {
    fun offsetAt(position: Float, line: Int, level: Float, phase: Float, reducedMotion: Boolean): Float {
        if (reducedMotion || !level.isFinite() || level <= 0.015f ||
            !position.isFinite() || position <= 0f || position >= 1f || !phase.isFinite()
        ) return 0f
        val strength = when (line) {
            0 -> 1f
            1 -> 0.7f
            else -> 0.45f
        }
        val taper = sin(PI * position).toFloat()
        return 0.052f * level.coerceAtMost(1f) * strength * taper * taper *
            sin(2 * PI * 1.35 * position + phase + line * 0.7).toFloat()
    }
}
