/*
 * xemu User Interface
 *
 * Copyright (C) 2020-2022 Matt Borgerson
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

#ifndef XEMU_SNAPSHOTS_H
#define XEMU_SNAPSHOTS_H

#ifdef __cplusplus
extern "C" {
#endif

#include "qemu/osdep.h"
#include "block/snapshot.h"
#if defined(ANDROID) || defined(__ANDROID__)
typedef unsigned int GLuint;
#else
#include <epoxy/gl.h>
#endif

#define XEMU_SNAPSHOT_DATA_MAGIC 0x78656d75 // 'xemu'
/*
 * Version 2 (#433) appends a list of identity fields to version 1's disc
 * path, title name and thumbnail: the device-state schema, the build, the
 * title ID, the disc and the controller layout. A load is refused, before the
 * machine is reset, when any of them differs from the running machine's.
 */
#define XEMU_SNAPSHOT_DATA_VERSION 2

#define XEMU_SNAPSHOT_THUMBNAIL_WIDTH 160
#define XEMU_SNAPSHOT_THUMBNAIL_HEIGHT 120

extern const char **g_snapshot_shortcut_index_key_map[];

typedef struct XemuSnapshotData {
    char *disc_path;
    char *xbe_title_name;
    GLuint gl_thumbnail;
} XemuSnapshotData;

// Implemented in xemu-snapshots.c
char *xemu_get_currently_loaded_disc_path(void);
int xemu_snapshots_list(QEMUSnapshotInfo **info, XemuSnapshotData **extra_data,
                        Error **err);
void xemu_snapshots_load(const char *vm_name, Error **err);
void xemu_snapshots_save(const char *vm_name, Error **err);
void xemu_snapshots_delete(const char *vm_name, Error **err);

void xemu_snapshots_save_extra_data(QEMUFile *f);
bool xemu_snapshots_offset_extra_data(QEMUFile *f);
void xemu_snapshots_mark_dirty(void);

/* The HAKUX_SNAPSHOT_TEST sequence; does nothing without the variable. */
void xemu_snapshots_test_init(void);

/*
 * The running machine's identity, as a version 2 header records it. Main
 * loop only; the caller frees each string. The disc hash is recomputed when
 * the disc changed, which reads the disc, so it is never called inside a
 * drained section.
 */
char *xemu_snapshots_running_build(void);
char *xemu_snapshots_running_title_id(void);
char *xemu_snapshots_running_title_name(void);
char *xemu_snapshots_running_disc(void);
char *xemu_snapshots_running_controllers(void);
/* The display region hash taken while the last state was written. */
uint64_t xemu_snapshots_last_save_region(void);
/* Test sequences: write these in place of the real values (NULL: real). */
void xemu_snapshots_set_test_overrides(const char *controllers,
                                       const char *build);

// Implemented in migration/savevm.c
char *xemu_savevm_schema_fingerprint(void);
void xemu_savevm_schema_test_mutate(const char *section);
const char *xemu_savevm_schema_test_mutated_field(void);
bool xemu_savevm_can_save(Error **errp);
int xemu_savevm_write(QEMUFile *f, Error **errp);
int xemu_loadvm_read(QEMUFile *f, Error **errp);

// Implemented in hw/xbox/nv2a/nv2a.c
uint64_t nv2a_display_region_hash(bool download);
void nv2a_get_wait_flags(bool *flip, bool *nop, bool *context_switch);

// Implemented in xemu-thumbnail.cc
void xemu_snapshots_set_framebuffer_texture(GLuint tex, bool flip);
bool xemu_snapshots_load_png_to_texture(GLuint tex, void *buf, size_t size);
void *xemu_snapshots_create_framebuffer_thumbnail_png(size_t *size);

#ifdef __cplusplus
}
#endif

#endif
