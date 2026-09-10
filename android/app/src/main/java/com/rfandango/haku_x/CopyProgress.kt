package com.rfandango.haku_x

import java.io.InputStream
import java.io.OutputStream

/**
 * Progress arithmetic and the copy loop for the long file copies this app
 * makes: importing a ~1 GB HDD image in the setup wizard, and staging a disc
 * image for XISO conversion in the library.
 *
 * Deliberately free of Android types so it can be tested on the JVM.
 */
object CopyProgress {

  /** Read size for the copy loop. Large enough that a 1 GB copy is not syscall bound. */
  const val BUFFER_BYTES = 65536

  /**
   * The percentage of [total] that [copied] represents, or null when no
   * honest percentage exists.
   *
   * A total of zero or less means the source size could not be determined —
   * a content provider is free to report nothing for it. Callers must show
   * that as indeterminate progress. Reporting it as 0% instead produces a bar
   * that never moves, which reads exactly like the freeze it was meant to
   * explain.
   */
  fun percentOf(copied: Long, total: Long): Int? {
    if (total <= 0L) return null
    if (copied <= 0L) return 0
    return (copied * 100 / total).toInt().coerceAtMost(100)
  }

  /**
   * Copy [input] to [output], invoking [onPercent] whenever the whole
   * percentage changes. Returns the number of bytes copied.
   *
   * [onPercent] is never called when [total] is unknown; there is nothing
   * truthful to report. Neither stream is closed — the caller owns them.
   */
  fun copy(
    input: InputStream,
    output: OutputStream,
    total: Long,
    onPercent: (Int) -> Unit,
  ): Long {
    val buffer = ByteArray(BUFFER_BYTES)
    var copied = 0L
    var lastPercent = -1
    while (true) {
      val read = input.read(buffer)
      if (read < 0) break
      if (read == 0) continue
      output.write(buffer, 0, read)
      copied += read
      val percent = percentOf(copied, total)
      if (percent != null && percent != lastPercent) {
        lastPercent = percent
        onPercent(percent)
      }
    }
    return copied
  }
}
