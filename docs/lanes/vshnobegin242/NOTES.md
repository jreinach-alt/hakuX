# lane.vshnobegin242 -- #242: run the vertex program for a vertex sent outside Begin/End

Base: master @ 21946df29b. PR #245.

## What changed

`hw/xbox/nv2a/pgraph/pgraph.c`, `SET_VERTEX4F`: when slot 3 arrives with
`primitive_mode == PRIM_TYPE_INVALID`, after the usual
`pgraph_finish_inline_buffer_vertex` it calls
`pgraph_vsh_writeback_constants(pg)` and then `pgraph_reset_inline_buffers(pg)`.

- That is #234's CPU evaluator, unchanged. It runs only in program mode, and
  only when the pre-scan finds a constant write in the bound program. It runs
  the program for "the last vertex". With `inline_buffer_length == 1` that is
  the lone vertex, and every attribute is known from `inline_value`.
- Nothing is rasterised. The reset drops the vertex, which the next Begin
  (or an End with no Begin) would have done anyway. Before this change, lone
  vertices piled up in the inline buffer until the next Begin.
- The inside-Begin/End path is textually unchanged: the new branch is guarded
  on `PRIM_TYPE_INVALID`.

Scope: only `SET_VERTEX4F`, as the brief says. `SET_VERTEX3F` and the
`SET_VERTEX_DATA*_M` attribute-0 setters also finish a vertex and have the same
gap outside Begin/End. Nothing measured exercises them, so they are left
alone. A lane that finds a test sending those outside Begin/End should route
them through the same two calls.

## Do a lone vertex's position/varying outputs go anywhere on silicon?

Unknown, and not settled here. Exceptional Float reads only the constants back
over RDI, and nothing in nxdk_vsh_tests or nxdk_pgraph_tests draws with a lone
vertex and then measures pixels. So this change writes **only the constants**
and rasterises nothing. The evaluator already ignores o-register outputs
except as temporaries.

## Prediction (registered before any build or run)

### vsh, must move (request.sh --program vsh, scored by vsh_score.py; ab_compare refuses vsh results)

`Exceptional_Float/Float.txt` on Thor, b_ref `bd552105ed`, goes from all
`0.000000` (master; #242 cites `1790346001-vsh-2643051`) to the console's
`hardware/runs/2026-09-25-vsh/stage2/console`:

```
Inf, -Inf, NaN, -Nan:            inf, -inf, nan, nan
Max, -Max, Min, -Min:            3.402823e+38, -3.402823e+38, 0.000000, -0.000000
MaxSub, -MaxSub, MinSub, -MinSub: 0.000000, -0.000000, 0.000000, -0.000000
```

i.e. vsh_score IDENTICAL. `MAC_mov` stays IDENTICAL (it draws inside
Begin/End, and that path did not change).

The world in which this fails, and what it would mean:
- **All rows still 0**: the program did not run, or it ran and its write did
  not reach the bank RDI reads. The first could be the mode check (CSV0_D MODE
  != 2 when the lone vertex arrives), the pre-scan, or the evaluator bailing
  out. The second would be a different RDI bank.
- **Finite rows right, NaN/-0 rows different**: arithmetic. `-NaN` printing
  `-nan` where the console prints `nan` would mean the console canonicalises
  NaN on MOV or on RDI, and the emulator keeps the sign bit. Score the finite
  rows separately. A partial fix is a diagnosis, not a revert.

### pgraph, must not move

`docs/testing/predictions/vshnobegin242-must-not-move.json`: a_ref
`21946df29b`, b_ref `bd552105ed`. The legs are Degenerate begin end,
SetVertexData, Attrib setter, 3D primitive, Material color, Overlapping draw
modes, Vertex shader independence/rounding tests, W param and Fog gen. That is
a representative slice of `nv2a_index.py blast pgraph.c`, which names the
whole file. The prediction text says what would move each leg. No `.vsh` on
the pgraph disc writes a constant, so on that disc the only live effect is the
reset of a lone vertex's inline buffer.

## Checks done so far

- `pgraph.c` passes `-fsyntax-only` with the desktop build's own compile
  command, with this worktree's headers put first. The only warning is one
  that was already there (`pgraph_method_histogram_log_and_reset`).
- `nv2a_index.json` was regenerated because the edit moved 190 sites by 16
  lines. The tests tree was at the index's provenance commit 6743b6ab16, and
  the build used `--support ~/pbkitplusplus`. `check --tests` matches.
- Preflight passes on `a75312472b` (the head after the index commit).

## State at the end of attempt 1 (2026-09-25): WAITING

- vsh proof, self-queued on Thor (no `[job.arms]` comment will announce
  these): fix `1790347577-vshnobegin242-3252169` (ref bd552105ed), base
  `1790347581-vshnobegin242-3253522` (ref 21946df29b). Results land in
  `~/hakux-work/dispatch/results/<id>/`. Read `vsh*.txt`, check that
  `log_completed` is true and that no row is STALE or MISSING, and grep
  run1.log for `UtilAcceptVsock` before believing either one.
- pgraph arm: the arms job should queue `vshnobegin242-must-not-move.json`
  and post a `[job.arms]` verdict on #245. Read both arms' status columns
  for `unreadable`, and run1.log for PARTIAL COVERAGE.
- CI on the head.

The next attempt: judge both halves, post the verdicts on #245 and #242,
record them here, then `gh pr ready 245` if they are clean. If Exceptional
Float moves only partly, score the finite rows separately (see the prediction
above). Do not revert.

## Attempt 2 (2026-09-25, resumed by job.handback)

### Why attempt 1 did not finish

It ended on purpose, WAITING for the two vsh runs, the `[job.arms]` verdict
and CI. All three came back, but not cleanly. The arm was judged FAIL, so
the PR was labelled `regressed`. And master had moved 55 commits ahead, so
the PR had an `nv2a_index.json` conflict. A PR that does not merge gets no
CI run, which is why CI showed NONE on `f484395160`.

### vsh proof (Exceptional Float): 2 of 3 rows moved to the console's values

Both runs were on Thor `bdc158a5`, with `log_completed` true and
`log_stale` false. Neither run1.log contains `UtilAcceptVsock` or PARTIAL.

| row | console | base 21946df29b | fix bd552105ed |
|---|---|---|---|
| Inf, -Inf, NaN, -NaN | inf,-inf,nan,nan | 0,0,0,0 | **inf,-inf,nan,nan** |
| Max, -Max, Min, -Min | 3.402823e+38,-3.402823e+38,0,-0 | 0,0,0,0 | **3.402823e+38,-3.402823e+38,0.000000,-0.000000** |
| MaxSub, -MaxSub, MinSub, -MinSub | 0,**-0**,0,**-0** | 0,0,0,0 | 0,**0**,0,**0** |

MAC_mov is IDENTICAL in both arms.

So the lone vertex's program now runs, and its writes reach the bank that
RDI reads. The NaN row agrees too: the console prints `-NaN` as `nan`, and
so do we. The one remaining difference is arithmetic. A negative
**subnormal** input comes back as +0 here, while silicon keeps the sign
(-0). The flush-to-zero somewhere between the SET_VERTEX4F float and the
constant writeback drops the sign bit. Min/-Min are normal floats and do
keep it. This is outside this lane's scope, like #112 item 4's MUL/RCC
behaviours. It is reported on #242 for whoever takes the evaluator's
denormal handling.

### pgraph must-not-move arm: FAIL, read as device nondeterminism

`[job.arms]` FAIL, 4 of 403. The movers are all
`Vertex_shader_rounding_tests/GeometrySuperscreen_*`: 0.4999 went 0→400,
0.5000 went 400→0, 0.9990 went 285→0, 1.0000 went 0→285. Neither arm has any
`unreadable` status. Neither log has PARTIAL COVERAGE. The fix arm's run1.log
has 4 `UtilAcceptVsock` lines, all at lines 1-4, before any test ran.

To analyse it, I masked the label strip (rows 20-45) and matched every
fix-arm capture of that suite against every base-arm capture:

- 47 of 51 captures match their own base capture.
- In the **base** arm, which is master without the patch, one stray image
  shows up in each half of GeometrySuperscreen, at 0.5000 and at 0.9990. It
  matches no other test's image.
- The **fix** arm has the same two stray images, identical byte for byte
  outside the label, one test earlier or later: at 0.4999 and 1.0000.
  The tests where the base arm had them now render the normal image.
- No earlier scores1.tsv on the host has a nonzero GeometrySuperscreen row.
  That covers 11 runs, from vshconst and xbox-region200 to the 090/091
  sweeps.

Master renders the stray frame without the patch, and the patch cannot run on
this disc (no constant writes). So the patch did not cause the frame. It
changed at most which test caught it. One run per arm cannot separate those,
as ab_compare's own byte-level block says. I re-registered at 3 runs per arm
instead of reverting: `vshnobegin242-must-not-move-runs3.json`, issue 242,
a = master `a8691063e6`, b = merge `6e3b1aff8b`. Under arms.sh's
supersession-by-issue rule, it supersedes the single-run FAIL once it is
judged.

If the 3-run arm still shows GeometrySuperscreen moving outside its band,
the next lane should find out where the stray frame comes from. It first
appeared in both arms of this pair, and never before. Candidates: a timing
or capture race, or something that landed in master between the 090/091
sweeps and 21946df29b (#224's flat-quad diagonal split is the obvious
suspect for a rounding-boundary test). Do not revert #242 for it.

### Merge

I merged `origin/master` into the branch, without rebasing, because the old
prediction names bd552105ed. The only conflict was `nv2a_index.json`. I
regenerated it over `~/nxdk_pgraph_tests` @ 6743b6ab16 (the provenance
tests_commit) with `--support ~/pbkitplusplus`. `check` matches.

### State at the end of attempt 2: WAITING

- the `[job.arms]` verdict on `vshnobegin242-must-not-move-runs3.json`. Read
  the NOISE column for GeometrySuperscreen, `unreadable`, PARTIAL COVERAGE.
- CI on the merged head.
Once both are clean: `gh pr ready 245`.
