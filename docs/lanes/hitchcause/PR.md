# hitchcause: attempt 3 adds the IRQ14 PIC-input counters; the MTV hold is still to run (#433)

State: draft

Lane: hitchcause            Issue: #433 (0.5: 50 Playable); #819 (the tracker row)
Base: origin/master @ 10f14d301d
Files: docs/lanes/hitchcause/NOTES.md, docs/lanes/hitchcause/OUTBOX.md, docs/lanes/hitchcause/PR.md, docs/lanes/hitchcause/hitchwin.py, docs/lanes/hitchcause/blockread.py, docs/lanes/hitchcause/ide_wake.py, docs/lanes/hitchcause/rr_split.py, docs/lanes/hitchcause/pc_exits.py, docs/lanes/hitchcause/g_conc.py, docs/lanes/hitchcause/ide425_windows.py, docs/lanes/hitchcause/capture_mtv_ide425.sh, hw/ide/core.c, hw/intc/i8259.c
Prediction: none: telemetry only (no pixels move)
Needs device: yes (queued: smoke 1-1791153154-lane.hitchcause-3372110 builds d4b0169ab2; then one MTV hold, pending the smoke's [pic14] lines)    Needs NDK: no

Release note (none): instrumentation only; the `[ide425]` and `[pic14]` window lines change no behaviour.

## What I found

Attempt 1 said the MTV hitches sit on IDE PIO sector-read bursts. Attempt 2
withdrew that: a 166 s MTV hold recorded zero PIO sector reads and zero
data-port words. Its one hitch (210 ms) had 200 vector-0x3e wakes against 7
IDE raises. Attempt 3 (NOTES section 11) adds the counter that can name the
source of those raises: a `[pic14]` line at the slave PIC input (commit
`d4b0169ab2`). It is telemetry only.

Attempt 2 did not finish because its hold stopped at 166 s, and the PIC
counters were not yet granted. Attempt 3 does not claim the 330 ms cause.

## Checks run

- `d4b0169ab2` is pushed; the smoke was queued on that sha.
- No selftest (the only code change is `hw/intc/i8259.c` telemetry; no
  harness file changed). No CI run (offline; GitHub suspended).
- Desktop build: not run. AGENTS.md's desktop build needs `libcurl`, not
  installed on this host. The Android build is the dispatcher's, on the smoke.

## Next

1. The smoke's `[pic14]` lines on the build (the window prints, the counts
   are non-zero in the hitch windows).
2. One 700 s MTV hold on the same build, via `capture_mtv_ide425.sh` with
   `REF=d4b0169ab2`, if the smoke shows the lines. Then compare `[pic14] edge`
   with `[ide425] irq` in the hitch windows (NOTES section 11 has the decision).
