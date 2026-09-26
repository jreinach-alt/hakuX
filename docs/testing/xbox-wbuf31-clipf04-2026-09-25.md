# #31 on silicon, second variant: `ClipF` at `clip_top = 4` anchors at 6 -- the 4-grid, uniquely

**Measured 2026-09-25 on the project console (GPU rev 163 / MCP rev 212).**
Registered beforehand in
[`docs/lanes/xbox/wbuf31-clipf04-prediction.md`](../lanes/xbox/wbuf31-clipf04-prediction.md)
(commit `89c3fbd344`). The first variant is
[`xbox-wbuf31-clipf35-2026-09-25.md`](xbox-wbuf31-clipf35-2026-09-25.md) (PR #218).

## The answer

`ClipF-150-004`'s second triangle recovers **6.001**. At `clip_top = 4` the
registered table gives 6 to `4*floor(ct/4)+2` **alone**; the 47 coarse-grid
rules that survived `clip_top = 35` predict 2, 10, 18 or 34 and are refuted.

| second triangle (t1) | 32 | 128 | 224 | 35 | **4** |
|---|---:|---:|---:|---:|---:|
| silicon | 34.000 | 130.001 | 226.001 | 34.000 | **6.001** |
| `4*floor(ct/4)+2` | 34 | 130 | 226 | 34 | **6** |

**Of the family's rules, the absolute 4-row grid at phase 2 is the only
one left**: the rule `TriH` pins on all 24 of its triangles. For a fix, that
settles which rule to encode for `ClipF`'s second triangle.

## New, and not what either model predicted: the first triangle

The registration asked only about t1, but every run recovers t0 too, and
the first triangle's three observations fit neither of the two models this
suite already had:

| first triangle (t0) | clip_top 32 | 35 | 4 |
|---|---:|---:|---:|
| silicon | **32.001** | 34.001 | **6.000** |
| `4*floor(ct/4)+2` | 34 | 34 | 6 |
| quad snap of the first covered row (shipped) | 32 | 34 | 4 |

The 4-grid fits 35 and 4 but not 32; the quad snap fits 32 and 35 but not 4.
So whatever selects t0's anchor depends on something neither rule reads.
`wbuf_anchor_recover.py --pairs` frames the candidates: plane, clip, first
covered pixel, top vertex. At `clip_top = 4` the clip may not cut t0 at
all, and an uncut triangle anchoring on the 4-grid is `TriH`'s behaviour, but
that is a hypothesis for the fix lane to test against geometry, not a
finding. This is a new constraint on any fix: t0 must come out 32, 34 and 6.

## Why the capture can be trusted

| check | result |
|---|---|
| C1: known anchors, and bit-identity | 032 t0/t1 32.001 / 34.000, 128 130.001, 224 226.001, 035 t0/t1 34.001 / 34.000. Every existing-test capture is **bit-identical** to its golden, and the `-035` pair is **bit-identical** to the first silicon run's (run-to-run determinism on the console) |
| C2: geometry | `ClipF-150-004` t0 **27,956 px**, t1 **192,054 px**, exactly as registered |
| C3: plane | `FloorQuad` `floor(w)` vs `ZS0`: **0** mismatches over 221,970 px |
| dry run first | the same XBE on the Thor (`1790318016-xbox-wbuf31b-dryrun-4179332`) completed normally with all 14 captures |

## How it was run

Tests tree `6743b6a` + both `ClipF` patches (`hakux/wbuf31-clipf04` @
`545195ee96`); XBE sha256 `16680c6b…a0b56e`. `tools/xbox/pgraph_run.py`
(PR #219) installed it to `E:\Apps\PgraphWbuf31b\` and ran seven `W buffering`
tests with shutdown-on-completion off and networking off: `SITE EXEC` at
23:35:57 PDT, back at the dashboard with the log complete at 23:36:53. It was
scored by `docs/lanes/xbox/score_clipf04.py`, which adds `clip_top = 4` to
`wbuf_anchor_recover.py`'s table at runtime and edits nothing. Captures and
logs stay on the host under
`~/hakux-work/hardware/runs/2026-09-25-wbuf31-clipf04/`.
