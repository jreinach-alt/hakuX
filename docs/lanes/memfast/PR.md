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
| F0a constants (Tron, control arm, 730 s) | queued: `1-1791081222-lane.memfast-2796953` |
| F1 reaches play, no crash or hang; `[fm]` faults, upkeep, patched sites | queued: `1-1791081223-lane.memfast-2797182` |
| Tron sustained fps, F against C: +5-15% predicted; kill below -3% | pending the pair |

## Local checks (no CI while GitHub is suspended)

- `-fsyntax-only -Wall` with the NDK compile database's flags on `cputlb.c`,
  `xbox.c`, `excp_helper.c`, `tcg.c` (which includes the backend) and
  `fastmem.c`: rc 0, no new warnings (`.scratch/fmcheck.py`). The
  preprocessed output confirms the F1 code is built.
- No harness files changed, so `selftest.sh` does not apply.

## Next

Read the pair with `f1_read.py`, and `title_verdict.py` on copies. Then:

- If F is not killed: a second Tron pair, and BF2 MC.
- If faults or upkeep are the cost: the fix the `[fm]` line names (decay for patched sites, `MAP_POPULATE`, a larger cap).
- If F is killed by the constants themselves: the lazy view swap (design section 2), or park F1.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
