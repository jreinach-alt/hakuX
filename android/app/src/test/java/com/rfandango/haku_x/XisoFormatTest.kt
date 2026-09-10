package com.rfandango.haku_x

import java.io.ByteArrayInputStream
import java.io.InputStream
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class XisoFormatTest {

  private val magic = "MICROSOFT*XBOX*MEDIA".toByteArray(Charsets.US_ASCII)

  /** A minimal image carrying [signature] where the volume descriptor belongs. */
  private fun image(signature: ByteArray = magic, trailing: Int = 2048): ByteArray {
    val offset = XisoFormat.VOLUME_DESCRIPTOR_OFFSET.toInt()
    return ByteArray(offset + signature.size + trailing).also {
      signature.copyInto(it, offset)
    }
  }

  @Test
  fun `recognises the volume descriptor`() {
    assertTrue(XisoFormat.hasVolumeMagic(ByteArrayInputStream(image())))
  }

  @Test
  fun `rejects an image with something else at the descriptor`() {
    val impostor = "MICROSOFT*XBOX*MEDIB".toByteArray(Charsets.US_ASCII)
    assertFalse(XisoFormat.hasVolumeMagic(ByteArrayInputStream(image(impostor))))
  }

  @Test
  fun `rejects an image that ends before the descriptor`() {
    val truncated = ByteArray(XisoFormat.VOLUME_DESCRIPTOR_OFFSET.toInt() - 1)
    assertFalse(XisoFormat.hasVolumeMagic(ByteArrayInputStream(truncated)))
  }

  @Test
  fun `rejects an image that ends partway through the descriptor`() {
    val full = image()
    val cut = full.copyOf(XisoFormat.VOLUME_DESCRIPTOR_OFFSET.toInt() + magic.size - 1)
    assertFalse(XisoFormat.hasVolumeMagic(ByteArrayInputStream(cut)))
  }

  @Test
  fun `rejects an empty stream`() {
    assertFalse(XisoFormat.hasVolumeMagic(ByteArrayInputStream(ByteArray(0))))
  }

  @Test
  fun `accepts a stream whose skip stops short of what was asked`() {
    // InputStream.skip may return less than requested for reasons unrelated to
    // the end of the stream. Treating that as failure rejected good discs.
    val stream = ThrottledStream(image(), maxSkip = 4096L, maxRead = Int.MAX_VALUE)
    assertTrue(XisoFormat.hasVolumeMagic(stream))
  }

  @Test
  fun `accepts a stream whose skip always returns zero`() {
    val stream = ThrottledStream(image(), maxSkip = 0L, maxRead = Int.MAX_VALUE)
    assertTrue(XisoFormat.hasVolumeMagic(stream))
  }

  @Test
  fun `accepts a stream that hands back the signature a few bytes at a time`() {
    // The old check read once and compared the count against the full length,
    // so a short read of a valid disc was reported as corruption.
    val stream = ThrottledStream(image(), maxSkip = Long.MAX_VALUE, maxRead = 3)
    assertTrue(XisoFormat.hasVolumeMagic(stream))
  }

  /** An InputStream that limits how much it will skip or read per call. */
  private class ThrottledStream(
    private val data: ByteArray,
    private val maxSkip: Long,
    private val maxRead: Int,
  ) : InputStream() {
    private var position = 0

    override fun read(): Int =
      if (position >= data.size) -1 else data[position++].toInt() and 0xFF

    override fun read(b: ByteArray, off: Int, len: Int): Int {
      if (position >= data.size) return -1
      val n = minOf(maxRead, len, data.size - position)
      System.arraycopy(data, position, b, off, n)
      position += n
      return n
    }

    override fun skip(n: Long): Long {
      val allowed = minOf(n, maxSkip, (data.size - position).toLong())
      position += allowed.toInt()
      return allowed
    }
  }
}
