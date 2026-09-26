# lane.wbuf31sel NOTES

Issue #31. PR #244. Base master `21946df29b`. This lane replaces the `flatTop`
clause of #222's W-buffer top-cut rule (`glsl/psh.c`, `wbufSlopeStep`), which
silicon refuted at ClipF clip_left 300 / clip_top 8 (PR #243).

## The choice

```
master:  grid = !cut || (topCut && !(flatTop          && ct%8 == 0))
this:    grid = !cut || (topCut && !(first != clip.x  && ct%8 == 0))
```

`first` is the start column of the first covered span of the clipped
polygon. `wbufSlopeStep` already computes it (the loop that finds the anchor
row `r`); this change only hoists it out of that loop. As a selector literal it
is `span_starts_at_clip`, and the fit is

    !cut | (cut_top_by_clip & (span_starts_at_clip | !ct%8==0))

It is the only one of the 57 survivors that keeps every other term of the
shipped rule (`!cut`, `topCut`, `ct%8`). So it is exactly "replace `flatTop`,
keep everything else".

### The brief's premise, tested

The brief and `docs/lanes/wbuf31fix/NOTES.md` item 3 say that
`span_starts_at_clip` "depend[s] on the traversal-derived anchor column". **It
does not.** It is `first == clip_left`. `first` is `ceil(lo - 0.5)` on the
first row whose sample line the clipped polygon crosses. That is a function of
the three vertices and the clip rect, and it never reads `c`, the anchor column
(`xtop` clamped into the span). Two more points:

- Master's own anchor ROW `r` comes out of the same loop. A rule that may use
  nothing from the span walk could not use master's anchor either.
- The Python literal (`features()`) and the shader compute `first` the same
  way: ceil of the span's left end on the first covered row. This is not an
  approximation of the literal the fit was scored on. It is that literal.

`B_quad_covered_at_c` does read `c`, and `c` is a heuristic column (TriV shows
that no integer column is right in general). This lane did not choose any fit
that uses it.

## The 57 fits and what each needs

Output: `fits57.out` (`python3 docs/lanes/wbuf31sel/fits57.py`). The
reproduction matches #243: 54 anchors, 35 informative, 57 fits, master's `sel`
at 53/78.

Each literal falls into one input tier:

| tier | literals | what the shader needs |
|---|---|---|
| V: vertices and clip rect only | `cut`, `cut_top_by_clip`, `clip_top_0`, `ct%8==0`, `top_vertex_inside` | has it |
| S: first covered span `(r, first, last)` | `span_starts_at_clip`, `xtop_in_first_span`, `r%8==0` | has it (same loop as master's `r`) |
| C: the anchor column `c` | `B_quad_covered_at_c`, `c%8<4` | has `c`, but `c` is a heuristic column, and `B_quad` also needs two more span evaluations |
| D: a second clip pass | `rows_removed_by_clip` | would need a clip at clip_top 0 as well |

The fits are `head | (mid & (x | y))`:

| head | mid | exception | count | tiers | computable now |
|---|---|---|---:|---|---|
| `top_vertex_inside` / `xtop_in_first_span` / `!cut` | `cut_top_by_clip` or `!clip_top_0` | `span_starts_at_clip \| !ct%8` or `\| !r%8` | 12 | V+S | **yes** |
| same three | `rows_removed_by_clip` | `span_starts_at_clip \| ...` | 6 | V+S+D | yes, with a second clip pass |
| same three | any of the three | `B_quad_covered_at_c \| ...` | 18 | +C | reads `c` |
| `!ct%8==0` | `B_quad_covered_at_c` | (9 variants) | 9 | +C | reads `c` |
| `!r%8==0` | `B_quad_covered_at_c` | (12 variants) | 12 | +C | reads `c` |

Total: 12 + 6 + 18 + 9 + 12 = 57. **No fit is tier V alone.** Every one of the
57 reads `span_starts_at_clip` or `B_quad_covered_at_c`. Under the strictest
reading of "nothing from the span walk", nothing is computable, and the minimal
extra input is `first`. But the shader already has `first`, so the 12 V+S fits
are computable today. Among them, `!cut` + `cut_top_by_clip` + `ct%8` is the
shipped rule's own skeleton.

## Score (`wbuf_anchor_recover.py`, anchor mode `span`)

Roots: the four 2026-09-25 console runs (`c300`, `clipf35`, `clipf04`, `t0`) plus
`/home/justin/goldens/results`. Full output: `simulate.out`.

- `sel` (master): **53/78**. It misses ClipF-300-008/t0 and the 24 TriV rows.
- `span` (this): **54/78**. It misses only the 24 TriV rows, which every rule
  misses (column, pb == 0; not reopened here).

`--simulate` (float32, exact / ±1 / wrong):

| capture | sel (master) | span (this) |
|---|---|---|
| ClipF-300-008 (console only) | 108,412 / 17,936 / **24,952** | 117,722 / 33,578 / **0** |
| every other capture | | identical to sel, row for row |

ClipF-150-008 keeps 16,600 wrong under both rules. That is pre-existing, and
this change does not touch it.

## The arm

The prediction is `docs/testing/predictions/wbuf31sel-spanclip.json`:
a_ref `d709a8d1fa` (master), b_ref `9848c0f227` (re-registered; the first
registration named `21946df29b` / `f32946d5ea`, see below). It has one leg,
must_not_move over `W_buffering/*` and `Depth_Clamp/*`. The positive evidence
is the offline simulation above, because ClipF-300-008 is not on the disc and
no golden can show it. The failure worlds are in the prediction's prose. In
short: a golden moving means the selector disagrees with `flatTop` somewhere
the old evidence pinned. Report which capture, and do not refit.

Before trusting the verdict, check both arms' `scores1.tsv` status column for
`unreadable`, and each `run1.log` for UtilAcceptVsock and PARTIAL COVERAGE.

**Status 2026-09-25: waiting.** The arm is queued by committing the
prediction, and CI runs on the head. Two signals resolve this: the `[job.arms]`
verdict comment on PR #244, and green CI. PR #244 stays draft until the verdict
is in and its status column is checked.

### Why attempt 1 did not finish (resume, 2026-09-25 ~19:45Z)

Two things stranded PR #244, neither a defect in the patch:

- **The arm was REFUSED, not judged.** The `[job.arms]` verdict (16:31Z) says
  the base arm `1790352053-arms-wbuf31sel-base-769582` had
  `progress_log_proof` false, so ab_compare counts it absent. Nothing requeues
  a refused arm with the same prediction.
- **The head conflicted with master** on `docs/testing/nv2a_index.json`
  (other folds regenerated it), so GitHub built no CI run on `dfd4fd3a98`.

Attempt 2 merged `origin/master` (`d709a8d1fa`) as `9848c0f227`, regenerated
the index over the pinned trees (tests `6743b6a`, pbkit `e91d509`; `check`
passes), and re-registered the same prediction, same legs, on a_ref
`d709a8d1fa` / b_ref `9848c0f227`. The emulator diff between those refs is
this lane's `psh.c` change and nothing else. The lane waits again on the new
`[job.arms]` verdict and CI on the new head.

No shader-cache version bump is needed: `vk/glsl.c` keys SPIR-V on a hash of
the GLSL text, and no ShaderState field changed.

### Why attempt 2 did not finish, and the verdict (resume, 2026-09-25 ~23:10Z)

Attempt 2 ended correctly, waiting: the re-registered arm was queued and CI had
not built the head. Nothing was wrong with it. Handback resumed the lane with
both resolved:

- **Arm verdict: PASS**, `[job.arms]` 16:04 PDT. a `d709a8d1fa`
  (`1790365513-arms-wbuf31sel-base-476580`), b `9848c0f227`
  (`...-fix-476626`). 570 captures per arm, progress-log proof yes on both.
  0 movers, and all 570 are byte-identical between the arms. Exact 116 -> 116.
- **Status column checked:** both `scores1.tsv` read ok 500, white-content 59,
  label-differs 9, blank 2. No `unreadable`, and the two arms match. Neither
  `run1.log` contains UtilAcceptVsock or PARTIAL COVERAGE.
- **CI GREEN** on `09cfd49a7b`.

Master had moved 91 commits ahead by then, and the PR conflicted again, only on
`nv2a_index.json`. Attempt 3 merged `origin/master` as `b77e03eb78` and
regenerated the index over the same pins; `check` passes. Neither `psh.c` nor
`wbuf_anchor_recover.py` differs between the judged b_ref `9848c0f227` and
that merge, so the verdict still covers the patch. Nothing was re-registered.

## For the next lane

- Do not re-run the 4-literal search hoping for a tier-V fit. There is none
  over this literal set with ClipF-300-008 in it.
- The capture that would separate the 12 computable fits from each other has
  not been identified. Their heads (`top_vertex_inside` / `xtop_in_first_span`
  / `!cut`) and `ct%8` vs `r%8` agree on every capture so far.
- nv2a_index.json was regenerated over tests `6743b6a` / pbkit `e91d509`;
  `check --tests` passes.
