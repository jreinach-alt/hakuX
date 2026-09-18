# lane.remote hand-off, 2026-09-18 (orchestration Phase 0 wind-down)

Written at the orchestrator's wind-down request: preserve, do not decide.

## Where the work is

- Branch `claude/docs-tooling-agentic-coding-u152m1`, tip `4c3364bcb1c1`, every
  commit pushed and verified against `origin`; 77 commits ahead of the
  campaign merge-base `8c5218af`. Every subject since the four bare commits
  the board already knows about carries `[skip ci]`.
- **Not pushed to `origin/lane/remote`.** This session may push only to its
  own branch and cannot take that instruction from a peer session. The owner
  reproduces it in one command: `git push origin 4c3364bcb1c1:refs/heads/lane/remote`.
- Audit state: pass 2 clean; M1/M2/L8 remediated in `4c3364bc`; N1-N6 fixed
  in `ecf6e53c`; the x87 checker runs on any tree since `cff75d42`.

## Issues

| issue | state | note |
|---|---|---|
| #82, #66, #71, #51 | closed this week | all fixed-unlanded: on this branch, not the campaign branch |
| #85, #86, #87, #88 | filed this week | #87 and #88 carry measurements, the others patch shapes |
| #34 | live, out of scope | four findings in `vk/*`, the device confirmation is APK packaging in `android/`; neither is this lane's |
| #39 | live, device symptom | desktop reproducers stale (25 runs, 1,402 captures, no variation); the skew-bound result is on the tracker |
| #60 | live, blocked | needs `gl/surface.c` (not held) and #59's pad alpha; one capture, +8,192 px |
| #62 | live, blocked | finding 2 needs `gl/surface.c` (not held) and an Android build |
| #86 | live, not started | Android-only code in `gl/shaders.c`; no NDK here; the patch shape is on the issue |

## Requested and not held: `gl/surface.c`

Asked for on the wind-down; held by lane.swizzle87 with `vk/texture.c` as one
claim. With it this lane would have: removed the dead `mem_dirty` arm of the
surface-upload gate (#85, correct by construction, measurable as inert on the
surface disc); landed #62's finding 2 as `android_surface_to_texture_needs_guest_reinterpretation()`
returning true for R5G6B5 so the replicating CPU path is taken (Android-only,
type-checkable here, not buildable); and held #60's refresh until #59 lands.

## Open on PR #45, superseded

Which two commits failed the orchestrator's trial fold. The design session
answers it by merging the branch; a full in-order replay onto `19389908e4`
conflicted on nine commits, listed on PR #45, and `gate.sh` / `gl/blit.c`
applied cleanly.

## Ephemeral artefacts on this container

Capture sets under `/tmp/pgraph-run/score_{i66head,i71vk,i66n,cubeBaseGL,cubeBaseVK,cubePost2GL,cubePost2VK,surfPost2GL,surfPost2VK}`,
the crash backtrace at `/tmp/pgraph-run/cubePostVK_crash_backtrace.txt`, and
the desktop build. All reproducible from `docs/testing/desktop-runs.md` and the
scripts in `docs/testing/`; nothing here is the only copy of a number.
