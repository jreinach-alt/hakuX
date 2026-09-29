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

### Result on GTA (the pilot pair, Thor, 300 s each)

| | A1 `…1718274` (31515f9751) | B1 `…1718333` (82e0ef1fa9) |
|---|---|---|
| `[mf0]` lines | 155 | 154 |
| `act=1` | **on every line** (155) | on every line (154) |
| `cb` on those lines | 2 to 27, never 0 | 2 to 27, never 0 |
| armed time (`act=1`, `cb=0`) | at most 2.0 s, all in window 0 (boot) | the same |
| low window: identity / other RAM page / device | 120,689 / **9,306,655** / 0 | 111,590 / 9,215,018 / 0 |
| distinct non-identity pages (low) | **6,310** | 6,292 |
| BAR1 window: identity / other / device | 178,771 / 0 / 0 | 178,481 / 0 / 0 |
| `cb` transitions | 0->1 once, never back | same |

- **98.7% of low-window installs on GTA have VA != PA.** The first samples
  are the XBE image: VA 0x10000 -> PA 0xbf000, 0x11000 -> 0xe0000, and so on.
  The census's guess (`ln > 0`) holds, and by far.
- **The path was activated and then held disarmed by the watches.** `act` is
  1 on every window line, and `cb` rose from 0 once, in window 0, and never
  came back. After window 0 the armed time is 0. Inside window 0 the line
  cannot order the two events, so the bound is that window's 2.0 s (0.6% of
  the run), at boot. So on GTA the path is dead in gameplay *and*, wherever
  it is armed, it reads the wrong page on almost every load. The removal is
  the fix for it. Nightfire, Crimson and AUF follow in the queued A runs.
- **CORRECTION (2026-09-29).** This table first said `act=1` ever: **no**, and
  the bullet said the path was never activated. Both were the reader's error,
  not the run's: `mf0_read.py` counted a line as active only when `cb0ms` was
  0 or more, and `cb0ms` prints -1 on every line (the bug noted under the
  pixel arm), so it found no active line and printed "never activated". The
  reader now keeps `act` apart from `cb0ms` and bounds the armed time from
  `cb`, `up` and `dn`. The dead-path conclusion stands on `cb`; the reason
  given for it was wrong. The same wrong sentence is on #507
  (issuecomment-5888195087) and is corrected there.
- **BAR1 (the VRAM window) is all identity.** Phase 2's shadow can map it
  flat; only the low window needs per-page mappings.

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

### 8. F0a, the offline half (2026-09-29): the rates, from soaks on disk

F0a has two halves. The device half measures the constants (a signal round
trip, an `mprotect`, a page walk) and is still to do. This half reads the
event rates that multiply them, from `[tlb68]`, `[watch311]` and `[mf0]`
lines that finished soaks already printed. **Where a line below conflicts
with sections 1-7, this section wins.**

- **Reader:** `f0a_rates.py <result dir>`; output `out/f0a-rates.out`. The
  span is from the route's `mark gameplay` to the end, unless the row says
  otherwise. Rates are per second of wall time.
- **The kill line** (section 6) is a third of the compare's 17.4% of the
  vCPU: 41-55 ms per wall second on these runs.

| title (device) | full flushes/s | cause | watch inserts/s | INVLPG/s | dirty clears/s, vCPU + other threads | `sd`/s | us per `sd` at the kill line |
|---|---|---|---|---|---|---|---|
| GTA, b_ref profile window (Thor) | 58.7 | `cr3s` 98% | 0.6 | 927 | 394 + 1,085 | 6,309 | 7.9 |
| GTA, R1 profile window (Thor) | 36.1 | `cr3s` 94% | 1.2 | 560 | 385 + 826 | 4,299 | 11.9 |
| GTA, pilot A1 (Thor) | 24.9 | `cr3s` 96% | 0.5 | 416 | 409 + 1,019 | 5,847 | 9.2 |
| GTA, pilot B1 (Thor) | 28.5 | `cr3s` 99% | 0.2 | 493 | 465 + 943 | 4,937 | 10.8 |
| Conker (Nova), **whole run, no mark** | 286.6 | `fo` 100% | 144.7 | 127 | 1,276 + 637 | 6,091 | 8.4 |
| Forza (Nova), **whole run, no mark** | 37.7 | `fo` 98% | 22.3 | 212 | 469 + 61 | 765 | 70.9 |
| Blinx 2 (Nova) | 57.7 | `fo` 100% | 28.9 | 0 | 427 + 2,232 | 2,669 | 20.3 |
| Blinx: The Time Sweeper (Nova) | 0.6 | `cr3s` | 0.0 | 31 | 499 + 332 | 1,231 | 34.5 |
| Crimson Skies (Thor) | 3.6 | `fo` 100% | 1.8 | 0 | 6,515 + 5,499 | 13,860 | 3.8 |
| Nightfire (Thor) | 0.4 | - | 0.0 | 1 | 436 + 9,637 | 13,163 | 3.4 |
| Agent Under Fire (Nova) | 0.0 | - | 0.0 | 0 | 282 + 6 | 282 | 124 |

The two unmarked rows include boot and menus, so read their rates as the
run's, not gameplay's. The runs are on different builds (ids in the output
file); a rate here sizes a design, it does not compare builds.

**What the rates decide**

- **H4's cause split is answered, and there are two kinds of title.**
  - **GTA reloads CR3 with the same value,** 25-59 times a second, 94-99% of
    its full flushes.
  - **Every other title's full flushes are ours.** `fo` is twice the watch
    insert rate: Conker 286.3 against 2 x 144.7, Blinx 2 57.7 against
    2 x 28.9, Crimson 3.6 against 2 x 1.8. That is one
    `tlb_flush_all_cpus_synced` per insert and one per remove
    (`system/physmem.c:960` and `:987`, both marked "FIXME: flush only
    applicable pages").
  - **No title changed CR3's value, CR0, CR4 or A20 in gameplay.** The guest
    has one address space, so section 2's revalidation never meets a new
    page directory in play.
- **The per-page watch flush moves ahead of F1.** Section 2 placed it in F2.
  - At Conker's 287 full flushes a second, a revalidation of an 8,192-page
    mapped set at about 25 ns a page is about 59 ms per second: over the
    kill line by itself. The 25 ns is an estimate; the device half measures
    it.
  - It is softmmu-only work inside this lane's files, and it pays without
    fastmem: each of those flushes empties the TLB and the jump cache today.
    **It is the next code item after phase 1 merges,** with its own
    prediction: `[tlb68] fo` to about 0 on Conker, Blinx 2 and Forza, and
    pixels identical.
- **On GTA, revalidation is affordable without PT-page write tracking.**
  59 flushes a second at the same estimate is about 12 ms per second, a
  quarter of the kill line. Section 7's H4 write tracking becomes an
  optimisation to measure later, not a precondition of F1.
- **M6 is priced, and a fault per re-arm cannot pay.** `sd` is above 4,000
  a second on four of the eight titles: GTA, Conker, Crimson and Nightfire.
  A design in which each one is a protection fault and an `mprotect` has 3.4
  to 12 us per event on those four before `sd` alone reaches the kill line. A signal round trip under libsigchain plus an `mprotect` is
  of that order, so the design must not depend on the constant. **Amendment:
  write permission in the shadow is optional, and it starts off.**
  - Section 2's invariant is one-way. A shadow page mapped read-only where
    softmmu would allow a store is always correct: the store faults to its
    stub, and the stub is today's path.
  - **F1 maps every page `PROT_READ`.** Dirty clears and `tlb_set_dirty` do
    not touch the shadow, so `rd`, `rdo` and `sd` cost F1 nothing. F1's
    reverse map serves watches only.
  - **F2 grants write permission late.** A page becomes writable in the
    shadow only after it has gone a stated interval with no dirty clear. The
    first clear takes the permission away, and `tlb_set_dirty` never gives it
    back. The `mprotect` rate is then bounded by the clears that land on
    quiet pages, not by `sd`.
- **F1 alone is sized at the load compares: 8.9% of GTA's vCPU** (leg S, on
  b_ref), plus the refill part of the helpers. The store compares are 5.7%.
  So loads-only reaches about 60% of the compare, and it carries none of the
  dirty-tracking risk. **This is the reason to build F1 first and judge F2
  on its own numbers.**
- **INVLPG is not a risk.** At most 927 a second, each one unmap.
- **GTA refills 770-1,330 pages after each full flush** (`[mf0]` installs
  per flush, census windows only). That is softmmu's cost today,
  `tlb_set_page_full` at 1.8-2.8% of the thread, and it is the set a
  revalidation would keep.

**The order of work, as amended**

| step | what | gate |
|---|---|---|
| W1 | watch insert and remove flush only the pages of the watched range | phase 1 merged; its own prediction |
| F0a, device half | the constants, measured with the other threads busy | a board request for a native test binary |
| F0b | RAM on a memfd, fastmem off | `hw/xbox/xbox.c` granted |
| F1 | loads only, every shadow page read-only, revalidate by walking | F0a prices it under the kill line on GTA and Conker |
| F1x, F2, F3 | as section 6, with F2's late write permission | each on the one before |

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
- 2026-09-28 (attempt 3): attempt 2 did finish its work: it pushed the fix
  (d6ef986b59) and ended on a `waiting:` at 21:14Z. It was resumed because
  lane.local's 21:20Z comment (R1 on disk) became the newest word on the PR,
  and the addendum asks to read R1 now. This attempt merged origin/master
  (20 commits; a merge, so the registered refs stand) and read R1, below.
  It posted R1 on #507 (issuecomment-5878914281) and ended on a `waiting:`
  on #590 for the arms verdict, the two pilot soaks (both still queued) and
  the held b_ref capture.
- 2026-09-28 (attempt 4): attempt 3 did not finish because its head never
  built on Desktop. It waited on the device while CI's Desktop build had been
  red since f49f39b859: `cputlb.c` is built into the target-independent
  `libsystem`, where `TARGET_PAGE_BITS` is a runtime value, so the census
  bitmaps sized with it were variably modified at file scope. Android builds
  it with a constant and was green, so the registered refs' APKs are
  unaffected and the refs stand. Fix: the bitmaps use a constant 12-bit shift
  (the Xbox page). Checked by a `gcc -fsyntax-only` stub with a runtime
  `TARGET_PAGE_BITS`: the old lines give both CI errors, the new ones none.
  A full local configure was not permitted in this sandbox; CI's Desktop
  build is the check. Read every CI job on the head, not only Android,
  before posting a `waiting:`.
- 2026-09-29 (attempt 5): attempt 4 did finish: CI went green on 6badcd9404
  (Desktop and Android) and it ended on a `waiting:` at 21:39Z. It was
  resumed because its four requests had all finished overnight: the GTA
  pilot pair and the arm pair. This attempt read the pilot (census table
  above; J/frame below), wrote `pilots/lane.memfast.ok`, and queued the
  other nine soaks in `memfast-drop-soak.json`'s order:
  `1-1790676918-lane.memfast-1478484` (GTA B2), `-1478533` (GTA A2),
  `-1478575`/`-1478620`/`-1478678`/`-1478752` (Nightfire B1 A1 B2 A2),
  `-1478812`/`-1478877` (Crimson B1 A1), `-1478936` (AUF A1). The Nova was
  held for charging at the time. The arms job had not posted its verdict yet,
  though both arm result dirs existed.

- 2026-09-29 (attempt 6; the resume header numbers it 3): attempt 5 did
  finish, ending on a `waiting:` at 10:16Z. It was resumed at 03:29 PDT on
  a **false premise**. The addendum says the nine soaks had finished, but
  all nine were still in `queue/`, behind about 44 requests, with the Nova
  held to charge and the Thor held for a title push. The waiter keys on
  `-memfast-`, but lane request ids read `lane.memfast-…`, so only the arms
  ids matched it; the arm pair finishing (03:12 PDT) looked like "nothing
  left". Check `queue/` before scoring anything. This attempt read the arm
  pair before the arms job judged it (below) and ended on a `waiting:` for
  the nine soaks and the verdict.

- 2026-09-29 (attempt 7; the resume header numbers it 4): attempt 6 did
  finish, ending on a `waiting:` at 10:32Z for the nine soaks, the arms
  verdict and the b_ref capture. It was resumed because the capture landed
  (05:32 PDT). The verdict had posted too (10:39Z, FAIL 6 of 3379). The nine
  soaks were still in `queue/` with nothing running, the Thor in a cool-down
  hold. This attempt merged origin/master (26 commits; a merge, so the refs
  stand), read leg S (below), found and corrected the `act` error in the
  census table, answered the verdict with the noise record, and did the
  offline half of F0a (section 8). It ended on a `waiting:` for the nine
  soaks.

- 2026-09-29 (attempt 8; the resume header numbers it 1): attempt 7 did
  finish, ending on a `waiting:` at 12:47Z for the nine soaks. It was resumed
  because the ground moved under that wait, twice:
  - hostops (12:51Z) put the `regressed` label back: `arms.sh state`
    recomputes it from the verdicts on disk, so an answer in prose cannot
    clear it. Only a newer registration on #507 that passes can;
  - lane.local (12:00 PDT) withdrew the four Thor soaks (GTA B2/A2, Crimson
    B1/A1) and moved fps and J/frame runs to the Nova.

  This attempt merged origin/master (62 commits; a merge, so the refs stand)
  and registered `memfast-drop-pixels-stable.json` (section below). It
  registered `memfast-drop-soak-nova.json` for Crimson and GTA on the Nova,
  queued the Crimson pair there (`1-1790709139-lane.memfast-1486524` B,
  `1-1790709140-lane.memfast-1486748` A), and read Nightfire pair 1. Nightfire
  B2 went VOID, so it was re-queued (`1-1790709166-lane.memfast-1492075`).
  GTA's Nova copy has not landed (`hardware/titlepush/listing-nova.txt`), so
  GTA is not queued.

## The superseding pixel prediction (2026-09-29)

`docs/testing/predictions/memfast-drop-pixels-stable.json`, on the same refs
(31515f9751 -> 82e0ef1fa9) and the same disc (100 suites, RenderTextureLoop
skipped).

- **The rule.** Every capture must stay bit-identical, except the ones that
  took two or more `differing` values on ONE build. A build is one
  `apk_sha`, run twice or more, in results on disk that do not carry this
  change.
  - Reader: `unstable_caps.py`; output: `out/unstable-caps.out`.
  - It found 217 such captures across 1,258 results. 212 of them are on this
    disc: Texture_cubemap 71, Bump_map 38, Texture_render_target 32,
    Volume_texture 15, Stencil 12, Vertex_shader_rounding_tests 9, and a
    few in other suites.
  - The file's `excluded_unstable` field lists them.
- **Why same-build, not cross-build.** A cross-build rule (two or more values
  anywhere) marks 1,679 of 3,168 captures, because code changes move
  captures between builds. Same-build variation cannot be code, so it is
  noise.
- **The six captures of the FAIL are all in the set.** The rule catches them
  without naming them.
- **Checks: 3,167 captures**, 342 patterns. Each pattern is a whole suite
  where no capture is unstable, or a single capture name where some are.
  - A dry run against the old arm pair gives PASS on all 3,167. That run is
    POST-HOC and tests only that every pattern matches a capture; the
    verdict that counts comes from the fresh arm the arms job queues.
- **Refutation:** any capture outside the excluded set moving.

## Nightfire pair 1 (Nova; `title_verdict.py` on copies in `.scratch/nf/`)

| | A1 `…1478620` (a_ref) | B1 `…1478575` (b_ref) | B/A |
|---|---|---|---|
| gameplay | 268.7 s | 270.1 s | |
| flips / scored s | 8040 / 273.0 | 8100 / 274.7 | |
| net W | 7.667 | 6.937 | 0.905 |
| **j_per_frame** | 0.2603 | 0.2352 | **0.904** |
| fps window median | 29.75 | 29.76 | 1.000 |
| share at >= 30 fps | 58.2% | 65.3% | |
| crash / hang / thermal status | none / none / 0 | none / none / 0 | |

- **B2 `…1478678` is VOID.** At 119 s the app had no focused window
  (`not-foreground`), so it scored no flips. It was re-queued once, as leg V
  allows. A2 `…1478752` is still queued.
- **Nightfire runs at its 30 fps cap,** not the 60 the registered F leg
  assumed. Its median is at the cap in both arms, so on Nightfire the fps leg
  is VOID by the leg's own rule, and J carries the claim.
- **J 0.904 is one pair, larger than the profile's 4-6% of vCPU time
  predicts,** as GTA's 0.830 pilot was. Both pairs moved net W by far more
  than the vCPU's share can explain. Run order does not explain it alone:
  this pair ran B first, and GTA's pilot ran A first. The two-pair mean is
  the registered measure.
- **Census, a_ref (`out/mf0-nightfire-a1.out`).** The same shape as GTA:
  - `act=1` on every line, and `cb` between 4 and 16;
  - armed for at most 2.1 s, in window 0 (boot);
  - low window: 7,963 identity installs against 1,385,657 non-identity
    (99.4%), on 1,026 distinct non-identity pages;
  - BAR1: all identity;
  - the first samples are the XBE image again (VA 0x10000 -> PA 0xbf000).

## Leg S: b_ref's profile against R1 (GTA, Thor, cold)

- **Captures.** A is R1 (`perf/2026-09-28-ibcache-r1`, master 01e62d8d1c).
  B is `perf/2026-09-29-memfast-bref` (b_ref 82e0ef1fa9): xo 46.3 C at the
  start, no thermal pause, `prof start` 74 s after `mark gameplay`, the MAX
  regimen, as R1.
- **Readers.** `legs_read.py` (this lane, new), `jitmix.py`, `symsplit.py`.
  Outputs: `out/legs-r1.out`, `out/legs-bref.out`, `out/jitmix-bref.out`,
  `out/sym-bref.out`.
- **Verdict: PASS.** The registered claim is that the preamble and the
  per-load test read about 0 on b_ref. Of b_ref's 3,429 disassembled TBs
  (95% of the mapped JIT samples), **none** holds either sequence; of R1's
  3,829, all hold the preamble and 3,292 the per-load test.

| | R1 (master) | b_ref | |
|---|---|---|---|
| vCPU samples / in the JIT | 21,168 / 10,773 (50.9%) | 21,934 / 10,510 (47.9%) | |
| TBs holding the preamble | 3,829 of 3,829 | **0 of 3,429** | leg S |
| TBs holding a per-load test | 3,292 | **0** | leg S |
| per-load tests per executed TB | 7.44 | **0.00** | |
| preamble, at-ip | 488 samples, 2.4% of the thread | 0 | |
| per-load test, at-ip | 150 samples, 0.7% | 0 | |
| host instructions per executed TB | 462.6 | **363.9** (-21%) | 7 preamble + 89 test |
| host per guest instruction | 26.12 | 20.63 | |
| softmmu compares per executed TB | 12.74 | 12.79 | unchanged, as designed |
| softmmu compare, at-ip | 17.5% of the thread | 14.6% | |
| ... on loads (7.44 and 7.28 per TB) | 2,378 samples, **11.8%** | 1,845 samples, **8.9%** | the test sat ahead of these |
| ... on stores (5.30 and 5.51 per TB) | 1,140 samples, **5.7%** | 1,189 samples, **5.7%** | the control: stores never had the test |
| the TB's first instruction (`bti`) | 973 samples, 4.8% | 1,125 samples, 5.4% | the jump into the TB |

- **The removed code held 3.1% of the vCPU thread, not 8%.** `jitmix.py`'s
  `preamble` role is 14.3% of R1's JIT samples, which is where the plan's 8.5%
  and this file's 8.0% came from. Two thirds of it is the TB's first
  instruction, the BTI landing pad ahead of the preamble: 973 of the role's
  1,461 samples. That is where the jump into the TB is billed, and it is
  still there on b_ref (1,125). It is lane.ibcache's cost (TB lookup and
  chaining), not the preamble's. The preamble's own seven instructions held
  488 samples. **On its own instructions phase 1 is 2.5% (static) to 3.1%
  (at-ip) of the vCPU,** and R1's section below is amended by this.
- **The load compares fell with it, and the store compares did not.** The
  compare that follows a load fell from 11.8% to 8.9% of the thread. The
  compare that follows a store, which never had the test ahead of it, held
  at 5.7% in both captures. The count of compares per TB did not change. So
  about 2.9% of the thread that was billed to the load's compare was the
  test's: its `cbz` and the branch around the fast-path block sat
  immediately ahead. With that, the removal reads **about 6% of the thread
  (2.4 + 0.7 + 2.9)**, and the store row says the two captures are
  comparable on this cost despite their other differences.
- **Why a new reader.** `jitmix.py` marks a TB's first instructions
  `preamble` until it meets `mov w26, #0`, and stops at 10. b_ref never
  emits that `mov`, so the role books the first 10 instructions of every TB
  and reads **13.0%** on the build where the preamble is gone. The static
  `xbox_fp` class has the matching blind spot: it keys on x26/x27, which b_ref
  hands to the allocator (5,678 ordinary uses in these TBs), and it still
  reads 0.1%. `legs_read.py` books a sample only inside the emitted sequence
  and prints the count of TBs that hold it. Do not read `preamble` or
  `xbox_fp` from `jitmix.py` on any build after this PR.
- **What this pair cannot show.** A and B differ by more than the removal:
  b_ref's base (be05285c44) is ten emulator commits ahead of R1's master, and
  b_ref carries the census. The two windows also did different guest work:
  same-value CR3 reloads 34/s against 58/s, INVLPG 560/s against 927/s. So the
  softmmu bucket's rise (7.0% to 9.5%) is not this change's.
  `tlb_set_page_full` rose 1.82% to 2.81%, a factor of 1.54 against 1.6 times
  the flushes, so the census costs nothing that this pair can see. A share
  is also not a saving: both threads ran 86-88% of the wall, so the saving
  is read from the work rate below.

### The work rate, from the same logs (an observation, not a registered leg)

vCPU CPU time per frame: `[tlb68] cpu` over the span, divided by the mean
frame rate over the same span (`[shd413] f`, which steps by 60 frames).

| pair | A | B | B/A |
|---|---|---|---|
| R1 vs b_ref, profile windows (70 s each) | 881 ms/s at 25.32 fps = 34.8 ms | 858 ms/s at 25.78 fps = 33.3 ms | 0.957 |
| pilot A1 vs B1, from `mark gameplay` (same base, 100 s each) | 923 ms/s at 25.84 fps = 35.7 ms | 918 ms/s at 27.42 fps = 33.5 ms | 0.938 |

- The pairs give -4.3% and -6.2% of vCPU time per frame. That agrees with
  the profile's 6% (the sequences' own 3.1% plus the 2.9% that left the load
  compares), and it is inside the brief's 4-8%. Two pairs, one title: a size
  to expect, not a result.
- **The pilot's J/frame of 0.830 is not this change.** A 4% cut in one
  thread's time cannot take net power from 6.19 W to 5.44 W. That pair's J
  differs for some other reason, and the registered J leg (the mean over two
  pairs per title) is what decides it. The vCPU is one term of the power, so
  a 4-6% cut in its time per frame is a smaller cut in J/frame, and against
  3.6% of per-pair noise two pairs may not resolve it. If the J leg reads
  inside the noise, that is the honest result; the fps leg and these
  counters carry the size.

## The pixel arm, read before its verdict (both arms on the Thor)

`1-1790631509-arms-memfast-base-2314018` (31515f9751) and `-fix-2314089`
(82e0ef1fa9): 3379 captures each, exact 1386 vs 1384. **6 captures differ**
on the scoring columns:

| capture | base differing px | fix differing px |
|---|---|---|
| `Stencil/Stencil_ZERO` | 40000 | 0 |
| `Stencil/Stencil_ZERO_ST_DT` | 40000 | 30000 |
| `Stencil/Stencil_ZERO_ST_DT_ZB` | 10000 | 30000 |
| `Stencil/Stencil_ZERO_ST_ZB` | 0 | 30000 |
| `Vertex_shader_rounding_tests/GeometrySuperscreen_0.4999` | 0 | 800 |
| `Vertex_shader_rounding_tests/GeometrySuperscreen_0.5626` | 0 | 570 |

**The path was never armed during the sweep, in either arm**, so the
removal cannot have moved these. Evidence from each arm's `logcat1.txt`
`[mf0]` window lines (774 base, 729 fix): `up` sums to 1 (the first watch
insert, at boot, while `act=0`), `dn` sums to 0, and `cb` is at least 5 in
every window with `act=1`. The fast path needs `act=1` with `cb=0`, which
never held. The moves are noise:
- Stencil is the #79 flake, and it swaps in both directions here;
- `GeometrySuperscreen_0.5626` takes several hashes across arms on builds
  without this code (notify488 NOTES:219, flip474 `sysmem.md`:197).
  `_0.4999` is the same test family at 800 px, with no prior record found.

**The verdict posted at 10:39Z: FAIL, 6 of 3379, label `regressed`,** the
same six. **Each of the six is on record as unstable on builds without
this change.** `arm_noise.py` (output: `out/arm-noise.out`) read
`scores1.tsv` in the 1,251 other results
on disk (aliases folded, this lane's four excluded); the counts are
differing pixels, with the number of runs in brackets:

| capture | runs on other builds | not exact | values seen | this arm (base / fix) |
|---|---|---|---|---|
| `GeometrySuperscreen_0.4999` | 59 | 7 | 400 (3), 800 (2), 1 (2) | 0 / 800 |
| `GeometrySuperscreen_0.5626` | 59 | 8 | 285 (5), 570 (3) | 0 / 570 |
| `Stencil_ZERO` | 48 | 9 | 40000 (8), 5000 (1) | 40000 / 0 |
| `Stencil_ZERO_ST_DT` | 48 | 26 | 30000 (23), 34950, 20000, 5050 | 40000 / 30000 |
| `Stencil_ZERO_ST_DT_ZB` | 48 | 22 | 30000 (18), 20000 (2), 5050, 2500 | 10000 / 30000 |
| `Stencil_ZERO_ST_ZB` | 48 | 18 | 30000 (16), 20000, 10000 | 0 / 30000 |

- `_0.4999` does have a prior record: 800 px on dpforce345's base
  (2dc2b5c49a), a build with none of this code.
- All six of the fix arm's values are values these captures take elsewhere.
  Two of the base arm's are not (40000 on `_ST_DT`, 10000 on `_ST_DT_ZB`);
  both are on captures that already take four distinct values, and the base
  arm is the side without the change.
- With the path unarmed in both arms, the falsifier's reading stands: the
  moves are these captures' run-to-run noise.

My registered prediction said "every capture bit-identical", with no noise
allowance, so a strict verdict is FAIL on 6 of 3379. The prediction's own
falsifier ("a moved capture ... a_ref's [mf0] lines say which") reads them
as unarmed, so not caused by the change. The next pixel prediction from this
lane should exclude the known-noisy captures up front instead of asserting
them.

- **An `[mf0]` reader bug:** `cb0ms` prints -1 on every line of these runs.
  The `cb==0` span opens at the first watch insert, so the closed total stays
  0 and `p_cb0` never leaves 0. Read `up`/`dn` and `cb` instead.

## Pilot J/frame (GTA, one pair; not a verdict)

`title_verdict.py` on copies (`.scratch/`, not committed). Both runs reached
gameplay, power was measured on battery, and neither had a thermal pause.

| | A1 (a_ref) | B1 (b_ref) | B/A |
|---|---|---|---|
| scored gameplay | 99.5 s | 93.9 s | |
| flips in the window | 2580 | 2580 | |
| net W | 6.188 | 5.442 | 0.879 |
| **j_per_frame** | 0.2386 | 0.1981 | **0.830** |
| fps window median | 27.14 | 28.21 | 1.039 |
| share of time at >= 30 fps | 14.4% | 39.6% | |

- B/A 0.830 is well past the predicted -3.5 to -7%, and it is one pair. Both
  runs cleared the shader cache (the APK changed), so the two ran under the
  same cold-cache conditions. Still, one pair against a 3.6% per-pair noise
  figure cannot size the effect. The J leg is judged on the mean of GTA's two
  pairs and Nightfire's two pairs, as registered.
- Both FAIL the Playable screening on duration (300 s requests) and on fps.
  That is expected and not this lane's measure.

## R1: master's shares, from lane.local's cold GTA capture

- **Capture.** `/home/justin/hakux-work/perf/2026-09-28-ibcache-r1`: master
  01e62d8d1c, Thor, cold start (xo 49.9 C), no thermal pause, recorded
  about 77 s after `mark gameplay`. Captured for lane.ibcache (PR #591);
  shared here, not repeated.
- **Readers.** `jitmix.py` and `symsplit.py --tid 19768` from
  `docs/lanes/vcpuplan/`. Outputs: `out/jitmix-r1.out`, `out/sym-r1.out`.
- **vCPU thread:** 21,168 samples (over lane.ibcache's 10,000 floor);
  10,773 in the JIT (50.9%), 95% of the mapped JIT samples disassembled.

| share of the vCPU | R1 (master, cold) | vcpuplan s4 (#589) | reading |
|---|---|---|---|
| inline softmmu compare (`tlb` role, at-ip) | 34.4% of JIT = **17.5%** | 17.4% | phase 2's main target |
| preamble + per-load test (`preamble` 14.3 + `xboxchk` 1.5 of JIT, at-ip) | **8.0%** | 8.5% | phase 1's target, at-ip |
| the same, static (`xbox_fp` class) | 4.9% of JIT = **2.5%** | - | phase 1's target, skid-free |
| softmmu helpers (`softmmu` bucket) | **7.0%** | 7.9% | `tlb_set_page_full` 1.8, `tlb_reset_dirty` 1.2, `probe_access_internal` 0.8, `mem_access_callback_address_matches` 0.5 |
| TB lookup (lane.ibcache's) | 24.9% | - | not this lane's |

- **The preamble was armed in 0 of 43 samples** that landed on its outcome
  branch, and **0 samples fell inside a load fast-path block.** On master,
  cold, in gameplay, the path is dead, as the plan said.
- **Phase 1 is sized at 2.5-8.0% of the vCPU.** The static weighting counts
  the preamble's instructions; the at-ip one counts where the stalls land,
  and the preamble's first load (`ldr w16,[x27,#8]`) is where a TB-entry
  stall is billed. The truth is between. The registered soak leg does not
  depend on which, since it measures J/frame and fps.
  - **AMENDED by leg S (2026-09-29): 2.5-3.1%.** The 8.0% counted the TB's
    first instruction, the BTI pad, as preamble: 973 of the role's 1,461
    samples. The TB-entry stall is billed there, not on the preamble's first
    load, and b_ref still pays it. The rows above that say 8.0% and 14.3%
    are `jitmix.py`'s role, kept as first written.
- **Phase 2's ceiling on master** is the 17.5% compare plus the refill part
  of the 7.0% helpers (`tlb_set_page_full`, `mmu_translate`, `mmu_lookup1`:
  about 2.6%). `tlb_reset_dirty` at 1.2% is the cost the design's M6 (re-arm
  churn) turns into `mprotect`s, so it is a live term on GTA too, not only on
  the NV2A-heavy titles.

## Next, for whoever resumes this lane

0. DONE: leg S is read and passes (section "Leg S"). Do not re-run the
   readers on either capture. Read `preamble` and `xboxchk` with
   `legs_read.py`, never with `jitmix.py`, on any build after this PR.
1. **Outstanding soaks, all on the Nova** (as of 2026-09-29 19:30Z):
   - Nightfire A2 `-1478752` and the B2 re-queue `-1492075`;
   - AUF A1 `-1478936`;
   - Crimson B1 `-1486524` and A1 `-1486748`;
   - GTA: not queued. Queue two Nova pairs under
     `memfast-drop-soak-nova.json` once `listing-nova.txt` names GTA. The
     Thor pilot pair is not pooled with them.

   When they land, run `mf0_read.py` on every A run and `title_verdict.py`
   (`.scratch/score.py`) on a COPY of every dir. Judge J as the mean B/A over
   the pairs per title, and G on every B run. **Check `queue/` and `running/`
   before scoring anything.**
2. The first arms verdict (FAIL, 6 of 3379) is superseded by
   `memfast-drop-pixels-stable.json` once its arm runs and passes. Read that
   arm's `[job.arms]` comment; a capture that moves outside the
   excluded set refutes the change.
3. After the soaks: post the J and fps legs on #507 and #590, then mark
   PR #590 ready. The release note's size comes from those legs; the profile
   says to expect 4-6% of the vCPU's time per frame on GTA.
4. Phase 2 code waits for #590's merge. Then, in order: W1 (the per-page
   watch flush), F0a's device half, F0b, F1 (section 8's table). Do not
   build F1 before F0a's device half prices it.
5. Do not repeat: the `act` reading through `cb0ms` (the reader is fixed);
   a pixel prediction that asserts the Stencil_ZERO family or
   GeometrySuperscreen_0.4999/_0.5626 as exact.
