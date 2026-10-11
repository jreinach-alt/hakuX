# hitchcause: the MTV 330 ms hitches are guest-side waits, not the IDE host read ([ide425d] held run on af37f7a3ea) (#433)

State: ready

Lane: hitchcause            Issue: #433 (0.5: 50 Playable); #819 (the tracker row)
Base: origin/master @ d32c35d3ce (merged)
Files: docs/lanes/hitchcause/NOTES.md, docs/lanes/hitchcause/OUTBOX.md, docs/lanes/hitchcause/PR.md, docs/lanes/hitchcause/hitchwin.py, docs/lanes/hitchcause/blockread.py, docs/lanes/hitchcause/ide_wake.py, docs/lanes/hitchcause/rr_split.py, docs/lanes/hitchcause/pc_exits.py, docs/lanes/hitchcause/g_conc.py, docs/lanes/hitchcause/ide425_windows.py, docs/lanes/hitchcause/capture_mtv_ide425.sh, hw/ide/core.c, hw/intc/i8259.c
Prediction: none: telemetry only (no pixels move)
Needs device: yes (done: smoke 1-1791210904-lane.hitchcause-2015470 on af37f7a3ea, DONE; one 700 s MTV hold on af37f7a3ea, released 15:44:29 UTC)    Needs NDK: no

Release note (none): instrumentation only; the `[ide425]`, `[ide425d]` and `[pic14]` window lines change no behaviour.

## What I found

- IRQ14 is the IDE device, and the MTV bursts are DMA (zero PIO reads; `[pic14]`
  edges equal the IDE model's raises, never masked).
- The held run on af37f7a3ea (`[ide425d]`) shows two 330 ms hitches (08:39:36,
  08:44:03 PDT) in IDE bursts of about 547 DMA commands per 2 s. Host DMA per
  command is about 40 µs, device time about 40 µs in total per window, and the
  guest's gap between an IRQ and its next command is 98% of the window.
- The vCPU was busy 98% of each window with `halts=0`, and its hot PC is the
  guest's idle loop. Lock wait is 0.1 ms and the PFIFO drain is under 17 ms.
  So the 330 ms is a guest-side wait on a guest event, not a host stall and not
  the device. Section 12's rule picks (a), and the vCPU counters agree.
- Not separable here: the 215 and 251 ms hitches (no burst in their windows).
  Orta has one 300-plus window and no `[ide425d]` line, so "harness-wide" is
  not claimed.

## Deviation from the 10-05 addendum (lane.local to confirm)

The addendum named `REF=d4b0169ab2`. The earlier session built `af37f7a3ea`
(adds `[ide425d]`), which is a second build beyond "one build". This session
did not build again; the hold ran on the existing smoked APK. On
`d4b0169ab2` the hold could not separate the branches.

## Checks run

- `capture_mtv_ide425.sh` (this lane's file): the route is now read from the
  lane/pathfind checkout via `PATHFIND_KNOW` (the file was not in this tree).
  No route file is copied here.
- `hw/ide/core.c`: syntax-only compile with the desktop build's flags passes.
  The full desktop build is not run (libcurl is missing on this host).
- No selftest: no harness file outside this lane changed. No CI (offline).

## Next

Ranked by P x win (NOTES section 13):

1. Guest-side attribution at a hitch: which guest task is blocked when the idle
   loop spins, and on what. P 0.6 that it names the guest event; the win is the
   whole 330 ms class (1.15/min on MTV, shared with Orta and Blood Wake). One
   build, one 700 s hold. Needs a grant: it touches the title's guest-trace hooks.
2. Host preemption check (`[rr425w]` busy against the host scheduler): P 0.2 that
   any of the class is host-side. One build.
3. DVD read-ahead or batching: P 0.05, because the device answers in 0.3 ms.
   Not recommended.
