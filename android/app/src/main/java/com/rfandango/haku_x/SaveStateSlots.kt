package com.rfandango.haku_x

import java.text.DateFormat
import java.util.Date

/** What the pause menu needs from the native save state code (#433). */
interface SaveStateActions {
  fun save(slot: Int): SaveStateResult
  fun load(slot: Int): SaveStateResult
  fun undoLoad(): SaveStateResult
  fun undoSave(): SaveStateResult
  /** Slots 0-9, then auto; null when no title is running. */
  fun list(): List<SaveStateSlot>?
  /** Bit 0: a load can be undone; bit 1: a save can be undone. */
  fun canUndo(): Int
}

data class SaveStateResult(
  val ok: Boolean,
  val reason: String,
  val slot: Int,
  val pauseMs: Long,
  val totalMs: Long,
  /** The machine changed: a load reached the disk snapshot. */
  val changed: Boolean,
  val error: String
) {
  companion object {
    /** Parses nativeSaveState*'s "key=value\t..." line. */
    fun parse(s: String?): SaveStateResult {
      val m = HashMap<String, String>()
      s?.split('\t')?.forEach { kv ->
        val eq = kv.indexOf('=')
        if (eq > 0) m[kv.substring(0, eq)] = kv.substring(eq + 1)
      }
      return SaveStateResult(
        ok = m["ok"] == "1",
        reason = m["reason"].orEmpty(),
        slot = m["slot"]?.toIntOrNull() ?: -1,
        pauseMs = m["pause_ms"]?.toDoubleOrNull()?.toLong() ?: 0,
        totalMs = m["total_ms"]?.toDoubleOrNull()?.toLong() ?: 0,
        changed = m["changed"] == "1",
        error = m["error"].orEmpty()
      )
    }
  }
}

data class SaveStateSlot(
  val slot: Int,
  val exists: Boolean,
  val loadable: Boolean,
  val reason: String,
  val savedAt: Long,
  val bytes: Long,
  val codec: String,
  val otherTitleSince: Boolean
) {
  companion object {
    const val AUTO = 10

    /** Parses nativeSaveStateList's lines. */
    fun parseList(s: String?): List<SaveStateSlot>? {
      s ?: return null
      return s.lines().filter { it.isNotBlank() }.mapNotNull { line ->
        val f = line.split('\t')
        if (f.size < 8) return@mapNotNull null
        SaveStateSlot(
          slot = f[0].toIntOrNull() ?: return@mapNotNull null,
          exists = f[1] == "1",
          loadable = f[2] == "1",
          reason = if (f[3] == "-") "" else f[3],
          savedAt = f[4].toLongOrNull() ?: 0,
          bytes = f[5].toLongOrNull() ?: 0,
          codec = f[6],
          otherTitleSince = f[7] == "1"
        )
      }
    }
  }

  fun label(): String = if (slot == AUTO) "Auto" else "Slot $slot"

  fun whenText(): String {
    if (!exists) return "Empty"
    val d = Date(savedAt * 1000)
    return DateFormat.getDateTimeInstance(DateFormat.SHORT, DateFormat.SHORT).format(d)
  }
}

object SaveStateText {
  /** Why a state cannot be saved or loaded, for a player. */
  fun reason(r: String): String = when (r) {
    "schema" -> "saved by a version with different machine state"
    "title" -> "saved in another game"
    "disc" -> "saved with a different disc"
    "controller-layout" -> "saved with different controllers connected"
    "disk-snapshot-missing" -> "its hard disk snapshot is gone"
    "hdd-not-qcow2" -> "the hard disk image is not qcow2"
    "no-folder" -> "no save state folder"
    "not-running" -> "no game is running"
    "no-title" -> "the game is not identified yet"
    "corrupt", "incomplete" -> "the file is damaged"
    "empty" -> "empty"
    "nothing-to-undo" -> "nothing to undo"
    "open-failed", "write-failed" -> "the folder could not be written"
    "cannot-save" -> "the machine cannot be saved right now"
    "save-failed" -> "saving failed"
    "restore-failed" -> "loading failed; the game was put back"
    "undo-failed" -> "undo failed"
    else -> r
  }

  fun ms(ms: Long): String = if (ms >= 1000) "%.1f s".format(ms / 1000.0) else "$ms ms"
}
