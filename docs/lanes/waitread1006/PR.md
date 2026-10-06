# waitread1006: D&D is submit-bound and its GPU time is unverified; SW3 is fence-bound at 36 passes a frame; GTA is guest-bound; Tron's 1.06 s stall is 188 ms shader work
State: ready

Lane: waitread1006                Issue: #433 (split issues filed: #863, #864, #865 under #747; #866, #867 under #746; lane PR #862)
Base: master @ bf85412b88
Files: docs/lanes/waitread1006/NOTES.md, docs/lanes/waitread1006/REPORT.md, docs/lanes/waitread1006/evidence.tsv, docs/lanes/waitread1006/OUTBOX.md, docs/lanes/waitread1006/PR.md, docs/lanes/waitread1006/issues/split-drafts.md, docs/lanes/waitread1006/tools/summ_verdicts.py, docs/lanes/waitread1006/tools/run_waits.py, docs/lanes/waitread1006/tools/sd_share.py, docs/lanes/waitread1006/tools/family_read.py, docs/lanes/waitread1006/tools/file_split_issues.py
Prediction: none: analysis-only (no change to the emulator; no device run)
Needs device: no    Needs NDK: no

Release note: none. This PR changes no emulator code.

## What this found

Offline read of the four 10-05/06 Nova runs (ref c3a0c70ace) and the readers
in `tools/`. Full report: `REPORT.md`. Evidence rows: `evidence.tsv`.

| title | named wait (gameplay, ms per frame) | fps_ok share |
|---|---|---|
| D&D Heroes | submit back-pressure: `Sub` 38.6 of `Tot` 74.4; GPU stamps 41.3 but 17.6% of its finishes are the pre-5c35880d0a over-count | 0.0 |
| Star Wars III | fence wait `Fen` 9.8 of `Tot` 30.8; 36 render passes a frame; median frame 1.8 ms over the 30-fps deadline | 0.474 |
| GTA SA | guest-bound: `IdleFr` 10.0, `IdleSt` 7.35 of a 33.8 ms wall; shader compile is load-time (7.9 s run-wide, 38 ms in gameplay) | 0.746 |
| Tron 2.0 | 1063 ms stall: 188 ms pipeline creation, the rest unexplained by any counter; two more gameplay stalls (744, 530 ms) with no shader work | 0.920 |

Also: the SW3 figure on disk for 10-02 is 87.7% (survey `7a090b6fa2`), not
96%. The range to 10-06 is 676 commits, 46 touching hw/accel/android.

## Not done

- Family rows: pace and vblank re-read for five sweep runs (`tools/family_read.py`); NHL 2K3's run dir was not found; the vCPU split is the issues' own figure.
- Castlevania's 1.43 s stall: not on disk. #851 is Marvel Nemesis r3 (1014 ms, no shader work).
- Split issues: filed as #863-#867 from `issues/split-drafts.md`.

Preflight: every gate passes but coverage, which fails on #863-#867 (no tracker rows; board request at dispatch/board-requests/waitread1006.md) and on #859 (not this lane).
