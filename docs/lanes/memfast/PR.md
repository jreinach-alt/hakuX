# lane.memfast W1: a surface watch flushes only its own pages, not the whole TLB (#507)
State: draft

Lane: memfast            Issue: #507
Base: master @ a143aa5db8, merged (phase 1, the XBOX fast-path removal, folded as ddbc5f0173)
Files: accel/tcg/cputlb.c, system/physmem.c, docs/lanes/memfast/NOTES.md, docs/lanes/memfast/PR.md, docs/lanes/memfast/OUTBOX.md, docs/lanes/memfast/w1_read.py, docs/lanes/memfast/WAITING, docs/testing/predictions/memfast-w1-pixels.json, docs/testing/predictions/memfast-w1-soak.json
Prediction: docs/testing/predictions/memfast-w1-pixels.json @ 8ec879bd71192076e3b0df62a560c7f2f774cfa77278aa5e8db13dbcc8180d02 ; docs/testing/predictions/memfast-w1-soak.json @ 65bb616e110c75807522e2ac39d8698c4be47c1f80f1cea3122901e3eb3a7bcc (a_ref 5e249bbfe0, b_ref 1b0f73a8bd)
Needs device: yes    Needs NDK: yes

Release note (performance): PENDING -- written from the measured legs.

## What it changes

- **Before:** every NV2A surface-watch insert and remove queued a full TLB
  and jump-cache flush (the "FIXME: flush only applicable pages" in
  `system/physmem.c`). That was 287 full flushes a second on Conker, 58 on
  Blinx 2 and 38 on Forza (NOTES, section 8).
- **After:** the exclusive work item that changes the callback list walks
  the TLB and drops only the entries whose RAM address overlaps the watched
  range. It recovers the address the same way the watch check does
  (`xlat_section`). `HAKUX_W1=0` restores the full flush.
- **A cross-check, `wx`:** the walk also tests each entry's host pointer,
  an independent recovery of the same address. An entry that only the
  cross-check catches is dropped and counted, and the prediction says the
  count is 0.
- **New `[tlb68]` fields:** `w1=`, `wn=`, `wh=`, `wx=` and `wus=`. The
  reader is `docs/lanes/memfast/w1_read.py`.

## Legs

| leg | result |
|---|---|
| M: B's `fo`/s at most 10% of A's (Conker, Blinx 2, Forza); `wn` about 2 x inserts | Conker **PASS**: 0.96/s against 144.67/s (0.7%); `wn` 1.00 x 2 x inserts. Blinx 2 and Forza queued |
| X: `wx` = 0 on every B line | **PASS** so far: Conker (153 lines) and the pgraph fix arm (408 lines) |
| P: B's `pfl`/s and `ff`/s against A's (the large-page region; an observation) | Conker: `pfl` 0 on both arms; `ff` 1.27/s against 144.98/s |
| C: vCPU ms per wall second, B/A <= 0.97 on Conker (a labelled guess) | not shown: 0.985. The thread is on-CPU about 90% on both arms |
| G: B reaches play on Forza and Crimson; no crash or hang | queued |
| Pixels (`memfast-w1-pixels.json`) | **PASS**, all 3,064 checks. The pair split across devices (base on the Thor). Watch-capture leg PASS (0, 0, 134). One excluded capture, `FramebufferNotModifiedBySurfaceState`, read 0 -> 79, so the Antialiasing suite is queued 3 x per arm on the Nova to settle it (NOTES) |

## Local checks (no CI while GitHub is suspended)

- `-fsyntax-only` with the NDK compile database's flags on `cputlb.c` and
  `physmem.c`: rc 0, no diagnostics beyond master's `TARGET_PAGE_MASK`
  shifts.
- No harness files changed, so `selftest.sh` does not apply.
- An independent review of the diff found no correctness bug and one
  performance risk, which leg P watches (NOTES, "W1").

## Phase 1 (folded)

The Nova scores for phase 1 (pixels PASS, reach PASS, J not shown at the
30 fps cap) are in NOTES, "Phase 1 on the Nova", and in OUTBOX.md. The
corrected release note is: the emulated CPU does about 5% less work per
frame in GTA San Andreas, with no measured fps or battery change on the
30 fps titles measured.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
