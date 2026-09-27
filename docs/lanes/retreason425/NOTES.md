# lane.retreason425 -- #425: why the vCPU's TBs return to cpu_exec_loop

Base: master @ 231d04df51. Issue #425, feeding #412 (Agent Under Fire, 4541000D).
Hand-off: #425 comments 01:45Z (lane.aufire412b) and 02:04Z (job.cloud's
correction: the fourth cause, gen_eob's plain exit).

## 1. The counter (6a598c5404)

`[rr425]` and `[rr425pc]`, one line each every 2 s at `[jc425]`'s gate, tag
`hakuX` at WARN (in every runner's LOGCAT_SPEC, so no allow-list edit). Counters
only; no control-flow change. XBOX builds only; always on (no switch).

The problem it solves: a TB that ends in gen_eob()'s plain `exit_tb(NULL, 0)`
and a `helper_lookup_tb_ptr` miss that returns the epilogue both reach
cpu_tb_exec with ret 0, so the loop sees tb_exit 0 and a NULL TB for both. A
loop-side counter cannot separate them. So each marks itself:

- **translator** (translate.c, two hunks): `gen_eob()` stores a 64-bit tag
  into the host global `hakux_rr425_eob` just before each plain
  `exit_tb(NULL, 0)` (the RECHECK_TF arm and the final `else`). The tag carries
  the mode (EOB_NEXT, EOB_INHIBIT_IRQ, EOB_ONLY, RECHECK_TF, DISAS_JUMP inside a
  shadow), whether the TB began in an interrupt shadow, and the pc of the TB's
  last instruction (recorded in `i386_tr_insn_start`, a new DisasContext field
  under XBOX). Codegen cost: a pointer materialisation and one store per such
  exit.
- **helper** (cpu-exec.c): `helper_lookup_tb_ptr` counts its calls (`hc`) and
  misses (`hm`) and sets `rr425_miss` before returning the epilogue.
- **loop** (cpu-exec.c, `cpu_loop_exec_tb`): after every return, reads and
  clears both marks and books the return once: `r` TB_EXIT_REQUESTED, `g` a
  goto_tb exit not yet patched (returned TB non-NULL), `e` tagged, `m`
  helper miss, `o` none of these. At the next dispatch `g` splits into `gs`
  (target spans two pages, never chained), `gi` (CF_INVALID), `ga`
  (tb_add_jump called).
- **context**: `it` dispatches, `x` longjmps into cpu_exec_setjmp, `ip`
  dispatches with `interrupt_request` non-zero, `iq` interrupts taken, `xr`
  loop exits on exit_request.
- **timing**: 1 in 64 dispatches, get_clock() from a TB's return to the next
  TB's entry (`gapus`: the loop, including the barrier in
  cpu_handle_interrupt) and across that TB's run (`tbus`), each scaled by
  `it / samples`. A sample a longjmp lands in is dropped; cpu_exec_loop entry
  resets it so a gap never spans time outside cpu_exec.
- **top PCs** (`[rr425pc]`): the 16 commonest (cause, pc) pairs in the window,
  each with the first three guest bytes at that pc (cpu_memory_rw_debug at
  print time). For `e` the pc is the returning TB's last instruction as
  translated; for the others it is the pc the loop resumes at (under CF_PCREL
  the returning TB's own pc is not known for them).

Self-checks the reader enforces before any number is read (`rr425.py`):
`d = it - (e+m+o+r+g)` must not exceed `x` (a return nothing booked is a
longjmp out of a TB); `m` must equal `hm` up to window-edge slop; `gs+gi+ga
<= g`; `pcdrop == 0`.

Known blind spots, stated so they are not read as zeros: a superblock's
rewritten exit (translate-all.c, `b_exit1->args[0] = 0`) and VMRUN end in `o`,
not `e`. `ga` counts tb_add_jump calls, including ones that find the slot
already claimed. Returns from `cpu_exec_step_atomic` are not booked (their
marks are dropped).

Compile-checked for arm64 Android against the shared tree's compile commands
(clang, NDK 29, the Release flags; no new warnings). `rr425.py --selftest`
passes.

## 2. Arms

| what | ref | request id |
|---|---|---|
| B: counters, AUF survey route, 400 s, Nova | 6a598c5404 | `1790477867-retreason425-2004056` |
| A: master control (fps without counters) | 231d04df51 | `1790477870-retreason425-2004282` |
| pixels must-not-move, 8 suites | 231d04df51 vs 6a598c5404 | `docs/testing/predictions/retreason425-pixels-inert.json` (arms job) |

Read with `python3 docs/lanes/retreason425/rr425.py --from 299 --to 400 <id>`
(mission play starts ~299 s on the survey route, per aufire412b).

## 3. Result (attempt 2, 2026-09-27)

Why attempt 1 did not finish: it ended correctly on a wait. Both soaks were
queued behind five other Nova requests and the session stopped with a
`waiting:` note; the soaks finished at 00:43 and 00:56 PDT, after it ended.
Nothing was lost. Attempt 2 reads them.

Build of the runs: 6a598c5404 on master 231d04df51, which predates PR #465, so
the #425 jump cache was OFF (HAKUX_TCG68_JC unset). It does not matter for the
answer below: the dominant returns are gen_eob exits, which no jump cache sees.

AUF, survey route, mission play 299-400 s, Nova, MAX regimen.
B = `1790477867-retreason425-2004056` (counters), A = `1790477870-retreason425-2004282` (master).
fps 17.82 (B) vs 17.76 (A): the counters cost nothing measurable.

| cause | returns/s | returns/frame | share |
|---|---:|---:|---:|
| e: gen_eob plain exit_tb | 28,649,427 | 1,607,997 | 99.9% |
|   of which EOB_INHIBIT_IRQ (STI) | 14,321,430 | 803,814 | 49.9% |
|   of which EOB_NEXT (the NOP in its shadow) | 14,322,774 | 803,890 | 50.0% |
|   EOB_ONLY (IRET, far jump) | 3,410 | 191 | 0.0% |
| g: goto_tb not patched (all page-spanning) | 23,907 | 1,342 | 0.1% |
| r: TB_EXIT_REQUESTED | 272 | 15 | 0.0% |
| m: lookup_tb_ptr miss | 1 | 0 | 0.0% |
| o: other | 0 | 0 | 0.0% |
| dispatches (it) | 28,681,180 | 1,609,779 | |
| interrupts taken | 1,353 | 76 | |

Top returning pcs: `e 8001b02e fb9090` 49.94% and `e 8001b02f 9090fa` 49.94%
(`sti; nop; nop; cli`), then nothing above 0.07%. Checks: d <= x ok, m = hm
(115), gs+gi+ga <= g ok, pcdrop 3 of 2.87e9 (negligible).

**Reading.** The returns are not a translator or jump-cache cost. They are the
guest kernel's idle loop: `sti; nop; nop; cli; <test>; jz` at 0x8001b02e,
NT's idle idiom. Each iteration returns twice (the STI TB, then the lone NOP in
its shadow) and the rest chains, so ~14M iterations a second. Over the run the
idle share per 2 s window is ~0 in the menus (w10-w50) and 50% of returns per
side from w60 on: mission play is when the vCPU goes idle.

So the 54% "exec loop between TBs" in #412's profile, and slowdown462's
AUF 42 ms/frame, is the vCPU **waiting**, not work. Making returns cheaper
(chaining across the STI shadow, a faster barrier) spins the idle loop faster
and moves fps by 0. The bound on the vCPU's own work: the busiest idle window
ran 32.0M dispatches/s, the mission average 28.7M/s, so the idle loop takes
between 54% (the profile) and ~90% (28.7/32.0, if the peak window was pure
idle) of vCPU time. At 17.8 fps (56 ms) the vCPU's real work is at most
~26 ms/frame: AUF mission play is not vCPU-bound on the Nova. That is a bound,
not a value.

Falsifier (counted returns vs the profile's share): 28.7M returns/s at the
profile's 54% implies ~19 ns of loop per return, and the whole vCPU second
bounds it at 35 ns (1 s / 28.7M). 19 ns sits inside that; the counter is
consistent. The counter's own timing leg is not: `gapus + tbus` came to ~4x
the wall clock (the 1-in-64 sample charges its two get_clock() calls and is
scaled by 64). The reader now prints `timed <= wall: INVALID`; no cost in this
file comes from `gapus`/`tbus`.

## 4. The fix for the dominant reason: HAKUX_IDLE_HLT (d259abab29)

**Removed from the tree in attempt 4 (section 7): it wedged AUF at boot
(section 6). d259abab29 keeps it in history.** Default off. With `HAKUX_IDLE_HLT=1`, after the STI return at P (bytes
`fb 90 90 fa`, verified once per pc) and the EOB_NEXT return of the NOP in its
shadow at P+1, if `cpu_has_work()` is false the vCPU does what helper_hlt does:
`halted = 1`, EXCP_HLT, cpu_loop_exit. The interrupt wakes it and is taken at
the second NOP, where the spinning loop would have taken it. One vCPU and only
interrupts change what the idle loop tests, so the guest cannot tell the
difference except by time. `[rr425] ih=` counts the halts.

What it can move: the spinning vCPU holds a big core at 100% on the Nova. A
halted vCPU frees that core (and its power/thermal budget) for the GPU and
render threads. Whether that moves fps is exactly what the A/B asks; the risk
is interrupt latency (a condvar wake instead of a spin). No fps number is
claimed before it lands.

Compile-checked with the NDK arm64 Release line (`typecheck_rr.py`): no new
warnings.

| arm | ref | env | request id |
|---|---|---|---|
| AUF A (pilot) | d259abab29 | none | `1790515915-retreason425-1213003` |
| AUF B (pilot) | d259abab29 | HAKUX_IDLE_HLT=1 | `1790515918-retreason425-1213231` |
| pixels must-not-move, 8 suites | f131dd11c6 vs d259abab29 | | `retreason425-idlehlt-inert.json` (arms job) |

Next, only after the pilot is read: Blinx and Blinx 2, one title at a time,
Nova, MAX. Their A arms also carry `[rr425]`, which says whether their
exec-loop share is the same idle loop before any B is judged.

## 5. Waiting (2026-09-27, attempt 2)

The split has been posted to #425, #412 and #462. The PR body is current and preflight passes on
d1fab17eb0. Waiting on two things outside this session: the AUF pilot
`1790515915-retreason425-1213003` / `1790515918-retreason425-1213231`
(queued on the Nova behind titleroutes and lanelocal), and the arms job's
verdict on `retreason425-idlehlt-inert.json`. Next: read the pilot with
`rr425.py --from 299 --to 400` on both ids (fps and `ih`), and write
`pilots/retreason425.ok`. If B has halts and fps is not worse, queue Blinx, then Blinx 2
(A off / B on, same ref, Nova, one title at a time). Report ms/frame and fps
on #425 and #462.

## 6. The idle-halt pilot: B wedged the guest at boot (attempt 3)

Why attempt 2 did not finish: it ended correctly, waiting on the pilot and the
arms verdict (both outside the session). Both have come back.

| arm | request | build | result |
|---|---|---|---|
| A, flag off | `1790515915-retreason425-1213003` | d259abab29 (has #465, JC on) | ran; mission ~15 fps (gfps 13-16, G ~62 ms); 398 `[rr425]` windows |
| B, `HAKUX_IDLE_HLT=1` | `1-1790515918-retreason425-1213231` | d259abab29 | **wedged at boot**: `env: HAKUX_IDLE_HLT=1` logged, then no `[rr425]` line, no `gfps` line, `refresh ... flip=0 ... no nv2a fb` for all 400 s |
| pixels must-not-move | `retreason425-idlehlt-inert.json` | f131dd11c6 vs d259abab29 | PASS, 593 checks (flag off by default) |

Arm A with the #465 jump cache on (the overnight split runs were built before
#465 folded, on 6a598c5404) gives the same split: `8001b02e sti` and
`8001b02f nop` at 49.72% each of all returns, 3.36e9 of each over 400 s, and
`hm` (lookup misses) 29,729 in total. The jump cache does not touch the idle loop's
returns, as expected: they are gen_eob plain exits, not lookups.

B stopped inside the first 2 s `[rr425]` window, so the vCPU halted in an
early idle window and nothing woke it. With one vCPU, a halt that no interrupt
ends is a deadlock. Unverified candidates, for the next lane: (a) the first
`fb 90 90 fa` STI the guest runs is an early-boot idle before the PIT/PIC are
live, so no interrupt ever comes; (b) halting from `rr425_book` (after the TB
has returned, outside helper context) leaves state that `cpu_handle_halt`
does not expect; (c) a hakuX interrupt source that sets `interrupt_request`
without kicking a halted vCPU. The only direct `qatomic_or` on
`interrupt_request` in hw/, system/ and target/i386 is `system/cpus.c:260`
(the generic `cpu_interrupt` path), which argues against (c).

**Verdict.** No fps number for the lever: the B arm has none. The flag stays
default off and pixels-inert (arms PASS). Blinx and Blinx 2 were not queued:
the pilot's purpose was to show a halt that wakes, and it does not.

**The finding stands without the lever.** The exec-loop share that
slowdown462 books as 42 ms/frame (AUF), 21.7 (Blinx) and 13.5 (Blinx 2) is,
on AUF, the guest idling. Chaining or cheapening those returns moves fps by
0. On AUF the most a halt could gain is freeing a host core; the vCPU's own
work is at most ~26 ms of the frame, which is a bound. The Blinx titles'
split is unmeasured: run an A arm with `[rr425]` on each before any lever is
priced for them.

Do not repeat: pricing a return-path lever (jump cache, EOB chaining, barrier)
against the exec-loop share of a title before its `[rr425]` top pcs have been
read. If they are `sti; nop` pairs, that share is idle time.

## Files outside this lane

None edited. cputlb.c / tb-maint.c / tb-internal.h untouched; the `[rr425]`
line needs no dispatcher allow-list change (tag `hakuX` at W).

## 7. What wakes the idle guest: `[rr425w]` (attempt 4)

Why attempt 3 did not finish: it did. It recorded the pilot (section 6) and
ended; then job.cloud's audit pass 1 (`docs/audits/2026-09-27-retreason425-pass1.md`,
needs-remediation, M1) and lane.local's 08:48 PDT addendum arrived: find what
the idle guest waits for, park HAKUX_IDLE_HLT, run Blinx and Blinx 2.

Audit answers:
- **M1 (fixed):** the idle-halt path is gone (`idle_hlt_*`, the `getenv`,
  `RR_IH` and `ih=`). No `HAKUX_IDLE_HLT` remains in the tree.
- **L1 (decided):** the counters stay always-on in XBOX builds until #425
  and #412 close, as `[jc425]` does; the AUF fps A/B measured no cost
  (17.82 vs 17.76). Whoever closes #412 removes them with `[jc425]`.
- **L2, L3:** moot for the halt. The new idle detector re-reads the window's
  bytes in every 2 s window and never caches a failed read.

The counter (e156fcdf02, three files):
- `accel/tcg/cpu-exec.c`: an idle stretch starts at the STI return of the
  `fb 90 90 fa` window and ends when `cpu_handle_interrupt` takes an
  interrupt. Each wake is keyed by vector and by which NV2A units had an
  enabled interrupt pending; the busy period it starts (to the next idle
  entry) is charged to the same key. Per key and 2 s window: wakes, idle us,
  busy us, idle-length and busy-length histograms, and `nb` (the same key
  taken while busy). One `[rr425w]` line per window, after `[rr425pc]`.
- `target/i386/tcg/system/seg_helper.c`: stores the PIC vector in
  `hakux_rr425_vec` (one line, XBOX only).
- `hw/xbox/nv2a/nv2a.c`: `hakux_nv2a_irq_units()`, read-only: PFIFO,
  PCRTC (vblank), PGRAPH, and PGRAPH's NOTIFY / CONTEXT_SWITCH /
  BUFFER_NOTIFY / ERROR / other.
- Reader: `rr425.py` prints idle and busy ms/frame by wake key, labels the
  vector as IRQ (vector - 0x30, the Xbox kernel's mapping), and checks
  idle + busy against the wall clock of the span (5%); that check is this
  counter's falsifier. `--selftest` covers a passing and a failing span.
- Compile-checked with the NDK arm64 Release line (`typecheck_rr.py`, now
  four TUs): no warnings on the new lines.

How to read it: a wake whose busy period is short (<20-200 us) is an ISR that
went straight back to idle (the 1 kHz PIT tick). A wake followed by a long
busy period readied a thread; that key is what the guest was waiting for.
Idle ms/frame by the key of the stretch's end says how long it waited.

| run | ref | request id |
|---|---|---|
| AUF, survey, 420 s, Nova, perflog MAX | e156fcdf02 | `1-1790524520-retreason425-202048` |
| Blinx, same | e156fcdf02 | `1-1790524520-retreason425-202137` |
| Blinx 2, same | e156fcdf02 | `1-1790524520-retreason425-202197` |
| pixels must-not-move, 8 suites | 6e4dee6a28 vs e156fcdf02 | `retreason425-wake-inert.json` (arms job) |

Read with `python3 docs/lanes/retreason425/rr425.py --from 299 --to 420 <id>`
(AUF); for the Blinx titles read the windows after the route's `mark play`.

### Waiting (attempt 4, 2026-09-27 09:05 PDT)

On the three `[rr425w]` soaks above (queued at priority 1 behind seven
requests) and the arms job's verdict on `retreason425-wake-inert.json`. The
index regeneration for the nv2a.c accessor is a6a12af6bf; preflight passes.
Next: read each soak with `rr425.py`; name the wake key with the long busy
periods per title, its idle ms/frame, and its owner (#474 for PFIFO waits
and pacing); check the Blinx titles' `[rr425pc]` for `sti; nop`; post on
#425 and #462; then mark #460 ready.

## 8. The wake split, read (attempt 4, resumed 2026-09-27 09:55 PDT)

Why the previous session did not finish: it ended correctly on a wait for the
three soaks and the wake arm, all outside the session. The soaks finished at
09:54, 10:08 and 10:15 PDT. The arm (`retreason425-wake-inert.json`) was still
queued when this was written.

All three on the Nova, e156fcdf02 (apk 28f7987cf5ab, perflog, MAX regimen,
survey route, 420 s). Windows: AUF 299-420 s (mission play, as before); the
Blinx titles `mark play` + 10 s to 10 s before the end, checked against the
route's `play` shots (Blinx: first level, timer running; Blinx 2: "Locate
the 3 balloons"). Read with `rr425.py --from A --to B <id>`; the last table it
prints ("wake source") is the one below.

| | AUF | Blinx | Blinx 2 |
|---|---:|---:|---:|
| request `1-1790524520-retreason425-` | `202048` | `202137` | `202197` |
| window, s | 299-420 | 255-411 | 251-411 |
| fps / ms per frame | 14.96 / 66.9 | 17.32 / 57.7 | 28.54 / 35.0 |
| VBLANKs per flip (median `Vpf`) | 3.88 | 2.74 | 2.01 |
| returns on `8001b02e sti` + `8001b02f nop` | 99.86% | 99.84% | 99.90% |
| vCPU idle, share of wall | 65.1% | 52.5% | 65.6% |
| idle, ms/frame | 43.5 | 30.3 | 23.0 |
| busy, ms/frame | 23.4 | 27.4 | 12.1 |
| check: idle + busy vs wall (5%) | ok | ok | ok |

What starts the guest's work. A busy period of 2 ms or more is a thread that
was readied; an ISR that returns to idle is under 0.2 ms.

| wake source | AUF busy ms/f (share) | AUF share of >=2 ms periods | Blinx busy | Blinx >=2 ms | Blinx 2 busy | Blinx 2 >=2 ms |
|---|---:|---:|---:|---:|---:|---:|
| PGRAPH ERROR (push-buffer callback) | 17.64 (75.5%) | 84.6% | 25.42 (92.8%) | 95.8% | 10.81 (89.6%) | 96.3% |
| NV2A vblank | 3.35 (14.4%) | 10.0% | 1.11 (4.0%) | 2.4% | 0.68 (5.7%) | 2.1% |
| PIT timer | 2.11 (9.0%) | 5.2% | 0.35 (1.3%) | 0.8% | 0.16 (1.4%) | 0.5% |
| USB | 0.24 (1.0%) | 0.3% | 0.50 (1.8%) | 0.9% | 0.40 (3.3%) | 1.1% |
| APU, IDE | 0.01 | 0.1% | 0.03 | 0.1% | 0.00 | 0.0% |
| PGRAPH NOTIFY, PFIFO, CTXSW, BUFFER_NOTIFY | never pending at a wake | | never | | never | |

| per frame | AUF | Blinx | Blinx 2 |
|---|---:|---:|---:|
| PGRAPH ERROR interrupts taken | 1.97 | 14.66 | 2.30 |
| busy periods >= 2 ms, all sources | 0.87 | 1.22 | 1.00 |
| idle per such period, ms (derived: all idle / their count) | 50.0 | 24.9 | 23.0 |
| PIT ticks that end an idle stretch | 43.5 | 30.6 | 23.3 |
| idle booked to those PIT ticks, ms | 40.4 | 26.6 | 18.1 |

**Reading.**
- The three titles idle in the same kernel loop (`sti; nop; nop; cli`), so
  slowdown462's exec-loop rows for Blinx (21.7 ms) and Blinx 2 (13.5 ms) are
  idle time too, as AUF's 42 ms is.
- The event that readies the guest's frame work is the PGRAPH ERROR
  interrupt. In this tree that interrupt has one source: `NV097_NO_OPERATION`
  with a non-zero parameter (pgraph.c, `DEF_METHOD(NV097, NO_OPERATION)`),
  the push buffer's software callback. The puller raises it when it reaches
  the marker the guest wrote, and then stalls (`waiting_for_nop`) until the
  guest clears it. So the guest submits its frame, sleeps, and is woken when
  the emulated GPU has consumed the push buffer up to the marker. **The
  frame is set by how late that callback arrives**, which is the PFIFO
  thread's progress through the frame (flip stall on VBLANK included).
- The 1 kHz PIT ends most idle stretches and readies nothing (its busy
  periods are under 20 us in 75-98% of wakes). It chops the wait into 1 ms
  pieces, which is why idle time by key does not name the waited-for event
  and the source of the long busy periods does.
- Blinx 2 is at its 2-VBLANK cap (92% of flips take 2 VBLANKs, 8% take 3):
  its 23 ms of idle is the title's own pacing, and no lever moves it in this
  scene. AUF (70% of flips take 4 or more) and Blinx (42% take 2, 36% take 3,
  22% take 4 or more) are above the cap, so their callback is late.

**Notifier and semaphore polling (the 09:54 PDT question).** Not on these
titles, as far as this counter sees:
- A spinning poll keeps a thread runnable, and the kernel's idle loop runs
  only when none is. The vCPU is in the idle loop 52-66% of the time.
- A sleeping poll (a timed wait between reads) would start its work on a
  timer tick. Timer-started busy periods of 2 ms or more are 5.2% (AUF),
  0.8% (Blinx) and 0.5% (Blinx 2) of all such periods. A timeout fallback
  for a notifier hakuX never writes would look the same, so that is also
  the ceiling on frames started by a timeout.
- No wake had PGRAPH NOTIFY, BUFFER_NOTIFY or PFIFO pending.
- What the counter cannot see: what the woken thread reads after the
  callback. A thread that is woken by the callback and then reads a
  semaphore or notifier location is booked as the callback's busy period.
  AUF's PIT row also has 1.05 busy periods of 0.2-2 ms per frame (16 a
  second): a timer-driven thread whose work is under 2 ms a frame. What it
  does is unread.

**Bounds, not values.** With no wait at all the frame is at least the
guest's own work and the GPU's: AUF 23.4 ms busy and `GPU Tot` 29.3 ms, so
<= 34 fps and <= 30 at 2-VBLANK pacing; Blinx 27.4 ms busy and 20.5 ms GPU,
so <= 30 fps at 2-VBLANK pacing. Blinx 2 has no bound above its cap. The
perflog build's PFIFO wall time per frame (`Push`, medians) is 56.0 ms (AUF),
40.1 (Blinx), 30.3 (Blinx 2); these are wall time with a clock read around
every method, upper bounds on cost (slowdown462, "Do not repeat").

**Owner.** The wait belongs to the PFIFO thread's latency, not to the vCPU
or the exec loop: #474 (the PFIFO thread's own waits; flip474's "next lever")
and #488 (semaphore and notifier latency, 13.8 ms after the last kick against
2.7 us on silicon). #425's return path is not a lever for these three
titles. `HAKUX_IDLE_HLT` stays parked: it frees a host core at most.

**Not measured, and the next measurement.** Which callback it is (the NOP's
parameter: flip, fence, read or write callback), and the time from the
guest's kick that covers the marker to the puller reaching it. Both belong
in the puller (pgraph.c `NO_OPERATION`, pfifo.c), outside this lane's files:
a histogram of the parameter, and kick-to-callback latency split by what
the puller waited on in between (flip stall, finish, download). Blinx takes
14.66 callbacks a frame against AUF's 1.97, so the parameter mix differs by
title.

**Known defects of the reader's checks.** `pcdrop == 0` prints FAIL at 3, 151
and 224 dropped pc samples of ~3e9; it affects only the top-pc counts, by
under 1e-7. `timed <= wall` is INVALID as in section 3; nothing here uses
`gapus`/`tbus`.

Do not repeat: reading idle ms by wake key as "what the guest waits for".
The PIT takes 79-93% of the idle time on every title and readies nothing.

### State at the end of this session

Master is merged (576b4b6faf; the only conflict was `nv2a_index.json`,
rebuilt over the pinned trees in aae68b4aed) and the four TUs compile with
the NDK arm64 line. The result is posted on #425, #462 and #412.
