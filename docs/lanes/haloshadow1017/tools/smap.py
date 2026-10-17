#!/usr/bin/env python3
"""What the Nova's square sampled: per-pixel S = 1 - nova/desktop over a region (#1038).

  smap.py NOVA.png DESK.png X0,Y0,X1,Y1 DX,DY OUTPREFIX
dst' = dst * (1 - S) with S = (1-t1) * v0.a * t0 * (1-c0); t1, v0.a and c0 are grey, so per pixel
S_g/S_r = t0.g/t0.r and S_b/S_r = t0.b/t0.r: the hue of what stage 0 sampled, free of the falloff.
Writes OUTPREFIX_s.png (S, contrast-stretched, x4) and OUTPREFIX_hue.png (t0's hue normalised to
its max channel, where S > 0.05), and prints rows of S and a histogram of the hue ratios.
"""
import sys
from collections import Counter
from PIL import Image


def main():
    nova = Image.open(sys.argv[1]).convert("RGB")
    desk = Image.open(sys.argv[2]).convert("RGB")
    x0, y0, x1, y1 = map(int, sys.argv[3].split(","))
    dx, dy = map(int, sys.argv[4].split(","))
    out = sys.argv[5]
    w, h = x1 - x0, y1 - y0
    s_img = Image.new("RGB", (w, h))
    hue_img = Image.new("RGB", (w, h))
    gr, br = Counter(), Counter()
    rows = []
    for y in range(h):
        row = []
        for x in range(w):
            n = nova.getpixel((x0 + x, y0 + y))
            d = desk.getpixel((x0 + x + dx, y0 + y + dy))
            s = [max(0.0, 1 - n[c] / d[c]) if d[c] > 8 else 0.0 for c in range(3)]
            s_img.putpixel((x, y), tuple(min(255, int(v * 400)) for v in s))
            if s[0] > 0.05 and s[1] > 0.05 and s[2] > 0.05:
                m = max(s)
                hue_img.putpixel((x, y), tuple(int(255 * v / m) for v in s))
                gr[round(s[1] / s[0], 1)] += 1
                br[round(s[2] / s[0], 1)] += 1
            row.append(s)
        rows.append(row)
    s_img.resize((w * 4, h * 4), Image.NEAREST).save(out + "_s.png")
    hue_img.resize((w * 4, h * 4), Image.NEAREST).save(out + "_hue.png")
    step = max(1, w // 14)
    for y in range(0, h, 3):
        print(f"y{y0 + y:4d} " + " ".join(f"{int(100 * p[0]):2d}/{int(100 * p[1]):2d}/{int(100 * p[2]):2d}"
                                         for p in rows[y][::step]))
    print("S_g/S_r:", sorted(gr.items()))
    print("S_b/S_r:", sorted(br.items()))


if __name__ == "__main__":
    main()
