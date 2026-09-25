# #31 on silicon, third run: `ClipF` at `clip_top` 8, 12, 16, 64 -- the first triangle -- registered before the run

**Status: PRE-REGISTERED**, committed and pushed before this disc boots.
Asked for by `lane.wbuf31fix` on #31: over the goldens plus the console runs
at 35 and 4, no selector of up to three literals over 27 geometric features
picks the quad snap vs the 4-grid for all 44 recovered anchors. 333
four-literal fits exist. All of them give the second triangle the 4-grid; they
differ on the first. These four `clip_top` values separate row alignment
(8/16/32), column parity and column phase for t0.

## Legs

- **T1 -- the second triangle stays on the 4-grid.** At `clip_top` 8, 12,
  16 and 64, t1 recovers **10, 14, 18, 66** (`4*floor(ct/4)+2`, within the
  tool's 0.01 px). All 333 surviving selectors agree, so a miss refutes the
  conclusion of PRs #218 / #221 itself.
- **T0-form -- the first triangle takes one of the two rules.** At each new
  `clip_top`, t0 recovers either `ct` (the quad snap: every new value is a
  multiple of 4) or `ct+2` (the 4-grid). Any other value refutes the
  quad-snap-or-grid framing the whole selector search rests on.
- **T0-verdict -- read mechanically, not chosen.** Which of the two each t0
  takes is recorded as measured. The surviving selectors are then whatever
  `wbuf_anchor_recover.py --selectors` (lane/wbuf31fix @ `37192979a2`)
  reports over the goldens plus every silicon run, this one included.

## Controls

- **C1:** the known anchors come back (32 t0/t1 32/34, 128 t1 130, 224 t1
  226, 35 t0/t1 34/34, 4 t0/t1 6/6). Every existing-test capture is
  bit-identical to its golden, and the 035 and 004 pairs are bit-identical to
  the earlier silicon runs.
- **C2 -- geometry**, from the suite's own coverage routine, which
  reproduces the three known pairs exactly (4: 27,956 / 192,054; 32:
  16,801 / 189,489; 35: 15,773 / 189,047):

  | clip_top | t0 px | t1 px |
  |---:|---:|---:|
  | 8 | 26,190 | 191,860 |
  | 12 | 24,481 | 191,609 |
  | 16 | 22,830 | 191,300 |
  | 64 | 7,513 | 183,097 |

- **C3:** the `FloorQuad` plane control, 0 mismatches.

## What runs

Tests tree `6743b6a` plus the three `ClipF` patches (branch
`hakux/wbuf31-clipf-t0` @ `da77078d9a`; this one is
[`wbuf31_clipf_t0.patch`](wbuf31_clipf_t0.patch)). XBE sha256
`a2c2220f454e14713313c4dfac36cd7b38760a456049954755d3af02aa242c11`, ISO
`b8a4c71532a6b595af9df32a02df0a667aa4c6520389b94f534dc0baeedfc7e5`.
The dry run is on the Thor through the dispatcher, then the console through
`tools/xbox/pgraph_run.py` into the new app directory `E:\Apps\PgraphWbuf31c\`,
with shutdown off and networking off. It is scored by
[`score_clipf_t0.py`](score_clipf_t0.py), which adds the new `clip_top`s to
the tool's table at runtime and edits nothing.
