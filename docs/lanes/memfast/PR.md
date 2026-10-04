# lane.memfast F1: guest loads through the host MMU ("fastmem"), behind HAKUX_FASTMEM, default off (#507)
State: draft

Lane: memfast            Issue: #507
Base: master @ 4a3308a21e (W1 folded as de396edb2a)
Files: accel/tcg/fastmem.c, accel/tcg/fastmem.h, accel/tcg/cputlb.c, tcg/aarch64/tcg-target.c.inc, hw/xbox/xbox.c, target/i386/tcg/system/excp_helper.c, docs/lanes/memfast/NOTES.md, docs/lanes/memfast/PR.md, docs/lanes/memfast/OUTBOX.md, docs/lanes/memfast/f1_read.py, docs/lanes/memfast/WAITING
Prediction: none: an env pilot on one binary. The predicted values and the kill line are written in NOTES ("Attempt 3") before the runs. A registered arm follows if the pilot is not killed.
Needs device: yes    Needs NDK: yes

Release note (none): an opt-in prototype, off unless HAKUX_FASTMEM=1 is set; with it unset, nothing a player can see changes.

## What it changes

- **`HAKUX_FASTMEM=1` (F1, loads only).**
  - Guest RAM moves to a memfd.
  - A 4 GiB host "shadow" of the guest's linear space gets a read-only map of each RAM page that softmmu would serve with no read flags, on mmu_idx 5.
  - A guest load on that index is one instruction, `ldr wD, [x26, wA, uxtw]`. A fault resumes at the load's ordinary slow path.
  - The shadow follows fills, INVLPG, full flushes and W1's watch walk. A same-value CR3 reload is revalidated by a side-effect-free walk; anything else drops it.
- **`HAKUX_FASTMEM=ram`** is F0b: RAM on a memfd with no shadow.
- **`HAKUX_F0A=<s>`** runs the F0a microbenchmark in the app, <s> seconds after start.
- **Unset:** emission, RAM and register allocation are master's. The hooks cost one load of a false global.

The design and the choices against it are in NOTES ("Phase 2 design" and "Attempt 3").

## Legs

| leg | result |
|---|---|
| F0a constants (Tron, control arm, 730 s) | **done**: SIGSEGV 1.6-2.4 us, map 1.6-2.4 us, cold refault 4.4 us, walk 2.2-2.5 ns a page, drop-all 10-12 ms per 8,192 pages (NOTES, "F1 pilot") |
| F1 reaches play, no crash or hang; `[fm]` faults, upkeep, patched sites | **pass**: 750 s, 5.3 faults/s, 0.12 ms/s upkeep, 732 sites patched |
| Tron sustained fps, F against C: +5-15% predicted; kill below -3% | **killed in the early scenes**: -1 to -35% fps for 0-210 s after the mark; faster after 270 s (guest busy -25%, at the cap). Cause under test: batch 2 (THP probe, F0b arm) |

## Local checks (no CI while GitHub is suspended)

- `-fsyntax-only -Wall` with the NDK compile database's flags on `cputlb.c`,
  `xbox.c`, `excp_helper.c`, `tcg.c` (which includes the backend) and
  `fastmem.c`: rc 0, no new warnings (`.scratch/fmcheck.py`). The
  preprocessed output confirms the F1 code is built.
- No harness files changed, so `selftest.sh` does not apply.

## Next

Batch 2 (F2, B = F0b, C2, each with the THP probe) decides between the
memfd RAM losing THP and the shadow's 4 KiB alias as the early-scene cost.
NOTES, "Next" item 7 has each candidate with P, win and cost. F1 stays draft
and default-off until one of them recovers the early scenes.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
