#!/usr/bin/env python3
"""Sheet of [boot1045] RAM dumps decoded as the VGA view draws them, next to window frames.

usage: ramsheet.py <probe dir> <out.png> r<n> ... f<n> ...
r<n>: boot1045_r<n>.bin decoded at the present's logged vga size and bpp (32 bpp only: B,G,R,X), at 320x240.
f<n>: the window frame boot1045_f<n>.ppm (or the latest one written before n). Each tile is labelled with its probe line.
"""
import os
import re
import sys

from PIL import Image, ImageDraw

KV = re.compile(r"(\w+)=(\S+)")
TW, TH = 320, 240


def main():
    d, out = sys.argv[1], sys.argv[2]
    log = {}
    with open(os.path.join(d, "boot1045_log.txt"), errors="replace") as f:
        for line in f:
            kv = dict(KV.findall(line))
            if "n" in kv and "src" in kv:
                log[int(kv["n"])] = kv
    tiles = []
    for w in sys.argv[3:]:
        n = int(w[1:])
        kv = log[n]
        if w[0] == "r":
            vw, vh = (int(x) for x in kv["vga"].split("x"))
            raw = open(os.path.join(d, "boot1045_r%05u.bin" % n), "rb").read()
            pitch = int(kv["lo"]) or vw * 4
            rows = min(vh, len(raw) // pitch)
            img = Image.new("RGB", (vw, vh))
            px = img.load()
            for y in range(rows):
                o = y * pitch
                for x in range(vw):
                    p = o + x * 4
                    px[x, y] = (raw[p + 2], raw[p + 1], raw[p])
            img = img.resize((TW, TH), Image.NEAREST)
            label = "RAM n=%d start=%s sr01=%s %s" % (n, kv["start"], kv["sr01"], kv["vga"])
        else:
            m = max(k for k in range(n + 1) if os.path.exists(os.path.join(d, "boot1045_f%05u.ppm" % k)))
            img = Image.open(os.path.join(d, "boot1045_f%05u.ppm" % m)).convert("RGB").resize((TW, TH))
            label = "window n=%d (f%d) sr01=%s nb=%s" % (n, m, kv["sr01"], kv["nb"])
        tiles.append((img, label))
    sheet = Image.new("RGB", (TW * len(tiles), TH + 16), (40, 40, 40))
    dr = ImageDraw.Draw(sheet)
    for i, (img, label) in enumerate(tiles):
        sheet.paste(img, (i * TW, 16))
        dr.text((i * TW + 2, 2), label, fill=(255, 255, 0))
    sheet.save(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
