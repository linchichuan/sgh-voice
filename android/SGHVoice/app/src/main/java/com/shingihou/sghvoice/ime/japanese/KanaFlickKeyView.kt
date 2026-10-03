package com.shingihou.sghvoice.ime.japanese

import android.content.Context
import android.graphics.Canvas
import android.graphics.Paint
import android.os.Bundle
import android.util.AttributeSet
import android.view.MotionEvent
import android.view.View
import android.view.ViewConfiguration
import android.view.accessibility.AccessibilityEvent
import android.view.accessibility.AccessibilityNodeInfo
import android.widget.Button
import androidx.appcompat.widget.AppCompatTextView
import kotlin.math.min

/** A styled TextView key whose touch gesture commits only when released. */
class KanaFlickKeyView @JvmOverloads constructor(
    context: Context,
    attrs: AttributeSet? = null,
    defStyleAttr: Int = android.R.attr.textViewStyle
) : AppCompatTextView(context, attrs, defStyleAttr) {
    private val gesture = KanaFlickGesture(ViewConfiguration.get(context).scaledTouchSlop.toFloat())
    private val hintPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply { textAlign = Paint.Align.CENTER }
    private var group: String? = null
    private var onKana: ((String) -> Unit)? = null
    private var onCenterTap: (() -> Unit)? = null

    /** Call after generic key styling/listeners; this replaces the tap-only listener. */
    fun bindFlick(group: String, onKana: (String) -> Unit, onCenterTap: (() -> Unit)? = null) {
        cancelGesture()
        this.group = group
        this.onKana = onKana
        this.onCenterTap = onCenterTap
        val center = Kana12Key.kanaForDirection(group, KanaFlickDirection.CENTER)
        text = center.orEmpty()
        contentDescription = center.orEmpty()
        isClickable = center != null
        isFocusable = center != null
        setOnTouchListener(null)
        setOnLongClickListener(null)
        isLongClickable = false
        setOnClickListener {
            if (isEnabled) {
                this.onCenterTap?.invoke() ?: emitKana(KanaFlickDirection.CENTER)
            }
        }
    }

    override fun onTouchEvent(event: MotionEvent): Boolean {
        if (group == null) return super.onTouchEvent(event)
        if (!isEnabled) {
            cancelGesture()
            return false
        }
        when (event.actionMasked) {
            MotionEvent.ACTION_DOWN -> {
                if (event.pointerCount != 1 ||
                    !gesture.begin(event.getPointerId(0), event.x, event.y)
                ) {
                    cancelGesture()
                    return true
                }
                parent?.requestDisallowInterceptTouchEvent(true)
                isPressed = true
                invalidate()
            }
            MotionEvent.ACTION_MOVE -> {
                val pointerIndex = gesture.activePointerId?.let(event::findPointerIndex) ?: -1
                if (event.pointerCount != 1 || pointerIndex < 0) {
                    cancelGesture()
                } else {
                    gesture.move(event.getPointerId(pointerIndex), event.getX(pointerIndex), event.getY(pointerIndex))
                    invalidate()
                }
            }
            MotionEvent.ACTION_UP -> {
                val pointerIndex = gesture.activePointerId?.let(event::findPointerIndex) ?: -1
                val selected = if (event.pointerCount == 1 && pointerIndex >= 0) {
                    gesture.end(event.getPointerId(pointerIndex), event.getX(pointerIndex), event.getY(pointerIndex))
                } else {
                    null
                }
                cancelGesture()
                if (selected == KanaFlickDirection.CENTER) {
                    performClick()
                } else if (selected != null && emitKana(selected)) {
                    sendAccessibilityEvent(AccessibilityEvent.TYPE_VIEW_CLICKED)
                }
            }
            MotionEvent.ACTION_POINTER_DOWN -> {
                gesture.secondaryPointerDown()
                cancelGesture()
            }
            MotionEvent.ACTION_POINTER_UP, MotionEvent.ACTION_CANCEL, MotionEvent.ACTION_OUTSIDE -> cancelGesture()
        }
        return true
    }

    /** TalkBack and hardware-key activation use the same centre tap as touch. */
    override fun performClick(): Boolean {
        if (!isEnabled) return false
        cancelGesture()
        return super.performClick()
    }

    override fun onInitializeAccessibilityNodeInfo(info: AccessibilityNodeInfo) {
        super.onInitializeAccessibilityNodeInfo(info)
        info.className = Button::class.java.name
        val currentGroup = group ?: return
        if (!isEnabled) return
        accessibilityDirections.forEach { (actionId, direction, arrow) ->
            Kana12Key.kanaForDirection(currentGroup, direction)?.let { kana ->
                info.addAction(AccessibilityNodeInfo.AccessibilityAction(actionId, "$arrow $kana"))
            }
        }
    }

    override fun performAccessibilityAction(action: Int, arguments: Bundle?): Boolean {
        val direction = accessibilityDirections.firstOrNull { it.actionId == action }?.direction
            ?: return super.performAccessibilityAction(action, arguments)
        if (!isEnabled) return false
        cancelGesture()
        return emitKana(direction).also { emitted ->
            if (emitted) sendAccessibilityEvent(AccessibilityEvent.TYPE_VIEW_CLICKED)
        }
    }

    /** No animation or popup delay for an interaction repeated on every key. */
    override fun onDraw(canvas: Canvas) {
        val currentGroup = group
        val selected = gesture.direction
        if (currentGroup == null || !gesture.isActive || selected == null) {
            super.onDraw(canvas)
            return
        }
        val selectedKana = Kana12Key.kanaForDirection(currentGroup, selected)
        hintPaint.typeface = typeface
        hintPaint.color = currentTextColor
        hintPaint.alpha = 255
        hintPaint.textSize = min(textSize, height * 0.38f)
        // An unassigned direction visibly clears the centre and commits nothing.
        selectedKana?.let { drawCentered(canvas, it, width * 0.5f, height * 0.5f) }

        hintPaint.textSize = min(textSize * 0.58f, height * 0.20f)
        accessibilityDirections.forEach { (_, direction, _) ->
            val kana = Kana12Key.kanaForDirection(currentGroup, direction) ?: return@forEach
            val (x, y) = when (direction) {
                KanaFlickDirection.LEFT -> width * 0.16f to height * 0.5f
                KanaFlickDirection.UP -> width * 0.5f to height * 0.17f
                KanaFlickDirection.RIGHT -> width * 0.84f to height * 0.5f
                KanaFlickDirection.DOWN -> width * 0.5f to height * 0.83f
                KanaFlickDirection.CENTER -> return@forEach
            }
            hintPaint.alpha = if (selected == direction) 255 else 170
            hintPaint.isFakeBoldText = selected == direction
            drawCentered(canvas, kana, x, y)
        }
        hintPaint.isFakeBoldText = false
    }

    override fun onDetachedFromWindow() {
        cancelGesture()
        super.onDetachedFromWindow()
    }

    override fun onWindowFocusChanged(hasWindowFocus: Boolean) {
        if (!hasWindowFocus) cancelGesture()
        super.onWindowFocusChanged(hasWindowFocus)
    }

    private fun drawCentered(canvas: Canvas, kana: String, x: Float, y: Float) {
        val baseline = y - (hintPaint.ascent() + hintPaint.descent()) / 2f
        canvas.drawText(kana, x, baseline, hintPaint)
    }

    private fun emitKana(direction: KanaFlickDirection): Boolean {
        val kana = group?.let { Kana12Key.kanaForDirection(it, direction) } ?: return false
        val callback = onKana ?: return false
        callback(kana)
        return true
    }

    private fun cancelGesture() {
        gesture.cancel()
        isPressed = false
        parent?.requestDisallowInterceptTouchEvent(false)
        invalidate()
    }

    private data class DirectionAction(val actionId: Int, val direction: KanaFlickDirection, val arrow: String)

    private companion object {
        // Raw generateViewId() values can collide with legacy action constants
        // (1 = focus, 2 = clear focus, 4 = select). Reserve a non-framework prefix.
        fun newActionId(): Int = 0x02000000 or View.generateViewId()

        val accessibilityDirections = listOf(
            DirectionAction(newActionId(), KanaFlickDirection.LEFT, "←"),
            DirectionAction(newActionId(), KanaFlickDirection.UP, "↑"),
            DirectionAction(newActionId(), KanaFlickDirection.RIGHT, "→"),
            DirectionAction(newActionId(), KanaFlickDirection.DOWN, "↓")
        )
    }
}
