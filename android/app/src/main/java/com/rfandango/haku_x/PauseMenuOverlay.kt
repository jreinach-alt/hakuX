package com.rfandango.haku_x

import android.content.Context
import android.graphics.Color
import android.graphics.Typeface
import android.graphics.drawable.GradientDrawable
import android.util.Log
import android.util.TypedValue
import android.view.Gravity
import android.view.InputDevice
import android.view.KeyEvent
import android.view.MotionEvent
import android.view.View
import android.widget.Button
import android.widget.FrameLayout
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import android.widget.Toast

class PauseMenuOverlay(context: Context) : FrameLayout(context) {

    var onExitEmulation: (() -> Unit)? = null
    var onDismiss: (() -> Unit)? = null
    var onDiagCapture: ((Int) -> Unit)? = null
    var isDebugToolsEnabled: (() -> Boolean)? = null
    /** #433: save states; null hides the four items. */
    var saveStates: SaveStateActions? = null
        set(v) {
            field = v
            stateButtons.forEach { it.visibility = if (v != null) View.VISIBLE else View.GONE }
        }

    private val card: LinearLayout
    private val mainPage: LinearLayout
    private val slotPage: LinearLayout
    private val slotTitle: TextView
    private val slotList: LinearLayout
    private val slotScroll: ScrollView
    private val statusText: TextView
    private val saveButton: Button
    private val loadButton: Button
    private val undoLoadButton: Button
    private val undoSaveButton: Button
    private val exitButton: Button
    private val stateButtons: List<Button>
    private var debugSection: LinearLayout? = null
    private var debugButton: Button? = null
    private var debugExpanded = false
    /** #433 perflog1016: the owner's marks this run, numbered from 1. */
    private var marks = 0
    private var busy = false
    private var selected = 0
    private var stickHeld = 0

    init {
        setBackgroundColor(Color.argb(160, 0, 0, 0))
        visibility = View.GONE
        isClickable = true
        isFocusable = true

        card = LinearLayout(context).apply {
            orientation = LinearLayout.VERTICAL
            gravity = Gravity.CENTER_HORIZONTAL
            val bg = GradientDrawable().apply {
                setColor(Color.argb(230, 30, 30, 30))
                cornerRadius = dpToPx(16f)
            }
            background = bg
            setPadding(dpToPx(32f).toInt(), dpToPx(24f).toInt(), dpToPx(32f).toInt(), dpToPx(24f).toInt())
            elevation = dpToPx(8f)
        }

        statusText = TextView(context).apply {
            setTextColor(Color.argb(220, 255, 255, 255))
            setTextSize(TypedValue.COMPLEX_UNIT_SP, 14f)
            gravity = Gravity.CENTER
            visibility = View.GONE
        }
        card.addView(statusText, createButtonParams())

        mainPage = LinearLayout(context).apply { orientation = LinearLayout.VERTICAL }
        card.addView(mainPage, LinearLayout.LayoutParams(
            LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT))

        saveButton = createMenuButton(context, "Save state").apply {
            setOnClickListener { openSlots(save = true) }
        }
        loadButton = createMenuButton(context, "Load state").apply {
            setOnClickListener { openSlots(save = false) }
        }
        undoLoadButton = createMenuButton(context, "Undo load").apply {
            setOnClickListener { run("Undoing the load") { it.undoLoad() } }
        }
        undoSaveButton = createMenuButton(context, "Undo save").apply {
            setOnClickListener { run("Undoing the save") { it.undoSave() } }
        }
        stateButtons = listOf(saveButton, loadButton, undoLoadButton, undoSaveButton)
        for (b in stateButtons) {
            b.visibility = View.GONE
            mainPage.addView(b, createButtonParams())
        }

        exitButton = createMenuButton(context, "Exit").apply {
            val bg = (background as GradientDrawable)
            bg.setColor(Color.argb(230, 90, 90, 90))
            setOnClickListener { if (!busy) onExitEmulation?.invoke() }
        }
        mainPage.addView(exitButton, createButtonParams())

        slotPage = LinearLayout(context).apply {
            orientation = LinearLayout.VERTICAL
            visibility = View.GONE
        }
        slotTitle = TextView(context).apply {
            setTextColor(Color.WHITE)
            setTextSize(TypedValue.COMPLEX_UNIT_SP, 18f)
            typeface = Typeface.DEFAULT_BOLD
            gravity = Gravity.CENTER
        }
        slotPage.addView(slotTitle, createButtonParams())
        slotList = LinearLayout(context).apply { orientation = LinearLayout.VERTICAL }
        slotScroll = ScrollView(context).apply {
            isVerticalScrollBarEnabled = true
            addView(slotList)
        }
        val listHeight = (resources.displayMetrics.heightPixels * 0.55f).toInt()
        slotPage.addView(slotScroll, LinearLayout.LayoutParams(
            LinearLayout.LayoutParams.MATCH_PARENT, listHeight))
        val back = createMenuButton(context, "Back").apply {
            setOnClickListener { if (!busy) showMain() }
        }
        slotPage.addView(back, createButtonParams().apply { topMargin = dpToPx(12f).toInt() })
        card.addView(slotPage, LinearLayout.LayoutParams(
            LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT))

        val cardParams = LayoutParams(
            dpToPx(320f).toInt(),
            LayoutParams.WRAP_CONTENT
        ).apply { gravity = Gravity.CENTER }
        addView(card, cardParams)

        setOnTouchListener { _, event ->
            if (event.action == MotionEvent.ACTION_UP && visibility == View.VISIBLE && !busy) {
                onDismiss?.invoke()
                true
            } else {
                true
            }
        }

        // The perflog switch is off at every launch. A marker the last run
        // left behind would turn it on at the emulator's first poll; this runs
        // in onCreate, before SDL starts the emulator thread.
        val stale = perflogMarker()
        if (stale != null && stale.exists() && stale.delete()) {
            Log.i(PERF_TAG, "[perflog] pause menu: cleared the last run's marker; OFF at launch")
        }
    }

    fun show() {
        rebuildDebugSection()
        debugExpanded = false
        showMain()
        visibility = View.VISIBLE
        refreshUndo()
    }

    fun dismiss() {
        visibility = View.GONE
    }

    fun isShowing(): Boolean = visibility == View.VISIBLE

    // ---- gamepad and keyboard

    /**
     * Keys while the menu is up. The emulator's surface keeps the input focus
     * and takes every gamepad key, so the menu moves its own selection.
     * Returns false for keys the menu leaves alone.
     */
    fun handleKey(event: KeyEvent): Boolean {
        val down = event.action == KeyEvent.ACTION_DOWN
        when (event.keyCode) {
            KeyEvent.KEYCODE_DPAD_UP, KeyEvent.KEYCODE_DPAD_LEFT -> { if (down) move(-1) }
            KeyEvent.KEYCODE_DPAD_DOWN, KeyEvent.KEYCODE_DPAD_RIGHT -> { if (down) move(1) }
            KeyEvent.KEYCODE_DPAD_CENTER, KeyEvent.KEYCODE_ENTER,
            KeyEvent.KEYCODE_BUTTON_A -> {
                if (down && event.repeatCount == 0) navigable().getOrNull(selected)?.performClick()
            }
            KeyEvent.KEYCODE_BACK, KeyEvent.KEYCODE_BUTTON_B -> {
                if (down && event.repeatCount == 0 && !busy) {
                    if (slotPage.visibility == View.VISIBLE) showMain() else onDismiss?.invoke()
                }
            }
            else -> return false
        }
        return true
    }

    /** The d-pad as a hat and the left stick, which arrive as motion. */
    fun handleMotion(event: MotionEvent): Boolean {
        if (event.source and InputDevice.SOURCE_JOYSTICK != InputDevice.SOURCE_JOYSTICK) return false
        val hat = event.getAxisValue(MotionEvent.AXIS_HAT_Y) + event.getAxisValue(MotionEvent.AXIS_HAT_X)
        val stick = event.getAxisValue(MotionEvent.AXIS_Y)
        val v = if (Math.abs(hat) > 0.5f) hat else stick
        val dir = when {
            v > 0.6f -> 1
            v < -0.6f -> -1
            else -> 0
        }
        if (dir != 0 && dir != stickHeld) move(dir)
        stickHeld = dir
        return true
    }

    private fun navigable(): List<Button> {
        val page = if (slotPage.visibility == View.VISIBLE) slotList else mainPage
        val out = ArrayList<Button>()
        collect(page, out)
        if (slotPage.visibility == View.VISIBLE) collect(slotPage.getChildAt(2) as? Button, out)
        return out.filter { it.visibility == View.VISIBLE && it.isEnabled && it.isShown }
    }

    private fun collect(v: View?, out: MutableList<Button>) {
        when (v) {
            null -> return
            is Button -> out += v
            is LinearLayout -> for (i in 0 until v.childCount) collect(v.getChildAt(i), out)
        }
    }

    private fun move(d: Int) {
        val list = navigable()
        if (list.isEmpty()) return
        selected = (selected + d).coerceIn(0, list.size - 1)
        highlight()
    }

    private fun highlight() {
        val list = navigable()
        val all = ArrayList<Button>()
        collect(mainPage, all)
        collect(slotList, all)
        collect(slotPage.getChildAt(2) as? Button, all)
        val sel = list.getOrNull(selected)
        for (b in all) {
            (b.background as? GradientDrawable)?.setStroke(
                if (b === sel) dpToPx(3f).toInt() else 0, Color.argb(255, 120, 200, 120))
        }
        if (sel != null && slotPage.visibility == View.VISIBLE) {
            slotScroll.post {
                val top = sel.top
                val bottom = sel.bottom
                if (top < slotScroll.scrollY) slotScroll.smoothScrollTo(0, top)
                else if (bottom > slotScroll.scrollY + slotScroll.height)
                    slotScroll.smoothScrollTo(0, bottom - slotScroll.height)
            }
        }
    }

    // ---- save states

    private fun showMain() {
        slotPage.visibility = View.GONE
        mainPage.visibility = View.VISIBLE
        selected = 0
        highlight()
    }

    private fun setStatus(text: String?) {
        statusText.text = text ?: ""
        statusText.visibility = if (text.isNullOrEmpty()) View.GONE else View.VISIBLE
    }

    private fun refreshUndo() {
        val ss = saveStates ?: return
        undoLoadButton.isEnabled = false
        undoSaveButton.isEnabled = false
        applyEnabledLook()
        Thread {
            val bits = try { ss.canUndo() } catch (_: Throwable) { 0 }
            post {
                undoLoadButton.isEnabled = bits and 1 != 0
                undoSaveButton.isEnabled = bits and 2 != 0
                applyEnabledLook()
                highlight()
            }
        }.start()
    }

    private fun applyEnabledLook() {
        for (b in stateButtons) b.alpha = if (b.isEnabled) 1f else 0.4f
    }

    private fun openSlots(save: Boolean) {
        val ss = saveStates ?: return
        if (busy) return
        busy = true
        setStatus("Reading slots…")
        Thread {
            val slots = try { ss.list() } catch (_: Throwable) { null }
            post {
                busy = false
                setStatus(null)
                if (slots == null) {
                    toast("Save states are not available: no game is running")
                    return@post
                }
                buildSlots(save, slots)
                mainPage.visibility = View.GONE
                slotPage.visibility = View.VISIBLE
                selected = 0
                highlight()
                slotScroll.scrollTo(0, 0)
            }
        }.start()
    }

    private fun buildSlots(save: Boolean, slots: List<SaveStateSlot>) {
        slotTitle.text = if (save) "Save to slot" else "Load from slot"
        slotList.removeAllViews()
        // Loading also offers the auto slot, first; saving offers 0-9.
        val order = if (save) slots.filter { it.slot in 0..9 }
                    else slots.filter { it.slot == SaveStateSlot.AUTO } + slots.filter { it.slot in 0..9 }
        for (s in order) {
            if (!save && s.slot == SaveStateSlot.AUTO && !s.exists) continue
            val text = StringBuilder("${s.label()}  ·  ${s.whenText()}")
            val usable = save || (s.exists && s.loadable)
            if (!save && s.exists && !s.loadable) {
                text.append("\n").append(SaveStateText.reason(s.reason))
            } else if (!save && s.exists && s.otherTitleSince) {
                text.append("\nanother game ran since; its saves on the hard disk roll back too")
            }
            val b = createMenuButton(context, text.toString()).apply {
                setTextSize(TypedValue.COMPLEX_UNIT_SP, 14f)
                gravity = Gravity.START or Gravity.CENTER_VERTICAL
                isEnabled = usable
                alpha = if (usable) 1f else 0.4f
                setPadding(dpToPx(16f).toInt(), dpToPx(10f).toInt(), dpToPx(16f).toInt(), dpToPx(10f).toInt())
                setOnClickListener {
                    if (save) run("Saving to ${s.label()}") { it.save(s.slot) }
                    else run("Loading ${s.label()}") { it.load(s.slot) }
                }
            }
            slotList.addView(b, createButtonParams().apply { bottomMargin = dpToPx(8f).toInt() })
        }
    }

    private fun run(what: String, op: (SaveStateActions) -> SaveStateResult) {
        val ss = saveStates ?: return
        if (busy) return
        busy = true
        setStatus("$what…")
        Thread {
            val r = try { op(ss) } catch (t: Throwable) {
                SaveStateResult(false, "error", -1, 0, 0, false, t.message ?: "")
            }
            post { finish(what, r) }
        }.start()
    }

    private fun finish(what: String, r: SaveStateResult) {
        busy = false
        setStatus(null)
        val slotName = when (r.slot) {
            SaveStateSlot.AUTO -> "the auto slot"
            in 0..9 -> "slot ${r.slot}"
            else -> ""
        }
        val msg = when {
            what.startsWith("Saving") && r.ok ->
                "Saved to $slotName (paused ${SaveStateText.ms(r.pauseMs)})"
            what.startsWith("Loading") && r.ok ->
                "Loaded $slotName (${SaveStateText.ms(r.totalMs)})"
            what.startsWith("Undoing the load") && r.ok ->
                "Load undone (${SaveStateText.ms(r.totalMs)})"
            what.startsWith("Undoing the save") && r.ok ->
                "Previous state put back in $slotName"
            else -> "$what failed: ${SaveStateText.reason(r.reason)}"
        }
        toast(msg)
        // A save and a load go back to the game; so does a failed load that
        // changed the machine (it put the game back as it was).
        val leave = r.ok && !what.startsWith("Undoing the save") || r.changed
        if (leave) {
            onDismiss?.invoke()
        } else {
            showMain()
            refreshUndo()
        }
    }

    private fun toast(msg: String) {
        Toast.makeText(context, msg, Toast.LENGTH_SHORT).show()
    }

    // ---- debug

    private fun rebuildDebugSection() {
        // Remove old debug UI
        debugSection?.let { mainPage.removeView(it) }
        debugSection = null
        debugButton?.let { mainPage.removeView(it) }
        debugButton = null

        val enabled = isDebugToolsEnabled?.invoke() ?: false
        if (!enabled) return

        // Add "Debug" button
        debugButton = createMenuButton(context, "🔧 Debug Capture").apply {
            val bg = (background as GradientDrawable)
            bg.setColor(Color.argb(200, 50, 80, 120))
            setOnClickListener { toggleDebugSection() }
        }
        mainPage.addView(debugButton, createButtonParams())

        // Prepare expandable section (hidden initially)
        debugSection = LinearLayout(context).apply {
            orientation = LinearLayout.VERTICAL
            visibility = View.GONE

            addView(createPerflogButton(context), createButtonParams())
            addView(createMarkButton(context), createButtonParams())
            addView(createFrameDumpButton(context), createButtonParams())

            val capture1 = createCaptureButton(context, "Capture 1 Frame", 1)
            addView(capture1, createButtonParams())

            val capture5 = createCaptureButton(context, "Capture 5 Frames", 5)
            addView(capture5, createButtonParams())

            val capture10 = createCaptureButton(context, "Capture 10 Frames", 10)
            addView(capture10, createButtonParams())
        }
        mainPage.addView(debugSection, createButtonParams())
    }

    private fun toggleDebugSection() {
        debugExpanded = !debugExpanded
        debugSection?.visibility = if (debugExpanded) View.VISIBLE else View.GONE
    }

    private fun createCaptureButton(context: Context, label: String, frames: Int): Button {
        return createMenuButton(context, label).apply {
            val bg = (background as GradientDrawable)
            bg.setColor(Color.argb(200, 40, 100, 70))
            setTextSize(TypedValue.COMPLEX_UNIT_SP, 14f)
            setOnClickListener {
                android.util.Log.i("hakuX-diag", "capture: setting $frames frame pending, then resuming")
                // Set the pending flag BEFORE resuming so the first
                // FLIP_STALL / FLIP_INCREMENT_WRITE after unpause picks it up.
                onDiagCapture?.invoke(frames)
                onDismiss?.invoke()
            }
        }
    }

    // ---- the perflog switch, marks and the frame dump (#433, perflog1016)
    //
    // All three are marker files or log lines, with no JNI: the emulator polls
    // its markers once a second at the flip, in the directory SDL calls the
    // external storage path (xemu_android.cpp hands it to the frame dump),
    // which is getExternalFilesDir(null). A marker written while the menu is
    // up is read within a second of resuming.

    private fun markerFile(name: String): java.io.File? =
        context.getExternalFilesDir(null)?.let { java.io.File(it, name) }

    /** Present means on (hw/xbox/nv2a/debug.h, NV2A_PERFLOG_MARKER). */
    private fun perflogMarker(): java.io.File? = markerFile("perflog.on")

    /** Why the switch cannot move, or null when the button decides. A perflog
     *  build times everything always (versionName ends -perflog, from
     *  version_stamp.sh); XEMU_PERFLOG_RT=1 pins it on for the run. */
    private fun perflogPinned(): String? {
        val version = try {
            context.packageManager.getPackageInfo(context.packageName, 0).versionName
        } catch (_: Throwable) { null }
        if (version != null && version.contains("-perflog")) return "perflog build"
        val env = System.getenv("XEMU_PERFLOG_RT")
        if (env != null && env.isNotEmpty() && env != "0") return "XEMU_PERFLOG_RT"
        return null
    }

    private fun perflogLabel(): String {
        val pinned = perflogPinned()
        return when {
            pinned != null -> "Perflog: ON ($pinned)"
            perflogMarker()?.exists() == true -> "Perflog: ON"
            else -> "Perflog: OFF"
        }
    }

    private fun createPerflogButton(context: Context): Button {
        return createMenuButton(context, perflogLabel()).apply {
            val bg = (background as GradientDrawable)
            bg.setColor(Color.argb(200, 110, 80, 40))
            setTextSize(TypedValue.COMPLEX_UNIT_SP, 14f)
            setOnClickListener {
                val pinned = perflogPinned()
                val marker = perflogMarker()
                if (pinned != null) {
                    Log.i(PERF_TAG, "[perflog] pause menu: no change, pinned on by $pinned")
                    toast("Perflog is on for this whole run ($pinned)")
                } else if (marker == null) {
                    Log.w(PERF_TAG, "[perflog] pause menu: no external files dir; the switch is unavailable")
                    toast("Perflog switch unavailable: no external storage")
                } else {
                    val on = !marker.exists()
                    val ok = try {
                        if (on) { marker.createNewFile(); marker.exists() }
                        else { marker.delete(); !marker.exists() }
                    } catch (_: Throwable) { false }
                    val want = if (on) "ON" else "OFF"
                    if (ok) {
                        // The emulator's own line, "[perflog] runtime tier ON
                        // (frame N, by marker)", follows on resume; this one
                        // dates the press.
                        Log.i(PERF_TAG, "[perflog] pause menu: $want requested")
                        toast("Perflog $want from about a second after you resume")
                    } else {
                        Log.w(PERF_TAG, "[perflog] pause menu: $want requested, marker write failed: $marker")
                        toast("Perflog: could not write the marker")
                    }
                }
                text = perflogLabel()
            }
        }
    }

    /** One `mark owner-N` line on hakuX-route, the route driver's shape
     *  (`log -t hakuX-route "mark <label>"`), on the logcat clock. "gameplay"
     *  and "play" are the scored window's marks, so the owner's are numbered. */
    private fun createMarkButton(context: Context): Button {
        return createMenuButton(context, "Mark this moment").apply {
            val bg = (background as GradientDrawable)
            bg.setColor(Color.argb(200, 110, 80, 40))
            setTextSize(TypedValue.COMPLEX_UNIT_SP, 14f)
            setOnClickListener {
                marks += 1
                Log.i("hakuX-route", "mark owner-$marks")
                toast("Marked owner-$marks")
            }
        }
    }

    /** Arms the per-draw frame dump for 30 frames from about a second after
     *  resume (vk/renderer.c fdump_poll_marker; the marker is one-shot). */
    private fun createFrameDumpButton(context: Context): Button {
        return createMenuButton(context, "Frame dump (30 frames)").apply {
            val bg = (background as GradientDrawable)
            bg.setColor(Color.argb(200, 40, 100, 70))
            setTextSize(TypedValue.COMPLEX_UNIT_SP, 14f)
            setOnClickListener {
                val marker = markerFile("frame_dump.on")
                val ok = marker != null && try {
                    marker.writeText("30\n")
                    true
                } catch (_: Throwable) { false }
                if (ok) {
                    Log.i(PERF_TAG, "[framedump] pause menu: armed 30 frames, from resume")
                    onDismiss?.invoke()
                } else {
                    Log.w(PERF_TAG, "[framedump] pause menu: marker write failed: $marker")
                    toast("Frame dump: could not write the marker")
                }
            }
        }
    }

    private fun createMenuButton(context: Context, label: String): Button {
        return Button(context).apply {
            text = label
            setTextColor(Color.WHITE)
            setTextSize(TypedValue.COMPLEX_UNIT_SP, 16f)
            typeface = Typeface.DEFAULT_BOLD
            isAllCaps = false
            val bg = GradientDrawable().apply {
                setColor(Color.argb(200, 70, 70, 70))
                cornerRadius = dpToPx(8f)
            }
            background = bg
            setPadding(dpToPx(16f).toInt(), dpToPx(14f).toInt(), dpToPx(16f).toInt(), dpToPx(14f).toInt())
            stateListAnimator = null
        }
    }

    private fun createButtonParams(): LinearLayout.LayoutParams {
        return LinearLayout.LayoutParams(
            LinearLayout.LayoutParams.MATCH_PARENT,
            LinearLayout.LayoutParams.WRAP_CONTENT
        ).apply { bottomMargin = dpToPx(12f).toInt() }
    }

    private fun dpToPx(dp: Float): Float {
        return TypedValue.applyDimension(TypedValue.COMPLEX_UNIT_DIP, dp, resources.displayMetrics)
    }

    private companion object {
        /** The emulator's flip line is on this tag too, and the dispatcher's
         *  logcat spec keeps it (dispatcher.sh LOGCAT_SPEC). */
        const val PERF_TAG = "hakuX-perf"
    }
}
