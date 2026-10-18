"""Each ring draw's texture-unit registers, decoded (#939, (a), M7).

usage: texregs.py DUMP.jsonl FRAME

For n4 and n5 at FRAME, per stage 0-3: TEXOFFSET, TEXFMT (dimensionality,
colour format, mip levels, log2 sizes), TEXCTL0 (enable, the two LOD clamps
in both bit assignments, since the field names in nv2a_regs.h and in the
NV097 method names disagree on which is min and which is max), TEXCTL1
(pitch), TEXFILTER (LOD bias as 4.8 signed, min and mag filters, the signed
channel bits) and TEXADDRESS (the wrap modes). A clamp or bias hakuX ignores
moves the mip a detail map is read at, and so its mean.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "x1port1012", "tools"))
import gdread as g  # noqa: E402

NAMES = {864: "n4", 4362: "n5"}
dump, frame = sys.argv[1], int(sys.argv[2])
session, draws, frames, skips, shaders = g.load(dump)
for d in draws:
    for k in ("f", "n", "count"):
        d[k] = int(d[k])
st = g.replay(draws, {frame})
fd = {NAMES[d["count"]]: d for d in draws if d["f"] == frame and d["count"] in NAMES}


def s13(v):
    v &= 0x1fff
    return (v - 0x2000 if v & 0x1000 else v) / 256.0


for name in ("n4", "n5"):
    d = fd[name]
    r = st[(frame, d["n"])]["r"]
    print(f"== f{frame} {name} (draw {d['n']})")
    for s in range(4):
        off, fmt = r[0x1A24 + 4 * s], r[0x1A04 + 4 * s]
        ctl0, ctl1, ctl2 = r[0x19CC + 4 * s], r[0x19DC + 4 * s], r[0x19EC + 4 * s] if s < 2 else None
        filt, addr = r[0x19F4 + 4 * s], r[0x19BC + 4 * s]
        dim = (fmt >> 4) & 0xf
        cfmt = (fmt >> 8) & 0x7f
        mips = (fmt >> 16) & 0xf
        bu, bv, bp = (fmt >> 20) & 0xf, (fmt >> 24) & 0xf, (fmt >> 28) & 0xf
        lo12, hi12 = (ctl0 >> 6) & 0xfff, (ctl0 >> 18) & 0xfff
        print(f"   s{s}: off {off:#010x} fmt {fmt:#010x} (dim {dim} cfmt {cfmt:#04x} mips {mips} log2 {bu}x{bv}x{bp} "
              f"cube {(fmt >> 2) & 1})")
        print(f"       ctl0 {ctl0:#010x} enable {(ctl0 >> 30) & 1}; bits 6-17 = {lo12} ({lo12 / 256:.3f}), "
              f"bits 18-29 = {hi12} ({hi12 / 256:.3f}); aniso {(ctl0 >> 4) & 3}; colour key {ctl0 & 3}")
        print(f"       ctl1 {ctl1:#010x} pitch {ctl1 >> 16}" + (f"; ctl2 {ctl2:#010x}" if ctl2 is not None else ""))
        print(f"       filter {filt:#010x}: lod bias {s13(filt):+.3f}; min {(filt >> 16) & 0x3f} mag {(filt >> 24) & 0xf} "
              f"signed rgba bits {(filt >> 28) & 0xf:04b}; convolution {(filt >> 13) & 7}")
        print(f"       address {addr:#010x}: u {addr & 0xf} wrapu {(addr >> 4) & 1} v {(addr >> 8) & 0xf} "
              f"wrapv {(addr >> 12) & 1} p {(addr >> 16) & 0xf} wrapp {(addr >> 20) & 1}")
