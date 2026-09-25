# #266: 24-bit depth on the W-buffering suite's FloorQuad family, about 1.5 M structural px with no owner

Lane: wbufdepth24            Issue: #266
Base: origin/master
Files: docs/lanes/wbufdepth24/**, docs/testing/predictions/wbufdepth24-*.json. **No emulator code
yet.** When the mechanism is named and priced, ask the board for the file(s) with a comment on #266
starting `` `[lane.wbufdepth24]` grant request: ``. `glsl/psh.c` is held by lane.wbuf31sel (#31);
coordinate through the board.
Needs device: yes (Thor and Nova runs of the W buffering suite). Needs NDK: no.

## What is known (read #266 first)

From PR #222's fix arm `1790321693-arms-wbuf31fix-fix-301236` (Thor; #222's rule is on master as
`3d3a646f8e`), the W buffering suite has **1,955,022 structural px**. #31 owns the TriV family
(105,628). The rest has no owner. The largest parts:

- **ZBuf24D FloorQuad:** 874,418 over 16 captures, **0 exact**. 6 of those are tagged
  `white-content`.
- **WBuf24D FloorQuad, two `blank` captures** (`V0_ZB0_ZS1`, `V0_ZB1_ZS1`): 460,868.
- WBuf24F FloorQuad 158,050; ZBuf24D WallQuad/RoofQuad 277,308 (incl. `label-differs`).
- **Controls:** every 16-bit format, and ZBuf24F, are nearly exact on the same geometry.

About 1.06 M of the structural px are in captures the scorer tags `blank` / `white-content` /
`label-differs`. Since toolsmith's defect 0, arm verdicts treat those as void, which is partly why
nobody chased them.

## The job

1. **Re-measure at master, on both handhelds, twice each** (`bash docs/testing/request.sh --suites
   "W buffering" --device thor|nova --runs 2 --ref <sha> --no-expect "#266 baseline"`).
   - Are the two blank captures blank on both devices, every run? That is a real, large failure: the
     draw is missing or cleared.
   - Are the `white-content` rows real renders, or capture artifacts? Compare the PNGs with the
     goldens.
   - Read the test source (`w_buffering_tests.cpp` in the tests tree at 6743b6a) for what `V0/V1`,
     `ZB0/ZB1`, `ZS0/ZS1` and the `_ZB` suffix select.
2. **Classify.** For each family (format × geometry × variant), find where on the quad the pixels
   differ: the far edge, near edge, a band, or everything. Find which way they differ: depth-test
   pass/fail flips, or colour. Say whether one mechanism explains the 24-bit rows and not the 16-bit
   ones.
3. **Name and price mechanisms offline before writing C,** as lane.wparamgeom223 did on #223 (PR
   #246). Candidates to test, not assume:
   - 24-bit fixed-point depth quantisation of interpolated z on steep slopes (D24 on the host
     versus the hardware's integer depth);
   - the depth clear or compare rounding at 24 bits;
   - the Z/W-scale or bias constants for 24-bit formats;
   - a draw or clear path that leaves a blank surface for the two `ZS1` variants.

   **Re-derive the premise from the test source and the captures,** not from this brief (host
   memory: a brief premise taken from NOTES is a claim).
4. **Report on #266:** the families and their mechanisms, with numbers. Name the kill condition for
   each. Where one mechanism is clear, request its file(s), register a prediction (after your last
   merge), and fix with an arm. Use the 16-bit rows and ZBuf24F as `must_not_move`, and check the
   status column for `unreadable` before trusting a verdict.

## Do not

- **Touch #31's TriV/ClipF rule or `psh.c`'s slope-offset code.** That is lane.wbuf31sel's.
- **Score a desktop capture against these goldens.** The host renderer decides depth edge cases
  differently.
- **Trigger CI as a self-check.**

## Done when

- #266 carries the classified breakdown and at least one named, priced mechanism (or a stated
  refutation of each candidate).
- NOTES are written.
- A PR with the lane template (analysis, or the fix and its arm) is marked ready.
