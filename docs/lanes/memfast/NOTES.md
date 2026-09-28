# lane.memfast (#507)

The vCPU's memory path: a VA==PA census of the XBOX load fast path (phase 0),
removing its dead preamble and per-load test (phase 1), and a fastmem design
(phase 2). Brief: `briefs/memfast.md`; plan: lane.vcpuplan, PR #589,
`docs/lanes/vcpuplan/NOTES.md` items 0, 1 and 3.

## Refs

| ref | what |
|---|---|
| `31515f9751` | phase 0: the `[mf0]` census (instrumentation only); a_ref |
| `82e0ef1fa9` | phase 1: the fast path, its preamble and the X26/X27 reservations removed; b_ref |

## The code as found (master be05285c44)

- `tcg_out_tb_start` (`tcg/aarch64/tcg-target.c.inc`) opened every TB with
  `ldr w16,[x27,#8]; cbz; ldr w16,[x27,#12]; cbnz; ldr x26,[x27]; b; mov x26,#0`.
  That is `xbox_ram_fp.active`, then `cb_count`, then `host_base` cached in X26,
  or 0.
- `prepare_host_addr` opened every guest **load** with `cbz x26, tlb`, then:
  - `tst addr, #~(ram_size-1)`: if the address is in range, host = X26 + addr,
    with no TLB lookup;
  - otherwise, the same test against `vram_pci_base` (NV2A BAR1):
    host = X26 + addr - vram_base.
  - Only then the softmmu compare.
- `active` is set once, at the first flip (`pgraph/vk/renderer.c:2485`).
  `cb_count` counts live `mem_access_callback`s, which are the NV2A surface
  watches (`system/physmem.c`).
- X26 and X27 were reserved, taking two callee-saved registers from the
  allocator.
- **The fast path indexes guest-physical RAM with the guest-virtual address.**
  Nothing checks that the page is identity-mapped, present, readable, not
  MMIO, or that the access does not straddle the window's end.

## Phase 1 decision: drop it, do not make it live

The brief asks: drop the path, or make it correct and live. **Drop it.** The
census does not change this, for three reasons:

1. **A correct version needs a per-page lookup.** Whether VA maps to the same
   RAM offset is a property of each page. Knowing it per access *is* a TLB
   lookup, which is what the softmmu compare already does.
2. **The hoist cannot make it correct.** The plan's hoist (one global, with a
   `tb_flush` on change) removes the per-TB test, but it does not make a
   non-identity page read the right bytes.
3. **Phase 2 is the correct form.** Direct access with no compare is fastmem:
   the host MMU holds the per-page translation. It replaces this path.

What the census decides is different: whether the removal is *also a
correctness fix*. That needs both:

- the armed share (`act=1` with `cb=0`) above 0 on some title;
- non-identity (`ln`) or device (`lo`) installs on that title.

The census also sizes phase 2: the distinct mappings in the windows. If a
title has both, the fix gets its own line on #507, and the release note
names it.

### What the removal can and cannot move

- **Pixels.** They can move only where the path was armed during a pgraph
  test and read a different page than the TLB would. Such a move is a fix.
  The pixel prediction (`memfast-drop-pixels.json`) says no capture moves.
- **Speed.** Every TB loses up to 7 instructions and every load loses 1-12.
  The allocator gains X26/X27 (callee-saved, already saved and restored by the
  prologue).
- **Unchanged.** The softmmu compare, the slow path and store codegen.

## Phase 0: the `[mf0]` census

- **Where.** `tlb_set_page_full` (`accel/tcg/cputlb.c`) classes every install
  in the fast path's two windows. The test compares the TLB's own host pointer
  for the page with the one the fast path computes:
  - `id`: the same pointer;
  - `nid`: another RAM page;
  - `io`: not RAM.
- **What else it records:**
  - distinct `nid` pages, in a bitmap;
  - the first 8 with their VA and PA (`[mf0] first`);
  - the exact wall time with `cb_count == 0`, booked on the 0<->1 transitions
    under a lock in `physmem.c`.
- **Output.** One line every 2 s, at the `[tlb68]` cadence, tag `hakuX` at W:
  `[mf0] w dt act cb cb0ms up dn li ln lo vi vn vo lnd vnd vb`.
  - `cb0ms=-1` on the first window (no baseline).
  - A run with no line is VOID.
- **Reader:** `docs/lanes/memfast/mf0_read.py <result dir>`.
- **The b_ref keeps the counter.** There, the "armed" share still counts
  `cb=0` time, but nothing reads it.

## Predictions

- `docs/testing/predictions/memfast-drop-pixels.json`: all 100 golden suites
  bit-identical per capture, skipping `RenderTextureLoop` as the full sweep
  does. The arms job queues it.
- `docs/testing/predictions/memfast-drop-soak.json`, hand-read:
  - J/frame and fps pairs on GTA (Thor) and Nightfire (Nova);
  - gameplay reach on GTA, Nightfire and Crimson;
  - the census on the A runs, plus AUF;
  - the jitmix vCPU-share leg (needs a held simpleperf window: board request).

## Phase 2 design: guest memory through the host MMU ("fastmem")

Status: **design, no code.** The code waits for phase 1's merge (brief).
Sources were read by a research subagent on 2026-09-28. Dolphin, libsigchain,
PPSSPP and Eden were read at source. **ESPT/HSPT were NOT reached** (ACM 403,
no search), so no figure below comes from them. The plan's 1.51-1.59x is
theirs and is unverified here.

### Goal and the win it can reach

After phase 1, the vCPU's translation cost on GTA is two parts (vcpuplan §1):
- the inline softmmu compare, **17.4%**: `ldp` mask/table, `and`, `add`, two
  dependent loads, `and`, `cmp`, `b.ne`;
- the slow-path helpers, **7.9%**.

Fastmem replaces the compare with one instruction, `ldr wD, [x26, wA, uxtw]`,
and lets the host MMU do the translation. Its ceiling is the 17.4% plus the
part of the 7.9% that is TLB refill. Its cost is the faults and remaps it adds.
**The design exists to keep that cost well under the win.** Every choice below
is made against that cost.

### 1. Layout

- **Guest RAM moves to a memfd.**
  - Today it is anonymous and private: `hw/xbox/xbox.c:195`
    `memory_region_init_ram`, down to `qemu_anon_ram_alloc(shared=false)`.
    A private page cannot be aliased at a second address.
  - With `RAM_SHARED`, QEMU backs it with a memfd. `memory_region_get_ram_ptr`
    still returns one host mapping, so NV2A, DMA and every host-pointer path
    are unchanged.
  - **Risk:** a shared mapping loses THP. The measurement is an A/B of
    memfd RAM with fastmem off (step F0b).
- **The shadow:** reserve 4 GiB + 64 KiB of host VA, `PROT_NONE`, once at
  init. Shadow + VA stands for guest linear address VA, for ONE mmu_idx.
  - `uxtw` bounds the index to 4 GiB.
  - The 64 KiB tail is a guard for an access that starts below 4 GiB and
    ends above it.
- **Which mmu_idx.** Xbox titles run at CPL0. The shadow mirrors the
  kernel-mode, no-SMAP 32-bit index.
  - An op's mmu_idx is a translation-time constant (`get_mmuidx(oi)`), so
    ops on any other index simply keep the compare. There is no runtime test.
  - This must be confirmed with a counter of fills per mmu_idx before F1.
- **X26 holds the shadow base.** Phase 1 frees it. It is set in the prologue
  and never changes.

### 2. Coherence: the shadow is a view of what the TLB may hold

**Invariant.** A shadow page is mapped only with a translation and
permissions that the softmmu TLB would install for that VA at that moment.
A present entry must never be staler than x86 allows a TLB entry to be.
Then fastmem is exactly as correct as softmmu.

- **The single map point is `tlb_set_page_full`.** It is the only TLB fill,
  and tcgchurn relies on the same invariant. When `mmu_idx` is the shadow's:
  - **readable** (`PROT_READ`): the section is RAM, there is no read watch,
    and neither `TLB_INVALID_MASK` nor `lg_page_size < TARGET_PAGE_BITS` holds;
  - **writable** (`PROT_READ|PROT_WRITE`): also `prot & PAGE_WRITE`, and the
    write flags carry none of `TLB_NOTDIRTY`, `TLB_DISCARD_WRITE`,
    `TLB_WATCHPOINT` or `TLB_INVALID_MASK`;
  - otherwise `PROT_NONE`.

  The call is `mmap(shadow+VA, 4K, prot, MAP_SHARED|MAP_FIXED, memfd, ram_offset)`.
  A remap at the same offset with new permissions is an `mprotect`.
- **Capacity eviction does NOT unmap.** A direct-mapped TLB slot can be
  overwritten by another page while the translation stays valid. x86 lets a
  TLB keep any translation until an invalidation, so the shadow keeps it too.
  The shadow is then a TLB with no capacity misses, which Dolphin #13768
  describes as "effectively infinitely large".
- **Invalidations the shadow must follow:**

| event | where | shadow action |
|---|---|---|
| INVLPG | `tlb_flush_page*` | unmap the page (a large page: its 4 MB) |
| full flush: MOV CR3, CR0, CR4, A20, `tcg_commit` | `tlb_flush_by_mmuidx_async_work` | **revalidate**, below |
| watch insert/remove | `physmem.c` `mem_access_callback_*` | per page: re-protect the watched range's aliases. Today this is a full flush ("FIXME: flush only applicable pages"), which must become per page first (plan step 2) |
| dirty clear: CODE (SMC), NV2A, NV2A_TEX, VGA | `tlb_reset_dirty_range_all` | downgrade every alias of those RAM pages to `PROT_READ` (reverse map) |
| notdirty store re-enables a page | `tlb_set_dirty` | upgrade the aliases to RW |

- **A reverse map** takes a RAM page to its shadow VAs. Most pages have one or
  two: the kernel's `0x80000000+PA` alias and the title's VA. A dirty clear can
  come from another thread (the `[tlb68]` `rdo` counts it), so the map is under
  a lock, and the `mprotect` runs on the caller's thread.
  - The race: a store between the dirty-bit clear and the `mprotect` lands
    unflagged. Today's cross-thread `tlb_reset_dirty` has the same window
    against the atomic TLB-entry update, so this adds no new race. It needs a
    written argument in the code.
- **Full flushes are the cost that decides the project.**
  - The rates: GTA does 0-96 same-value CR3 reloads/s, and Conker does 514
    full flushes/s (`docs/lanes/slowtier2/readall.out:211`).
  - **Unmap-and-refault is ruled out.** Every touched page costs a signal, a
    fill and an mmap after every flush. 514/s times a few hundred pages is
    most of a second per second.
  - **The design: revalidate.** For each mapped page, re-walk the guest page
    table without side effects. Keep the mapping only if the PA, the
    permissions and the watch/dirty state are unchanged, PTE.A is set, and
    PTE.D is set if the page is mapped writable. Otherwise unmap it.
    - This is exact: the kept page is what the refill would install, and a
      guest that cleared A (or D) gets a fault and a refill that sets it.
    - The cost is one page walk (~2 cached loads) per mapped page per flush.
      No syscall unless something changed.
    - It needs a non-mutating walk in `target/i386`. That file is outside
      this lane's grant, so a board request comes before F3.
  - **The alternative, if revalidation is too slow at Conker's rate,** is
    Dolphin PR #14649's lazy view swap. A second 4 GiB view is swapped in on
    the flush and rebuilt lazily, which costs faults instead of walks.
    Dolphin measured it at about the same speed and about 1% faster.

### 3. Self-modifying code and NV2A watches map onto page protection

- **Code pages.** `tlb_protect_code` clears DIRTY_MEMORY_CODE, and the shadow
  alias drops to read-only.
  1. A store faults and goes to the site's softmmu stub. The stub takes the
     notdirty path, which invalidates the TBs and calls `tlb_set_dirty`.
  2. The shadow goes back to RW.
  3. The guest sees the same behaviour it sees today.
- **NV2A surface watches** (`mem_access_callback`). The watched pages go to
  `PROT_NONE` (or `PROT_READ` for write-only watches). The stub reaches
  `TLB_WATCHPOINT` and the callback, as today.
- **The pathological case is measured.**
  - fps382: 2,505,844 notdirty slow stores/s into 7 pages during Blinx's movie
    decode (`docs/lanes/fps382/NOTES.md:49`). Each store re-armed the page.
  - A signal per store would be fatal, so faults are bounded per site
    (section 4). A site that keeps faulting is backpatched to its stub after K
    faults. It then costs what it costs today: a compare in the stub and a
    helper call.

### 4. Faults and backpatching on arm64 Android

- **Emission.** For each guest load or store on the shadow's mmu_idx:
  - **Inline:** one instruction, `ldr/str w, [x26, wA, uxtw]`. Under
    `hakux_tso_rcpc` it is two: `add x17, x26, wA, uxtw; ldapr/stlr [x17]`,
    since LDAPR/STLR take a base register only.
  - **Out of line** (in the TB's slow-path area, where the ldst labels already
    go): the full softmmu sequence as emitted today, meaning the compare, the
    fast host access, the slow helper call on a miss, and a branch back to
    the instruction after the inline access.

  The instruction count moves the compare off the hot path; the code size is
  about today's plus one instruction.
- **Fault → stub, not fault → patch.**
  - The `SIGSEGV`/`SIGBUS` handler looks up the faulting PC in the owning
    TB's site table (a compact table after the TB's code, like QEMU's restore
    search data). It sets the context PC to that site's stub, bumps the site's
    fault count, and returns.
  - The stub runs in normal context. Its helper does the fill, and the fill
    maps the page, so the next access hits.
  - After K faults (K about 4-8) the stub's helper rewrites the inline
    instruction to `b stub` through the RW alias (splitwx) and flushes the
    icache. That is Dolphin's permanent patch, taken only for sites that
    prove to be MMIO, watched or flapping.
  - All of this is async-signal-safe: a table lookup and a context write. No
    locks are taken in the handler.
- **Misaligned LDAPR/STLR** raise `SIGBUS` (the reason the TSO mode is marked
  not runnable as built, tcg-target.c.inc ~1962). The same handler sends them
  to the stub. That makes the TSO mode runnable as a side effect.
- **Android signal chaining.**
  - ART's libsigchain interposes `sigaction`. Our handler is recorded as the
    user action and runs after ART's special handlers. ART's `FaultManager`
    declines a fault that is not in managed code after one TLS check (read in
    `runtime/fault_handler.cc`), and libsigchain adds one `sigprocmask` per
    fault.
  - `AddSpecialSignalHandlerFn` would run ahead of ART and skip that syscall,
    if the microbenchmark shows it matters.
  - Our crash handler (`android/app/src/main/cpp/android_crash_handler.cpp:169`)
    installs `SA_RESETHAND` from a constructor and keeps no old action. The
    fastmem handler installs after it, saves it, and chains to it for any
    fault outside the shadow. A test must show that a deliberate wild pointer
    still produces a tombstone.
  - Dolphin, PPSSPP and Eden all use plain `sigaction` on Android with no ART
    code, which is some evidence that this works.

### 5. Where it cannot apply, and the fallback

- **The fallback everywhere is today's code**, the softmmu compare, reached
  per site.
- **Host page size must be 4 KiB** (`getpagesize()==4096`, checked at init).
  On 16 KiB hosts a shadow unit spans 4 guest pages, so the fast path stays
  off. Coalescing aligned, contiguous runs as Dolphin does is future work.
  Both handhelds must be checked; the build reads the page size at runtime.
- **Ops on other mmu_idxes, atomics and cmpxchg** (these go through helpers
  already) and 128-bit ops keep the compare.
- **`vm.max_map_count`** is 65530. Scattered 4K aliases are one VMA each, and
  128 MB is 32768 pages. The design keeps a mapped-page counter, evicts LRU
  above a cap of about 30k, and logs the `/proc/self/maps` line count per
  soak.
- **A global off switch** (the env switch; later an automatic one if
  faults/s exceed a ceiling) stops mapping new pages. Every site then faults
  K times and patches itself to its stub, which converges to today's cost.

### 6. Steps, each gated on the one before

The owner's rule applies here: the hard work fits the platform, and cheap
steps come first only when they decide something. F0a and F0b decide whether
F1 can pay; nothing else below is a probe.

| step | what | decides / leg |
|---|---|---|
| F0a | a device microbenchmark (a native test binary via `request.sh`, or a debug entry point): SIGSEGV round trip under libsigchain; `mmap`/`mprotect` of one memfd 4K page; one page walk | the constants. With `[tlb68]` ff/pf/sd and fills per flush it prices the overhead per title **before** building F1. Kill if the predicted overhead on GTA is over a third of 17.4% |
| F0b | RAM on memfd, fastmem off | no fps/J change beyond noise (the THP risk); pixels identical |
| F1 | loads only, behind `HAKUX_FASTMEM=1` (default off). Stores keep the compare. Revalidate by walking | jitmix: `tlb` role on loads down; fps up on GTA and Forza; faults/s and remaps/s under a stated ceiling; pixels identical |
| F1x | `HAKUX_FASTMEM=2`, an equivalence mode: every fast load also runs the compare path and counts mismatches | 0 mismatches over soaks on the watch-heavy titles |
| F2 | stores, with code, dirty and watched pages protected; the watch-insert flush made per page | the fps382 case bounded by backpatch; Conker's flush rate priced |
| F3 | default on, with the release note | the full pgraph sweep, title soaks across the benchmark set, and a stress run on the titles with the most surface watches |

### 7. Adversarial review (2026-09-28): amendments that supersede sections 1-6

A review subagent checked the design against the code. It found 4 HIGH, 6
MEDIUM and 5 LOW. **Where a line below conflicts with the sections above, this
section wins.**

**HIGH**

- **H1: revalidation cannot run inside the flush.**
  - **Old state.** CR0, CR4 and A20 call `tlb_flush` *before* writing the
    new value (`target/i386/helper.c:143-146` vs `:165`, `:202-206` vs
    `:236`, `:130`), so a walk there reads the old mode. Only CR3 is written
    first.
  - **Deadlock.** The walker probes PTEs through `MMU_PHYS_IDX`, whose fill
    takes `tlb_c.lock`, and the flush already holds that lock.
  - **Amendment:**
    - the flush only sets `shadow_pending`, and revalidation runs at the next
      `cpu_exec` iteration, outside the lock (MOV CRn and INVLPG already end
      the TB);
    - PTEs are read through `xbox.ram`'s host pointer, and a page whose PT
      page is outside that block is dropped;
    - CR0, CR4 and A20 flushes drop the whole shadow.
- **H2: fastmem makes the flush skip itself.**
  - `to_clean = asked & c.dirty` (`cputlb.c:734`), and `c.dirty` is set only
    by a fill. Shadow hits never fill, so a later CR3 flush would find the
    mode clean and skip the hook.
  - **Amendment:** the shadow hook runs unconditionally, outside the
    `to_clean` loop.
- **H3: "is RAM" is not "is `xbox.ram`".**
  - `nv2a-ramin` (`nv2a.c:1302`), `xbox.mcpx` (`xbox.c:170`) and the ROMD
    flash are also RAM or ROMD. Mapping by `ram_addr` into the memfd would
    alias the wrong bytes.
  - QEMU also falls back silently to fd-less shared memory
    (`physmem.c:3019`).
  - **Amendment:**
    - map only when `section->mr->ram_block == xbox_ram_block`, at the
      offset within that block;
    - assert `block->fd >= 0` at init, or keep fastmem off.
- **H4: revalidation was priced on the wrong set.**
  - With no capacity eviction, the mapped set is every page since boot, up to
    the cap. That is 20-30k pages against softmmu's 8k-entry cap
    (`hakux-tlb68.h:41`), so revalidating it at 514 flushes/s costs 0.1-0.3 s
    per second.
  - Conker's 514/s has not been split by cause. `[tlb68]` does split it:
    `cr3n`, `cr3s`, `cr0`, `cr4`, `a20`, `other`, and `other` includes the
    watch-insert flushes that F2 removes anyway.
  - **Amendment:**
    - bound the mapped set to about softmmu's size;
    - **write-track the page-table pages.** Record each PT/PD page's PA at
      fill time and protect those pages with a dirty client. A CR3_SAME flush
      with no PT page written is then a no-op, and only entries under written
      PT pages are re-walked. This follows HSPT's idea, which was not read at
      source here.
    - **F0a must split the flush rate by cause first**, on GTA and Conker.

**MEDIUM**

- **M1: large pages.** A shadow piece of a 4 MB page outlives softmmu's
  large-page record, so an INVLPG inside it drops one 4K piece and leaves 1023
  stale.
  - **Amendment:**
    - store `lg_page_size` and the base address with each shadow page;
    - INVLPG unmaps the whole covering large page;
    - revalidation also requires PDE.A.
- **M2: a fault can reach the stub without a remap.** If softmmu still holds
  the entry, the stub's compare hits and no fill runs, so the page is never
  mapped again.
  - **Amendment:**
    - the fault entry calls a helper that maps from the existing TLB entry;
    - faults are counted as cold vs protection, and only protection faults
      count toward K;
    - patched sites decay back to fast after a quiet interval.
- **M3: watch-insert ordering.** The list insert is deferred to safe work
  (`physmem.c:956`).
  - **Amendment:** the re-protect runs inside the same safe-work item, after
    the insert.
  - Watches are always R|W (`physmem.c:866`), so the "PROT_READ for write-only
    watches" case in section 3 does not exist.
- **M4: a fill against a cross-thread dirty clear.**
  - **Amendment:**
    - the fill inserts into the reverse map first, then checks `is_clean`,
      then maps, all under an rmap mutex (not the `tlb_c` spinlock);
    - `tlb_set_dirty`'s upgrade re-checks `is_clean` under that mutex;
    - no syscall runs under `tlb_c.lock`.
- **M5: VMA and mm costs.**
  - A scattered 4K page splits the reservation into about two VMAs, so the
    cap is on VMAs, not pages.
  - "Unmap" is `mmap(PROT_NONE, MAP_FIXED|MAP_ANONYMOUS)`, never `munmap`.
  - Use `MADV_POPULATE_*`, since a fresh map costs a host minor fault on
    first touch.
  - **Per-VMA locks (Linux 6.4+):** check both handhelds' kernels. Without
    them, every `mmap`/`mprotect` stalls page faults in the Vulkan and NV2A
    threads. F0a runs with the other threads busy.
- **M6: the re-arm rate is unpriced.**
  - NV2A logs all of RAM for two dirty clients (`nv2a.c:1313`). Each clear
    becomes an `mprotect` of every alias, then a fault and an upgrade on the
    next store.
  - Conker re-translates code 1695 times/s.
  - F0a prices this from `[tlb68]` `rdo`/`rdh`/`sd`.

**LOW**

- **L1: the handler takes a lock.** `tcg_tb_lookup` takes `rt->lock`
  (`region.c:258`), which is safe only because the vCPU thread is its sole
  user; state that in the code. The handler first checks that the PC is in
  the rx buffer and `si_addr` is in the shadow, and chains otherwise.
- **L2: a misaligned store can be partly written.** arm64 may partly perform
  one whose second page aborts. Gate the inline form on a naturally aligned
  memop or document the case, and count it in F1x.
- **L3: unmap on #PF.** A fill that raises #PF unmaps the shadow page.
- **L4: whitelist the flags.** Map only when the flags are 0, or exactly
  `TLB_NOTDIRTY` for a `PROT_READ` mapping.
- **L5: where it cannot apply, additions:**
  - loadvm and reset (`machine.c:404`): drop the shadow and the rmap;
  - gdbstub read watchpoints count as watches;
  - fastmem stays off when TCG plugins are active.

**Net effect on P and the order of work.** The review does not change the
mechanism. It adds one piece of real work, PT-page write tracking, and moves
the cause split into F0a. P stays 0.4. The largest risk remaining is M6
(re-arm churn) on NV2A-heavy titles, which F0a prices before any F1 code.

**Needs outside this lane's grant**, to be requested before F1:
- `hw/xbox/xbox.c` (RAM_SHARED);
- `target/i386/tcg/system/excp_helper.c` (the side-effect-free walk);
- a new `accel/tcg/fastmem.c` and `.h`, and their meson entry (granted).

## Log

- 2026-09-28: branch, both commits, a type check against the NDK compile
  database (`compile_commands.json` from the main tree's Release `.cxx`; no
  new warnings in `physmem.c`, `cputlb.c` or `tcg.c`, which includes the
  backend). Predictions registered. Both devices were held at the start
  (Nova battery 14%, Thor host maintenance).
- 2026-09-28: the pilot was queued, GTA A1 `1-1790629267-lane.memfast-1718274`
  and B1 `1-1790629267-lane.memfast-1718333`, with 20 requests ahead of it. A
  board request (`board-requests/memfast.md`) asks lane.local for a held Thor
  simpleperf window on b_ref. lane.ibcache confirmed it no longer edits
  `tcg-target.c.inc` and needs no reserved register, so X26 is free for
  fastmem. Preflight passes. The phase report and the design are on #507
  (comment 5878543877). The design review was folded in (section 7).
- 2026-09-28 (attempt 2): attempt 1 did not finish because it ended on a
  `waiting:` comment (21:13Z) posted seven minutes after the arms job had
  already REFUSED `memfast-drop-pixels.json` (21:06Z): its `skip_tests` named
  `Texture render target::RenderTextureLoop` with spaces, and skip names use
  the underscored suite, `Texture_render_target::RenderTextureLoop`. Attempt
  1 waited on a verdict that could not come. Fixed in the file only (refs
  unchanged, 31515f9751 -> 82e0ef1fa9); the arms job re-registers it on its
  next tick. Read the newest PR comments before posting a `waiting:`.

## Next, for whoever resumes this lane

1. When the pilot lands, run `mf0_read.py` on A1 and `title_verdict.py` on a
   COPY of both dirs. Check that gameplay was reached, power was measured, and
   the `[mf0]` lines are present. Write `pilots/lane.memfast.ok` with python3,
   then queue the rest per `memfast-drop-soak.json`'s queue_order. The Nova
   titles wait for the battery hold to lift.
2. Read the `[job.arms]` verdict on `memfast-drop-pixels.json`. A moved
   capture is read against that run's `[mf0]` lines before it is called
   anything.
3. Post the census and the J/frame results on #507, then mark PR #590 ready.
4. Phase 2 code waits for #590's merge. Do F0a first, and do not build F1
   before F0a prices the overhead.
