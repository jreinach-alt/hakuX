# #31 on silicon, second variant: `ClipF` at `clip_top = 4` -- prediction, registered before the run

**Status: PRE-REGISTERED.** Committed and pushed before this disc boots on the
console. The first variant (`clip_top = 35`, PR #218) came back **34** on
silicon: the absolute 4-grid at phase 2, `4*floor(ct/4)+2`. With that fourth
observation, 48 rules of the family still fit. One is on a grid of 4 or finer
(the 4-grid itself); 47 are on grids of 8, 16 and 32 and fit only because the
other three `clip_top` values are multiples of 32. This run is meant to
separate the 4-grid from all 47.

## The choice of 4 is the registered tool's, not mine

`docs/testing/wbuf_clip_phase_choice.py`, given the goldens plus the silicon
`clip_top = 35` capture, ranks the candidates and prints this table for its
pick. Every value in its best set (4-7, 12-15, 20-23, 28-31, 36-39, ...) gives
5 classes over the 48 survivors, and it prints the first.

| recovered anchor at `clip_top = 4` | rules | reading |
|---:|---|---|
| **6** | `4*floor(ct/4)+2` -- alone | the 4-grid at phase 2, and nothing else |
| **2** | 44 rules on grids >= 8 | coarse grid; the 4-grid refuted |
| **10** | 1 rule on a grid >= 8 | coarse grid; the 4-grid refuted |
| **18** | 1 rule on a grid >= 8 | coarse grid; the 4-grid refuted |
| **34** | 1 rule on a grid >= 8 | coarse grid; the 4-grid refuted |
| anything else | -- | the whole family is refuted |

## What runs

| | |
|---|---|
| tests tree | `6743b6a` + `wbuf31_clipf_phase.patch` (35) + [`wbuf31_clipf04.patch`](wbuf31_clipf04.patch) (4): branch `hakux/wbuf31-clipf04` @ `545195ee96` |
| XBE | sha256 `16680c6bf971cb98841f9e5bf713113f4ec6fbb60133025212ff160883a0b56e` |
| ISO | 5,832,704 bytes, sha256 `f7131b205f71e2990b32f2d6030695a1a08239ece9eb311f217770f319dea5a9` |
| console install | `E:\Apps\PgraphWbuf31b\` (new; `PgraphWbuf31` is left as it is) |
| tests | `W buffering`: `WBuf24D_FloorQuad_V1_ZB0_ZS0`, `WBuf24D_FloorQuad_V1_ZB0_ZS1`, `WBuf24D_ClipF-150-{032,128,224,035,004}_V1_ZB0_ZS1` |
| runner | `tools/xbox/pgraph_run.py` (PR #219) |

## Controls, each of which voids the run if it fails

- **C1 -- the known anchors come back.** `ClipF` 032 t0 32 and t1 34; 128
  t1 130; 224 t1 226; **and 035 t1 34 and t0 34**, the first silicon result,
  now a control. The 032/128/224/FloorQuad captures must be bit-identical
  to their goldens, and the 035 pair bit-identical to PR #218's silicon
  captures of it (same console, same test code).
- **C2 -- the geometry.** `ClipF-150-004`: t0 **27,956 px**, t1 **192,054
  px**, computed from geometry alone by the same tool.
- **C3 -- the plane.** `FloorQuad` `floor(w)` vs the run's own `ZS0`: 0
  mismatches.

## Safeguards, unchanged from the first variant

The disc runs on the Thor through the dispatcher first. On the console:
shutdown-on-completion off, networking off, no register writes, and the
runner's preflight and refusals.

## Scoring, exactly

    python3 docs/lanes/xbox/score_clipf04.py --goldens <fetched root>

`wbuf_anchor_recover.py` lists `ClipF` at 32, 35, 128 and 224 only. The
wrapper, committed with this registration, adds 4 to its `PRIMS` table
exactly as the others are defined and runs the tool's own `main()`. It edits
no line of the tool. C1 and the verdict are the `ClipF-150-*` rows, C2 the
`n` column, and C3 the CONTROL block.
