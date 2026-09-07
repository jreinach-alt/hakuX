package com.rfandango.haku_x

import android.app.Application
import android.util.Log
import java.io.File
import java.io.FileOutputStream
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

class HakuXApplication : Application() {

  companion object {
    private const val TAG = "HakuXApp"
    private val LOG_TAGS = arrayOf(
      // App
      "hakuX:V", "hakuX-phase:V", "hakuX-cpu:V", "hakuX-stall:V",
      "hakuX-rw:V", "hakuX-rpbrk:V", "hakuX-tex:V",
      "hakuX-mmio:V", "hakuX-nop:V", "hakuX-mhist:V",
      "hakuX-compat:V", "hakuX-config:V", "hakuX-diag:V",
      "hakuX-texreplace:V", "hakuX-watchdog:V",
      "hakuX-vk:V", "hakuX-vk-dbg:V",
      "xemu:V", "xemu-sfp:V", "xemu-surf:V", "xemu-vsync:V",
      "xemu-gpu:V", "xemu-pace:V", "xemu-work:V",
      "xemu-android:V", "xemu-fpu:V", "xemu-glsl:V", "xemu-vaf:V",
      "xemu-vulkan:V", "xemu-vk-debug:V", "xemu-vk-validation:V",
      "nv2a:V",
      // Guest kernel crash detection (BugCheck 0x1E and friends). Emitted from
      // target/i386 and accel/tcg; omitting it silenced the very diagnostics
      // KNOWN_ISSUES.md tells people to collect.
      "hakuX-crash:V",
      // Native crash
      "DEBUG:V", "libc:V", "crash_dump:V", "tombstoned:V",
      // Memory / OOM
      "lowmemorykiller:V", "lmkd:V", "ActivityManager:W", "Zygote:W",
      // Runtime
      "AndroidRuntime:V", "art:W", "linker:V",
      // GPU
      "EGL:W", "Vulkan:V",
      // Silence everything else
      "*:S"
    )

    @Volatile
    private var logProcess: Process? = null

    /**
     * Suffix distinguishing this process's logs from another's.
     *
     * The emulator runs in a separate `:xemu` process, and Application.onCreate
     * runs once per process. Without a suffix both processes rotate and stream
     * into one file, and the older process's still-open handle keeps writing to
     * the inode the younger one just renamed — so `current.log` and
     * `previous.log` end up holding two copies of one session.
     */
    private fun processSuffix(): String {
      val name = try {
        File("/proc/self/cmdline").readText().trim('\u0000', ' ', '\n')
      } catch (_: Exception) {
        ""
      }
      val colon = name.indexOf(':')
      return if (colon >= 0) "-" + name.substring(colon + 1) else ""
    }

    private fun isMainProcess(): Boolean = processSuffix().isEmpty()

    fun getLogFile(context: android.content.Context, name: String): File =
      File(context.filesDir, name)

    fun currentLogFile(context: android.content.Context): File =
      getLogFile(context, "current${processSuffix()}.log")

    fun previousLogFile(context: android.content.Context): File =
      getLogFile(context, "previous${processSuffix()}.log")

    /** Every rotated log on disk, whichever process wrote it. */
    fun allLogFiles(context: android.content.Context): List<File> =
      context.filesDir
        .listFiles { f -> f.isFile && f.name.endsWith(".log") &&
                          (f.name.startsWith("current") || f.name.startsWith("previous")) }
        ?.sortedBy { it.name }
        ?: emptyList()
  }

  override fun onCreate() {
    super.onCreate()
    rotateLogs()
    startLogCapture()
  }

  private fun rotateLogs() {
    val current = currentLogFile(this)
    val previous = previousLogFile(this)

    if (current.exists() && current.length() > 0) {
      previous.delete()
      current.renameTo(previous)
      Log.i(TAG, "Rotated logs: current -> previous (${previous.length()} bytes)")
    }
  }

  private fun startLogCapture() {
    Thread {
      try {
        // Clear the buffer so this file holds only the current session. The
        // buffer is shared system-wide, so only the main process may do it:
        // were :xemu to clear it too, it would discard what the launcher had
        // not yet drained — including a crash in LauncherActivity itself.
        if (isMainProcess()) {
            Runtime.getRuntime().exec(arrayOf("logcat", "-c")).waitFor()
        }

        // Write session separator header
        val current = currentLogFile(this)
        val timestamp = SimpleDateFormat("yyyy-MM-dd HH:mm:ss.SSS", Locale.US).format(Date())
        FileOutputStream(current, false).use { fos ->
          fos.write("========================================\n".toByteArray())
          fos.write("=== Session started: $timestamp\n".toByteArray())
          fos.write("=== PID: ${android.os.Process.myPid()}\n".toByteArray())
          fos.write("=== Device: ${android.os.Build.MANUFACTURER} ${android.os.Build.MODEL}\n".toByteArray())
          fos.write("=== Android: ${android.os.Build.VERSION.RELEASE} (SDK ${android.os.Build.VERSION.SDK_INT})\n".toByteArray())
          fos.write("========================================\n\n".toByteArray())
        }

        // Start logcat with tag filter, appending to the file with the header
        val cmd = mutableListOf("logcat", "-v", "threadtime")
        cmd.addAll(LOG_TAGS)
        val process = Runtime.getRuntime().exec(cmd.toTypedArray())
        logProcess = process

        FileOutputStream(current, true).use { fos ->
          process.inputStream.copyTo(fos)
        }
      } catch (e: Exception) {
        Log.e(TAG, "Log capture failed", e)
      }
    }.apply {
      isDaemon = true
      name = "log-capture"
      start()
    }
  }
}
