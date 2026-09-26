#!/usr/bin/env python3
"""#285: price the B8/G8B8 byte-0 rule against a capture and the golden.

Surface_format renders tex3 into a B8 or G8B8 surface, then samples that
memory as a 640x480 A8R8G8B8 texture. So each 32-bit texel is several surface
pixels: for G8B8, texel (B, G, R, A) = (B[2x], G[2x], B[2x+1], G[2x+1]); for
B8, (B, G, R, A) = (B[4x], B[4x+1], B[4x+2], B[4x+3]). The bottom half of the
frame shows those texels opaque, so it reads the stored bytes directly.

tex3 is GenerateRGBRadialATestPattern: four 64x64 copies of
(R, G, B) = (255 - yn, xn, yn), so src.r = 255 - src.b everywhere.

Two rules for the byte the surface holds as "B":
  ours    B <- src.r  (R8/R8G8 host format, fragment .r lands in byte 0)
  silicon B <- src.b
Each is scored on the bottom half, R/G/B channels, label columns (x < 90)
excluded. A rule that is right scores ~0 against its own image.

usage: derive_g8b8.py <capture dir> [goldens dir]
"""
import os
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..",
                                "testing"))
import captures  # noqa: E402


def load(p):
    return np.array(Image.open(p).convert("RGBA")).astype(int)


def surface_src():
    t = np.zeros((128, 128, 3), int)
    for y in range(64):
        yn = int(np.float32(y) * np.float32(255.0) / np.float32(64))
        for x in range(64):
            xn = int(np.float32(x) * np.float32(255.0) / np.float32(64))
            for oy in (0, 64):
                for ox in (0, 64):
                    t[oy + y, ox + x] = (255 - yn, xn, yn)
    s = np.zeros((480, 640, 3), int)
    left = (640 - (128 * 2 + 16)) // 2
    for x0 in (left, left + 128 + 16):
        s[96:224, x0:x0 + 128] = t
    return s


def texels(s, b_chan, fmt):
    """The 240x640 texel image (B, G, R, A planes) for one B-byte rule."""
    if fmt == "G8B8":
        # 1280-byte rows; texel row Y covers surface rows 2Y and 2Y+1.
        out = np.zeros((240, 640, 4), int)
        for y in range(240):
            for h in (0, 1):
                row, sl = s[2 * y + h], slice(h * 320, (h + 1) * 320)
                out[y, sl, 0] = row[0::2, b_chan]
                out[y, sl, 1] = row[0::2, 1]
                out[y, sl, 2] = row[1::2, b_chan]
                out[y, sl, 3] = row[1::2, 1]
        return out
    stream = np.zeros(240 * 2560, int)
    b = s[..., b_chan].reshape(-1)
    stream[:len(b)] = b
    return stream.reshape(240, 640, 4)


def wrong(tex, img):
    bot = img[240:]
    d = np.maximum.reduce([np.abs(tex[..., 2] - bot[..., 0]),
                           np.abs(tex[..., 1] - bot[..., 1]),
                           np.abs(tex[..., 0] - bot[..., 2])])
    d[:, :90] = 0
    return int((d > 0).sum())


def main():
    cap = sys.argv[1]
    gold = sys.argv[2] if len(sys.argv) > 2 else os.path.expanduser(
        "~/goldens/results/Surface_format")
    s = surface_src()
    for fmt in ("G8B8", "B8"):
        p = captures.find(cap, "Surface_format", "Fmt_" + fmt)
        if not p:
            print("Fmt_%s: MISSING in %s" % (fmt, cap))
            continue
        ours = load(p)
        g = load(os.path.join(gold, "Fmt_%s.png" % fmt))
        diff = np.abs(ours - g).max(2) > 0
        print("Fmt_%s: capture vs golden %d px; per channel R/G/B/A %s" % (
            fmt, diff.sum(),
            [int((ours[..., c] != g[..., c]).sum()) for c in range(4)]))
        for name, ch, img in (("B<-src.r vs capture", 0, ours),
                              ("B<-src.b vs golden ", 2, g),
                              ("B<-src.r vs golden ", 0, g)):
            print("  %s: %6d bottom px wrong" % (name,
                                                 wrong(texels(s, ch, fmt), img)))


if __name__ == "__main__":
    main()
