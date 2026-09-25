# #31: replace the refuted `flatTop` clause with a surviving selector the shader can compute

Lane: wbuf31sel            Issue: #31 (slope-scaled polygon offset under W buffering)
Base: origin/master
Files: hw/xbox/nv2a/pgraph/glsl/psh.c, docs/testing/wbuf_anchor_recover.py,
docs/testing/predictions/wbuf31sel-*.json, docs/lanes/wbuf31sel/**
Needs device: yes (a Thor arm on W buffering + Depth Clamp). Needs NDK: no.

## Where this starts

- **PR #222** (folded as `3d3a646f8e`, arm PASS 371) encoded the W-buffer
  top-cut rule in `glsl/psh.c`. A triangle cut by the window clip's top takes
  the 4-grid row anchor. The exception is an edge that is 8-aligned with a
  flat-topped triangle (`flatTop`), which takes the 2x2 quad snap.
- **`flatTop` was the rule's weakest clause.** It was interchangeable on every
  existing capture with `span_starts_at_clip`, `B_quad_covered_at_c` and
  `second_of_quad`. `docs/lanes/wbuf31fix/NOTES.md`, "Weakest part", named the
  silicon capture that would separate them.
- **lane.xbox ran it** (PR #243; #31 comment 5834223393). ClipF at clip_left
  300 / clip_top 8: **t0 anchors at 10.000 on silicon (the 4-grid)**, and
  master's `sel` says 8.
  - `flatTop` is refuted.
  - **57 four-literal fits survive**: exactly the 57 that were registered as
    voting grid. The 36 that voted quad, master's among them, are gone.
  - The captures are in `~/hakux-work/hardware/runs/2026-09-25-wbuf31-c300/`.
  - The write-up is `docs/testing/xbox-wbuf31-clipf300-2026-09-25.md` on
    PR #243's branch. Read it from there if #243 has not folded.
  - In the float32 simulation of master's rule, all 24,952 t0 px of that
    capture are wrong. The variant is NOT on the golden disc, so no golden
    moves.

## The job

1. **Choose among the 57 survivors one the shader can compute.** The wbuf31fix
   NOTES ("Its inputs are ones the shader already has") set the constraint: the
   three vertices and the clip rect, with nothing from the span walk.
   `span_starts_at_clip` and `B_quad_covered_at_c` depend on the
   traversal-derived anchor column, and `second_of_quad` cannot be seen from
   three vertices.
   - Say which of the 57 are computable, and pick the simplest.
   - **If none of the 57 is computable from shader inputs, that is the
     finding.** Stop, and say what the minimal extra input would be. Do not
     encode a traversal-dependent rule by approximating it.
2. **Encode it in `psh.c`,** replacing `flatTop`. Keep everything else in
   PR #222's rule unchanged.
3. **`wbuf_anchor_recover.py`:**
   - add the new rule as an anchor mode;
   - score it over the anchors plus the new silicon capture: master's `sel` is
     53 of 78, and the new rule should reproduce at least that plus
     ClipF-300-008 t0;
   - run `--simulate` on ClipF-300-008 (24,952 t0 px wrong under master) to
     show the float32 prediction.

## The arm (register BEFORE building; after the last rebase)

Thor; suites **W buffering** and **Depth Clamp** (the ones #222's arm used).

- **must_not_move:** every capture. The variant is not on the golden disc, and
  the new selector must agree with `flatTop` everywhere the disc reaches. That
  is the whole reason they were interchangeable.
- **The world in which it fails:** a golden moves. Then the chosen selector
  disagrees with `flatTop` somewhere the old evidence had pinned. Report which
  capture, and do not refit.
- **The positive evidence is offline,** over the console capture
  (`--simulate`), because no golden can show it. State that limit in the PR
  body.
- **Before trusting the verdict:** check both arms' `scores1.tsv` status column
  for `unreadable`, and `run1.log` for UtilAcceptVsock and PARTIAL COVERAGE.

## Do not

- **Touch `glsl/geom.c`.** lane.wparamgeom223 holds it for #223.
- **Re-open the 24 `TriV` anchors** every rule misses. They are on the column,
  and `TriV` has pb == 0.
- **Trigger CI as a self-check.**

## Done when

- The arm verdict is on your PR, with its status column checked.
- NOTES record the selector choice and the 57-fit computability table.
- `nv2a_index.json` is regenerated if `psh.c` lines moved. Use the tests tree at
  `provenance.tests_commit` 6743b6a and pbkitplusplus e91d509.
- The PR has the lane template with its `Files:` line, preflight passes, and
  the PR is marked ready.
