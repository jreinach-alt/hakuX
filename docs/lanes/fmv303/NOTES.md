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
