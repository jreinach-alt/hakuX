# lane.clrvk184 -- #184, the Clear suite's surface-format captures on Vulkan

Analysis lane. No renderer code changed. One instrument landed,
`docs/testing/clear_surface_fmt.py`, and one mechanism claim from #184
**refuted as stated** and replaced with a narrower one that the data supports.

Goldens on this host are at `/home/justin/goldens/results`, not the
`/tmp/goldens/results` the sibling script defaults to. Pass `--goldens`.

## What the instrument does, and why it is not the sibling script

`x1a7_clear_bytes.py` asks what the stored bytes say about one format pair's
pad bit. This one asks a question about the *emulator*: for each of the eight
`Clear::{SCF,SFC}_*` captures, is the error `the renderer served swatch 0's
pixels for swatches 1..5`, or `swatch 0 itself came out wrong`? Those are two
different defects with two different owners -- #184 and #164/#48 -- and they
are **superimposed** on four of the eight captures, so the single
differing-pixel count in #184's table attributes neither.

`TestSurfaceFmt` loops six times: point a 128x128 surface of the format under
test at `GetTextureMemoryForStage(0)`, one `NV097_CLEAR_SURFACE`, one 4x4
centre mark, then sample that same memory through a `LU_IMAGE_A8B8G8R8` stage
into quad N. One address, one texture state, six different contents. So
"quad N is byte-identical to quad M" is directly observable, and the six clear
colours being distinct is what stops the test being vacuous --
`check_goldens()` asserts that per capture rather than arguing it once from
the colour list.

    docs/testing/clear_surface_fmt.py <run_dir> --goldens <dir>
    docs/testing/clear_surface_fmt.py --selftest      # no disc, no numpy

## Measured, on `z-c866527e03-012-Clear` (and 12 other runs, see below)

    capture                          diff  alias    aliased  residual
    SFC_A8R8G8B8                    81936  00000      81920        16
    SFC_X1R5G5B5_Z1R5G5B5           49152  .....          0     49152
    SCF_X1R5G5B5_O1R5G5B5               0  .....          0         0
    SCF_R5G6B5                      40920  00000      40920         0
    SCF_X8R8G8B8_Z8R8G8B8           81840  00000      81840         0
    SCF_X8R8G8B8_O8R8G8B8           81840  00000      81840         0
    SCF_X1A7R8G8B8_Z1A7R8G8B8       81936  00000      81920        16
    SCF_X1A7R8G8B8_O1A7R8G8B8       98208  00000      81840     16368

`alias` is, for quads 1..5, the earlier quad whose bytes they repeat. `00000`
means **quad 0 served six times**. The swatch colours themselves say it
plainly -- on `SCF_X8R8G8B8_Z8R8G8B8` the golden holds six distinct colours
and the run holds `bacada00` in all six.

So #184's "four distinct golden swatch colours come out as one" is
**confirmed and sharpened**: it is five quads carrying quad 0's bytes, not
four, and it is every capture but the two `X1R5G5B5` ones.

The `residual` column is the part that was not visible before:

- `SCF_R5G6B5`, `SCF_X8R8G8B8_{Z,O}`: residual **0**. Quad 0 is bit-exact.
  These three captures are *entirely* #184 and nothing else.
- `SFC_A8R8G8B8`, `SCF_X1A7R8G8B8_Z`: residual **16** -- quad 0's centre
  mark alpha. Pad-byte territory, #48/#164, 16 px of it.
- `SCF_X1A7R8G8B8_O`: residual **16,368** -- quad 0's own body is wrong too
  (`bacada00` where the golden holds `bacada80`). Two defects stacked; #184
  owns 81,840 of the 98,208 and #60/#183's pad model owns the rest.
- `SFC_X1R5G5B5_Z`: residual **49,152**, alias none. **None of this capture
  is #184.** It is the `sampled_pad_alpha` override zeroing a byte that is
  the high byte of a second 1555 word rather than a pad bit, which
  `surface_sampled_pad_alpha()`'s own comment already names and #164 owns.

## Stability: 13 runs, 13 refs, 6 days

Every device run of `Clear` on disk from 2026-09-13 to 2026-09-19 reports the
identical alias column, across 13 distinct refs (`ce9c4eecf8`, `0026f00534`,
`2501f35211`, `6762a54c82`, `c866527e03` twice, `23be8223f5`, `4381fae5f6`,
`1f9eac66c4`, `55de5edfff`, `0e919fe51e`, `cd8854be10`, `11ddd94a66`,
`2ffd961764`). This is not noise and it is not one commit's.

## THE REFUTATION

#184 offered, explicitly as a hypothesis it had not instrumented: *one texture
cache key reused across the suite's six `NV097_CLEAR_SURFACE` calls, keyed at
`GetTextureMemoryForStage(0)`*. #60's comment had floated the same shape.
**As stated it is refuted, and the refuting row is in the table above.**

All eight format cases point at that one address with the *identical* texture
stage -- 128x128, `LU_IMAGE_A8B8G8R8`, same filter, same address mode
(`clear_tests.cpp:353-356`, outside the per-format branch). `TextureKey` is
guest texture state plus VRAM offsets (`vk/texture.c:1760-1777`), so **all
eight share one key, and so do all six iterations within each**. A
shared-key account therefore predicts that all eight duplicate.

Two do not. `SCF_X1R5G5B5_O1R5G5B5` is **pixel-exact on all six swatches**,
and `SFC_X1R5G5B5_Z1R5G5B5` shows no duplication at all. The key is shared by
the captures that duplicate *and* by the ones that do not, so the key is not
what varies. What varies is the surface format -- which means the failure is
in the **invalidation**, not in the key.

A second row narrows it further, and this one comes from the code rather than
the pixels. `vk/texture.c:1987-1997` already forces `binding_found = false`
for a pad-alpha surface that is a texture source -- an *unconditional rebuild*
whose comment says in so many words that it exists because a kept view "would
be right on the first capture and wrong on the rest". Among our eight that
condition is true for exactly `SCF_X8R8G8B8_{Z,O}` (`host_bytes_per_pixel` 4
matching the A8B8G8R8 stage, and `sampled_pad_alpha` ZERO/ONE --
`vk/constants.h:552-598`). **Those two get a fresh image on every bind and
still serve quad 0's pixels.** Throwing the cached image away does not help,
so the stale thing is the **source the refill reads**, not the cache entry.
That is a different defect from GL's `da9e02a2`, which *was* a cache-entry
defect (`data_hash` describing bytes the s2t blit had overwritten) and is
fixed by making the slow path notice.

### The rebuild claim, checked against the refs rather than against the tip

"`SCF_X8R8G8B8_{Z,O}` rebuild on every bind and still fail" is a claim about
code, and the runs that measured the failure are not the tip. So it was
checked per ref rather than read off master:

- **10 of the 13 refs carry `pad_alpha_needs_rebuild` in
  `vk/texture.c`** (`0026f00534`, `2501f35211`, `6762a54c82`, `c866527e03`,
  `23be8223f5`, `55de5edfff`, `0e919fe51e`, `cd8854be10`, `11ddd94a66`,
  `2ffd961764`), and all ten duplicate.
- **3 do not** — `ce9c4eecf8` predates `4946433d87`, which introduced it at
  2026-09-12 16:49, and the two arm builds `4381fae5f6` / `1f9eac66c4`
  descend from it without the string in that file. **All three duplicate
  identically.**

So the duplication is present with the rebuild and without it, which says
independently that the rebuild is neither its cause nor its cure — and rules
`4946433d87` out as the flip commit, since `ce9c4eecf8` is already in the
post-flip regime three hours before it.

## What I could NOT establish, stated as a fit rather than a cause

Which source is stale, and why the split. The rule that fits all eight rows is
two-term: duplication is absent exactly when the surface's host format is
`VK_FORMAT_A1R5G5B5_UNORM_PACK16` -- i.e. neither 4 bytes per pixel *nor*
`R5G6B5`. `R5G6B5` is the awkward row: it is 2 bytes like the 1555 pair, so
`surface_is_texture_source()` is false for it too, and it duplicates anyway.

**Eight rows and two terms is a curve fit and I am naming it as one.** I am
not claiming a call site on it. What I *am* claiming is everything above the
line: the duplication, its exact extent, its separation from the pad-byte
defects, and the refutation of the cache-key reading.

## A dating lead, with its provenance caveat

Five older local run dirs (`res_29_clear`, `res_clr_live`, `res_fullrun3/4/5`,
2026-09-09/10) report the **exact complement**: the two `X1R5G5B5` captures
duplicate and the 4-byte group does not. `R5G6B5` duplicates in both regimes.

Their quad 0 on `SCF_X8R8G8B8_Z` reads `dacabaff` where the golden holds
`bacada00` -- red and blue swapped, alpha unhandled -- which is precisely the
pre-fix channel-order defect that `surface_view_decodes_as_texture()`'s
comment describes. So they predate `f825d6a9ee` (2026-09-11).

These run dirs carry **no renderer record**. No handheld in this fleet can run
OPENGL, so they are almost certainly Vulkan, but I am dating them rather than
claiming them. *If* they are Vulkan, the flip falls between 2026-09-10 and
`ce9c4eecf8` (2026-09-12 13:33), the earliest ref measured in the post-flip
regime. That window holds `f825d6a9ee`, `2d8cebbf95`, `c477155f55` (which
introduced `surface_is_texture_source`), `d66e9b861f` and `f009555537`, and
**excludes `4946433d87`** (16:49 the same day) by three hours — see the ref
check above. That would also make the 4-byte group's duplication *newer*
than `R5G6B5`'s, i.e. two mechanisms rather than one -- which is a claim the
next lane should test before assuming a single fix covers all six.

## What the next lane should not repeat

- **Do not re-state the cache-key hypothesis.** It has now been offered three
  times (#60's comment, #184's filing, this brief) and it is refuted above by
  the two captures that share the key and do not duplicate.
- **Do not reach for the cache.** `SCF_X8R8G8B8_{Z,O}` already rebuild
  unconditionally and still fail; a patch that invalidates harder is inert on
  them by construction.
- **Do not score these captures with one number.** Four of the eight carry two
  defects. Use the `residual` column, or a fix for #184 will be read as
  partial and a fix for #164 as a regression.
- **`SFC_X1R5G5B5_Z1R5G5B5`'s 49,152 px is not #184's** and must be off any
  prediction this issue registers.

## The experiment that would settle it, and why I did not run it

One desktop `Clear` run under Vulkan with the three exits of
`pgraph_vk_bind_textures` counted per bind -- s2t direct view, s2t copy, VRAM
upload -- over the six iterations of one 4-byte capture and one 1555 capture.
`trace_nv2a_pgraph_surface_texture_compat_failed` (`vk/texture.c:1806`) is
already on that path. **No device time.** This worktree has no desktop xemu
toolchain and no built binary (`dispatch/builds` holds apks only), so I could
not run it here; it needs a host that can build desktop xemu, not device time.

## Provenance

Instrument written and all figures derived 2026-09-20 from
`/home/justin/goldens/results` and the run dirs named above. Test geometry
read off `nxdk_pgraph_tests/src/tests/clear_tests.cpp:310-437`. No device run
was requested and none was needed.
