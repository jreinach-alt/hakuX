# lane.vcpuplan (#507): where the vCPU's time goes, and a ranked plan

Brief: `briefs/vcpuplan.md`. Docs only: no device run, no code change, no
board edit. Base `origin/master @ 6d2b2e49eb`.

**The short version.**
- **About a third of GTA's vCPU thread goes to translating guest addresses:**
  - the inline softmmu TLB compare is 17% of the thread;
  - the slow-path helpers are 8%;
  - a per-TB XBOX preamble adds 8%. It buys nothing in gameplay, because the
    load fast path it arms is switched off whenever any NV2A surface watch is
    live.
- **None of this showed in any earlier profile.** It sits inside the
  "guest JIT code" bucket that the energy map (#586) read as the guest's own
  work.
- **The approach that fits the platform** is to give guest memory to the host
  MMU (Dolphin's fastmem, ESPT in QEMU).
- **The indirect-branch lookup is second** (23% of the thread).
- **Floating point is not where the time is.** x87 already runs as inline
  native-double code, and the SSE float helpers are already native.

## 1. Where the vCPU thread's time goes

### 1.1 Sources, and what makes each one trustworthy

| id | title, place | device, build | record | what it is |
|---|---|---|---|---|
| **G4** | GTA SA, alley after the route's `gameplay` mark, fast regime, 28.8 fps | Thor, a593d8eb85, fp_jit on | `perf/2026-09-27-gta482/s4/rec-on.data` + `codebuf-77d9822000.bin.gz` (the full 128 MiB TCG buffer) | on-CPU, 23,492 vCPU samples (tid 16027), gta482 NOTES:255-280 |
| G5 | GTA SA, same route, **thermally paused** (cpu3-7 off), 2 fps | Thor, same | `.../s5/` | code mix only; its ms are void (gta482:493) |
| GA | GTA SA alley | Thor, a593d8eb85 | `perf/2026-09-26-slowdown462/gta/gta.data` | on-CPU, 28,045 vCPU samples (slowdown462:656) |
| FZ | Forza race, 28 fps | Nova, a593d8eb85 | `perf/2026-09-26-slowdown462/forza/forza.data` | off-CPU trace: 57% of its samples are kernel sleep; the shares below exclude them |

Counts are `report-sample` records, not simpleperf's rounded percentages. All
four records are on a593d8eb85. That build predates cf09ea47a1, which made
the jump-cache wipe skip (#425, `HAKUX_TCG68_JC`) the default.

**Tools, new in this lane.** Both run offline, on files only.
- `symsplit.py` books each sample's leaf symbol into the brief's buckets.
- `jitmix.py` reuses gta482's `tbmap.py` to map each JIT sample to its
  TranslationBlock. It disassembles the TBs that hold 95% of the samples
  with the NDK's llvm-objdump, then books each sample by the role of the host
  instruction it landed on:
  - `preamble`: the XBOX `active`/`cb_count` checks at TB entry;
  - `exitchk`: the exit-request check;
  - `xboxchk`: the per-load fast-path test;
  - `tlb`: the TLB LDP through its `b.ne`;
  - `tbexit`: the EIP store and the chain branch;
  - `body`: everything else.

  Roles are found from the code's shape, and `--dump N` prints annotated
  listings to check them against.

### 1.2 The split (share of the vCPU thread's on-CPU samples)

| bucket | G4 GTA fast | GA GTA alley | FZ Forza | status |
|---|---:|---:|---:|---|
| **JIT'd code, total** | **53.9%** | 49.8% | 42.2% | measured |
| ... inline softmmu TLB compare (`tlb`) | **17.4%** | - | - | measured at-ip, G4 (32.3% of JIT); G5 46.5% of JIT |
| ... XBOX preamble + per-load test (`preamble`, `xboxchk`) | **8.5%** | - | - | measured at-ip (14.3 + 1.5% of JIT); G5 17.3% |
| ... exit-request check (`exitchk`) | 2.0% | - | - | measured (3.7% of JIT) |
| ... EIP store + chain branch (`tbexit`) | 3.3% | - | - | measured (6.2% of JIT); skid-prone, see 1.3 |
| ... the guest's own work, flags, env traffic (`body`) | 22.7% | - | - | measured (42.1% of JIT) |
| ... of which x87 scalar FP instructions | 0.6% | - | - | measured (1.1% of JIT at-ip; 9% of JIT samples are in TBs that hold any FP op) |
| ... of which a two-TB guest spin-wait (`0x273686`, `0x27368e`) | 6.4% | - | - | measured (11.8% of JIT, gta482:278) |
| **TB lookup** (`tb_lookup` 9.5, `helper_lookup_tb_ptr` 6.2, `qht_lookup_custom` 4.4, `tb_lookup_cmp` 1.8, `x86_get_tb_cpu_state` 0.7) | **22.8%** | 24.8% | 27.4% | measured on a593d8eb85; **stale**, see 1.4 |
| **softmmu slow path** (`tlb_set_page_full` 1.9, `tlb_reset_dirty` 1.2, `probe_access_internal` 1.2, `mmu_translate` 0.6, `do_ld4_mmu` 0.6, ...) | 7.9% | 8.3% | 10.2% (incl. `mem_access_callback_address_matches` 3.5) | measured |
| **x87/SSE helpers** (`helper_mulss` 1.8, `subss` 0.8, `addss` 0.7, `comiss` 0.6: scalar SSE) | 4.7% | 4.7% | 5.3% | measured |
| MMIO exits (`*mmio*`, `io_*`, `memory_region_*`) | 0.6% | 0.7% | 0.7% | measured |
| exec loop, lazy-flag and other helpers | 1.1% | 1.2% | 6.3% | measured |
| translation (`tb_gen_code` and friends) | 0.4% | 0.5% | 0.7% | measured |
| kernel | 2.0% | 2.3% | (excluded) | measured |
| other (APU `voice_lock` 1.2, `tlsdesc_resolver` 0.6, since removed by #427, ...) | 6.7% | 7.8% | 7.2% | measured |

Reproduce with:
- `python3 docs/lanes/vcpuplan/symsplit.py <rec-on.data> [--tid T]`
- `python3 docs/lanes/vcpuplan/jitmix.py <session dir> [--dump 6]`

The outputs behind the table are in `out/`:
- `sym-s4.out`, `sym-gta-alley.out`, `sym-forza.out`;
- `jitmix-s4.out`, `jitmix-s5.out`;
- `jitmix-s4-dump.out`, the annotated listings of the six hottest G4 TBs,
  written by an earlier revision of the script without the role table.

**Guest-address translation totals 33.8% of GTA's vCPU:** the inline compare
(17.4), the slow path (7.9) and the preamble plus per-load test (8.5).

### 1.3 What the listings show, and the limits of at-ip attribution

- **The XBOX load fast path is dead in GTA gameplay.**
  - **The code:** every TB starts with `ldr w16,[x27,#8]; cbz; ldr
    w16,[x27,#0xc]; cbnz; ldr x26,[x27]; b; mov w26,#0`
    (`tcg/aarch64/tcg-target.c.inc:4512-4545`). Each load then tests x26
    (`:1787-1843`).
  - **The samples:** across the TBs that hold 95% of the samples, the armed
    leg (`ldr x26`) has 0 samples in G4 and 0 in G5. The `mov w26,#0` leg has
    79 and 69. No sample lands inside any per-load fast-path block. The
    listing of `0x273686` shows the `cbnz` on `cb_count` taken.
  - **Why:** `cb_count` is incremented for every `mem_access_callback_insert`
    (`system/physmem.c:894-900`). Those callbacks are the NV2A surface
    watches, so while a title has a watched surface, every load takes the
    full TLB compare and also pays the dead test.
  - **Forza** has `mem_access_callback_address_matches` at 3.5% of its thread,
    so its callbacks are live too (inferred: no code buffer was dumped for
    Forza).
- **The fast path assumes guest VA == PA, and nothing verifies it.**
  `host_base` is the base of guest physical RAM (`hw/xbox/xbox.c:203`), but
  the test indexes it with the guest *virtual* address. There is no check that
  a page below 64 MB is identity-mapped. The fast path also skips the
  present/permission check and the check for loads straddling the end of RAM.
  - Where it was measured it never ran, so the hazard is latent there.
  - It is live on any title with no surface watch.
  - No lane has examined it (a search of `docs/` finds only
    `perf-architecture.md:241`, which describes it). The expert review (§4)
    found the same.
- **Skid limits the at-ip numbers.** A sample lands on the instruction after a
  stall.
  - The `tlb` window contains the comparator load and the addend load.
    Their misses are real TLB cost, but the stall after the guest load itself
    lands on the first `body` instruction, not on `tlb`.
  - The 283 and 222 samples on the EIP store just before the chain branch in
    the two spin TBs are the branch's redirect cost, booked to the store.
  - The preamble's samples are spread evenly over its six instructions
    (22/14/12/14/10/11 in `0x273686`), so they are not only TB-arrival skid.
  - The shares are therefore sized with a discount in §5; they are not
    savings.

### 1.4 Measured versus inferred

- **Measured:** every row of the table for G4/GA/FZ, the preamble outcome,
  and the x87 share (G4).
- **Inferred:**
  - **The TB lookup share on current master is lower than 22.8%, by an
    unmeasured amount.** On Crimson, the JC default cut qht probes from 11.25%
    to 2.31% of the thread (`jcache425/NOTES.md:130-156`). On G4 the qht part
    is 4.4%; the hit path (`tb_lookup`, the helper call, `tb_lookup_cmp`,
    `get_tb_cpu_state`: 18.4%) is not what JC removes. Best guess on master:
    17-20%.
  - **The inline `tlb` and preamble shares on Forza, Nightfire and MA2** are
    not measured. No code buffer exists for them.
- **Unmeasured on any bound title:**
  - Nightfire and MechAssault 2 have no profile at all. MA2's energy-map row
    is a paused run. Unpaused, MA2 sits at its 30 fps cap with the vCPU
    on-CPU 98% and the renderer idle 28.7 of 33.4 ms (slowtier2:69). That is
    a spin at the cap, not a vCPU-bound title.
  - `[rr425]`/`[rr425pc]` return reasons.
  - `g_fpu_profile` dynamic counts (`emit.c.inc:594-603`, never read).
  - Slow-path store causes.
- **The one run that decides the biggest unknown** is R1 in §6. It measures
  GTA on current master with the code buffer dumped: `symsplit.py` gives the
  lookup share after JC, and `jitmix.py` gives the `tlb`/`preamble` shares on
  master.

## 2. What translators built for x86-on-ARM64 do differently

Web research used WebFetch only (WebSearch was denied to the research agent).
The Dolphin blog, the ACM PDFs and the QEMU wiki refused. Each claim below
cites its URL.

| technique | who, and what they publish | numbers (published) | in hakuX today | fit |
|---|---|---|---|---|
| **Guest RAM through the host MMU; MMIO trapped by page protection** | Dolphin fastmem: direct access; a faulting access is backpatched to a `BL` to the slow path ([JitArm64_BackPatch.cpp](https://raw.githubusercontent.com/dolphin-emu/dolphin/master/Source/Core/Core/PowerPC/JitArm64/JitArm64_BackPatch.cpp)). ESPT puts QEMU softmmu on the host MMU ([VEE'14](https://api.openalex.org/works/doi:10.1145/2576195.2576201)); HSPT does it with mmap alone ([VEE'15](https://api.openalex.org/works/doi:10.1145/2731186.2731188)). FEX and Box64 are user-mode, where this is free | ESPT: **1.51x** (ARM guest on x86) and **1.59x** (IA32 on x86_64) from the memory technique alone. No Dolphin number reached (403) | softmmu compare (~9 insns, 2 dependent loads) on every access; a VA<64 MB load bypass that is off in gameplay and assumes VA==PA (§1.3) | **The platform fit.** 64 MB fixed RAM, a single page directory in gameplay (`cr3s` 0-96/s, slowdown462), MMIO at fixed windows. **Large rework** |
| **Return-address stack, inline indirect-branch cache** | Rosetta 2 maps CALL/RET onto BL/RET with a validating side stack ([dougallj](https://dougallj.wordpress.com/2022/11/09/why-is-rosetta-2-fast/)). Box64 `CALLRET=2` is default, plus an inlined jump table ([USAGE.md](https://github.com/ptitSeb/box64/blob/main/docs/USAGE.md), [v0.4.4](https://box86.org/2026/08/new-box64-v0-4-4-release/)) | no isolated number published | every RET/indirect JMP calls `helper_lookup_tb_ptr` (`cpu-exec.c:1636`); a 4096-entry jump cache with a 6+6-bit hash (`tb-hash.h:46-51`); no RAS | **Local-to-medium rework**: `translate.c`, `cpu-exec.c`, `tcg/aarch64` |
| **Register allocation across blocks** | FEX multiblock ([FEX-2502](https://fex-emu.com/FEX-2502/)); Box64 `BIGBLOCK=2` default and preloading XMM before loops ([v0.4.0](https://box86.org/2026/01/new-box64-v0-4-0-released/)); HQEMU 2.4-4x over QEMU on SPEC (a whole LLVM tier) | no isolated number | per-TB allocation; the fork's superblocks exist but are off (`XBOX_SUPERBLOCK_ENABLED 0`, `cpu-exec.c:488`); tier-1 does dead-flag elimination | medium-large rework; SMC and precise-exception risk |
| **x87 on the host FPU with a precision policy** | FEX `X87ReducedPrecision`; x87 stack resolved per block: 2340 → 165 host instructions on one routine ([FEX-2408](https://fex-emu.com/FEX-2408/)); Box64 `X87DOUBLE` ([USAGE.md](https://github.com/ptitSeb/box64/blob/main/docs/USAGE.md)). xemu's own #211 host-FPU x87 is x86_64-only ([PR 211](https://github.com/xemu-project/xemu/pull/211/files)) | instruction counts, no fps | **Done.** `fp_jit` (default on, `config_spec.yml:367`): ST(n) as native double, inline TCG FP ops (`translate.c:1810-2110`, ba30a0bffd) | nothing left to take on GTA: x87 is 0.6% of the vCPU (§1.2) |
| **SSE mapped to NEON** | FEX, Box64 and Rosetta translate directly. QEMU's 2022 decoder rewrite left packed float as helpers ([patchew](https://patchew.org/QEMU/20220911230418.340941-1-pbonzini@redhat.com/), no perf numbers) | none isolated | integer SSE inline gvec (`emit.c.inc:826-845`); float SSE a helper per instruction; helper bodies are **native NEON/C float** (`ops_sse.h:32-33` defaults `XEMU_OPT_NATIVE_FLOAT` to 1, despite CMake's `OFF`) | local: scalar `ss` ops onto the fp_jit backend's existing f32 ops. 4.7% of the vCPU is the ceiling |
| **Native flags (NZCV, FlagM)** | FEX since 2312; FlagM SETF8/16 up to 14% in one benchmark, ~4% Geekbench ([FEX-2403](https://fex-emu.com/FEX-2403/)). The X3/A715 have FlagM/FlagM2 (v9.0 includes v8.5; [LLVM](https://raw.githubusercontent.com/llvm/llvm-project/main/llvm/lib/Target/AArch64/AArch64Features.td)) | whole-release numbers | lazy `cc_op`; the helpers are 0.25% (jcache425:62); inline flag stores (cc_dst/cc_src/cc_op) sit in `body` | low: only part of `body`, unmeasured |
| **Memory ordering (TSO)** | FEX: "near a 10x performance hit" for TSO emulation ([FEX-2404](https://fex-emu.com/FEX-2404/)); upstream xemu barriers every guest access even with one vCPU ([tcg-op.c](https://raw.githubusercontent.com/xemu-project/xemu/master/tcg/tcg-op.c)) | - | **Done**: barriers elided under XBOX (`tcg/tcg-op.c:325-358`, #54) | nothing to take |
| **Idle-loop detection** | Dolphin's JIT idle skipping (from memory; the blog refused, so no URL) | - | #525's idle halt matches only the kernel's `sti; nop; nop; cli` (`cpu-exec.c:1152-1157`) | local; energy |

## 3. What this tree already tried

Issue states are read from `gh issue list`.

| item | status | why; what not to re-propose |
|---|---|---|
| #81 tier-1 promotion slots | CLOSED; fix folded (7dfa94c403) | the mechanism fires but is starved (the table fills in 2.2-2.7 s); dedup landed. Its fps value was never measured, and the lazy-flag helpers it targets are 0.25% |
| #90 tier-hint restore | CLOSED | dead preprocessor on Android (`translate-all.c:659-688`); ruled out offline in the tier81fix prediction |
| #68/#311 tcgchurn: RD, JC, keep-armed (a), TLB cap (b) | (a)/(b) dormant; RD in #575; JC default-on | #311's model refuted (the arming walk was 0.8%); **do not re-propose (a)/(b) for fps** |
| #424 range test + code bitmap | OPEN; landed opt-in (`HAKUX_TCG424_RANGE=1`, #434), default flip parked | Crimson churn 21% → 0 (gfps 26 → 29, pixels identical); Blinx no-regression leg failed; bound on GTA 4.4% of frame (gta482:61-66) |
| #425 jump-cache wipe (JC) | OPEN issue; JC landed default-on (#465) | qht probes 11.25% → 2.31% on Crimson. Its other half, "an inline indirect-branch probe", was **never built**: that is item 3 below |
| #425 return reasons (aufdispatch 0/A/B) | closed as a lever | 99.9% of AUF's returns are the kernel idle loop. **Do not re-propose chaining, EOB-across-STI or barrier levers against the exec-loop share** without `[rr425pc]` |
| #525 idle halt | OPEN; opt-in (#528); default judged by #566 | frees a core, no fps; matches the kernel idiom only |
| #428 prime-core pin | CLOSED, refuted | -21.5% fps: the pinned vCPU is ejected to little cores under heat. **No hard pin.** #544 ADPF refuted too (the HAL ignores hints) |
| #429 smaller TBs | CLOSED, refuted offline | guest-written blocks = 0 in gameplay; blocks are already 5.6 insns |
| #427 build flags | landed | emutls/outline atomics 3.42% → 0.41%. LTO never tried |
| perfarch rcpc TSO build | parked | did not boot (misaligned LDAPR, likely); moot with barriers elided |
| perfarch patch-free chaining | unbuilt | bound ~1.3%; chaining misses ≤ 1% |
| #548 dirty-TLB RD | OPEN; #575 waiting on arms | render thread -3.35 ms/flip on Crimson; vCPU walks x0.16 |
| #461, #372 | OPEN; not vCPU | texture hashing / Blinx surfaces |
| #54 guest barriers | tracker row open (latent) | **already elided**; FEX's TSO cost does not apply |
| upstream hardfloat (Cota 2018) | compiled in (`fpu/softfloat.c:187-237`) | f32/f64 only, never floatx80 ([patchew](https://patchew.org/QEMU/20181124235553.17371-1-cota@braap.org/)); moot for x87 (fp_jit) and for SSE (native helpers) |
| upstream TCG aarch64 backend | QEMU 10.2.0 base (`QEMU_VERSION`) | no later upstream backend work was pulled; nothing found that targets this workload |
| #557 predictive governor | stopped by the owner | do not re-propose |

## 4. Independent expert review

A subagent with the persona of an engineer who has shipped an x86-to-ARM64
translator (FEX/Box64 class) got the facts and code paths, not my
conclusions. It had the profile split of §1.2 without the `jitmix` columns,
which did not exist yet. It read the code; it did not measure.

**Its view:**

1. **Premise corrections.**
   - The SSE native-float helpers ship ON: `ops_sse.h:32-33` defaults the
     macro to 1, and CMake only ever emits `=1`, the same "OFF meant ON" bug
     as TB cache hints.
   - The jump cache's hash is 6 page bits + `pc & 63`, which explains the 86%
     collision share of misses.
2. **The load fast path is wrong or risky.** It assumes VA==PA, skips the
   present/permission and end-of-RAM checks, and is off whenever
   `cb_count > 0` ("Forza probably never gets it"). The per-TB preamble is "a
   lot for 5.6 guest instructions". Fix correctness before perf work.
3. **Its top 5:**
   1. Inline indirect-branch cache + RAS (~0.6 x 8-12%);
   2. multi-block regions via the existing superblocks (~0.4 x 10-20%);
   3. park the guest spin-wait (~0.7 x 5-6% of thread energy);
   4. inline SSE float as custom TCG ops (~0.7 x 3-4%);
   5. stop the not-dirty store tax with a code-page bitmap (~0.4 x 3-5%).
4. **What it would not do:** a store twin of the X26 path before VA==PA is
   answered; a full x87 allocator or 80-bit work; native flags; more TSO
   work; qht tuning.

**Where I agree:**
- **Both premise corrections.** I had read `XEMU_OPT_NATIVE_FLOAT` as off
  from CMake alone. It is on, and §2 and the plan are corrected.
- **The fast path's correctness.** My measurement sharpens it: the path never
  ran in either GTA session, so the preamble is pure cost there, and the
  VA==PA hazard is latent where measured and live elsewhere.
- **The x87, flags, TSO and qht exclusions.** The data agrees: x87 is 0.6% of
  GTA's vCPU.
- **Spin-wait parking.** The listing now shows what the loop is:
  `0x273686`/`0x27368e` load a word at guest `0x5f2534`, compare it with EAX,
  and loop, with no stores. On a one-vCPU machine only an interrupt handler
  or a device write can change it. I rank it on energy and on reach: MA2 at
  its cap spins with the vCPU 98% on-CPU, which the `[rr425w]` idle
  signature cannot see.
- **Inline scalar SSE.** Yes. The measured helpers are all scalar (`mulss`,
  `subss`, `addss`, `comiss`), and the fp_jit backend already has the f32
  ops.

**Where I disagree:**
- **The order.** The review put the indirect-branch cache first because the
  profile it saw showed lookup as the largest non-guest cost. `jitmix`
  shows guest-address translation is larger: 33.8% of GTA's vCPU against
  22.8% (stale, likely lower now) for lookup. The review's own "don't build
  a store twin before VA==PA is answered" argues for the host-MMU design,
  which does not assume VA==PA at all.
- **Multi-block regions:** below its rank. Its kill test was "boundaries
  under 15% of JIT". Boundaries measure 24.2% of JIT (preamble 14.3, exit
  check 3.7, EIP/chain 6.2), but 15.8 points of that are the preamble and
  per-load test, which item 3 removes cheaply. What is left (about 5% of the
  vCPU) plus unmeasured register sync does not carry the SMC and
  precise-exception risk of regions.
- **The not-dirty store bitmap:** folded into item 1, which replaces the
  TLB's store checks, instead of built separately.

## 5. The ranked plan

**Ranking rule** (lane.md, "Ranking options"): expected impact = probability
x win at full scale; effort breaks ties. The approach that fits the hardware
leads.

**Sizing.** On a vCPU-bound title below its cap, J/frame falls about 0.87x
the vCPU time saved: the energy map's "15% vCPU speedup is about -13%
J/frame" (#586, row 4). Titles bound now:
- GTA SA (vCPU share 0.81, guest idle 0.01);
- Nightfire (0.77 / 0.06);
- Forza after #583 (0.91 / 0.05).

Near-bound: Crimson (0.94 / 0.15), D&D (0.79 / 0.18). On capped titles a vCPU
saving is worth joules only through the halt (#566), and there it reaches all
13 titles.

| rank | item | P | win at full scale (vCPU time; J/frame on bound titles; fps) | P x win |
|---|---|---:|---|---:|
| 1 | Guest memory through the host MMU ("fastmem") | 0.40 | 12-20% vCPU; **-10 to -17% J/f**; +12-22% fps on GTA-class titles | **6.4** |
| 2 | Inline indirect-branch cache + return-address stack | 0.50 | 8-13% vCPU; -7 to -11% J/f | **5.3** |
| 3 | Drop the dead XBOX preamble and per-load test (a slice of #1 that ships alone) | 0.80 | 4-8% vCPU; -3.5 to -7% J/f; +4-8% fps | **4.8** |
| 4 | Park pure guest polling loops until an interrupt | 0.45 | GTA 6.4% vCPU → -4% J/f; capped spinners (MA2 at cap) -10 to -20% J/f, **energy only** | 2.7-4.5 |
| 5 | Scalar SSE onto inline fp_jit f32 ops | 0.70 | 2.5-4% vCPU; -2 to -3.5% J/f | 2.2 |
| 6 | Multi-block regions (superblocks on) | 0.25 | 5-10% vCPU | 1.9 |

Ranks 1-3 go first and in parallel: 1 is the platform-fitting lead, 2
touches different code, and 3 is small, proven by reading, and ships in days.
Item 0 below is a correctness census, not a speed item, and it gates rank 1's
design.

### Item 0: correctness census of the load fast path (gates 1 and 3)

- **What:** a counter build. At `tlb_set_page_full` for mmu_idx user/kernel,
  count installs with VA < 64 MB where the page's PA != VA, and log the first
  8 (VA, PA). Count `cb_count > 0` time per title (the preamble leg taken)
  and `[TLB-FP] activated` per session.
- **Why first:**
  - If any title runs with no surface watch and a non-identity low page, the
    shipped fast path returns wrong data today. That is a bug to fix
    regardless.
  - The census also sizes rank 1: distinct guest mappings, PTE-change and
    flush rates.
- **Probability:** it decides something whichever way it reads. P it finds
  live non-identity pages under an armed fast path: unknown. The Xbox maps
  the XBE onto kernel-allocated pages (expert review).
- **Files:** `accel/tcg/cputlb.c` (lane.dirtytlb, released; #575 still open,
  so land after it), or read-only through `[tlb68]`'s existing line.
- **Needs device:** yes (one soak each on GTA, a title without surface
  watches, and AUF). No pixel legs: counters only.

### Rank 1: guest memory through the host MMU

- **Mechanism** (ESPT/HSPT on QEMU; Dolphin fastmem):
  - Back guest RAM with a memfd. Reserve 4 GiB of host VA as a shadow of the
    guest's 32-bit virtual space.
  - On `tlb_set_page_full` for a RAM page that is not watched and not a code
    page, `mmap(MAP_FIXED|MAP_SHARED)` the RAM page at shadow + VA, readable
    and writable. Code pages get `PROT_READ`, so a store faults and takes the
    SMC path. MMIO, unmapped and watched pages stay `PROT_NONE`.
  - Guest loads and stores become one instruction, `ldr w, [x_shadow, w_addr,
    uxtw]`, instead of CBZ + TST + LDP + AND + ADD + LDR + LDR + ADD/AND + CMP
    + B.NE.
  - A `SIGSEGV` on the shadow region backpatches that access to a call to
    today's slow path (Dolphin's `HandleFastmemFault`) and retries it.
  - A guest TLB flush or invlpg `munmap`s (or `PROT_NONE`s) the range. Our
    own `tlb_flush_all_cpus_synced` on every watch insert
    (`physmem.c:905`, "FIXME: flush only applicable pages") must become a
    per-page protect first, or it will dominate.
  - The per-TB preamble goes away.
- **Evidence for P = 0.40.**
  - For: the cause is measured at 33.8% of GTA's vCPU. The technique is
    proven for exactly this problem inside QEMU (ESPT 1.51-1.59x) and in the
    console emulator closest to ours (Dolphin). The Xbox has one page
    directory in gameplay (`cr3s` 0-96/s on GTA).
  - Against:
    - Full-flush rates of 514/s (Conker) would make remapping expensive until
      the watch-insert flush is per-page.
    - Android's ART also owns `SIGSEGV` (the handler must chain via
      libsigchain's special-handler hook).
    - A backpatched site stays slow.
    - NV2A dirty tracking moves from the TLB's notdirty bits to page
      protection.
    - It is a large rework across `cputlb.c`, `physmem.c` and the backend.
- **Win at full scale:** the inline compare (17.4%), most of the slow path
  (~5 of 7.9; `mem_access_callback` and MMIO stay), the preamble and
  per-load test (8.5). That is ~31% at face value. Discounted for skid and for
  fault/remap cost: **12-20% of the vCPU; J/f -10 to -17% on GTA,
  Nightfire, Forza; fps +12-22% on GTA.**
- **Titles:** every title (all pay the compare). J/f on the 3-5 bound ones;
  on the rest through the halt.
- **Files and holders** (origin/board `territory.toml` read 2026-09-28):
  - `tcg/aarch64/tcg-target.c.inc`, `tcg/tcg-op-ldst.c`: [free].
  - `accel/tcg/cputlb.c` and `system/physmem.c`: lane.dirtytlb, released,
    with #575 open. Sequence after #575 folds.
  - `include/exec/**` and `accel/**/*.h`: [free].
  - `hw/xbox/xbox.c` (memfd-backed RAM): in no row.
  - A new `accel/tcg/fastmem.c`.
  - `android/app/src/main/cpp/xemu_android.cpp` for the signal chain:
    check the board at dispatch.
- **Prediction legs:**
  - **(exact) goldens bit-identical.** A memory-path change must not move a
    pixel.
  - **(exact) guest-state equivalence:** a debug mode that runs every
    shadow access and the softmmu path side by side on a soak and counts
    mismatches (must be 0).
  - **(counter)** fastmem faults/s and remaps/s under a stated ceiling.
  - **(fps/J)** GTA and Nightfire same-build pairs, cold start, on battery,
    fps up and J/f down beyond the 3.6% noise.
  - **(regression)** an MMIO-heavy title (BloodRayne: 4,234 kicks/s) holds
    fps.
- **Needs device:** yes, after a host build proves it boots.
- **Step order:**
  1. Item 0.
  2. Watch-insert flush per page (also a standalone win on Conker-like
     titles).
  3. Loads only.
  4. Stores with code pages protected.
  5. Watched pages protected.

### Rank 2: inline indirect-branch cache + return-address stack

- **Mechanism:**
  - At each `lookup_and_goto_ptr` site (RET, JMP/CALL r/m), emit an inline
    probe of a direct-mapped {pc, host ptr} table in env: 2^14-2^16 entries,
    hashing all low PC bits. The flags are a translate-time constant for
    these sites. On a hit, `br`; only a miss calls `helper_lookup_tb_ptr`.
  - On CALL, push {return EIP, host ptr of the fall-through TB} onto a 16-32
    entry ring in env. On RET, compare with the popped EIP and branch
    directly on a match.
- **P = 0.50.**
  - For: Rosetta and Box64 (`CALLRET=2`, default) do it. The helper hit path
    alone (18.4% on G4) is what the inline probe removes, and it is untouched
    by the JC fix.
  - Against: the measured share is on a593d8eb85 and will be lower on master
    by the qht part. The split between returns and other indirects is
    unknown.
- **Win:** 8-13% of the vCPU; J/f -7 to -11% on bound titles.
- **Titles:** all; largest where the lookup share is highest (Forza 27.4%,
  GTA 22.8-24.8%).
- **Files:**
  - `target/i386/tcg/translate.c`: released by lane.idlehaltspin; #565 in
    audit/fold, so coordinate.
  - `accel/tcg/cpu-exec.c`, `accel/tcg/tb-maint.c` (generation counter on
    invalidation), `accel/tcg/tb-jmp-cache.h`, `accel/tcg/tb-hash.h`,
    `include/exec/**`: [free].
  - `tcg/aarch64/tcg-target.c.inc` [free], shared with ranks 1 and 3, so
    sequence the edits or give one lane both.
- **Correctness:**
  - Any TB invalidation, `tlb_flush` or CR3 write bumps a generation that
    table and RAS entries carry (or flushes both).
  - Turn it off with breakpoints set.
  - The target TB's own exit check keeps interrupts timely.
- **Prediction legs:**
  - **(exact) goldens bit-identical.**
  - **(counter)** the RAS hit rate on returns and the inline hit rate, from
    a counter build.
  - **(counter)** `helper_lookup_tb_ptr` calls/s down by at least 70%.
  - **(fps/J)** GTA + Forza pairs.
- **Needs device:** yes.
- **Cheap decider first** (it decides, per the rule): R1 gives the lookup
  share on master. If it is under 8% of the vCPU, demote this item below
  rank 5.

### Rank 3: drop the dead XBOX preamble and per-load test

- **Mechanism:** delete the per-TB preamble (`tcg-target.c.inc:4512-4545`)
  and the per-load `cbz x26` block (`:1775-1850`). Loads take the TLB
  compare they already take in gameplay. If item 0 shows the fast path is
  ever armed and correct on some title, keep it behind one global that
  `tb_flush`es on change instead of re-testing per TB. That is the expert's
  "hoist".
- **P = 0.80:** the code is measured never armed in two GTA sessions, and its
  cost is measured. The risk is a title where the path is armed and fast.
  Item 0 answers that, and the path's VA==PA hazard argues for removal
  anyway.
- **Win:** 8.5% of the vCPU at face value. Discounted for arrival skid:
  **4-8% vCPU; J/f -3.5 to -7%; fps +4-8% on GTA-class titles.**
- **Titles:** all. The removed code runs on every TB entry of every title.
- **Files:** `tcg/aarch64/tcg-target.c.inc` [free];
  `hw/xbox/nv2a/pgraph/vk/renderer.c:2485` (the activation) [free];
  `hw/xbox/xbox.c`.
- **Prediction legs:**
  - **(exact) goldens bit-identical.**
  - **(counter)** `jitmix.py` on a new capture shows `preamble`+`xboxchk` at
    0.
  - **(fps)** GTA same-build pair, cold start, on battery; fps up by at least
    3%.
- **Needs device:** yes (one arm).

### Rank 4: park pure guest polling loops until an interrupt

- **Mechanism:**
  - At tier-1 promotion, recognise a loop of at most 2 TBs with no stores and
    no MMIO/IO reads, whose exit depends on a RAM load, with IF=1. GTA's
    `0x273686` is exactly this: poll `[0x5f2534]` against EAX.
  - On a one-vCPU machine only an interrupt or a device (DMA) write can end
    it. Replace the back-edge with a bounded wait for the next pending
    interrupt, with the same wakeup and bound as #525's halt.
  - Device-written addresses (a surface watch, or a DMA target) are excluded
    or covered by the bound.
- **P = 0.45.** For: the loop is measured, and the idea is Dolphin's idle
  skipping. Against:
  - #525's latency leg failed at 14.2% / 3.7%. The same wake latency applies
    here.
  - A loop polling a device-written word without an interrupt needs the
    bound.
- **Win: energy only.**
  - GTA: 6.4% of the vCPU → about -4% J/f.
  - Capped titles whose wait is their own code (MA2 at its cap, vCPU 98%):
    -10 to -20% J/f (inferred from MA2's renderer idle 28.7 of 33.4 ms).
- **Titles:** GTA (measured); MA2 and other capped titles with a
  title-specific wait (unmeasured, so R3 decides).
- **Files:** `tcg/tier1-opt.c` (in no row), `accel/tcg/cpu-exec.c` [free],
  `system/cpus.c` (check the board; lane.idlehalt retired).
- **Prediction legs:**
  - **(exact) goldens bit-identical.**
  - **(latency)** #525's leg L.
  - **(counter)** parked-loop entries/s and wake reasons.
  - **(J)** MA2 at cap, same-build pair.
- **Needs device:** yes.

### Rank 5: scalar SSE onto inline fp_jit f32 ops

- **Mechanism:** emit ADDSS/SUBSS/MULSS/DIVSS/COMISS/UCOMISS through the f32
  TCG FP ops that ba30a0bffd added for x87
  (`tcg/aarch64/tcg-target.c.inc`), instead of a helper call per
  instruction (`emit.c.inc:586-628`).
- **P = 0.70:** the mechanism exists, and the four hottest helpers are
  measured.
- **Exactness gate:** bit-identical to **today's native helpers**
  (`ops_sse.h` `FPU_ADD` etc. are plain C float ops under the same FPCR), not
  to softfloat.
  - COMISS/UCOMISS flag results must match the helper's for NaN and ±0.
  - MINSS/MAXSS stay helpers: x86 returns the second operand on NaN or ±0, and
    `FMIN`/`FMAX` do not.
  - MXCSR rounding and FTZ/DAZ: bail to the helper unless the translate-time
    MXCSR is the default, or carry it in the TB flags.
- **Win:** the helpers are 4.7% of the vCPU; inline removes the call and
  sync. **2.5-4% of the vCPU; J/f -2 to -3.5%.**
- **Titles:** all SSE users (GTA, Forza measured).
- **Files:** `target/i386/tcg/emit.c.inc` [free under target/**];
  `tcg/aarch64/tcg-target.c.inc` [free].
- **Prediction legs:**
  - **(exact) goldens bit-identical.**
  - **(exact)** an nxdk SSE test XBE (memory: nxdk build recipe) comparing
    results and flags against the helper build over NaN/denormal/±0/rounding
    vectors.
  - **(fps)** GTA pair.
- **Needs device:** yes, for fps; the exactness leg can run on the host
  emulator build.

### Rank 6: multi-block regions

- **What it would buy:** superblocks exist and are off. After ranks 1 and 3
  remove the preamble, the boundary cost left is the exit check (2.0%) and
  EIP/chain (3.3%), plus unmeasured register sync inside `body` (22.7%).
- **P = 0.25:** SMC across pages, precise-exception restore, and the code's
  own "lookup/invalidation integration is being finalised".
- **Revisit** after a new `jitmix` on master, once rank 3 is in, shows the
  env-traffic share of `body`.

### Not proposed, and why

- **x87 register-stack work:** 0.6% of GTA's vCPU.
- **Native NZCV flags:** the helpers are 0.25%; inline flag stores are only
  part of `body`.
- **TSO/rcpc:** barriers are already elided.
- **Jump-cache hash widening alone:** subsumed by rank 2.
- **Hard pin, ADPF, governor:** refuted or stopped.
- **Smaller TBs:** refuted.
- **Chaining/EOB levers against the exec loop:** refuted.
- **LTO:** never tried. It is not a vCPU-structure item, and a build-flag
  lane can price it separately.

## 6. Profile runs (at most 4). Not queued: lane.local slots them

All on the Thor, current master, cold start (xo-therm ≤ 50 C: the start
temperature matters, the regimen does not), defaults regimen, **on battery**,
display on and focused. Each runs gta482's `capture_gta.sh` (an on-CPU
simpleperf record of the vCPU, then the TCG code-buffer dump) and logs
`[jc425]`, `[rr425]`, `[rr425pc]`, `[rr425w]`, `[tlb68]` and `hakuX-pages`.
Readers: `symsplit.py` and `jitmix.py`.

| id | title, route | decides |
|---|---|---|
| **R1** (the one that decides the biggest unknown) | GTA SA, the `gta` alley route as slowdown462/gta482 s4, record 30 s from +60 s after `mark gameplay` | **The lookup share on master after JC** (rank 2 go/no-go at ≥ 8% of the vCPU), and the `tlb`/`preamble` shares on master (sizes ranks 1 and 3). Also whether the preamble is ever armed (item 0's partial answer) |
| R2 | 007 Nightfire, its `titleroutes` route (`1-1790563604-titleroutes-373432`) | the unprofiled bound title: whether GTA's split generalises (ranks 1-3 reach) |
| R3 | MechAssault 2 **unpaused at its 30 fps cap** (as hostops-810152: cold, 24 min at MAX, no pause) | whether a capped title's 98% on-CPU vCPU is a title-own polling loop (rank 4's reach) or real work |
| R4 | Forza, after #583 folds, its forza414 race route | lookup/softmmu split with live memory-access callbacks (3.5%), and the `tlb` share on a second bound title |

## 7. What the next lane should not repeat

- **Do not read "guest JIT code" as the guest's own work.** On GTA, 46% of
  JIT samples are the softmmu compare, the XBOX preamble and TB-boundary
  glue. Run `jitmix.py` before pricing any JIT-side item.
- **Do not trust `XEMU_OPT_*` CMake options' declared defaults.** Read the
  `#ifndef` in the consumer (`ops_sse.h:32`). `NATIVE_FLOAT` ships ON while
  CMake says OFF.
- **The `gta482` s1-s3 sessions are void** (display/focus). s4 is the fast
  regime; s5 is thermally paused (code mix only).
- **`slowdown462`'s Forza record is an off-CPU trace:** 57% of its samples are
  kernel sleep. Normalise to on-CPU before comparing.
- **Every vCPU profile on disk is a593d8eb85.** The lookup bucket is stale
  after cf09ea47a1.
