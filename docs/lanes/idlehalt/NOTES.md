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
