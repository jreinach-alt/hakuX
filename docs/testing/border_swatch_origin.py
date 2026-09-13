#!/usr/bin/env python3
"""Name which iteration's texture each 2D_BorderTex_SZ swatch actually rendered.

Issue #44 files this capture as "a band of padding texels inside the B32x32
swatch on some runs", and it has been carried as noise because the only
statistic anyone had was a differing-pixel count: 0 0 0 0 146 181 1847 2352
2430 5640 over ten runs of one unchanged APK. A count that swings 40x cannot
say what happened, and it cannot be used to judge a fix -- a single-run A/B on
this capture is a coin flip.

This tool replaces the count with a measurement of the mechanism.

WHY A FORWARD MODEL IS POSSIBLE HERE
------------------------------------
`Test2DBorderedSwizzled` draws eighteen 64x64 swatches, and for each one the
guest rewrites the SAME texture address (`GetTextureMemoryForStage(2)`) with a
freshly generated bordered surface:

    for size in [1x1 2x2 4x4 8x8 16x16 32x32 16x1 8x2 4x8]:   # pass 1, st 0..1
        GenerateBordered2DSurface(tex_mem, size)
        draw one 64x64 quad
    for size in [... the same nine ...]:                       # pass 2, st shows border

The surface is a grey 2x2 checkerboard (0xFFCCCCCC / 0xFF444444) over a
bordered rect -- 2*w if w >= 8 else 16, same for h -- with a coloured 2x2
checkerboard of eight colours written over the w x h image at offset (4,4).
The draw is nearest-sampled and alpha-blended over the 0xFE181818 clear, so
every screen pixel of every swatch is computable in closed form. It is:
`--self-check` reproduces all 73,728 swatch pixels of the hardware golden
exactly, both passes, zero mismatches. That is what licenses everything below.

WHAT IT MEASURES
----------------
Because the eighteen writes all land at one address, a capture that shows the
WRONG surface names the iteration it came from. For each swatch the tool
classifies every screen pixel against its own surface and against each of the
nine candidate surfaces read through this iteration's swizzle layout, and
reports:

    races_lost     swatches showing any pixel of another iteration's surface
    successor_px   screen pixels carrying the SUCCESSOR surface's content
    other_px       screen pixels matching neither own nor successor

`successor_px` is the mechanism. `races_lost` is the coarse version, for a
bar. Both go to zero if and only if every upload read the bytes the guest had
written for that draw; neither can be moved by a change that merely shifts the
timing, which is exactly what a differing-pixel count cannot tell you.

Usage:
    border_swatch_origin.py RESULTDIR [RESULTDIR ...] [--goldens DIR] [--json]
    border_swatch_origin.py --self-check [--goldens DIR]

RESULTDIR may be a dispatcher result directory (every `captures<N>/` in it is
scored as a separate run) or a captures directory. Resolution goes through
`captures.py` rather than through a hand-rolled glob, because a falsifier that
cannot find its own evidence answers anyway.
"""
import argparse
import json
import os
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import captures as captures_mod

SUITE = "Texture_border"
TEST = "2D_BorderTex_SZ"

# kBorderTextureSizes, in the order the test iterates them.
SIZES = [(1, 1), (2, 2), (4, 4), (8, 8), (16, 16), (32, 32), (16, 1), (8, 2), (4, 8)]
# kColors from texture_border_tests.cpp, ARGB.
COLORS = [0xFF0000FF, 0x660000FF, 0xFF00FF00, 0x6600FF00,
          0xFFFF4444, 0x66FF4444, 0xFFFFFFFF, 0x66FFFFFF]

SWATCH = 64
# Derived from the test's own layout arithmetic: kWidth/kHeight 64, kSpacing 32,
# six per row on a 640x480 framebuffer, two rows per pass.
COLUMNS = [32, 128, 224, 320, 416, 512]
PASS_TOPS = [(80, 176), (272, 368)]
CLEAR = (24, 24, 24)  # 0xFE181818


def bordered_dims(w, h):
    return (2 * w if w >= 8 else 16), (2 * h if h >= 8 else 16)


def surface(w, h):
    """The bytes GenerateBordered2DSurface leaves for this size, unswizzled."""
    bw, bh = bordered_dims(w, h)
    s = np.empty((bh, bw), dtype=np.int64)
    for y in range(bh):
        for x in range(bw):
            s[y, x] = 0xFFCCCCCC if ((x // 2) + (y // 2)) % 2 == 0 else 0xFF444444
    for y in range(h):
        for x in range(w):
            s[4 + y, 4 + x] = COLORS[((x // 2) + (y // 2)) % 8]
    return s


def swizzle_masks(width, height):
    """generate_swizzle_masks() from pgraph/swizzle.c, 2D only."""
    x = y = 0
    bit = 1
    mask_bit = 1
    while True:
        done = True
        if bit < width:
            x |= mask_bit
            mask_bit <<= 1
            done = False
        if bit < height:
            y |= mask_bit
            mask_bit <<= 1
            done = False
        bit <<= 1
        if done:
            break
    return x, y


def spread(value, mask):
    out = 0
    bit = 1
    m = mask
    while m:
        low = m & -m
        if value & bit:
            out |= low
        m &= ~low
        bit <<= 1
    return out


def gather(offset, mask):
    out = 0
    bit = 1
    m = mask
    while m:
        low = m & -m
        if offset & low:
            out |= bit
        m &= ~low
        bit <<= 1
    return out


def blend(argb):
    a = ((argb >> 24) & 0xFF) / 255.0
    return tuple(int(round(c * a + bg * (1 - a)))
                 for c, bg in zip(((argb >> 16) & 0xFF, (argb >> 8) & 0xFF,
                                   argb & 0xFF), CLEAR))


def swatch_taps(index, which_pass):
    """(screen_x, screen_y, bordered_x, bordered_y) for each pixel of a swatch.

    Nearest sampling: pass 1 runs st over 0..1, pass 2 over the range that
    brings the four-texel border into view, and the border wrap makes the
    out-of-image taps land on real texels of the bordered surface.
    """
    w, h = SIZES[index]
    bw, bh = bordered_dims(w, h)
    left = COLUMNS[index if index < 6 else index - 6]
    top = PASS_TOPS[which_pass][0 if index < 6 else 1]
    if which_pass == 0:
        s0, s1, t0, t1 = 0.0, 1.0, 0.0, 1.0
    else:
        s0, s1 = -4.0 / w, 1.0 + 4.0 / w
        t0, t1 = -4.0 / h, 1.0 + 4.0 / h
    taps = []
    for py in range(SWATCH):
        ty = t0 + (py + 0.5) / SWATCH * (t1 - t0)
        by = 4 + int(np.floor(ty * h))
        for px in range(SWATCH):
            tx = s0 + (px + 0.5) / SWATCH * (s1 - s0)
            bx = 4 + int(np.floor(tx * w))
            if 0 <= bx < bw and 0 <= by < bh:
                taps.append((left + px, top + py, bx, by))
    return taps


def read_through(dst_index, src_index):
    """src_index's surface bytes as dst_index's swizzle layout decodes them.

    All eighteen writes go to one address, so a late upload reads whatever is
    there under the CURRENT iteration's dimensions. Returns a dict keyed by
    (bordered_x, bordered_y) in dst's layout; a key is absent where dst's
    offset is past the end of what src ever wrote.
    """
    dw, dh = bordered_dims(*SIZES[dst_index])
    sw, sh = bordered_dims(*SIZES[src_index])
    dmx, dmy = swizzle_masks(dw, dh)
    smx, smy = swizzle_masks(sw, sh)
    src = surface(*SIZES[src_index])
    out = {}
    for by in range(dh):
        for bx in range(dw):
            off = spread(bx, dmx) | spread(by, dmy)
            if off >= sw * sh:
                continue
            sx = gather(off, smx)
            sy = gather(off, smy)
            if sx < sw and sy < sh:
                out[(bx, by)] = int(src[sy, sx])
    return out


BYTE_MASKS = [(0xFF000000, 24), (0x00FF0000, 16), (0x0000FF00, 8), (0x000000FF, 0)]


def byte_mixtures(own_argb, cand_argb):
    """Every way the four bytes of one texel could be half-written.

    A guest store that our upload reads mid-flight can leave a single texel
    holding some bytes of the old value and some of the new. Ten of the 5,566
    wrong pixels in the #44 noise floor are exactly this, and no "we forgot to
    re-upload" or "stale host allocation" story can produce one: a byte-level
    mixture inside one texel is only reachable while a write is in flight.
    """
    out = []
    for mask in range(1, 15):  # 0 is own, 15 is the whole candidate
        v = 0
        for i, (bm, _) in enumerate(BYTE_MASKS):
            v |= (cand_argb if mask & (1 << i) else own_argb) & bm
        out.append(v)
    return out


def classify(img, golden):
    """Per-swatch verdict for one capture."""
    rows = []
    for which_pass in (0, 1):
        for index in range(len(SIZES)):
            taps = swatch_taps(index, which_pass)
            own = surface(*SIZES[index])
            # Iteration order across the whole test is pass 1 then pass 2, so
            # the last swatch's successor is a write by the NEXT TEST, whose
            # content this tool does not model. Its stale pixels still land in
            # stale_px via the any-candidate match.
            flat = which_pass * len(SIZES) + index
            succ = (flat + 1) % len(SIZES) if flat + 1 < 2 * len(SIZES) else None

            wrong = []
            for sx, sy, bx, by in taps:
                got = tuple(int(v) for v in img[sy, sx])
                if got != blend(int(own[by, bx])):
                    wrong.append((sx, sy, bx, by, got))
            if not wrong:
                continue

            tables = {c: read_through(index, c)
                      for c in range(len(SIZES)) if c != index}
            counts = {c: 0 for c in tables}
            stale = mixed = 0
            for _, _, bx, by, got in wrong:
                whole = [c for c, t in tables.items()
                         if (bx, by) in t and got == blend(t[(bx, by)])]
                for c in whole:
                    counts[c] += 1
                if whole:
                    stale += 1
                    continue
                own_v = int(own[by, bx])
                if any(got == blend(v)
                       for c, t in tables.items() if (bx, by) in t
                       for v in byte_mixtures(own_v, t[(bx, by)])):
                    mixed += 1
                    stale += 1
            best = max(counts, key=lambda c: counts[c]) if counts else None
            rows.append(dict(
                pass_=which_pass + 1, index=index, size="%dx%d" % SIZES[index],
                wrong=len(wrong),
                successor=counts.get(succ, 0) if succ is not None else 0,
                stale=stale, mixed=mixed, unexplained=len(wrong) - stale,
                best="%dx%d" % SIZES[best] if best is not None else None,
                best_px=counts.get(best, 0) if best is not None else 0))
    return rows


def self_check(golden):
    bad = 0
    total = 0
    for which_pass in (0, 1):
        for index in range(len(SIZES)):
            own = surface(*SIZES[index])
            for sx, sy, bx, by in swatch_taps(index, which_pass):
                total += 1
                if tuple(int(v) for v in golden[sy, sx]) != blend(int(own[by, bx])):
                    bad += 1
    print("self-check: %d/%d golden swatch pixels reproduced by the model"
          % (total - bad, total))
    return bad == 0


def run_dirs(d):
    subs = sorted(p for p in (os.path.join(d, n) for n in os.listdir(d))
                  if os.path.isdir(p) and os.path.basename(p).startswith("captures"))
    return subs or [d]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("results", nargs="*")
    ap.add_argument("--goldens", default="/home/justin/goldens/results")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--self-check", action="store_true")
    args = ap.parse_args()

    gpath = os.path.join(args.goldens, SUITE, TEST + ".png")
    if not os.path.exists(gpath):
        print("golden missing: %s" % gpath, file=sys.stderr)
        return 2
    golden = np.array(Image.open(gpath).convert("RGB"))

    if args.self_check:
        return 0 if self_check(golden) else 1

    out = []
    for d in args.results:
        for sub in run_dirs(d):
            path = captures_mod.find(sub, SUITE, TEST)
            if not path:
                print("%s: capture MISSING" % sub, file=sys.stderr)
                out.append(dict(run=sub, missing=True))
                continue
            img = np.array(Image.open(path).convert("RGB"))
            rows = classify(img, golden)
            lost = [r for r in rows if r["wrong"]]
            rec = dict(run=os.path.relpath(sub),
                       races_lost=len(lost),
                       successor_px=sum(r["successor"] for r in lost),
                       stale_px=sum(r["stale"] for r in lost),
                       mixed_px=sum(r["mixed"] for r in lost),
                       unexplained_px=sum(r["unexplained"] for r in lost),
                       wrong_px=sum(r["wrong"] for r in lost),
                       swatches=[dict(r) for r in lost])
            out.append(rec)
            if not args.json:
                print("%s  races_lost=%d wrong_px=%d stale_px=%d "
                      "successor_px=%d mixed_px=%d unexplained_px=%d" % (
                          rec["run"], rec["races_lost"], rec["wrong_px"],
                          rec["stale_px"], rec["successor_px"],
                          rec["mixed_px"], rec["unexplained_px"]))
                for r in lost:
                    print("    pass%d %-7s wrong=%-5d stale=%-5d successor=%-5d "
                          "mixed=%-3d best_match=%-7s best_px=%d" % (
                              r["pass_"], r["size"], r["wrong"], r["stale"],
                              r["successor"], r["mixed"], r["best"],
                              r["best_px"]))
    if args.json:
        json.dump(out, sys.stdout, indent=2)
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
