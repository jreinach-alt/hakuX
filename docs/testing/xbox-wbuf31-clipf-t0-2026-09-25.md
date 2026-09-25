# #31 on silicon, third run: the first triangle at `clip_top` 8, 12, 16, 64

**Measured 2026-09-25 on the project console (GPU rev 163 / MCP rev 212)**,
for `lane.wbuf31fix`, which was blocked on the first triangle. Registered
beforehand in
[`docs/lanes/xbox/wbuf31-clipf-t0-prediction.md`](../lanes/xbox/wbuf31-clipf-t0-prediction.md)
(`61e1e3899f`). Earlier runs: PR #218 (35) and PR #221 (4).

## Every registered leg held

| clip_top | t0 px (pred) | t1 px (pred) | t0 anchor | t0 rule | t1 anchor (pred) |
|---:|---:|---:|---:|---|---:|
| 8 | 26,190 (26,190) | 191,860 (191,860) | **8.000** | quad snap | 9.999 (10) |
| 12 | 24,481 (24,481) | 191,609 (191,609) | **13.999** | 4-grid | 14.001 (14) |
| 16 | 22,830 (22,830) | 191,300 (191,300) | **16.000** | quad snap | 18.000 (18) |
| 64 | 7,513 (7,513) | 183,097 (183,097) | **63.999** | quad snap | 65.999 (66) |

- **T1:** the second triangle stays on the 4-grid at all four.
- **T0-form:** the first triangle takes `ct` or `ct+2` every time; no third value.
- **C1:** all 14 known captures are bit-identical to their goldens or to the
  earlier silicon runs, and the known anchors came back.
- **C2:** geometry exact on all eight.
- **C3:** 0 plane mismatches.

The dry run on the Thor (`1790319670-xbox-wbuf31c-dryrun-100759`) completed
normally first. The console run took 55 s and handed back to the dashboard.

## The verdict, as the registered tool reports it

`wbuf_anchor_recover.py --selectors` as on master (last changed `63a24f9834`),
over the goldens plus all three silicon runs:

```
52 anchors, 34 informative (quad != grid), 0 fit neither rule
'grid iff P' over 54 literals: 201348 selectors of <= 3 literals tried
  fit every informative anchor: 1 literal 0, 2 literals 0, 3 literals 0
  4 literals 'a | (b & (c | d))': 93 fit
      72 rules rest on ClipF-150-008/t0, ClipF-150-016/t0, ClipF-150-032/t0, ClipF-150-064/t0
      21 rules rest on FloorQuad/t1, RoofQuad/t0, WallQuad/t0, ClipW-159-000/t0, ClipW-261-000/t0, ClipW-261-000/t1, ClipW-363-000/t0
  ClipF clip_tops where the 93 four-literal fits disagree: none
```

The run cut the four-literal fits from 333 to 93, and all 93 give one answer
at every `ClipF` `clip_top` (at `clip_left` 150).

_Corrected 2026-09-25: this section first said 75 fits, 54 of them resting
on the four ClipF anchors. That figure came from `score_clipf_t0.py` driving
the tool at `37192979a2`. That version did not list clip_top 8, 12, 16 or 64,
so the wrapper added them after `_QUADS` had already been built from PRIMS at
import. Those four captures' second triangles were therefore scored with
`second_of_quad` False, which is wrong for a quad. Master's tool lists all
four at import, and the wrapper now adds to `_QUADS` too. The pre-run count
(333) did not involve those captures and reproduces on master. The
conclusion is unchanged._

**An observation, not a registered result:** the first triangle took the
quad snap at exactly the `clip_top` values that are multiples of 8 (8, 16,
32, 64). It took the 4-grid at the two that are 4 mod 8 (4, 12); at 35 both
rules give 34. Before this run, the exception clause the four-literal fits
share rested on one anchor (032/t0) that nothing else tested; it now rests on
four, all consistent with that pattern. Which selector to encode is
`lane.wbuf31fix`'s call.

**Later refuted as a rule:** the fourth run
([`xbox-wbuf31-clipf300-2026-09-25.md`](xbox-wbuf31-clipf300-2026-09-25.md))
put a flat-topped t0 under an 8-aligned `clip_top` (clip_left 300, clip_top 8),
and it took the 4-grid (10). What differs is that its first span starts at the
clip.

Captures stay on the host under
`~/hakux-work/hardware/runs/2026-09-25-wbuf31-t0/`. Score with
`docs/lanes/xbox/score_clipf_t0.py --goldens <that>/console-run/console`.
