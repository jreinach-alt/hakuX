# Audit pass 1 -- PR #269 (lane.remote, #109): Vulkan stages a swizzled surface at width * bpp on the CPU paths

**Auditor** `job.cloud` (audit record only; claims no files).
**Subject** PR #269, branch `claude/docs-tooling-agentic-coding-u152m1`, head
**`b411c403`**. CI at audit time: `build` pass (x2), `check` pass; mergeable
`clean`.
**Date** 2026-09-25.
**Record** `docs-tooling-agentic-coding-u152m1-pr269-pass1.md`. The brief named
`...-u152m1-pass1.md`, but that file on this branch is PR #247's pass-1 record
(the GL half of #109). This branch carries several PRs, so this record takes
the `-pr269-` suffix, as PR #256's did, and #247's record is left as it is.

**0 HIGH. 0 MEDIUM. 2 LOW.** Verdict: `fold-ready`. Neither LOW is a defect
the diff introduces, so pass 2 has nothing to verify.

The code change is `hw/xbox/nv2a/pgraph/vk/surface.c` (+33 -7): a
`swizzle_linear_pitch(width, bpp)` helper and three call sites that use it.
The rest of the diff is four predictions, the lane's `NOTES.md`, a forcing
script under `docs/lanes/remote/`, and a regenerated `nv2a_index.json`.

## What I checked and found correct, so pass 2 does not re-derive it

* **No new overflow on any of the three staging buffers.** This was the
  question most likely to produce a HIGH: moving a buffer's row stride from
  `pitch` to `width * bpp` makes it bigger whenever `pitch < width * bpp`,
  which is exactly the case being fixed.
  - Deferred completion (`pgraph_vk_complete_staged_downloads`): the buffer is
    now `g_malloc(linear_pitch * dl->height)`, and `memcpy_image` and
    `swizzle_rect` both use `linear_pitch`, so it is exactly the size they
    touch. Before the change it was `pitch * height` with a `width * bpp`
    last row, which is the over-read the PR describes. It is fixed, not moved.
  - Synchronous download (`download_surface_to_buffer`) and upload
    (`pgraph_vk_upload_surface_data`): both CPU buffers are
    `g_malloc(surface->size)`. `surface->size` is set in one place
    (`vk/surface.c:3376`) as `height * MAX(pitch, width * bpp)`, so it is at
    least `width * bpp * height` for every pitch. The new stride fits.
* **The source and destination strides are the right ones.**
  `memcpy_image(dst, src, dst_stride, src_stride, h)`. In each site only the
  linear buffer's stride changes. The staging side stays at `width * bpp`
  (tightly packed, as it already was). The upload's final
  `memcpy_image(mapped, gl_read_buf, width * bpp, buf_pitch, h)` reads
  `buf_pitch`, which is `width * bpp` for the CPU unswizzle and still
  `surface->pitch` for a linear surface read straight from VRAM.
* **Linear surfaces are untouched.** The sync download picks `surface->pitch`
  when `!surface->swizzle`. The upload initialises `buf_pitch` to
  `surface->pitch` and changes it only inside `surface->swizzle &&
  !use_compute_to_unswizzle`. A partial download (`pixels += row_start *
  pitch`) exists only for `!surface->swizzle`, so it never meets the new
  stride.
* **The three sites are all the CPU swizzle sites in `vk/surface.c`.** Grep
  of `swizzle_rect(` / `unswizzle_rect(` under `pgraph/vk/` gives these
  three plus `texture.c:373`, which is the texture path and is not #109's
  surface defect.
* **The case the helper comment half-covers is covered.** A 4-byte swizzled
  surface with a D24S8/D32S8 host format takes the CPU upload
  (`use_compute_to_unswizzle` is false). The fix covers it too, because the
  branch is keyed on `!use_compute_to_unswizzle` and not on bpp.
* **The extent sites are left alone on purpose.** `surface_vram_written(...,
  pitch * height)` and the dirty-range sites still use `pitch * height`. The
  PR's "Not covered" hands that to lane.xbox as #109's silicon question. It is
  not a regression of this diff.
* **The predictions are consistent with the tree.** `b_ref` `3f3fe35b` is an
  ancestor of the head. `git diff 3f3fe35b b411c403 -- hw/` is only #242's
  `pgraph/pgraph.c` (the master merge), so `vk/surface.c` at `b_ref` is what
  folds. The unforced registration is an honest inert claim: it has
  `must_not_move: ["*"]` and `better = worse = 0`, and the measured row count
  (238/238) says it ran. It does not open an empty `expect` and call that a
  pass. Each forced registration has one named `expect` leg
  (`Surface_pitch/Swizzle = 0`), and its must_not_move covers the other seven
  suites.
* **The forcing script cannot reach the emulator by accident.** It is under
  `docs/lanes/remote/`. It edits the working tree only when someone runs it,
  and every replacement asserts `count == 1`. Nothing in the diff builds it
  or imports it.
* **The index regeneration is mechanical.** Only 50 `loc`/`line` values move,
  plus `emulator_commit` and the two checkout paths. `tests_root` /
  `pbkit_roots` are provenance fields, and their host-path value has changed
  back and forth before (`78ef3ced`, `93bc128f`). CI `check` is green.

## Findings

### LOW-1 -- the forced arms name a patch that is not in the tree

`docs/lanes/remote/v109_force_paths.py` and the forced predictions'
`$SCRATCH/p109/v109_forcing.patch` (sha256 `39537fdc...`) are two statements
of the same forcing. Nothing ties them together. A re-run from the committed
script cannot show that it produced the patch the verdicts were measured
with.
*Failure scenario:* someone edits the script later, re-runs a forced arm and
gets a different Swizzle count. They cannot tell whether the fix regressed or
the forcing changed.
*Suggested:* record in `NOTES.md` the sha256 of `git diff` after running the
script on `5807b54f`, next to the patch's sha. This does not block the fold.

### LOW-2 -- `swizzle_linear_pitch()` is a one-line multiply

It is `return width * bytes_per_pixel;`. The name and its comment carry the
reasoning, and the GL half (#247) did the same, so the two back-ends read
alike. This is a style note, and there is no failure scenario.

## Not a finding

* **`defer` A not identical with itself** (one pixel of Swizzle across its two
  runs). The PR names this in advance as A's last-row over-read, which reads
  whatever lies past a `pitch * height` buffer. That is the defect this diff
  removes.
* **`Blend_surface/R5G6B5_Add_SrcA_DstA` moved in master's run only.** It
  moved in A only, so it cannot come from B's change. It is outside this PR's
  scope. The lane can raise a `KNOWN_UNSTABLE` candidate separately if it
  recurs.
