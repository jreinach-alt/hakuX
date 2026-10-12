package com.rfandango.haku_x

import android.content.Context
import android.net.Uri
import android.provider.DocumentsContract
import android.util.Log

/**
 * Save states in a folder picked through the Storage Access Framework (#433).
 *
 * The native save state code (savestate/hxs_jni.cpp) calls these from its own
 * threads with paths relative to the picked folder, such as
 * "55530036/slot3.hxs". Each returns 0 or a file descriptor on success and a
 * negative errno on failure, the way the POSIX calls they stand in for do.
 */
object SaveStateStore {
  private const val TAG = "hakuX-savestate"
  private const val ENOENT = 2
  private const val EIO = 5
  private const val EEXIST = 17
  private const val EXDEV = 18

  private data class Child(val id: String, val name: String, val size: Long,
                           val mtime: Long, val dir: Boolean)

  private fun children(ctx: Context, tree: Uri, parentId: String): List<Child>? {
    val uri = DocumentsContract.buildChildDocumentsUriUsingTree(tree, parentId)
    val cols = arrayOf(
      DocumentsContract.Document.COLUMN_DOCUMENT_ID,
      DocumentsContract.Document.COLUMN_DISPLAY_NAME,
      DocumentsContract.Document.COLUMN_SIZE,
      DocumentsContract.Document.COLUMN_LAST_MODIFIED,
      DocumentsContract.Document.COLUMN_MIME_TYPE
    )
    return try {
      ctx.contentResolver.query(uri, cols, null, null, null)?.use { c ->
        val out = ArrayList<Child>(c.count)
        while (c.moveToNext()) {
          out += Child(
            c.getString(0), c.getString(1) ?: "",
            if (c.isNull(2)) 0 else c.getLong(2),
            if (c.isNull(3)) 0 else c.getLong(3),
            c.getString(4) == DocumentsContract.Document.MIME_TYPE_DIR
          )
        }
        out
      }
    } catch (e: Exception) {
      Log.w(TAG, "list $parentId: ${e.message}")
      null
    }
  }

  private fun parts(rel: String) = rel.split('/').filter { it.isNotEmpty() && it != "." }

  /** The document id of a relative path, or null if any part is absent. */
  private fun resolve(ctx: Context, tree: Uri, rel: String): String? {
    var id = DocumentsContract.getTreeDocumentId(tree)
    for (p in parts(rel)) {
      id = children(ctx, tree, id)?.firstOrNull { it.name == p }?.id ?: return null
    }
    return id
  }

  private fun split(rel: String): Pair<String, String> {
    val p = parts(rel)
    return p.dropLast(1).joinToString("/") to (p.lastOrNull() ?: "")
  }

  private fun docUri(tree: Uri, id: String) =
    DocumentsContract.buildDocumentUriUsingTree(tree, id)

  @JvmStatic
  fun open(ctx: Context, treeUri: String, rel: String, write: Boolean): Int {
    return try {
      val tree = Uri.parse(treeUri)
      var id = resolve(ctx, tree, rel)
      if (id == null) {
        if (!write) return -ENOENT
        val (dir, name) = split(rel)
        val parent = resolve(ctx, tree, dir) ?: return -ENOENT
        val made = DocumentsContract.createDocument(
          ctx.contentResolver, docUri(tree, parent), "application/octet-stream", name)
          ?: return -EIO
        id = DocumentsContract.getDocumentId(made)
      }
      val pfd = ctx.contentResolver.openFileDescriptor(
        docUri(tree, id!!), if (write) "rwt" else "r") ?: return -EIO
      pfd.detachFd()
    } catch (e: java.io.FileNotFoundException) {
      -ENOENT
    } catch (e: Exception) {
      Log.w(TAG, "open $rel: ${e.message}")
      -EIO
    }
  }

  /** Replaces [to] with [from]; both in one folder. */
  @JvmStatic
  fun rename(ctx: Context, treeUri: String, from: String, to: String): Int {
    return try {
      val tree = Uri.parse(treeUri)
      val (fromDir, _) = split(from)
      val (toDir, toName) = split(to)
      if (fromDir != toDir) return -EXDEV
      val src = resolve(ctx, tree, from) ?: return -ENOENT
      resolve(ctx, tree, to)?.let {
        DocumentsContract.deleteDocument(ctx.contentResolver, docUri(tree, it))
      }
      val moved = DocumentsContract.renameDocument(
        ctx.contentResolver, docUri(tree, src), toName) ?: return -EIO
      // A provider that would not take the name exactly has made a copy name.
      val got = resolve(ctx, tree, to)
      if (got == null) {
        Log.w(TAG, "rename $from -> $to gave ${moved.lastPathSegment}")
        return -EIO
      }
      0
    } catch (e: Exception) {
      Log.w(TAG, "rename $from -> $to: ${e.message}")
      -EIO
    }
  }

  @JvmStatic
  fun unlink(ctx: Context, treeUri: String, rel: String): Int {
    return try {
      val tree = Uri.parse(treeUri)
      val id = resolve(ctx, tree, rel) ?: return -ENOENT
      if (DocumentsContract.deleteDocument(ctx.contentResolver, docUri(tree, id))) 0 else -EIO
    } catch (e: Exception) {
      Log.w(TAG, "unlink $rel: ${e.message}")
      -EIO
    }
  }

  /** Makes every missing folder along [rel]; 0 if it already exists. */
  @JvmStatic
  fun mkdir(ctx: Context, treeUri: String, rel: String): Int {
    return try {
      val tree = Uri.parse(treeUri)
      var id = DocumentsContract.getTreeDocumentId(tree)
      for (p in parts(rel)) {
        val found = children(ctx, tree, id)?.firstOrNull { it.name == p }
        id = when {
          found == null -> {
            val made = DocumentsContract.createDocument(ctx.contentResolver,
              docUri(tree, id), DocumentsContract.Document.MIME_TYPE_DIR, p) ?: return -EIO
            DocumentsContract.getDocumentId(made)
          }
          found.dir -> found.id
          else -> return -EEXIST
        }
      }
      0
    } catch (e: Exception) {
      Log.w(TAG, "mkdir $rel: ${e.message}")
      -EIO
    }
  }

  /** "name\tsize\tmtime_ms\tkind\n" per entry, kind 'd' or 'f'; null if absent. */
  @JvmStatic
  fun list(ctx: Context, treeUri: String, rel: String): String? {
    return try {
      val tree = Uri.parse(treeUri)
      val id = resolve(ctx, tree, rel) ?: return null
      val kids = children(ctx, tree, id) ?: return null
      buildString {
        for (k in kids) {
          append(k.name).append('\t').append(k.size).append('\t').append(k.mtime)
            .append('\t').append(if (k.dir) 'd' else 'f').append('\n')
        }
      }
    } catch (e: Exception) {
      Log.w(TAG, "list $rel: ${e.message}")
      null
    }
  }

  /** A readable form of a picked folder, for the settings screen. */
  fun describe(treeUri: String): String {
    return try {
      val id = DocumentsContract.getTreeDocumentId(Uri.parse(treeUri))
      val colon = id.indexOf(':')
      if (colon < 0) id else {
        val vol = id.substring(0, colon)
        val path = id.substring(colon + 1)
        (if (vol == "primary") "Internal storage" else vol) + "/" + path
      }
    } catch (e: Exception) {
      treeUri
    }
  }
}
