#!/usr/bin/env python3
"""Contact sheet of [boot1045] probe frames, each labelled with its present number and the probe's line for it.

usage: sheet.py <probe dir> <out.png> <n>[-<m>] ... [--cols C]
Frames that were not written (same hash as the one before) are skipped; the label carries src, start, bpp, nb, lit.
"""
import os
import re
import sys

from PIL import Image, ImageDraw

KV = re.compile(r"(\w+)=(\S+)")


def main():
    a = sys.argv[1:]
    d, out = a[0], a[1]
    cols = 4
    want = []
    i = 2
    while i < len(a):
        if a[i] == "--cols":
            cols = int(a[i + 1])
            i += 2
            continue
        if "-" in a[i]:
            lo, hi = (int(x) for x in a[i].split("-"))
            want.extend(range(lo, hi + 1))
        else:
            want.append(int(a[i]))
        i += 1
    lines = {}
    with open(os.path.join(d, "boot1045_log.txt"), errors="replace") as f:
        for line in f:
            kv = dict(KV.findall(line))
            if "n" in kv:
                lines[int(kv["n"])] = kv
    tiles = []
    for n in want:
        p = os.path.join(d, "boot1045_f%05u.ppm" % n)
        if not os.path.exists(p):
            continue
        kv = lines.get(n, {})
        label = "n=%d %s start=%s bpp=%s nb=%s lit=%s t=%s" % (
            n, kv.get("src", "?"), kv.get("start", "?"), kv.get("bpp", "?"), kv.get("nb", "?"), kv.get("lit", "?"),
            kv.get("t_ms", "?"))
        tiles.append((Image.open(p).convert("RGB"), label))
    if not tiles:
        print("no frames")
        return 1
    tw = max(t.size[0] for t, _ in tiles)
    th = max(t.size[1] for t, _ in tiles) + 14
    rows = (len(tiles) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * tw, rows * th), (40, 40, 40))
    dr = ImageDraw.Draw(sheet)
    for k, (t, label) in enumerate(tiles):
        x, y = (k % cols) * tw, (k // cols) * th
        sheet.paste(t, (x, y + 14))
        dr.text((x + 2, y + 1), label, fill=(255, 255, 0))
    sheet.save(out)
    print("%d frames -> %s" % (len(tiles), out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
