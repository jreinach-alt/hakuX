# lane.memfast W1: a surface watch flushes only its own pages, not the whole TLB (#507)
State: ready

Lane: memfast            Issue: #507
Base: master @ 34e6e8dcba, merged (phase 1, the XBOX fast-path removal, folded as ddbc5f0173)
Files: accel/tcg/cputlb.c, system/physmem.c, docs/lanes/memfast/NOTES.md, docs/lanes/memfast/PR.md, docs/lanes/memfast/OUTBOX.md, docs/lanes/memfast/w1_read.py, docs/lanes/memfast/WAITING, docs/testing/predictions/memfast-w1-pixels.json, docs/testing/predictions/memfast-w1-soak.json
Prediction: docs/testing/predictions/memfast-w1-pixels.json @ 8ec879bd71192076e3b0df62a560c7f2f774cfa77278aa5e8db13dbcc8180d02 ; docs/testing/predictions/memfast-w1-soak.json @ 65bb616e110c75807522e2ac39d8698c4be47c1f80f1cea3122901e3eb3a7bcc (a_ref 5e249bbfe0, b_ref 1b0f73a8bd)
Needs device: yes    Needs NDK: yes

Release note (performance): Conker, Blinx 2 and Forza no longer empty the emulated CPU's address-translation cache each time the GPU starts or stops watching a surface (Conker: 145 full flushes a second down to 1); no fps or battery change was measured, as these titles run at their 30 fps cap.

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
| M: B's `fo`/s at most 10% of A's (Conker, Blinx 2, Forza); `wn` about 2 x inserts | **PASS** on all three: B's `fo` is 0.7% (Conker), 2.4% (Blinx 2) and 6.7% (Forza, to its crash) of A's; `wn` 1.00-1.03 x 2 x inserts |
| X: `wx` = 0 on every B line | **PASS**: every B soak and the pgraph fix arm |
| P: B's `pfl`/s and `ff`/s against A's (the large-page region; an observation) | no cost: `pfl` 0 on every run, both arms; non-watch full flushes unchanged (Blinx 2: 7.15/s B, 7.18/s A) |
| C: vCPU ms per wall second, B/A <= 0.97 on Conker (a labelled guess) | not shown, not refuted: 0.985 (Conker), 0.997 (Blinx 2), 0.987 (Forza). The thread is on-CPU 85-95% on both arms, so this reads busyness, not work per frame |
| G: B reaches play on Forza and Crimson; no crash or hang | Crimson **PASS** (191 s of play, fps_ok 0.989). Forza **VOID**: both arms hit the same guest BugCheck 0x7f (double fault) at about 110-120 s in the menus, on the golden-profile disk; filed in OUTBOX, not caused by W1. Conker and Blinx 2 (no gameplay route): 300 s, no crash or hang, both arms |
| Pixels (`memfast-w1-pixels.json`) | **PASS**, all 3,064 checks (pair split across devices). `FramebufferNotModifiedBySurfaceState`'s 0 -> 79 on that arm was the capture's race: the Antialiasing suite x3 per arm on the Nova read 0 on all six runs |

## Local checks (no CI while GitHub is suspended)

- On the merged head: `-fsyntax-only` with the NDK compile database's
  flags on `cputlb.c` and `physmem.c` (`.scratch/syncheck.py`): rc 0, no
  errors; the only warnings are master's `-Wshift-negative-value` on
  `TARGET_PAGE_MASK`.
- A Crimson B soak (300 s, `--perflog`, `crimson-skies`) is queued at this
  head on the Nova for `offline_fold`'s head-run check.
- No harness files changed, so `selftest.sh` does not apply.
- An independent review of the diff found no correctness bug and one
  performance risk, which leg P watches (NOTES, "W1").

## Next

After the fold: F0a's device half (one native test run; it decides whether
F1, fastmem, is built), then F1 (P 0.4, about 11% of GTA's vCPU time,
+15-19% fps on Tron 2.0 if it stays vCPU-bound). The ranking, with P, win
and cost, is in NOTES, "Next", item 5.

## Phase 1 (folded)

The Nova scores for phase 1 (pixels PASS, reach PASS, J not shown at the
30 fps cap) are in NOTES, "Phase 1 on the Nova", and in OUTBOX.md. The
corrected release note is: the emulated CPU does about 5% less work per
frame in GTA San Andreas, with no measured fps or battery change on the
30 fps titles measured.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
