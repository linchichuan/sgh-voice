package com.shingihou.sghvoice.ime.japanese

import kotlin.math.abs

enum class KanaFlickDirection { CENTER, LEFT, UP, RIGHT, DOWN }

/**
 * One pointer-down/up pair produces at most one direction. This has no Android
 * dependencies so cancellation, thresholds and repeated taps remain testable.
 * Selection follows the current displacement, allowing corrections before up.
 */
class KanaFlickGesture(private val touchSlop: Float) {
    init {
        require(touchSlop.isFinite() && touchSlop > 0f)
    }

    var activePointerId: Int? = null
        private set
    var direction: KanaFlickDirection? = null
        private set
    val isActive: Boolean get() = activePointerId != null

    private var originX = 0f
    private var originY = 0f

    fun begin(pointerId: Int, x: Float, y: Float): Boolean {
        if (isActive || pointerId < 0 || !x.isFinite() || !y.isFinite()) {
            cancel()
            return false
        }
        activePointerId = pointerId
        originX = x
        originY = y
        direction = KanaFlickDirection.CENTER
        return true
    }

    fun move(pointerId: Int, x: Float, y: Float): KanaFlickDirection? {
        if (activePointerId != pointerId || !x.isFinite() || !y.isFinite()) {
            cancel()
            return null
        }
        val dx = x - originX
        val dy = y - originY
        direction = when {
            dx * dx + dy * dy <= touchSlop * touchSlop -> KanaFlickDirection.CENTER
            abs(dx) > abs(dy) -> if (dx < 0f) KanaFlickDirection.LEFT else KanaFlickDirection.RIGHT
            dy < 0f -> KanaFlickDirection.UP
            else -> KanaFlickDirection.DOWN
        }
        return direction
    }

    fun end(pointerId: Int, x: Float, y: Float): KanaFlickDirection? {
        val selected = move(pointerId, x, y)
        cancel()
        return selected
    }

    /** Fail closed for multi-touch rather than transferring the gesture. */
    fun secondaryPointerDown() = cancel()

    fun cancel() {
        activePointerId = null
        direction = null
    }
}
