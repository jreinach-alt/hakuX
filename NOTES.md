# lane.blit84 -- #84: BLEND_AND and the destination's bytes-per-pixel

## The headline: the brief's code change is already in master

The brief asked me to make `perform_blit()`'s `BLEND_AND` branch honour
`bytes_per_pixel`. **That work landed before this lane started**, and my base
`a1691ae68e` already contains it:

| commit | what it did |
| --- | --- |
| `9db71ddcb2` | threads `bytes_per_pixel` into `perform_blit()` and returns early in the leaf when it is not 4 |
| `3c4892563b` | moves the deciding guard up to `pgraph_vk_image_blit()`, before any surface bookkeeping is committed; keeps the leaf guard as a backstop |
| `bb9e8672c1` | fold of lane/blit38, which carried both |

Both are ancestors of HEAD (`git merge-base --is-ancestor` confirms). The
sibling renderer was fixed the same way by `b9d845d316`
(`hw/xbox/nv2a/pgraph/gl/blit.c:69`), so neither renderer can reach the 32bpp
indexing with a narrow format any more.

I checked that the guard is actually complete rather than assuming it:
`pgraph_vk_image_blit()` is the only caller of `perform_blit()` and
`perform_blit_tiled()` in the file (call sites at `vk/blit.c:395`, `:639`,
`:646`, `:660`, `:669`), and all four are downstream of the entry guard at
`:499`. `patch_alpha()`/`patch_alpha_tiled()` also hard-code `*4`, but they run
only under `needs_alpha_patching`, which is set for `LE_X8R8G8B8` and
`LE_X8R8G8B8_Z8R8G8B8` only -- both 32bpp -- so their constant is correct.

**The issue can be closed on the mechanism.** What follows is what I found that
is not closed, and why I did not write code for it.

## Why the brief's literal goal should not be done: BLEND_AND is not a byte blend

The obvious generalisation -- "blend `width * bytes_per_pixel` bytes instead of
`width * 4`" -- is wrong, and it is worth writing down why, because it is the
first thing anyone picking this up will try.

`BLEND_AND` **does not blend the fourth byte of each pixel.** The NEON path
restores it from the destination with a `vbslq_u8` mask of
`{0,0,0,0xFF, ...}` (`vk/blit.c:232-235`) and the scalar path loops
`for (ch = 0; ch < 3; ch++)` (`vk/blit.c:243`). So the branch is not a per-byte
operation with a byte count; it is a per-pixel operation with a 3-of-4 channel
structure baked into it. There is no substitution of `bytes_per_pixel` for the
constant `4` that carries that structure to a 1-byte or 2-byte format.

For `LE_R5G6B5` the landed comment's reason already stands: a correct blend must
unpack 5/6/5, blend and repack, and the repack's rounding rule is not
established by anything measured -- #38's 2^24 exhaustive covers 8-bit channels
only.

For `LE_Y8` I thought there was a case for implementing it, since a single
8-bit channel is exactly the domain #38 measured exhaustively, so the blend
itself would invent nothing. **The 3-of-4 structure is what defeats that.** The
question a Y8 blend has to answer is not "what is the arithmetic" but "is this
byte a channel BLEND_AND touches, or the one it preserves", and nothing in the
corpus answers it -- see the next section, which is worse than I expected.

## New fact: no capture in the suite constrains BLEND_AND's fourth byte

All 20 `ImgBlt_BLENDAND_*` goldens are XRGB (12) or ZRGB (8); I listed
`~/goldens/results/Image_blit/` and there is no `ImgBlt_BLENDAND_ARGB_*` at
all, though the SRCCOPY set does carry `ImgBlt_SRCCOPY_ARGB_B00000000`, so the
naming does distinguish the two deliberately.

Those two formats are exactly the two that set `needs_alpha_patching`
(`vk/blit.c:677-688`), and `patch_alpha()` then writes `d[x * 4 + 3]`
unconditionally over **the same rect the blend just wrote**
(`row_pixels x adjusted_height` at `dest_row`, `vk/blit.c:700`). So on every
one of the 20, the byte `BLEND_AND` carefully preserved is overwritten a few
lines later, before anything reads it.

The consequence, stated as a limit rather than a result: **the fleet has no
evidence about BLEND_AND's fourth channel in any format.** The 3-of-4 structure
is inherited, not measured. Extrapolating it to a 1-byte destination would be
building an unmeasured rule on top of an unmeasured rule, in the one path #38
just made exact. That is the concrete reason this lane did not implement Y8,
and it is a stronger reason than the one in the landed comment.

(What this does *not* say: that the 3-of-4 structure is wrong. It is very
likely right -- it is what xemu has always done and what the operation's name
suggests. It says only that this corpus cannot tell, so it is not a foundation
to build a second inference on. An `ImgBlt_BLENDAND_ARGB_*` capture is what
would settle it; see "For the next lane".)

## What #84 still leaves open, and why I left it

`3c4892563b`'s comment flags one item as unfixed, `vk/blit.c:130-139`, audit
LOW L2: `perform_blit_tiled()` passes `chunk / bytes_per_pixel` as `width` and
`chunk` as `width_bytes` (`vk/blit.c:395-398`). `chunk` stops at the next
16-byte boundary, and `dest_offset` is aligned by nothing
(`pgraph/pgraph.c:2024` masks with `0x07FFFFFF`), so at 32bpp an unaligned
offset makes those two disagree. `SRCCOPY` never looks at `width`, so only
`BLEND_AND` is affected, and there it both truncates (dropping `chunk % 4`
bytes of each chunk) and starts at the wrong pixel phase.

I did not fix it, for a specific reason rather than a shrug:

- The natural place for the refusal is the entry guard, which is where
  `3c4892563b` deliberately moved the bpp guard -- but the entry does not yet
  know whether a GPU tile is valid; `clipped_dest_size` and
  `find_blit_gpu_tile()` are 150 lines later (`vk/blit.c:604-611`). Guarding on
  alignment at the entry regardless of tiling would refuse blits the linear
  path handles correctly today.
- Putting it at the tiled call site instead (`vk/blit.c:639`) means refusing
  *after* the `surf_dest` block has already cleared `download_pending` and
  `draw_dirty` and set `upload_pending` -- which is exactly the shape
  `3c4892563b` was written to eliminate (audit MEDIUM M1). Fixing a LOW by
  reintroducing a MEDIUM the fleet just closed is a bad trade.
- And no arm could score either version. See below.

So it needs a restructure -- hoisting the tile lookup above the bookkeeping --
which is a different change from #84 and wants its own issue and its own grant.

## The arm situation, honestly: an inertness claim here would be vacuous

`Prediction: none`, and this is the part worth arguing rather than asserting.

#38's arm was bound `a_ref 71c7bd1d7d` -> `b_ref 24a75d6e3c`
(`docs/testing/predictions/blit38-blend-and-divide.json`). Both #84 guard
commits sit **above** `24a75d6e3c`, so **the guards folded into master with no
arm covering them.** That looked like this lane's obvious deliverable: register
the missing inertness claim over `Image_blit/*`.

It is not, and registering it would be the tautological falsifier this
repository keeps warning about. Both guards are `bytes_per_pixel != 4`
early-returns. Every one of the 42 `Image_blit` goldens is 32bpp, so no
capture can enter either branch. **There is no error I could make in that code
that any leg could detect** -- a leg that cannot fail under a wrong patch is
not a control, and 20 of them are not 20 controls. The honest report is that
the guards are unarmed and unarmable on this fleet, which is the same fact the
issue opened with ("no arm on this fleet could surface this") pointed at the
fix instead of the defect.

This lane changes no code, so there is additionally nothing to be inert about.
`Prediction: none: analysis-only`.

## For the next lane -- do not repeat these

1. **Do not re-implement the guard.** It is in master on both renderers. Check
   `git log -- hw/xbox/nv2a/pgraph/vk/blit.c` before writing anything; the
   brief for this lane was written against a tree that predated the fold.
2. **Do not "just multiply by `bytes_per_pixel`".** The 3-of-4 channel
   structure does not survive it. See above.
3. **Do not register an inertness arm over `Image_blit/*` for the guards.**
   No leg can move. It would read as a green verdict for a check that ran
   nothing.
4. **The one measurement that would actually advance #84** is an
   `ImgBlt_BLENDAND_ARGB_*` capture -- a BLEND_AND into a destination whose
   fourth byte is *not* overwritten by `patch_alpha` afterwards. That is a new
   test in `nxdk_pgraph_tests`, not an arm over the existing disc. It would
   pin the 3-of-4 structure, and pinning it is the precondition for ever
   implementing Y8 rather than refusing it.
5. **LOW L2 needs the tile lookup hoisted above the `surf_dest` bookkeeping**
   before it can be fixed without reintroducing M1. Separate issue.

## What I did not check

- I did not build or run anything; this is a reading result end to end.
- The XRGB/ZRGB -> `LE_X8R8G8B8`/`LE_X8R8G8B8_Z8R8G8B8` mapping is read off the
  capture names plus the renderer's own format switch. I had no
  `nxdk_pgraph_tests` checkout in this worktree to confirm it from the guest
  source. The "no capture constrains the fourth byte" conclusion does not
  depend on it either way: there is no `BLENDAND_ARGB` golden at all, so no
  BLEND_AND capture exists whose destination format leaves the fourth byte
  unpatched.
- I did not establish anything new about the overrun's extent. The issue's own
  correction comment (bounded, ~3 extra pitches at Y8, not a host-memory
  escape) stands as written.
