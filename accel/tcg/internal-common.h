/*
 * Internal execution defines for qemu (target agnostic)
 *
 *  Copyright (c) 2003 Fabrice Bellard
 *
 * SPDX-License-Identifier: LGPL-2.1-or-later
 */

#ifndef ACCEL_TCG_INTERNAL_COMMON_H
#define ACCEL_TCG_INTERNAL_COMMON_H

#include "exec/cpu-common.h"
#include "exec/translation-block.h"
#include "exec/mmap-lock.h"
#include "accel/tcg/tb-cpu-state.h"

extern int64_t max_delay;
extern int64_t max_advance;

extern bool one_insn_per_tb;

extern bool icount_align_option;

/*
 * Return true if CS is not running in parallel with other cpus, either
 * because there are no other cpus or we are within an exclusive context.
 */
static inline bool cpu_in_serial_context(CPUState *cs)
{
    return !tcg_cflags_has(cs, CF_PARALLEL) || cpu_in_exclusive_context(cs);
}

/**
 * cpu_plugin_mem_cbs_enabled() - are plugin memory callbacks enabled?
 * @cs: CPUState pointer
 *
 * The memory callbacks are installed if a plugin has instrumented an
 * instruction for memory. This can be useful to know if you want to
 * force a slow path for a series of memory accesses.
 */
static inline bool cpu_plugin_mem_cbs_enabled(const CPUState *cpu)
{
#ifdef CONFIG_PLUGIN
    return !!cpu->neg.plugin_mem_cbs;
#else
    return false;
#endif
}

TranslationBlock *tb_gen_code(CPUState *cpu, TCGTBCPUState s);
void page_init(void);
void tb_htable_init(void);
TranslationBlock *inv_tb_htable_lookup(CPUState *cpu, TCGTBCPUState s);
void tb_reset_jump(TranslationBlock *tb, int n);
TranslationBlock *tb_link_page(TranslationBlock *tb);

/*
 * Smaller translation blocks on pages the guest keeps writing.
 *
 * HAKUX_SMALL_BLOCK_INSNS is the block extent, in guest instructions, used on
 * a latched page. **Zero disables the mechanism entirely**, which is the
 * default: tb_page_wants_small_blocks() compiles to `false`, nothing is
 * latched, and no page lookup is added to code generation. The arm that turns
 * it on is one commit changing this line, so folding this branch in is inert
 * and the two refs differ in exactly one constant.
 *
 * HAKUX_THRASH_LATCH is how many times a page must be emptied of translated
 * code before it is marked. It latches: once marked, a page stays marked for
 * the life of the PageDesc and is never unmarked.
 *
 * Latching is not a tuning choice, it is the correctness constraint. cflags is
 * part of the TB hash key -- tb_hash_func() takes it, and tb_lookup_cmp()
 * compares it -- and a TB must be findable by both lookup sites,
 * cpu_exec_loop() and helper_lookup_tb_ptr(), which each compute cflags from
 * curr_cflags() with no idea which page the PC lands on. Any policy visible in
 * cflags and varying with a counter would make those lookups miss and turn the
 * thrash into a total retranslation loop.
 *
 * This implementation sidesteps that rather than satisfying it: the block
 * extent is applied to tb_gen_code()'s local `max_insns` and never written
 * into cflags at all, so the hash key is bit-identical to what it is today and
 * both lookup sites find the block they would have found. What varies is only
 * how much code is inside it, which is already free to vary -- the
 * code-too-large path halves max_insns and retranslates without touching
 * cflags, and translator_loop stops early on page crossings and I/O regardless
 * of the requested maximum. It is only applied when the incoming request is
 * the permissive default (CF_COUNT_MASK == 0, meaning "up to TCG_MAX_INSNS");
 * every site that needs an exact count -- icount at cpu-exec.c, breakpoints,
 * precise SMC at tb-maint.c and watchpoint.c, cpu_io_recompile, and the
 * untranslatable-page one-shot -- sets a nonzero count, and those are passed
 * through untouched.
 *
 * The latch is kept anyway, because a policy that can flip a page back would
 * leave long blocks in the table until something invalidated them and make a
 * run's block-length profile depend on history rather than on the build.
 */
#define HAKUX_SMALL_BLOCK_INSNS 0
#define HAKUX_THRASH_LATCH      16

#if HAKUX_SMALL_BLOCK_INSNS
/*
 * Has this physical page been emptied of translated code often enough to be
 * worth translating in smaller pieces? Reads a latched flag on the PageDesc.
 * Called once per code generation -- about 29 times a guest frame on the
 * measured workload -- and not on the guest store path, which is deliberate:
 * the shape of instrumentation that cost +34.1% here and presented as a
 * renderer deadlock was per-guest-write work.
 */
bool tb_page_wants_small_blocks(tb_page_addr_t phys_pc);
#else
static inline bool tb_page_wants_small_blocks(tb_page_addr_t phys_pc)
{
    return false;
}
#endif
void cpu_restore_state_from_tb(CPUState *cpu, TranslationBlock *tb,
                               uintptr_t host_pc);

/**
 * tlb_init - initialize a CPU's TLB
 * @cpu: CPU whose TLB should be initialized
 */
void tlb_init(CPUState *cpu);
/**
 * tlb_destroy - destroy a CPU's TLB
 * @cpu: CPU whose TLB should be destroyed
 */
void tlb_destroy(CPUState *cpu);

bool tcg_exec_realizefn(CPUState *cpu, Error **errp);
void tcg_exec_unrealizefn(CPUState *cpu);

/* current cflags for hashing/comparison */
uint32_t curr_cflags(CPUState *cpu);

void tb_check_watchpoint(CPUState *cpu, uintptr_t retaddr);

/**
 * get_page_addr_code_hostp()
 * @env: CPUArchState
 * @addr: guest virtual address of guest code
 *
 * See get_page_addr_code() (full-system version) for documentation on the
 * return value.
 *
 * Sets *@hostp (when @hostp is non-NULL) as follows.
 * If the return value is -1, sets *@hostp to NULL. Otherwise, sets *@hostp
 * to the host address where @addr's content is kept.
 *
 * Note: this function can trigger an exception.
 */
tb_page_addr_t get_page_addr_code_hostp(CPUArchState *env, vaddr addr,
                                        void **hostp);

/**
 * get_page_addr_code()
 * @env: CPUArchState
 * @addr: guest virtual address of guest code
 *
 * If we cannot translate and execute from the entire RAM page, or if
 * the region is not backed by RAM, returns -1. Otherwise, returns the
 * ram_addr_t corresponding to the guest code at @addr.
 *
 * Note: this function can trigger an exception.
 */
static inline tb_page_addr_t get_page_addr_code(CPUArchState *env,
                                                vaddr addr)
{
    return get_page_addr_code_hostp(env, addr, NULL);
}

/*
 * Access to the various translations structures need to be serialised
 * via locks for consistency.  In user-mode emulation access to the
 * memory related structures are protected with mmap_lock.
 * In !user-mode we use per-page locks.
 */
#ifdef CONFIG_USER_ONLY
#define assert_memory_lock() tcg_debug_assert(have_mmap_lock())
#else
#define assert_memory_lock()
#endif

#if defined(CONFIG_SOFTMMU) && defined(CONFIG_DEBUG_TCG)
void assert_no_pages_locked(void);
#else
static inline void assert_no_pages_locked(void) { }
#endif

#ifdef CONFIG_USER_ONLY
static inline void page_table_config_init(void) { }
#else
void page_table_config_init(void);
#endif

#ifndef CONFIG_USER_ONLY
G_NORETURN void cpu_io_recompile(CPUState *cpu, uintptr_t retaddr);
#endif /* CONFIG_USER_ONLY */

void tb_phys_invalidate(TranslationBlock *tb, tb_page_addr_t page_addr);
void tb_set_jmp_target(TranslationBlock *tb, int n, uintptr_t addr);

void tcg_get_stats(AccelState *accel, GString *buf);

#endif
