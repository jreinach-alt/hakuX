/*
 * hakuX fastmem (lane.memfast, #507): guest loads through the host MMU.
 *
 * Design: docs/lanes/memfast/NOTES.md, "Phase 2 design" (sections 1-8 and
 * the F1 section). In short: one mmu_idx (MMU_KNOSMAP32_IDX, the only data
 * index Xbox titles fill in play, `[tlb68] dm=0x60`) gets a 4 GiB host
 * "shadow" of the guest's linear address space. A TLB fill that softmmu would
 * serve from xbox.ram with no read flags also maps that 4 KiB of the RAM
 * memfd at shadow + VA, read-only. A guest load on that index is then one
 * host instruction, `ldr wD, [x26, wA, uxtw]`; a load to anything not mapped
 * (MMIO, a watched page, a page not yet filled) faults, and the SIGSEGV
 * handler sends it to the load's ordinary softmmu slow path. Stores keep the
 * compare (F1 is loads only).
 *
 * HAKUX_FASTMEM=1  F1 as above.
 * HAKUX_FASTMEM=ram  RAM on a memfd only, no shadow (step F0b).
 * HAKUX_F0A=<s>   the F0a microbenchmark, <s> seconds after TCG init.
 * Unset: one getenv() at init and nothing else.
 *
 * Android/arm64 only: android/app/src/main/cpp/CMakeLists.txt globs every
 * .c under accel/, so fastmem.c builds there with no list entry. meson does
 * not list it, and every other build gets the inline stubs below.
 */
#ifndef HAKUX_FASTMEM_H
#define HAKUX_FASTMEM_H

#if defined(XBOX) && defined(__aarch64__) && defined(__ANDROID__)
#define HAKUX_FM_BUILD 1
#else
#define HAKUX_FM_BUILD 0
#endif

#define HAKUX_FM_IDX 5          /* MMU_KNOSMAP32_IDX (target/i386/cpu.h) */

#if HAKUX_FM_BUILD
#include <stdbool.h>
#include <stdint.h>

extern bool hakux_fm_want;      /* env asked for the shadow; X26 reserved */
extern bool hakux_fm_on;        /* shadow live: translation may emit it */
extern uintptr_t hakux_fm_base; /* shadow base, held in X26 */

/* tcg_target_init: read the env, reserve the shadow, install the handler. */
void hakux_fm_init(void);
/* xbox.c: true if RAM should come from hakux_fm_ram_fd(). */
bool hakux_fm_ram_wanted(void);
int hakux_fm_ram_fd(uint64_t size);
/* xbox.c, after the RAM region exists: arms the shadow if the fd took. */
void hakux_fm_set_ram(void *host, uint64_t size, int fd);

/* backend: the inline load at rx_load faults to rx_stub. */
void hakux_fm_site_add(const void *rx_load, const void *rx_stub);

/* cputlb.c hooks, all on the vCPU thread, none under tlb_c.lock. */
struct CPUState;
void hakux_fm_fill(unsigned mmu_idx, uint64_t va_page, uint64_t pa_page,
                   uintptr_t host, unsigned read_flags, int prot,
                   bool large);
void hakux_fm_full_flush(struct CPUState *cpu, int cause_is_cr3);
void hakux_fm_page_flush(uint64_t va, bool softmmu_large_flush);
void hakux_fm_ram_range(uintptr_t host, uint64_t len);
void hakux_fm_slow_hit(uint64_t va, uintptr_t host, uint64_t pa,
                       unsigned read_flags, bool large);
void hakux_fm_tick(int64_t dt_ms);

/*
 * target/i386: walk the guest page tables for @va with no side effects.
 * Returns 0 for a 4 KiB page, 1 for a piece of a 4 MiB page, -1 when the
 * fill would differ (not present, A clear, PAE, paging off, or a table
 * outside RAM). *pa gets the physical page.
 */
typedef int (*hakux_fm_walk_fn)(struct CPUState *cpu, uint32_t va,
                                uint64_t *pa);
extern hakux_fm_walk_fn hakux_fm_walk;
extern uintptr_t hakux_fm_ram_host;
extern uint64_t hakux_fm_ram_size;

#else
#define hakux_fm_want false
#define hakux_fm_on false
static inline void hakux_fm_init(void) { }
static inline bool hakux_fm_ram_wanted(void) { return false; }
static inline int hakux_fm_ram_fd(unsigned long long size) { return -1; }
static inline void hakux_fm_set_ram(void *h, unsigned long long s, int fd) { }
#endif

#endif
