/*
 * Save states as files (#433): ten numbered slots per title, an auto slot,
 * undo save and undo load, optional compression.
 *
 * A state is <root>/<title_id>/slot<N>.hxs. It holds the migration stream
 * that qemu_savevm_state writes (which starts with xemu's identity header),
 * and it names a disk-only internal snapshot of the hard disk taken at the
 * same instant. A load goes to that disk snapshot, then loads the stream, so
 * the hard disk always matches the RAM that is loaded.
 *
 * Every function below may be called from any thread except the QEMU main
 * loop's: each one hands its machine work to the main loop and waits.
 */
#ifndef HAKUX_SAVESTATE_HXS_H
#define HAKUX_SAVESTATE_HXS_H

#include <stdbool.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define HXS_SLOTS 10
#define HXS_SLOT_AUTO 10
#define HXS_SLOT_UNDO_SAVE 11
#define HXS_SLOT_COUNT 12

typedef enum HxsMode {
    HXS_MODE_RAW = 0,        /* a: the stream straight to the file */
    HXS_MODE_INLINE = 1,     /* b: compressed while the machine is stopped */
    HXS_MODE_BACKGROUND = 2, /* c: raw file first, compressed by a worker */
    HXS_MODE_DEFERRED = 3,   /* d: to memory, a worker compresses and writes */
} HxsMode;

typedef enum HxsCodec {
    HXS_CODEC_NONE = 0,
    HXS_CODEC_LZ4 = 1,
    HXS_CODEC_ZSTD = 2,
} HxsCodec;

/*
 * File operations relative to the states root, for a root that is not a
 * POSIX directory (a folder picked through the Storage Access Framework).
 * open() returns a file descriptor the caller closes; a write open creates
 * and truncates, and the descriptor is readable too. rename() replaces its
 * target. list() returns a malloc'd string of "name\tsize\tmtime_ms\tkind\n"
 * lines, kind 'd' for a folder and 'f' for a file, or NULL if the folder is
 * absent. Each returns a negative value on failure.
 */
typedef struct HxsStoreOps {
    int (*open)(const char *rel, bool write);
    int (*rename)(const char *from, const char *to);
    int (*unlink)(const char *rel);
    int (*mkdir)(const char *rel);
    char *(*list)(const char *rel);
} HxsStoreOps;

/* What one operation measured. Times in microseconds, 0 when not reached. */
typedef struct HxsStats {
    bool ok;
    char reason[48];   /* why it was refused or failed; "" on success */
    char error[192];
    int slot;
    int mode;
    int codec;
    int level;
    int threads;
    int64_t total_us;      /* the whole call */
    int64_t check_us;      /* identity check before anything stops */
    int64_t pause_us;      /* the machine stopped: what the player feels */
    int64_t disksnap_us;   /* disk-only snapshot, inside the pause */
    int64_t serialize_us;  /* qemu_savevm_state, inside the pause */
    int64_t compress_us;   /* wall time compressing (inline or worker) */
    int64_t write_us;      /* writing the file (inline or worker) */
    int64_t cpu_us;        /* thread CPU time spent compressing */
    int64_t durable_us;    /* from the stop until the file is fsynced in place */
    int64_t compressed_us; /* c: from the stop until the compressed file is */
    int64_t read_us;       /* load: reading the file */
    int64_t decompress_us; /* load: decompressing it */
    int64_t undo_us;       /* load: keeping the machine for undo load */
    int64_t goto_us;       /* load: going to the disk snapshot */
    int64_t restore_us;    /* load: reset and qemu_loadvm_state */
    int64_t post_us;       /* deleting the disk snapshot it made unused */
    uint64_t raw_bytes;    /* the stream */
    uint64_t file_bytes;   /* the file on disk */
    uint64_t region;       /* display region hash at the save / after the load */
    uint64_t undo_region;  /* load: the region when undo load's state was kept */
    int file_codec;        /* load: the codec of the file that was read */
    bool job_running;      /* load: a worker was compressing this slot */
    int worker_cpu;        /* the core the worker ran on, -1 if none */
    char disk_snap[64];
} HxsStats;

typedef struct HxsSlotInfo {
    bool exists;
    bool loadable;
    char reason[48];        /* why it cannot be loaded */
    bool other_title_since; /* another title ran after it was saved */
    int64_t saved_at;       /* unix seconds */
    uint64_t file_bytes;
    int codec;
    int origin_slot;        /* the slot it was saved to */
    char title_name[64];
} HxsSlotInfo;

/* Configuration, set before the machine starts. */
void hxs_set_root(const char *posix_dir);
void hxs_set_store(const HxsStoreOps *ops, const char *label);
void hxs_set_compression(bool on);
bool hxs_get_compression(void);
void hxs_set_auto_load(bool on);
void hxs_set_boot_title(const char *title_id);
const char *hxs_root_label(void);

/* The modes "Off" and "On" stand for. */
void hxs_default_mode(bool compression, int *mode, int *codec, int *level);

int hxs_save(int slot, int mode, int codec, int level, bool wait_durable,
             HxsStats *st);
int hxs_save_default(int slot, bool wait_durable, HxsStats *st);
/* The auto slot, durable before it returns: for the quit path. */
int hxs_save_auto_quit(HxsStats *st);
/*
 * A save leaves the machine as it found it, running or paused. A load leaves
 * it running, also from paused; a load refused before anything changed
 * leaves it as it was.
 */
int hxs_load(int slot, HxsStats *st);
int hxs_undo_load(HxsStats *st);
int hxs_undo_save(HxsStats *st);
int hxs_delete(int slot);
bool hxs_can_undo_load(void);
bool hxs_can_undo_save(void);
int hxs_slot_info(int slot, HxsSlotInfo *out);
/* Every slot of the running title, indexed by slot number. */
int hxs_slot_list(HxsSlotInfo out[HXS_SLOT_COUNT]);
/* Waits until the worker has finished every job, at most timeout_ms. */
bool hxs_wait_idle(int timeout_ms);
/* The newest loadable state among auto and 0-9, or -1. */
int hxs_newest_loadable(HxsSlotInfo *out);

/*
 * Called once on the main thread while the machine is built. When the
 * machine first runs, a thread does the startup cleanup, then auto-load when
 * it is on (or the test sequence when HAKUX_SAVESTATE_TEST is set).
 */
void hxs_init(void);
/* The outcome of auto-load for the frontend's toast; NULL until known. */
const char *hxs_auto_load_message(void);

/* One-line description of an operation for logs. */
void hxs_describe(const HxsStats *st, const char *op, char *out, int len);

#ifdef __cplusplus
}
#endif

#endif
