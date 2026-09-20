# board-request: `lane.cloud-111` — #89 `status_note`, and a status correction

Written 2026-09-19 by `lane.cloud-111` at `master` `9472a18d33`, for issue
#111. Lanes may not edit `docs/testing/nv2a_issues.toml`
(`docs/testing/jobs/roles/lane.md`), so this is a request and not an edit.

**On the location.** The brief said to write this to
`$DISPATCH_DIR/board-requests/<lane>.md`. **A lane worktree cannot reach the
dispatch directory** — the sandbox confines writes to the worktree, and both
`ls /home/justin/hakux-work` and a write into
`/home/justin/hakux-work/dispatch/board-requests/` are refused. Tested, not
assumed. So this file is in the repo where it folds with the rest of the
lane, **and it is also posted as a `board-request` comment on #89**, which is
the route `roles/board.md:139` actually names ("Routing: apply `board-request`
comments"). The file is the record; the comment is the delivery.

---

## Request 1 (the one #111 asked for): append to #89's `status_note`

Verbatim text to append. Every figure in it is either a citation into this
tree at `9472a18d33` or a quotation from a prior judged verdict on this board.

> SEVERITY NOTE 2026-09-19 (lane.cloud-111, offline, no device), ANSWERING
> #111: the video-output path discards framebuffer alpha on hardware, and
> #111 infers that this residual "is invisible to a player and only matters
> where a later draw reads the surface back as a texture". THE PREMISE IS
> PLAUSIBLE AND UNCONFIRMED; THE INFERENCE IS TOO STRONG, and that half is
> checkable without hardware. DIRECT SCANOUT IS ONE OF FIVE CONSUMERS OF A
> COLOUR SURFACE'S ALPHA IN THIS TREE AND THE QUIRK EXEMPTS ONLY THAT ONE.
> The four it does not exempt, read at 9472a18d33: (1) DESTINATION-ALPHA
> BLENDING -- NV097_SET_BLEND_FUNC_{S,D}FACTOR_V_DST_ALPHA and their
> ONE_MINUS_ partners, decoded at pgraph.c:2855-2858 and :2896-2899 and
> mapped at vk/draw.c:316-318 and gl/draw.c:186-188, read the STORED
> destination alpha and multiply an RGB contribution by it, entirely upstream
> of the encoder; (2) THE SURFACE RE-SAMPLED AS A TEXTURE, vk/texture.c:1359
> and its call sites; (3) ALPHA TEST over such a sample, glsl/psh.c:281-284
> emitted at :3455-3460; (4) GUEST CPU READBACK, which is also how every
> golden in this harness is made. THE MAGNITUDE ON ROUTE 1 IS THE SEVERITY
> ARGUMENT AND IT IS THE OPPOSITE OF INVISIBLE: this residual is 141,125 of
> 307,200 px -- 45.9% OF THE FRAME -- carrying 0xFF000000 where the hardware
> golden holds 0x00000000, i.e. Ad = 1.0 where hardware holds 0.0. Under
> DST_ALPHA a later blended draw contributes IN FULL where hardware
> contributes NOTHING; under ONE_MINUS_DST_ALPHA the reverse. That is a
> presence/absence flip of a whole draw, in RGB, on screen -- not a shade.
> The channel is not theoretical: vk/draw.c:263-267 records that
> Blend_surface's swatches build result = S x Ad precisely to read Ad out of
> the framebuffer, and read 255 for DST_ALPHA and 0 for ONE_MINUS_DST_ALPHA.
> AND THE PAD OVERRIDE DOES NOT COVER THIS CASE, which is the part most
> likely to be assumed the other way: surface_sampled_pad_alpha()
> (vk/texture.c:1359) substitutes the format's pad constant only for PAD
> formats, and returns IDENTITY outright where
> pgraph_glsl_dual_src_pad_supported() holds (:1440-1443). Color zeta
> overlap's surface is A8R8G8B8 at all six SetSurfaceFormat sites in
> color_zeta_overlap_tests.cpp (:53, :199, :212, :234, :267, :292) --
> PAD_ALPHA_NONE, glsl/psh.c:254-266, taking neither branch -- so the alpha
> carrying this residual is a REAL GUEST-VISIBLE CHANNEL and not a pad bit in
> a field the format calls meaningless. THIS TREE DOES NOT MODEL THE QUIRK IN
> EITHER DIRECTION: the GL display shader is out_Color.rgba = texture(tex,
> texCoord) at gl/display.c:215 -- .rgba, not .rgb with a forced opaque alpha.
> IF #111 IS CONFIRMED, THE FIX IS AT THE DISPLAY STAGE ONLY (gl/display.c:215
> and the Vulkan display path). A fix that stops STORING alpha, or zeroes it
> earlier, regresses all four routes above; vk/draw.c:735-737 already records
> that reverting #59's clear stamp "restores a different defect" for exactly
> this class of confusion. THE BUCKET, STATED AS A BOUND RATHER THAN A VALUE:
> "one capture in 4,522" bounds WHAT THE CORPUS WOULD CATCH and is not a
> statement about titles, for two instrument reasons. The trigger -- two or
> more captures in suites PRECEDING the capture's own -- is a property of a
> TEST DISC's composition, and with the mechanism still unnamed and five
> candidates dead by their own falsifiers, nobody has derived what the
> equivalent state is in a running title or shown that a title reaches it.
> And the corpus has NO COVERAGE for the case that would cost most -- a
> DST_ALPHA blend over a region cleared under the trigger condition --
> Blend_tests (1,673 goldens) having no same-ref two-disc pair at all. So:
> NARROW WHERE MEASURED, UNKNOWN WHERE IT WOULD COST MOST, and #111 does not
> shrink it to zero in either place. THE HARDWARE RUN THAT WOULD SETTLE #111
> IS REGISTERED AND IS NOT AN ARM:
> docs/testing/predictions/2026-09-19-alpha-at-video-output.md. It cannot be
> an ab_compare arm -- every capture in this harness is a guest readback of
> surface memory and the video output is downstream of the framebuffer, so a
> registered .json would queue an arm that captured THE FRAMEBUFFER TWICE and
> reported a confident zero about a channel it never looked at. Full
> reasoning: docs/investigations/2026-09-19-alpha-at-video-output-severity.md.

## Request 2: #89's `status` and its GitHub state disagree with the tip

**Not a new measurement. A statement about the record, with every part
quotable.** #89 is closed on GitHub and its row reads `status =
"fixed-verified"`, and the 141,125 is live at the tip.

The row's own justification is: *"PR #102 merged with the pad-alpha-format
narrowing landed and its arm PASS (44/44, 42 of 42 captures byte-identical)
-- status set to fixed-verified."* That arm judged
`docs/testing/predictions/issue89-clear-pad-alpha-shape.json`, and that
prediction says, in its own first sentence and in its own words:

- *"**AN INERTNESS CLAIM, REGISTERED AS ONE.** This arm does not predict that
  #89's 141,125 moves; it predicts that **NOTHING** moves."*
- *"this change is a correctness narrowing, **NOT a fix for the 141,125**."*
- *"Swap_ZB is registered as must_not_move only, and on this disc it should
  read **141,125 in BOTH arms** … it doubles as a **positive control that the
  composition effect is present and untouched**. A leg reading '141,125 -> 0'
  would be a fit."*

PR #102's own per-issue table says the same: *"**#89** — Patch + arm PASS,
44/44, 42 of 42 captures byte-identical. **Untouched by this attempt.**"*

And the judged verdict itself (`[job.arms]` on PR #102, 2026-09-19T05:34:33Z)
reports `Color_zeta_overlap 9 caps, better 0 worse 0 same 9, differing A
387,179 differing B 387,179`, with *"every checked capture is byte-identical
between the arms."*

**A PASS on an inertness prediction is the strongest available statement that
nothing moved.** It was read into the tracker as a fix verdict. Byte-identical
between arms is not "the residual is gone"; it is "the residual is exactly
where it was".

`AGENTS.md` at the tip agrees and has not been corrected in the other
direction: *"the 141,125 is a live defect that appears once two captures have
run in preceding suites"*, *"MECHANISM IS NOT YET NAMED"*, *"Any surviving
candidate must be latched rather than graded"*.

**Requested:** `status` for #89 to a value meaning open-with-unnamed-mechanism
(the board owns the enum — `roles/board.md`'s own rule is that a gate must
offer a replacement for what it forbids, so this names the state and not the
word), a reopen on GitHub, and a `status_note` line recording that the #102
verdict was an inertness PASS. **I have not reopened it and have not touched
the row.** A lane may not edit the tracker and may not close or reopen an
issue; this is the board's call and the evidence for it is above.

**Why this is not cosmetic, and why #111 is the issue that surfaces it.**
#111's whole deliverable is a severity note on #89's residual. A severity
note attached to a row that says the defect is fixed and verified reaches
nobody: the row is out of every dispatchable view, and the next lane that
greps #89 finds `fixed-verified` and stops. Request 1 is worth having only if
Request 2 is acted on.

## What I did not do

- No tracker edit, no `territory.toml` edit, no issue closed or reopened.
- No `.json` prediction registered, so no arm is queued. Stated in the PR body
  as `Prediction: none: no arm` with the reason, per `roles/lane.md` item 4.
- No claim about #89's mechanism. It remains unnamed; five candidates are dead
  by their own pre-registered falsifiers and nothing here revives or adds one.
