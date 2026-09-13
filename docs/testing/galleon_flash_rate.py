#!/usr/bin/env python3
"""Count Galleon's flashing-surface frames per hundred, from frames on disk.

WHY THIS EXISTS. `docs/investigations/galleon-flashing-deck.md` chased this
defect through four readings without ever measuring how often it fires, and
then used "one violation across the captured frames, against an artifact
reported as cycling continuously" to retract a candidate. A cause has to fire
at roughly the rate of its effect, and nobody knew the rate.

The rate that WAS quoted -- one frame in forty -- came from mean luminance and
local contrast over a crop, and that instrument cannot tell two different
events apart:

    a BRIGHTNESS excursion    the surface reads lighter, large-scale
    a STIPPLE excursion       a hard high-frequency hatch appears, and its
                              DIRECTION changes between frames

Measured on `docs/investigations/images/galleon-deck-cycle.png`, the 40-frame
left-deck mosaic the investigation was built on, they are not the same frames.
Frame 38 is the brightest in the set (mean 110.2 against a median of 87.5) and
its high-frequency energy is dead average (4.94 against a median of 4.65) --
the frame the whole document calls "the flash" is not hatched. The hatched
frames are 4, 8, 13 and 32, at 8.96, 7.86, 6.80 and 8.25, and their diagonal
anisotropy runs the other way (d1/d2 0.75, 0.50, 0.73, 0.92) from frames 14,
21 and 31 (1.68, 1.90, 1.56), which is the reported direction reversal,
measured.

So this reports the two classes SEPARATELY and never merges them into one
"flash rate".

    galleon_flash_rate.py FRAMES...                     # one image per frame
    galleon_flash_rate.py --mosaic 8x5 mosaic.png       # a tiled contact sheet
    galleon_flash_rate.py --region 0,100,110,150 ...    # x0,y0,x1,y1 in a tile

THE REGION MATTERS AND IT IS NOT OPTIONAL THINKING. Over a whole town frame
the stipple is a few per cent of the pixels, and the mosaic's per-tile mean
moves by +-2 while the ground patch inside it moves by +15: measured over the
full tile the town capture looks static, and over the ground region 7 of 50
frames flash. A null result from this tool is only about the region given.

Baselines, recorded so a later run can be compared against something:

    galleon-deck-cycle.png  --mosaic 8x5 --region 4,4,196,84
        stipple  4 / 40  = 10.0 per 100   frames 4, 8, 13, 32     (k=3)
                 5 / 40  = 12.5 per 100   and frame 14            (k=2)
        bright   1 / 40  =  2.5 per 100   frame 38
    galleon-town-cycle.png  --mosaic 10x5 --region 0,100,110,150
        stipple  7 / 50  = 14.0 per 100   frames 3, 5, 7, 11, 22, 48, 49
        bright   0 / 50  =  0.0 per 100

Two independent scenes agree on roughly 10-14 stipple frames per hundred,
which is four to six times the 2.5 per 100 the investigation recorded. Any
candidate cause has to fire about that often.

The deck's direction reversal sits just under the k=3 bar: frame 14 is at HF
6.11 against a bar of 6.74, and it is the one frame in the set whose hatch
lies along the OTHER diagonal (d1/d2 1.68 against 0.50-0.92 for the four
above). At k=2 it is flagged and the tool reports both directions. So the
default bar is tuned for "is the artifact present at all" and a reversal
question wants --k 2 and --per-frame.
"""
import argparse
import sys

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view
from PIL import Image

# Robust outlier bar: median + K * (1.4826 * MAD). A median/MAD pair is used
# rather than a mean/std one because the outliers are the thing being counted,
# and they drag a mean towards themselves -- the bar would move with the
# defect's own rate and a scene with more flashing would report less.
K_SIGMA = 3.0

# The brightness class needs an absolute bar as well as a robust one: a scene
# where every frame is bright has no excursion, and a median shift of 20 grey
# levels over a fixed camera is the size the investigation measured (92.2 to
# 112.9 on the left deck).
BRIGHT_ABS = 15.0


def hf_energy(t):
    """Mean |pixel - 3x3 neighbourhood mean|: energy above the box-filter cutoff.

    This is the stipple's own quantity. Local contrast (std) cannot separate
    it from large-scale shading, which is how the two classes above got
    conflated: frame 38's std is the highest in the deck set at 22.7 and its
    HF energy is average.
    """
    w = sliding_window_view(t, (3, 3))
    return float(np.abs(t[1:-1, 1:-1] - w.mean(axis=(2, 3))).mean())


def anisotropy(t):
    """Mean |gradient| along each diagonal, and their ratio.

    A hatch lying along one diagonal raises the gradient across it. The ratio
    is the DIRECTION, and a rotating artifact moves it to both sides of 1 --
    which no single-frame appearance can do, and which is why the mip-level
    reading was abandoned.
    """
    d1 = float(np.abs(t[1:, 1:] - t[:-1, :-1]).mean())
    d2 = float(np.abs(t[1:, :-1] - t[:-1, 1:]).mean())
    return d1, d2


def load_frames(paths, mosaic, region):
    frames = []
    if mosaic:
        cols, rows = mosaic
        for p in paths:
            im = np.asarray(Image.open(p).convert("L")).astype(float)
            h, w = im.shape
            th, tw = h // rows, w // cols
            for r in range(rows):
                for c in range(cols):
                    frames.append(im[r * th:(r + 1) * th, c * tw:(c + 1) * tw])
    else:
        for p in paths:
            frames.append(np.asarray(Image.open(p).convert("L")).astype(float))
    if region:
        x0, y0, x1, y1 = region
        frames = [f[y0:y1, x0:x1] for f in frames]
    bad = [i for i, f in enumerate(frames) if f.shape[0] < 8 or f.shape[1] < 8]
    if bad:
        sys.exit(f"region leaves too few pixels in frame(s) {bad[:5]}")
    return frames


def robust_bar(v, k=K_SIGMA):
    med = float(np.median(v))
    mad = float(np.median(np.abs(v - med)))
    return med, mad, med + k * 1.4826 * mad


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="+")
    ap.add_argument("--mosaic", metavar="COLSxROWS",
                    help="each input is a contact sheet of COLS*ROWS frames")
    ap.add_argument("--region", metavar="X0,Y0,X1,Y1",
                    help="crop applied to every frame (or every tile)")
    ap.add_argument("--k", type=float, default=K_SIGMA,
                    help=f"robust sigmas above the median (default {K_SIGMA})")
    ap.add_argument("--per-frame", action="store_true",
                    help="print every frame's numbers, not just the outliers")
    args = ap.parse_args()

    mosaic = None
    if args.mosaic:
        c, _, r = args.mosaic.partition("x")
        mosaic = (int(c), int(r))
    region = tuple(int(x) for x in args.region.split(",")) if args.region else None
    if region and len(region) != 4:
        sys.exit("--region takes X0,Y0,X1,Y1")

    frames = load_frames(args.paths, mosaic, region)
    n = len(frames)
    mean = np.array([float(f.mean()) for f in frames])
    hf = np.array([hf_energy(f) for f in frames])
    aniso = [anisotropy(f) for f in frames]

    hf_med, hf_mad, hf_bar = robust_bar(hf, args.k)
    m_med, m_mad, m_bar_rob = robust_bar(mean, args.k)
    m_bar = max(m_bar_rob, m_med + BRIGHT_ABS)

    stipple = np.nonzero(hf > hf_bar)[0]
    bright = np.nonzero(mean > m_bar)[0]

    print(f"{n} frames, region {region or 'whole frame'}, "
          f"{frames[0].shape[1]}x{frames[0].shape[0]} px each")
    print(f"  HF energy   median {hf_med:.2f}  mad {hf_mad:.2f}  "
          f"bar {hf_bar:.2f}  (k={args.k})")
    print(f"  mean lum    median {m_med:.1f}  mad {m_mad:.1f}  bar {m_bar:.1f}")
    print()
    print(f"  STIPPLE  {len(stipple):3d} / {n}  = "
          f"{100.0 * len(stipple) / n:5.1f} per 100   {[int(i) for i in stipple]}")
    print(f"  BRIGHT   {len(bright):3d} / {n}  = "
          f"{100.0 * len(bright) / n:5.1f} per 100   {[int(i) for i in bright]}")
    both = sorted(set(stipple) & set(bright))
    print(f"  both classes on one frame: {both if both else 'none'}")
    print()

    if len(stipple):
        print("  stipple frames, with the hatch direction:")
        for i in stipple:
            d1, d2 = aniso[i]
            side = "main diagonal" if d1 > d2 else "anti-diagonal"
            print(f"    frame {i:3d}  HF {hf[i]:5.2f}  mean {mean[i]:6.1f}  "
                  f"d1/d2 {d1 / d2:5.2f}  {side}")
        dirs = {("main" if aniso[i][0] > aniso[i][1] else "anti") for i in stipple}
        if len(dirs) > 1:
            print("    BOTH DIRECTIONS PRESENT -- a rotating pattern, not one "
                  "wrong appearance")

    if args.per_frame:
        print("\n  all frames:")
        for i in range(n):
            d1, d2 = aniso[i]
            print(f"    {i:3d}  mean {mean[i]:6.1f}  HF {hf[i]:5.2f}  "
                  f"d1/d2 {d1 / d2:5.2f}")

    # Exit code carries the stipple rate so a driver A/B can branch on it:
    # 0 = no stipple frame found, 1 = the artifact is present in this set.
    return 1 if len(stipple) else 0


if __name__ == "__main__":
    sys.exit(main())
