package com.rfandango.haku_x

import android.content.Context
import android.content.SharedPreferences
import android.net.Uri
import android.util.Log
import org.json.JSONArray

/** The ordered set of games folders (SAF tree URIs), stored as a JSON array in `gamesFolderUris`. */
object GamesFolders {
  private const val TAG = "hakuX-folders"
  const val KEY = "gamesFolderUris"
  private const val LEGACY_KEY = "gamesFolderUri"

  /** Folders in the order the user added them; migrates the old single-folder pref on first read. */
  fun read(prefs: SharedPreferences): List<Uri> {
    val json = prefs.getString(KEY, null)
    if (json != null) {
      return parse(json)
    }
    val legacy = prefs.getString(LEGACY_KEY, null) ?: return emptyList()
    Log.i(TAG, "migrating single games folder into the set: $legacy")
    val migrated = listOf(Uri.parse(legacy))
    prefs.edit().putString(KEY, encode(migrated)).remove(LEGACY_KEY).apply()
    return migrated
  }

  fun write(prefs: SharedPreferences, folders: List<Uri>) {
    prefs.edit().putString(KEY, encode(folders.distinct())).remove(LEGACY_KEY).apply()
  }

  fun add(prefs: SharedPreferences, uri: Uri) {
    val current = read(prefs)
    if (uri !in current) {
      write(prefs, current + uri)
    }
  }

  fun remove(prefs: SharedPreferences, uri: Uri) {
    write(prefs, read(prefs).filter { it != uri })
  }

  fun hasPersistedRead(context: Context, uri: Uri): Boolean =
    context.contentResolver.persistedUriPermissions.any { it.uri == uri && it.isReadPermission }

  /** Folders that still hold a persisted read permission, in order. Does not touch the pref. */
  fun withPermission(context: Context, prefs: SharedPreferences): List<Uri> =
    read(prefs).filter { hasPersistedRead(context, it) }

  /** Drops only the folders whose permission is gone; returns the survivors. */
  fun pruneDead(context: Context, prefs: SharedPreferences): List<Uri> {
    val all = read(prefs)
    val live = all.filter { hasPersistedRead(context, it) }
    if (live.size != all.size) {
      for (dead in all - live.toSet()) {
        Log.w(TAG, "dropping games folder with no persisted permission: $dead")
      }
      write(prefs, live)
    }
    return live
  }

  private fun parse(json: String): List<Uri> {
    return try {
      val array = JSONArray(json)
      (0 until array.length()).map { Uri.parse(array.getString(it)) }.distinct()
    } catch (e: Exception) {
      Log.e(TAG, "unreadable $KEY, treating as empty: $json", e)
      emptyList()
    }
  }

  private fun encode(folders: List<Uri>): String {
    val array = JSONArray()
    folders.forEach { array.put(it.toString()) }
    return array.toString()
  }
}
