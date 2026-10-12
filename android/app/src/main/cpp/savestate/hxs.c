/*
 * Save states as files (#433). See hxs.h for the layout on disk.
 *
 * File format, little-endian:
 *   header (48 bytes): "HXS1", u32 header length, u32 codec, u32 level,
 *       u64 stream length, u64 payload length, u32 metadata length,
 *       u32 chunk size, u32 flags, u32 reserved
 *   payload: the stream as is (codec none), or chunks of at most 1 MiB, each
 *       [u32 raw length][u32 stored length][data], stored as is when the
 *       stored length equals the raw length
 *   metadata: u32 count, then per entry u8 key length, key, u16 value
 *       length, value
 *   trailer: "HXSE", u32 metadata length
 * A file is complete when its size is exactly header + payload + metadata +
 * trailer and the trailer matches; the header is written last, so a file cut
 * short anywhere is never mistaken for a complete one.
 *
 * Every file is written as <name>.tmp, fsynced, and renamed into place. A
 * numbered slot's previous file becomes undo-save.hxs. In mode c the raw
 * file is placed first, then the worker writes <name>.z.tmp and renames it
 * over the raw file, which is therefore deleted only once the compressed
 * file is complete.
 */
#ifndef _GNU_SOURCE
#define _GNU_SOURCE /* cpu_set_t, sched_getcpu */
#endif
#include "qemu/osdep.h"

#include <android/log.h>
#include <dirent.h>
#include <pthread.h>
#include <sched.h>
#include <sys/resource.h>
#include <sys/stat.h>
#include <sys/syscall.h>

#include "hxs.h"
#include "lz4/lz4.h"
#include "zstd/zstd.h"

#include "block/accounting.h"
#include "block/aio.h"
#include "block/block.h"
#include "block/block-io.h"
#include "block/block_int.h"
#include "block/snapshot.h"
#include "hw/boards.h"
#include "io/channel-buffer.h"
#include "io/channel-file.h"
#include "migration/global_state.h"
#include "migration/qemu-file.h"
#include "qapi/error.h"
#include "qemu/bswap.h"
#include "qemu/cutils.h"
#include "qemu/main-loop.h"
#include "qemu/thread.h"
#include "qemu/timer.h"
#include "system/block-backend.h"
#include "system/runstate.h"
#include "ui/xemu-snapshots.h"

#define HXS_LOG(...) \
    __android_log_print(ANDROID_LOG_INFO, "hakuX-lane", __VA_ARGS__)

#define HXS_HDR_LEN 48
#define HXS_TRAILER_LEN 8
#define HXS_CHUNK (1u << 20)
#define HXS_FLAG_CHUNKED 1u
#define HXS_MAX_THREADS 4
#define HXS_CTX_WORKER HXS_MAX_THREADS
#define HXS_JOB_RING 16

/*
 * What "On" stands for, chosen from the measurements in
 * docs/lanes/savestate1011/NOTES.md.
 */
#define HXS_ON_MODE HXS_MODE_INLINE
#define HXS_ON_CODEC HXS_CODEC_ZSTD
#define HXS_ON_LEVEL 1
#define HXS_ON_THREADS 4

static const char *const mode_names[] = { "raw", "inline", "background",
                                          "deferred" };
static const char *const codec_names[] = { "none", "lz4", "zstd" };

static const char *mode_name(int m)
{
    return m >= 0 && m < 4 ? mode_names[m] : "?";
}

static const char *codec_name(int c)
{
    return c >= 0 && c < 3 ? codec_names[c] : "?";
}

/* ---------------------------------------------------------------- time */

static int64_t now_us(void)
{
    return g_get_monotonic_time();
}

static int64_t thread_cpu_us(void)
{
    struct timespec ts;
    clock_gettime(CLOCK_THREAD_CPUTIME_ID, &ts);
    return ts.tv_sec * 1000000LL + ts.tv_nsec / 1000;
}

static void sleep_ms(int64_t ms)
{
    if (ms > 0) {
        g_usleep(ms * 1000);
    }
}

/* -------------------------------------------------------- configuration */

/* Guards the configuration, the job queue and every rename in the root. */
static pthread_mutex_t hxs_mu = PTHREAD_MUTEX_INITIALIZER;
static pthread_cond_t hxs_cv = PTHREAD_COND_INITIALIZER;
/* One save, load, undo, delete or listing at a time. */
static pthread_mutex_t hxs_op_mu = PTHREAD_MUTEX_INITIALIZER;

static char *cfg_root;
static HxsStoreOps cfg_ops;
static bool cfg_has_ops;
static char *cfg_label;
static char cfg_root8[9] = "00000000";
static bool cfg_compression = true;
static bool cfg_auto_load;
static char *cfg_boot_title;
static bool cfg_testing;
static char *auto_load_msg;
static int inline_threads = HXS_ON_THREADS;

/* The title the last identity check saw, for the cheap can-undo queries. */
static char *last_title;

/* Test hooks: a metadata value written in place of the real one. */
static char *test_meta_key;
static char *test_meta_val;

static void set_root_id(const char *label)
{
    char *h = g_compute_checksum_for_string(G_CHECKSUM_SHA256, label, -1);
    memcpy(cfg_root8, h, 8);
    cfg_root8[8] = 0;
    g_free(h);
}

void hxs_set_root(const char *posix_dir)
{
    pthread_mutex_lock(&hxs_mu);
    g_free(cfg_root);
    cfg_root = g_strdup(posix_dir);
    cfg_has_ops = false;
    g_free(cfg_label);
    cfg_label = g_strdup(posix_dir);
    set_root_id(cfg_label);
    pthread_mutex_unlock(&hxs_mu);
}

void hxs_set_store(const HxsStoreOps *ops, const char *label)
{
    pthread_mutex_lock(&hxs_mu);
    cfg_ops = *ops;
    cfg_has_ops = true;
    g_free(cfg_root);
    cfg_root = NULL;
    g_free(cfg_label);
    cfg_label = g_strdup(label);
    set_root_id(cfg_label);
    pthread_mutex_unlock(&hxs_mu);
}

void hxs_set_compression(bool on)
{
    pthread_mutex_lock(&hxs_mu);
    cfg_compression = on;
    pthread_mutex_unlock(&hxs_mu);
}

bool hxs_get_compression(void)
{
    pthread_mutex_lock(&hxs_mu);
    bool on = cfg_compression;
    pthread_mutex_unlock(&hxs_mu);
    return on;
}

void hxs_set_auto_load(bool on)
{
    pthread_mutex_lock(&hxs_mu);
    cfg_auto_load = on;
    pthread_mutex_unlock(&hxs_mu);
}

void hxs_set_boot_title(const char *title_id)
{
    pthread_mutex_lock(&hxs_mu);
    g_free(cfg_boot_title);
    cfg_boot_title = title_id && *title_id ? g_ascii_strdown(title_id, -1)
                                           : NULL;
    pthread_mutex_unlock(&hxs_mu);
}

const char *hxs_root_label(void)
{
    return cfg_label ? cfg_label : "";
}

void hxs_default_mode(bool compression, int *mode, int *codec, int *level)
{
    if (compression) {
        *mode = HXS_ON_MODE;
        *codec = HXS_ON_CODEC;
        *level = HXS_ON_LEVEL;
    } else {
        *mode = HXS_MODE_RAW;
        *codec = HXS_CODEC_NONE;
        *level = 0;
    }
}

const char *hxs_auto_load_message(void)
{
    pthread_mutex_lock(&hxs_mu);
    const char *m = auto_load_msg;
    pthread_mutex_unlock(&hxs_mu);
    return m;
}

static void set_auto_load_msg(char *msg)
{
    pthread_mutex_lock(&hxs_mu);
    /* The previous message is kept alive: the frontend may still hold it. */
    auto_load_msg = msg;
    pthread_mutex_unlock(&hxs_mu);
}

static bool have_root(void)
{
    return cfg_has_ops || cfg_root;
}

/* ---------------------------------------------------------------- store */

static char *st_path(const char *rel)
{
    return g_build_filename(cfg_root, rel, NULL);
}

static int st_open(const char *rel, bool write)
{
    if (cfg_has_ops) {
        return cfg_ops.open(rel, write);
    }
    g_autofree char *p = st_path(rel);
    int fd = open(p, write ? O_RDWR | O_CREAT | O_TRUNC | O_CLOEXEC
                           : O_RDONLY | O_CLOEXEC, 0644);
    return fd >= 0 ? fd : -errno;
}

static int st_rename(const char *from, const char *to)
{
    if (cfg_has_ops) {
        return cfg_ops.rename(from, to);
    }
    g_autofree char *pf = st_path(from);
    g_autofree char *pt = st_path(to);
    return rename(pf, pt) < 0 ? -errno : 0;
}

static int st_unlink(const char *rel)
{
    if (cfg_has_ops) {
        return cfg_ops.unlink(rel);
    }
    g_autofree char *p = st_path(rel);
    return unlink(p) < 0 && errno != ENOENT ? -errno : 0;
}

static int st_mkdir(const char *rel)
{
    if (cfg_has_ops) {
        return cfg_ops.mkdir(rel);
    }
    g_autofree char *p = st_path(rel);
    return g_mkdir_with_parents(p, 0755) < 0 ? -errno : 0;
}

/* Makes a rename in this folder durable. */
static void st_sync_dir(const char *rel)
{
    if (cfg_has_ops) {
        return;
    }
    g_autofree char *p = st_path(rel);
    int fd = open(p, O_RDONLY | O_DIRECTORY | O_CLOEXEC);
    if (fd >= 0) {
        fsync(fd);
        close(fd);
    }
}

static bool st_exists(const char *rel)
{
    if (!cfg_has_ops) {
        g_autofree char *p = st_path(rel);
        return access(p, F_OK) == 0;
    }
    int fd = st_open(rel, false);
    if (fd >= 0) {
        close(fd);
    }
    return fd >= 0;
}

typedef struct StEnt {
    char *name;
    int64_t size;
    int64_t mtime_ms;
    bool dir;
} StEnt;

static void stent_clear(gpointer p)
{
    g_free(((StEnt *)p)->name);
}

/* The entries of a folder, or NULL when it cannot be listed. */
static GArray *st_list(const char *rel)
{
    GArray *a = g_array_new(false, true, sizeof(StEnt));
    g_array_set_clear_func(a, stent_clear);

    if (cfg_has_ops) {
        char *s = cfg_ops.list(rel);
        if (!s) {
            g_array_unref(a);
            return NULL;
        }
        char **lines = g_strsplit(s, "\n", -1);
        free(s);
        for (char **l = lines; *l; l++) {
            char **f = g_strsplit(*l, "\t", 4);
            if (g_strv_length(f) == 4 && *f[0]) {
                StEnt e = {
                    .name = g_strdup(f[0]),
                    .size = g_ascii_strtoll(f[1], NULL, 10),
                    .mtime_ms = g_ascii_strtoll(f[2], NULL, 10),
                    .dir = f[3][0] == 'd',
                };
                g_array_append_val(a, e);
            }
            g_strfreev(f);
        }
        g_strfreev(lines);
        return a;
    }

    g_autofree char *p = st_path(rel);
    DIR *d = opendir(p);
    if (!d) {
        g_array_unref(a);
        return NULL;
    }
    struct dirent *de;
    while ((de = readdir(d))) {
        struct stat sb;
        if (!strcmp(de->d_name, ".") || !strcmp(de->d_name, "..") ||
            fstatat(dirfd(d), de->d_name, &sb, 0) < 0) {
            continue;
        }
        StEnt e = {
            .name = g_strdup(de->d_name),
            .size = sb.st_size,
            .mtime_ms = sb.st_mtim.tv_sec * 1000LL +
                        sb.st_mtim.tv_nsec / 1000000,
            .dir = S_ISDIR(sb.st_mode),
        };
        g_array_append_val(a, e);
    }
    closedir(d);
    return a;
}

static int pwrite_full(int fd, const void *buf, size_t n, off_t off)
{
    const uint8_t *p = buf;
    while (n) {
        ssize_t r = pwrite(fd, p, n, off);
        if (r < 0) {
            if (errno == EINTR) {
                continue;
            }
            return -errno;
        }
        p += r;
        n -= r;
        off += r;
    }
    return 0;
}

static int pread_full(int fd, void *buf, size_t n, off_t off)
{
    uint8_t *p = buf;
    while (n) {
        ssize_t r = pread(fd, p, n, off);
        if (r < 0) {
            if (errno == EINTR) {
                continue;
            }
            return -errno;
        }
        if (r == 0) {
            return -EIO;
        }
        p += r;
        n -= r;
        off += r;
    }
    return 0;
}

static char *read_text(const char *rel)
{
    int fd = st_open(rel, false);
    if (fd < 0) {
        return NULL;
    }
    struct stat sb;
    char *s = NULL;
    if (fstat(fd, &sb) == 0 && sb.st_size < (1 << 20)) {
        s = g_malloc0(sb.st_size + 1);
        if (pread_full(fd, s, sb.st_size, 0) < 0) {
            g_free(s);
            s = NULL;
        }
    }
    close(fd);
    return s;
}

static int write_text_atomic(const char *rel, const char *text)
{
    g_autofree char *tmp = g_strconcat(rel, ".tmp", NULL);
    int fd = st_open(tmp, true);
    if (fd < 0) {
        return fd;
    }
    int r = pwrite_full(fd, text, strlen(text), 0);
    if (r == 0 && fsync(fd) < 0) {
        r = -errno;
    }
    close(fd);
    if (r == 0) {
        r = st_rename(tmp, rel);
    }
    if (r < 0) {
        st_unlink(tmp);
    }
    return r;
}

/* ------------------------------------------------------------ metadata */

typedef struct Meta {
    GPtrArray *k;
    GPtrArray *v;
} Meta;

static Meta *meta_new(void)
{
    Meta *m = g_new0(Meta, 1);
    m->k = g_ptr_array_new_with_free_func(g_free);
    m->v = g_ptr_array_new_with_free_func(g_free);
    return m;
}

static void meta_free(Meta *m)
{
    if (m) {
        g_ptr_array_free(m->k, true);
        g_ptr_array_free(m->v, true);
        g_free(m);
    }
}

static const char *meta_get(const Meta *m, const char *key)
{
    for (guint i = 0; m && i < m->k->len; i++) {
        if (!strcmp(g_ptr_array_index(m->k, i), key)) {
            return g_ptr_array_index(m->v, i);
        }
    }
    return NULL;
}

static void meta_set(Meta *m, const char *key, const char *val)
{
    if (test_meta_key && !strcmp(key, test_meta_key)) {
        val = test_meta_val;
    }
    val = val ? val : "";
    for (guint i = 0; i < m->k->len; i++) {
        if (!strcmp(g_ptr_array_index(m->k, i), key)) {
            g_free(m->v->pdata[i]);
            m->v->pdata[i] = g_strdup(val);
            return;
        }
    }
    g_ptr_array_add(m->k, g_strdup(key));
    g_ptr_array_add(m->v, g_strdup(val));
}

static void meta_setf(Meta *m, const char *key, const char *fmt, ...)
    G_GNUC_PRINTF(3, 4);
static void meta_setf(Meta *m, const char *key, const char *fmt, ...)
{
    va_list ap;
    va_start(ap, fmt);
    char *v = g_strdup_vprintf(fmt, ap);
    va_end(ap);
    meta_set(m, key, v);
    g_free(v);
}

static Meta *meta_copy(const Meta *src)
{
    Meta *m = meta_new();
    for (guint i = 0; i < src->k->len; i++) {
        g_ptr_array_add(m->k, g_strdup(g_ptr_array_index(src->k, i)));
        g_ptr_array_add(m->v, g_strdup(g_ptr_array_index(src->v, i)));
    }
    return m;
}

static GByteArray *meta_encode(const Meta *m)
{
    GByteArray *b = g_byte_array_new();
    uint8_t n[4];
    stl_le_p(n, m->k->len);
    g_byte_array_append(b, n, 4);
    for (guint i = 0; i < m->k->len; i++) {
        const char *k = g_ptr_array_index(m->k, i);
        const char *v = g_ptr_array_index(m->v, i);
        uint8_t kl = MIN(strlen(k), 255);
        uint16_t vl = MIN(strlen(v), 65535);
        uint8_t v2[2];
        g_byte_array_append(b, &kl, 1);
        g_byte_array_append(b, (const uint8_t *)k, kl);
        stw_le_p(v2, vl);
        g_byte_array_append(b, v2, 2);
        g_byte_array_append(b, (const uint8_t *)v, vl);
    }
    return b;
}

static Meta *meta_decode(const uint8_t *p, size_t n)
{
    if (n < 4) {
        return NULL;
    }
    uint32_t count = ldl_le_p(p);
    size_t pos = 4;
    Meta *m = meta_new();
    for (uint32_t i = 0; i < count; i++) {
        if (pos + 1 > n) {
            goto bad;
        }
        uint8_t kl = p[pos++];
        if (pos + kl + 2 > n) {
            goto bad;
        }
        char *k = g_strndup((const char *)p + pos, kl);
        pos += kl;
        uint16_t vl = lduw_le_p(p + pos);
        pos += 2;
        if (pos + vl > n) {
            g_free(k);
            goto bad;
        }
        g_ptr_array_add(m->k, k);
        g_ptr_array_add(m->v, g_strndup((const char *)p + pos, vl));
        pos += vl;
    }
    return m;
bad:
    meta_free(m);
    return NULL;
}

/* -------------------------------------------------------------- format */

typedef struct FileHdr {
    uint32_t codec;
    uint32_t level;
    uint64_t raw_len;
    uint64_t payload_len;
    uint32_t meta_len;
    uint32_t chunk;
    uint32_t flags;
} FileHdr;

static void hdr_encode(const FileHdr *h, uint8_t out[HXS_HDR_LEN])
{
    memcpy(out, "HXS1", 4);
    stl_le_p(out + 4, HXS_HDR_LEN);
    stl_le_p(out + 8, h->codec);
    stl_le_p(out + 12, h->level);
    stq_le_p(out + 16, h->raw_len);
    stq_le_p(out + 24, h->payload_len);
    stl_le_p(out + 32, h->meta_len);
    stl_le_p(out + 36, h->chunk);
    stl_le_p(out + 40, h->flags);
    stl_le_p(out + 44, 0);
}

static bool hdr_decode(const uint8_t in[HXS_HDR_LEN], FileHdr *h)
{
    if (memcmp(in, "HXS1", 4) || ldl_le_p(in + 4) != HXS_HDR_LEN) {
        return false;
    }
    h->codec = ldl_le_p(in + 8);
    h->level = ldl_le_p(in + 12);
    h->raw_len = ldq_le_p(in + 16);
    h->payload_len = ldq_le_p(in + 24);
    h->meta_len = ldl_le_p(in + 32);
    h->chunk = ldl_le_p(in + 36);
    h->flags = ldl_le_p(in + 40);
    return h->codec <= HXS_CODEC_ZSTD;
}

/* Writes the metadata, the trailer and the header, then fsyncs. */
static int finish_file(int fd, FileHdr *h, const Meta *m)
{
    GByteArray *mb = meta_encode(m);
    uint8_t tr[HXS_TRAILER_LEN];
    uint8_t hb[HXS_HDR_LEN];
    off_t off = HXS_HDR_LEN + h->payload_len;
    int r;

    h->meta_len = mb->len;
    memcpy(tr, "HXSE", 4);
    stl_le_p(tr + 4, h->meta_len);
    hdr_encode(h, hb);
    r = pwrite_full(fd, mb->data, mb->len, off);
    if (!r) {
        r = pwrite_full(fd, tr, sizeof(tr), off + mb->len);
    }
    if (!r && fsync(fd) < 0) {
        r = -errno;
    }
    /* The header last: until it is there, the file is not complete. */
    if (!r) {
        r = pwrite_full(fd, hb, sizeof(hb), 0);
    }
    if (!r && fsync(fd) < 0) {
        r = -errno;
    }
    g_byte_array_free(mb, true);
    return r;
}

typedef struct FileInfo {
    FileHdr h;
    Meta *meta;
    int64_t size;
} FileInfo;

static void file_info_clear(FileInfo *fi)
{
    meta_free(fi->meta);
    fi->meta = NULL;
}

/* NULL when the file is complete and readable, else the reason. */
static const char *file_info_fd(int fd, FileInfo *fi)
{
    struct stat sb;
    uint8_t hb[HXS_HDR_LEN];
    uint8_t tr[HXS_TRAILER_LEN];

    memset(fi, 0, sizeof(*fi));
    if (fstat(fd, &sb) < 0) {
        return "open-failed";
    }
    fi->size = sb.st_size;
    if (sb.st_size < HXS_HDR_LEN + HXS_TRAILER_LEN ||
        pread_full(fd, hb, sizeof(hb), 0) < 0) {
        return "incomplete";
    }
    if (!memcmp(hb, "\0\0\0\0", 4)) {
        return "incomplete";
    }
    if (!hdr_decode(hb, &fi->h)) {
        return "corrupt";
    }
    uint64_t want = HXS_HDR_LEN + fi->h.payload_len + fi->h.meta_len +
                    HXS_TRAILER_LEN;
    if ((uint64_t)sb.st_size != want) {
        return (uint64_t)sb.st_size < want ? "incomplete" : "corrupt";
    }
    if (pread_full(fd, tr, sizeof(tr), sb.st_size - HXS_TRAILER_LEN) < 0 ||
        memcmp(tr, "HXSE", 4) || ldl_le_p(tr + 4) != fi->h.meta_len) {
        return "incomplete";
    }
    if (fi->h.meta_len > (1 << 20)) {
        return "corrupt";
    }
    uint8_t *mb = g_malloc(fi->h.meta_len);
    int r = pread_full(fd, mb, fi->h.meta_len,
                       HXS_HDR_LEN + fi->h.payload_len);
    fi->meta = r < 0 ? NULL : meta_decode(mb, fi->h.meta_len);
    g_free(mb);
    return fi->meta ? NULL : "corrupt";
}

static const char *file_info(const char *rel, FileInfo *fi)
{
    memset(fi, 0, sizeof(*fi));
    int fd = st_open(rel, false);
    if (fd < 0) {
        return "empty";
    }
    const char *reason = file_info_fd(fd, fi);
    close(fd);
    return reason;
}

static const char *slot_file(int slot)
{
    static const char *const names[HXS_SLOT_COUNT] = {
        "slot0.hxs", "slot1.hxs", "slot2.hxs", "slot3.hxs", "slot4.hxs",
        "slot5.hxs", "slot6.hxs", "slot7.hxs", "slot8.hxs", "slot9.hxs",
        "auto.hxs",  "undo-save.hxs",
    };
    return slot >= 0 && slot < HXS_SLOT_COUNT ? names[slot] : NULL;
}

static char *slot_rel(const char *title, int slot)
{
    return g_build_filename(title, slot_file(slot), NULL);
}

static int slot_from_file(const char *name)
{
    for (int s = 0; s < HXS_SLOT_COUNT; s++) {
        if (!strcmp(name, slot_file(s))) {
            return s;
        }
    }
    return -1;
}

/* --------------------------------------------------------------- codecs */

static ZSTD_CCtx *zc[HXS_MAX_THREADS + 1];
static ZSTD_DCtx *zd[HXS_MAX_THREADS + 1];

static size_t chunk_bound(int codec)
{
    switch (codec) {
    case HXS_CODEC_LZ4:
        return LZ4_compressBound(HXS_CHUNK);
    case HXS_CODEC_ZSTD:
        return ZSTD_compressBound(HXS_CHUNK);
    default:
        return HXS_CHUNK;
    }
}

/* The stored size, or -1 when the chunk does not compress. */
static int64_t compress_chunk(int ctx, int codec, int level,
                              const uint8_t *src, size_t n, uint8_t *dst,
                              size_t cap)
{
    if (codec == HXS_CODEC_LZ4) {
        int r = LZ4_compress_default((const char *)src, (char *)dst, n, cap);
        return r > 0 ? r : -1;
    }
    if (codec == HXS_CODEC_ZSTD) {
        if (!zc[ctx]) {
            zc[ctx] = ZSTD_createCCtx();
        }
        size_t r = ZSTD_compressCCtx(zc[ctx], dst, cap, src, n, level);
        return ZSTD_isError(r) ? -1 : (int64_t)r;
    }
    return -1;
}

static bool decompress_chunk(int ctx, int codec, const uint8_t *src,
                             size_t n, uint8_t *dst, size_t raw)
{
    if (codec == HXS_CODEC_LZ4) {
        return LZ4_decompress_safe((const char *)src, (char *)dst, n, raw) ==
               (int)raw;
    }
    if (codec == HXS_CODEC_ZSTD) {
        if (!zd[ctx]) {
            zd[ctx] = ZSTD_createDCtx();
        }
        return ZSTD_decompressDCtx(zd[ctx], dst, raw, src, n) == raw;
    }
    return false;
}

/* Writes one chunk record into dst: [raw][stored][data]. */
static size_t put_chunk(int ctx, int codec, int level, const uint8_t *src,
                        size_t n, uint8_t *dst, size_t cap)
{
    int64_t s = compress_chunk(ctx, codec, level, src, n, dst + 8, cap - 8);
    if (s < 0 || (size_t)s >= n) {
        memcpy(dst + 8, src, n);
        s = n;
    }
    stl_le_p(dst, n);
    stl_le_p(dst + 4, s);
    return 8 + s;
}

typedef struct ParJob {
    const uint8_t *src;
    size_t n;
    uint8_t *dst;
    size_t slot;
    int codec;
    int level;
    int step;
    uint32_t *len;
    int64_t cpu_us[HXS_MAX_THREADS];
    /* decompression */
    const uint8_t *const *in;
    const uint32_t *stored;
    const uint32_t *raw;
    const uint64_t *raw_off;
    uint8_t *out;
    size_t nch;
    bool fail[HXS_MAX_THREADS];
} ParJob;

typedef struct ParArg {
    ParJob *p;
    int t;
} ParArg;

static void *par_compress(void *o)
{
    ParArg *a = o;
    ParJob *p = a->p;
    int64_t c0 = thread_cpu_us();
    size_t nch = (p->n + HXS_CHUNK - 1) / HXS_CHUNK;

    for (size_t i = a->t; i < nch; i += p->step) {
        size_t off = i * HXS_CHUNK;
        p->len[i] = put_chunk(a->t, p->codec, p->level, p->src + off,
                              MIN(HXS_CHUNK, p->n - off),
                              p->dst + i * p->slot, p->slot);
    }
    p->cpu_us[a->t] = thread_cpu_us() - c0;
    return NULL;
}

static size_t par_capacity(size_t n, int codec)
{
    return ((n + HXS_CHUNK - 1) / HXS_CHUNK) * (chunk_bound(codec) + 8);
}

/* Compresses src into dst (par_capacity bytes); returns the payload length. */
static size_t compress_parallel(const uint8_t *src, size_t n, uint8_t *dst,
                                int codec, int level, int threads,
                                int64_t *cpu_us)
{
    size_t slot = chunk_bound(codec) + 8;
    size_t nch = (n + HXS_CHUNK - 1) / HXS_CHUNK;
    size_t w = 0;

    threads = MAX(1, MIN(threads, HXS_MAX_THREADS));
    if (threads == 1) {
        int64_t c0 = thread_cpu_us();
        for (size_t i = 0; i < nch; i++) {
            size_t off = i * HXS_CHUNK;
            w += put_chunk(0, codec, level, src + off,
                           MIN(HXS_CHUNK, n - off), dst + w, slot);
        }
        *cpu_us = thread_cpu_us() - c0;
        return w;
    }

    ParJob p = { .src = src, .n = n, .dst = dst, .slot = slot,
                 .codec = codec, .level = level, .step = threads };
    ParArg args[HXS_MAX_THREADS];
    pthread_t th[HXS_MAX_THREADS];
    p.len = g_new0(uint32_t, nch);
    for (int t = 0; t < threads; t++) {
        args[t] = (ParArg){ &p, t };
    }
    for (int t = 1; t < threads; t++) {
        pthread_create(&th[t], NULL, par_compress, &args[t]);
    }
    par_compress(&args[0]);
    for (int t = 1; t < threads; t++) {
        pthread_join(th[t], NULL);
    }
    for (size_t i = 0; i < nch; i++) {
        memmove(dst + w, dst + i * slot, p.len[i]);
        w += p.len[i];
    }
    *cpu_us = 0;
    for (int t = 0; t < threads; t++) {
        *cpu_us += p.cpu_us[t];
    }
    g_free(p.len);
    return w;
}

static void *par_decompress(void *o)
{
    ParArg *a = o;
    ParJob *p = a->p;
    int64_t c0 = thread_cpu_us();

    for (size_t i = a->t; i < p->nch; i += p->step) {
        uint8_t *dst = p->out + p->raw_off[i];
        if (p->stored[i] == p->raw[i]) {
            memcpy(dst, p->in[i], p->raw[i]);
        } else if (!decompress_chunk(a->t, p->codec, p->in[i], p->stored[i],
                                     dst, p->raw[i])) {
            p->fail[a->t] = true;
        }
    }
    p->cpu_us[a->t] = thread_cpu_us() - c0;
    return NULL;
}

static bool decompress_payload(const uint8_t *pl, size_t plen, int codec,
                               uint8_t *out, size_t raw_len, int threads)
{
    GArray *in = g_array_new(false, false, sizeof(const uint8_t *));
    GArray *stored = g_array_new(false, false, sizeof(uint32_t));
    GArray *raw = g_array_new(false, false, sizeof(uint32_t));
    GArray *roff = g_array_new(false, false, sizeof(uint64_t));
    size_t pos = 0;
    uint64_t r = 0;
    bool ok = true;

    while (pos < plen) {
        if (pos + 8 > plen) {
            ok = false;
            break;
        }
        uint32_t rl = ldl_le_p(pl + pos);
        uint32_t sl = ldl_le_p(pl + pos + 4);
        const uint8_t *d = pl + pos + 8;
        if (rl > HXS_CHUNK || sl > plen - pos - 8 || r + rl > raw_len) {
            ok = false;
            break;
        }
        g_array_append_val(in, d);
        g_array_append_val(stored, sl);
        g_array_append_val(raw, rl);
        g_array_append_val(roff, r);
        pos += 8 + sl;
        r += rl;
    }
    if (ok && r == raw_len) {
        threads = MAX(1, MIN(threads, HXS_MAX_THREADS));
        ParJob p = {
            .codec = codec, .step = threads, .out = out, .nch = in->len,
            .in = (const uint8_t *const *)in->data,
            .stored = (const uint32_t *)stored->data,
            .raw = (const uint32_t *)raw->data,
            .raw_off = (const uint64_t *)roff->data,
        };
        ParArg args[HXS_MAX_THREADS];
        pthread_t th[HXS_MAX_THREADS];
        for (int t = 0; t < threads; t++) {
            args[t] = (ParArg){ &p, t };
        }
        for (int t = 1; t < threads; t++) {
            pthread_create(&th[t], NULL, par_decompress, &args[t]);
        }
        par_decompress(&args[0]);
        for (int t = 1; t < threads; t++) {
            pthread_join(th[t], NULL);
        }
        for (int t = 0; t < threads; t++) {
            ok &= !p.fail[t];
        }
    } else {
        ok = false;
    }
    g_array_free(in, true);
    g_array_free(stored, true);
    g_array_free(raw, true);
    g_array_free(roff, true);
    return ok;
}

/* Writes a buffer in memory, or a raw file region, as chunks to fd at off. */
static int write_chunks_from_buf(int fd, off_t off, const uint8_t *src,
                                 size_t n, int codec, int level,
                                 uint64_t *payload, int64_t *compress_us,
                                 int64_t *write_us, const bool *cancel)
{
    size_t cap = chunk_bound(codec) + 8;
    uint8_t *c = g_malloc(cap);
    uint64_t w = 0;
    int r = 0;

    for (size_t done = 0; done < n && !r;) {
        if (cancel && qatomic_read(cancel)) {
            r = -ECANCELED;
            break;
        }
        size_t len = MIN(HXS_CHUNK, n - done);
        int64_t t = now_us();
        size_t rec = put_chunk(HXS_CTX_WORKER, codec, level, src + done, len,
                               c, cap);
        *compress_us += now_us() - t;
        t = now_us();
        r = pwrite_full(fd, c, rec, off + w);
        *write_us += now_us() - t;
        w += rec;
        done += len;
    }
    g_free(c);
    *payload = w;
    return r;
}

/* ------------------------------------------------------ main-loop calls */

typedef struct MainCall {
    void (*fn)(void *);
    void *arg;
    QemuSemaphore sem;
} MainCall;

static void main_call_bh(void *opaque)
{
    MainCall *c = opaque;
    c->fn(c->arg);
    qemu_sem_post(&c->sem);
}

/* Runs fn on the QEMU main loop and waits. Never call with hxs_mu held. */
static bool on_main(void (*fn)(void *), void *arg)
{
    if (bql_locked()) {
        HXS_LOG("[savestate] refused: called from the main loop");
        return false;
    }
    MainCall c = { .fn = fn, .arg = arg };
    qemu_sem_init(&c.sem, 0);
    aio_bh_schedule_oneshot(qemu_get_aio_context(), main_call_bh, &c);
    qemu_sem_wait(&c.sem);
    qemu_sem_destroy(&c.sem);
    return true;
}

/* -------------------------------------------------------------- identity */

typedef struct Ident {
    bool running;
    bool paused;
    char *boot_title;
    char *title;
    char *title_name;
    char *disc;
    char *controllers;
    char *schema;
    char *build;
    char *hdd_fmt;
    char *hdd_path;
    bool hdd_ok;
    bool can_save;
    char *can_save_err;
    GHashTable *snaps;
} Ident;

static void ident_clear(Ident *id)
{
    g_free(id->boot_title);
    g_free(id->title);
    g_free(id->title_name);
    g_free(id->disc);
    g_free(id->controllers);
    g_free(id->schema);
    g_free(id->build);
    g_free(id->hdd_fmt);
    g_free(id->hdd_path);
    g_free(id->can_save_err);
    if (id->snaps) {
        g_hash_table_destroy(id->snaps);
    }
    memset(id, 0, sizeof(*id));
}

static bool title_ok(const char *t)
{
    if (!t || strlen(t) != 8) {
        return false;
    }
    for (int i = 0; i < 8; i++) {
        if (!g_ascii_isxdigit(t[i])) {
            return false;
        }
    }
    return true;
}

static BlockBackend *hdd_blk(void)
{
    BlockBackend *blk = blk_by_name("ide0-hd0");
    if (blk && blk_bs(blk)) {
        return blk;
    }
    for (blk = blk_next(NULL); blk; blk = blk_next(blk)) {
        if (blk_bs(blk) && blk_is_writable(blk)) {
            return blk;
        }
    }
    return NULL;
}

/* Main loop. */
static GHashTable *snapshot_names(void)
{
    GHashTable *h = g_hash_table_new_full(g_str_hash, g_str_equal, g_free,
                                          NULL);
    BlockDriverState *bs = bdrv_all_find_vmstate_bs(NULL, false, NULL, NULL);
    if (bs) {
        QEMUSnapshotInfo *tab = NULL;
        int n = bdrv_snapshot_list(bs, &tab);
        for (int i = 0; i < n; i++) {
            g_hash_table_add(h, g_strdup(tab[i].name));
        }
        g_free(tab);
    }
    return h;
}

static void ident_main(void *opaque)
{
    Ident *id = opaque;
    Error *err = NULL;

    id->running = runstate_is_running();
    id->paused = runstate_check(RUN_STATE_PAUSED);
    char *t = xemu_snapshots_running_title_id();
    if (!title_ok(t)) {
        g_free(t);
        t = g_strdup(id->boot_title);
    }
    if (title_ok(t)) {
        id->title = g_ascii_strdown(t, -1);
    }
    g_free(t);
    id->title_name = xemu_snapshots_running_title_name();
    id->disc = xemu_snapshots_running_disc();
    id->controllers = xemu_snapshots_running_controllers();
    id->schema = xemu_savevm_schema_fingerprint();
    id->build = xemu_snapshots_running_build();

    BlockBackend *blk = hdd_blk();
    BlockDriverState *bs = blk ? blk_bs(blk) : NULL;
    if (bs) {
        const char *fmt = bdrv_get_format_name(bs);
        id->hdd_fmt = g_strdup(fmt ? fmt : "");
        id->hdd_path = g_strdup(bs->filename);
        id->hdd_ok = !strcmp(id->hdd_fmt, "qcow2");
    }
    id->can_save = xemu_savevm_can_save(&err);
    if (!id->can_save) {
        id->can_save_err = g_strdup(err ? error_get_pretty(err) : "");
    }
    error_free(err);
    id->snaps = snapshot_names();
}

static void ident_get(Ident *id)
{
    memset(id, 0, sizeof(*id));
    pthread_mutex_lock(&hxs_mu);
    id->boot_title = g_strdup(cfg_boot_title);
    pthread_mutex_unlock(&hxs_mu);
    on_main(ident_main, id);
    pthread_mutex_lock(&hxs_mu);
    if (id->title) {
        g_free(last_title);
        last_title = g_strdup(id->title);
    }
    pthread_mutex_unlock(&hxs_mu);
}

/* NULL when a file with this metadata may be loaded into the machine. */
static const char *check_meta(const Meta *m, const Ident *id)
{
    if (g_strcmp0(meta_get(m, "title_id"), id->title)) {
        return "title";
    }
    if (g_strcmp0(meta_get(m, "disc"), id->disc)) {
        return "disc";
    }
    if (g_strcmp0(meta_get(m, "controllers"), id->controllers)) {
        return "controller-layout";
    }
    if (g_strcmp0(meta_get(m, "schema"), id->schema)) {
        return "schema";
    }
    const char *snap = meta_get(m, "disk_snap");
    if (!snap || !g_hash_table_contains(id->snaps, snap)) {
        return "disk-snapshot-missing";
    }
    return NULL;
}

static int refuse(HxsStats *st, const char *reason, const char *fmt, ...)
    G_GNUC_PRINTF(3, 4);
static int refuse(HxsStats *st, const char *reason, const char *fmt, ...)
{
    st->ok = false;
    pstrcpy(st->reason, sizeof(st->reason), reason);
    if (fmt) {
        va_list ap;
        va_start(ap, fmt);
        vsnprintf(st->error, sizeof(st->error), fmt, ap);
        va_end(ap);
    }
    return -1;
}

/* The refusals every operation shares. */
static int refuse_ident(const Ident *id, HxsStats *st)
{
    if (!have_root()) {
        return refuse(st, "no-folder", "no save state folder is set");
    }
    if (!id->running && !id->paused) {
        return refuse(st, "not-running", "the machine is not running");
    }
    if (!id->hdd_ok) {
        return refuse(st, "hdd-not-qcow2",
                      "the hard disk image is %s, not qcow2",
                      id->hdd_fmt ? id->hdd_fmt : "absent");
    }
    if (!id->title) {
        return refuse(st, "no-title", "no title is running");
    }
    return 0;
}

static char *snap_name_new(const char *title, const char *tag)
{
    char *u = g_uuid_string_random();
    char *n = g_strdup_printf("hxs-%s-%s-%s-%.8s", cfg_root8, title, tag, u);
    g_free(u);
    return n;
}

/* ------------------------------------------------- disk snapshots (main) */

static bool make_disk_snapshot(const char *name, Error **errp)
{
    BlockDriverState *bs = bdrv_all_find_vmstate_bs(NULL, false, NULL, errp);
    QEMUSnapshotInfo sn;
    GDateTime *now;

    if (!bs) {
        return false;
    }
    memset(&sn, 0, sizeof(sn));
    pstrcpy(sn.name, sizeof(sn.name), name);
    now = g_date_time_new_now_local();
    sn.date_sec = g_date_time_to_unix(now);
    sn.date_nsec = g_date_time_get_microsecond(now) * 1000;
    g_date_time_unref(now);
    sn.vm_clock_nsec = qemu_clock_get_ns(QEMU_CLOCK_VIRTUAL);
    sn.icount = -1ULL;
    if (bdrv_all_create_snapshot(&sn, bs, 0, false, NULL, errp) < 0) {
        bdrv_all_delete_snapshot(name, false, NULL, NULL);
        return false;
    }
    return true;
}

typedef struct DelCall {
    const char *name;
    int ret;
    char err[160];
} DelCall;

static void del_main(void *o)
{
    DelCall *c = o;
    Error *err = NULL;
    c->ret = bdrv_all_delete_snapshot(c->name, false, NULL, &err);
    if (err) {
        pstrcpy(c->err, sizeof(c->err), error_get_pretty(err));
        error_free(err);
    }
}

static int64_t snap_delete(const char *name)
{
    if (!name || !*name) {
        return 0;
    }
    int64_t t = now_us();
    DelCall c = { .name = name };
    on_main(del_main, &c);
    if (c.ret < 0) {
        HXS_LOG("[savestate] snapshot-delete name=%s ok=0 err=\"%s\"", name,
                c.err);
    }
    return now_us() - t;
}

/* Whether a file in the title's folder still names this snapshot. */
static bool snap_referenced(const char *title, const char *name)
{
    bool found = false;
    pthread_mutex_lock(&hxs_mu);
    GArray *ents = st_list(title);
    for (guint i = 0; ents && i < ents->len && !found; i++) {
        StEnt *e = &g_array_index(ents, StEnt, i);
        if (e->dir || !strstr(e->name, ".hxs")) {
            continue;
        }
        g_autofree char *rel = g_build_filename(title, e->name, NULL);
        FileInfo fi;
        if (!file_info(rel, &fi)) {
            found = !g_strcmp0(meta_get(fi.meta, "disk_snap"), name);
        }
        file_info_clear(&fi);
    }
    if (ents) {
        g_array_unref(ents);
    }
    pthread_mutex_unlock(&hxs_mu);
    return found;
}

static int64_t delete_unreferenced(const char *title, GPtrArray *names)
{
    int64_t us = 0;
    for (guint i = 0; names && i < names->len; i++) {
        const char *n = g_ptr_array_index(names, i);
        if (!snap_referenced(title, n)) {
            us += snap_delete(n);
        }
    }
    return us;
}

/* The snapshot a file names, added to names. Under hxs_mu. */
static void add_snap_of(const char *rel, GPtrArray *names)
{
    FileInfo fi;
    if (!file_info(rel, &fi)) {
        const char *s = meta_get(fi.meta, "disk_snap");
        if (s && *s) {
            g_ptr_array_add(names, g_strdup(s));
        }
    }
    file_info_clear(&fi);
}

/*
 * Moves a finished .tmp into its slot. A numbered slot's previous file
 * becomes undo-save; without one, the old undo-save goes. Returns the
 * snapshots that may have lost their last reference in unref.
 */
static int place_file(const char *title, int slot, const char *tmp,
                      GPtrArray *unref)
{
    g_autofree char *final = slot_rel(title, slot);
    int r = 0;

    pthread_mutex_lock(&hxs_mu);
    if (slot < HXS_SLOTS) {
        g_autofree char *undo = slot_rel(title, HXS_SLOT_UNDO_SAVE);
        add_snap_of(undo, unref);
        r = st_exists(final) ? st_rename(final, undo) : st_unlink(undo);
    } else {
        add_snap_of(final, unref);
    }
    if (!r) {
        r = st_rename(tmp, final);
    }
    st_sync_dir(title);
    pthread_mutex_unlock(&hxs_mu);
    return r;
}

/* ---------------------------------------------------------------- jobs */

typedef enum HxsJobKind {
    JOB_COMPRESS,
    JOB_DEFERRED,
} HxsJobKind;

typedef struct HxsJob {
    HxsJobKind kind;
    uint64_t seq;
    char *title;
    int slot;
    int codec;
    int level;
    bool running;
    bool cancel;
    int64_t t_stop;
    uint8_t *buf;
    size_t len;
    Meta *meta;
    HxsStats st;
} HxsJob;

static GQueue job_q = G_QUEUE_INIT;
static uint64_t job_seq_next = 1;
static uint64_t job_done_seq;
static uint64_t last_job_seq;
static HxsStats job_ring[HXS_JOB_RING];
static uint64_t job_ring_seq[HXS_JOB_RING];
static bool worker_on;
static int worker_cpu = -1;

static void job_free(HxsJob *j)
{
    g_free(j->title);
    g_free(j->buf);
    meta_free(j->meta);
    g_free(j);
}

/* Under hxs_mu. */
static uint64_t job_push(HxsJob *j)
{
    j->seq = job_seq_next++;
    last_job_seq = j->seq;
    g_queue_push_tail(&job_q, j);
    pthread_cond_broadcast(&hxs_cv);
    return j->seq;
}

/*
 * Before a slot changes hands: waits for every deferred write of the title,
 * and cancels (or waits out) compression of the two slots named.
 */
static void jobs_settle(const char *title, int a, int b)
{
    pthread_mutex_lock(&hxs_mu);
    for (;;) {
        bool wait = false;
        GList *l = job_q.head;
        while (l) {
            GList *next = l->next;
            HxsJob *j = l->data;
            if (!strcmp(j->title, title)) {
                if (j->kind == JOB_DEFERRED) {
                    wait = true;
                } else if (j->slot == a || j->slot == b) {
                    if (j->running) {
                        j->cancel = true;
                        wait = true;
                    } else {
                        g_queue_delete_link(&job_q, l);
                        HXS_LOG("[savestate] bg-compress slot=%d dropped=1",
                                j->slot);
                        job_free(j);
                    }
                }
            }
            l = next;
        }
        if (!wait) {
            break;
        }
        pthread_cond_wait(&hxs_cv, &hxs_mu);
    }
    pthread_mutex_unlock(&hxs_mu);
}

static bool job_running_for(const char *title, int slot)
{
    for (GList *l = job_q.head; l; l = l->next) {
        HxsJob *j = l->data;
        if (j->running && j->slot == slot && !strcmp(j->title, title)) {
            return true;
        }
    }
    return false;
}

bool hxs_wait_idle(int timeout_ms)
{
    int64_t end = now_us() + timeout_ms * 1000LL;
    bool idle;

    pthread_mutex_lock(&hxs_mu);
    while (!(idle = g_queue_is_empty(&job_q)) && now_us() < end) {
        struct timespec ts;
        clock_gettime(CLOCK_REALTIME, &ts);
        ts.tv_nsec += 100 * 1000000L;
        if (ts.tv_nsec >= 1000000000L) {
            ts.tv_sec++;
            ts.tv_nsec -= 1000000000L;
        }
        pthread_cond_timedwait(&hxs_cv, &hxs_mu, &ts);
    }
    pthread_mutex_unlock(&hxs_mu);
    return idle;
}

static bool job_result(uint64_t seq, HxsStats *out)
{
    bool found = false;
    pthread_mutex_lock(&hxs_mu);
    int i = seq % HXS_JOB_RING;
    if (job_ring_seq[i] == seq) {
        *out = job_ring[i];
        found = true;
    }
    pthread_mutex_unlock(&hxs_mu);
    return found;
}

static bool job_wait(uint64_t seq, HxsStats *out)
{
    pthread_mutex_lock(&hxs_mu);
    while (job_done_seq < seq) {
        pthread_cond_wait(&hxs_cv, &hxs_mu);
    }
    pthread_mutex_unlock(&hxs_mu);
    return job_result(seq, out);
}

static void job_compress(HxsJob *j)
{
    g_autofree char *final = slot_rel(j->title, j->slot);
    g_autofree char *ztmp = g_strconcat(final, ".z.tmp", NULL);
    HxsStats *st = &j->st;
    int64_t t0 = now_us(), c0 = thread_cpu_us();
    int64_t write_us = 0, comp_us = 0;
    FileInfo fi = { 0 };
    const char *reason = NULL;
    int in = -1, out = -1, r = 0;
    uint8_t *rbuf = NULL, *cbuf = NULL;

    pthread_mutex_lock(&hxs_mu);
    in = st_open(final, false);
    pthread_mutex_unlock(&hxs_mu);
    if (in < 0) {
        reason = "empty";
        goto out;
    }
    reason = file_info_fd(in, &fi);
    if (reason) {
        goto out;
    }
    if (fi.h.codec != HXS_CODEC_NONE) {
        reason = "already-compressed";
        goto out;
    }
    out = st_open(ztmp, true);
    if (out < 0) {
        reason = "open-failed";
        goto out;
    }
    size_t cap = chunk_bound(j->codec) + 8;
    rbuf = g_malloc(HXS_CHUNK);
    cbuf = g_malloc(cap);
    uint64_t w = 0;
    for (uint64_t off = 0; off < fi.h.raw_len && !r;) {
        if (qatomic_read(&j->cancel)) {
            r = -ECANCELED;
            break;
        }
        size_t n = MIN(HXS_CHUNK, fi.h.raw_len - off);
        int64_t t = now_us();
        r = pread_full(in, rbuf, n, HXS_HDR_LEN + off);
        write_us += now_us() - t;
        if (r) {
            break;
        }
        t = now_us();
        size_t rec = put_chunk(HXS_CTX_WORKER, j->codec, j->level, rbuf, n,
                               cbuf, cap);
        comp_us += now_us() - t;
        t = now_us();
        r = pwrite_full(out, cbuf, rec, HXS_HDR_LEN + w);
        write_us += now_us() - t;
        w += rec;
        off += n;
    }
    if (!r) {
        Meta *m = meta_copy(fi.meta);
        meta_set(m, "codec", codec_name(j->codec));
        meta_setf(m, "level", "%d", j->level);
        FileHdr h = { .codec = j->codec, .level = j->level,
                      .raw_len = fi.h.raw_len, .payload_len = w,
                      .chunk = HXS_CHUNK, .flags = HXS_FLAG_CHUNKED };
        int64_t t = now_us();
        r = finish_file(out, &h, m);
        write_us += now_us() - t;
        st->file_bytes = HXS_HDR_LEN + w + h.meta_len + HXS_TRAILER_LEN;
        meta_free(m);
    }
    close(out);
    out = -1;
    pthread_mutex_lock(&hxs_mu);
    if (!r && !j->cancel) {
        r = st_rename(ztmp, final);
        st_sync_dir(j->title);
    } else {
        st_unlink(ztmp);
    }
    pthread_mutex_unlock(&hxs_mu);
    if (r) {
        reason = r == -ECANCELED || j->cancel ? "cancelled" : "write-failed";
    }

out:
    if (in >= 0) {
        close(in);
    }
    if (out >= 0) {
        close(out);
        st_unlink(ztmp);
    }
    g_free(rbuf);
    g_free(cbuf);
    st->ok = !reason;
    pstrcpy(st->reason, sizeof(st->reason), reason ? reason : "");
    st->compress_us = comp_us;
    st->write_us = write_us;
    st->cpu_us = thread_cpu_us() - c0;
    st->compressed_us = now_us() - j->t_stop;
    st->raw_bytes = fi.h.raw_len;
    st->worker_cpu = sched_getcpu();
    HXS_LOG("[savestate] bg-compress title=%s slot=%d ok=%d reason=%s "
            "codec=%s level=%d ms=%.1f compress_ms=%.1f io_ms=%.1f "
            "cpu_ms=%.1f compressed_ms=%.1f raw=%" PRIu64 " bytes=%" PRIu64
            " cpu=%d",
            j->title, j->slot, st->ok, st->reason, codec_name(j->codec),
            j->level, (now_us() - t0) / 1000.0, comp_us / 1000.0,
            write_us / 1000.0, st->cpu_us / 1000.0,
            st->compressed_us / 1000.0, (uint64_t)fi.h.raw_len,
            (uint64_t)st->file_bytes, st->worker_cpu);
    file_info_clear(&fi);
}

static void job_deferred(HxsJob *j)
{
    g_autofree char *final = slot_rel(j->title, j->slot);
    g_autofree char *tmp = g_strconcat(final, ".tmp", NULL);
    HxsStats *st = &j->st;
    int64_t c0 = thread_cpu_us();
    int64_t comp_us = 0, write_us = 0;
    GPtrArray *unref = g_ptr_array_new_with_free_func(g_free);
    uint64_t payload = 0;
    FileHdr h = { .codec = j->codec, .level = j->level, .raw_len = j->len };
    int r;

    int fd = st_open(tmp, true);
    if (fd < 0) {
        r = fd;
    } else if (j->codec == HXS_CODEC_NONE) {
        int64_t t = now_us();
        r = pwrite_full(fd, j->buf, j->len, HXS_HDR_LEN);
        write_us += now_us() - t;
        payload = j->len;
    } else {
        r = write_chunks_from_buf(fd, HXS_HDR_LEN, j->buf, j->len, j->codec,
                                  j->level, &payload, &comp_us, &write_us,
                                  NULL);
        h.chunk = HXS_CHUNK;
        h.flags = HXS_FLAG_CHUNKED;
    }
    h.payload_len = payload;
    if (!r) {
        int64_t t = now_us();
        r = finish_file(fd, &h, j->meta);
        write_us += now_us() - t;
    }
    if (fd >= 0) {
        close(fd);
    }
    g_free(j->buf);
    j->buf = NULL;
    if (!r) {
        r = place_file(j->title, j->slot, tmp, unref);
    }
    if (r) {
        st_unlink(tmp);
        g_ptr_array_add(unref, g_strdup(meta_get(j->meta, "disk_snap")));
    }
    st->ok = !r;
    pstrcpy(st->reason, sizeof(st->reason), r ? "write-failed" : "");
    st->compress_us = comp_us;
    st->write_us = write_us;
    st->cpu_us = thread_cpu_us() - c0;
    st->durable_us = now_us() - j->t_stop;
    st->file_bytes = HXS_HDR_LEN + payload + h.meta_len + HXS_TRAILER_LEN;
    st->worker_cpu = sched_getcpu();
    st->post_us = delete_unreferenced(j->title, unref);
    g_ptr_array_free(unref, true);
    HXS_LOG("[savestate] deferred-write title=%s slot=%d ok=%d codec=%s "
            "level=%d compress_ms=%.1f write_ms=%.1f cpu_ms=%.1f "
            "durable_ms=%.1f raw=%" PRIu64 " bytes=%" PRIu64 " cpu=%d",
            j->title, j->slot, st->ok, codec_name(j->codec), j->level,
            comp_us / 1000.0, write_us / 1000.0, st->cpu_us / 1000.0,
            st->durable_us / 1000.0, (uint64_t)j->len,
            (uint64_t)st->file_bytes, st->worker_cpu);
}

/* --------------------------------------------------------------- CPU probe */

typedef struct TaskSample {
    int tid;
    char comm[32];
    uint64_t ticks;
    int cpu;
} TaskSample;

static GArray *read_tasks(void)
{
    GArray *a = g_array_new(false, true, sizeof(TaskSample));
    DIR *d = opendir("/proc/self/task");
    struct dirent *de;

    if (!d) {
        return a;
    }
    while ((de = readdir(d))) {
        int tid = atoi(de->d_name);
        if (tid <= 0) {
            continue;
        }
        char path[64], buf[1024];
        snprintf(path, sizeof(path), "/proc/self/task/%d/stat", tid);
        int fd = open(path, O_RDONLY | O_CLOEXEC);
        if (fd < 0) {
            continue;
        }
        ssize_t n = read(fd, buf, sizeof(buf) - 1);
        close(fd);
        if (n <= 0) {
            continue;
        }
        buf[n] = 0;
        char *lp = strchr(buf, '(');
        char *rp = strrchr(buf, ')');
        if (!lp || !rp || rp < lp) {
            continue;
        }
        TaskSample s = { .tid = tid, .cpu = -1 };
        snprintf(s.comm, sizeof(s.comm), "%.*s", (int)(rp - lp - 1), lp + 1);
        char **f = g_strsplit(rp + 2, " ", -1);
        if (g_strv_length(f) > 36) {
            s.ticks = g_ascii_strtoull(f[11], NULL, 10) +
                      g_ascii_strtoull(f[12], NULL, 10);
            s.cpu = atoi(f[36]);
        }
        g_strfreev(f);
        g_array_append_val(a, s);
    }
    closedir(d);
    return a;
}

static int64_t read_ll(const char *path)
{
    char buf[64];
    int fd = open(path, O_RDONLY | O_CLOEXEC);
    if (fd < 0) {
        return -1;
    }
    ssize_t n = read(fd, buf, sizeof(buf) - 1);
    close(fd);
    if (n <= 0) {
        return -1;
    }
    buf[n] = 0;
    return g_ascii_strtoll(buf, NULL, 10);
}

/* Total idle time of a CPU in microseconds, or -1. */
static int64_t cpu_idle_us(int cpu)
{
    int64_t total = -1;
    for (int s = 0; s < 16; s++) {
        char path[96];
        snprintf(path, sizeof(path),
                 "/sys/devices/system/cpu/cpu%d/cpuidle/state%d/time", cpu, s);
        int64_t v = read_ll(path);
        if (v < 0) {
            break;
        }
        total = (total < 0 ? 0 : total) + v;
    }
    return total;
}

#define HXS_MAX_CPUS 16

/*
 * "An unused core" is measured, not assumed: for one second, which CPUs
 * this process's busy threads run on and how idle each CPU is. The worker
 * is pinned to the idlest CPU none of them used and runs at SCHED_IDLE.
 */
static void probe_and_pin(bool first)
{
    int ncpu = MIN((int)sysconf(_SC_NPROCESSORS_CONF), HXS_MAX_CPUS);
    int64_t freq[HXS_MAX_CPUS], idle0[HXS_MAX_CPUS], idle1[HXS_MAX_CPUS];
    int hot[HXS_MAX_CPUS] = { 0 };
    long hz = sysconf(_SC_CLK_TCK);
    GHashTable *busy = g_hash_table_new(g_direct_hash, g_direct_equal);
    GString *topo = g_string_new(NULL), *idle_s = g_string_new(NULL);
    GString *hot_s = g_string_new(NULL), *thr = g_string_new(NULL);
    int samples = 10;

    for (int c = 0; c < ncpu; c++) {
        char path[96];
        snprintf(path, sizeof(path),
                 "/sys/devices/system/cpu/cpu%d/cpufreq/cpuinfo_max_freq", c);
        freq[c] = read_ll(path);
        idle0[c] = cpu_idle_us(c);
    }
    int64_t w0 = now_us();
    GArray *prev = read_tasks();
    GArray *first_s = read_tasks();
    for (int k = 0; k < samples; k++) {
        sleep_ms(100);
        GArray *cur = read_tasks();
        for (guint i = 0; i < cur->len; i++) {
            TaskSample *s = &g_array_index(cur, TaskSample, i);
            for (guint p = 0; p < prev->len; p++) {
                TaskSample *q = &g_array_index(prev, TaskSample, p);
                if (q->tid == s->tid && s->ticks > q->ticks && s->cpu >= 0 &&
                    s->cpu < ncpu && s->tid != (int)gettid()) {
                    hot[s->cpu]++;
                    break;
                }
            }
        }
        g_array_unref(prev);
        prev = cur;
    }
    int64_t wall = now_us() - w0;
    for (int c = 0; c < ncpu; c++) {
        idle1[c] = cpu_idle_us(c);
    }

    /* Threads that used at least 2% of a CPU, with their affinity. */
    for (guint i = 0; i < prev->len; i++) {
        TaskSample *s = &g_array_index(prev, TaskSample, i);
        for (guint p = 0; p < first_s->len; p++) {
            TaskSample *q = &g_array_index(first_s, TaskSample, p);
            if (q->tid != s->tid) {
                continue;
            }
            double pct = (s->ticks - q->ticks) * 100.0 /
                         (hz * (wall / 1e6));
            if (pct >= 2.0) {
                cpu_set_t m;
                CPU_ZERO(&m);
                unsigned mask = 0;
                if (sched_getaffinity(s->tid, sizeof(m), &m) == 0) {
                    for (int c = 0; c < ncpu; c++) {
                        mask |= CPU_ISSET(c, &m) ? 1u << c : 0;
                    }
                }
                g_string_append_printf(thr, "%s%s:%d:%.0f%%:cpu%d:mask=%x",
                                       thr->len ? ";" : "", s->comm, s->tid,
                                       pct, s->cpu, mask);
                g_hash_table_add(busy, GINT_TO_POINTER(s->tid));
            }
            break;
        }
    }

    int pick = -1;
    double pick_idle = -2;
    for (int c = 0; c < ncpu; c++) {
        double idle = idle0[c] >= 0 && idle1[c] >= 0
                          ? (double)(idle1[c] - idle0[c]) / wall
                          : -1;
        g_string_append_printf(topo, "%s%d:%" PRId64, c ? "," : "", c,
                               freq[c] / 1000);
        g_string_append_printf(idle_s, "%s%d:%.2f", c ? "," : "", c, idle);
        if (hot[c] >= 3) {
            g_string_append_printf(hot_s, "%s%d(%d)", hot_s->len ? "," : "",
                                   c, hot[c]);
            continue;
        }
        if (idle > pick_idle ||
            (idle == pick_idle && pick >= 0 && freq[c] > freq[pick])) {
            pick = c;
            pick_idle = idle;
        }
    }

    bool pinned = false;
    if (pick >= 0) {
        cpu_set_t m;
        CPU_ZERO(&m);
        CPU_SET(pick, &m);
        pinned = sched_setaffinity(0, sizeof(m), &m) == 0;
    }
    const char *policy = "unchanged";
    if (first) {
        struct sched_param sp = { 0 };
        if (sched_setscheduler(0, SCHED_IDLE, &sp) == 0) {
            policy = "idle";
        } else if (setpriority(PRIO_PROCESS, 0, 19) == 0) {
            policy = "nice19";
        } else {
            policy = "none";
        }
    }
    worker_cpu = pinned ? pick : -1;
    HXS_LOG("[savestate] cpu probe_ms=%.0f ncpu=%d max_mhz=%s idle=%s hot=%s "
            "pick=%d pinned=%d policy=%s",
            wall / 1000.0, ncpu, topo->str, idle_s->str,
            hot_s->len ? hot_s->str : "-", pick, pinned, policy);
    HXS_LOG("[savestate] cpu threads=%s", thr->len ? thr->str : "-");
    g_array_unref(prev);
    g_array_unref(first_s);
    g_hash_table_destroy(busy);
    g_string_free(topo, true);
    g_string_free(idle_s, true);
    g_string_free(hot_s, true);
    g_string_free(thr, true);
}

static void *worker_main(void *arg)
{
    (void)arg;
    pthread_setname_np(pthread_self(), "hxs-worker");
    probe_and_pin(true);

    pthread_mutex_lock(&hxs_mu);
    for (;;) {
        while (g_queue_is_empty(&job_q)) {
            struct timespec ts;
            clock_gettime(CLOCK_REALTIME, &ts);
            ts.tv_sec += 120;
            if (pthread_cond_timedwait(&hxs_cv, &hxs_mu, &ts) == ETIMEDOUT &&
                g_queue_is_empty(&job_q)) {
                pthread_mutex_unlock(&hxs_mu);
                probe_and_pin(false);
                pthread_mutex_lock(&hxs_mu);
            }
        }
        HxsJob *j = g_queue_peek_head(&job_q);
        j->running = true;
        pthread_mutex_unlock(&hxs_mu);

        if (j->kind == JOB_COMPRESS) {
            job_compress(j);
        } else {
            job_deferred(j);
        }

        pthread_mutex_lock(&hxs_mu);
        g_queue_pop_head(&job_q);
        job_ring[j->seq % HXS_JOB_RING] = j->st;
        job_ring_seq[j->seq % HXS_JOB_RING] = j->seq;
        job_done_seq = j->seq;
        pthread_cond_broadcast(&hxs_cv);
        pthread_mutex_unlock(&hxs_mu);
        job_free(j);
        pthread_mutex_lock(&hxs_mu);
    }
    return NULL;
}

static void worker_start(void)
{
    pthread_mutex_lock(&hxs_mu);
    if (!worker_on) {
        pthread_t t;
        worker_on = pthread_create(&t, NULL, worker_main, NULL) == 0;
        if (worker_on) {
            pthread_detach(t);
        }
    }
    pthread_mutex_unlock(&hxs_mu);
}

/* ---------------------------------------------------------- the stream */

/* Writes the machine to f. Main loop, machine stopped, block layer drained. */
static int save_to_file(QEMUFile *f, uint64_t *bytes, Error **errp)
{
    int ret = xemu_savevm_write(f, errp);
    *bytes = qemu_file_transferred(f);
    int ret2 = qemu_fclose(f);
    if (ret >= 0 && ret2 < 0) {
        error_setg_errno(errp, -ret2, "writing the state failed");
        ret = ret2;
    }
    return ret;
}

/* Into a buffer the caller owns; it may be reallocated (g_malloc'd). */
static int save_to_buf(uint8_t **buf, size_t *cap, size_t *len, Error **errp)
{
    QIOChannelBuffer *bioc = qio_channel_buffer_new(0);
    g_free(bioc->data);
    bioc->data = *buf;
    bioc->capacity = *cap;
    bioc->usage = 0;
    bioc->offset = 0;
    QEMUFile *f = qemu_file_new_output(QIO_CHANNEL(bioc));
    int ret = xemu_savevm_write(f, errp);
    int ret2 = qemu_fflush(f);
    *buf = bioc->data;
    *cap = bioc->capacity;
    *len = bioc->usage;
    bioc->data = NULL;
    bioc->capacity = bioc->usage = bioc->offset = 0;
    qemu_fclose(f);
    object_unref(OBJECT(bioc));
    if (ret >= 0 && ret2 < 0) {
        error_setg_errno(errp, -ret2, "writing the state failed");
        ret = ret2;
    }
    return ret;
}

/* Resets the machine and loads it from a buffer, which is handed back. */
static int load_from_buf(uint8_t **buf, size_t len, size_t cap, Error **errp)
{
    QIOChannelBuffer *bioc = qio_channel_buffer_new(0);
    g_free(bioc->data);
    bioc->data = *buf;
    bioc->usage = len;
    bioc->capacity = cap;
    bioc->offset = 0;
    QEMUFile *f = qemu_file_new_input(QIO_CHANNEL(bioc));
    int ret = xemu_loadvm_read(f, errp);
    *buf = bioc->data;
    bioc->data = NULL;
    bioc->capacity = bioc->usage = bioc->offset = 0;
    qemu_fclose(f);
    object_unref(OBJECT(bioc));
    return ret;
}

static size_t last_raw_bytes;

static size_t stream_cap_guess(void)
{
    if (last_raw_bytes) {
        return last_raw_bytes + (8 << 20);
    }
    return (size_t)current_machine->ram_size + (32 << 20);
}

/* A buffer whose pages are already mapped, so the pause does not fault. */
static uint8_t *prefaulted(size_t n)
{
    uint8_t *p = g_try_malloc(n);
    if (p) {
        memset(p, 0, n);
    }
    return p;
}

/* ----------------------------------------------------------------- save */

typedef struct SaveCtx {
    HxsStats *st;
    int mode;
    int codec;
    int level;
    int threads;
    const char *snap;
    int fd;
    uint8_t *buf;
    size_t cap;
    size_t len;
    uint8_t *cbuf;
    size_t clen;
    int64_t t_stop;
    bool was_paused;
    bool ok;
    char reason[48];
    char err[192];
} SaveCtx;

static void save_fail(SaveCtx *c, const char *reason, Error *err)
{
    c->ok = false;
    pstrcpy(c->reason, sizeof(c->reason), reason);
    if (err) {
        pstrcpy(c->err, sizeof(c->err), error_get_pretty(err));
    }
}

static void save_main(void *o)
{
    SaveCtx *c = o;
    HxsStats *st = c->st;
    Error *err = NULL;
    bool snap_made = false;

    c->ok = true;
    c->was_paused = runstate_check(RUN_STATE_PAUSED);
    if (!runstate_is_running() && !c->was_paused) {
        save_fail(c, "not-running", NULL);
        return;
    }
    /*
     * From paused, vm_stop() notifies no device, and the GPU and audio
     * post-save hooks would then release locks they never took: start the
     * machine first, and pause it again afterwards.
     */
    if (c->was_paused) {
        vm_start();
    }
    global_state_store();
    c->t_stop = now_us();
    vm_stop(RUN_STATE_SAVE_VM);
    bdrv_drain_all_begin();

    int64_t t = now_us();
    snap_made = make_disk_snapshot(c->snap, &err);
    st->disksnap_us = now_us() - t;
    if (!snap_made) {
        save_fail(c, "save-failed", err);
        goto out;
    }

    t = now_us();
    int ret;
    if (c->fd >= 0) {
        QIOChannelFile *fioc = qio_channel_file_new_fd(dup(c->fd));
        QEMUFile *f = qemu_file_new_output(QIO_CHANNEL(fioc));
        object_unref(OBJECT(fioc));
        uint64_t bytes = 0;
        ret = save_to_file(f, &bytes, &err);
        c->len = bytes;
    } else {
        ret = save_to_buf(&c->buf, &c->cap, &c->len, &err);
    }
    st->serialize_us = now_us() - t;
    st->region = xemu_snapshots_last_save_region();
    if (ret < 0) {
        save_fail(c, "save-failed", err);
        goto out;
    }
    if (c->mode == HXS_MODE_INLINE) {
        t = now_us();
        c->cbuf = g_try_malloc(par_capacity(c->len, c->codec));
        if (!c->cbuf) {
            save_fail(c, "save-failed", NULL);
            pstrcpy(c->err, sizeof(c->err), "out of memory");
            goto out;
        }
        c->clen = compress_parallel(c->buf, c->len, c->cbuf, c->codec,
                                    c->level, c->threads, &st->cpu_us);
        st->compress_us = now_us() - t;
    }

out:
    bdrv_drain_all_end();
    if (!c->ok && snap_made) {
        bdrv_all_delete_snapshot(c->snap, false, NULL, NULL);
    }
    error_free(err);
    vm_start();
    st->pause_us = now_us() - c->t_stop;
    if (c->was_paused) {
        vm_stop(RUN_STATE_PAUSED);
    }
}

static Meta *build_meta(const Ident *id, int slot, int mode, int codec,
                        int level, const char *snap)
{
    Meta *m = meta_new();
    meta_set(m, "schema", id->schema);
    meta_set(m, "build", id->build);
    meta_set(m, "title_id", id->title);
    meta_set(m, "title_name", id->title_name);
    meta_set(m, "disc", id->disc);
    meta_set(m, "controllers", id->controllers);
    meta_set(m, "disk_snap", snap);
    meta_set(m, "hdd", id->hdd_path ? id->hdd_path : "");
    meta_setf(m, "saved_at", "%" PRId64, g_get_real_time() / 1000000);
    meta_setf(m, "slot", "%d", slot);
    meta_set(m, "mode", mode_name(mode));
    meta_set(m, "codec", codec_name(codec));
    meta_setf(m, "level", "%d", level);
    meta_set(m, "compress_later", mode == HXS_MODE_BACKGROUND ? "1" : "0");
    return m;
}

static int save_locked(int slot, int mode, int codec, int level,
                       bool wait_durable, bool compress_later, HxsStats *st)
{
    int64_t t_begin = now_us();
    Ident id;
    SaveCtx c = { .st = st, .mode = mode, .codec = codec, .level = level,
                  .threads = inline_threads, .fd = -1 };
    g_autofree char *snap = NULL;
    g_autofree char *final = NULL;
    g_autofree char *tmp = NULL;
    GPtrArray *unref = g_ptr_array_new_with_free_func(g_free);
    Meta *m = NULL;
    int r = -1;

    st->threads = mode == HXS_MODE_INLINE ? c.threads : 1;
    ident_get(&id);
    st->check_us = now_us() - t_begin;
    if (refuse_ident(&id, st)) {
        goto done;
    }
    if (!id.can_save) {
        refuse(st, "cannot-save", "%s", id.can_save_err);
        goto done;
    }
    jobs_settle(id.title, slot,
                slot < HXS_SLOTS ? HXS_SLOT_UNDO_SAVE : HXS_SLOT_AUTO);
    st_mkdir(id.title);
    final = slot_rel(id.title, slot);
    tmp = g_strconcat(final, ".tmp", NULL);
    snap = snap_name_new(id.title, slot == HXS_SLOT_AUTO
                                       ? "auto"
                                       : (char[]){ 's', '0' + slot, 0 });
    c.snap = snap;
    m = build_meta(&id, slot, mode, codec, level, snap);
    if (compress_later) {
        meta_set(m, "compress_later", "1");
    }

    if (mode == HXS_MODE_RAW || mode == HXS_MODE_BACKGROUND) {
        static const uint8_t zero[HXS_HDR_LEN];
        c.fd = st_open(tmp, true);
        if (c.fd < 0 || pwrite_full(c.fd, zero, sizeof(zero), 0) < 0 ||
            lseek(c.fd, HXS_HDR_LEN, SEEK_SET) != HXS_HDR_LEN) {
            refuse(st, "open-failed", "cannot write %s: %s", tmp,
                   strerror(c.fd < 0 ? -c.fd : errno));
            goto done;
        }
    } else {
        c.cap = stream_cap_guess();
        c.buf = prefaulted(c.cap);
        if (!c.buf) {
            refuse(st, "save-failed", "out of memory");
            goto done;
        }
    }

    on_main(save_main, &c);
    st->raw_bytes = c.len;
    if (!c.ok) {
        refuse(st, c.reason, "%s", c.err);
        goto done;
    }
    last_raw_bytes = c.len;
    meta_setf(m, "region", "%016" PRIx64, st->region);
    pstrcpy(st->disk_snap, sizeof(st->disk_snap), snap);

    if (mode == HXS_MODE_RAW || mode == HXS_MODE_BACKGROUND) {
        FileHdr h = { .raw_len = c.len, .payload_len = c.len };
        int64_t t = now_us();
        r = finish_file(c.fd, &h, m);
        st->write_us = now_us() - t;
        close(c.fd);
        c.fd = -1;
        if (!r) {
            r = place_file(id.title, slot, tmp, unref);
        }
        st->file_bytes = HXS_HDR_LEN + c.len + h.meta_len + HXS_TRAILER_LEN;
    } else if (mode == HXS_MODE_INLINE) {
        FileHdr h = { .codec = codec, .level = level, .raw_len = c.len,
                      .payload_len = c.clen, .chunk = HXS_CHUNK,
                      .flags = HXS_FLAG_CHUNKED };
        int64_t t = now_us();
        int fd = st_open(tmp, true);
        r = fd < 0 ? fd : pwrite_full(fd, c.cbuf, c.clen, HXS_HDR_LEN);
        if (!r) {
            r = finish_file(fd, &h, m);
        }
        if (fd >= 0) {
            close(fd);
        }
        st->write_us = now_us() - t;
        if (!r) {
            r = place_file(id.title, slot, tmp, unref);
        }
        st->file_bytes = HXS_HDR_LEN + c.clen + h.meta_len + HXS_TRAILER_LEN;
    } else {
        HxsJob *j = g_new0(HxsJob, 1);
        j->kind = JOB_DEFERRED;
        j->title = g_strdup(id.title);
        j->slot = slot;
        j->codec = codec;
        j->level = level;
        j->t_stop = c.t_stop;
        j->buf = c.buf;
        j->len = c.len;
        j->meta = m;
        j->st = *st;
        c.buf = NULL;
        m = NULL;
        pthread_mutex_lock(&hxs_mu);
        uint64_t seq = job_push(j);
        pthread_mutex_unlock(&hxs_mu);
        r = 0;
        if (wait_durable) {
            HxsStats js;
            if (job_wait(seq, &js)) {
                st->compress_us = js.compress_us;
                st->write_us = js.write_us;
                st->cpu_us = js.cpu_us;
                st->durable_us = js.durable_us;
                st->file_bytes = js.file_bytes;
                st->worker_cpu = js.worker_cpu;
                st->post_us = js.post_us;
                r = js.ok ? 0 : -1;
            }
        }
    }
    if (r) {
        st_unlink(tmp);
        g_ptr_array_add(unref, g_strdup(snap));
        refuse(st, "write-failed", "writing %s failed", tmp);
    } else if (mode != HXS_MODE_DEFERRED) {
        st->durable_us = now_us() - c.t_stop;
    }
    if (!r && mode == HXS_MODE_BACKGROUND) {
        HxsJob *j = g_new0(HxsJob, 1);
        j->kind = JOB_COMPRESS;
        j->title = g_strdup(id.title);
        j->slot = slot;
        j->codec = codec;
        j->level = level;
        j->t_stop = c.t_stop;
        pthread_mutex_lock(&hxs_mu);
        job_push(j);
        pthread_mutex_unlock(&hxs_mu);
    }
    st->post_us += delete_unreferenced(id.title, unref);
    st->ok = !r;

done:
    if (c.fd >= 0) {
        close(c.fd);
        st_unlink(tmp);
    }
    g_free(c.buf);
    g_free(c.cbuf);
    meta_free(m);
    g_ptr_array_free(unref, true);
    ident_clear(&id);
    st->total_us = now_us() - t_begin;
    return st->ok ? 0 : -1;
}

static void stats_init(HxsStats *st, int slot, int mode, int codec, int level)
{
    memset(st, 0, sizeof(*st));
    st->slot = slot;
    st->mode = mode;
    st->codec = codec;
    st->level = level;
    st->worker_cpu = -1;
    st->file_codec = -1;
}

static void log_op(const char *op, const HxsStats *st)
{
    char line[900];
    hxs_describe(st, op, line, sizeof(line));
    HXS_LOG("[savestate] %s", line);
}

static int save_entry(int slot, int mode, int codec, int level,
                      bool wait_durable, bool compress_later, HxsStats *st)
{
    HxsStats local;
    if (!st) {
        st = &local;
    }
    if (mode == HXS_MODE_RAW) {
        codec = HXS_CODEC_NONE;
        level = 0;
    }
    if (mode == HXS_MODE_BACKGROUND && codec == HXS_CODEC_NONE) {
        mode = HXS_MODE_RAW;
    }
    if (mode == HXS_MODE_INLINE && codec == HXS_CODEC_NONE) {
        mode = HXS_MODE_RAW;
    }
    stats_init(st, slot, mode, codec, level);
    if (slot < 0 || slot > HXS_SLOT_AUTO || mode < 0 ||
        mode > HXS_MODE_DEFERRED || codec < 0 || codec > HXS_CODEC_ZSTD) {
        refuse(st, "bad-slot", "slot %d mode %d codec %d", slot, mode, codec);
        log_op("save", st);
        return -1;
    }
    pthread_mutex_lock(&hxs_op_mu);
    int r = save_locked(slot, mode, codec, level, wait_durable,
                        compress_later, st);
    pthread_mutex_unlock(&hxs_op_mu);
    log_op("save", st);
    return r;
}

int hxs_save(int slot, int mode, int codec, int level, bool wait_durable,
             HxsStats *st)
{
    return save_entry(slot, mode, codec, level, wait_durable, false, st);
}

int hxs_save_default(int slot, bool wait_durable, HxsStats *st)
{
    int mode, codec, level;
    hxs_default_mode(hxs_get_compression(), &mode, &codec, &level);
    return hxs_save(slot, mode, codec, level, wait_durable, st);
}

int hxs_save_auto_quit(HxsStats *st)
{
    int mode, codec, level;
    bool on = hxs_get_compression();
    hxs_default_mode(on, &mode, &codec, &level);
    /*
     * The process ends right after this returns, so nothing may be left to
     * a worker: deferred becomes raw, and a background compression is
     * picked up at the next start.
     */
    bool later = on && (mode == HXS_MODE_BACKGROUND ||
                        mode == HXS_MODE_DEFERRED);
    if (mode == HXS_MODE_DEFERRED || mode == HXS_MODE_BACKGROUND) {
        mode = HXS_MODE_RAW;
    }
    return save_entry(HXS_SLOT_AUTO, mode, codec, level, true, later, st);
}

/* ----------------------------------------------------------------- load */

/* The machine as it was before the last load, for undo load. */
static struct {
    bool valid;
    char *title;
    char *snap;
    uint8_t *buf;
    size_t cap;
    size_t len;
} undo;

typedef struct LoadCtx {
    HxsStats *st;
    const char *snap;
    uint8_t *raw;
    size_t raw_len;
    size_t raw_cap;
    const char *undo_snap; /* NULL: undo load, keep no undo */
    bool undo_made;
    bool changed;
    bool fell_back;
    bool ok;
    char reason[48];
    char err[192];
} LoadCtx;

static void load_fail(LoadCtx *c, const char *reason, Error *err)
{
    c->ok = false;
    pstrcpy(c->reason, sizeof(c->reason), reason);
    if (err) {
        pstrcpy(c->err, sizeof(c->err), error_get_pretty(err));
    }
}

static void load_main(void *o)
{
    LoadCtx *c = o;
    HxsStats *st = c->st;
    Error *err = NULL;
    int64_t t;

    c->ok = true;
    bool was_paused = runstate_check(RUN_STATE_PAUSED);
    if (!runstate_is_running() && !was_paused) {
        load_fail(c, "not-running", NULL);
        return;
    }
    if (was_paused) {
        vm_start();
    }
    global_state_store();
    int64_t t0 = now_us();
    vm_stop(RUN_STATE_RESTORE_VM);
    bdrv_drain_all_begin();

    if (c->undo_snap) {
        t = now_us();
        undo.valid = false;
        bool ok = make_disk_snapshot(c->undo_snap, &err);
        if (ok) {
            ok = save_to_buf(&undo.buf, &undo.cap, &undo.len, &err) >= 0;
            if (!ok) {
                bdrv_all_delete_snapshot(c->undo_snap, false, NULL, NULL);
            }
        }
        st->undo_us = now_us() - t;
        st->undo_region = xemu_snapshots_last_save_region();
        if (!ok) {
            load_fail(c, "undo-failed", err);
            goto out;
        }
        c->undo_made = true;
    }

    t = now_us();
    int ret = bdrv_all_goto_snapshot(c->snap, false, NULL, &err);
    st->goto_us = now_us() - t;
    if (ret < 0) {
        load_fail(c, "restore-failed", err);
        goto out;
    }
    c->changed = true;
    t = now_us();
    ret = load_from_buf(&c->raw, c->raw_len, c->raw_cap, &err);
    st->restore_us = now_us() - t;
    if (ret < 0) {
        load_fail(c, "restore-failed", err);
        if (c->undo_made) {
            /* Put the machine back as it was before this load. */
            Error *err2 = NULL;
            c->fell_back =
                bdrv_all_goto_snapshot(c->undo_snap, false, NULL, &err2) >= 0 &&
                load_from_buf(&undo.buf, undo.len, undo.cap, &err2) >= 0;
            error_free(err2);
        }
    }
    st->region = nv2a_display_region_hash(false);

out:
    bdrv_drain_all_end();
    error_free(err);
    /*
     * Started here, not by the frontend's resume path: that path clears the
     * GPU's flip and NOP waits, and the loaded state's waits must stand. The
     * machine is left running; the frontend closes its menu after a load.
     * A load refused before anything changed leaves it as it was.
     */
    vm_start();
    st->pause_us = now_us() - t0;
    if (was_paused && !c->changed) {
        vm_stop(RUN_STATE_PAUSED);
    }
}

static void undo_drop(void)
{
    char *snap = undo.snap;
    undo.snap = NULL;
    undo.valid = false;
    snap_delete(snap);
    g_free(snap);
}

int hxs_load(int slot, HxsStats *st)
{
    HxsStats local;
    Ident id;
    FileInfo fi = { 0 };
    uint8_t *payload = NULL, *raw = NULL;
    int fd = -1;
    g_autofree char *final = NULL;
    g_autofree char *undo_snap = NULL;
    const char *reason;
    int64_t t_begin = now_us();

    if (!st) {
        st = &local;
    }
    stats_init(st, slot, -1, -1, 0);
    if (slot < 0 || slot >= HXS_SLOT_COUNT) {
        refuse(st, "bad-slot", "slot %d", slot);
        log_op("load", st);
        return -1;
    }
    pthread_mutex_lock(&hxs_op_mu);
    ident_get(&id);
    st->check_us = now_us() - t_begin;
    if (refuse_ident(&id, st)) {
        goto done;
    }
    jobs_settle(id.title, -1, -1);
    final = slot_rel(id.title, slot);
    pthread_mutex_lock(&hxs_mu);
    fd = st_open(final, false);
    st->job_running = job_running_for(id.title, slot);
    pthread_mutex_unlock(&hxs_mu);
    if (fd < 0) {
        refuse(st, "empty", "slot %d is empty", slot);
        goto done;
    }
    reason = file_info_fd(fd, &fi);
    if (!reason) {
        reason = check_meta(fi.meta, &id);
    }
    st->file_codec = fi.h.codec;
    st->file_bytes = fi.size;
    st->raw_bytes = fi.h.raw_len;
    if (reason) {
        refuse(st, reason, "saved %s, running %s",
               fi.meta ? meta_get(fi.meta, !strcmp(reason, "title")
                                               ? "title_id"
                                           : !strcmp(reason, "controller-layout")
                                               ? "controllers"
                                               : reason) ?: "-"
                       : "-",
               !strcmp(reason, "schema")   ? id.schema
               : !strcmp(reason, "disc")   ? id.disc
               : !strcmp(reason, "title")  ? id.title
               : !strcmp(reason, "controller-layout") ? id.controllers
                                                      : "-");
        goto done;
    }
    st->codec = fi.h.codec;
    st->level = fi.h.level;
    int64_t t = now_us();
    payload = g_try_malloc(MAX(fi.h.payload_len, 1));
    if (!payload || pread_full(fd, payload, fi.h.payload_len,
                               HXS_HDR_LEN) < 0) {
        refuse(st, "open-failed", "reading slot %d failed", slot);
        goto done;
    }
    st->read_us = now_us() - t;
    close(fd);
    fd = -1;
    if (fi.h.codec != HXS_CODEC_NONE) {
        t = now_us();
        raw = g_try_malloc(MAX(fi.h.raw_len, 1));
        if (!raw || !decompress_payload(payload, fi.h.payload_len, fi.h.codec,
                                        raw, fi.h.raw_len, HXS_MAX_THREADS)) {
            refuse(st, "corrupt", "slot %d does not decompress", slot);
            goto done;
        }
        st->decompress_us = now_us() - t;
        g_free(payload);
        payload = NULL;
    } else {
        raw = payload;
        payload = NULL;
    }

    /* Room for the machine as it is now, mapped before the pause. */
    if (undo.cap < fi.h.raw_len + (8 << 20)) {
        g_free(undo.buf);
        undo.cap = fi.h.raw_len + (16 << 20);
        undo.buf = prefaulted(undo.cap);
        undo.len = 0;
        undo.valid = false;
        if (!undo.buf) {
            undo.cap = 0;
            refuse(st, "undo-failed", "out of memory");
            goto done;
        }
    }
    undo_snap = snap_name_new(id.title, "undo-load");
    LoadCtx c = { .st = st, .snap = meta_get(fi.meta, "disk_snap"),
                  .raw = raw, .raw_len = fi.h.raw_len,
                  .raw_cap = fi.h.raw_len, .undo_snap = undo_snap };
    on_main(load_main, &c);
    raw = c.raw;
    if (c.undo_made) {
        char *old = undo.snap;
        undo.snap = g_strdup(undo_snap);
        undo.valid = true;
        g_free(undo.title);
        undo.title = g_strdup(id.title);
        t = now_us();
        snap_delete(old);
        st->post_us = now_us() - t;
        g_free(old);
    } else {
        undo_drop();
    }
    if (!c.ok) {
        refuse(st, c.reason, "%s%s", c.err,
               c.fell_back ? " (the machine was put back)" : "");
        goto done;
    }
    st->ok = true;

done:
    if (fd >= 0) {
        close(fd);
    }
    g_free(payload);
    g_free(raw);
    file_info_clear(&fi);
    ident_clear(&id);
    pthread_mutex_unlock(&hxs_op_mu);
    st->total_us = now_us() - t_begin;
    log_op("load", st);
    return st->ok ? 0 : -1;
}

int hxs_undo_load(HxsStats *st)
{
    HxsStats local;
    Ident id;
    int64_t t_begin = now_us();

    if (!st) {
        st = &local;
    }
    stats_init(st, -1, -1, -1, 0);
    pthread_mutex_lock(&hxs_op_mu);
    ident_get(&id);
    st->check_us = now_us() - t_begin;
    if (refuse_ident(&id, st)) {
        goto done;
    }
    if (!undo.valid) {
        refuse(st, "nothing-to-undo", "no load to undo");
        goto done;
    }
    if (g_strcmp0(undo.title, id.title)) {
        refuse(st, "title", "the load to undo was in %s", undo.title);
        goto done;
    }
    if (!g_hash_table_contains(id.snaps, undo.snap)) {
        refuse(st, "disk-snapshot-missing", "%s", undo.snap);
        goto done;
    }
    LoadCtx c = { .st = st, .snap = undo.snap, .raw = undo.buf,
                  .raw_len = undo.len, .raw_cap = undo.cap };
    on_main(load_main, &c);
    undo.buf = c.raw;
    st->raw_bytes = undo.len;
    if (!c.ok) {
        refuse(st, c.reason, "%s", c.err);
        goto done;
    }
    st->ok = true;

done:
    ident_clear(&id);
    pthread_mutex_unlock(&hxs_op_mu);
    st->total_us = now_us() - t_begin;
    log_op("undo-load", st);
    return st->ok ? 0 : -1;
}

int hxs_undo_save(HxsStats *st)
{
    HxsStats local;
    Ident id;
    FileInfo fi = { 0 };
    int64_t t_begin = now_us();
    g_autofree char *u = NULL;
    g_autofree char *final = NULL;
    g_autofree char *swap = NULL;
    int r = 0;

    if (!st) {
        st = &local;
    }
    stats_init(st, -1, -1, -1, 0);
    pthread_mutex_lock(&hxs_op_mu);
    ident_get(&id);
    st->check_us = now_us() - t_begin;
    if (refuse_ident(&id, st)) {
        goto done;
    }
    u = slot_rel(id.title, HXS_SLOT_UNDO_SAVE);
    const char *reason = file_info(u, &fi);
    if (reason) {
        refuse(st, !strcmp(reason, "empty") ? "nothing-to-undo" : reason,
               "no save to undo");
        goto done;
    }
    const char *os = meta_get(fi.meta, "slot");
    int origin = os ? atoi(os) : -1;
    if (origin < 0 || origin >= HXS_SLOTS) {
        refuse(st, "corrupt", "undo-save names slot %s", os ? os : "-");
        goto done;
    }
    st->slot = origin;
    jobs_settle(id.title, origin, HXS_SLOT_UNDO_SAVE);
    final = slot_rel(id.title, origin);
    swap = g_strconcat(u, ".swap", NULL);
    pthread_mutex_lock(&hxs_mu);
    if (st_exists(final)) {
        /* The two trade places, so a second undo save puts them back. */
        r = st_rename(final, swap);
        if (!r) {
            r = st_rename(u, final);
        }
        if (!r) {
            r = st_rename(swap, u);
        }
    } else {
        r = st_rename(u, final);
    }
    st_sync_dir(id.title);
    pthread_mutex_unlock(&hxs_mu);
    if (r) {
        refuse(st, "undo-failed", "renaming failed: %s", strerror(-r));
        goto done;
    }
    st->ok = true;

done:
    file_info_clear(&fi);
    ident_clear(&id);
    pthread_mutex_unlock(&hxs_op_mu);
    st->total_us = now_us() - t_begin;
    log_op("undo-save", st);
    return st->ok ? 0 : -1;
}

int hxs_delete(int slot)
{
    Ident id;
    FileInfo fi = { 0 };
    char *snap = NULL;
    int r = -1;

    if (slot < 0 || slot >= HXS_SLOT_COUNT) {
        return -1;
    }
    pthread_mutex_lock(&hxs_op_mu);
    ident_get(&id);
    if (have_root() && id.title) {
        jobs_settle(id.title, slot, -1);
        g_autofree char *final = slot_rel(id.title, slot);
        g_autofree char *tmp = g_strconcat(final, ".tmp", NULL);
        g_autofree char *ztmp = g_strconcat(final, ".z.tmp", NULL);
        pthread_mutex_lock(&hxs_mu);
        if (!file_info(final, &fi)) {
            snap = g_strdup(meta_get(fi.meta, "disk_snap"));
        }
        r = st_unlink(final);
        st_unlink(tmp);
        st_unlink(ztmp);
        st_sync_dir(id.title);
        pthread_mutex_unlock(&hxs_mu);
        if (snap && !snap_referenced(id.title, snap)) {
            snap_delete(snap);
        }
    }
    HXS_LOG("[savestate] op=delete slot=%d ok=%d snap=%s", slot, r == 0,
            snap ? snap : "-");
    g_free(snap);
    file_info_clear(&fi);
    ident_clear(&id);
    pthread_mutex_unlock(&hxs_op_mu);
    return r;
}

bool hxs_can_undo_load(void)
{
    pthread_mutex_lock(&hxs_mu);
    bool v = undo.valid && !g_strcmp0(undo.title, last_title);
    pthread_mutex_unlock(&hxs_mu);
    return v;
}

bool hxs_can_undo_save(void)
{
    pthread_mutex_lock(&hxs_mu);
    bool v = false;
    if (have_root() && last_title) {
        g_autofree char *u = slot_rel(last_title, HXS_SLOT_UNDO_SAVE);
        v = st_exists(u);
    }
    pthread_mutex_unlock(&hxs_mu);
    return v;
}

/* --------------------------------------------------------- slot listing */

static char **sessions_read(void)
{
    char *s = read_text("sessions.log");
    char **lines = g_strsplit(s ? s : "", "\n", -1);
    g_free(s);
    return lines;
}

static void sessions_append(const char *title)
{
    char **lines = sessions_read();
    guint n = g_strv_length(lines);
    GString *out = g_string_new(NULL);
    for (guint i = n > 200 ? n - 200 : 0; i < n; i++) {
        if (*lines[i]) {
            g_string_append_printf(out, "%s\n", lines[i]);
        }
    }
    g_string_append_printf(out, "%" PRId64 "\t%s\n",
                           g_get_real_time() / 1000000,
                           title ? title : "-");
    write_text_atomic("sessions.log", out->str);
    g_string_free(out, true);
    g_strfreev(lines);
}

/* Whether a different title (or none) was started after this time. */
static bool other_title_since(char **sessions, const char *title,
                              int64_t saved_at)
{
    for (char **l = sessions; *l; l++) {
        char **f = g_strsplit(*l, "\t", 2);
        if (g_strv_length(f) == 2 &&
            g_ascii_strtoll(f[0], NULL, 10) > saved_at &&
            g_strcmp0(f[1], title)) {
            g_strfreev(f);
            return true;
        }
        g_strfreev(f);
    }
    return false;
}

static void slot_fill(const Ident *id, char **sessions, int slot,
                      HxsSlotInfo *out)
{
    g_autofree char *rel = slot_rel(id->title, slot);
    FileInfo fi;
    const char *reason = file_info(rel, &fi);

    memset(out, 0, sizeof(*out));
    out->origin_slot = slot;
    out->codec = -1;
    if (reason && !strcmp(reason, "empty")) {
        file_info_clear(&fi);
        return;
    }
    out->exists = true;
    out->file_bytes = fi.size;
    if (fi.meta) {
        const char *v = meta_get(fi.meta, "saved_at");
        out->saved_at = v ? g_ascii_strtoll(v, NULL, 10) : 0;
        v = meta_get(fi.meta, "slot");
        out->origin_slot = v ? atoi(v) : slot;
        pstrcpy(out->title_name, sizeof(out->title_name),
                meta_get(fi.meta, "title_name") ?: "");
        out->codec = fi.h.codec;
        reason = check_meta(fi.meta, id);
    }
    out->loadable = !reason;
    pstrcpy(out->reason, sizeof(out->reason), reason ? reason : "");
    out->other_title_since = other_title_since(sessions, id->title,
                                               out->saved_at);
    file_info_clear(&fi);
}

int hxs_slot_info(int slot, HxsSlotInfo *out)
{
    HxsSlotInfo all[HXS_SLOT_COUNT];
    if (slot < 0 || slot >= HXS_SLOT_COUNT || hxs_slot_list(all) < 0) {
        return -1;
    }
    *out = all[slot];
    return 0;
}

int hxs_slot_list(HxsSlotInfo out[HXS_SLOT_COUNT])
{
    Ident id;
    int r = -1;

    memset(out, 0, sizeof(HxsSlotInfo) * HXS_SLOT_COUNT);
    pthread_mutex_lock(&hxs_op_mu);
    ident_get(&id);
    if (have_root() && id.title) {
        jobs_settle(id.title, -1, -1);
        char **sessions = sessions_read();
        pthread_mutex_lock(&hxs_mu);
        for (int s = 0; s < HXS_SLOT_COUNT; s++) {
            slot_fill(&id, sessions, s, &out[s]);
        }
        pthread_mutex_unlock(&hxs_mu);
        g_strfreev(sessions);
        r = 0;
    }
    ident_clear(&id);
    pthread_mutex_unlock(&hxs_op_mu);
    return r;
}

int hxs_newest_loadable(HxsSlotInfo *out)
{
    HxsSlotInfo all[HXS_SLOT_COUNT];
    int best = -1;

    if (hxs_slot_list(all) < 0) {
        return -1;
    }
    for (int s = 0; s <= HXS_SLOT_AUTO; s++) {
        if (all[s].exists && all[s].loadable && !all[s].other_title_since &&
            (best < 0 || all[s].saved_at > all[best].saved_at)) {
            best = s;
        }
    }
    if (best >= 0 && out) {
        *out = all[best];
    }
    return best;
}

/* -------------------------------------------------------------- startup */

/* Finishes or removes what an interrupted save or compression left. */
static void startup_title(const char *title, bool requeue)
{
    GArray *ents = st_list(title);
    if (!ents) {
        return;
    }
    for (guint i = 0; i < ents->len; i++) {
        StEnt *e = &g_array_index(ents, StEnt, i);
        g_autofree char *rel = g_build_filename(title, e->name, NULL);
        FileInfo fi;
        const char *reason;

        if (e->dir) {
            continue;
        }
        if (g_str_has_suffix(e->name, ".hxs.z.tmp")) {
            g_autofree char *base = g_strndup(e->name, strlen(e->name) - 6);
            g_autofree char *final = g_build_filename(title, base, NULL);
            FileInfo ff;
            reason = file_info(rel, &fi);
            const char *fr = file_info(final, &ff);
            bool same = !reason && !fr &&
                        !g_strcmp0(meta_get(fi.meta, "disk_snap"),
                                   meta_get(ff.meta, "disk_snap"));
            bool keep = !reason && (fr || same);
            if (keep) {
                st_rename(rel, final);
            } else {
                st_unlink(rel);
            }
            HXS_LOG("[savestate] startup %s %s", rel,
                    keep ? "promoted" : "removed");
            file_info_clear(&ff);
            file_info_clear(&fi);
        } else if (g_str_has_suffix(e->name, ".hxs.tmp")) {
            g_autofree char *base = g_strndup(e->name, strlen(e->name) - 4);
            int slot = slot_from_file(base);
            g_autofree char *final = g_build_filename(title, base, NULL);
            FileInfo ff;
            reason = file_info(rel, &fi);
            const char *fr = file_info(final, &ff);
            const char *how = "removed";
            if (!reason && slot >= 0 && fr) {
                st_rename(rel, final);
                how = "promoted";
            } else if (!reason && slot >= 0 &&
                       g_ascii_strtoll(meta_get(fi.meta, "saved_at") ?: "0",
                                       NULL, 10) >
                           g_ascii_strtoll(meta_get(ff.meta, "saved_at")
                                               ?: "0", NULL, 10)) {
                GPtrArray *unref = g_ptr_array_new_with_free_func(g_free);
                place_file(title, slot, rel, unref);
                g_ptr_array_free(unref, true);
                how = "placed";
            } else {
                st_unlink(rel);
            }
            HXS_LOG("[savestate] startup %s %s", rel, how);
            file_info_clear(&ff);
            file_info_clear(&fi);
        } else if (!strcmp(e->name, "undo-save.hxs.swap")) {
            reason = file_info(rel, &fi);
            int origin = !reason ? atoi(meta_get(fi.meta, "slot") ?: "-1")
                                 : -1;
            g_autofree char *u = slot_rel(title, HXS_SLOT_UNDO_SAVE);
            if (!st_exists(u)) {
                st_rename(rel, u);
            } else if (origin >= 0 && origin < HXS_SLOTS) {
                g_autofree char *final = slot_rel(title, origin);
                if (!st_exists(final)) {
                    st_rename(rel, final);
                } else {
                    st_unlink(rel);
                }
            } else {
                st_unlink(rel);
            }
            HXS_LOG("[savestate] startup %s recovered", rel);
            file_info_clear(&fi);
        }
    }
    st_sync_dir(title);

    /* Raw files that were to be compressed: the quit save, a lost job. */
    for (int s = 0; requeue && s < HXS_SLOT_COUNT; s++) {
        g_autofree char *rel = slot_rel(title, s);
        FileInfo fi;
        if (!file_info(rel, &fi) && fi.h.codec == HXS_CODEC_NONE &&
            !g_strcmp0(meta_get(fi.meta, "compress_later"), "1")) {
            HxsJob *j = g_new0(HxsJob, 1);
            j->kind = JOB_COMPRESS;
            j->title = g_strdup(title);
            j->slot = s;
            j->codec = HXS_ON_CODEC;
            j->level = HXS_ON_LEVEL;
            j->t_stop = now_us();
            pthread_mutex_lock(&hxs_mu);
            job_push(j);
            pthread_mutex_unlock(&hxs_mu);
        }
        file_info_clear(&fi);
    }
    g_array_unref(ents);
}

/* Every snapshot a file under the root names. */
static GHashTable *referenced_snaps(bool *listed)
{
    GHashTable *refs = g_hash_table_new_full(g_str_hash, g_str_equal, g_free,
                                             NULL);
    GArray *dirs = st_list("");
    *listed = dirs != NULL;
    for (guint i = 0; dirs && i < dirs->len; i++) {
        StEnt *d = &g_array_index(dirs, StEnt, i);
        if (!d->dir || !title_ok(d->name)) {
            continue;
        }
        GArray *ents = st_list(d->name);
        for (guint k = 0; ents && k < ents->len; k++) {
            StEnt *e = &g_array_index(ents, StEnt, k);
            if (e->dir || !strstr(e->name, ".hxs")) {
                continue;
            }
            g_autofree char *rel = g_build_filename(d->name, e->name, NULL);
            FileInfo fi;
            if (!file_info(rel, &fi)) {
                const char *s = meta_get(fi.meta, "disk_snap");
                if (s && *s) {
                    g_hash_table_add(refs, g_strdup(s));
                }
            }
            file_info_clear(&fi);
        }
        if (ents) {
            g_array_unref(ents);
        }
    }
    if (dirs) {
        g_array_unref(dirs);
    }
    return refs;
}

typedef struct SnapList {
    GHashTable *names;
} SnapList;

static void snaplist_main(void *o)
{
    ((SnapList *)o)->names = snapshot_names();
}

static GHashTable *snaps_now(void)
{
    SnapList l = { 0 };
    on_main(snaplist_main, &l);
    return l.names;
}

/*
 * Deletes this root's snapshots that no file names, and every undo-load
 * snapshot (the RAM that went with it is gone). Snapshots of other roots
 * are left alone: their files may come back with that folder.
 */
static int startup_gc(void)
{
    bool listed;
    GHashTable *refs = referenced_snaps(&listed);
    int n = 0;
    if (listed) {
        GHashTable *names = snaps_now();
        g_autofree char *prefix = g_strdup_printf("hxs-%s-", cfg_root8);
        GHashTableIter it;
        gpointer k;
        g_hash_table_iter_init(&it, names);
        while (g_hash_table_iter_next(&it, &k, NULL)) {
            const char *name = k;
            if (g_str_has_prefix(name, prefix) &&
                (strstr(name, "-undo-load-") ||
                 !g_hash_table_contains(refs, name))) {
                snap_delete(name);
                n++;
            }
        }
        g_hash_table_destroy(names);
    }
    g_hash_table_destroy(refs);
    return n;
}

static void startup_files(bool requeue)
{
    GArray *dirs = st_list("");
    for (guint i = 0; dirs && i < dirs->len; i++) {
        StEnt *d = &g_array_index(dirs, StEnt, i);
        if (d->dir && title_ok(d->name)) {
            startup_title(d->name, requeue);
        }
    }
    if (dirs) {
        g_array_unref(dirs);
    }
}

/* ------------------------------------------------------------ auto-load */

typedef struct LayoutCall {
    char *layout;
} LayoutCall;

static void layout_main(void *o)
{
    ((LayoutCall *)o)->layout = xemu_snapshots_running_controllers();
}

static int64_t machine_start_us;

static void auto_load_run(void)
{
    /* The controllers are bound a moment after start; wait until they settle. */
    int64_t t0 = now_us(), since = t0;
    char *prev = NULL;
    while (now_us() - t0 < 8000000) {
        LayoutCall l = { 0 };
        on_main(layout_main, &l);
        if (prev && !strcmp(prev, l.layout)) {
            g_free(l.layout);
            if (now_us() - since >= 1000000) {
                break;
            }
        } else {
            g_free(prev);
            prev = l.layout;
            since = now_us();
        }
        sleep_ms(200);
    }
    g_free(prev);

    HxsSlotInfo pick, all[HXS_SLOT_COUNT];
    char *msg;
    int best = hxs_newest_loadable(&pick);
    if (best >= 0) {
        HxsStats st;
        if (hxs_load(best, &st) == 0) {
            msg = g_strdup_printf("ok\t%d\t%" PRId64 "\t%.0f", best,
                                  pick.saved_at, st.pause_us / 1000.0);
        } else {
            msg = g_strdup_printf("refused\t%d\t%s", best, st.reason);
        }
    } else if (hxs_slot_list(all) < 0) {
        msg = g_strdup("none");
    } else {
        /* Nothing loadable: name why the newest state is not. */
        int newest = -1;
        for (int s = 0; s <= HXS_SLOT_AUTO; s++) {
            if (all[s].exists &&
                (newest < 0 || all[s].saved_at > all[newest].saved_at)) {
                newest = s;
            }
        }
        if (newest >= 0) {
            msg = g_strdup_printf("refused\t%d\t%s", newest,
                                  all[newest].other_title_since &&
                                          all[newest].loadable
                                      ? "other-title-since"
                                      : all[newest].reason);
        } else {
            msg = g_strdup("none");
        }
    }
    HXS_LOG("[savestate] auto-load result=\"%s\" after_ms=%.0f", msg,
            (now_us() - machine_start_us) / 1000.0);
    set_auto_load_msg(msg);
}

/* ----------------------------------------------------------- the test */

static void test_main(void);

static void *start_thread(void *arg)
{
    (void)arg;
    pthread_setname_np(pthread_self(), "hxs-start");
    worker_start();

    pthread_mutex_lock(&hxs_mu);
    char *boot = g_strdup(cfg_boot_title);
    bool requeue = cfg_compression && !cfg_testing;
    bool auto_load = cfg_auto_load;
    pthread_mutex_unlock(&hxs_mu);

    pthread_mutex_lock(&hxs_op_mu);
    int gc = 0;
    if (have_root()) {
        st_mkdir("");
        sessions_append(boot);
        startup_files(requeue);
        gc = startup_gc();
    }
    pthread_mutex_unlock(&hxs_op_mu);
    HXS_LOG("[savestate] startup root=%s title=%s gc=%d ms=%.0f",
            hxs_root_label(), boot ? boot : "-", gc,
            (now_us() - machine_start_us) / 1000.0);
    g_free(boot);

    if (cfg_testing) {
        test_main();
    } else if (auto_load) {
        auto_load_run();
    } else {
        set_auto_load_msg(g_strdup("off"));
    }
    return NULL;
}

static bool hxs_started;
static QEMUTimer *hdd_log_timer;

static void hdd_log_tick(void *opaque);

static void vm_change(void *opaque, bool running, RunState state)
{
    (void)opaque;
    (void)state;
    if (!running || hxs_started) {
        return;
    }
    hxs_started = true;
    machine_start_us = now_us();
    if (cfg_testing) {
        hdd_log_timer = timer_new_ms(QEMU_CLOCK_REALTIME, hdd_log_tick, NULL);
        timer_mod(hdd_log_timer, qemu_clock_get_ms(QEMU_CLOCK_REALTIME));
    }
    pthread_t t;
    if (pthread_create(&t, NULL, start_thread, NULL) == 0) {
        pthread_detach(t);
    }
}

void hxs_init(void)
{
    const char *dir = getenv("HAKUX_STATE_DIR");
    const char *test = getenv("HAKUX_SAVESTATE_TEST");

    /*
     * A request's environment stays set for the sessions after it, so a
     * scratch folder serves one session only: <dir>.done marks it used, and
     * a later session keeps the configured folder and runs no test.
     */
    if (dir && *dir) {
        g_autofree char *mark = g_strconcat(dir, ".done", NULL);
        if (access(mark, F_OK) == 0) {
            HXS_LOG("[savestate] init scratch %s already used; ignored", dir);
            dir = NULL;
            test = NULL;
        } else {
            g_autofree char *parent = g_path_get_dirname(mark);
            g_mkdir_with_parents(parent, 0700);
            int fd = open(mark, O_WRONLY | O_CREAT | O_CLOEXEC, 0600);
            if (fd >= 0) {
                close(fd);
            }
            hxs_set_root(dir);
        }
    }
    cfg_testing = test && *test;
    qemu_add_vm_change_state_handler(vm_change, NULL);
    HXS_LOG("[savestate] init root=%s compression=%d auto_load=%d "
            "boot_title=%s testing=%d",
            hxs_root_label(), cfg_compression, cfg_auto_load,
            cfg_boot_title ? cfg_boot_title : "-", cfg_testing);
}

void hxs_describe(const HxsStats *s, const char *op, char *out, int len)
{
    snprintf(out, len,
             "op=%s slot=%d ok=%d reason=%s mode=%s codec=%s level=%d thr=%d "
             "total_ms=%.1f check_ms=%.1f pause_ms=%.1f disksnap_ms=%.1f "
             "serialize_ms=%.1f compress_ms=%.1f write_ms=%.1f cpu_ms=%.1f "
             "durable_ms=%.1f read_ms=%.1f decompress_ms=%.1f undo_ms=%.1f "
             "goto_ms=%.1f restore_ms=%.1f post_ms=%.1f raw=%" PRIu64
             " bytes=%" PRIu64 " region=%016" PRIx64 " undo_region=%016" PRIx64
             " file_codec=%s job_running=%d worker_cpu=%d snap=%s err=\"%s\"",
             op, s->slot, s->ok, s->reason[0] ? s->reason : "-",
             s->mode >= 0 ? mode_name(s->mode) : "-",
             s->codec >= 0 ? codec_name(s->codec) : "-", s->level, s->threads,
             s->total_us / 1000.0, s->check_us / 1000.0, s->pause_us / 1000.0,
             s->disksnap_us / 1000.0, s->serialize_us / 1000.0,
             s->compress_us / 1000.0, s->write_us / 1000.0,
             s->cpu_us / 1000.0, s->durable_us / 1000.0, s->read_us / 1000.0,
             s->decompress_us / 1000.0, s->undo_us / 1000.0,
             s->goto_us / 1000.0, s->restore_us / 1000.0,
             s->post_us / 1000.0, s->raw_bytes, s->file_bytes, s->region,
             s->undo_region,
             s->file_codec >= 0 ? codec_name(s->file_codec) : "-",
             s->job_running, s->worker_cpu,
             s->disk_snap[0] ? s->disk_snap : "-", s->error);
}

/*
 * ---------------------------------------------------------------------------
 * HAKUX_SAVESTATE_TEST=<start_s>:<plans>, plans joined by '+':
 *   func     every feature once, one "[savestate] step=..." line each
 *   measure  HAKUX_SAVESTATE_CYCLES rounds of every option in
 *            HAKUX_SAVESTATE_OPTS, each followed by a 10 s window for the
 *            frame pacing report
 *   disk     HAKUX_SAVESTATE_DISK=<save_s>,<load_s>[,<undo_s>]: the hard
 *            disk rewind, by partition hashes
 * It runs only with HAKUX_STATE_DIR set and a hard disk image whose name
 * contains "titles" (the dispatcher's scratch image), and it removes the
 * folder and every hxs-* snapshot before it ends.
 * ---------------------------------------------------------------------------
 */

static uint64_t hdd_file_size(const char *path)
{
    struct stat sb;
    return path && stat(path, &sb) == 0 ? (uint64_t)sb.st_size : 0;
}

static void hdd_log_tick(void *opaque)
{
    (void)opaque;
    BlockBackend *blk = hdd_blk();
    if (!blk) {
        return;
    }
    BlockAcctStats *s = blk_get_stats(blk);
    BlockDriverState *bs = blk_bs(blk);
    double t = (now_us() - machine_start_us) / 1e6;
    HXS_LOG("[savestate] hdd t=%.1f wr_ops=%" PRIu64 " wr_bytes=%" PRIu64
            " file_bytes=%" PRIu64,
            t, s->nr_ops[BLOCK_ACCT_WRITE], s->nr_bytes[BLOCK_ACCT_WRITE],
            hdd_file_size(bs ? bs->filename : NULL));
    timer_mod(hdd_log_timer, qemu_clock_get_ms(QEMU_CLOCK_REALTIME) +
                                 (t < 90 ? 1000 : 10000));
}

static bool test_pass = true;

static void test_step(const char *step, bool pass, const char *fmt, ...)
    G_GNUC_PRINTF(3, 4);
static void test_step(const char *step, bool pass, const char *fmt, ...)
{
    va_list ap;
    va_start(ap, fmt);
    char *d = g_strdup_vprintf(fmt, ap);
    va_end(ap);
    test_pass &= pass;
    HXS_LOG("[savestate] step=%s pass=%d t=%.1f %s", step, pass,
            (now_us() - machine_start_us) / 1e6, d);
    g_free(d);
}

typedef struct RegionCall {
    uint64_t h;
    char state[32];
} RegionCall;

static void region_main(void *o)
{
    RegionCall *c = o;
    bool running = runstate_is_running();
    if (running) {
        vm_stop(RUN_STATE_PAUSED);
    }
    c->h = nv2a_display_region_hash(true);
    if (running) {
        vm_start();
    }
}

/* The display region now, with the GPU's surfaces written back. */
static uint64_t region_now(void)
{
    RegionCall c = { 0 };
    on_main(region_main, &c);
    return c.h;
}

static void state_main(void *o)
{
    RegionCall *c = o;
    pstrcpy(c->state, sizeof(c->state), RunState_str(runstate_get()));
}

static const char *run_state(char *buf, size_t n)
{
    RegionCall c = { 0 };
    on_main(state_main, &c);
    pstrcpy(buf, n, c.state);
    return buf;
}

static void pause_main(void *o)
{
    (void)o;
    if (runstate_is_running()) {
        vm_stop(RUN_STATE_PAUSED);
    }
}

static void resume_main(void *o)
{
    (void)o;
    if (!runstate_is_running()) {
        vm_start();
    }
}

typedef struct DelAll {
    int deleted;
    int left;
} DelAll;

static void delall_main(void *o)
{
    DelAll *c = o;
    GHashTable *names = snapshot_names();
    GHashTableIter it;
    gpointer k;
    g_hash_table_iter_init(&it, names);
    while (g_hash_table_iter_next(&it, &k, NULL)) {
        if (g_str_has_prefix(k, "hxs-")) {
            bdrv_all_delete_snapshot(k, false, NULL, NULL);
            c->deleted++;
        }
    }
    g_hash_table_destroy(names);
    names = snapshot_names();
    c->left = g_hash_table_size(names);
    g_hash_table_destroy(names);
}

static DelAll delete_all_hxs(void)
{
    DelAll c = { 0 };
    on_main(delall_main, &c);
    return c;
}

static void rm_tree(const char *path)
{
    DIR *d = opendir(path);
    if (d) {
        struct dirent *de;
        while ((de = readdir(d))) {
            if (!strcmp(de->d_name, ".") || !strcmp(de->d_name, "..")) {
                continue;
            }
            g_autofree char *p = g_build_filename(path, de->d_name, NULL);
            struct stat sb;
            if (lstat(p, &sb) == 0 && S_ISDIR(sb.st_mode)) {
                rm_tree(p);
            } else {
                unlink(p);
            }
        }
        closedir(d);
    }
    rmdir(path);
}

static void sleep_until(double t_s)
{
    sleep_ms((int64_t)(t_s * 1000) - (now_us() - machine_start_us) / 1000);
}

static double t_now(void)
{
    return (now_us() - machine_start_us) / 1e6;
}

/* ---- func */

static void test_func(void)
{
    HxsStats a, b, c, d;
    char rs[32];
    Ident id;

    /* F1: a raw save and load bring the scene back. */
    hxs_save(0, HXS_MODE_RAW, 0, 0, true, &a);
    sleep_ms(3000);
    uint64_t before = region_now();
    hxs_load(0, &b);
    test_step("F1", a.ok && b.ok && b.region == a.region && before != a.region,
              "save_region=%016" PRIx64 " before_load=%016" PRIx64
              " after_load=%016" PRIx64 " scene_moved=%d",
              a.region, before, b.region, before != a.region);

    /* F2: background compression; a load while it runs reads a complete file. */
    hxs_save(1, HXS_MODE_BACKGROUND, HXS_CODEC_ZSTD, 3, false, &a);
    sleep_ms(1000);
    hxs_load(1, &b);
    bool idle = hxs_wait_idle(60000);
    sleep_ms(1000);
    hxs_load(1, &c);
    test_step("F2", a.ok && b.ok && c.ok && idle && b.region == a.region &&
                        c.region == a.region &&
                        c.file_codec == HXS_CODEC_ZSTD,
              "first_load_codec=%s job_running=%d second_load_codec=%s "
              "raw_bytes=%" PRIu64 " zstd_bytes=%" PRIu64,
              codec_name(b.file_codec), b.job_running,
              codec_name(c.file_codec), b.file_bytes, c.file_bytes);

    /* F3: undo load returns to the machine before the last load. */
    sleep_ms(2000);
    hxs_load(0, &a);
    sleep_ms(1000);
    hxs_undo_load(&b);
    test_step("F3", a.ok && b.ok && b.region == a.undo_region &&
                        a.undo_region != a.region,
              "kept_region=%016" PRIx64 " loaded_region=%016" PRIx64
              " after_undo=%016" PRIx64 " undo_ms=%.1f",
              a.undo_region, a.region, b.region, a.undo_us / 1000.0);

    /* F4: undo save puts the previous slot 0 back, and a second one redoes. */
    sleep_ms(2000);
    HxsStats f1;
    hxs_save(0, HXS_MODE_RAW, 0, 0, true, &f1);
    bool can = hxs_can_undo_save();
    hxs_undo_save(&a);
    hxs_load(0, &b);
    uint64_t r_old = b.region;
    hxs_undo_save(&c);
    hxs_load(0, &d);
    test_step("F4", can && a.ok && b.ok && c.ok && d.ok &&
                        d.region == f1.region && r_old != f1.region,
              "new_region=%016" PRIx64 " after_undo_save=%016" PRIx64
              " after_redo=%016" PRIx64 " origin_slot=%d",
              f1.region, r_old, d.region, a.slot);

    /* F5: the quit save, then the auto-load choice and load. */
    sleep_ms(2000);
    hxs_save_auto_quit(&a);
    sleep_ms(2000);
    HxsSlotInfo info;
    int pick = hxs_newest_loadable(&info);
    if (pick >= 0) {
        hxs_load(pick, &b);
    } else {
        stats_init(&b, -1, -1, -1, 0);
    }
    test_step("F5", a.ok && pick == HXS_SLOT_AUTO && b.ok &&
                        b.region == a.region,
              "auto_mode=%s auto_ms=%.1f picked=%d region_match=%d "
              "(across runs: owner check)",
              mode_name(a.mode), a.total_us / 1000.0, pick,
              b.region == a.region);

    /* F5b: the function a boot with auto-load on runs; auto is the newest. */
    auto_load_run();
    g_autofree char *al = g_strdup(hxs_auto_load_message());
    g_autofree char *al_want = g_strdup_printf("ok\t%d\t", HXS_SLOT_AUTO);
    bool al_ok = al && g_str_has_prefix(al, al_want);
    test_step("F5b", al_ok, "auto_load_result=\"%s\"",
              al ? g_strdelimit(al, "\t", ' ') : "-");

    /* F6: a state from a different device-state schema is refused. */
    hxs_save(2, HXS_MODE_RAW, 0, 0, true, &a);
    xemu_savevm_schema_test_mutate("nv2a");
    hxs_load(2, &b);
    const char *field = xemu_savevm_schema_test_mutated_field();
    g_autofree char *mutated = g_strdup(field ? field : "-");
    xemu_savevm_schema_test_mutate(NULL);
    uint64_t r1 = region_now();
    sleep_ms(1500);
    uint64_t r2 = region_now();
    test_step("F6", a.ok && !b.ok && !strcmp(b.reason, "schema") &&
                        b.pause_us == 0 && b.restore_us == 0 && r1 != r2 &&
                        !strcmp(run_state(rs, sizeof(rs)), "running"),
              "field=%s reason=%s stopped_ms=%.1f still_running=%s "
              "scene_moves=%d",
              mutated, b.reason, b.pause_us / 1000.0, rs, r1 != r2);

    /* F7: a state written by another build loads when the schema matches. */
    xemu_snapshots_set_test_overrides(NULL, "build-A-test");
    hxs_save(3, HXS_MODE_RAW, 0, 0, true, &a);
    xemu_snapshots_set_test_overrides(NULL, NULL);
    hxs_load(3, &b);
    ident_get(&id);
    test_step("F7", a.ok && b.ok && b.region == a.region,
              "saved_build=build-A-test running_build=%s schema=%s",
              id.build, id.schema);
    ident_clear(&id);

    /* F8: controller layout, title and disc are still compared. */
    hxs_save(4, HXS_MODE_RAW, 0, 0, true, &a);
    xemu_snapshots_set_test_overrides("test-layout", NULL);
    hxs_load(4, &b);
    xemu_snapshots_set_test_overrides(NULL, NULL);
    test_meta_key = "title_id";
    test_meta_val = "deadbeef";
    hxs_save(5, HXS_MODE_RAW, 0, 0, true, &c);
    test_meta_key = NULL;
    HxsStats e, f, g;
    hxs_load(5, &e);
    test_meta_key = "disc";
    test_meta_val = "0000";
    hxs_save(6, HXS_MODE_RAW, 0, 0, true, &f);
    test_meta_key = NULL;
    hxs_load(6, &g);
    test_step("F8", a.ok && !b.ok && !strcmp(b.reason, "controller-layout") &&
                        c.ok && !e.ok && !strcmp(e.reason, "title") && f.ok &&
                        !g.ok && !strcmp(g.reason, "disc"),
              "layout=%s title=%s disc=%s", b.reason, e.reason, g.reason);

    /* F9: deleting a slot removes its file and its disk snapshot. */
    g_autofree char *snap6 = g_strdup(f.disk_snap);
    int dr = hxs_delete(6) | hxs_delete(5);
    ident_get(&id);
    bool gone = !g_hash_table_contains(id.snaps, snap6);
    g_autofree char *rel6 = slot_rel(id.title, 6);
    bool file_gone = !st_exists(rel6);
    test_step("F9", dr == 0 && gone && file_gone,
              "snapshot_gone=%d file_gone=%d snapshots=%u", gone, file_gone,
              g_hash_table_size(id.snaps));
    ident_clear(&id);

    /* F10: the slot list. */
    HxsSlotInfo all[HXS_SLOT_COUNT];
    int lr = hxs_slot_list(all);
    GString *s = g_string_new(NULL);
    int shown = 0;
    for (int i = 0; i < HXS_SLOT_COUNT; i++) {
        if (all[i].exists) {
            shown++;
            g_string_append_printf(s, " %d:%s:%s:%" PRId64 ":%s", i,
                                   all[i].loadable ? "ok" : "no",
                                   all[i].reason[0] ? all[i].reason : "-",
                                   all[i].saved_at,
                                   all[i].codec >= 0 ? codec_name(all[i].codec)
                                                     : "-");
        }
    }
    test_step("F10", lr == 0 && shown >= 5 && all[4].exists &&
                        all[4].loadable,
              "slots=%d%s", shown, s->str);
    g_string_free(s, true);

    /* F11: a save while paused stays paused; a load from paused runs. */
    on_main(pause_main, NULL);
    hxs_save(7, HXS_MODE_RAW, 0, 0, true, &a);
    char after_save[32];
    run_state(after_save, sizeof(after_save));
    hxs_load(7, &b);
    char after_load[32];
    run_state(after_load, sizeof(after_load));
    sleep_ms(1500);
    uint64_t moved = region_now();
    test_step("F11", a.ok && b.ok && !strcmp(after_save, "paused") &&
                        !strcmp(after_load, "running") &&
                        b.region == a.region && moved != a.region,
              "after_save=%s after_load=%s region_match=%d scene_moves=%d",
              after_save, after_load, b.region == a.region,
              moved != a.region);
    on_main(resume_main, NULL);
}

/* ---- measure */

typedef struct Opt {
    char name[16];
    int mode;
    int codec;
    int level;
    int threads;
} Opt;

static bool parse_opt(const char *s, Opt *o)
{
    memset(o, 0, sizeof(*o));
    pstrcpy(o->name, sizeof(o->name), s);
    o->threads = 1;
    switch (s[0]) {
    case 'a':
        o->mode = HXS_MODE_RAW;
        return true;
    case 'b':
        o->mode = HXS_MODE_INLINE;
        break;
    case 'c':
        o->mode = HXS_MODE_BACKGROUND;
        break;
    case 'd':
        o->mode = HXS_MODE_DEFERRED;
        break;
    default:
        return false;
    }
    const char *c = s[1] == '-' ? s + 2 : "";
    if (g_str_has_prefix(c, "lz4")) {
        o->codec = HXS_CODEC_LZ4;
        o->level = 1;
        c += 3;
    } else if (g_str_has_prefix(c, "zstd")) {
        o->codec = HXS_CODEC_ZSTD;
        c += 4;
        o->level = (int)strtol(c, (char **)&c, 10);
        o->level = o->level ? o->level : 3;
    } else if (g_str_has_prefix(c, "none")) {
        o->codec = HXS_CODEC_NONE;
        c += 4;
    } else {
        return false;
    }
    if (*c == 'x') {
        o->threads = MAX(1, MIN(atoi(c + 1), HXS_MAX_THREADS));
    }
    return true;
}

static void test_measure(void)
{
    const char *opts_env = getenv("HAKUX_SAVESTATE_OPTS");
    const char *cycles_env = getenv("HAKUX_SAVESTATE_CYCLES");
    int cycles = cycles_env ? MAX(1, atoi(cycles_env)) : 2;
    char **names = g_strsplit(opts_env && *opts_env
                                  ? opts_env
                                  : "a,b-lz4,b-zstd1,b-zstd3,b-zstd1x4,"
                                    "c-zstd3,c-lz4,d-zstd3,d-none",
                              ",", -1);
    GArray *opts = g_array_new(false, true, sizeof(Opt));
    for (char **n = names; *n; n++) {
        Opt o;
        if (parse_opt(*n, &o)) {
            g_array_append_val(opts, o);
        } else {
            HXS_LOG("[savestate] measure bad-option=%s", *n);
        }
    }
    g_strfreev(names);

    HxsStats st, ld;
    hxs_save(9, HXS_MODE_RAW, 0, 0, true, &st);
    HXS_LOG("[savestate] measure base ok=%d raw=%" PRIu64 " t=%.1f", st.ok,
            st.raw_bytes, t_now());
    for (int k = 0; k < 3; k++) {
        hxs_load(9, &ld);
        sleep_ms(1000);
        HXS_LOG("[savestate] win begin opt=base cycle=%d", k);
        sleep_ms(10000);
        HXS_LOG("[savestate] win end opt=base cycle=%d", k);
    }
    for (int cy = 0; cy < cycles; cy++) {
        for (guint i = 0; i < opts->len; i++) {
            Opt *o = &g_array_index(opts, Opt, i);
            hxs_load(9, &ld);
            sleep_ms(1000);
            inline_threads = o->threads;
            pthread_mutex_lock(&hxs_mu);
            uint64_t seq0 = last_job_seq;
            pthread_mutex_unlock(&hxs_mu);
            hxs_save(8, o->mode, o->codec, o->level, false, &st);
            inline_threads = HXS_ON_THREADS;
            HXS_LOG("[savestate] measure save opt=%s cycle=%d ok=%d "
                    "pause_ms=%.1f durable_ms=%.1f raw=%" PRIu64
                    " bytes=%" PRIu64 " cpu_ms=%.1f",
                    o->name, cy, st.ok, st.pause_us / 1000.0,
                    st.durable_us / 1000.0, st.raw_bytes, st.file_bytes,
                    st.cpu_us / 1000.0);
            HXS_LOG("[savestate] win begin opt=%s cycle=%d", o->name, cy);
            sleep_ms(10000);
            HXS_LOG("[savestate] win end opt=%s cycle=%d", o->name, cy);
            bool idle = hxs_wait_idle(120000);
            pthread_mutex_lock(&hxs_mu);
            uint64_t seq1 = last_job_seq;
            pthread_mutex_unlock(&hxs_mu);
            HxsStats js;
            if (seq1 != seq0 && job_result(seq1, &js)) {
                HXS_LOG("[savestate] measure job opt=%s cycle=%d ok=%d "
                        "compress_ms=%.1f io_ms=%.1f cpu_ms=%.1f "
                        "compressed_ms=%.1f durable_ms=%.1f bytes=%" PRIu64
                        " worker_cpu=%d idle=%d",
                        o->name, cy, js.ok, js.compress_us / 1000.0,
                        js.write_us / 1000.0, js.cpu_us / 1000.0,
                        js.compressed_us / 1000.0, js.durable_us / 1000.0,
                        js.file_bytes, js.worker_cpu, idle);
            }
            hxs_load(8, &ld);
            HXS_LOG("[savestate] measure load opt=%s cycle=%d ok=%d "
                    "pause_ms=%.1f total_ms=%.1f read_ms=%.1f "
                    "decompress_ms=%.1f undo_ms=%.1f goto_ms=%.1f "
                    "restore_ms=%.1f bytes=%" PRIu64 " codec=%s",
                    o->name, cy, ld.ok, ld.pause_us / 1000.0,
                    ld.total_us / 1000.0, ld.read_us / 1000.0,
                    ld.decompress_us / 1000.0, ld.undo_us / 1000.0,
                    ld.goto_us / 1000.0, ld.restore_us / 1000.0,
                    ld.file_bytes,
                    ld.file_codec >= 0 ? codec_name(ld.file_codec) : "-");
            sleep_ms(1000);
        }
    }
    g_array_free(opts, true);
}

/* ---- disk */

static const struct {
    const char *name;
    uint64_t off;
    uint64_t len;
} parts[] = {
    { "X", 0x80000ULL, 0x2EE00000ULL },
    { "Y", 0x2EE80000ULL, 0x2EE00000ULL },
    { "Z", 0x5DC80000ULL, 0x2EE00000ULL },
    { "C", 0x8CA80000ULL, 0x1F400000ULL },
    { "E", 0xABE80000ULL, 0x1312D6000ULL },
};
#define NPARTS 5

typedef struct DiskHash {
    uint64_t h[NPARTS + 1];      /* the partitions, then the rest */
    uint64_t data[NPARTS + 1];   /* bytes of non-zero data hashed */
    bool fatx[NPARTS];
    uint64_t wr_ops;
    int64_t us;
} DiskHash;

static uint64_t mix64(uint64_t h, uint64_t v)
{
    h ^= v * 0x9E3779B97F4A7C15ULL;
    h = (h << 31) | (h >> 33);
    return h * 0xC2B2AE3D27D4EB4FULL;
}

static bool block_zero(const uint8_t *p, size_t n)
{
    const uint64_t *q = (const uint64_t *)p;
    for (size_t i = 0; i < n / 8; i++) {
        if (q[i]) {
            return false;
        }
    }
    return true;
}

/* Hashes the non-zero 4 KiB blocks of [off, off+len) with their offsets. */
static void hash_range(BlockBackend *blk, BlockDriverState *bs, uint64_t off,
                       uint64_t len, uint64_t *h, uint64_t *data,
                       uint8_t *buf)
{
    uint64_t end = off + len;
    while (off < end) {
        int64_t pnum = 0;
        int ret = bdrv_block_status_above(bs, NULL, off, end - off, &pnum,
                                          NULL, NULL);
        if (ret < 0 || pnum <= 0) {
            *h = mix64(*h, 0xBADBADULL);
            return;
        }
        if ((ret & BDRV_BLOCK_DATA) && !(ret & BDRV_BLOCK_ZERO)) {
            for (uint64_t p = off; p < off + pnum;) {
                size_t n = MIN((uint64_t)(1 << 20), off + pnum - p);
                if (blk_pread(blk, p, n, buf, 0) < 0) {
                    *h = mix64(*h, 0xBADBAD2ULL);
                    break;
                }
                for (size_t b = 0; b < n; b += 4096) {
                    size_t bn = MIN((size_t)4096, n - b);
                    if (block_zero(buf + b, bn)) {
                        continue;
                    }
                    *h = mix64(*h, p + b);
                    const uint64_t *q = (const uint64_t *)(buf + b);
                    for (size_t i = 0; i < bn / 8; i++) {
                        *h = mix64(*h, q[i]);
                    }
                    *data += bn;
                }
                p += n;
            }
        }
        off += pnum;
    }
}

static void diskhash_main(void *o)
{
    DiskHash *d = o;
    int64_t t0 = now_us();
    bool running = runstate_is_running();
    BlockBackend *blk = hdd_blk();
    BlockDriverState *bs = blk ? blk_bs(blk) : NULL;

    if (!bs) {
        return;
    }
    if (running) {
        vm_stop(RUN_STATE_PAUSED);
    }
    uint8_t *buf = g_malloc(1 << 20);
    for (int i = 0; i < NPARTS; i++) {
        d->h[i] = 0x51ED270B2C1D0E3FULL;
        hash_range(blk, bs, parts[i].off, parts[i].len, &d->h[i], &d->data[i],
                   buf);
        uint8_t m[4] = { 0 };
        d->fatx[i] = blk_pread(blk, parts[i].off, 4, m, 0) >= 0 &&
                     !memcmp(m, "FATX", 4);
    }
    int64_t size = blk_getlength(blk);
    uint64_t e_end = parts[NPARTS - 1].off + parts[NPARTS - 1].len;
    d->h[NPARTS] = 0x51ED270B2C1D0E3FULL;
    hash_range(blk, bs, 0, parts[0].off, &d->h[NPARTS], &d->data[NPARTS],
               buf);
    if (size > 0 && (uint64_t)size > e_end) {
        hash_range(blk, bs, e_end, size - e_end, &d->h[NPARTS],
                   &d->data[NPARTS], buf);
    }
    g_free(buf);
    d->wr_ops = blk_get_stats(blk)->nr_ops[BLOCK_ACCT_WRITE];
    if (running) {
        vm_start();
    }
    d->us = now_us() - t0;
}

static DiskHash disk_hash(const char *tag)
{
    DiskHash d = { 0 };
    on_main(diskhash_main, &d);
    GString *s = g_string_new(NULL);
    for (int i = 0; i <= NPARTS; i++) {
        g_string_append_printf(s, " %s=%016" PRIx64 "/%" PRIu64 "%s",
                               i < NPARTS ? parts[i].name : "rest", d.h[i],
                               d.data[i],
                               i < NPARTS ? (d.fatx[i] ? "/fatx" : "/nofatx")
                                          : "");
    }
    HXS_LOG("[savestate] disk-hash tag=%s t=%.1f ms=%.0f wr_ops=%" PRIu64 "%s",
            tag, t_now(), d.us / 1000.0, d.wr_ops, s->str);
    g_string_free(s, true);
    return d;
}

static void disk_diff(const DiskHash *a, const DiskHash *b, GString *out)
{
    for (int i = 0; i <= NPARTS; i++) {
        if (a->h[i] != b->h[i]) {
            g_string_append_printf(out, "%s%s", out->len ? "," : "",
                                   i < NPARTS ? parts[i].name : "rest");
        }
    }
    if (!out->len) {
        g_string_append(out, "none");
    }
}

static bool disk_same(const DiskHash *a, const DiskHash *b)
{
    return !memcmp(a->h, b->h, sizeof(a->h));
}

static bool all_fatx(const DiskHash *d)
{
    for (int i = 0; i < NPARTS; i++) {
        if (!d->fatx[i]) {
            return false;
        }
    }
    return true;
}

/*
 * Milliseconds until the display region changes, sampled once a second, or
 * -1 after limit_ms. A title screen holds the region still for half a minute
 * (187's, 1461488), so a single 5 s look reads a running game as stopped.
 */
static int64_t wait_moving(int64_t limit_ms)
{
    int64_t t0 = now_us();
    uint64_t r0 = region_now();
    while ((now_us() - t0) / 1000 < limit_ms) {
        sleep_ms(1000);
        if (region_now() != r0) {
            return (now_us() - t0) / 1000;
        }
    }
    return -1;
}

static void test_disk(void)
{
    const char *env = getenv("HAKUX_SAVESTATE_DISK");
    double save_s = 0, load_s = 0, undo_s = 0;
    if (!env || sscanf(env, "%lf,%lf,%lf", &save_s, &load_s, &undo_s) < 2) {
        HXS_LOG("[savestate] disk refused: HAKUX_SAVESTATE_DISK unset");
        test_pass = false;
        return;
    }
    HxsStats a, b, c;
    sleep_until(save_s);
    DiskHash h0 = disk_hash("H0-at-save");
    hxs_save(7, HXS_MODE_RAW, 0, 0, true, &a);
    sleep_until(load_s);
    DiskHash h1 = disk_hash("H1-before-load");
    hxs_load(7, &b);
    DiskHash h2 = disk_hash("H2-after-load");
    int64_t moved = wait_moving(30000);
    GString *d01 = g_string_new(NULL), *d02 = g_string_new(NULL);
    disk_diff(&h0, &h1, d01);
    disk_diff(&h0, &h2, d02);
    test_step("D1", a.ok && b.ok && !disk_same(&h0, &h1) &&
                        disk_same(&h0, &h2) && all_fatx(&h2) && moved >= 0,
              "game_wrote=%s writes_between=%" PRIu64
              " after_load_differs=%s fatx=%d game_runs=%d moved_ms=%" PRId64,
              d01->str, h1.wr_ops - h0.wr_ops, d02->str, all_fatx(&h2),
              moved >= 0, moved);
    g_string_free(d01, true);
    g_string_free(d02, true);
    if (undo_s > 0) {
        sleep_until(undo_s);
        hxs_undo_load(&c);
        DiskHash h3 = disk_hash("H3-after-undo-load");
        GString *d13 = g_string_new(NULL);
        disk_diff(&h1, &h3, d13);
        moved = wait_moving(60000);
        test_step("D2", c.ok && disk_same(&h1, &h3) && all_fatx(&h3) &&
                            moved >= 0,
                  "after_undo_differs_from_H1=%s fatx=%d game_runs=%d "
                  "moved_ms=%" PRId64,
                  d13->str, all_fatx(&h3), moved >= 0, moved);
        g_string_free(d13, true);
    }
}

static void test_main(void)
{
    const char *env = getenv("HAKUX_SAVESTATE_TEST");
    double start_s = g_ascii_strtod(env, NULL);
    const char *colon = strchr(env, ':');
    const char *plans = colon ? colon + 1 : "func";
    Ident id;

    ident_get(&id);
    /* The folder is removed at the end: only a scratch folder qualifies. */
    g_autofree char *base = cfg_root ? g_path_get_basename(cfg_root) : NULL;
    bool safe = cfg_root && !cfg_has_ops && getenv("HAKUX_STATE_DIR") &&
                base && g_str_has_prefix(base, "hxs-test") &&
                id.hdd_path && strstr(id.hdd_path, "titles");
    HXS_LOG("[savestate] test plans=%s start_s=%.0f root=%s hdd=%s fmt=%s "
            "title=%s safe=%d",
            plans, start_s, cfg_root ? cfg_root : "-",
            id.hdd_path ? id.hdd_path : "-", id.hdd_fmt ? id.hdd_fmt : "-",
            id.title ? id.title : "-", safe);
    ident_clear(&id);
    if (!safe) {
        HXS_LOG("[savestate] done ok=0 reason=unsafe");
        return;
    }
    double func_s = start_s;
    if (strstr(plans, "disk")) {
        double save_s = 0;
        const char *d = getenv("HAKUX_SAVESTATE_DISK");
        if (d) {
            save_s = g_ascii_strtod(d, NULL);
        }
        start_s = MIN(start_s, MAX(save_s - 2, 1));
    }
    sleep_until(start_s);
    DelAll del = delete_all_hxs();
    HXS_LOG("[savestate] test begin t=%.1f snapshots_deleted=%d left=%d",
            t_now(), del.deleted, del.left);
    if (strstr(plans, "disk")) {
        test_disk();
    }
    if (strstr(plans, "func")) {
        /*
         * F1, F3 and F4 tell states apart by the region, so they need a
         * moving scene: the disk test's loads leave the game on its title
         * screen, which F1-F4 read as still in 1461488.
         */
        if (strstr(plans, "disk")) {
            sleep_until(func_s);
            int64_t moved = wait_moving(60000);
            HXS_LOG("[savestate] func waits for a moving scene t=%.1f "
                    "moved_ms=%" PRId64, t_now(), moved);
        }
        test_func();
    }
    if (strstr(plans, "measure")) {
        test_measure();
    }
    bool idle = hxs_wait_idle(120000);
    pthread_mutex_lock(&hxs_op_mu);
    undo_drop();
    del = delete_all_hxs();
    rm_tree(cfg_root);
    bool dir_gone = access(cfg_root, F_OK) != 0;
    pthread_mutex_unlock(&hxs_op_mu);
    ident_get(&id);
    HXS_LOG("[savestate] done ok=%d t=%.1f idle=%d snapshots_deleted=%d "
            "snaps_left=%d dir_gone=%d hdd_bytes=%" PRIu64,
            test_pass, t_now(), idle, del.deleted, del.left, dir_gone,
            hdd_file_size(id.hdd_path));
    ident_clear(&id);
}
