package com.rfandango.haku_x

import android.util.Log
import java.io.File

/**
 * The CPU floor the native libraries are built for.
 *
 * CMakeLists.txt builds every native target with `-march=armv8.2-a`, so
 * atomics are emitted as inline LSE instructions (`casal`, `ldaddal`, ...)
 * rather than calls to the run-time-dispatched `__aarch64_*` helpers (#427).
 * On an ARMv8.0 core without LSE (Cortex-A53/A73: SD 835, 660, 665, 460,
 * Helio G35) the first of those raises SIGILL while the library loads, and
 * the process dies with nothing on screen.
 *
 * This check has to be Kotlin: a native check built from that CMakeLists
 * would carry the flag and could trap before it answered. Every
 * `System.loadLibrary` of ours goes through [requireSupported] first.
 */
object CpuSupport {
  private const val TAG = "hakuX"

  const val UNSUPPORTED_MESSAGE =
    "This device's CPU is not supported. hakuX needs an ARMv8.2 CPU with " +
      "LSE atomics (Snapdragon 845 / 865 class or newer)."

  /**
   * True when every core's `Features` line in /proc/cpuinfo lists `atomics`
   * (HWCAP_ATOMICS). A cpuinfo with no `Features` line at all cannot answer,
   * so it is logged and treated as supported rather than locking out a
   * device the check cannot read.
   */
  val hasLse: Boolean by lazy { readHasLse() }

  private fun readHasLse(): Boolean {
    val features = try {
      File("/proc/cpuinfo").readLines()
        .filter { it.substringBefore(':').trim() == "Features" }
        .map { it.substringAfter(':').trim().split(Regex("\\s+")) }
    } catch (e: Exception) {
      Log.w(TAG, "CpuSupport: /proc/cpuinfo unreadable, assuming LSE", e)
      return true
    }
    if (features.isEmpty()) {
      Log.w(TAG, "CpuSupport: no Features line in /proc/cpuinfo, assuming LSE")
      return true
    }
    val ok = features.all { "atomics" in it }
    if (!ok) Log.e(TAG, "CpuSupport: a core lacks LSE atomics; native libraries will not be loaded")
    return ok
  }

  /**
   * Throws [UnsatisfiedLinkError] when the CPU is below the floor, so every
   * caller that already handles a missing library handles this the same way
   * and never reaches the load that would trap.
   */
  fun requireSupported() {
    if (!hasLse) throw UnsatisfiedLinkError(UNSUPPORTED_MESSAGE)
  }
}
