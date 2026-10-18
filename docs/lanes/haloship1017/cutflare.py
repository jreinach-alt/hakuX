#!/usr/bin/env python3
"""The judge across the cut: per frame, the rear lights' tests and their flares (#1039).

usage: cutflare.py DUMP.jsonl ZREP.txt [--from F] [--to F] [--lo HEX --hi HEX]

Halo tests each light with a pixel count (GET_REPORT at 0x60000 + 16 k; the
ship's 12 rear lights are 0x60200-0x602b0) and draws its flare later in the
frame as a quad of shader 7d6aedad with the depth test OFF, its brightness the
alpha of attribute 9 (r4b: 0.53-0.76 behind; colour (0.369,0.886,1) for the
engines' 8 quads, (0.259,0.478,1) for the other 4). A rear flare drawn in a
front frame is the defect, whatever the image shows: nothing on the GPU can
hide it.

One line per frame:
  f nv2a  own nz/sum  early n  ans nz/sum  flares [rgb x n a min-max] ...
  - own: the rear tests' own counts (HAKUX_ZREP "r" value), nonzero / total;
  - early: how many were answered early (HAKUX_REPORT_EARLY), and ans what the
    guest was given: the own count, or for an early one the previous own count
    at the same offset (reports.c: the offset's last value when queued; one or
    two frames old -- the zrep line does not say which);
  - flares: the frame's 7d6aedad quads grouped by attribute 9's colour, with
    their alpha range (gd "va" replayed, as flares.py).
"""
import json
import struct
import sys


def f32(u):
    return struct.unpack("<f", struct.pack("<I", u & 0xFFFFFFFF))[0]


def main():
    a = sys.argv[1:]

    def opt(k, d, conv):
        if k in a:
            i = a.index(k)
            v = conv(a[i + 1])
            del a[i:i + 2]
            return v
        return d

    f0 = opt("--from", 0, int)
    f1 = opt("--to", 1 << 30, int)
    lo = opt("--lo", 0x60200, lambda s: int(s, 16))
    hi = opt("--hi", 0x602c0, lambda s: int(s, 16))
    dump, zrep = a[:2]

    own = {}
    prev_at = {}
    last = {}
    for line in open(zrep, errors="replace"):
        p = line.split()
        if len(p) == 6 and p[0] == "r":
            rs, off, v, early = int(p[1]), int(p[3], 16), int(p[4]), int(p[5])
            own[rs] = (off, v, early)
            prev_at[rs] = last.get(off)
            last[off] = v

    frames = {}
    va = [0] * 64
    for line in open(dump, errors="replace"):
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        t = rec.get("t")
        f = rec.get("f")
        if t == "draw":
            d = (rec.get("gd") or {}).get("va") or []
            for i in range(0, len(d) - 1, 2):
                va[d[i]] = d[i + 1]
        if f is None or not (f0 <= f <= f1):
            continue
        fr = frames.setdefault(f, {"nv2a": "?", "tests": [], "fl": {}})
        if t == "frame":
            fr["nv2a"] = rec.get("nv2a_frame", "?")
        elif t == "rep" and not rec.get("clr") and rec["rs"] in own:
            off, v, early = own[rec["rs"]]
            if lo <= off < hi:
                ans = prev_at[rec["rs"]] if early else v
                fr["tests"].append((v, early, ans))
        elif t == "draw" and rec["shader"].startswith("7d6aedad"):
            rgb = tuple(round(f32(va[36 + c]), 2) for c in range(3))
            al = f32(va[39])
            fr["fl"].setdefault(rgb, []).append(al)

    print("f nv2a own(nz/sum) early ans(nz/sum) flares")
    for f in sorted(frames):
        fr = frames[f]
        ts = fr["tests"]
        own_nz = sum(1 for v, _, _ in ts if v)
        ans = [x for _, _, x in ts if x is not None]
        fl = " ".join(f"({','.join(f'{c:g}' for c in k)})x{len(v)} "
                      f"a{min(v):.3f}-{max(v):.3f}"
                      for k, v in sorted(fr["fl"].items())) or "-"
        print(f"{f} {fr['nv2a']} {own_nz}/{sum(v for v, _, _ in ts)} "
              f"{sum(1 for _, e, _ in ts if e)} "
              f"{sum(1 for x in ans if x)}/{sum(ans)} {fl}")


if __name__ == "__main__":
    main()
