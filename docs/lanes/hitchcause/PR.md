# hitchcause: MTV hitch bursts are IDE DMA (IRQ14 confirmed at the PIC); [ide425d] times the DMA path before the one MTV hold (#433)

State: draft

Lane: hitchcause            Issue: #433 (0.5: 50 Playable); #819 (the tracker row)
Base: origin/master @ d32c35d3ce (merged)
Files: docs/lanes/hitchcause/NOTES.md, docs/lanes/hitchcause/WAITING, docs/lanes/hitchcause/OUTBOX.md, docs/lanes/hitchcause/PR.md, docs/lanes/hitchcause/hitchwin.py, docs/lanes/hitchcause/blockread.py, docs/lanes/hitchcause/ide_wake.py, docs/lanes/hitchcause/rr_split.py, docs/lanes/hitchcause/pc_exits.py, docs/lanes/hitchcause/g_conc.py, docs/lanes/hitchcause/ide425_windows.py, docs/lanes/hitchcause/capture_mtv_ide425.sh, hw/ide/core.c, hw/intc/i8259.c
Prediction: none: telemetry only (no pixels move)
Needs device: yes (queued: build+smoke 1-1791210904-lane.hitchcause-2015470 of af37f7a3ea; then one MTV hold)    Needs NDK: no

Release note (none): instrumentation only; the `[ide425]`, `[ide425d]` and `[pic14]` window lines change no behaviour.

## What I found

Attempt 1 said the MTV hitches sit on IDE PIO sector-read bursts. Attempt 2
withdrew the PIO part (zero PIO sectors, zero data-port words in a 166 s hold)
and, wrongly, the IDE part: its 200-wakes-vs-7-raises came from the
`[ide425]` window closing on the burst's first IRQ. Attempt 3 added `[pic14]`
(d4b0169ab2). Its smoke shows PIC pin-14 edges equal to the IDE model's raises
(537 vs 546), never masked. So IRQ14 is the IDE device, and the bursts are
DMA. Attempt 4 adds `[ide425d]` (af37f7a3ea): DMA-to-IRQ, command-to-IRQ,
IRQ-to-next-command and drain time per 2 s. These decide the brief's (a) guest
work against (b) host read. NOTES section 12 has the tables and the decision
rule.

## Checks run

- af37f7a3ea pushed; the build and smoke are queued on that sha.
- `hw/ide/core.c`: a syntax-only compile with the desktop build's flags
  (`/home/justin/hakuX/build-desktop/compile_commands.json`) passes. The
  full desktop build is not run (libcurl is missing on this host).
- No selftest: no harness file changed. No CI (offline).

## Next

1. The smoke prints `[ide425d]`, so the line works on the device.
2. One 700 s MTV hold: `capture_mtv_ide425.sh` with `REF=af37f7a3ea`. Read
   each 200+ ms hitch window by NOTES section 12's rule. dev dominates
   (P 0.4): the host read is the fix. gap dominates (P 0.45): guest loader
   work, under the vCPU JIT direction. drain (P 0.05): a synchronous host
   stall. The win is the 330 ms class, 1.15 hitches per minute on MTV, and the
   same IRQ14 link on Orta and Blood Wake.
