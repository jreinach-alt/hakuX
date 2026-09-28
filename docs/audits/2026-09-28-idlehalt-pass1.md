# Audit pass 1: PR #528 (lane/idlehalt)

PR: #528, "lane.idlehalt: halt the vCPU in the guest idle loop (#525)"
Head audited: cee0e5f3cb (merge base with master 96263a8f9c)
Scope: the diff against master. Code: `target/i386/tcg/translate.c`,
`target/i386/tcg/system/misc_helper.c`, `target/i386/helper.h`,
`system/cpus.c`, `accel/tcg/tcg-accel-ops.c`, `accel/tcg/tcg-accel-ops-rr.c`,
`include/hw/core/cpu.h`. Also five predictions under
`docs/testing/predictions/idlehalt-*.json` and the lane tools under
`docs/lanes/idlehalt/`. CI (`build`, both runs) is green on the head. The
PR's `Files:` line matches the diff's 17 paths.

Verdict: **no HIGH, no MEDIUM, four LOW. needs-audit-2.**

## What the change does

1. With `HAKUX_IDLE_HALT=1`, the translator recognises the TB that starts in
   the `sti` shadow of `fb 90 90 fa` (ring 0, 32-bit PM, no TF/RF, all four
   bytes on the first page). It emits one TB holding both nops. The TB sets
   EIP to the `cli` and calls `helper_hakux_idle_hlt`. With IF = 1 and the
   halt armed (the PIT, vector 0x30, has been taken once), the helper does
   `helper_hlt`'s work: `do_end_instruction`, `halted = 1`, `EXCP_HLT`.
   Otherwise it returns, and the TB ends as two nops.
2. In `qemu_process_cpu_events` (MTTCG) and `rr_wait_io_event`
   (`thread=single`), the halt wait goes through `hakux_idle_halt_wait`.
   For a real `hlt` that is QEMU's unbounded `qemu_cond_wait`. For an idiom
   halt it is a 1 ms `qemu_cond_timedwait`, optionally preceded by a spin of
   up to `HAKUX_IDLE_HALT_SPIN_US` (capped at 1000) without the BQL. A timeout
   with no work un-halts the vCPU, which runs the loop again.
3. `tcg_handle_interrupt` reports the first HARD kick of each idiom halt,
   classed by pending NV2A unit. There is an `[idlehalt]` line every 2 s,
   halt on or off.

## Checked and found sound

- **No lost or early interrupt at the idiom.** The shadow TB is entered with
  `HF_INHIBIT_IRQ`, so a pending IRQ is not taken at its start, just as in
  the stock one-insn shadow TB. The helper's `do_end_instruction` clears the
  inhibit before halting. A pending HARD IRQ with IF = 1 makes
  `cpu_has_work` true, so the thread does not wait, and `cpu_handle_halt`
  un-halts it. The IRQ is then taken with EIP at the `cli`, which is where
  the spinning loop takes it. When the helper returns (not armed), `gen_eob`
  resets `HF_INHIBIT_IRQ` because `s->flags` carried it
  (`translate.c:2922`), so the TB at the `cli` is not in a shadow.
- **EIP and cc_op at the helper.** `dc->pc = pc_next + 2`,
  `gen_update_cc_op`, and `gen_update_eip_next` before a
  `DEF_HELPER_1` (globals synced) call match stock `hlt`'s translation. So
  `cpu_loop_exit` from the helper needs no restore. `pc_first` indexes
  `host_addr[0]` (the host pointer for `pc_first`, not the page start), so
  `h[-1]` is the byte before, and `off >= 1` keeps it on the page. A NULL
  host page (code from MMIO) is refused.
- **Wake ordering across the spin.** `hakux_idle_halt_kick` runs under the
  BQL and publishes `ih_kick_ns` with a full barrier before `qemu_cpu_kick`.
  A kick after the spin's last poll is either seen by `cpu_thread_is_idle`
  under the retaken BQL or signals the condvar wait that follows. No wake is
  lost.
- **`qemu_cond_timedwait` return sense.** It returns true when signalled.
  The code returns false (loop re-tests) on a signal. It un-halts only on a
  timeout with `halted`, `ih_on`, and no work.
- **The default-off path.** `hakux_idle_idiom` returns false unless enabled.
  Then `ih_on` is never set, `hakux_idle_halt_kick` returns at once, and
  `hakux_idle_halt_wait` is exactly `qemu_cond_wait(cond, &bql)` (what
  `qemu_cond_wait_bql` does, for the rr path too). The only default-off cost
  is `ih_tick`: one `get_clock()` per pass and a schedstat read plus a log
  line every 2 s. The pixels prediction (8 suites, 593/593) covers
  rendering on the flip ref.
- **Shared state.** The Xbox has one vCPU. Every `ih_*` write outside the
  kicker is on the vCPU thread (translation, the helper, the wait,
  `ih_tick`). The kicker writes only `ih_kick_class` and `ih_kick_ns`, under
  the BQL, which the vCPU holds when it reads them in `ih_wake`.
- **`ih_tick`'s buffers.** Counters reset every 2 s, so the `wk` string
  (5 x " name=N") stays far under 128 bytes. See LOW 4 for the unguarded
  worst case.

## Findings

### LOW 1: a stale `ih_on` can bound a real `hlt` (opt-in, needs a narrow race)

`system/cpus.c` `hakux_idle_halt_after_wait` clears `ih_on` only when the
pass ends with `!halted || cpu_has_work`. The wait loop can exit with the
vCPU still halted and idle because of `cpu->stop` or a queued
`run_on_cpu`. If a kick then lands before `tcg_cpu_exec`,
`cpu_handle_halt` un-halts the vCPU inside `cpu_exec`, and the guest runs
with `ih_on` still true. If that slice executes a real `hlt`, the next wait
takes the bounded branch. After 1 ms with no IRQ, the timeout clears
`halted` and the guest resumes past the `hlt` with no interrupt taken. The
same stale state makes the vCPU wake every 1 ms (not unboundedly) while the
VM is stopped with `halted == 0` and `ih_on` set. Failure scenario: with
`HAKUX_IDLE_HALT=1`, a title that uses `hlt` gets an early return from one
`hlt`, when a stop request or async work races the idiom halt's wake.
Architecturally that is a spurious wake; loops that re-test are unaffected.
Default off, and the race needs two events in one pass, so LOW. A fix is
cheap: clear `ih_on` whenever `cpu->halted` is found 0, or tag the halt so
`hakux_idle_halt_wait` takes the bounded path only when
`cpu->exception_index`/PC match the idiom.

### LOW 2: the idiom match depends on bytes outside the TB's range

`hakux_idle_idiom` reads `h[-1]` (the `sti`) and `h[2]` (the `cli`), but
the TB covers only the two nops. A write to either neighbouring byte that
does not overlap the TB's range leaves a TB that still halts. Failure
scenario: code at that page is overwritten so that the byte before the nops
is no longer `sti`. The stale TB then adds a halt of up to 1 ms (or until
the next IRQ) at a non-idle `nop; nop` that runs in ring 0 with IF = 1.
Semantics otherwise stay correct (EIP lands after the two nops). `xpc`
would count it. The retail kernel's idle loop is not rewritten, so LOW.

### LOW 3: `slept_us` includes spin time

With `HAKUX_IDLE_HALT_SPIN_US > 0`, `ih_wake` and the timeout path add
`now - ih_t0` to `slept_ns`, and `ih_t0` is before the spin. So `slept%`
counts on-CPU spinning as sleep. `ihread.py` prints `spinning` beside it,
but a reader comparing `slept%` between the B and C arms of
`idlehalt-spin-*.json` would read the spin as extra idle. Failure scenario:
C at 100 us shows a higher `slept%` than B for the same guest idle, and it
is read as the spin "sleeping more". Subtract `spin_ns` in the reader, or
document it on the line.

### LOW 4: `ih_tick`'s `wk` offset is unguarded

`off += snprintf(wk + off, sizeof(wk) - off, ...)`: if the total ever
exceeded 128 bytes, `sizeof(wk) - off` would wrap to a huge `size_t`, and
the next `snprintf` would write past `wk`. That needs per-class counts of
about 10^19 inside one 2 s window, which cannot happen. It is quality only:
clamp `off`, or print the five counters in one format string as the rest of
the line does.

## Not findings

- The `[idlehalt]` line prints every 2 s on every build, stderr included on
  desktop. That is intentional and documented, so the A arm reads the same
  host columns.
- `idlehalt-auf/blinx/spin-*.json` are same-ref env pairs, which the PR
  says the arms job refuses. They were run through request.sh and judged by
  `ihread.py`. That is a process note, not a defect in the diff.
- The halt stays default off because leg L fails. That is the PR's own
  finding and is correctly reflected in the code (`ih_enabled` needs
  `HAKUX_IDLE_HALT=1`).

## For pass 2

Nothing is HIGH or MEDIUM. Pass 2 should check whether LOWs 1 and 3 were
addressed or explicitly deferred in NOTES. None of them blocks a fold of a
default-off change.
