package com.shingihou.sghvoice.ime.japanese

import android.graphics.Rect
import android.view.MotionEvent
import android.view.View
import android.view.ViewGroup
import android.view.accessibility.AccessibilityNodeInfo
import android.widget.FrameLayout
import com.shingihou.sghvoice.ime.KeyboardView
import com.shingihou.sghvoice.ime.manual.KeyAction
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.mockito.kotlin.any
import org.mockito.kotlin.doAnswer
import org.mockito.kotlin.mock
import org.mockito.kotlin.whenever
import org.robolectric.RobolectricTestRunner
import org.robolectric.RuntimeEnvironment
import org.robolectric.annotation.Config

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35], qualifiers = "w393dp-h852dp-xxhdpi")
class KanaFlickKeyViewTest {
    private val emitted = mutableListOf<String>()
    private var eventTime = 100L

    private fun key(group: String = "na") = KanaFlickKeyView(RuntimeEnvironment.getApplication()).apply {
        layout(0, 0, 180, 96)
        bindFlick(group, emitted::add)
    }

    private fun touch(view: KanaFlickKeyView, action: Int, x: Float = 90f, y: Float = 48f) {
        val event = MotionEvent.obtain(100L, eventTime++, action, x, y, 0)
        try {
            view.onTouchEvent(event)
        } finally {
            event.recycle()
        }
    }

    private fun touchTwo(view: KanaFlickKeyView, action: Int) {
        val properties = Array(2) { index -> MotionEvent.PointerProperties().apply { id = index } }
        val coordinates = Array(2) { index ->
            MotionEvent.PointerCoords().apply {
                x = 90f + index * 10
                y = 48f
                pressure = 1f
                size = 1f
            }
        }
        val event = MotionEvent.obtain(100L, eventTime++, action, 2, properties, coordinates, 0, 0, 1f, 1f, 0, 0, 0, 0)
        try {
            view.onTouchEvent(event)
        } finally {
            event.recycle()
        }
    }

    @Test
    fun `one tap emits once on release and repeated taps do not cycle`() {
        val view = key()
        repeat(3) {
            touch(view, MotionEvent.ACTION_DOWN)
            assertEquals(it, emitted.size)
            touch(view, MotionEvent.ACTION_UP)
        }
        assertEquals(listOf("な", "な", "な"), emitted)
        touch(view, MotionEvent.ACTION_UP)
        assertEquals(3, emitted.size)
    }

    @Test
    fun `release chooses all four flick directions`() {
        val view = key()
        listOf(0f to 48f, 90f to -48f, 180f to 48f, 90f to 144f).forEach { (x, y) ->
            touch(view, MotionEvent.ACTION_DOWN)
            touch(view, MotionEvent.ACTION_MOVE, x, y)
            touch(view, MotionEvent.ACTION_UP, x, y)
        }
        assertEquals(listOf("に", "ぬ", "ね", "の"), emitted)
    }

    @Test
    fun `a flick may return to center before release`() {
        val view = key()
        touch(view, MotionEvent.ACTION_DOWN)
        touch(view, MotionEvent.ACTION_MOVE, 0f, 48f)
        touch(view, MotionEvent.ACTION_UP)
        assertEquals(listOf("な"), emitted)
    }

    @Test
    fun `cancelled or focus lost touches emit nothing`() {
        val view = key()
        touch(view, MotionEvent.ACTION_DOWN)
        touch(view, MotionEvent.ACTION_CANCEL)
        touch(view, MotionEvent.ACTION_UP)
        touch(view, MotionEvent.ACTION_DOWN)
        view.onWindowFocusChanged(false)
        touch(view, MotionEvent.ACTION_UP)
        assertTrue(emitted.isEmpty())
        assertFalse(view.isPressed)
    }

    @Test
    fun `multi touch cannot emit either finger`() {
        val view = key()
        touch(view, MotionEvent.ACTION_DOWN)
        touchTwo(view, MotionEvent.ACTION_POINTER_DOWN or (1 shl MotionEvent.ACTION_POINTER_INDEX_SHIFT))
        touchTwo(view, MotionEvent.ACTION_POINTER_UP or (1 shl MotionEvent.ACTION_POINTER_INDEX_SHIFT))
        touch(view, MotionEvent.ACTION_UP)
        assertTrue(emitted.isEmpty())
        assertFalse(view.isPressed)
    }

    @Test
    fun `an unavailable flick direction emits nothing`() {
        val view = key("ya")
        touch(view, MotionEvent.ACTION_DOWN)
        touch(view, MotionEvent.ACTION_UP, 0f, 48f)
        assertTrue(emitted.isEmpty())
        touch(view, MotionEvent.ACTION_DOWN)
        touch(view, MotionEvent.ACTION_UP, 90f, -48f)
        assertEquals(listOf("ゆ"), emitted)
    }

    @Test
    fun `TalkBack click and custom direction actions use distinct callbacks`() {
        val view = key()
        val node = AccessibilityNodeInfo.obtain()
        view.onInitializeAccessibilityNodeInfo(node)
        val leftAction = node.actionList.first { it.label == "← に" }
        val upAction = node.actionList.first { it.label == "↑ ぬ" }
        assertTrue(leftAction.id > 0x01000000)
        assertTrue(view.performAccessibilityAction(AccessibilityNodeInfo.ACTION_CLICK, null))
        assertTrue(view.performAccessibilityAction(leftAction.id, null))
        assertTrue(view.performAccessibilityAction(upAction.id, null))
        assertEquals(listOf("な", "に", "ぬ"), emitted)
        node.recycle()
    }

    @Test
    fun `unassigned directions have no accessibility action`() {
        val view = key("ya")
        val node = AccessibilityNodeInfo.obtain()
        view.onInitializeAccessibilityNodeInfo(node)
        val labels = node.actionList.mapNotNull { it.label?.toString() }
        assertTrue(labels.containsAll(listOf("↑ ゆ", "↓ よ")))
        assertFalse(labels.any { it.startsWith("←") || it.startsWith("→") })
        node.recycle()
    }

    @Test
    fun `accessibility click cancels an in progress touch instead of doubling output`() {
        val view = key()
        touch(view, MotionEvent.ACTION_DOWN)
        view.performClick()
        touch(view, MotionEvent.ACTION_UP)
        assertEquals(listOf("な"), emitted)
    }

    @Test
    fun `binding replaces a preexisting tap and long press listener`() {
        val view = key()
        view.setOnClickListener { emitted.add("old tap") }
        view.setOnLongClickListener { emitted.add("old long press"); true }
        view.bindFlick("a", emitted::add)
        assertFalse(view.isLongClickable)
        view.performClick()
        assertEquals(listOf("あ"), emitted)
    }

    @Test
    fun `disabled key does not emit`() {
        val view = key()
        touch(view, MotionEvent.ACTION_DOWN)
        view.isEnabled = false
        touch(view, MotionEvent.ACTION_UP)
        assertFalse(view.performClick())
        assertTrue(emitted.isEmpty())
    }

    @Test
    fun `parent cannot intercept the flick but is released on cancellation`() {
        val view = key()
        val requests = mutableListOf<Boolean>()
        val parent = object : FrameLayout(RuntimeEnvironment.getApplication()) {
            override fun requestDisallowInterceptTouchEvent(disallowIntercept: Boolean) {
                requests.add(disallowIntercept)
                super.requestDisallowInterceptTouchEvent(disallowIntercept)
            }
        }
        parent.addView(view)
        touch(view, MotionEvent.ACTION_DOWN)
        assertEquals(true, requests.last())
        touch(view, MotionEvent.ACTION_CANCEL)
        assertEquals(false, requests.last())
    }

    private fun productionKeyboard(actions: MutableList<KeyAction>): KeyboardView {
        val listener = mock<KeyboardView.KeyboardActionListener>()
        doAnswer { invocation ->
            actions.add(invocation.getArgument<KeyAction>(0))
            null
        }.whenever(listener).onKeyAction(any())
        return KeyboardView(RuntimeEnvironment.getApplication()).apply {
            setKeyboardActionListener(listener)
            setInputMode(KeyboardView.InputMode.JAPANESE)
            setJapaneseInputStyle(JapaneseInputStyle.KANA_12_KEY)
            val density = resources.displayMetrics.density
            measure(
                View.MeasureSpec.makeMeasureSpec((393 * density).toInt(), View.MeasureSpec.EXACTLY),
                View.MeasureSpec.makeMeasureSpec((852 * density).toInt(), View.MeasureSpec.AT_MOST)
            )
            layout(0, 0, measuredWidth, measuredHeight)
        }
    }

    private fun keyBounds(keyboard: KeyboardView, group: String): Rect {
        val key = requireNotNull(keyboard.findViewWithTag<View>("japanese_kana_$group"))
        assertTrue("Production key $group must use the flick view", key is KanaFlickKeyView)
        return Rect().also { bounds ->
            key.getDrawingRect(bounds)
            keyboard.offsetDescendantRectToMyCoords(key, bounds)
        }
    }

    private fun dispatch(keyboard: KeyboardView, action: Int, x: Float, y: Float) {
        val event = MotionEvent.obtain(100L, eventTime++, action, x, y, 0)
        try {
            keyboard.dispatchTouchEvent(event)
        } finally {
            event.recycle()
        }
    }

    private fun dispatchPair(keyboard: KeyboardView, action: Int, first: Rect, second: Rect) {
        val properties = Array(2) { index -> MotionEvent.PointerProperties().apply { id = index } }
        val coordinates = arrayOf(first, second).map { bounds ->
            MotionEvent.PointerCoords().apply {
                x = bounds.exactCenterX()
                y = bounds.exactCenterY()
                pressure = 1f
                size = 1f
            }
        }.toTypedArray()
        val event = MotionEvent.obtain(100L, eventTime++, action, 2, properties, coordinates, 0, 0, 1f, 1f, 0, 0, 0, 0)
        try {
            keyboard.dispatchTouchEvent(event)
        } finally {
            event.recycle()
        }
    }

    @Test
    fun `production keyboard routes rapid taps to independent insert callbacks`() {
        val actions = mutableListOf<KeyAction>()
        val keyboard = productionKeyboard(actions)
        val bounds = keyBounds(keyboard, "na")
        repeat(3) {
            dispatch(keyboard, MotionEvent.ACTION_DOWN, bounds.exactCenterX(), bounds.exactCenterY())
            dispatch(keyboard, MotionEvent.ACTION_UP, bounds.exactCenterX(), bounds.exactCenterY())
        }
        assertEquals(List(3) { KeyAction.InsertText("な") }, actions)
        val composer = JapaneseComposer().apply { setInputStyle(JapaneseInputStyle.KANA_12_KEY) }
        actions.forEach { assertTrue(composer.appendKana((it as KeyAction.InsertText).text)) }
        assertEquals("ななな", composer.composition)
    }

    @Test
    fun `production keyboard preserves the directional mapping and empty slots`() {
        val actions = mutableListOf<KeyAction>()
        val keyboard = productionKeyboard(actions)
        val cases = listOf(
            Triple("na", -100f to 0f, "に"), Triple("na", 0f to -100f, "ぬ"),
            Triple("na", 100f to 0f, "ね"), Triple("na", 0f to 100f, "の"),
            Triple("ya", 0f to -100f, "ゆ"), Triple("ya", 0f to 100f, "よ"),
            Triple("wa", -100f to 0f, "を"), Triple("wa", 0f to -100f, "ん"),
            Triple("wa", 100f to 0f, "ー")
        )
        cases.forEach { (group, delta, _) ->
            val bounds = keyBounds(keyboard, group)
            dispatch(keyboard, MotionEvent.ACTION_DOWN, bounds.exactCenterX(), bounds.exactCenterY())
            dispatch(keyboard, MotionEvent.ACTION_UP, bounds.exactCenterX() + delta.first, bounds.exactCenterY() + delta.second)
        }
        assertEquals(cases.map { KeyAction.InsertText(it.third) }, actions)
        listOf("ya" to (-100f to 0f), "ya" to (100f to 0f), "wa" to (0f to 100f)).forEach { (group, delta) ->
            val bounds = keyBounds(keyboard, group)
            dispatch(keyboard, MotionEvent.ACTION_DOWN, bounds.exactCenterX(), bounds.exactCenterY())
            dispatch(keyboard, MotionEvent.ACTION_UP, bounds.exactCenterX() + delta.first, bounds.exactCenterY() + delta.second)
        }
        assertEquals("Empty directions must not fall back to a tap", cases.size, actions.size)
    }

    @Test
    fun `production keyboard disables touch splitting along every flick key ancestor`() {
        val keyboard = productionKeyboard(mutableListOf())
        Kana12Key.groups.keys.forEach { group ->
            var ancestor = keyboard.findViewWithTag<View>("japanese_kana_$group").parent
            while (ancestor is ViewGroup) {
                assertFalse("$group ancestor ${ancestor.javaClass.simpleName} must not split touch events", ancestor.isMotionEventSplittingEnabled)
                if (ancestor === keyboard) break
                ancestor = ancestor.parent
            }
        }
    }

    @Test
    fun `production root cancels two fingers on different keys and rows`() {
        val actions = mutableListOf<KeyAction>()
        val keyboard = productionKeyboard(actions)
        val first = keyBounds(keyboard, "na")
        // A second row forces the event through multiple ViewGroup ancestors.
        val second = keyBounds(keyboard, "a")
        dispatch(keyboard, MotionEvent.ACTION_DOWN, first.exactCenterX(), first.exactCenterY())
        dispatchPair(keyboard, MotionEvent.ACTION_POINTER_DOWN or (1 shl MotionEvent.ACTION_POINTER_INDEX_SHIFT), first, second)
        dispatchPair(keyboard, MotionEvent.ACTION_POINTER_UP or (1 shl MotionEvent.ACTION_POINTER_INDEX_SHIFT), first, second)
        dispatch(keyboard, MotionEvent.ACTION_UP, first.exactCenterX(), first.exactCenterY())
        assertTrue("Neither finger may commit after multi-touch", actions.isEmpty())
        dispatch(keyboard, MotionEvent.ACTION_DOWN, first.exactCenterX(), first.exactCenterY())
        dispatch(keyboard, MotionEvent.ACTION_UP, first.exactCenterX(), first.exactCenterY())
        assertEquals(listOf(KeyAction.InsertText("な")), actions)
    }
}
