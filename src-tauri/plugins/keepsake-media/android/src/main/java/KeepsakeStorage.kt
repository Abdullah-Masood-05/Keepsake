package app.keepsake.media

import android.content.ContentUris
import android.content.ContentValues
import android.content.Context
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.os.Environment
import android.provider.DocumentsContract
import android.provider.MediaStore
import android.provider.OpenableColumns
import android.media.MediaScannerConnection
import android.webkit.MimeTypeMap
import androidx.core.content.ContextCompat
import androidx.core.content.FileProvider
import java.io.File
import java.io.FileInputStream
import java.io.FileOutputStream
import java.io.IOException
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import org.json.JSONObject

/**
 * Storage permission state, "which folder did this file come from" and "save into folder X" helpers.
 * Blocking; call from a worker thread (except the permission helpers). Errors are [MediaError] with codes
 * "not_writable", "source_missing", "permission", "no_space", "bad_args", "unknown".
 */
internal object KeepsakeStorage {
    private const val BUF = 64 * 1024
    private const val PREFS = "PluginPermStates" // written by Tauri's PluginHandle after each request

    const val READ_MEDIA_VIDEO = "android.permission.READ_MEDIA_VIDEO"
    const val READ_MEDIA_IMAGES = "android.permission.READ_MEDIA_IMAGES"
    const val READ_MEDIA_AUDIO = "android.permission.READ_MEDIA_AUDIO"
    const val READ_EXTERNAL = "android.permission.READ_EXTERNAL_STORAGE"
    const val WRITE_EXTERNAL = "android.permission.WRITE_EXTERNAL_STORAGE"

    private val IMAGE_VIDEO_TOPS = setOf("DCIM", "Pictures", "Movies")
    private val AUDIO_TOPS = setOf("Music", "Podcasts", "Ringtones", "Alarms", "Notifications", "Audiobooks", "Recordings")

    // ---------------- permissions ----------------

    /** Permissions that make up "full storage access" on this API level (also the list we request). */
    fun requiredPermissions(): List<String> = when {
        Build.VERSION.SDK_INT >= 33 -> listOf(READ_MEDIA_VIDEO, READ_MEDIA_IMAGES, READ_MEDIA_AUDIO)
        Build.VERSION.SDK_INT >= 29 -> listOf(READ_EXTERNAL)
        else -> listOf(READ_EXTERNAL, WRITE_EXTERNAL)
    }

    private fun held(context: Context, perm: String): Boolean =
        ContextCompat.checkSelfPermission(context, perm) == PackageManager.PERMISSION_GRANTED

    private fun missing(context: Context): List<String> = requiredPermissions().filter { !held(context, it) }

    fun isGranted(context: Context): Boolean = missing(context).isEmpty()

    /** True when a missing permission was denied with "don't ask again" (Tauri caches that state). */
    fun isPermanentlyDenied(context: Context): Boolean {
        val miss = missing(context)
        if (miss.isEmpty()) return false
        val prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        return miss.any { prefs.getString(it, null) == "denied" }
    }

    // ---------------- source folder ----------------

    /** @return {relativePath: string|null, displayPath: string|null, writable: boolean} */
    fun sourceFolder(context: Context, raw: String): JSONObject {
        val rel = try {
            resolveRelative(context, raw)
        } catch (ignored: Throwable) {
            null
        }
        return JSONObject().apply {
            put("relativePath", rel ?: JSONObject.NULL)
            put("displayPath", rel?.trimEnd('/') ?: JSONObject.NULL)
            put("writable", rel != null && isWritable(context, rel))
        }
    }

    private fun isWritable(context: Context, rel: String): Boolean {
        if (Build.VERSION.SDK_INT <= 28) {
            return held(context, WRITE_EXTERNAL) && !rel.startsWith("Android/")
        }
        val top = rel.substringBefore('/')
        return top == "Download" || top in IMAGE_VIDEO_TOPS || audioTopAllowed(top)
    }

    private fun audioTopAllowed(top: String): Boolean =
        top in AUDIO_TOPS && (top != "Recordings" || Build.VERSION.SDK_INT >= 31)

    /** "DCIM/Camera/" style: no leading slash, one trailing slash, no "." or ".." segments; null when empty/unsafe. */
    fun normDir(raw: String?): String? {
        if (raw == null) return null
        val parts = raw.replace('\\', '/').split('/').filter { it.isNotEmpty() }
        if (parts.isEmpty() || parts.any { it == ".." || it == "." || it.contains('\u0000') }) return null
        return parts.joinToString("/") + "/"
    }

    @Suppress("DEPRECATION")
    private fun fromAbsolute(path: String): String? {
        val roots = listOf(
            Environment.getExternalStorageDirectory().path,
            "/storage/emulated/0",
            "/storage/self/primary",
            "/sdcard",
        )
        for (r in roots) {
            val prefix = r.trimEnd('/') + "/"
            if (path.startsWith(prefix)) {
                val rest = path.substring(prefix.length)
                return normDir(rest.substringBeforeLast('/', ""))
            }
        }
        return null
    }

    private fun fromDocumentId(id: String?, isDir: Boolean): String? {
        if (id == null) return null
        val colon = id.indexOf(':')
        if (colon < 0 || id.substring(0, colon) != "primary") return null // other volumes: not saved to primary
        val path = id.substring(colon + 1)
        return normDir(if (isDir) path else path.substringBeforeLast('/', ""))
    }

    private fun resolveRelative(context: Context, raw: String): String? {
        if (raw.startsWith("/")) return fromAbsolute(raw)
        val uri = Uri.parse(raw)
        if (uri.scheme == "file") return uri.path?.let { fromAbsolute(it) }
        if (uri.scheme != "content") return null
        return when (uri.authority) {
            "com.android.externalstorage.documents" -> {
                val isDoc = DocumentsContract.isDocumentUri(context, uri)
                val id = try {
                    if (isDoc) DocumentsContract.getDocumentId(uri) else DocumentsContract.getTreeDocumentId(uri)
                } catch (e: IllegalArgumentException) {
                    null
                }
                fromDocumentId(id, !isDoc)
            }
            "com.android.providers.media.documents" -> {
                val id = documentId(uri) ?: return null
                val type = id.substringBefore(':')
                val rowId = id.substringAfter(':', "").toLongOrNull() ?: return null
                val base = when (type) {
                    "video" -> MediaStore.Video.Media.EXTERNAL_CONTENT_URI
                    "audio" -> MediaStore.Audio.Media.EXTERNAL_CONTENT_URI
                    "image" -> MediaStore.Images.Media.EXTERNAL_CONTENT_URI
                    else -> filesUri()
                }
                mediaRowFolder(context, ContentUris.withAppendedId(base, rowId), null)
            }
            "com.android.providers.downloads.documents" -> {
                val id = documentId(uri) ?: return null
                if (id.startsWith("raw:")) return fromAbsolute(id.removePrefix("raw:"))
                val rowId = id.substringAfter(':', id).toLongOrNull() ?: return null
                mediaRowFolder(context, ContentUris.withAppendedId(filesUri(), rowId), null)
            }
            "media" -> {
                val segs = uri.pathSegments
                if (segs.contains("picker") || segs.contains("picker_get_content")) {
                    // Photo-picker URI: its last segment is the MediaStore id for local items. Verify by
                    // display name so a cloud item can never map to an unrelated local file.
                    val rowId = segs.lastOrNull()?.toLongOrNull() ?: return null
                    val name = displayName(context, uri) ?: return null
                    mediaRowFolder(context, ContentUris.withAppendedId(filesUri(), rowId), name)
                } else {
                    mediaRowFolder(context, uri, null)
                }
            }
            else -> null
        }
    }

    private fun documentId(uri: Uri): String? = try {
        DocumentsContract.getDocumentId(uri)
    } catch (e: IllegalArgumentException) {
        null
    }

    private fun filesUri(): Uri = MediaStore.Files.getContentUri("external")

    private fun displayName(context: Context, uri: Uri): String? = try {
        context.contentResolver.query(uri, arrayOf(OpenableColumns.DISPLAY_NAME), null, null, null)?.use { c ->
            if (c.moveToFirst() && !c.isNull(0)) c.getString(0) else null
        }
    } catch (ignored: Throwable) {
        null
    }

    /** Folder of a MediaStore row (primary volume only). [expectName] must match when given. */
    @Suppress("DEPRECATION")
    private fun mediaRowFolder(context: Context, uri: Uri, expectName: String?): String? {
        val proj = mutableListOf(MediaStore.MediaColumns.DATA, MediaStore.MediaColumns.DISPLAY_NAME)
        if (Build.VERSION.SDK_INT >= 29) {
            proj.add(MediaStore.MediaColumns.RELATIVE_PATH)
            proj.add(MediaStore.MediaColumns.VOLUME_NAME)
        }
        return context.contentResolver.query(uri, proj.toTypedArray(), null, null, null)?.use { c ->
            if (!c.moveToFirst()) return@use null
            fun str(col: String): String? {
                val i = c.getColumnIndex(col)
                return if (i < 0 || c.isNull(i)) null else c.getString(i)
            }
            if (expectName != null && str(MediaStore.MediaColumns.DISPLAY_NAME) != expectName) return@use null
            if (Build.VERSION.SDK_INT >= 29) {
                val vol = str(MediaStore.MediaColumns.VOLUME_NAME)
                if (vol != null && vol != MediaStore.VOLUME_EXTERNAL_PRIMARY) return@use null
                normDir(str(MediaStore.MediaColumns.RELATIVE_PATH))?.let { return@use it }
            }
            str(MediaStore.MediaColumns.DATA)?.let { fromAbsolute(it) }
        }
    }

    // ---------------- save ----------------

    /**
     * Copies [src] into the shared [relRaw] folder (e.g. "Download/Keepsake/") through MediaStore (API 29+) or
     * a direct write (API 24-28). Deletes [src] only after success.
     * @return {uri, displayPath}
     */
    fun save(context: Context, src: File, relRaw: String, displayName: String, mimeIn: String?): JSONObject {
        val rel = normDir(relRaw) ?: throw MediaError("Invalid folder: $relRaw", "bad_args")
        if (displayName.isEmpty() || displayName.contains('/') || displayName.contains('\\') || displayName == "." || displayName == "..") {
            throw MediaError("Invalid file name: $displayName", "bad_args")
        }
        if (!src.isFile) throw MediaError("Source file is missing: ${src.path}", "source_missing")
        val mime = mimeIn?.takeIf { it.contains('/') }
            ?: MimeTypeMap.getSingleton().getMimeTypeFromExtension(displayName.substringAfterLast('.', "").lowercase())
            ?: "application/octet-stream"
        try {
            KeepsakeGallery.checkSpace(src.length())
            val out = if (Build.VERSION.SDK_INT >= 29) {
                saveQ(context, src, rel, displayName, mime)
            } else {
                saveLegacy(context, src, rel, displayName, mime)
            }
            src.delete()
            return out
        } catch (e: MediaError) {
            throw e
        } catch (e: Throwable) {
            throw mapError(e)
        }
    }

    private fun mapError(e: Throwable): MediaError {
        val msg = e.message ?: e.javaClass.simpleName
        return when {
            e is SecurityException -> MediaError(msg, "permission")
            e is IOException && (msg.contains("ENOSPC") || msg.contains("No space", true)) -> MediaError(msg, "no_space")
            else -> MediaError(msg, "unknown")
        }
    }

    private fun collectionFor(rel: String, mime: String): Uri {
        val top = rel.substringBefore('/')
        val fam = mime.substringBefore('/').lowercase()
        val vol = MediaStore.VOLUME_EXTERNAL_PRIMARY
        return when {
            top == "Download" -> MediaStore.Downloads.getContentUri(vol)
            top in IMAGE_VIDEO_TOPS && fam == "image" -> MediaStore.Images.Media.getContentUri(vol)
            top in IMAGE_VIDEO_TOPS && fam == "video" -> MediaStore.Video.Media.getContentUri(vol)
            audioTopAllowed(top) && fam == "audio" -> MediaStore.Audio.Media.getContentUri(vol)
            else -> throw MediaError("Keepsake can't save $mime files into $rel.", "not_writable")
        }
    }

    private fun saveQ(context: Context, src: File, rel: String, name: String, mime: String): JSONObject {
        val resolver = context.contentResolver
        val collection = collectionFor(rel, mime)
        val now = System.currentTimeMillis() / 1000
        val values = ContentValues().apply {
            put(MediaStore.MediaColumns.DISPLAY_NAME, name)
            put(MediaStore.MediaColumns.MIME_TYPE, mime)
            put(MediaStore.MediaColumns.RELATIVE_PATH, rel.trimEnd('/'))
            put(MediaStore.MediaColumns.IS_PENDING, 1)
            put(MediaStore.MediaColumns.DATE_ADDED, now)
            put(MediaStore.MediaColumns.DATE_MODIFIED, now)
        }
        // MediaStore itself renames to "name (1).ext" when the name is taken in that folder.
        val uri = try {
            resolver.insert(collection, values)
        } catch (e: IllegalArgumentException) {
            throw MediaError("Keepsake can't save into $rel: ${e.message}", "not_writable")
        } ?: throw MediaError("Could not create an entry in $rel.", "not_writable")
        try {
            val os = resolver.openOutputStream(uri, "w")
                ?: throw MediaError("Could not open the new entry in $rel.", "unknown")
            os.use { o ->
                FileInputStream(src).use { it.copyTo(o, BUF) }
                o.flush()
            }
            val done = ContentValues().apply { put(MediaStore.MediaColumns.IS_PENDING, 0) }
            if (resolver.update(uri, done, null, null) < 1) {
                throw MediaError("Could not finish the new entry in $rel.", "unknown")
            }
            var actual = name
            resolver.query(uri, arrayOf(MediaStore.MediaColumns.DISPLAY_NAME), null, null, null)?.use { c ->
                if (c.moveToFirst()) c.getString(0)?.let { actual = it }
            }
            return JSONObject().apply {
                put("uri", uri.toString())
                put("displayPath", rel + actual)
            }
        } catch (e: Throwable) {
            try { resolver.delete(uri, null, null) } catch (ignored: Throwable) {}
            throw if (e is MediaError) e else mapError(e)
        }
    }

    @Suppress("DEPRECATION")
    private fun saveLegacy(context: Context, src: File, rel: String, name: String, mime: String): JSONObject {
        if (!held(context, WRITE_EXTERNAL)) throw MediaError("Storage permission is not granted.", "permission")
        if (rel.startsWith("Android/")) throw MediaError("Keepsake can't save into $rel.", "not_writable")
        val dir = File(Environment.getExternalStorageDirectory(), rel)
        if (!dir.isDirectory && !dir.mkdirs()) throw MediaError("Could not create ${dir.path}.", "not_writable")
        val dest = KeepsakeGallery.uniqueFile(dir, name)
        val part = File(dir, dest.name + ".part")
        try {
            FileInputStream(src).use { i -> FileOutputStream(part).use { o -> i.copyTo(o, BUF); o.flush() } }
            if (!part.renameTo(dest)) throw MediaError("Could not finalise file.", "unknown")
        } catch (e: Throwable) {
            part.delete()
            dest.delete()
            throw if (e is MediaError) e else mapError(e)
        }
        val latch = CountDownLatch(1)
        var scanned: Uri? = null
        MediaScannerConnection.scanFile(context, arrayOf(dest.absolutePath), arrayOf(mime)) { _, u ->
            scanned = u
            latch.countDown()
        }
        latch.await(10, TimeUnit.SECONDS)
        val uriStr = scanned?.takeIf { it.scheme == "content" }?.toString()
            ?: KeepsakeGallery.legacyMediaUri(context, dest)?.toString()
            ?: try {
                FileProvider.getUriForFile(context, "${context.packageName}.keepsake.fileprovider", dest).toString()
            } catch (ignored: Exception) {
                dest.absolutePath
            }
        return JSONObject().apply {
            put("uri", uriStr)
            put("displayPath", rel + dest.name)
        }
    }
}
