/*
 * xemu User Interface
 *
 * Copyright (C) 2020-2025 Matt Borgerson
 *
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation; either version 2 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program.  If not, see <http://www.gnu.org/licenses/>.
 */

#include "xemu-snapshots.h"
#include "xemu-settings.h"
#include "xemu-xbe.h"
#include "xemu-input.h"
#include "xemu-version.h"

#if defined(ANDROID) || defined(__ANDROID__)
#define XEMU_SNAPSHOTS_GL 0
#include <android/log.h>
#else
#define XEMU_SNAPSHOTS_GL 1
#include <SDL2/SDL.h>
#include <epoxy/gl.h>
#endif

#if defined(__linux__) || defined(__ANDROID__)
#include <dlfcn.h>
#include "elf.h"
#endif

#include "block/aio.h"
#include "block/block_int.h"
#include "block/qapi.h"
#include "block/qdict.h"
#include "block/block-io.h"
#include "migration/qemu-file.h"
#include "migration/snapshot.h"
#include "qapi/error.h"
#include "qapi/qapi-commands-block.h"
#include "qemu/bswap.h"
#include "qemu/main-loop.h"
#include "qemu/timer.h"
#include "system/block-backend.h"
#include "system/runstate.h"

#include "ui/console.h"
#include "ui/input.h"

#if defined(ANDROID) || defined(__ANDROID__)
#define SNAP_LOG(...) \
    __android_log_print(ANDROID_LOG_INFO, "hakuX-lane", __VA_ARGS__)
#else
#define SNAP_LOG(...)                 \
    do {                              \
        fprintf(stderr, __VA_ARGS__); \
        fputc('\n', stderr);          \
    } while (0)
#endif

static QEMUSnapshotInfo *xemu_snapshots_metadata = NULL;
static XemuSnapshotData *xemu_snapshots_extra_data = NULL;
static int xemu_snapshots_len = 0;
static bool xemu_snapshots_dirty = true;

const char **g_snapshot_shortcut_index_key_map[] = {
    &g_config.general.snapshots.shortcuts.f5,
    &g_config.general.snapshots.shortcuts.f6,
    &g_config.general.snapshots.shortcuts.f7,
    &g_config.general.snapshots.shortcuts.f8,
};

/*
 * Identity of the running machine, written into a version 2 header and
 * compared before a load. Keys and values are short strings.
 */
#define SNAP_KEY_SCHEMA "schema"
#define SNAP_KEY_BUILD "build"
#define SNAP_KEY_TITLE_ID "title_id"
#define SNAP_KEY_DISC "disc"
#define SNAP_KEY_CONTROLLERS "controllers"
#define SNAP_KEY_REGION "region"

/* The disc is hashed outside the save (no block reads inside its drain). */
static char *snap_disc_path;
static char *snap_disc_sha;

/* A layout written in place of the real one; the test sequence uses it. */
static char *snap_layout_override;

/* What the last save and load measured; the test sequence logs them. */
static int64_t snap_last_save_us;
static int64_t snap_last_load_us;
static int64_t snap_last_check_us;
static uint64_t snap_last_save_region;
static uint64_t snap_last_load_region;
static const char *snap_last_refuse;

static QEMUTimer *snap_repause_timer;

static void xemu_snapshots_append_build_id(GString *s)
{
#if defined(__linux__) || defined(__ANDROID__)
    Dl_info info;

    if (!dladdr((void *)&xemu_snapshots_save, &info) || !info.dli_fbase) {
        return;
    }
#if UINTPTR_MAX > 0xffffffffu
    typedef Elf64_Ehdr Ehdr;
    typedef Elf64_Phdr Phdr;
    typedef Elf64_Nhdr Nhdr;
#else
    typedef Elf32_Ehdr Ehdr;
    typedef Elf32_Phdr Phdr;
    typedef Elf32_Nhdr Nhdr;
#endif
    const uint8_t *base = info.dli_fbase;
    const Ehdr *eh = (const Ehdr *)base;
    if (memcmp(eh->e_ident, ELFMAG, SELFMAG)) {
        return;
    }
    const Phdr *ph = (const Phdr *)(base + eh->e_phoff);
    uintptr_t page = qemu_real_host_page_size();
    uintptr_t min_vaddr = UINTPTR_MAX;
    for (int i = 0; i < eh->e_phnum; i++) {
        if (ph[i].p_type == PT_LOAD && ph[i].p_vaddr < min_vaddr) {
            min_vaddr = ph[i].p_vaddr & ~(page - 1);
        }
    }
    if (min_vaddr == UINTPTR_MAX) {
        return;
    }
    const uint8_t *bias = base - min_vaddr;
    for (int i = 0; i < eh->e_phnum; i++) {
        if (ph[i].p_type != PT_NOTE) {
            continue;
        }
        const uint8_t *p = bias + ph[i].p_vaddr;
        const uint8_t *end = p + ph[i].p_memsz;
        while (p + sizeof(Nhdr) <= end) {
            const Nhdr *n = (const Nhdr *)p;
            const uint8_t *name = p + sizeof(Nhdr);
            const uint8_t *desc = name + ROUND_UP(n->n_namesz, 4);
            if (desc + n->n_descsz > end) {
                break;
            }
            if (n->n_type == 3 /* NT_GNU_BUILD_ID */ && n->n_namesz == 4 &&
                !memcmp(name, "GNU", 4)) {
                g_string_append_c(s, '+');
                for (uint32_t j = 0; j < n->n_descsz; j++) {
                    g_string_append_printf(s, "%02x", desc[j]);
                }
                return;
            }
            p = desc + ROUND_UP(n->n_descsz, 4);
        }
    }
#endif
}

static char *xemu_snapshots_build(void)
{
    static char *build;

    if (!build) {
        GString *s = g_string_new(xemu_commit);
        xemu_snapshots_append_build_id(s);
        build = g_string_free(s, false);
    }
    return g_strdup(build);
}

static char *xemu_snapshots_title_id(void)
{
    struct xbe *xbe_data = xemu_get_xbe_info();
    if (!xbe_data || !xbe_data->cert) {
        return g_strdup("");
    }
    return g_strdup_printf("%08x", xbe_data->cert->m_titleid);
}

/*
 * Ports that hold a device each add a USB device to the machine's state. A
 * state saved with a device on a port the running machine leaves empty does
 * not load (xemu #2241), so the layout is part of the identity.
 */
static char *xemu_snapshots_controller_layout(void)
{
    if (snap_layout_override) {
        return g_strdup(snap_layout_override);
    }

    GString *s = g_string_new(NULL);
    for (int i = 0; i < 4; i++) {
        ControllerState *c = xemu_input_get_bound(i);
        if (i) {
            g_string_append_c(s, ';');
        }
        if (!c) {
            g_string_append_c(s, '-');
            continue;
        }
        g_string_append_printf(s, "%s,%d,%d",
                               bound_drivers[i] ? bound_drivers[i] : "?",
                               c->peripheral_types[0], c->peripheral_types[1]);
    }
    return g_string_free(s, false);
}

/*
 * A sampled hash of the disc: its length and 1 MiB at its start, middle and
 * end. It tells discs apart without reading a whole one.
 */
static void xemu_snapshots_update_disc_sha(void)
{
    char *path = xemu_get_currently_loaded_disc_path();

    if (!g_strcmp0(path, snap_disc_path) && snap_disc_sha) {
        g_free(path);
        return;
    }
    g_free(snap_disc_path);
    g_free(snap_disc_sha);
    snap_disc_path = path;

    BlockBackend *blk = path ? blk_by_name("ide0-cd1") : NULL;
    int64_t len = blk ? blk_getlength(blk) : -1;
    if (len <= 0) {
        snap_disc_sha = g_strdup("");
        return;
    }

    const int64_t chunk = 1024 * 1024;
    int64_t offsets[3] = { 0, QEMU_ALIGN_DOWN(len / 2, 2048),
                           len > chunk ? QEMU_ALIGN_DOWN(len - chunk, 2048) : 0 };
    GChecksum *sum = g_checksum_new(G_CHECKSUM_SHA256);
    uint8_t *buf = g_malloc(chunk);
    uint64_t len_le = cpu_to_le64(len);
    bool read_ok = true;

    g_checksum_update(sum, (const guchar *)&len_le, sizeof(len_le));
    for (int i = 0; i < 3; i++) {
        int64_t n = MIN(chunk, len - offsets[i]);
        if (blk_pread(blk, offsets[i], n, buf, 0) < 0) {
            read_ok = false;
            break;
        }
        g_checksum_update(sum, buf, n);
    }
    snap_disc_sha = read_ok ? g_strdup(g_checksum_get_string(sum))
                            : g_strdup_printf("unread-%" PRId64, len);
    g_checksum_free(sum);
    g_free(buf);
}

static char *xemu_snapshots_disc_sha(void)
{
    char *path = xemu_get_currently_loaded_disc_path();
    char *sha = g_strcmp0(path, snap_disc_path) ? g_strdup("") :
                                                  g_strdup(snap_disc_sha);
    g_free(path);
    return sha;
}

static void xemu_snapshots_put_field(GByteArray *a, const char *key,
                                     const char *val)
{
    uint8_t klen = MIN(strlen(key), 255);
    uint16_t vlen = MIN(strlen(val), 65535);
    uint16_t vlen_be = cpu_to_be16(vlen);

    g_byte_array_append(a, &klen, 1);
    g_byte_array_append(a, (const guint8 *)key, klen);
    g_byte_array_append(a, (const guint8 *)&vlen_be, 2);
    g_byte_array_append(a, (const guint8 *)val, vlen);
}

/* Reads the header of a saved state: version 1's fields, then version 2's. */
static bool xemu_snapshots_read_header(BlockDriverState *bs_ro,
                                       QEMUSnapshotInfo *info,
                                       XemuSnapshotData *data,
                                       GHashTable *fields, uint32_t *version,
                                       Error **err)
{
    int res = bdrv_snapshot_load_tmp(bs_ro, info->id_str, info->name, err);
    if (res < 0) {
        return false;
    }

    uint32_t header[3];
    int64_t offset = 0;
    res = bdrv_load_vmstate(bs_ro, (uint8_t *)&header, offset, sizeof(header));
    if (res != sizeof(header)) {
        return false;
    }
    offset += res;

    *version = be32_to_cpu(header[1]);
    if (be32_to_cpu(header[0]) != XEMU_SNAPSHOT_DATA_MAGIC ||
        *version < 1 || *version > XEMU_SNAPSHOT_DATA_VERSION) {
        return false;
    }

    size_t size = be32_to_cpu(header[2]);
    if (size < 9) {
        return false;
    }
    uint8_t *buf = g_malloc(size);
    res = bdrv_load_vmstate(bs_ro, buf, offset, size);
    if (res != size) {
        g_free(buf);
        return false;
    }

    bool ok = false;
    offset = 0;

    const size_t disc_path_size = ldl_be_p(&buf[offset]);
    offset += 4;
    if (size < offset + disc_path_size + 1) {
        goto out;
    }
    if (disc_path_size && data) {
        data->disc_path = g_strndup((const char *)&buf[offset], disc_path_size);
    }
    offset += disc_path_size;

    const size_t xbe_title_name_size = buf[offset];
    offset += 1;
    if (size < offset + xbe_title_name_size + 4) {
        goto out;
    }
    if (xbe_title_name_size && data) {
        data->xbe_title_name =
            g_strndup((const char *)&buf[offset], xbe_title_name_size);
    }
    offset += xbe_title_name_size;

    const size_t thumbnail_size = ldl_be_p(&buf[offset]);
    offset += 4;
    if (size < offset + thumbnail_size) {
        goto out;
    }
#if XEMU_SNAPSHOTS_GL
    if (thumbnail_size && data) {
        GLuint thumbnail;
        glGenTextures(1, &thumbnail);
        if (xemu_snapshots_load_png_to_texture(thumbnail, &buf[offset],
                                               thumbnail_size)) {
            data->gl_thumbnail = thumbnail;
        } else {
            glDeleteTextures(1, &thumbnail);
        }
    }
#endif
    offset += thumbnail_size;

    if (*version >= 2) {
        if (size < offset + 4) {
            goto out;
        }
        uint32_t nfields = ldl_be_p(&buf[offset]);
        offset += 4;
        for (uint32_t i = 0; i < nfields; i++) {
            if (size < offset + 1) {
                goto out;
            }
            size_t klen = buf[offset];
            offset += 1;
            if (size < offset + klen + 2) {
                goto out;
            }
            char *key = g_strndup((const char *)&buf[offset], klen);
            offset += klen;
            size_t vlen = lduw_be_p(&buf[offset]);
            offset += 2;
            if (size < offset + vlen) {
                g_free(key);
                goto out;
            }
            char *val = g_strndup((const char *)&buf[offset], vlen);
            offset += vlen;
            if (fields) {
                g_hash_table_replace(fields, key, val);
            } else {
                g_free(key);
                g_free(val);
            }
        }
    }
    ok = true;

out:
    g_free(buf);
    return ok;
}

static void xemu_snapshots_load_data(BlockDriverState *bs_ro,
                                     QEMUSnapshotInfo *info,
                                     XemuSnapshotData *data, Error **err)
{
    uint32_t version;

    data->disc_path = NULL;
    data->xbe_title_name = NULL;
    data->gl_thumbnail = 0;
    xemu_snapshots_read_header(bs_ro, info, data, NULL, &version, err);
}

static BlockDriverState *xemu_snapshots_open_ro(const char *filename,
                                                Error **err)
{
    QDict *opts = qdict_new();

    qdict_put_bool(opts, BDRV_OPT_READ_ONLY, true);
    return bdrv_open(filename, NULL, opts,
                     BDRV_O_RO_WRITE_SHARE | BDRV_O_AUTO_RDONLY, err);
}

static void xemu_snapshots_close_ro(BlockDriverState *bs_ro)
{
    bdrv_flush(bs_ro);
    bdrv_drain(bs_ro);
    assert(bs_ro->refcnt == 1);
    bdrv_unref(bs_ro);
}

static void xemu_snapshots_all_load_data(QEMUSnapshotInfo **info,
                                         XemuSnapshotData **data,
                                         int snapshots_len, Error **err)
{
    BlockDriverState *bs_ro;

    assert(info && data);

    if (*data) {
        for (int i = 0; i < xemu_snapshots_len; ++i) {
            g_free((*data)[i].disc_path);
            g_free((*data)[i].xbe_title_name);
#if XEMU_SNAPSHOTS_GL
            if ((*data)[i].gl_thumbnail) {
                glDeleteTextures(1, &((*data)[i].gl_thumbnail));
            }
#endif
        }
        g_free(*data);
    }

    *data =
        (XemuSnapshotData *)g_malloc(sizeof(XemuSnapshotData) * snapshots_len);
    memset(*data, 0, sizeof(XemuSnapshotData) * snapshots_len);

    bs_ro = xemu_snapshots_open_ro(g_config.sys.files.hdd_path, err);
    if (!bs_ro) {
        return;
    }

    for (int i = 0; i < snapshots_len; ++i) {
        xemu_snapshots_load_data(bs_ro, (*info) + i, (*data) + i, err);
        if (*err) {
            break;
        }
    }

    xemu_snapshots_close_ro(bs_ro);
    if (!(*err))
        xemu_snapshots_dirty = false;
}

int xemu_snapshots_list(QEMUSnapshotInfo **info, XemuSnapshotData **extra_data,
                        Error **err)
{
    BlockDriverState *bs;
    int snapshots_len;
    assert(err);

    if (!xemu_snapshots_dirty && xemu_snapshots_extra_data &&
        xemu_snapshots_metadata) {
        goto done;
    }

    if (xemu_snapshots_metadata)
        g_free(xemu_snapshots_metadata);

    bs = bdrv_all_find_vmstate_bs(NULL, false, NULL, err);
    if (!bs) {
        return -1;
    }

    snapshots_len = bdrv_snapshot_list(bs, &xemu_snapshots_metadata);
    xemu_snapshots_all_load_data(&xemu_snapshots_metadata,
                                 &xemu_snapshots_extra_data, snapshots_len,
                                 err);
    if (*err) {
        return -1;
    }

    xemu_snapshots_len = snapshots_len;

done:
    if (info) {
        *info = xemu_snapshots_metadata;
    }

    if (extra_data) {
        *extra_data = xemu_snapshots_extra_data;
    }

    return xemu_snapshots_len;
}

char *xemu_get_currently_loaded_disc_path(void)
{
    char *file = NULL;
    BlockInfoList *block_list, *info;

    block_list = qmp_query_block(NULL);

    for (info = block_list; info; info = info->next) {
        if (strcmp("ide0-cd1", info->value->device)) {
            continue;
        }

        if (info->value->inserted && info->value->inserted->node_name) {
            file = g_strdup(info->value->inserted->file);
        }
    }

    qapi_free_BlockInfoList(block_list);
    return file;
}

static bool xemu_snapshots_refuse(const char *reason, Error **err,
                                  const char *detail_saved,
                                  const char *detail_running)
{
    snap_last_refuse = reason;
    SNAP_LOG("[snap] refuse reason=%s saved=%s running=%s", reason,
             detail_saved ? detail_saved : "", detail_running ? detail_running : "");
    error_setg(err, "Snapshot refused: %s differs", reason);
    return false;
}

/*
 * Compares a saved state's header with the running machine. Runs before
 * load_snapshot, which resets the machine before it reads anything.
 */
static bool xemu_snapshots_check(const char *vm_name, Error **err)
{
    QEMUSnapshotInfo sn;
    BlockDriverState *bs, *bs_ro;
    GHashTable *fields;
    uint32_t version = 0;
    bool ok;

    snap_last_refuse = NULL;
    bs = bdrv_all_find_vmstate_bs(NULL, false, NULL, err);
    if (!bs) {
        snap_last_refuse = "no-disk";
        return false;
    }
    if (bdrv_snapshot_find(bs, &sn, vm_name) < 0) {
        return xemu_snapshots_refuse("missing", err, vm_name, NULL);
    }

    bdrv_flush_all();
    bs_ro = xemu_snapshots_open_ro(bs->filename[0] ? bs->filename :
                                   g_config.sys.files.hdd_path, err);
    if (!bs_ro) {
        snap_last_refuse = "open";
        return false;
    }
    fields = g_hash_table_new_full(g_str_hash, g_str_equal, g_free, g_free);
    Error *local_err = NULL;
    ok = xemu_snapshots_read_header(bs_ro, &sn, NULL, fields, &version,
                                    &local_err);
    xemu_snapshots_close_ro(bs_ro);
    if (local_err) {
        snap_last_refuse = "header";
        error_propagate(err, local_err);
        g_hash_table_destroy(fields);
        return false;
    }
    if (!ok || version < 2) {
        g_autofree char *v = g_strdup_printf("%u", version);
        g_hash_table_destroy(fields);
        return xemu_snapshots_refuse("header", err, v, "2");
    }

    xemu_snapshots_update_disc_sha();
    struct {
        const char *key;
        const char *reason;
        char *running;
    } checks[] = {
        { SNAP_KEY_BUILD, "build", xemu_snapshots_build() },
        { SNAP_KEY_TITLE_ID, "title", xemu_snapshots_title_id() },
        { SNAP_KEY_DISC, "disc", xemu_snapshots_disc_sha() },
        { SNAP_KEY_CONTROLLERS, "controller-layout",
          xemu_snapshots_controller_layout() },
        { SNAP_KEY_SCHEMA, "schema", xemu_savevm_schema_fingerprint() },
    };

    ok = true;
    for (int i = 0; i < ARRAY_SIZE(checks); i++) {
        const char *saved = g_hash_table_lookup(fields, checks[i].key);
        if (ok && g_strcmp0(saved, checks[i].running)) {
            ok = xemu_snapshots_refuse(checks[i].reason, err, saved,
                                       checks[i].running);
        }
        g_free(checks[i].running);
    }
    g_hash_table_destroy(fields);
    return ok;
}

static void xemu_snapshots_repause(void *opaque)
{
    bool flip, nop, ctx;

    nv2a_get_wait_flags(&flip, &nop, &ctx);
    SNAP_LOG("[snap] repause state=%s flip=%d nop=%d ctx=%d",
             RunState_str(runstate_get()), flip, nop, ctx);
    if (runstate_is_running()) {
        vm_stop(RUN_STATE_PAUSED);
    }
}

/*
 * QEMU runs the device state handlers only when the machine leaves the
 * running state: from paused, vm_stop() notifies no one, and the GPU and
 * audio post-save hooks then release locks they never took. A save or load
 * requested while paused therefore starts the machine first and pauses it
 * again afterwards.
 */
void xemu_snapshots_load(const char *vm_name, Error **err)
{
    bool was_paused = runstate_check(RUN_STATE_PAUSED);
    int64_t t0 = g_get_monotonic_time();

    snap_last_load_us = 0;
    if (!runstate_is_running() && !was_paused) {
        error_setg(err, "Snapshot load needs a running or paused machine");
        return;
    }
    if (!xemu_snapshots_check(vm_name, err)) {
        snap_last_check_us = g_get_monotonic_time() - t0;
        return;
    }
    snap_last_check_us = g_get_monotonic_time() - t0;

    if (was_paused) {
        vm_start();
    }
    vm_stop(RUN_STATE_RESTORE_VM);
    t0 = g_get_monotonic_time();
    bool ok = load_snapshot(vm_name, NULL, false, NULL, err);
    snap_last_load_us = g_get_monotonic_time() - t0;
    if (!ok) {
        return;
    }
    snap_last_load_region = nv2a_display_region_hash(false);
    /*
     * Started here, not by the frontend's resume path: that path clears the
     * GPU's flip and NOP waits, and the loaded state's waits must stand. A
     * load asked for while paused runs briefly first, so that those waits
     * are consumed before the machine pauses again.
     */
    vm_start();
    if (was_paused) {
        if (!snap_repause_timer) {
            snap_repause_timer =
                timer_new_ms(QEMU_CLOCK_REALTIME, xemu_snapshots_repause, NULL);
        }
        timer_mod(snap_repause_timer,
                  qemu_clock_get_ms(QEMU_CLOCK_REALTIME) + 250);
    }
}

void xemu_snapshots_save(const char *vm_name, Error **err)
{
    bool was_paused = runstate_check(RUN_STATE_PAUSED);

    snap_last_save_us = 0;
    if (!runstate_is_running() && !was_paused) {
        error_setg(err, "Snapshot save needs a running or paused machine");
        return;
    }
    xemu_snapshots_update_disc_sha();
    if (was_paused) {
        vm_start();
    }
    int64_t t0 = g_get_monotonic_time();
    save_snapshot(vm_name, true, NULL, false, NULL, err);
    snap_last_save_us = g_get_monotonic_time() - t0;
    if (was_paused) {
        vm_stop(RUN_STATE_PAUSED);
    }
}

void xemu_snapshots_delete(const char *vm_name, Error **err)
{
    delete_snapshot(vm_name, false, NULL, err);
}

void xemu_snapshots_save_extra_data(QEMUFile *f)
{
    char *path = xemu_get_currently_loaded_disc_path();
    size_t path_size = path ? strlen(path) : 0;

    size_t xbe_title_name_size = 0;
    char *xbe_title_name = NULL;
    struct xbe *xbe_data = xemu_get_xbe_info();
    if (xbe_data && xbe_data->cert) {
        glong items_written = 0;
        xbe_title_name = g_utf16_to_utf8(xbe_data->cert->m_title_name, 40, NULL, &items_written, NULL);
        if (xbe_title_name) {
            xbe_title_name_size = MIN(items_written, 255);
        }
    }

    size_t thumbnail_size = 0;
    void *thumbnail_buf = NULL;
#if XEMU_SNAPSHOTS_GL
    thumbnail_buf = xemu_snapshots_create_framebuffer_thumbnail_png(&thumbnail_size);
#endif

    /* The GPU wrote its surfaces back to RAM when the machine stopped. */
    snap_last_save_region = nv2a_display_region_hash(false);

    GByteArray *fields = g_byte_array_new();
    g_autofree char *schema = xemu_savevm_schema_fingerprint();
    g_autofree char *build = xemu_snapshots_build();
    g_autofree char *title_id = xemu_snapshots_title_id();
    g_autofree char *disc = xemu_snapshots_disc_sha();
    g_autofree char *controllers = xemu_snapshots_controller_layout();
    g_autofree char *region =
        g_strdup_printf("%016" PRIx64, snap_last_save_region);
    xemu_snapshots_put_field(fields, SNAP_KEY_SCHEMA, schema);
    xemu_snapshots_put_field(fields, SNAP_KEY_BUILD, build);
    xemu_snapshots_put_field(fields, SNAP_KEY_TITLE_ID, title_id);
    xemu_snapshots_put_field(fields, SNAP_KEY_DISC, disc);
    xemu_snapshots_put_field(fields, SNAP_KEY_CONTROLLERS, controllers);
    xemu_snapshots_put_field(fields, SNAP_KEY_REGION, region);
    const uint32_t nfields = 6;

    qemu_put_be32(f, XEMU_SNAPSHOT_DATA_MAGIC);
    qemu_put_be32(f, XEMU_SNAPSHOT_DATA_VERSION);
    qemu_put_be32(f, 4 + path_size + 1 + xbe_title_name_size + 4 +
                     thumbnail_size + 4 + fields->len);

    qemu_put_be32(f, path_size);
    if (path_size) {
        qemu_put_buffer(f, (const uint8_t *)path, path_size);
    }
    g_free(path);

    qemu_put_byte(f, xbe_title_name_size);
    if (xbe_title_name_size) {
        qemu_put_buffer(f, (const uint8_t *)xbe_title_name, xbe_title_name_size);
    }
    g_free(xbe_title_name);

    qemu_put_be32(f, thumbnail_size);
    if (thumbnail_size) {
        qemu_put_buffer(f, (const uint8_t *)thumbnail_buf, thumbnail_size);
    }
    g_free(thumbnail_buf);

    qemu_put_be32(f, nfields);
    qemu_put_buffer(f, fields->data, fields->len);
    g_byte_array_free(fields, true);

    xemu_snapshots_dirty = true;
}

bool xemu_snapshots_offset_extra_data(QEMUFile *f)
{
    unsigned int v;
    uint32_t version;
    uint32_t size;

    v = qemu_get_be32(f);
    if (v != XEMU_SNAPSHOT_DATA_MAGIC) {
        qemu_file_skip(f, -4);
        return true;
    }

    version = qemu_get_be32(f);
    (void)version;

    /* qemu_file_skip only works if you aren't skipping past internal buffer limit.
     * Unfortunately, it's not usable here.
     */
    size = qemu_get_be32(f);
    void *buf = g_malloc(size);
    qemu_get_buffer(f, buf, size);
    g_free(buf);

    return true;
}

void xemu_snapshots_mark_dirty(void)
{
    xemu_snapshots_dirty = true;
}

/*
 * HAKUX_SNAPSHOT_TEST=<seconds>: from that many seconds after the GPU is
 * created, run a fixed sequence of saves and loads on the main loop and log
 * one "[snap]" line per step:
 *   c1  save slot a, play 20 s, load a; the display region must hash as at
 *       the save
 *   c2  60 s of play after that load, hashed every 10 s
 *   c3  20 cycles of save b, 2 s, load b, 2 s
 *   c4  pause, save b, load b, check the machine is paused again, resume
 *   c5  save b under another controller layout, load b: refused, still
 *       running
 * Both slots are deleted at the end.
 */
enum {
    SNAP_T_START,
    SNAP_T_C1_SAVE,
    SNAP_T_C1_SCENE_B,
    SNAP_T_C1_LOAD,
    SNAP_T_C2,
    SNAP_T_C3_SAVE,
    SNAP_T_C3_LOAD,
    SNAP_T_C4_PAUSE,
    SNAP_T_C4_SAVE,
    SNAP_T_C4_LOAD,
    SNAP_T_C4_CHECK,
    SNAP_T_C4_RESUME,
    SNAP_T_C4_PLAY,
    SNAP_T_C5_SAVE,
    SNAP_T_C5_LOAD,
    SNAP_T_C5_PLAY,
    SNAP_T_END,
};

#define SNAP_C2_SAMPLES 6
#define SNAP_C3_CYCLES 20

typedef struct SnapTest {
    QEMUTimer *timer;
    int step;
    int n;
    int ok;
    uint64_t hash_a;
    uint64_t hash_b;
    uint64_t hashes[SNAP_C2_SAMPLES];
    int save_ms[SNAP_C3_CYCLES];
    int load_ms[SNAP_C3_CYCLES];
    bool c4_paused_after_save;
    uint64_t c5_hash;
} SnapTest;

static SnapTest snap_test;

static int snap_ms(int64_t us)
{
    return (int)((us + 500) / 1000);
}

static uint64_t snap_state_bytes(const char *name)
{
    QEMUSnapshotInfo sn;
    BlockDriverState *bs = bdrv_all_find_vmstate_bs(NULL, false, NULL, NULL);
    if (!bs || bdrv_snapshot_find(bs, &sn, name) < 0) {
        return 0;
    }
    return sn.vm_state_size;
}

static int snap_count(void)
{
    QEMUSnapshotInfo *sn_tab = NULL;
    BlockDriverState *bs = bdrv_all_find_vmstate_bs(NULL, false, NULL, NULL);
    if (!bs) {
        return -1;
    }
    int n = bdrv_snapshot_list(bs, &sn_tab);
    g_free(sn_tab);
    return n;
}

static bool snap_save(const char *slot)
{
    Error *err = NULL;

    xemu_snapshots_save(slot, &err);
    if (err) {
        SNAP_LOG("[snap] save slot=%s fail ms=%d state=%s err=%s", slot,
                 snap_ms(snap_last_save_us), RunState_str(runstate_get()),
                 error_get_pretty(err));
        error_free(err);
        return false;
    }
    SNAP_LOG("[snap] save slot=%s ok ms=%d bytes=%" PRIu64
             " hash=%016" PRIx64 " state=%s",
             slot, snap_ms(snap_last_save_us), snap_state_bytes(slot),
             snap_last_save_region, RunState_str(runstate_get()));
    return true;
}

static bool snap_load(const char *slot)
{
    Error *err = NULL;

    xemu_snapshots_load(slot, &err);
    if (err) {
        SNAP_LOG("[snap] load slot=%s fail ms=%d check_ms=%d refuse=%s "
                 "state=%s err=%s",
                 slot, snap_ms(snap_last_load_us), snap_ms(snap_last_check_us),
                 snap_last_refuse ? snap_last_refuse : "-",
                 RunState_str(runstate_get()), error_get_pretty(err));
        error_free(err);
        return false;
    }
    SNAP_LOG("[snap] load slot=%s ok ms=%d check_ms=%d bytes=%" PRIu64
             " hash=%016" PRIx64 " state=%s",
             slot, snap_ms(snap_last_load_us), snap_ms(snap_last_check_us),
             snap_state_bytes(slot), snap_last_load_region,
             RunState_str(runstate_get()));
    return true;
}

static void snap_delete(const char *slot)
{
    QEMUSnapshotInfo sn;
    Error *err = NULL;
    BlockDriverState *bs = bdrv_all_find_vmstate_bs(NULL, false, NULL, NULL);

    if (!bs || bdrv_snapshot_find(bs, &sn, slot) < 0) {
        return;
    }
    xemu_snapshots_delete(slot, &err);
    SNAP_LOG("[snap] delete slot=%s %s", slot, err ? "fail" : "ok");
    error_free(err);
}

static int snap_cmp_int(const void *a, const void *b)
{
    return *(const int *)a - *(const int *)b;
}

static void snap_log_spread(const char *what, int *v, int n)
{
    int s[SNAP_C3_CYCLES];

    if (n <= 0) {
        return;
    }
    memcpy(s, v, n * sizeof(int));
    qsort(s, n, sizeof(int), snap_cmp_int);
    SNAP_LOG("[snap] c3 %s n=%d min=%d median=%d max=%d", what, n, s[0],
             s[n / 2], s[n - 1]);
}

static int snap_test_step(SnapTest *t)
{
    bool flip, nop, ctx;
    uint64_t h;

    switch (t->step++) {
    case SNAP_T_START: {
        xemu_snapshots_update_disc_sha();
        g_autofree char *build = xemu_snapshots_build();
        g_autofree char *title = xemu_snapshots_title_id();
        g_autofree char *layout = xemu_snapshots_controller_layout();
        g_autofree char *schema = xemu_savevm_schema_fingerprint();
        SNAP_LOG("[snap] start build=%s title=%s disc=%s controllers=%s "
                 "schema=%s snapshots=%d state=%s",
                 build, title, snap_disc_sha, layout, schema, snap_count(),
                 RunState_str(runstate_get()));
        snap_delete("a");
        snap_delete("b");
        return 1000;
    }
    case SNAP_T_C1_SAVE:
        t->ok = snap_save("a");
        t->hash_a = snap_last_save_region;
        return 20000;
    case SNAP_T_C1_SCENE_B:
        t->hash_b = nv2a_display_region_hash(true);
        SNAP_LOG("[snap] c1 scene-b hash=%016" PRIx64 " differs=%s",
                 t->hash_b, t->hash_b != t->hash_a ? "yes" : "no");
        return 100;
    case SNAP_T_C1_LOAD:
        t->ok &= snap_load("a");
        h = snap_last_load_region;
        SNAP_LOG("[snap] c1 %s hash-a=%016" PRIx64 " after-load=%016" PRIx64
                 " match=%s scene-b-differs=%s",
                 t->ok && t->hash_a && h == t->hash_a &&
                         t->hash_b != t->hash_a ? "pass" : "fail",
                 t->hash_a, h, h == t->hash_a ? "yes" : "no",
                 t->hash_b != t->hash_a ? "yes" : "no");
        t->n = 0;
        return 10000;
    case SNAP_T_C2:
        t->hashes[t->n] = nv2a_display_region_hash(true);
        nv2a_get_wait_flags(&flip, &nop, &ctx);
        SNAP_LOG("[snap] c2 t=%d hash=%016" PRIx64 " state=%s flip=%d nop=%d",
                 (t->n + 1) * 10, t->hashes[t->n], RunState_str(runstate_get()),
                 flip, nop);
        if (++t->n < SNAP_C2_SAMPLES) {
            t->step--;
            return 10000;
        } else {
            int distinct = 0;
            for (int i = 0; i < SNAP_C2_SAMPLES; i++) {
                bool seen = false;
                for (int j = 0; j < i; j++) {
                    seen |= t->hashes[j] == t->hashes[i];
                }
                distinct += !seen;
            }
            SNAP_LOG("[snap] c2 %s distinct=%d/%d state=%s",
                     distinct > 1 && runstate_is_running() ? "pass" : "fail",
                     distinct, SNAP_C2_SAMPLES, RunState_str(runstate_get()));
        }
        t->n = 0;
        t->ok = 0;
        return 100;
    case SNAP_T_C3_SAVE:
        t->ok += snap_save("b");
        t->save_ms[t->n] = snap_ms(snap_last_save_us);
        return 2000;
    case SNAP_T_C3_LOAD:
        t->ok += snap_load("b");
        t->load_ms[t->n] = snap_ms(snap_last_load_us);
        if (++t->n < SNAP_C3_CYCLES) {
            t->step -= 2;
            return 2000;
        }
        snap_log_spread("save_ms", t->save_ms, t->n);
        snap_log_spread("load_ms", t->load_ms, t->n);
        SNAP_LOG("[snap] c3 %s cycles=%d ok=%d/%d bytes=%" PRIu64 " state=%s",
                 t->ok == 2 * SNAP_C3_CYCLES && runstate_is_running() ?
                     "pass" : "fail",
                 t->n, t->ok, 2 * SNAP_C3_CYCLES, snap_state_bytes("b"),
                 RunState_str(runstate_get()));
        return 5000;
    case SNAP_T_C4_PAUSE:
        vm_stop(RUN_STATE_PAUSED);
        SNAP_LOG("[snap] c4 pause state=%s", RunState_str(runstate_get()));
        t->ok = 1;
        return 2000;
    case SNAP_T_C4_SAVE:
        t->ok &= snap_save("b");
        t->c4_paused_after_save = runstate_check(RUN_STATE_PAUSED);
        return 2000;
    case SNAP_T_C4_LOAD:
        t->ok &= snap_load("b");
        return 1000;
    case SNAP_T_C4_CHECK:
        nv2a_get_wait_flags(&flip, &nop, &ctx);
        SNAP_LOG("[snap] c4 %s paused-after-save=%s paused-after-load=%s "
                 "flip=%d nop=%d",
                 t->ok && t->c4_paused_after_save &&
                         runstate_check(RUN_STATE_PAUSED) ? "pass" : "fail",
                 t->c4_paused_after_save ? "yes" : "no",
                 runstate_check(RUN_STATE_PAUSED) ? "yes" : "no", flip, nop);
        return 1000;
    case SNAP_T_C4_RESUME:
        if (runstate_check(RUN_STATE_PAUSED)) {
            vm_start();
        }
        SNAP_LOG("[snap] c4 resume state=%s", RunState_str(runstate_get()));
        return 10000;
    case SNAP_T_C4_PLAY:
        h = nv2a_display_region_hash(true);
        SNAP_LOG("[snap] c4 play hash=%016" PRIx64 " state=%s", h,
                 RunState_str(runstate_get()));
        return 1000;
    case SNAP_T_C5_SAVE: {
        static const char *const other[] = {
            "usb-xbox-gamepad,0,0;usb-xbox-gamepad,0,0;-;-", "-;-;-;-",
        };
        g_autofree char *layout = xemu_snapshots_controller_layout();
        snap_layout_override =
            g_strdup(g_strcmp0(layout, other[0]) ? other[0] : other[1]);
        SNAP_LOG("[snap] c5 layout running=%s saved=%s", layout,
                 snap_layout_override);
        t->ok = snap_save("b");
        g_free(snap_layout_override);
        snap_layout_override = NULL;
        return 1000;
    }
    case SNAP_T_C5_LOAD: {
        bool loaded = snap_load("b");
        bool refused = !loaded && !g_strcmp0(snap_last_refuse,
                                             "controller-layout");
        t->c5_hash = nv2a_display_region_hash(true);
        SNAP_LOG("[snap] c5 refused=%s reason=%s state=%s hash=%016" PRIx64,
                 refused ? "yes" : "no",
                 snap_last_refuse ? snap_last_refuse : "-",
                 RunState_str(runstate_get()), t->c5_hash);
        t->ok &= refused && runstate_is_running();
        return 5000;
    }
    case SNAP_T_C5_PLAY:
        h = nv2a_display_region_hash(true);
        SNAP_LOG("[snap] c5 %s hash=%016" PRIx64 " moving=%s state=%s",
                 t->ok && h != t->c5_hash && runstate_is_running() ? "pass" :
                                                                     "fail",
                 h, h != t->c5_hash ? "yes" : "no",
                 RunState_str(runstate_get()));
        return 1000;
    case SNAP_T_END:
    default:
        snap_delete("a");
        snap_delete("b");
        SNAP_LOG("[snap] done snapshots=%d state=%s", snap_count(),
                 RunState_str(runstate_get()));
        return -1;
    }
}

static void snap_test_tick(void *opaque)
{
    SnapTest *t = opaque;
    int delay_ms = snap_test_step(t);

    if (delay_ms >= 0) {
        timer_mod(t->timer, qemu_clock_get_ms(QEMU_CLOCK_REALTIME) + delay_ms);
    }
}

void xemu_snapshots_test_init(void)
{
    const char *env = getenv("HAKUX_SNAPSHOT_TEST");
    int start_s = env ? atoi(env) : 0;

    if (start_s <= 0 || snap_test.timer) {
        return;
    }
    SNAP_LOG("[snap] armed start_s=%d", start_s);
    snap_test.timer =
        timer_new_ms(QEMU_CLOCK_REALTIME, snap_test_tick, &snap_test);
    timer_mod(snap_test.timer,
              qemu_clock_get_ms(QEMU_CLOCK_REALTIME) + start_s * 1000LL);
}
