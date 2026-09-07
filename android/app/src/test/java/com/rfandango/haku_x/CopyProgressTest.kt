package com.rfandango.haku_x

import java.io.ByteArrayInputStream
import java.io.ByteArrayOutputStream
import java.io.InputStream
import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class CopyProgressTest {

  @Test
  fun `unknown total has no honest percentage`() {
    // The setup wizard bug: a provider that reports no size must produce
    // indeterminate progress, not a bar sitting at zero for several minutes.
    assertNull(CopyProgress.percentOf(copied = 512L, total = 0L))
    assertNull(CopyProgress.percentOf(copied = 512L, total = -1L))
  }

  @Test
  fun `percentage spans nothing copied to everything copied`() {
    assertEquals(0, CopyProgress.percentOf(0L, 200L))
    assertEquals(50, CopyProgress.percentOf(100L, 200L))
    assertEquals(100, CopyProgress.percentOf(200L, 200L))
  }

  @Test
  fun `a source that grew mid-copy does not exceed one hundred`() {
    assertEquals(100, CopyProgress.percentOf(300L, 200L))
  }

  @Test
  fun `a gigabyte copy does not overflow or round to zero`() {
    val total = 1_073_741_824L
    assertEquals(0, CopyProgress.percentOf(1L, total))
    assertEquals(50, CopyProgress.percentOf(total / 2, total))
    assertEquals(100, CopyProgress.percentOf(total, total))
  }

  @Test
  fun `copy reproduces the source exactly`() {
    val source = ByteArray(200_000) { (it % 251).toByte() }
    val sink = ByteArrayOutputStream()

    val copied = CopyProgress.copy(ByteArrayInputStream(source), sink, source.size.toLong()) {}

    assertEquals(source.size.toLong(), copied)
    assertArrayEquals(source, sink.toByteArray())
  }

  @Test
  fun `copy reports rising percentages and finishes at one hundred`() {
    val source = ByteArray(CopyProgress.BUFFER_BYTES * 4)
    val seen = mutableListOf<Int>()

    CopyProgress.copy(
      ByteArrayInputStream(source),
      ByteArrayOutputStream(),
      source.size.toLong(),
    ) { seen += it }

    assertTrue("expected progress reports, got none", seen.isNotEmpty())
    assertEquals(seen.sorted(), seen)
    assertEquals(seen.distinct(), seen)
    assertEquals(100, seen.last())
  }

  @Test
  fun `copy stays silent when the total is unknown`() {
    val seen = mutableListOf<Int>()

    val copied = CopyProgress.copy(
      ByteArrayInputStream(ByteArray(100_000)),
      ByteArrayOutputStream(),
      total = -1L,
    ) { seen += it }

    assertEquals(100_000L, copied)
    assertEquals(emptyList<Int>(), seen)
  }

  @Test
  fun `copy handles a stream that returns short reads`() {
    // Content providers, decompressing streams and network-backed sources all
    // hand back less than asked for without being at the end.
    val source = ByteArray(50_000) { (it % 97).toByte() }
    val sink = ByteArrayOutputStream()

    val copied = CopyProgress.copy(StubbornStream(source, chunk = 7), sink, source.size.toLong()) {}

    assertEquals(source.size.toLong(), copied)
    assertArrayEquals(source, sink.toByteArray())
  }

  @Test
  fun `an empty source copies nothing and reports nothing`() {
    val seen = mutableListOf<Int>()

    val copied = CopyProgress.copy(
      ByteArrayInputStream(ByteArray(0)),
      ByteArrayOutputStream(),
      total = 100L,
    ) { seen += it }

    assertEquals(0L, copied)
    assertEquals(emptyList<Int>(), seen)
  }

  /** An InputStream that never returns more than [chunk] bytes at a time. */
  private class StubbornStream(private val data: ByteArray, private val chunk: Int) : InputStream() {
    private var position = 0

    override fun read(): Int =
      if (position >= data.size) -1 else data[position++].toInt() and 0xFF

    override fun read(b: ByteArray, off: Int, len: Int): Int {
      if (position >= data.size) return -1
      val n = minOf(chunk, len, data.size - position)
      System.arraycopy(data, position, b, off, n)
      position += n
      return n
    }
  }
}
