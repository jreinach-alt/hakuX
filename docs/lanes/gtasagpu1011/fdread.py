#!/usr/bin/env python3
"""Read a schema-4/5/6/7 live frame dump (framedump_<id>.jsonl) by draw.

  fdread.py DUMP targets            colour targets per frame, draws on each
  fdread.py DUMP draws F [A [B]]    frame F's draws A..B, state decoded
  fdread.py DUMP rtt                draws sampling a rendered surface, and
                                    draws sampling their own colour target
  fdread.py DUMP shader HASH        one shader record (combiners + GLSL)
  fdread.py DUMP vhaz [SHADER]      schema 5: per frame, the draws whose
                                    vertex RAM a later upload in the same
                                    command buffer ("rot") changed; with
                                    SHADER (a hash prefix), that shader's
                                    draws only, hit or not
  fdread.py DUMP means [X0 Y0 X1 Y1]  mean RGB of a region of each frame's
                                    image (default the sky top, 180,0-480,20)
  fdread.py DUMP rb [F [OUTDIR]]    schema 6 (`rtt`): each readback ("rb") of
                                    frame F (default all): texels with any
                                    channel above 32 ("lit"), mean RGBA; with
                                    OUTDIR, one PNG per readback (x4) and a
                                    sheet per frame, f<F>_sheet.png
  fdread.py DUMP cons [OUTDIR [X0 Y0 X1 Y1]]
                                    schema 7: per consumer draw (one that
                                    samples a small target into a large one),
                                    the pixels its "pre" and "post" readbacks
                                    differ in (any channel by more than 2),
                                    their box and mean change, and the depth
                                    before it ("zpre") over the image and over
                                    the box X0..X1 x Y0..Y1 when given; with
                                    OUTDIR, pre/post/diff/zpre PNGs
  fdread.py DUMP cover F N [OUTDIR]
                                    an FF TRIANGLES draw's coverage worked
                                    out from its "v" and "cm" words, one
                                    pixel centre at a time and correct for
                                    vertices behind the eye (w < 0): the
                                    pixels it covers, its depth and UV
                                    there, the stage-0 "tex" readback's
                                    texel at that UV, and, with schema 7's
                                    readbacks, how many covered pixels pass
                                    LEQUAL against "zpre" and how many
                                    "pre"/"post" pixels changed in and out
                                    of the coverage

vhaz: an upload record ("vup") carries the draw it synced for in "n" (the
draw record is written after its sync) and the first and last changed byte
("clo", "chi"). A draw is hit when a vup with the same "rot" and a larger "n"
has a changed span overlapping one of its "vr" ranges. The span is first to
last changed byte, so an overlap can be a false hit where bytes in between
did not change; the "v" words (guest RAM at the draw) settle a doubtful one.

The registers are written raw by fdump_log_draw_state (vk/renderer.c); the
decode here follows nv2a_regs.h and nv2a_diag_log_draw_call.
"""
import json
import sys
from collections import Counter, defaultdict

BF = ["0", "1", "SC", "1-SC", "SA", "1-SA", "DA", "1-DA", "DC", "1-DC",
      "SAS", "?11", "CC", "1-CC", "CA", "1-CA"]
EQ = ["SUB", "RSUB", "ADD", "MIN", "MAX", "RSUBS", "ADDS", "?7"]
FN = ["NEVER", "LT", "EQ", "LE", "GT", "NE", "GE", "ALWAYS"]
SOP = ["?0", "KEEP", "ZERO", "REPL", "INCS", "DECS", "INV", "INC", "DEC"]


def h(v):
    return int(v, 16) if isinstance(v, str) else v


def hf(v):
    """A dump's hex word ("3f800000" or "0x3f800000") as the float it holds."""
    import struct
    if not isinstance(v, str):
        return float(v)
    return struct.unpack(">f", int(v, 16).to_bytes(4, "big"))[0]


VUPS = []


def load(path):
    session, draws, frames, shaders = None, [], [], {}
    with open(path) as f:
        for line in f:
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            t = r.get("t")
            if t == "session":
                session = r
            elif t == "draw":
                draws.append(r)
            elif t == "frame":
                frames.append(r)
            elif t == "shader":
                shaders[r["shader"]] = r
            elif t == "vup":
                VUPS.append(r)
    return session, draws, frames, shaders


def state(d):
    rs = d.get("rs") or {}
    c0, c1, c2 = h(rs.get("c0", 0)), h(rs.get("c1", 0)), h(rs.get("c2", 0))
    bl, sr = h(rs.get("blend", 0)), h(rs.get("sr", 0))
    out = []
    if bl & 8:
        out.append("blend %s*S %s %s*D" % (BF[(bl >> 4) & 15], EQ[bl & 7],
                                          BF[(bl >> 8) & 15]))
    else:
        out.append("noblend")
    if c0 & (1 << 14):
        out.append("z%s%s" % (FN[(c0 >> 16) & 7], "+w" if c0 & (1 << 24) else ""))
    else:
        out.append("noz" + ("+w" if c0 & (1 << 24) else ""))
    if c1 & 1:
        out.append("st %s ref%02x rm%02x wm%02x f/zf/zp %s/%s/%s" % (
            FN[(c1 >> 4) & 7], (c1 >> 8) & 255, (c1 >> 16) & 255,
            (c1 >> 24) & 255, SOP[min(c2 & 15, 8)],
            SOP[min((c2 >> 4) & 15, 8)], SOP[min((c2 >> 8) & 15, 8)]))
    m = "".join(ch for ch, b in (("R", 27), ("G", 28), ("B", 29), ("A", 26))
                if c0 & (1 << b))
    out.append("mask " + (m or "-"))
    if c0 & (1 << 12):
        out.append("atest %s %02x" % (FN[(c0 >> 8) & 7], c0 & 255))
    if sr & (1 << 28):
        out.append("cull %s" % ["?", "F", "B", "FB"][(sr >> 21) & 3])
    return " ".join(out)


def texs(d):
    out = []
    for t in d.get("tex", []):
        if not t.get("en"):
            continue
        fmt = h(t["fmt"])
        s = "t%d@%s c%02x %dx%d" % (t["s"], t["off"], (fmt >> 8) & 0x7f,
                                   1 << ((fmt >> 20) & 15),
                                   1 << ((fmt >> 24) & 15))
        srf = t.get("srf")
        if srf:
            s += " SRF[%dx%d f%d %s%s%s%s%s]" % (
                srf["w"], srf["h"], srf["fmt"],
                "col" if srf["color"] else "zeta",
                " swz" if srf["swizzle"] else "",
                " dirty" if srf["dirty"] else "",
                " upl" if srf["upl"] else "",
                " dlp" if srf["dlp"] else "")
        if t.get("s2t"):
            s += " s2t"
        out.append(s)
    return " | ".join(out)


def tgt(d):
    c = d.get("color")
    return (c["addr"], c["w"], c["h"], c["fmt"], c["swizzle"]) if c else None


def load_rgba(base, e):
    """A colour readback as an RGBA PIL image, or None."""
    import os
    from PIL import Image
    if not e or not e.get("file"):
        return None
    path = os.path.join(base, e["file"])
    if not os.path.exists(path):
        return None
    mode = "BGRA" if e["vkfmt"] == 44 else "RGBA"
    return Image.frombytes("RGBA", (e["w"], e["h"]), open(path, "rb").read(),
                           "raw", mode)


def load_depth(base, e):
    """A depth readback as (values 0..1 or float, w, h), or None. 129 is
    D24_UNORM_S8_UINT (depth in the low 24 bits of 4 bytes), 130
    D32_SFLOAT_S8_UINT (a float), 124 D16_UNORM."""
    import os
    import struct
    if not e or not e.get("file"):
        return None
    path = os.path.join(base, e["file"])
    if not os.path.exists(path):
        return None
    raw = open(path, "rb").read()
    n = e["w"] * e["h"]
    if e["vkfmt"] == 129:
        v = [(u & 0xFFFFFF) / 0xFFFFFF for u in struct.unpack("<%dI" % n, raw)]
    elif e["vkfmt"] == 130:
        v = list(struct.unpack("<%df" % n, raw))
    elif e["vkfmt"] == 124:
        v = [u / 0xFFFF for u in struct.unpack("<%dH" % n, raw)]
    else:
        return None
    return v, e["w"], e["h"]


def cover(argv, draws):
    import os
    import numpy as np
    fsel, nsel = int(argv[3]), int(argv[4])
    out = argv[5] if len(argv) > 5 else None
    base = os.path.dirname(argv[1])
    d = next((x for x in draws if x["f"] == fsel and x["n"] == nsel), None)
    if d is None:
        print("no draw f%d n%d" % (fsel, nsel))
        return
    if d.get("prim") != 5 or not d.get("cm") or not d.get("v"):
        print("f%d n%d: needs TRIANGLES (prim 5) with cm and v words" % (fsel, nsel))
        return
    cm = [[hf(x) for x in r.split()] for r in d["cm"]]
    M = np.array(cm[0:4], dtype=np.float64)      # rows are the matrix's columns
    off = cm[5][:2] if len(cm) > 5 else [0.0, 0.0]
    zmax = hf(d["rs"]["zmax"]) if "zmax" in d.get("rs", {}) else 16777215.0
    zmin = hf(d["rs"]["zmin"]) if "zmin" in d.get("rs", {}) else 0.0
    W, H = d["color"]["w"], d["color"]["h"]
    verts = []
    for e in d["v"]:
        pos = [hf(x) for x in e[1].split()]
        while len(pos) < 3:
            pos.append(0.0)
        uv = [hf(x) for x in e[3].split()] if len(e) > 3 and e[3] else [0.0, 0.0]
        verts.append((np.array(pos[:3] + [1.0]), uv[:2] + [0.0] * (2 - len(uv[:2]))))
    X, Y = np.meshgrid(np.arange(W) + 0.5 - off[0], np.arange(H) + 0.5 - off[1])
    cov = np.zeros((H, W), bool)
    zexp = np.full((H, W), np.nan)
    U = np.full((H, W), np.nan)
    V = np.full((H, W), np.nan)
    for t in range(len(verts) // 3):
        tri = verts[3 * t:3 * t + 3]
        c = np.array([M @ v[0] for v in tri])    # 3 x (x, y, z, w)
        A = np.array([c[:, 0], c[:, 1], c[:, 3]])
        if abs(np.linalg.det(A)) < 1e-12:
            print("tri %d: degenerate" % t)
            continue
        Ai = np.linalg.inv(A)
        lam = [Ai[i, 0] * X + Ai[i, 1] * Y + Ai[i, 2] for i in range(3)]
        inside = (lam[0] >= 0) & (lam[1] >= 0) & (lam[2] >= 0)
        z = lam[0] * c[0, 2] + lam[1] * c[1, 2] + lam[2] * c[2, 2]
        inside &= (z >= zmin) & (z <= zmax)
        ssum = lam[0] + lam[1] + lam[2]
        u = sum(lam[i] * tri[i][1][0] for i in range(3)) / ssum
        v = sum(lam[i] * tri[i][1][1] for i in range(3)) / ssum
        new = inside & ~cov
        cov |= inside
        zexp[new], U[new], V[new] = z[new] / 16777215.0, u[new], v[new]
        ws = "".join("-" if w < 0 else "+" for w in c[:, 3])
        print("tri %d: w %s (%s) covers %d px" % (
            t, ws, " ".join("%.2f" % w for w in c[:, 3]), int(inside.sum())))
    n = int(cov.sum())
    line = "f%d n%d %s: covers %d px" % (fsel, nsel, d["shader"][:8], n)
    if n:
        ys, xs = np.nonzero(cov)
        line += " box %d,%d-%d,%d z %.6f..%.6f u %.2f..%.2f v %.2f..%.2f" % (
            xs.min(), ys.min(), xs.max(), ys.max(), np.nanmin(zexp),
            np.nanmax(zexp), np.nanmin(U), np.nanmax(U), np.nanmin(V),
            np.nanmax(V))
    print(line)
    rbs = {}
    for e in d.get("rb", []):
        rbs.setdefault((e["k"], e["s"]), e)
    lit = None
    te = rbs.get(("tex", 0)) or rbs.get(("srf", 0))
    timg = load_rgba(base, te)
    if timg is not None and n:
        ta = np.asarray(timg.convert("RGB"), dtype=np.int32)
        th, tw = ta.shape[:2]
        tx = np.clip(np.floor(np.nan_to_num(U) * tw), 0, tw - 1).astype(int)
        ty = np.clip(np.floor(np.nan_to_num(V) * th), 0, th - 1).astype(int)
        lit = cov & (ta[ty, tx].max(axis=2) > 8)
        print("  %s%d at the UV: %d covered px sample a texel above 8" % (
            te["k"], te["s"], int(lit.sum())))
    z = load_depth(base, rbs.get(("zpre", -1)))
    pas = None
    if z is not None and n:
        zv, zw, zh = z
        if (zw, zh) == (W, H):
            zp = np.array(zv).reshape(zh, zw)
            pas = cov & (zexp <= zp + 2.0 / 16777215.0)
            dz = (zexp - zp)[cov]
            print("  zpre: %d of %d covered px pass LEQUAL; draw z - zpre "
                  "min %+.6f med %+.6f max %+.6f" % (
                      int(pas.sum()), n, dz.min(), np.median(dz), dz.max()))
            if lit is not None:
                print("  covered, lit and passing: %d" % int((pas & lit).sum()))
    pre, post = load_rgba(base, rbs.get(("pre", -1))), load_rgba(base, rbs.get(("post", -1)))
    chg = None
    if pre is not None and post is not None:
        a = np.asarray(pre.convert("RGB"), dtype=np.int32)
        b = np.asarray(post.convert("RGB"), dtype=np.int32)
        chg = np.abs(a - b).max(axis=2) > 2
        print("  pre/post: %d px changed, %d inside the coverage, %d outside" % (
            int(chg.sum()), int((chg & cov).sum()), int((chg & ~cov).sum())))
    if out:
        from PIL import Image
        os.makedirs(out, exist_ok=True)
        img = np.zeros((H, W, 3), np.uint8)
        img[cov] = (0, 0, 120)
        if lit is not None:
            img[lit] = (0, 90, 200)
        if pas is not None:
            img[pas & (lit if lit is not None else cov)] = (0, 200, 0)
        if chg is not None:
            img[chg] = (255, 0, 0)
            img[chg & cov] = (255, 255, 0)
        Image.fromarray(img).save(os.path.join(out, "f%03d_n%04d_cover.png" % (fsel, nsel)))


def main(argv):
    if len(argv) < 3:
        print(__doc__)
        return 2
    session, draws, frames, shaders = load(argv[1])
    cmd = argv[2]
    print("schema=%s draws=%d frames=%d shaders=%d" % (
        session and session.get("schema"), len(draws), len(frames),
        len(shaders)))
    if cmd == "targets":
        per = defaultdict(Counter)
        for d in draws:
            per[d["f"]][tgt(d)] += 1
        for f in sorted(per):
            print("f%d: %s" % (f, ", ".join(
                "%s %sx%s f%s%s: %d" % (k[0], k[1], k[2], k[3],
                                        " swz" if k[4] else "", n)
                if k else "none: %d" % n for k, n in per[f].items())))
    elif cmd == "draws":
        f = int(argv[3])
        a = int(argv[4]) if len(argv) > 4 else 0
        b = int(argv[5]) if len(argv) > 5 else 10 ** 9
        for d in draws:
            if d["f"] != f or not a <= d["n"] <= b:
                continue
            t = tgt(d)
            z = d.get("zeta")
            print("n%-5d %-6s %5d prim%d sh %s -> %s%s | %s | %s" % (
                d["n"], d["kind"], d["count"], d["prim"], d["shader"][:8],
                "%s %sx%s f%s" % t[:4] if t else "-",
                " z%s" % z["addr"] if z else " noz",
                state(d), texs(d)))
    elif cmd == "rtt":
        for d in draws:
            t = tgt(d)
            hits = []
            for x in d.get("tex", []):
                if not x.get("en"):
                    continue
                own = t and h(x["off"]) == h(t[0])
                if x.get("srf") or own:
                    hits.append(x)
            if hits:
                own = any(t and h(x["off"]) == h(t[0]) for x in hits)
                print("f%d n%-5d -> %s %sx%s%s | %s | %s" % (
                    d["f"], d["n"], t[0] if t else "-", t[1] if t else "",
                    t[2] if t else "", " FEEDBACK" if own else "",
                    state(d), texs(d)))
    elif cmd == "vhaz":
        only = argv[3] if len(argv) > 3 else None
        ups = defaultdict(list)
        for u in VUPS:
            ups[(u["f"], u["rot"])].append(u)
        per = defaultdict(list)
        for d in draws:
            per[d["f"]].append(d)
        for f in sorted(per):
            hits, shown = [], []
            nup = sum(len(v) for k, v in ups.items() if k[0] == f)
            hzf = sum(1 for u in VUPS if u["f"] == f and u.get("hzf"))
            rots = sorted({d.get("rot") for d in per[f]})
            for d in per[f]:
                if "rot" not in d:
                    continue
                vr = [(h(x[1]), h(x[2])) for x in d.get("vr", [])]
                by = []
                for u in ups.get((f, d["rot"]), []):
                    if u["n"] <= d["n"]:
                        continue
                    clo, chi = h(u["clo"]), h(u["chi"])
                    if any(clo < hi and chi > lo for lo, hi in vr):
                        by.append(u["n"])
                if by:
                    hits.append(d["n"])
                if only and d["shader"].startswith(only):
                    shown.append("n%d rot%d %s" % (
                        d["n"], d["rot"],
                        "HIT by n%s" % ",".join(map(str, by[:6])) if by
                        else "clean"))
            print("f%d rots %s vups %d hzf %d hit draws %d%s%s" % (
                f, ",".join(map(str, rots)), nup, hzf, len(hits),
                " (n%s)" % ",".join(map(str, hits[:12])) if hits else "",
                " | " + "; ".join(shown) if shown else ""))
    elif cmd == "means":
        import os
        from PIL import Image
        box = tuple(int(x) for x in argv[3:7]) if len(argv) > 6 else (
            180, 0, 480, 20)
        base = os.path.dirname(argv[1])
        for fr in frames:
            if not fr.get("image"):
                print("f%d no image (img_sync %s)" % (fr["f"],
                                                      fr.get("img_sync")))
                continue
            path = os.path.join(base, fr["image"])
            if not os.path.exists(path):
                print("f%d %s not pulled" % (fr["f"], fr["image"]))
                continue
            im = Image.open(path).convert("RGB")
            px = list(im.crop(box).get_flattened_data())
            m = [round(sum(p[i] for p in px) / len(px)) for i in range(3)]
            print("f%d %s %d,%d,%d img_sync %s" % (
                fr["f"], fr["image"], m[0], m[1], m[2], fr.get("img_sync")))
    elif cmd == "rb":
        import os
        from PIL import Image, ImageDraw
        only = int(argv[3]) if len(argv) > 3 else None
        out = argv[4] if len(argv) > 4 else None
        base = os.path.dirname(argv[1])
        if out:
            os.makedirs(out, exist_ok=True)
        sheets = defaultdict(list)
        for d in draws:
            if "rb" not in d or (only is not None and d["f"] != only):
                continue
            for e in d["rb"]:
                if e["k"] == "zpre":
                    continue
                tag = "f%d n%d %s %s%s %s %dx%d" % (
                    d["f"], d["n"], d["shader"][:8], e["k"],
                    "" if e["s"] < 0 else e["s"], e["addr"], e["w"], e["h"])
                if not e.get("file"):
                    print(tag, "no file (vkfmt %s layout %s)" % (
                        e["vkfmt"], e["layout"]))
                    continue
                path = os.path.join(base, e["file"])
                if not os.path.exists(path):
                    print(tag, "not pulled")
                    continue
                raw = open(path, "rb").read()
                mode = "BGRA" if e["vkfmt"] == 44 else "RGBA"
                im = Image.frombytes("RGBA", (e["w"], e["h"]), raw, "raw",
                                     mode)
                px = list(im.get_flattened_data())
                lit = sum(1 for p in px if max(p[:3]) > 32)
                m = [round(sum(p[i] for p in px) / len(px)) for i in range(4)]
                print("%s lit %d/%d mean %d,%d,%d a %d" % (
                    tag, lit, len(px), m[0], m[1], m[2], m[3]))
                if out:
                    x = 4 if e["w"] * e["h"] <= 4096 else 1
                    big = im.convert("RGB").resize((e["w"] * x, e["h"] * x),
                                                   Image.NEAREST)
                    big.save(os.path.join(out, "f%03d_n%04d_%s%d.png" % (
                        d["f"], d["n"], e["k"], max(e["s"], 0))))
                    sheets[d["f"]].append((tag, im.convert("RGB")))
        for f, items in sheets.items():
            cols = 8
            rows = (len(items) + cols - 1) // cols
            sheet = Image.new("RGB", (cols * 136, rows * 150), (40, 0, 40))
            dr = ImageDraw.Draw(sheet)
            for i, (tag, im) in enumerate(items):
                x, y = (i % cols) * 136 + 4, (i // cols) * 150 + 4
                sheet.paste(im.resize((128, 128), Image.NEAREST), (x, y))
                dr.text((x, y + 129), " ".join(tag.split()[1:5]),
                        fill=(255, 255, 0))
            sheet.save(os.path.join(out, "f%03d_sheet.png" % f))
    elif cmd == "cons":
        import os
        out = argv[3] if len(argv) > 3 else None
        box = [int(v) for v in argv[4:8]] if len(argv) > 7 else None
        base = os.path.dirname(argv[1])
        if out:
            os.makedirs(out, exist_ok=True)
        for d in draws:
            rbs = {e["k"]: e for e in d.get("rb", [])}
            if "post" not in rbs:
                continue
            tag = "f%d n%d %s" % (d["f"], d["n"], d["shader"][:8])
            pre, post = load_rgba(base, rbs.get("pre")), load_rgba(base, rbs["post"])
            if pre is None or post is None:
                print(tag, "pre/post missing")
                continue
            w, hh = post.size
            a, b = pre.load(), post.load()
            n = 0
            x0, y0, x1, y1 = w, hh, -1, -1
            dsum = [0, 0, 0]
            for y in range(hh):
                for x in range(w):
                    p, q = a[x, y], b[x, y]
                    if max(abs(p[i] - q[i]) for i in range(3)) > 2:
                        n += 1
                        x0, y0 = min(x0, x), min(y0, y)
                        x1, y1 = max(x1, x), max(y1, y)
                        for i in range(3):
                            dsum[i] += q[i] - p[i]
            line = "%s %dx%d changed %d" % (tag, w, hh, n)
            if n:
                line += " box %d,%d-%d,%d mean %+.0f,%+.0f,%+.0f" % (
                    x0, y0, x1, y1, *(v / n for v in dsum))
            z = load_depth(base, rbs.get("zpre"))
            if z is not None:
                zv, zw, zh = z
                fin = sorted(v for v in zv)
                line += " | zpre %s min %.6f med %.6f max %.6f" % (
                    rbs["zpre"]["vkfmt"], fin[0], fin[len(fin) // 2], fin[-1])
                if box and zw == w:
                    bx = sorted(zv[y * zw + x]
                                for y in range(box[1], box[3] + 1)
                                for x in range(box[0], box[2] + 1))
                    line += " box min %.6f med %.6f max %.6f" % (
                        bx[0], bx[len(bx) // 2], bx[-1])
            elif "zpre" in rbs:
                print(tag, "zpre not readable (vkfmt %s)" % rbs["zpre"]["vkfmt"])
            print(line)
            if out:
                from PIL import Image
                stem = os.path.join(out, "f%03d_n%04d_" % (d["f"], d["n"]))
                pre.convert("RGB").save(stem + "pre.png")
                post.convert("RGB").save(stem + "post.png")
                diff = Image.new("RGB", (w, hh))
                dp = diff.load()
                for y in range(hh):
                    for x in range(w):
                        dp[x, y] = tuple(min(255, 8 * abs(a[x, y][i] - b[x, y][i]))
                                         for i in range(3))
                diff.save(stem + "diff.png")
                if z is not None:
                    zv, zw, zh = z
                    lo, hi = min(zv), max(zv)
                    zi = Image.new("L", (zw, zh))
                    zi.putdata([int(255 * (v - lo) / (hi - lo)) if hi > lo else 0
                                for v in zv])
                    zi.save(stem + "zpre.png")
    elif cmd == "cover":
        cover(argv, draws)
    elif cmd == "shader":
        s = shaders.get(argv[3]) or next(
            (v for k, v in shaders.items() if k.startswith(argv[3])), None)
        if not s:
            print("no such shader")
            return 1
        for k, v in s.items():
            if k in ("vsh", "geom", "psh"):
                print("---- %s ----\n%s" % (k, v))
            else:
                print("%s: %s" % (k, v))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
