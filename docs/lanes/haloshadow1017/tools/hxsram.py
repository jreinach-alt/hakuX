#!/usr/bin/env python3
"""Guest-RAM view of a save state's render targets (#1038).

  hxsram.py STREAM OUTDIR ADDR:W:H:FMT[:sw] [ADDR:W:H:FMT[:sw] ...]

STREAM is the raw migration stream docs/lanes/audio1016/tools/hxs_unpack.py
writes. A save state runs pgraph_vk_pre_savevm_trigger first, which downloads
every draw-dirty surface into guest RAM, so RAM at a render target's address
holds that target's host content at the moment of the save.

FMT: 565 (R5G6B5), 8888 (A8R8G8B8, little-endian BGRA in memory). ':sw' reads
the bytes as NV2A-swizzled (Morton, x in the low bit); without it, linear with
pitch W*bpp. Writes OUTDIR/<addr>.png (and a x4 enlargement) and prints, per
target: distinct texel values, the top values with their counts, and the
per-channel mean, min and max as 0-255.
"""
import collections
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "audio1016", "tools"))
import hxs_voices  # noqa: E402
from PIL import Image  # noqa: E402


def swz_masks(w, h):
    mx = my = 0
    bit = 1
    i = 1
    while i < w or i < h:
        if i < w:
            mx |= bit
            bit <<= 1
        if i < h:
            my |= bit
            bit <<= 1
        i <<= 1
    return mx, my


def pdep(v, mask):
    out = 0
    b = 1
    m = mask
    while m:
        low = m & -m
        if v & b:
            out |= low
        b <<= 1
        m &= m - 1
    return out


def decode(raw, w, h, fmt, sw):
    bpp = 2 if fmt == "565" else 4
    mx, my = swz_masks(w, h)
    px = []
    vals = []
    for y in range(h):
        for x in range(w):
            idx = (pdep(x, mx) | pdep(y, my)) if sw else (y * w + x)
            o = idx * bpp
            v = int.from_bytes(raw[o:o + bpp], "little")
            vals.append(v)
            if fmt == "565":
                r5, g6, b5 = (v >> 11) & 31, (v >> 5) & 63, v & 31
                px.append(((r5 << 3) | (r5 >> 2), (g6 << 2) | (g6 >> 4),
                           (b5 << 3) | (b5 >> 2)))
            else:
                px.append(((v >> 16) & 255, (v >> 8) & 255, v & 255))
    return px, vals


def main():
    stream, outdir = sys.argv[1], sys.argv[2]
    data = open(stream, "rb").read()
    blocks, _, _ = hxs_voices.parse(data)
    # pc.ram and xbox.ram are both 64 MiB; the guest's pages are in xbox.ram
    name = "xbox.ram" if "xbox.ram" in blocks else max(blocks, key=lambda k: len(blocks[k]))
    ram = blocks[name]
    print(f"ram block {name!r} {len(ram):#x} bytes; blocks {sorted(blocks)}")
    os.makedirs(outdir, exist_ok=True)
    for spec in sys.argv[3:]:
        parts = spec.split(":")
        addr, w, h, fmt = int(parts[0], 16), int(parts[1]), int(parts[2]), parts[3]
        sw = len(parts) > 4 and parts[4] == "sw"
        bpp = 2 if fmt == "565" else 4
        raw = bytes(ram[addr:addr + w * h * bpp])
        px, vals = decode(raw, w, h, fmt, sw)
        im = Image.new("RGB", (w, h))
        im.putdata(px)
        base = os.path.join(outdir, f"{addr:08x}{'_sw' if sw else ''}")
        im.save(base + ".png")
        im.resize((w * 4, h * 4), Image.NEAREST).save(base + "_x4.png")
        c = collections.Counter(vals)
        print(f"{addr:#010x} {w}x{h} {fmt}{' sw' if sw else ''}: {len(c)} distinct; top "
              + ", ".join(f"{v:#06x}x{n}" for v, n in c.most_common(6)))
        for ch, nm in enumerate("RGB"):
            col = [p[ch] for p in px]
            print(f"   {nm} mean {sum(col) / len(col):6.1f} min {min(col):3d} max {max(col):3d}")
        print(f"   -> {base}.png")


if __name__ == "__main__":
    main()
