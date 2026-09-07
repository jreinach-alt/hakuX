package com.rfandango.haku_x

import java.io.InputStream

/**
 * Recognition of the XDVDFS volume descriptor that marks a disc image as an
 * Xbox one.
 *
 * Deliberately free of Android types so it can be tested on the JVM.
 */
object XisoFormat {

  /** Sector 32, where the primary volume descriptor sits in a plain XISO. */
  const val VOLUME_DESCRIPTOR_OFFSET = 0x10000L

  private val MAGIC = "MICROSOFT*XBOX*MEDIA".toByteArray(Charsets.US_ASCII)

  /**
   * True when [input], read from its start, carries the volume descriptor
   * signature at [VOLUME_DESCRIPTOR_OFFSET].
   *
   * Both the seek and the read are done to completion rather than in one
   * call. InputStream.skip and InputStream.read are each permitted to do less
   * than asked for reasons that have nothing to do with reaching the end —
   * a decompressing or network-backed stream commonly does — so treating a
   * short result as failure rejects discs that are perfectly good.
   */
  fun hasVolumeMagic(input: InputStream): Boolean {
    if (!skipFully(input, VOLUME_DESCRIPTOR_OFFSET)) return false
    val buffer = ByteArray(MAGIC.size)
    if (!readFully(input, buffer)) return false
    return buffer.contentEquals(MAGIC)
  }

  /** Skip exactly [count] bytes. False if the stream ended first. */
  private fun skipFully(input: InputStream, count: Long): Boolean {
    var remaining = count
    while (remaining > 0) {
      val skipped = input.skip(remaining)
      if (skipped > 0) {
        remaining -= skipped
        continue
      }
      // skip() may legitimately return 0. Fall back to reading, which
      // distinguishes "nothing available right now" from end of stream.
      if (input.read() < 0) return false
      remaining--
    }
    return true
  }

  /** Fill [buffer] completely. False if the stream ended first. */
  private fun readFully(input: InputStream, buffer: ByteArray): Boolean {
    var offset = 0
    while (offset < buffer.size) {
      val read = input.read(buffer, offset, buffer.size - offset)
      if (read < 0) return false
      offset += read
    }
    return true
  }
}
