# lane.cloud-111 — alpha dropped at video output, and what it is worth to #89

Issue #111. Cloud lane, no device, no code change. Base `master`
`9472a18d33` (the brief named `5d573d21cb`; the branch was fast-forwarded to
the tip before any work, `rev-list --left-right` first).

## The headline

**#111's premise is fine. Its inference is too strong, and the correction is
checkable offline.**

#111 says: if alpha never reaches the encoder, #89's residual "is invisible
to a player and only matters where a later draw reads the surface back as a
texture."

Direct scanout is **one of five** consumers of a colour surface's alpha in
this tree, and the quirk exempts only that one. Texture readback is not the
only survivor — it is the *second*. The first is the blend unit:
`DST_ALPHA` / `ONE_MINUS_DST_ALPHA` (`pgraph.c:2855-2899`,
`vk/draw.c:316-318`, `gl/draw.c:186-188`) read the **stored** destination
alpha and multiply an **RGB** contribution by it, wholly upstream of the
encoder.

The magnitude is what makes this a severity argument rather than a
technicality: the residual is `Ad = 1.0` where hardware holds `0.0`, over
141,125 of 307,200 px — **45.9% of the frame**. Under `DST_ALPHA` a later
blended draw contributes in full where hardware contributes nothing; under
`ONE_MINUS_DST_ALPHA` the reverse. Presence/absence of a whole draw, in RGB.

And the pad-alpha override does not blunt it. `surface_sampled_pad_alpha()`
(`vk/texture.c:1359`) substitutes the pad constant only for pad formats, and
returns `IDENTITY` outright where `pgraph_glsl_dual_src_pad_supported()`
holds (`:1440-1443`). `Color zeta overlap` is `A8R8G8B8` at all six
`SetSurfaceFormat` sites — `PAD_ALPHA_NONE`, `glsl/psh.c:254-266` — so this
residual sits in a **real guest-visible channel**, not in a pad bit.

## Files

- `docs/investigations/2026-09-19-alpha-at-video-output-severity.md` — the
  five-consumer enumeration with citations, what confirming #111 would and
  would not license changing, and the severity stated as a bound.
- `docs/testing/predictions/2026-09-19-alpha-at-video-output.md` — the
  hardware test: three programs, what each model predicts for the video
  capture, and the void program named so nobody runs it.
- `docs/lanes/cloud-111/board-request.md` — the `status_note` text for #89,
  plus a status correction (below). Also posted as a `board-request` comment
  on #89.

## Two things found that were not in the brief

**1. #89 is closed and `fixed-verified` while the 141,125 is live at the
tip.** Not a new measurement — a statement about the record, every part
quotable. The row credits PR #102's arm PASS. That arm judged
`issue89-clear-pad-alpha-shape.json`, whose own first sentence is *"AN
INERTNESS CLAIM, REGISTERED AS ONE … it predicts that NOTHING moves"*, which
registers `Swap_ZB` as a **positive control that the residual is still
there**, and whose verdict reports `Color_zeta_overlap … differing A 387,179
differing B 387,179`, byte-identical between arms. A PASS on an inertness
prediction says the patch changed nothing; it was read as a fix verdict.
`AGENTS.md` at the tip still calls the 141,125 live with an unnamed
mechanism. Requested of the board; **not acted on by me** — a lane may not
edit the tracker and may not reopen an issue.

This is why it matters to #111 and not just to bookkeeping: a severity note
on a row marked fixed-and-verified reaches nobody.

**2. This question cannot be an `ab_compare` arm, so no `.json` is
registered.** Every capture in this harness is a PNG the *guest* writes by
reading surface memory; the video output is downstream of the framebuffer and
the guest cannot read back what the RAMDAC emitted — on hardware or here. A
registered `.json` would queue an arm that captured **the framebuffer twice**
and returned a confident zero about a channel it never looked at. The
prediction is a `.md`, in the shape `lane.cloud-110` used for the same wall
(`docs/lanes/cloud-110/NOTES.md`). PR body says `Prediction: none: no arm`
with that reason.

## What the next lane should not repeat

- **Do not test #111 with a flat cleared field.** Both models predict the
  same picture. The prediction file names it "the void program". The pair
  `SCF_X8R8G8B8_Z8R8G8B8` / `_O8R8G8B8` is that program made informative,
  because it holds RGB byte-identical while alpha moves — and even then it is
  limited by the capture's noise floor, which is why the colour-key program
  (binary: overlay shows or does not) is the real discriminator.
- **The framebuffer half of the control is already on disk.** `vk/draw.c:705-726`
  records `Clear::TestSurfaceFmt` hardware goldens: `_O8R8G8B8` vs
  `_Z8R8G8B8`, **98,342 px differ, RGB IDENTICAL, alpha 255 against 0**,
  across all six clear colours. A hardware session only needs the
  video-output half.
- **The hardware cursor does not discriminate.** NV-class cursor blending
  uses the *cursor's* alpha, not the framebuffer's. Named in the prediction
  so nobody spends a program on it.
- **If #111 is confirmed, fix it at the display stage only.** Stopping the
  storage of alpha, or zeroing it earlier, regresses all four non-scanout
  routes. `vk/draw.c:735-737` already records this shape of error: reverting
  #59's clear stamp "restores a different defect".
- **PVIDEO colour keying ignores alpha in this tree at two sites**
  (`gl/display.c:221`, `vk/display.c` `& 0xFFFFFF`) and **nothing on this
  board sources it**. It is either a second instance of #111's premise or a
  defect of its own. The prediction's P2 tests exactly that line.

## Blocked / not done

Nothing in the brief is undone. `DONE WHEN` was "the board-request file for
#89 exists with the severity reasoning, and a prediction file for the
hardware test exists" — both exist.

One deviation, stated: the brief named
`$DISPATCH_DIR/board-requests/<lane>.md` as the board-request's location. **A
lane worktree cannot reach the dispatch directory** — writes are confined to
the worktree, and both `ls /home/justin/hakux-work` and a write into
`/home/justin/hakux-work/dispatch/board-requests/` are refused. Tested, not
assumed. The request is in-repo at `docs/lanes/cloud-111/board-request.md`
and posted as a `board-request` comment on #89, which is the route
`roles/board.md:139` actually names.
