# #60 on the campaign branch: a live 31,436 px regression, and one line recovers 23,244 of it

The campaign tracker's `[issue.60]` entry says the port "is faithfully
present", that "nothing judges it and the device lane cannot -- it is
Vulkan", and names the arm it needs: *"a105a51a00 against its parent on the
GL lane, predicting that no capture moves at all, which is a real falsifier
of the format-table audit."*

This lane holds the GL renderer as a capability, so it is the only one that
can run it. It has been run. Predictions were registered first, in
`../testing/predictions/issue60-campaign-refresh-arm.json` and
`issue60-with-issue71-prerequisite.json`, and both are scored below
including where they were wrong.

## The specified arm is inert, and cannot falsify anything

`a105a51a` against its parent `1a879e56`, two runs each, byte-compared:
**0 of 44 captures moved.**

The tracker's prediction is correct and the arm is worthless as a test.
`a105a51a` is **+104 lines, 0 deletions** — it adds the `drawn_format` field
and populates it. The read side is a *separate, later* commit, `082bc0ac`,
which swaps eight `surface->shape.color_format` reads for
`pgraph_gl_surface_drawn_format(surface)`. A pure addition cannot change
behaviour until something reads it, so this arm is inert by construction,
not by evidence about the format table.

**My own prediction on this arm was refuted, and the reason is a process
error worth recording.** I registered three captures moving, because I was
predicting the behaviour of the *pair*. I did not read the named commit's
diff before registering. `+104/-0` is visible in one `git show --stat` and
would have told me the arm could not move anything.

## The pair is not inert: three captures, +31,436 px

`082bc0ac` against `a105a51a` — i.e. the read side alone — and equally
against `1a879e56`, since the write half does nothing:

| capture | before | after | delta |
|---|---:|---:|---:|
| `Blend_surface::ARGB8_Add_SrcA_1-SrcA` | 9,547 | 22,910 | **+13,363** |
| `Blend_surface::ARGB8_Add_SrcA_DstA` | 11,521 | 21,402 | **+9,881** |
| `Blend_surface::DstAlpha_XA_O1A7RGB8` | 81,920 | 90,112 | **+8,192** |

Net **+31,436 px**. Two runs per arm, all four arms 44/44 byte-stable
against their own repeat, so none of this is the noise band.

Those `before` values — 9,547 / 11,521 / 81,920 — are **identical** to the
ones this lane measured at `d662ba2b` with a runtime switch, across 599
commits of drift. The figure reported then was "4 worse, +31,948 px"; the
fourth was `Surface_pitch::Swizzle` at 512 px, which is inside that
capture's noise band and carries no number. Three and 31,436 is the real
claim, and it was corrected in the registration *before* this arm ran rather
than after.

## The ordering note is right, and now bounded

`territory.toml`'s `lane.remote` note says **"#71 before #60"**, because
#60's refresh flips thirty surface-to-texture decisions from false to true
into a path that was wrong for every format exercising it.

**The campaign branch does not carry #71's fix.** `f75a4aad` is not an
ancestor of it, and `min_filter = 0xFFFFFFFF` appears **zero** times in its
`gl/surface.c`. So it is holding #60 in exactly the configuration the note
warns about.

Applying `f75a4aad`'s **single added line** on top of `082bc0ac` — nothing
else — and re-running:

| capture | parent | #60 landed | #60 + one line |
|---|---:|---:|---:|
| `ARGB8_Add_SrcA_1-SrcA` | 9,547 | 22,910 | **9,547** |
| `ARGB8_Add_SrcA_DstA` | 11,521 | 21,402 | **11,521** |
| `DstAlpha_XA_O1A7RGB8` | 81,920 | 90,112 | **90,112** |

Disc total over the 44 captures: **1,203,109 → 1,234,545 → 1,211,301.**

**Two of the three close completely** — back to the exact parent value, not
merely improved, which is more than was predicted. **One does not move at
all**: `DstAlpha_XA_O1A7RGB8`, +8,192 px.

That residual is the capture and the number this lane has repeatedly
attributed to **#59's pad-alpha semantics**, and it is now reproduced on the
campaign's own commits rather than on this lane's tree.

**The second prediction was partly refuted too.** It said all three would
shrink, `expect_counts {better: 3, worse: 0}`. Actual: **2 better, 1
unchanged, 0 worse**. The registration did hedge that "if a second reason
remains, the captures improve without closing" — but it still put three in
the count, and one of the three never moved.

## What follows

* **The campaign branch should take `f75a4aad`.** Without it, #60 is a live
  31,436 px regression there; with it, 8,192 px on one capture, attributable
  to #59.
* The arm named in the tracker should be replaced with `082bc0ac` against
  `1a879e56`. As written it tests a pure addition.
* #60 is not blocked on this lane. It is blocked on #59's pad alpha, and
  that is one capture.

## Coverage, registered before the result

**#66's assert is live on the campaign branch**, so every run there stops at
**44 of 236 captures** with `QEMU_EXIT=134` —
`gl/shaders.c:413: Assertion 'glGetError() == GL_NO_ERROR' failed`. All
three movers are inside the 44, so every leg above is testable; nothing
outside them is. `fada1d89` is what makes the full disc runnable and it has
not been folded either.

Three landed fixes from this lane are missing on the campaign branch --
`fada1d89` (#66), `f75a4aad` (#71) and the #60 read-side ordering they
imply. The first is why that branch cannot measure its own GL renderer at
all.
