# hitchcause: the MTV hitch bursts are not IDE PIO reads; the IRQ14 wakes have another source (#433)

State: ready

Lane: hitchcause            Issue: #433 (0.5: 50 Playable); #819 (the tracker row)
Base: origin/master @ 10f14d301d
Files: docs/lanes/hitchcause/NOTES.md, docs/lanes/hitchcause/OUTBOX.md, docs/lanes/hitchcause/PR.md, docs/lanes/hitchcause/hitchwin.py, docs/lanes/hitchcause/blockread.py, docs/lanes/hitchcause/ide_wake.py, docs/lanes/hitchcause/rr_split.py, docs/lanes/hitchcause/pc_exits.py, docs/lanes/hitchcause/g_conc.py, docs/lanes/hitchcause/ide425_windows.py, docs/lanes/hitchcause/capture_mtv_ide425.sh, hw/ide/core.c
Prediction: none: telemetry only (no pixels move)
Needs device: yes (done: one build, two smoke runs, one MTV hold)    Needs NDK: no

Release note (none): instrumentation only; the `[ide425]` window line changes no behaviour.

## What I found

Attempt 1 said the MTV hitches sit on IDE PIO sector-read bursts. This run
withdraws that. A 166 s MTV hold with a `[ide425]` window line in `hw/ide/core.c`
(branch build `b559c094eb`) recorded **zero PIO sector reads and zero data-port
words** in all 23 windows. Its one hitch of 100 ms or more (210 ms at 15:22:26)
has 200 wakes on vector 0x3e in its span, while the IDE model raised 7
interrupts in its 7 s window. So the wakes are not the IDE device's
per-sector interrupts. The 330 ms hitches of the 10-04 hold did not recur in
166 s of play, so their cause is not separable yet.

The hold ended early: pathfind's play went to the main menu for 13 steps and
stopped at 166 s. That is the only held run this lane made; the brief's second
hold is not queued (see the next step).

## Table (full in NOTES.md section 10)

| run | what | result |
|---|---|---|
| 1-1791150826 | smoke, 805cb8054f, per-command line, 120 s | no `[ide425]` line: no PIO command began |
| 1-1791151242 | smoke, b559c094eb, window line, 150 s | 24 windows; boot bursts of 552 IDE raises per 2 s with no PIO |
| hold (capture_mtv_ide425.sh) | pathfind 5454000B, `--state any` | FAIL: 166 s of play; 23 windows; one 210 ms hitch with 200 vector-0x3e wakes and 7 IDE raises |

## Checks run

- The build is the dispatcher's `b559c094eb-perflog.apk`, checked to contain
  the `[ide425] win_us` string; smoke 2 and the hold ran that APK. Smoke 1 ran
  the earlier per-command build `805cb8054f-perflog.apk`.
- `ide425_windows.py` on the hold's logcat: 23 windows, 160 pace lines.
- No selftest (no harness file changed). No CI run (offline; GitHub suspended).
  No emulator behaviour changed; the only code change is the logging in
  `hw/ide/core.c` (one IRQ-path counter, the word-time wrapper, one write
  counter).

## Next

1. **A grant for `hw/intc/i8259.c`**: count the raises on IRQ14 at the PIC
   input, tagged by caller, per 2 s next to `[rr425w]`. P 0.7 that it names the
   source (the 200 wakes vs 7 raises says the source is not the IDE model).
   Win: the 330 ms class, if that source is what the hitch waits on (14 hitches
   in 689 s on 10-04). Cost: one build (with the `hw/ide` counters of
   NOTES section 10, candidate B, which is already in this lane's grant), one
   2-minute smoke.
2. **The owner's decision on a second MTV hold** of 700 s, on that build. P 0.5
   that it reproduces the class. Only way to test item 1 against the hitches.
3. Withdrawn: read-ahead of PIO sectors (P 0.05 with no PIO reads seen) and
   batching the PIO data port (P 0.02).
