# lane.memfast F1: guest loads through the host MMU ("fastmem"), behind HAKUX_FASTMEM, default off (#507)
State: draft

Lane: memfast            Issue: #507
Base: master @ 51305b71dd (merged; W1 folded as de396edb2a)
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
- **`HAKUX_FASTMEM=one`** is F1 with one host alias for the vCPU: shadow pages are mapped read-write, and an idx-5 TLB entry for a mapped page takes the shadow as its addend. Softmmu stores, slow paths and fast loads then reach a page at one host VA. `tlb_reset_dirty` and the code-fetch lookup translate shadow pointers back to xbox.ram, and every shadow unmap softmmu did not ask for flushes the entries it leaves stale.
- **`HAKUX_FASTMEM=ram`** is F0b: RAM on a memfd with no shadow.
- **`HAKUX_F0A=<s>`** runs the F0a microbenchmark in the app, <s> seconds after start.
- **Unset:** emission, RAM and register allocation are master's. The hooks cost one load of a false global.

The design and the choices against it are in NOTES ("Phase 2 design" and "Attempt 3").

## Legs

| leg | result |
|---|---|
| F0a constants (Tron, control arm, 730 s) | **done**: SIGSEGV 1.6-2.4 us, map 1.6-2.4 us, cold refault 4.4 us, walk 2.2-2.5 ns a page, drop-all 10-12 ms per 8,192 pages (NOTES, "F1 pilot") |
| F1 reaches play, no crash or hang; `[fm]` faults, upkeep, patched sites | **pass**: 750 s, 5.3 faults/s, 0.12 ms/s upkeep, 732 sites patched |
| Tron sustained fps, F against C: +5-15% predicted; kill below -3% | **killed**: -9 to -33% fps for 0-150 s after the mark, repeated in batch 2 (F2). The pilot's late gain was route divergence: B, with no shadow, reaches the same 60 cap state |
| Batch 2: what costs the early scenes | **named**: THP is `never` on the Nova (master's RAM has no huge pages either), and memfd RAM alone (B) is level with the control. The cost is the shadow's second host alias for each page: loads use one VA and stores another. F1's counted work is under 0.1 ms/s there (NOTES, "Attempt 4") |
| One alias (`=one`) against the control, Tron, 0-150 s | **queued** at `62cc8e1aab`: O `1-1791094714-lane.memfast-388323`, C3 `1-1791094714-lane.memfast-388398`. Predicted: O within 3% of C3 in every early bucket |

## Local checks (no CI while GitHub is suspended)

- At `62cc8e1aab`: `-fsyntax-only -Wall` with the NDK compile database's flags on `cputlb.c`,
  `xbox.c`, `excp_helper.c`, `tcg.c` (which includes the backend) and
  `fastmem.c`: rc 0, no new warnings (`.scratch/fmcheck.py`). The
  preprocessed output confirms the F1 code is built.
- No harness files changed, so `selftest.sh` does not apply.

## Next

The O/C3 pair decides whether one alias recovers the early scenes. NOTES
("Attempt 4") has the outcome table, and "Next" item 8 has each candidate
with P, win and cost. The leading candidate is one alias: P 0.55, it
recovers a 9-33% loss, and it is the precondition for F1's +5-15% on Tron.
F1 stays draft and default-off until a pair shows it no slower than the
control.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
