#!/usr/bin/env python3
"""Per-channel darkening of a region, Nova frame against a frame-matched desktop frame (#1038).

  tint.py NOVA.png DESK.png NAME:X0,Y0,X1,Y1[:DX,DY] ...
For each region: mean r,g,b on both frames (the desktop region shifted by DX,DY for the camera
offset between the two shots) and the ratio Nova / desktop per channel. A control region outside
the square should read ~1.0 in all three; a grey darkening reads equal ratios, a tinted one not.
"""
import sys
from PIL import Image


def mean(im, box):
    px = list(im.crop(box).getdata())
    return [sum(p[c] for p in px) / len(px) for c in range(3)]


def main():
    nova = Image.open(sys.argv[1]).convert("RGB")
    desk = Image.open(sys.argv[2]).convert("RGB")
    for spec in sys.argv[3:]:
        parts = spec.split(":")
        name, box = parts[0], tuple(map(int, parts[1].split(",")))
        dx, dy = map(int, parts[2].split(",")) if len(parts) > 2 else (0, 0)
        n = mean(nova, box)
        d = mean(desk, (box[0] + dx, box[1] + dy, box[2] + dx, box[3] + dy))
        r = [n[c] / d[c] if d[c] else float("nan") for c in range(3)]
        print(f"{name:10s} nova {n[0]:6.1f},{n[1]:6.1f},{n[2]:6.1f}  "
              f"desk {d[0]:6.1f},{d[1]:6.1f},{d[2]:6.1f}  "
              f"ratio r {r[0]:.3f} g {r[1]:.3f} b {r[2]:.3f}")


if __name__ == "__main__":
    main()
