# lane.fmv303 -- #303 Spikeout FMV green block corruption

## 1. What the green is: Cr = 0, with Y and Cb intact (from the frames, no device)

Source: `gamecheck/spikeout-soak/f00028.png` (1280x960 screencap of a
640x480 guest, soak `1790364700-gamecheck-355013`, apk `851650a27937`).

The flat green is **(0,132,25)**, the commonest colour in the picture
(9,192 px, with (0,131,24), (0,133,27) etc. close behind). It is **not**
what Y=U=V=0 gives. Through our exact YUV->RGB (`convert_yuy2_to_rgb`,
docs/investigations/yuv-conversion.md), Y=Cb=Cr=0 gives (0,136,0). Inverting
every (Y,Cb,Cr) in 0..255^3 through that function:

| colour in frame | triples that produce it through OUR converter |
|---|---|
| (0,132,25) flat green, commonest | **0** |
| (0,131,24), (0,137,30) | **0** |
| (29,27,25) dark grey of the clean picture | **0** |
| (0,86,0), (0,255,0) | many, all Cr <= 113 |

So **the picture is not produced by our YUY2 converter**. That rules out the
PVIDEO overlay (`upload_pvideo_image` -> `convert_texture_data__CR8YB8CB8YA8`,
displayed unmodified) and a YUY2/UYVY texture sampled directly (same
function). The game does its own colour conversion.

Under plain BT.601, (0,132,25) is Y~40, **Cb~127 (neutral), Cr~0**. The
whole frame reads the same way: dark areas with Cr=0 go green, bright ones
cyan (R pulled to 0, G and B saturated), and the face is visible *through*
the green blocks (f00028). Luma and Cb survive; **only Cr is lost.** In
packed YUY2, V is every fourth byte, so an unwritten region would lose luma
too. **The source is planar, or at least Cr is its own plane.**

Geometry: the edges of the green mask fall on a 32-px screen grid in both
axes, i.e. **16x16 guest pixels: MPEG macroblocks** (8x8 in a half-res Cr
plane). The blocks stack into vertical columns. The pattern differs between
frames and between the two passes over the same shot.

Consequence for the brief. Its premise, "Y=U=V=0 through the YUV->RGB path",
is refuted by the colours. The display path, the only file this lane owns,
cannot be where Cr is lost. Two readings remain, and they differ by WHERE the
zero lives:

- **(A) guest RAM holds Cr=0 in those macroblocks.** The guest decoder
  (Sofdec, running on the emulated CPU) wrote it. That is a CPU-side defect,
  such as a JIT miscompile of MMX/SSE saturation in the IDCT or MC path.
  Pass-to-pass variation would come from tier1 promotion timing.
- **(B) guest RAM holds a normal Cr, and the GPU sampled zeros.** A Cr
  texture upload saw its memory before the write, or was not re-uploaded.
  That is texture.c (lane.texvol283's territory): name the hunk and ask for
  a grant.

## 2. Probe (commit 4fe77d5830, `vk/display.c`, env `HAKUX_FMV303_PROBE=1`)

At each displayed frame it logs the PVIDEO registers and, for each enabled
texture stage, the colour format, dims and address. It also summarises the
guest bytes behind each one: zero fraction, mean, a hash, and the number of
aligned 8x8 blocks that are entirely zero. It settles the path (PVIDEO vs
which texture formats). Comparing all-zero 8x8 blocks in the Cr source in
guest RAM with the green area on screen separates (A) from (B).

Caveat, stated in advance: it samples registers at vblank, so if a subtitle
or other draw follows the video's, the video stages may be missed on some
frames. Silence from the texture lines is void, not a zero.

Runs: `1790370304-fmv303-3205005` and `1790370307-fmv303-3209950` (Thor,
150 s, frames every 2 s, same ref: the pair is also the "do two runs of one
build disagree" leg).

The original soak ran on the Nova while Vulkan validation and sync
validation were on (11:11-13:05 PDT, #265 thread). Its timing is not
representative, and a race reading must not rest on it.

## 3. Attempt 1 ended waiting; attempt 2 (2026-09-25 ~23:30 UTC)

Attempt 1 did not finish because it was correctly waiting: the two probe runs
(`1790370304-…`, `1790370307-…`, queued 21:05 UTC) had not been claimed. It
also left CI red, which it did not know about: the `display.c` probe adds 17
PGRAPH register read sites (TEXCTL0/1, TEXFMT, TEXOFFSET...), so the committed
`nv2a_index.json` no longer matched the tree. Attempt 2 merged origin/master
and regenerated the index over the pinned trees (tests `6743b6ab16`, pbkit
`e91d509e4f`, same as CI). The only site changes are the probe's.

At 23:30 UTC both probe requests are still in `dispatch/queue/`, behind a
~190-request pgraph arm (`8e683b3a26`, running Pixel_shader). The dispatcher is
busy, not jammed, so no nudge. The lane is waiting on those two runs. They
settle the path (PVIDEO vs which texture format) and whether guest RAM holds
the Cr=0 (reading A, CPU/JIT) or not (reading B, texture upload: texvol283's
hunk, ask for a grant on #303). No fix and no prediction exist yet, so none
is registered. The probe is env-gated (`HAKUX_FMV303_PROBE=1`) and inert by
default.

Next lane, do not repeat: the "Y=U=V=0" premise (section 1 refutes it); the
Nova soak's timing (validation layers were on).

## 4. Attempt 3 (2026-09-26): the v1 probe runs, read

Attempt 2 ended correctly, while waiting. The two runs were queued and
unclaimed, and CI was not yet green on the regenerated index. Both have
since landed (Thor, apk `bb5f85ba682e`, ref `4fe77d5830`), and CI went green
on `26a67e33d8`.

### The path: a CPU-written ARGB texture. Not PVIDEO, not a YUV texture

| run | pvideo lines | `buf` ever nonzero | FMV source lines (tex0 `color=12 lin 640x368 pitch=2560`) | addresses |
|---|---|---|---|---|
| `1790370304-…` | 2252 | no | 1898 | `307d000` ×948, `3163000` ×950 |
| `1790370307-…` | 4312 | no | 1921 | `307d000` ×963, `3163000` ×958 |

PVIDEO is never enabled (`buf=00000000 size_in=ffffffff` on every line).
The FMV is texture stage 0 alone, format 0x12 (`LU_IMAGE_A8R8G8B8`),
double-buffered at two addresses. No stage ever binds a YUY2/UYVY format.
**The game converts YUV to RGB on the CPU** and hands the GPU finished ARGB.
So no GPU YUV path exists for this FMV, and `vk/display.c`'s overlay code
cannot be where the green is made. Section 1's inference ("the game does its
own colour conversion") is confirmed by the registers.

### The green on Thor: region counts per frame

Scored with `green_cells.py` (this directory). It uses a hue predicate over
32x32-px cells and was validated before use: Nova f00028 gives 477/887,
f00054 and f00058 give 0. **The Thor green is not R=0.** The commonest colours
in run 1's f00030 are (117,251,76), (59,133,36) and (34,84,19): one green hue
scaled by luma. An R<=6 detector read 0 on every Thor frame, including
visibly green ones, and was thrown out. Section 1's exact "Cr=0" inversion
therefore holds for the Nova frames only. On both devices the defect is a
chroma-dominated tint over live luma, in macroblock cells.

| run | FMV-window frames | green > 10% of lit cells | exactly 0 | > 90% | mean fraction |
|---|---|---|---|---|---|
| `1790370304-…` (f12-f50) | 39 | 27 | 10 | 3 | 0.41 |
| `1790370307-…` (f16-f54, f63-f66) | 43 | 40 | 3 | 11 | 0.66 |

It switches on and off within a shot: fully clean frames (0 cells) sit
between frames that are 50-100% green. Same binary, same device, same spec:
the two runs differ in both level (0.41 vs 0.66) and clean-frame count
(10 vs 3). Frames are not aligned between the runs (the FMV starts at f12 in
one and f16 in the other, with 2 s sampling), so a frame-for-frame
disagreement is **not** claimed. The distributions differ, which is what a
timing-dependent defect predicts and a deterministic one does not.

### What v1 could not answer, and v2

The v1 byte statistics are blind to this format. Alpha is 0xFF, so an
all-zero 8x8 block cannot occur (`zblk=0/3680` on every line), and the Thor
tint has R,B > 0, so zero bytes do not track it either. **Whether guest RAM
holds the green is not measured yet.** One argument is not a measurement:
since the GPU samples CPU-written RGB, a missed or stale upload would show an
*older RGB picture*, not a green tint over the current luma. So reading (B),
the upload, is unlikely on the colours alone. Where the chroma is lost
(guest decoder, a JIT defect, or an emulated write clobbering the guest's
chroma planes) stays open.

Probe v2 (`de1c93d244`) counts tinted 16x16 macroblocks **in the guest ARGB
buffer**, with the same predicate as `green_cells.py`
(`[fmv303] f=… tex0 tint mb=… lit=… of=… px=… rgb=…`). Queued as
`1790389079-fmv303-1248256` (Thor, 150 s, frames every 2 s).

- Guest `mb/lit` distribution matching the screen's (≈0.4-0.7 mean, clean
  frames interleaved): the green is in guest RAM and the display and upload
  paths are exonerated. The next lane looks for who zeroes the chroma: CPU/JIT
  (tier1 on/off A/B) or a surface write-back over the planes.
- Guest buffer clean (mb≈0) while the screen is green: a missed upload of
  the ARGB texture. That is `texture.c`, texvol283's file: name the hunk on
  #303 for a grant.
- `rgb=` sanity: a black frame must read 0,0,0 (the byte order is B,G,R,A).
  If it does not, the v2 counts are void.

No fix exists, so no prediction is registered. The brief's fix file
(`vk/display.c`) is refuted as the fix site by the path table above.
