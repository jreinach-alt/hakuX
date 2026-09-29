# lane.tcg424flip (#424): flip the range test to the default

## What changed

`hakux_tcg424_range_on()` (accel/tcg/tb-maint.c) now returns true unless
`HAKUX_TCG424_RANGE=0`. Before, it returned true only for
`HAKUX_TCG424_RANGE=1`. Nothing else changes. The opt-out keeps the
whole-page path (xemu 703566ce33) reachable for A/B runs. The comments in
tb-maint.c and tb-internal.h now describe the new default. The `[tlb68]` line's
`rt=` field reads the same function (cputlb.c:302), so each run reports which
path it took.

Commit: 62ef8bf0fe, on master 30538458a0.

The flip follows tbflip424-blinx2.json, which passed on the Thor over three
pairs (hostops' #424 comment of 2026-09-28 22:30 PDT): M0, M1 and M4' passed,
gfps medians 19 / 19, churn% 2.1 / 0.0.

## Two predictions, both registered before any run

| file | what | who runs it |
|---|---|---|
| `docs/testing/predictions/tcg424flip-pgraph.json` | full pgraph sweep, 100 suites, every capture `must_not_move`; a = master 30538458a0, b = 62ef8bf0fe; skip `Texture_render_target::RenderTextureLoop` as the other full-sweep arms do | the arms job (a_ref != b_ref, no title) |
| `docs/testing/predictions/tcg424flip-arctic.json` | Arctic Thunder soak, Thor, MAX, cool gate, 560 s, route `arctic-thunder`; A = 62ef8bf0fe with `--env HAKUX_TCG424_RANGE=0`, B = 62ef8bf0fe with no env; 3 runs per arm, pilot = first A and first B | this lane, with request.sh (arms.sh skips soaks) |

The Arctic legs are M0 (instrument, and B reading `rt=1` with no env is the
flip's own check), M1 (churn% A >= 5, B <= 0.5 x A; di/s B <= 0.1 x A), M2a
(lane.local's on-CPU leg: on% B <= A - 2), M2b (cpf B <= 0.95 x A), and M4'
(gfps B >= A - 1; no crash; tail <= 15 s). The flip ships iff M0, M1 and M4'
pass and the pgraph arm is byte-identical. M2a and M2b decide what the release
note can claim.

Why M2b was added: on% alone cannot tell apart a saving the vCPU spends on more
frames and no saving at all. On a guest-bound title the first case is the one
we want, so a fall in on% is not the only good outcome. cpf (vCPU on-CPU ms per
game frame) measures the same saving per unit of work.

## The reader

`docs/lanes/tcg424flip/arcticread.py` loads `docs/lanes/tbflip424/playread.py`
unchanged and swaps two strings in it before it runs:

- `'mark play'` becomes `'mark gameplay'`. The arctic-thunder route writes no
  `mark play`.
- `'mark booted'` becomes `'soak start'`, which is m50's start. The route writes
  no `mark booted`.

It adds `on%` and `cpf`. playread.py itself is not edited.

## Baseline on disk (A path only, before this lane)

`baseline.out`, from lane.slowtier2's two titleroutes runs (Thor, MAX):

| run | gfps | churn% | di/s | inv/s | slow/s | on% | cpf | m50 |
|---|---|---|---|---|---|---|---|---|
| 1-1790547557-titleroutes-979135 (677ae13af8) | 21 | 14.1 | 37,642 | 7,364 | 10,221 | 87.6 | 41.7 | 89 |
| 1-1790548502-titleroutes-1531400 (e884ad260e) | 23.0 | 13.9 | 41,061 | 8,092 | 11,202 | 87.1 | 37.9 | 88 |

Arctic spends 14% of its vCPU time on the two #424 mechanisms. Blinx spends
2.1%.

## Runs

(filled in as they land)

## For the next lane

- Soak predictions are hand-read. arms.sh skips any prediction that has a
  `title`, and one whose a_ref equals its b_ref. Queue the soak with
  `request.sh --title` yourself.
- The arctic-thunder route marks `mark gameplay`, not `mark play`. playread.py
  would VOID every run.
