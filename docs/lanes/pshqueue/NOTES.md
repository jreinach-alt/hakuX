# lane.pshqueue

Brief: land the queued glsl/psh.c hunks for #278, #279, #285, #315 and #271,
one commit and one prediction each, so a failing arm names one hunk.
Base: master @ 336b0728f2 (still the tip at registration; no rebase needed).

## What landed, and what did not

| issue | commit | hunk source | state |
|---|---|---|---|
| #279 DOT_ZW | 24546d197b | docs/lanes/cloud-279/NOTES.md "The hunk, for a grant" | committed, `pshqueue-279-dotzw.json` |
| #285 G8B8 | a389648b0b | docs/lanes/g8b8285/g8b8-bswap.diff (psh.c + psh.h) | committed, `pshqueue-285-g8b8.json` |
| #315 BRDF | e3b13f5b45 | docs/lanes/brdf315/brdf315-psh.diff | committed, `pshqueue-315-brdf.json` |
| #278 fog INF | none | docs/lanes/cloud-278/NOTES.md "The hunk to grant" | **not landed: needs glsl/vsh.c** |
| #271 X1A7 read | none | docs/lanes/x1a7271/x1a7-read-side.diff | **skipped: vk/texture.c is lane.remote's (PR #343)** |

Each prediction's a_ref is its hunk's parent commit, not master, so each arm
measures one hunk: 279 is 5d23f1fec8..24546d197b, 285 is
24546d197b..a389648b0b, and 315 is a389648b0b..e3b13f5b45. runs_per_arm is 2
(added by hand, as in texvol283-bytes16.json; `--register` has no flag for it).

### #278 needs vsh.c, which the brief did not grant

cloud-278's hunk has **two** sites. psh.c `append_fog_factor` exempts
`vtxFogSpecial > 1.5 && fogParam.y == 0.0`, and vsh.c:944-949 must set
`fogSpecial = 2.0` for INF, apart from NaN. With the psh.c half alone,
`vtxFogSpecial` is never 2.0, so the exemption never fires and the hunk
is inert. That half is not a partial fix. glsl/vsh.c is held by
lane.nanfix281 (PR #336, territory `[lane.nanfix281]`). A board request asks
for vsh.c to be lent for the four-line flag hunk, or for #278 to be routed to
lane.nanfix281 to carry both halves. The prediction legs are ready in
cloud-278's NOTES ("Prediction legs for the lane that takes the grant").

## Checks made before registering

- `syntax_check.py`: `-fsyntax-only` with the desktop build's own compile
  line on this worktree's psh.c (and its psh.h, which it includes from its own
  directory). Returns 0 after each of the three hunks.
- No GLSL compiler exists on this host (no glslangValidator, and no glslang
  standalone in build-desktop), so the device arm is the GLSL compile. What
  was checked by reading:
  - #279: `zvalue`/`zfloor` are mutable `precise float`s declared in `clip`,
    only under `depth_needed`, the same gate as the hunk. `clip` is emitted
    before `vars` (psh.c `final` assembly), and `dot<i-1>` is a `float` from
    the DOTPRODUCT stage that `stage_consistent(..., 1)` requires.
  - #285: the swap goes after the #59 pad block, which is the last writer of
    `fragColor`. The uniform is staged in the shared
    `pgraph_glsl_set_psh_uniform_values`.
  - #315: a non-3D BRDF stage sets `tex_unusable`, and psh.c:2944 checks that
    flag before any stage samples, so `texSamp<i>` is never read undeclared.
- `mode_users.py`: DOT_ZW is named only in pixel_shader_tests.cpp, BRDF only
  in texture_brdf_tests.cpp, and B8/G8B8 surfaces only in surface_format and
  surface_clip. That bounds what each hunk can move, and the must_not_move
  legs cover each suite that is reachable.
- `git merge-tree` against PR #268 (lane.wbufdepth24, D24 write): psh.c
  merges clean. The G8B8 insertion is about 55 lines above the D24 case and
  does not touch it.

## Scores at a_ref's binary (latest arms on disk, thor, 8e683b3a26)

| capture | differing | predicted after |
|---|---|---|
| Pixel_shader/DotZW | 65,536 | <= ~137 |
| Surface_format/Fmt_G8B8 | 32,552 | <= ~100 |
| Surface_format/Fmt_B8 | 16,144 (label-differs) | down by its quad pixels |
| Texture_BRDF/BRDF_e0_l0, _e0_l1, _e1_l0 | 614 each (blank) | <= 30 each; (639,479) = (198,246,222,255) |

`expect` is an exact match in `ab_compare.judge`, so the "at most" ceilings
can't be machine legs. Each file checks `better=N, worse=0` with every other
capture in its disc under must_not_move. The ceilings are in the prose, and
the verdict's magnitudes are read against them. A must_move that lands well
above its ceiling refutes that hunk's model and is reported, not tuned.

## For the next lane

- Do not apply cloud-278's psh.c half alone. It is inert without the vsh.c
  flag (see above).
- `--register` cannot set runs_per_arm. Add it to the JSON before committing.
- `latest_scores.py SUITE_DIR ...` prints the newest scored rows on disk per
  result directory, which is enough to date a baseline before registering.

## State at end of session 1 (2026-09-25): waiting on three arms

Waiting on the arms job's `[job.arms]` verdicts for pshqueue-279-dotzw.json,
pshqueue-285-g8b8.json and pshqueue-315-brdf.json on PR #347, and on CI for
the head. On resume: read each verdict's magnitudes against the ceilings above,
drop any hunk whose arm refutes it (by revert commit, not rebase), cite the
verdicts in the PR body, then mark the PR ready. A board request
(board-requests/pshqueue.md) asks for vsh.c for #278 and for the [free] psh.h
entry that fails check_territory.
