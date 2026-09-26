#!/usr/bin/env python3
"""Run #77's registered falsifier: does an unattended Galleon soak ever hold one scene?

WHAT IS BEING TESTED. #77 is blocked on a claim -- "a soak cannot park a
camera" -- and the blocker was registered with its own falsifier and then
never run:

    if that were false, the attract demo would contain a sustained
    single-scene segment long enough for galleon_flash_rate.py's median/MAD
    bar to be set by the deck rather than by scene cuts -- observable offline
    by segmenting an existing 180 s soak.

`galleon_flash_rate.py` flags a frame when its high-frequency energy exceeds
`median + 3 * 1.4826 * MAD` over the frames it is handed. That bar is only
about the artifact if the frames it is handed are one scene. Over a cutting
attract loop the MAD is content variation, the bar floats up above it, and the
artifact never clears it.

THE OPERATIVE QUESTION IS NOT SEMANTIC, AND IS NOT ASKED THAT WAY HERE. This
does not thresholdthe word "scene". It asks the consequence directly, over
every contiguous window of every length in every arm:

    is there a window long enough, on live textured content, whose HF bar
    sits close enough to its own median that a stipple frame would clear it?

That removes the one step a reader would otherwise have to take on trust --
what counts as a cut -- from the load-bearing path. A descriptive scene
segmentation is still reported, but only as colour.

THE PASS BAR IS CALIBRATED THROUGH THIS SCRIPT'S OWN CHAIN, not borrowed from
the parked mosaics' absolutes. Borrowing them would have been wrong twice
over, and the first version of this file did it: the founding 40-frame deck
mosaic reads HF median 4.65 and the soak reads 0.54 in the same units, so a
guard set at the mosaic's scale rejects every soak window and manufactures
the answer the blocker wants. The mosaic is also itself a 2x NEAREST upscale
of the 640x480 guest frame -- its spectrum has a two-order spike at exactly
0.5 with a collapse either side, and 38% of its horizontal neighbours are
equal -- so its absolute HF is not a native figure either.

What IS transferable is the ratio, so the bar was measured by pushing that
parked mosaic through this script's chain (2.25x upscale, the 0.40 modal
dim, BOX resample back) with the compositor filter bracketed:

    parked reference                    HF median   bar/median
    deck mosaic, as registered              4.655        1.448
    deck mosaic -> native -> soak chain     2.25-3.53    1.271-1.382
    deck mosaic as native -> soak chain     1.95-2.73    1.385-1.467
    town mosaic, as registered              3.340        1.219

So a PARKED camera lands at bar/median 1.22-1.47 whatever the filter, and the
strongest stipple frames still clear it after the chain (f4 +35..+93%, f32
+78..+129%). The pass bar is 1.45 -- the top of that bracket, the loosest
value any parked reference produced, and therefore generous to the falsifier.
Set with --bar-ratio.

AND THE LENGTH. #77's driver A/B registered V0 as ">= 3 stipple frames per 40
in the named region", so 40 frames is the denominator the campaign already
committed to. At the measured 10-14 per 100 that is 4.0-5.6 expected events.
Set with --min-len.

THE DEGENERATE PASS IS GUARDED, AND BOTH GUARDS ARE IN THE SOAK'S OWN UNITS.
A window of frozen duplicate frames -- a Loading card, the "press START"
title -- has MAD ~ 0 and bar/median ~ 1.0, and would pass the ratio test
while containing no deck at all. Measured over the four soaks:

    black screen / Loading card       HF 0.00-0.11   motion 0.00-0.21
    frozen "press START" title card   HF 1.01        motion 0.06-0.12
    live gameplay ground              HF 0.30-1.25   motion 4-15

Note that HF ALONE CANNOT DO IT: the frozen title card reads HIGHER HF than
live gameplay, because its text is high-frequency. So:

  * --min-motion (default 1.0) is the guard that rejects a frozen window, and
    it sits in a gap two orders of magnitude wide.
  * --min-hf (default 0.25) only rejects a blank screen, and sits in the gap
    between 0.11 and 0.30.

The verdict is reported BOTH with and without the HF guard, so a reader can
see whether either guard was load-bearing rather than take it on trust.

WHAT THIS INSTRUMENT CANNOT SEE, stated before any empty result is allowed to
mean anything:

  1. THE SOAK FRAMES ARE 1.4-1.8 s APART, not consecutive. Galleon runs at
     14-26 fps here, so consecutive samples are 20-40 guest frames apart. At
     that spacing a hard cut and 1.5 s of camera motion are not separable by
     any per-pair measure, which is exactly why the verdict is NOT routed
     through a cut threshold. It also means a single-scene segment shorter
     than ~1.5 s cannot be seen at all: this can only refute "no sustained
     segment", never "no segment".
  2. A MODAL DIALOG OCCLUDES THE CENTRAL 61% x 44% of every frame and dims
     the rest by a measured 0.40. The occluded box is 36% of the guest frame
     and is discarded here. The 0.40 dim scales HF median and MAD together,
     so bar/median -- a ratio -- is unaffected by it; absolute HF figures
     from this script are NOT comparable to the parked mosaics' absolutes.
  3. THE CAPTURE IS A 2.25x UPSCALE. Every frame is resampled back to the
     native 640x480 before anything is measured, because HF on the upscale
     measures the compositor: the same correction moved the A/B's HF median
     from 0.256 to 0.614.
  4. IT CANNOT SEE THE ARTIFACT ITSELF, only whether the bar could. A window
     that passes says the instrument would work there; it does not say the
     artifact is present.

USAGE

    galleon_scene_segments.py DIR [DIR...]

where each DIR holds a soak's frames as f0000.png, f0001.png, ... at device
resolution, optionally with a frames.tsv of `index timestamp bytes`.
"""
import argparse
import glob
import os
import sys

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view
from PIL import Image

# --- device geometry, measured, not assumed -------------------------------
# The game viewport inside a 1920x1080 Thor screenshot. Pinned by taking the
# per-column temporal std over 4 arms x 15 frames: columns 0..239 are dead at
# 0.0 and column 241 onwards sits at 42.2. 1440x1080 is 4:3, and 1440/640 =
# 1080/480 = 2.25, which is the upscale factor the A/B measured independently.
VIEW = (240, 0, 1680, 1080)
NATIVE = (640, 480)

# The modal dialog's opaque box, in screenshot pixels: rows 275..747, cols
# 372..1547, found as the >200-luma block. 1176/1920 = 61.3% and 473/1080 =
# 43.8%, which is the 61% x 44% the A/B recorded.
DIALOG = (372, 275, 1548, 748)

# The one band of the guest frame that is BELOW the dialog, ABOVE the nav bar,
# and carries ground. In native pixels. The nav-bar icons are the only pixels
# in it with a near-constant value across a whole run (min across-arm temporal
# std < 8 covers y 447..463 and nothing else, 0.66% of the band), so cutting
# at y=444 leaves a band with no constant overlay in it at all.
GROUND_BAND = (0, 336, 640, 444)

# Region size to score. The two parked references used 192x80 (deck) and
# 110x50 (town) native crops, so a like-for-like window here is 192x80.
WIN = (192, 80)

BAR_RATIO = 1.45   # top of the measured parked bracket 1.22-1.47
MIN_LEN = 40       # the A/B's registered V0 denominator
MIN_HF = 0.25      # soak units: blank <= 0.11, live gameplay >= 0.30
MIN_MOTION = 1.0   # soak units: frozen 0.00-0.21, live gameplay 4-15
K_SIGMA = 3.0      # galleon_flash_rate.py's own k


def hf_energy(t):
    """Mean |pixel - 3x3 neighbourhood mean|. Identical to galleon_flash_rate."""
    w = sliding_window_view(t, (3, 3))
    return float(np.abs(t[1:-1, 1:-1] - w.mean(axis=(2, 3))).mean())


def robust_bar(v, k=K_SIGMA):
    med = float(np.median(v))
    mad = float(np.median(np.abs(v - med)))
    return med, mad, med + k * 1.4826 * mad


def load_native(path):
    """Crop to the guest viewport and undo the 2.25x upscale."""
    im = Image.open(path).convert("L").crop(VIEW)
    return np.asarray(im.resize(NATIVE, Image.BOX)).astype(np.float32)


def load_native_rgb(path):
    im = Image.open(path).convert("RGB").crop(VIEW)
    return np.asarray(im.resize(NATIVE, Image.BOX)).astype(np.float32)


def dialog_present(path):
    a = np.asarray(Image.open(path).convert("L"))
    x0, y0, x1, y1 = DIALOG
    box = a[y0 + 25:y1 - 25, x0 + 30:x1 - 30]
    return bool((box > 200).mean() > 0.5)


def unoccluded(nat):
    """The two bands of the guest frame the modal dialog does not cover.

    The slivers either side of the dialog are 9% of the width and are dropped
    rather than masked; they buy nothing a reader would then have to check.
    """
    dy0 = int(DIALOG[1] / 2.25)
    dy1 = int(np.ceil(DIALOG[3] / 2.25))
    return np.concatenate([nat[:dy0], nat[dy1 + 4:476]], axis=0)


def thumbnail(nat):
    """8x8 block means over the unoccluded bands. Luminance or RGB."""
    band = unoccluded(nat)
    h, w = band.shape[:2]
    h -= h % 8
    w -= w % 8
    b = band[:h, :w]
    if b.ndim == 2:
        return b.reshape(h // 8, 8, w // 8, 8).mean(axis=(1, 3)).ravel()
    return b.reshape(h // 8, 8, w // 8, 8, 3).mean(axis=(1, 3)).ravel()


def colour_hist(nat_rgb):
    """Normalised 4x4x4 joint RGB histogram of the unoccluded bands.

    Colour is what separates these scenes and luminance alone throws it away:
    a red-lit chamber, a green outdoor stretch and a grey stone corridor all
    sit within 5-15 of each other on a luminance thumbnail -- inside the 9.0
    that one step of ordinary camera motion costs -- and are 0.12-0.49 apart
    here, at or above the level of two UNRELATED frames.
    """
    q = (unoccluded(nat_rgb) // 64).astype(int).clip(0, 3)
    h = np.bincount((q[..., 0] * 16 + q[..., 1] * 4 + q[..., 2]).ravel(),
                    minlength=64).astype(np.float64)
    return h / h.sum()


def tv(a, b):
    """Total-variation distance between two normalised histograms, 0..1."""
    return 0.5 * float(np.abs(a - b).sum())


def cut_bar(hists, seed=0):
    """The distance between two UNRELATED frames of this same run.

    A cut is, by definition, a transition to content unrelated to what came
    before, so the bar is not a number chosen here: it is the median
    histogram distance over a random pairing of the run's own frames. Pairs
    that fall short of it are not called cuts, which OVERSTATES segment
    length -- the direction that is generous to the falsifier.
    """
    n = len(hists)
    perm = np.random.default_rng(seed).permutation(n)
    return float(np.median([tv(hists[i], hists[perm[i]]) for i in range(n)]))


def windows():
    """Every 192x80 native window inside the clean ground band."""
    gx0, gy0, gx1, gy1 = GROUND_BAND
    ww, wh = WIN
    xs = list(range(gx0, gx1 - ww + 1, 112))
    ys = list(range(gy0, gy1 - wh + 1, 14))
    return [(x, y) for y in ys for x in xs]


def load_arm(d):
    paths = sorted(glob.glob(os.path.join(d, "f*.png")))
    if not paths:
        sys.exit(f"{d}: no f*.png frames")
    keep = [p for p in paths if dialog_present(p)]
    dropped = len(paths) - len(keep)
    nats = [load_native(p) for p in keep]
    return keep, nats, dropped


def sample_interval(d, n):
    tsv = os.path.join(d, "frames.tsv")
    if not os.path.exists(tsv):
        return None
    ts = []
    for line in open(tsv):
        f = line.split()
        if len(f) >= 2:
            try:
                ts.append(float(f[1]))
            except ValueError:
                pass
    if len(ts) < 3:
        return None
    dt = np.diff(np.array(ts))
    return float(np.median(dt)), float(dt.min()), float(dt.max())


def best_window_run(hfs, motion, args, wins):
    """Longest contiguous run, over any window, that a stipple could clear.

    hfs: (n_windows, n_frames). Returns the best (length, start, end, wi,
    med, mad, bar, ratio) and the per-length best ratio for reporting.
    """
    nw, n = hfs.shape
    # cumulative median-motion per (start, length), computed once
    best = {"all": None, "no_hf": None, "no_motion": None, "ratio_only": None}
    longest = {k: 0 for k in best}
    per_len = {}
    for wi in range(nw):
        v = hfs[wi]
        for L in range(2, n + 1):
            for s in range(0, n - L + 1):
                seg = v[s:s + L]
                med, mad, bar = robust_bar(seg, args.k)
                if med <= 0:
                    continue
                ratio = bar / med
                if ratio <= args.bar_ratio:
                    cand = (L, s, s + L, wi, med, mad, bar, ratio)
                    hf_ok = med >= args.min_hf
                    mo_ok = (float(np.median(motion[s:s + L - 1]))
                             >= args.min_motion)
                    for key, passing in (("all", hf_ok and mo_ok),
                                         ("no_hf", mo_ok),
                                         ("no_motion", hf_ok),
                                         ("ratio_only", True)):
                        if passing:
                            longest[key] = max(longest[key], L)
                            if L >= args.min_len and (best[key] is None
                                                      or L > best[key][0]):
                                best[key] = cand
                if L not in per_len or ratio < per_len[L][7]:
                    per_len[L] = (L, s, s + L, wi, med, mad, bar, ratio)
    return best, per_len, longest


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("dirs", nargs="+")
    ap.add_argument("--bar-ratio", type=float, default=BAR_RATIO)
    ap.add_argument("--min-len", type=int, default=MIN_LEN)
    ap.add_argument("--min-hf", type=float, default=MIN_HF)
    ap.add_argument("--min-motion", type=float, default=MIN_MOTION)
    ap.add_argument("--k", type=float, default=K_SIGMA)
    ap.add_argument("--cut-bar", type=float, default=None,
                    help="histogram TV distance that counts as a cut; the "
                         "default is derived per arm from its own "
                         "unrelated-frame pairing")
    args = ap.parse_args()

    wins = windows()
    print(f"{len(wins)} candidate {WIN[0]}x{WIN[1]} native windows in the "
          f"ground band y{GROUND_BAND[1]}..{GROUND_BAND[3]}")
    print(f"pass bar: length >= {args.min_len}, bar/median <= {args.bar_ratio}, "
          f"HF median >= {args.min_hf}, motion >= {args.min_motion}")
    print()

    verdicts = []
    for d in args.dirs:
        paths, nats, dropped = load_arm(d)
        n = len(nats)
        si = sample_interval(d, n)
        print(f"=== {d}: {n} frames with the dialog up"
              + (f", {dropped} dropped without it" if dropped else ""))
        if si:
            print(f"    sample interval median {si[0]:.2f} s "
                  f"(min {si[1]:.2f}, max {si[2]:.2f})")

        rgbs = [load_native_rgb(p) for p in paths]
        th = np.stack([thumbnail(a) for a in rgbs])
        hist = [colour_hist(a) for a in rgbs]
        motion = np.abs(np.diff(th, axis=0)).mean(axis=1)
        unrel = float(np.median(np.abs(
            th - th[np.random.default_rng(0).permutation(n)]).mean(axis=1)))
        print(f"    colour-thumb distance: consecutive median "
              f"{np.median(motion):.2f} (min {motion.min():.2f}, "
              f"max {motion.max():.2f}), unrelated pair {unrel:.2f}")

        # --- clause (a): is there a sustained SINGLE-SCENE segment? -------
        cb = args.cut_bar if args.cut_bar is not None else cut_bar(hist)
        dh = np.array([tv(hist[i], hist[i + 1]) for i in range(n - 1)])
        cuts = [i + 1 for i in range(n - 1) if dh[i] >= cb]
        segs, prev = [], 0
        for c in cuts + [n]:
            segs.append((prev, c))
            prev = c
        segs.sort(key=lambda t: t[1] - t[0], reverse=True)
        s0, e0 = segs[0]
        print(f"    cut bar {cb:.3f} (this run's own unrelated-pair median); "
              f"consecutive median {np.median(dh):.3f}; {len(cuts)} cuts")
        print(f"    LONGEST SINGLE-SCENE SEGMENT: {e0 - s0} frames "
              f"[{s0}..{e0}) = {(e0 - s0) * (si[0] if si else 0):.0f} s "
              f"-- needed {args.min_len}")
        print("    next longest: " + ", ".join(
            f"{b - a}f [{a}..{b})" for a, b in segs[1:5]))

        hfs = np.empty((len(wins), n), dtype=np.float64)
        for wi, (x, y) in enumerate(wins):
            for i, a in enumerate(nats):
                hfs[wi, i] = hf_energy(a[y:y + WIN[1], x:x + WIN[0]])

        # --- clause (b): is the bar set by the cuts, as the blocker says? --
        allmed, allmad, allbar = robust_bar(hfs.mean(axis=0), args.k)
        print(f"    whole soak, windows averaged: HF median {allmed:.2f} "
              f"mad {allmad:.2f} bar {allbar:.2f}  bar/median "
              f"{allbar / allmed:.3f}")
        segbars = []
        for a, b in sorted(segs, key=lambda t: t[0]):
            if b - a >= 5:
                m, _, br = robust_bar(hfs[:, a:b].mean(axis=0), args.k)
                if m > 0:
                    segbars.append(br / m)
        if segbars:
            print(f"    within-single-scene bar/median over the "
                  f"{len(segbars)} segments of >= 5 frames: median "
                  f"{np.median(segbars):.3f}, range "
                  f"{min(segbars):.3f}-{max(segbars):.3f}")

        best, per_len, longest = best_window_run(hfs, motion, args, wins)
        if best["all"]:
            L, s, e, wi, med, mad, bar, ratio = best["all"]
            ncut = sum(1 for c in cuts if s < c < e)
            print(f"    longest window with a usable bar: {L} frames "
                  f"[{s}..{e}) in {wins[wi]}, median {med:.2f} mad "
                  f"{mad:.2f} bar {bar:.2f} ratio {ratio:.3f} -- and it "
                  f"SPANS {ncut} cuts")
        else:
            print(f"    no window of >= {args.min_len} frames on live "
                  f"content reaches bar/median <= {args.bar_ratio}")
        verdicts.append((best["all"], e0 - s0))

        # Which guard, if any, was load-bearing. A null that only holds
        # because of a guard is a null about the guard.
        print("    longest qualifying run, by which guards are applied "
              f"(needed {args.min_len}):")
        for key, label in (("all", "ratio + HF + motion (the verdict)"),
                           ("no_hf", "ratio + motion, HF guard off"),
                           ("no_motion", "ratio + HF, motion guard off"),
                           ("ratio_only", "ratio alone, both guards off")):
            print(f"      {longest[key]:4d} frames   {label}")
        if args.min_len in per_len:
            c = per_len[args.min_len]
            print(f"    best {args.min_len}-frame run anywhere: ratio "
                  f"{c[7]:.3f} at [{c[1]}..{c[2]}) window {wins[c[3]]}, "
                  f"median {c[4]:.2f} mad {c[5]:.2f} "
                  f"-- needed <= {args.bar_ratio}")
        for L in (10, 15, 20, 25, 30, 40, 50):
            if L in per_len:
                c = per_len[L]
                flag = "ok " if (c[7] <= args.bar_ratio and c[4] >= args.min_hf) else "   "
                print(f"      {flag}L={L:3d}  best ratio {c[7]:.3f} "
                      f"[{c[1]}..{c[2]}) median {c[4]:.2f}")

        print()

    print("=" * 72)
    longest_scene = max(v[1] for v in verdicts)
    any_bar = any(v[0] is not None for v in verdicts)
    print(f"(a) sustained single-scene segment of >= {args.min_len} frames: "
          f"{'YES' if longest_scene >= args.min_len else 'NO'} "
          f"-- longest anywhere is {longest_scene} frames")
    print(f"(b) the bar is set by the cuts, as the blocker claims:      "
          f"{'NO' if any_bar else 'YES'} "
          f"-- windows spanning cuts still reach bar/median "
          f"<= {args.bar_ratio}")
    if longest_scene < args.min_len:
        print("\nVERDICT: the falsifier as registered FAILS -- no arm holds "
              "one scene for the registered length. But its stated MECHANISM "
              "is refuted by (b): the cuts are not what sets the bar.")
        return 1
    print("\nVERDICT: the blocker is FALSE -- a qualifying single-scene "
          "segment exists.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
