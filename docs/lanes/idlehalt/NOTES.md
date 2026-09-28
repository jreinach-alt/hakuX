# lane.idlehalt (#525): halt the vCPU in the guest kernel's idle loop

Read first: `docs/lanes/retreason425/NOTES.md` sections 6-8 (the loop, its
cost, what wakes it, and the failed `HAKUX_IDLE_HLT` pilot).

## 1. What is built (056eea9aaf)

Opt-in, default off: `HAKUX_IDLE_HALT=1`.

| piece | file | what it does |
|---|---|---|
| recognise | `target/i386/tcg/translate.c` `hakux_idle_idiom()` | a TB that starts in an interrupt shadow, ring 0, 32-bit PM, no TF/RF, max_insns >= 2, whose bytes at pc-1..pc+2 are `fb 90 90 fa`, all on the TB's first page, read from its host page. Bytes, not the address. |
| translate | same, `i386_tr_translate_insn` | that TB holds both nops: EIP -> the cli (pc+2), `helper_hakux_idle_hlt`, then `gen_eob(EOB_ONLY)` (clears the shadow, exits), so when the helper returns the nops stay nops |
| halt | `target/i386/tcg/system/misc_helper.c` | if IF=1 and armed: `do_end_instruction`, `halted = 1`, `EXCP_HLT`, `cpu_loop_exit`: helper_hlt's path, from helper context (the pilot's candidate (b) avoided) |
| arm | `system/cpus.c` `hakux_idle_halt_enter` | only once the last interrupt taken was vector 0x30 (the PIT) (candidate (a)) |
| bounded wait | `system/cpus.c` `hakux_idle_halt_wait`, called from `qemu_process_cpu_events` (MTTCG, the Android default) and `rr_wait_io_event` (thread=single) | an idiom halt waits `qemu_cond_timedwait(halt_cond, bql, 1 ms)`; on a timeout with no work it un-halts the vCPU, which runs the loop once and halts again. A real `hlt` keeps the unbounded wait. |
| wake source | `accel/tcg/tcg-accel-ops.c` `tcg_handle_interrupt` -> `hakux_idle_halt_kick` | first HARD kick of each halt: time, and the NV2A units pending (`hakux_nv2a_irq_units`) |
| counter | `[idlehalt]` on tag `hakuX` (W), one per 2 s, **on or off** | `on span_us run_us rq_us halts pc xpc imm pg pgo vb fifo ot to tp tr slept_us pit lpg lpgmax lall lallmax` (field meanings: the comment above `hakux_idle_halt_enabled`, and `ihread.py`'s docstring) |
| reader | `docs/lanes/idlehalt/ihread.py` (`--selftest`) | per result: fps, vCPU run% and rq% (schedstat), guest idle from `[rr425w]`, halts/s, slept%, wakes, timeouts, raise-to-run histograms; VOID on < 20 windows, span off the wall clock, or a failed schedstat read |

Check of the reader on retreason425's AUF soak (`1-1790524520-retreason425-202048`,
299-420 s): fps 14.96 and guest idle 65.1%, the numbers section 8 printed.
That build has no `[idlehalt]` line, so the row is VOID for the rest.

Compile check: `docs/lanes/idlehalt/typecheck_ih.py` (retreason425's
NDK arm64 Release line over the seven touched TUs plus cpu-exec.c): exit 0,
no diagnostics on the new lines.

The idiom's bytes are confirmed from a live read, not a disassembler:
retreason425's `[rr425pc]` reads guest memory at the returning pcs and
printed `8001b02e fb9090` and `8001b02f 9090fa`.

## 2. Candidate (c), audited by reading (no edit)

Every path from an NV2A interrupt to the vCPU:
- `nv2a_update_irq` (nv2a.c) -> `pci_irq_assert` -> PIC -> `cpu_interrupt`,
  which does `g_assert(bql_locked())` (system/cpus.c). An unlocked raise
  would abort, not lose a wake.
- The pgraph.c raises (`NO_OPERATION` callback -> PGRAPH ERROR at
  pgraph.c:2535-2550, NOTIFY 2620-2635, CONTEXT_SWITCH 1325-1340) drop
  `pg->lock` and take `bql_lock()` around `nv2a_update_irq`. PCRTC (vblank,
  nv2a.c:935-945, 1170-1177), PFIFO, PMC and PTIMER register writes run in
  MMIO context, which holds the BQL.
- `cpu_interrupt` -> `tcg_handle_interrupt`: `cpu_set_interrupt` then, from
  another thread, `qemu_cpu_kick` -> `qemu_cond_broadcast(halt_cond)`. The
  waiter tests `cpu_thread_is_idle` (which reads `cpu_has_work`) under the
  same BQL, so a raise between the test and the wait cannot be lost.
- The only other writers of `interrupt_request` in the i386 system build
  are `cpu_set_interrupt` itself and svm_helper's VIRQ (not used here).

So (c) is refuted by the code. The counter still measures it: `tp` counts
a timeout that found work pending with no kick seen.

## 3. Proof plan and predictions

| leg | prediction | refs | how it runs |
|---|---|---|---|
| pixels | `idlehalt-pixels.json` | A 056eea9aaf (off) vs B 0ff391f8e5 (on by default) | the arms job (8 suites) |
| AUF host/fps/counters/latency/boots | `idlehalt-auf.json` | 6554f06175 both, B `HAKUX_IDLE_HALT=1` | request.sh, Nova, survey, perflog, 420 s |
| Blinx the same | `idlehalt-blinx.json` | same | same |

0ff391f8e5 only flips the default (`!v || v[0] != '0'`); 6554f06175 reverts
it, so the PR head is default off and has the same tree as 056eea9aaf. The
arms job pairs refs, not environments, which is why the pixel arm's B is a
commit.

Pilot (the 30 min gate): AUF B1 then A1. After reading them, write
`pilots/idlehalt.ok` and queue Blinx B1, A1, then B2-B5 for both titles at
300 s (boots).

## Do not repeat

- Halting from bookkeeping after a TB has returned (the old pilot).
- An unbounded wait for an idiom halt.
- Reading `[rr425w]` idle time by wake key as "what the guest waits for"
  (retreason425): the PIT ends most idle stretches and readies nothing.

## 4. Waiting (session 1, 2026-09-27 18:5x PDT)

Preflight passes on dd8a09522e. Waiting on things outside this session:
- the AUF pilot, B1 `1790559837-idlehalt-2274611` (HAKUX_IDLE_HALT=1) and
  A1 `1790559849-idlehalt-2278164`, both Nova, queued behind ~6 Nova
  requests;
- the arms job's pixel verdict on `idlehalt-pixels.json` (a `[job.arms]`
  comment on PR #528);
- CI on the head.

Next: `python3 docs/lanes/idlehalt/ihread.py --from 299 --to 420 <B1> <A1>`,
check B1 booted (gfps lines, `[idlehalt] armed`, play shots), and read the
cooling state. If B1 wedged, the halt is refuted as built: read its logcat for
the last `[idlehalt]` window (tp, to, halts) before changing anything. If it
passes, write `pilots/idlehalt.ok` (python3) and queue Blinx B1/A1, then the
B2-B5 boot runs (300 s) for both titles, per the predictions' queue_order.

## 5. Session 2 (2026-09-27 20:3x PDT): why session 1 did not finish

Session 1 ended correctly on a `waiting:` (the pilot was behind ~6 Nova
requests), but its head was red: the Desktop build failed with
`system/cpus.c: 'CPU_INTERRUPT_HARD' undeclared`. system/cpus.c is compiled
target-independent on the desktop, and nothing in its include chain there
brings in `exec/cpu-interrupt.h`; the Android build and `typecheck_ih.py`
(NDK flags) reached it transitively, so the local check could not see it.
Fixed in 6dabebe883 by including the header (it is target-independent: only
the flag `#define`s). No behaviour change, so the queued pilot APKs (built at
6554f06175) and the predictions' refs stand.

The pixel arm is in: PASS, all 593 checks (`[job.arms]` on #528, 02:43Z).

Do not repeat: `typecheck_ih.py` checks the Android TUs only; a new use of a
target header's name in a libsystem file needs the header named explicitly.

## 6. AUF B1 read (session 2, 04:20Z)

`1-1790559837-idlehalt-2274611`, Nova, 6554f06175 + `HAKUX_IDLE_HALT=1`,
survey, 420 s; `ihread.py --from 299 --to 420`:

| | B1 (halt on) | retreason425 AUF (spin, older build) |
|---|---|---|
| windows / checks | 60, all ok | n/a |
| fps | 17.05 | 14.96 |
| vCPU on-CPU (schedstat) | **26.9%** | ~94% |
| run-queue wait | 0.3% | |
| guest idle (`[rr425w]`) | 71.9% | 65.1% |
| slept | 71.5% | |
| halts/s | 1006 (xpc 0, imm 180) | |
| wakes pg / vb / ot | 3276 / 5170 / 111891 | |
| timeouts to / tp / tr | 344 / **0** / 337 | |
| pg raise-to-run >= 50 us | **14.2%** (<20: 1599, <50: 1211, <100: 392, <200: 59, >=200: 15) | |
| all kicked wakes >= 50 us | 3.6% | |

- Boot: level play in every play shot (204247-204557), `armed at 8001b031`
  20:38:50, one second after the first line. No thermal pause in
  thermal.jsonl (cpuss 53-67 C, no pause/hotplug device set).
- Legs H (<= 50%, slept within 10 points of idle), C (tp = 0, xpc = 0) hold
  on B1. F waits on A1.
- **Leg L fails as registered**: the pg callback's raise-to-run p99 is in
  the 100-200 us bin (14.2% of pg wakes at >= 50 us, not <= 1%). By the
  prediction's falsifier the halt stays default off. It is a condvar wake of
  a sleeping thread on Android (futex + scheduler + core exit from idle);
  the spin had no such cost. What it costs a frame is what leg F measures:
  ~1.6 pg wakes per frame at ~30 us median is ~0.1% of a 58 ms frame, so F
  may well hold while L fails. That would say the 50 us bound was the
  wrong threshold, but it was registered, and it is not moved after the fact.
- Next design lever for L, if the audit wants the default flipped: spin
  briefly (tens of us) on `interrupt_request` before the condvar sleep, or
  skip the halt when a PGRAPH callback is predicted (PFIFO in
  `waiting_for_nop`). Both trade some of the 67-point on-CPU drop for latency.

Pilot verdict written to `pilots/idlehalt.ok` 04:19Z. Queued the rest
(all Nova, 6554f06175): Blinx B1 `1790569178-idlehalt-3064707` (on, 420 s),
A1 `1790569178-idlehalt-3064828` (off, 420 s); boots B2-B5 at 300 s, AUF
3064914 3065084 3065236 3065340, Blinx 3065000 3065157 3065294 3065390.
AUF A1 `1790559849-idlehalt-2278164` waits behind an owner top-up hold of
the Nova (~04:45Z).

**Waiting (session 2 end, 04:2xZ):** on the ten request ids above plus AUF
A1; posted as `[lane.idlehalt] waiting:` on #528. On resume: `ihread.py
--from 299 --to 420` on each B/A pair, the boot shots of B2-B5, then legs F
and B, then post on #525 and #462.

## 7. Session 3 (2026-09-28 07:4xZ): the batch read, the verdict

Why session 2 did not finish: it ended correctly on a `waiting:` for the
device batch. The Nova dropped off adb at 23:11 PDT, partway through Blinx
A1. hostops voided that run and re-queued it as `-r2` on the Nova, and
re-pinned Blinx B2-B5 to the Thor. When the last run finished,
`job.handback` resumed this lane. There was nothing to fix, only the read.

All at 6554f06175. AUF uses `ihread.py --from 299 --to 420` and Blinx uses
`ihread.py --play` (252-418 s), each the window its prediction names:

| | AUF B1 (on) | AUF A1 (off) | Blinx B1 (on) | Blinx A1-r2 (off) |
|---|---|---|---|---|
| result | `2274611` | `2278164` | `3064707` | `3064828-r2` |
| device | Nova | Nova | Nova | Nova |
| windows, checks | 60 ok | 60 ok | 82 ok | 83 ok |
| gfps | 17.05 | 17.28 | 18.57 | 18.75 |
| vCPU on-CPU (schedstat) | **26.9%** | 95.1% | **35.5%** | 76.4% |
| guest idle (`[rr425w]`) | 71.9% | 80.1% | 40.3% | 47.6% |
| slept | 71.5% | 0 | 40.1% | 0 |
| halts/s | 1006 | 0 | 677 | 0 |
| to / tp / xpc | 344 / 0 / 0 | 0 | 218 / 0 / 0 | 0 |
| pg raise-to-run >= 50 us | **14.2%** | n/a | **3.7%** | n/a |
| thermal pause in window | none | none | none | none |

Legs:

| leg | AUF | Blinx |
|---|---|---|
| V | holds | holds |
| H | holds: A 95.1 >= 85; B 26.9 <= 43.1; slept is within 0.4 points of idle | **A fails**: A 76.4 < 85, so the spin is not ~94% on this build in Blinx. B holds: 35.5 <= 74.7, slept within 0.2 points |
| C | holds | holds |
| L | **fails**: 14.2% >= 1% | **fails**: 3.7% >= 1% |
| F | holds: 0.987 x A | holds: 0.990 x A |
| B (boots) | 5 of 5 reach level play, armed in each | 4 of 4 valid runs reach level play (B1 on the Nova, B2-B4 on the Thor). B5 (`3065390`, Thor) is VOID: the route aborted not-foreground before any input, with 5 logcat lines and no emulator start, so it is a harness abort, not a wedge. |
| heat (B at least 25 points under A) | holds: 68.2 points | holds: 40.9 points |
| J/frame | pending (#523): no power record in these results | pending |

**Verdict.** The halt frees the core: on-CPU share falls 68 points on AUF
and 41 on Blinx, with fps within 1.3%, no missed wake (tp = 0), no stray
halt (xpc = 0), and no boot wedge in 9 valid boots. Leg L is refuted in
both titles, and by the registered falsifier that keeps the halt **default
off**. This PR ships it opt-in (`HAKUX_IDLE_HALT=1`) with its counters. I
did not re-queue Blinx B5: leg L already decides the default, so a fifth
boot cannot change the outcome.

What L costs is a condvar wake of a sleeping thread (futex, scheduler, core
out of idle). On these two titles F shows no fps cost. L's 50 us bound was
a guess, but it was registered, and it is not moved after the fact.

The guest's own idle share falls with the halt on (AUF 80.1 -> 71.9, Blinx
47.6 -> 40.3). The guest is not doing more work: its wake reaches it later,
so less of the wall clock is spent in the idle loop. That matches L.

For the next lane (to flip the default):
- Spin on `interrupt_request` for tens of us before the condvar sleep, or
  skip the halt while PFIFO is in `waiting_for_nop` (a callback is coming).
  Register a new prediction with an L bound argued from F, not 50 us.
- Measure J/frame once #523's power record is in the dispatcher.
- Do not repeat: judging Blinx A against the ~94% spin figure. On this
  build it spins at 76%.
