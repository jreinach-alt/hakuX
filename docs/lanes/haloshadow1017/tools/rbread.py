#!/usr/bin/env python3
"""Readbacks of Halo's shadow chain in a frame dump (#1038), schema 10 with rttmax16384.

  rbread.py DUMP.jsonl [F]       per projection draw (BLEND 0x30a, stage 0 SZ_R5G6B5 128x128):
                                 stage 0's sampled image (tex0) against its host surface (srf0),
                                 decoded the way the shader sees them, and the target's darkening
                                 (post/pre) inside the draw's changed pixels
  rbread.py DUMP.jsonl F N png   writes tex0/srf0 x4 PNGs and a pre/post/diff strip for draw N

Values are 0..255 per channel. "tex0==srf0" compares tex0's rgb with srf0's 565 widened by bit
replication (the CPU decode, f009555537). The darkening ratio is post/pre per channel over the
pixels the draw changed, so a neutral texel (black) shows as no changed pixels at all.
"""
import json, os, sys
from collections import Counter

VK_RGBA8, VK_BGRA8, VK_R5G6B5, VK_A1R5G5B5 = 37, 44, 4, 8


def load(path):
    draws = []
    for ln in open(path):
        try:
            o = json.loads(ln)
        except ValueError:
            continue
        if o.get("t") == "draw":
            draws.append(o)
    return draws


def rd(dirn, rb):
    data = open(os.path.join(dirn, rb["file"]), "rb").read()
    w, h, f = rb["w"], rb["h"], rb["vkfmt"]
    px = []
    if f in (VK_RGBA8, VK_BGRA8):
        for i in range(w * h):
            b = data[4 * i:4 * i + 4]
            px.append((b[0], b[1], b[2], b[3]) if f == VK_RGBA8 else (b[2], b[1], b[0], b[3]))
    elif f == VK_R5G6B5:
        for i in range(w * h):
            v = data[2 * i] | data[2 * i + 1] << 8
            r, g, b = v >> 11, (v >> 5) & 63, v & 31
            px.append(((r << 3) | (r >> 2), (g << 2) | (g >> 4), (b << 3) | (b >> 2), 255))
    elif f == VK_A1R5G5B5:
        for i in range(w * h):
            v = data[2 * i] | data[2 * i + 1] << 8
            r, g, b = (v >> 10) & 31, (v >> 5) & 31, v & 31
            px.append(((r << 3) | (r >> 2), (g << 3) | (g >> 2), (b << 3) | (b >> 2),
                       255 if v >> 15 else 0))
    else:
        return None
    return w, h, px


def is_proj(d):
    t = d["tex"][0] if d["tex"] else {}
    return d["rs"]["blend"] == "0x0000030a" and t.get("fmt") == "0x0771058a"


def summary(dirn, d):
    rbs = {(r["k"], r["s"]): r for r in d.get("rb", [])}
    t0 = d["tex"][0]
    out = [f"f{d['f']} n{d['n']} bv={t0.get('bv')} img={t0.get('img')} pv={t0.get('pv')} "
           f"s2t={t0.get('s2t')} ptd={d.get('ptd')}"]
    tex = rd(dirn, rbs[("tex", 0)]) if ("tex", 0) in rbs else None
    srf = rd(dirn, rbs[("srf", 0)]) if ("srf", 0) in rbs else None
    if tex:
        c = Counter(p[:3] for p in tex[2])
        out.append(f"  tex0 {len(c)} rgb values, top {c.most_common(4)}")
    if srf:
        c = Counter(p[:3] for p in srf[2])
        out.append(f"  srf0 {len(c)} rgb values, top {c.most_common(4)}")
    if tex and srf and len(tex[2]) == len(srf[2]):
        diff = sum(1 for a, b in zip(tex[2], srf[2]) if a[:3] != b[:3])
        out.append(f"  tex0==srf0: {len(tex[2]) - diff}/{len(tex[2])} texels equal")
    pre = rd(dirn, rbs[("pre", -1)]) if ("pre", -1) in rbs else None
    post = rd(dirn, rbs[("post", -1)]) if ("post", -1) in rbs else None
    if pre and post:
        ch = [(a, b) for a, b in zip(pre[2], post[2]) if a[:3] != b[:3]]
        if ch:
            sums = [0.0, 0.0, 0.0]
            n = 0
            for a, b in ch:
                if min(a[:3]) >= 16:
                    for k in range(3):
                        sums[k] += b[k] / a[k]
                    n += 1
            rat = " ".join(f"{s / n:.3f}" for s in sums) if n else "-"
            out.append(f"  target: {len(ch)} px changed; mean post/pre r g b over {n} lit px: {rat}")
        else:
            out.append("  target: 0 px changed")
    return "\n".join(out)


def png(dirn, d, outdir):
    from PIL import Image
    rbs = {(r["k"], r["s"]): r for r in d.get("rb", [])}
    tag = f"f{d['f']:03d}_n{d['n']:04d}"
    for k in (("tex", 0), ("srf", 0)):
        if k in rbs:
            w, h, px = rd(dirn, rbs[k])
            im = Image.new("RGB", (w, h))
            im.putdata([p[:3] for p in px])
            im.resize((w * 4, h * 4), Image.NEAREST).save(os.path.join(outdir, f"{tag}_{k[0]}{k[1]}_x4.png"))
    if ("pre", -1) in rbs and ("post", -1) in rbs:
        w, h, a = rd(dirn, rbs[("pre", -1)])
        _, _, b = rd(dirn, rbs[("post", -1)])
        strip = Image.new("RGB", (w * 3, h))
        for i, px in enumerate((a, b)):
            im = Image.new("RGB", (w, h))
            im.putdata([p[:3] for p in px])
            strip.paste(im, (i * w, 0))
        im = Image.new("RGB", (w, h))
        im.putdata([(255, 0, 255) if p[:3] != q[:3] else (q[0] // 3, q[1] // 3, q[2] // 3)
                    for p, q in zip(a, b)])
        strip.paste(im, (2 * w, 0))
        strip.save(os.path.join(outdir, f"{tag}_prepost.png"))


def main():
    path = sys.argv[1]
    dirn = os.path.dirname(os.path.abspath(path))
    draws = load(path)
    if len(sys.argv) >= 5 and sys.argv[4] == "png":
        f, n = int(sys.argv[2]), int(sys.argv[3])
        d = next(x for x in draws if x["f"] == f and x["n"] == n)
        png(dirn, d, dirn)
        return
    want = int(sys.argv[2]) if len(sys.argv) > 2 else None
    for d in draws:
        if is_proj(d) and (want is None or d["f"] == want):
            print(summary(dirn, d))


if __name__ == "__main__":
    main()
