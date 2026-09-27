# lane.aufdispatch -- #412 / #425: why AUF's TBs return to the exec loop, and the fixes

Base: master @ e5db66fa37. Analysis only: no code or prediction here. The
fixes below are designs for lane.retreason425's split to select from. Files
they touch belong to other lanes (named per fix).

Data used, all on disk:

- aufire412b's held Nova profile, APK 1b557ff6a4, AUF survey route:
  `~/hakux-work/perf/2026-09-26-aufire412b/{p1,p2}.data`, vCPU tid 9188
  (p2 = mission play, 26,139 samples; p1 = menus over the scene, 24,698).
  All line numbers below are cpu-exec.c **at 1b557ff6a4**, the profiled
  binary.
- The same capture's per-line breakdown of `cpu_exec_loop` self
  (`p2-loop-lines.txt` in that directory).
- Profiles of other titles on the Nova: `2026-09-26/crimson-p2.data`,
  `ff-p2.data`, `galleon-p{1,2}.data`, `2026-09-26-buildflags427/a.data`.
- `[jc425]` probe counters from nine dispatch soaks (jcache425's four Crimson
  arms, DOA, Nightfire, Kabuki Warriors, Black, tbflip424). None is AUF.
- `[tlb68]` from the AUF perflog soak `1790470425-aufire412b-4161655`.

Tools in this directory (each counts plain `report-sample` records):
`loopshare.py` (per-thread split: JIT, loop self, barrier addresses, lookup,
translation, named helpers), `jithot.py` (how concentrated the JIT samples
are), `rates.py` (loop and indirect probe rates from `[jc425]`).

## 1. The ranking: what returns, from the profile

A TB can return to `cpu_exec_loop` unchained for these reasons. Each one either
leaves samples on its own code path or runs a helper with its own symbol.
Where the path carries no samples, the cause can be ruled out or bounded
without a counter:

| cause (brief's list) | where it would show | AUF p2 samples | verdict |
|---|---|---|---|
| **TB_EXIT_REQUESTED** (a kick: `exit_request`, `cpu_exit`) | `cpu_loop_exec_tb` lines 1670-1701 (the requested path) | 0 of 14,152 loop-self | **excluded** |
| **IRQ pending** (`interrupt_request` set at the check) | `cpu_handle_interrupt` lines 1576-1641 | 3 | **excluded** |
| **I/O and MMIO exits**, exceptions (longjmp) | `io_readx`/`io_writex`, `cpu_handle_exception`, `siglongjmp` | 0 / 1 / 0 | **excluded** |
| **indirect jump, helper miss** (helper returns the epilogue) | a helper miss means no TB in the qht, so the loop's own lookup misses too and translates: loop miss path (1740-1758), `tb_gen_code` | 1 on the miss path; translation 13 (0.05%) | **bounded by the translation rate** (hundreds per s) |
| **cflags mismatch** | a `k` jump-cache miss goes to the qht; `CF_INVALID` (tier-1 promotion) is budget-limited and skips kernel PCs | qht total 194 (0.74%) | **not a return cause**; ≤0.74% as lookup cost |
| **gen_eob plain exit, helper-backed**: FLDCW/FLDENV/FNINIT (EOB_ONLY), POPF, IRET, segment loads, CR/MSR writes | `helper_fldcw__hard`, `helper_fldenv__hard`, `helper_fninit__hard`, `helper_write_eflags`, `helper_iret_protected`, `helper_load_seg` | 1, 0, 0, 0, 0, 0 | **excluded** (under ~10^4/s against ≥10^6/s returns) |
| **gen_eob plain exit, no helper**: STI (EOB_INHIBIT_IRQ) plus the one-instruction shadow TB after it; a jump that ends a shadow TB | nothing: STI sets IF inline | -- | **live, invisible to the profile** |
| **page-spanning target** (`tb_page_addr1(tb) != -1` clears `last_tb`, line 1770) | nothing: line 1770 runs on every iteration | -- | **live, invisible to the profile** |
| `o`: superblock exit rewrite | `XBOX_SUPERBLOCK_ENABLED` is 0 | -- | excluded by build |

`tb_add_jump` also has 0 samples, and lines 1775-1776 have none. So the loop
almost never receives a `last_tb` that survives the page check: the returns
are not first-time unpatched `goto_tb` exits into ordinary targets.

That leaves **two live causes, and the profile cannot tell them apart**:

1. **page-spanning targets** (rr425 `gs`), and
2. **STI and interrupt-shadow exits** (rr425 `es`, `ej`, `esh`).

I rank the page-spanning cause first, on shape rather than proof. AUF's guest
code is concentrated: 50% of its JIT samples fall in 7 buckets of 256 host
bytes (Crimson needs 640, and Fuzion Frenzy's known spin loop needs 1). The
lowest bucket is the TCG prologue/epilogue and alone holds 13.1% of JIT. The
rest sit in about three code regions. That is a hot inner loop of a few TBs.
If one of those TBs straddles a 4 KB guest page, every iteration returns, a
title-specific accident that fits Crimson reading 11.7% on the same binary.
The STI cause needs millions of STIs a second in game code. It is not ruled
out, but nothing points to it.

**Predictions this analysis makes of rr425's split** (the AUF B soak,
`1790477867-retreason425-2004056`, mission window):

- `r`, `m`, `ip`, and `eo`/`en` whose PC bytes start `d9`/`9d`/`cf`
  (FLDCW, POPF, IRET): **each under 5% of `it`**.
- `gs + es + ej`: **at least 80% of `it`**.
- `it`: **5-17 M returns/s** (estimate, section 2). Floor: at least 1 M/s
  while the vCPU runs, since 45 of 65 mission `[tlb68]` windows print
  `dt=2000`, so 1,024 loop iterations took under 1 ms. Crimson's windows
  overshoot 1-7 ms, because it runs long chained stretches between returns.

If `o` or `m` is large instead, this ranking is wrong: read the `[rr425pc]`
PCs before building anything.

## 2. What a return costs, and why AUF has so many

Per-return cost on AUF p2, as a share of the vCPU thread's 26,139 samples. The
ms column is that share times 54.0 ms of vCPU CPU per frame (aufire412b §6), a
**bound** on each item's per-frame cost:

| per-return item | samples | share | ms/frame (bound) |
|---|---|---|---|
| the `stlrh; dmb ish; ldar` in `cpu_handle_interrupt` (0x5b1a8c, 0x5b1a90) | 9,781 | 37.4% | 20.2 |
| rest of `cpu_exec_loop` self (state, inline jump-cache hit, tier1, checks) | 4,371 | 16.7% | 9.0 |
| `cpu_tb_exec` self | 1,945 | 7.4% | 4.0 |
| state getters called from the loop (`x86_get_tb_cpu_state`, `curr_cflags`) | 1,157 | 4.4% | 2.4 |
| TCG prologue/epilogue (lowest JIT bucket, 13.1% of JIT) | ~896 | 3.4% | 1.8 |
| **total per-return stack** | **~18,150** | **69.4%** | **37.5** |

**The barrier is not AUF's problem. The number of returns is.** On every title,
the barrier is about 2/3 of `cpu_exec_loop` self:

| capture | loop self | barrier (top 2 loop addresses) | barrier / loop | loop self / JIT |
|---|---|---|---|---|
| AUF p2 | 54.1% | 37.4% | 0.69 | **2.07** |
| AUF p1 | 51.2% | 35.4% | 0.69 | 1.78 |
| Fuzion Frenzy p2 | 22.0% | 15.5% | 0.70 | 0.38 |
| Galleon p2 | 12.0% | 8.2% | 0.68 | 0.27 |
| Crimson (buildflags427 a) | 9.4% | 6.5% | 0.69 | 0.36 |
| Crimson p2 (perfbase) | 2.3% | 1.3% | 0.57 | 0.08 |

AUF returns 5-25 times more often per unit of guest work than the others.

**Return rate, an estimate.** The loop's non-barrier instructions carry about
45 samples each in p2, or 1.7 ms per second of CPU per instruction. At an
assumed ~3 GHz big core and 0.33-1 cycle per instruction, that is **5-17 M
returns/s**, or 0.3-1.1 M per frame at 16.1 fps, at 36-120 ns each. rr425's
`it` measures it directly. Use `it`, not this estimate, for any ms figure.

**What the brief's lookup-side candidates are worth on AUF** (from
jcache425's `price_lookup.py` on p2):

| lever | what it removes | AUF share | ms/frame (bound) |
|---|---|---|---|
| inline indirect-branch probe in the aarch64 `lookup_and_goto_ptr` | the helper call: `helper_lookup_tb_ptr` self 1.4% + getters via the helper 0.9% | 2.3% | 1.2 |
| jump-cache shape (size, second way) | qht probes on a jump-cache miss: `qht_lookup_custom` + `tb_lookup_cmp` + `tb_htable_lookup` | 0.74% | 0.4 |
| chaining a `goto_tb` across pages (translator side) | cross-page direct jumps already go through `lookup_and_goto_ptr`, **not** the loop. So this is a subset of the inline-probe line above | ≤2.3% | ≤1.2 |

All three are sound levers on Crimson, where the helper is 10% of the thread.
On AUF they are worth about 2 ms per frame together, and none of them removes
a return.

## 3. The fixes

The fixes do not add up. Fix 0 shrinks what every return costs, so it shrinks
what Fix A and Fix B can save per return. Price them in the order they land.

### Fix 0 (cause-independent): skip the barrier when no kick is pending

**What.** In `cpu_handle_interrupt` (cpu-exec.c at 1b557ff6a4 line 1570; the
`qatomic_set_mb` of `icount_decr.u16.high`), clear and fence only when there
is something to clear:

```c
if (unlikely(qatomic_read(&cpu->neg.icount_decr.u16.high))) {
    qatomic_set_mb(&cpu->neg.icount_decr.u16.high, 0);
}
/* unchanged: load-acquire of interrupt_request, then exit_request */
```

**Why it is safe.** Every writer of `high = -1` first sets the reason:

- `tcg_kick_vcpu_thread` stores `exit_request` and then store-releases
  `high`;
- `cpu_exit` stores `exit_request` and then kicks;
- `tcg_handle_interrupt` sets `interrupt_request` and then kicks, or on the
  vCPU's own thread stores `high` directly.

The barrier exists so that clearing `high` cannot erase a kick whose reason
this iteration then fails to see.

- If the relaxed read sees `-1`, the code does exactly what it does today.
- If it sees `0`, nothing is stored, so nothing can be erased. A kick whose
  store is not yet visible stays in `high`. The next TB's entry check
  (`gen_tb_start`: `icount_decr.u32 < 0`, translator.c) exits with
  `TB_EXIT_REQUESTED`, and the next iteration takes the full path. Delivery
  latency is at most one TB. That is the same bound every chained TB already
  runs under.

**Bound.** At most 37.4% of the vCPU on AUF p2 (≤20.2 ms/frame), 15.5% on FF,
8.2% on Galleon, 1.3-6.5% on Crimson. It is a bound, not a value. Part of the
`dmb` stall is the guest's own stores draining, and without the `dmb` they
drain in the background, but some of that cost can resurface wherever the
store buffer fills. Only an arm gives the value.

**Arm.** AUF survey-route perflog soak, A = master, B = the hunk. Legs:
`[tlb68]` `cpu=` per frame falls; the sample share at the barrier address
goes to ~0 (needs a profile); fps is reported, not judged, because
aufire412b §2-3 shows the frame is VBLANK-paced. Pixels must not move (8
suites).

**Files.** accel/tcg/cpu-exec.c only, which is lane.retreason425's until
PR `lane/retreason425` folds. It does not depend on the split, and can be
queued as soon as that file is free.

### Fix A (cause: page-spanning target, rr425 `gs`): chain into a spanning TB, unlink on TLB flush

**What stops it today.** cpu-exec.c line 1770 clears `last_tb` for any TB
with a second page. The reason given is that the second page's virtual to
physical mapping can change under a direct jump. The jump cache has the same
exposure: its hit path does not re-check page 2. It is protected by being
invalidated on every TLB flush:

- `tlb_flush_by_mmuidx_async_work` calls `tcg_flush_jmp_cache`
  (cputlb.c:641);
- `tlb_flush_page_by_mmuidx_async_0` clears the page and the one before it
  (806-807);
- the range flush does the same (997, 1007).

`HAKUX_TCG68_JC` changes only the discard path (tb-maint.c:1487), not these
three.

**Design.** Give chained-into spanning TBs the same protection:

1. Per vCPU (one on the Xbox), keep a small array `span_linked[]` (for
   example 64 entries) of spanning TBs that have incoming chains, and one flag
   bit per TB for "listed".
2. At line 1770: if the TB spans, and it is listed or there is room to list
   it, keep `last_tb` so that `tb_add_jump` runs. Otherwise clear it as
   today.
3. In the three flush sites, next to the jump-cache invalidation, unlink
   every listed TB's incoming jumps and empty the list. That needs
   `tb_jmp_unlink(tb)`, which is static in tb-maint.c:1431, behind a new
   exported wrapper. A page or range flush may unlink only the TBs whose
   second page lies in the flushed range, but the simplest correct version
   unlinks all of them.
4. `tb_phys_invalidate` (SMC or a discard) already unlinks incoming jumps and
   must also drop the TB from the list.

**Cost.** One unlink pass per flush. Across all 63 `[tlb68]` lines of AUF
mission play (299-483 s of `1790470425-aufire412b-4161655`), `ff`, `fo` and
`cr3s` sum to 0. The busiest window read, at boot, has 85 CR3 reloads
(`cr3s`) in 2 s. Each flush walks at most 64 entries.

**Bound.** (share of `it` that is `gs`) x 69.4% of vCPU before Fix 0, or x
~32% after it. Take the share from rr425. At 100% it would be 37.5 ms/frame
before Fix 0. A chained jump costs ~0, so nearly all of the per-return stack
is saved.

**Must-hold legs.** `gs` falls to ~0 in `[rr425]`. `ga` rises once per
(listed TB, flush epoch), not per iteration. Pixels are identical. Add a
CR3-heavy control, the Crimson route or a menu window with `cr3s` > 0, to
exercise the unlink.

**Files.** accel/tcg/cpu-exec.c (retreason425's), accel/tcg/cputlb.c and
accel/tcg/tb-maint.c (lane.tbflip424's). This one is a board request.

### Fix B (cause: STI / interrupt shadow, rr425 `es`, `ej`, `esh`): look up instead of exiting when no interrupt is pending

**What stops it today.** `gen_eob()` (translate.c) uses `exit_tb(NULL, 0)`
for every mode except an uninhibited `DISAS_JUMP`. For STI it exits twice:

- the STI TB ends with `EOB_INHIBIT_IRQ`;
- the next TB starts in the shadow, is cut after one instruction
  (translate.c:4533), and ends with `inhibit_reset`.

Both exit so that the loop can deliver an interrupt that became deliverable
when IF went to 1. An interrupt that arrives later needs no exit: it kicks,
and the next TB's entry check catches it. Only an interrupt **already
pending** (`interrupt_request` set earlier, refused while IF was 0) needs the
loop.

**Design.** In `gen_eob()`, for `EOB_INHIBIT_IRQ` and for any EOB with
`inhibit_reset`, when `HF_TF_MASK` is clear, emit:

```c
TCGv_i32 t = tcg_temp_new_i32();
TCGLabel *pend = gen_new_label();
tcg_gen_ld_i32(t, tcg_env, offsetof(ArchCPU, parent_obj.interrupt_request)
                           - offsetof(ArchCPU, env));
tcg_gen_brcondi_i32(TCG_COND_NE, t, 0, pend);
tcg_gen_lookup_and_goto_ptr();
gen_set_label(pend);
tcg_gen_exit_tb(NULL, 0);
```

- The lookup takes its state from `env` after the STI, so it finds the
  shadow TB, keyed with `HF_INHIBIT_IRQ`. The shadow semantics hold because
  the shadow TB is still one instruction long.
- A relaxed read is enough. A request that is set but not yet visible was
  followed by its kicker's store to `high`, so the next TB's entry check
  exits.
- The same conditional form fits POPF (`EOB_NEXT`, IF may go 0 to 1) and
  IRET (`EOB_ONLY`). The profile says both are rare on AUF, so they are
  optional.
- FLDCW, FLDENV and FNINIT end with `EOB_ONLY` only so that the next TB
  reloads the host FPCR (`gen_flcr`, once per TB) and keys the new
  `HF_FPU_PC`. They cannot enable an interrupt, so they can use
  `lookup_and_goto_ptr` unconditionally. That is worth ~0 on AUF, whose
  `helper_fldcw__hard` has 1 sample, and it is listed so that nobody builds it
  for AUF.

**Bound.** (share of `it` in `es + ej`) x (69.4% of vCPU minus a helper
lookup per replaced return). The helper path is ~2.3% of vCPU at AUF's
indirect-branch rate, which is about one-fifth of its returns. At 100% that is
about 35 ms/frame before Fix 0.

**Must-hold legs.** `es`/`ej`/`esh` fall to ~0, and `hc` rises by the same
count. `iq` (interrupts taken) does not fall per second of guest time. Pixels
are identical. Run a timer-interrupt-heavy control (any title's boot) to show
that no interrupt is lost.

**Files.** target/i386/tcg/translate.c (retreason425 edits only its counter
tag there). Board request.

## 4. Reading rr425's split into a decision

| rr425 dominant | fix | first check |
|---|---|---|
| `gs` | A | the `g:` PCs in `[rr425pc]` sit within one TB length below a 4 KB boundary (page offset 0xf00-0xfff) |
| `es`, `ej`, `esh` | B | the `e:` PCs' first byte is `fb` (STI), or the shadow's next instruction |
| `en` with `9d`, `eo` with `cf` | B, conditional form at POPF/IRET | contradicts this analysis (helpers have 0 samples): recheck the counter first |
| `eo` with `d9` (FLDCW) | B, unconditional FP part | contradicts `helper_fldcw__hard` = 1 sample: recheck the counter first |
| `m` | inline probe / jump-cache shape (≤1.2 / ≤0.4 ms) | contradicts the miss-path samples: the helper must be missing on a key the loop finds |
| `r`, `ip` | none designed: find the kicker | contradicts lines 1670-1701 = 0 samples |
| `o` | none: read the PCs | a cause this table does not list |

Whichever of A or B, Fix 0 applies too, and is not selected by the split.

## Status (2026-09-26, session 1)

Done: the ranking (section 1), the per-return pricing and the cross-title
comparison (section 2), and three designs with bounds, files and legs
(section 3). The retreason425 soaks had not run when this was written
(`1790477867-retreason425-2004056` and `-2004282` have no result directory),
so nothing here uses `[rr425]`.

Posted on #412 (issuecomment-5852701461) and #462 (issuecomment-5852701584).
preflight passes.

Not done: no code. Every fix touches another lane's file: cpu-exec.c
(retreason425), cputlb.c and tb-maint.c (tbflip424), translate.c. Fix 0 is
the one to queue first: it is independent of the split, and cpu-exec.c-only.

## Do not repeat

- Do not read FLDCW as AUF's cause. MSVC's `_ftol` does two FLDCWs per cast,
  and this tree ends a TB at every FLDCW, which made it a good suspect. But
  `helper_fldcw__hard` has 1 sample in 26,139. Check a cause's helper
  symbol before building for it.
- Do not price the indirect-branch levers (inline probe, jump-cache shape)
  for AUF from Crimson's numbers: the helper is 10% on Crimson and 2.3% on
  AUF.
- The barrier's share of loop self is ~0.69 on every title. A large barrier
  share means many returns, not a slow barrier.
- `[tier1] threshold=` never reaches logcat (qemu_printf), so
  aufire412b's `loops.py` finds no lines. Use rr425's `it`.
