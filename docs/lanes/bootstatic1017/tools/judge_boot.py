#!/usr/bin/env python3
"""Judge one [boot1045] present-probe run (#1045): which presents flash, from which source, in which mode.

Usage: judge_boot.py <dir> [--json out.json]

<dir> holds what HAKUX_BOOTPROBE writes: boot1045_log.txt (one line per present), boot1045_f<n>.ppm (each new
window image, downscaled) and boot1045_r<n>.bin (guest RAM at the scan-out address while the VGA fallback is drawn).

Committed before any run's data. The rules, fixed here:

Coverage (the run counts only if all hold):
  C1  the log starts at n=0 and n has no gaps (every present from the first is in it);
  C2  it reaches a GPU picture: a present with src=n and lit >= LIT_PICTURE;
  C3  it runs at least TAIL_PRESENTS presents past that first GPU picture, so the launch window is closed.
  C2 on a run with no src=n present at all (the desktop on lavapipe presents by download, so every present is src=v;
  added after run d1, before d2): the first picture-class present with lit >= LIT_PICTURE whose start address differs
  from that of the first such present (the kernel's logo), i.e. the title has moved the scan-out. A title that keeps
  the kernel's address fails C2 under this rule, and the run says so.

Classes, per present, over the centre half of the window (the probe's numbers):
  black    lit < LIT_BLACK
  green    grn >= GRN_BAR
  noise    nb >= nb_bar and lit >= LIT_NOISE
  picture  anything else
nb_bar comes from the run itself, outside the measured spread of clean frames: the clean set is the lit (lit >=
LIT_BLACK) presents in the last quarter of the log's time, after the launch; nb_bar = max(NB_FLOOR, 2 x their
largest nb). If the clean set is empty, nb_bar = NB_FLOOR and the verdict says so. GRN_BAR is checked the same way:
the largest grn in the clean set is printed, and a green verdict needs GRN_BAR above 2 x that.

Episodes: maximal runs of consecutive noise or green presents. For each: presents, ms, sources, and the scan-out
registers at its first present and on the present before it (a mode change near it is H6's hit).

Hypotheses (NOTES.md table):
  H1 hit: every flash present has src=v (the VGA fallback); miss: any flash present has src=n.
  H2 hit: a flash present has src=n (a GPU display image shown with garbage in it).
  H3 hit: a flash present has PVIDEO in use (pv bit 0).
  H5    : during the flash the guest has blanked (sr01 bit 5 set = screen off, or ari bit 5 clear = palette
          address source off, or cr17 bit 7 clear = sync off) -> silicon would show nothing; else silicon shows RAM too.
          Each episode also says whether the present before it was blanked (blanked_prev): the desktop draws the VGA
          image one refresh late, so its flash can be the image of a blanked present.
  H6 hit: start, lo, vga size or bpp changes within 2 presents of an episode's first present.
RAM match (H1's "the pixels are guest RAM"): for each boot1045_r<n>.bin, the RAM is decoded at present n's logged bpp
(32 = XRGB8888, 16 = RGB565, 15 = XRGB1555, little-endian), line offset and VGA size, scaled to the picture's box in
the window frame (the box of rows and columns with any lit pixel), and its luma is correlated (Pearson) with the
frame's luma. The null is the same decode shifted by 37 columns and 23 rows. A match needs r >= R_MATCH and r >= 3 x
the null's |r|. Indexed modes (bpp 0 or 8) are reported, not decoded. Two pairings per dump (the second added after
d1): "same", the window at present n (Android runs the VGA update before the draw), and "next", the window at
present n+1 (the desktop runs it after the present, so it draws the image one refresh late). The window at present m
is the latest frame dump at or before m: the probe skips a frame only when it hashes the same as the one before.

Unblanked view (added after d1): for src=v presents the probe logs tnb/tlit/tgrn, the same numbers over the console
surface the texture was made from, before any screen-off blank. Classed with the same bars (tcls), they show what a
present path that ignores SR01 screen-off draws, which is the Android path (android_blit_frame has no screen-off
check). Reported as episodes of noise or green, with how many of their presents had the screen off.
"""
import json
import math
import os
import re
import sys

LIT_BLACK = 0.01
LIT_NOISE = 0.10
LIT_PICTURE = 0.05
GRN_BAR = 0.25
NB_FLOOR = 20.0
TAIL_PRESENTS = 120
R_MATCH = 0.30

KV = re.compile(r"(\w+)=(\S+)")


def parse_log(path):
    rows = []
    with open(path, errors="replace") as f:
        for line in f:
            kv = dict(KV.findall(line))
            if "n" not in kv or "src" not in kv:
                continue
            r = {"raw": kv}
            for k in ("n", "lo", "bpp", "dump", "ramdump", "flip", "tex"):
                r[k] = int(kv.get(k, "0"))
            for k in ("t_ms", "nb", "lit", "grn", "ram_nb"):
                r[k] = float(kv.get(k, "0"))
            for k in ("tnb", "tlit", "tgrn"):
                r[k] = float(kv.get(k, "-1"))
            for k in ("cr28", "gr06", "ari", "sr01", "cr17"):
                r[k] = int(kv.get(k, "0"), 16)
            r["start"] = int(kv.get("start", "0x0"), 16)
            r["gc"] = int(kv.get("gc", "0"), 16)
            r["pv"] = int(kv.get("pv", "0"), 16)
            r["src"] = kv["src"]
            r["vga"] = kv.get("vga", "0x0")
            r["win"] = kv.get("win", "0x0")
            r["mean"] = kv.get("mean", "0,0,0")
            nz = kv.get("ram_nz", "0/0").split("/")
            r["ram_nz"] = int(nz[0]) / max(1, int(nz[1])) if len(nz) == 2 else 0.0
            r["ram_h"] = kv.get("ram_h", "")
            rows.append(r)
    return rows


def read_ppm(path):
    with open(path, "rb") as f:
        data = f.read()
    # P6\n<w> <h>\n255\n
    parts = data.split(b"\n", 3)
    w, h = (int(x) for x in parts[1].split())
    px = parts[3]
    return w, h, px


def luma(r, g, b):
    return 0.299 * r + 0.587 * g + 0.114 * b


def decode_ram(buf, bpp, lo, vw, vh):
    """Luma image (list of rows) of guest RAM at the scan-out, or None for indexed modes."""
    if bpp == 32:
        bpx = 4
    elif bpp in (15, 16):
        bpx = 2
    else:
        return None
    if lo <= 0:
        lo = vw * bpx
    img = []
    for y in range(vh):
        row = []
        base = y * lo
        for x in range(vw):
            o = base + x * bpx
            if o + bpx > len(buf):
                row.append(0.0)
                continue
            if bpx == 4:
                b, g, r = buf[o], buf[o + 1], buf[o + 2]
            else:
                v = buf[o] | (buf[o + 1] << 8)
                if bpp == 16:
                    r, g, b = (v >> 11) & 31, (v >> 5) & 63, v & 31
                    r, g, b = r * 255 // 31, g * 255 // 63, b * 255 // 31
                else:
                    r, g, b = (v >> 10) & 31, (v >> 5) & 31, v & 31
                    r, g, b = r * 255 // 31, g * 255 // 31, b * 255 // 31
            row.append(luma(r, g, b))
        img.append(row)
    return img


def pearson(a, b):
    n = len(a)
    if n < 16:
        return 0.0
    ma, mb = sum(a) / n, sum(b) / n
    sa = sum((x - ma) ** 2 for x in a)
    sb = sum((y - mb) ** 2 for y in b)
    if sa <= 0 or sb <= 0:
        return 0.0
    return sum((x - ma) * (y - mb) for x, y in zip(a, b)) / math.sqrt(sa * sb)


def frame_at(m, frames):
    """The window at present m: the latest frame dump at or before m (None if there is none)."""
    best = None
    for k in frames:
        if k <= m:
            best = k
        else:
            break
    return best


def ram_matches(d, rows):
    by_n = {r["n"]: r for r in rows}
    frames = sorted(int(f[10:15]) for f in os.listdir(d) if f.startswith("boot1045_f") and f.endswith(".ppm"))
    dumps = sorted(int(f[10:15]) for f in os.listdir(d) if f.startswith("boot1045_r") and f.endswith(".bin"))
    out = []
    for n in dumps:
        row = by_n.get(n)
        m = {"n": n}
        if row is None:
            m["verdict"] = "no log line for this dump"
            out.append(m)
            continue
        m.update({"start": "0x%08x" % row["start"], "bpp": row["bpp"], "lo": row["lo"], "vga": row["vga"],
                  "sr01": "%02x" % row["sr01"]})
        for name, at in (("same", n), ("next", n + 1)):
            fn = frame_at(at, frames)
            if fn is None:
                m[name] = {"verdict": "no frame dump at or before %d" % at}
                continue
            m[name] = ram_match(d, row, n, fn)
        out.append(m)
    return out


def ram_match(d, row, n, fn):
    rp = os.path.join(d, "boot1045_r%05u.bin" % n)
    fp = os.path.join(d, "boot1045_f%05u.ppm" % fn)
    out = {"frame": fn}
    vw, vh = (int(x) for x in row["vga"].split("x"))
    with open(rp, "rb") as f:
        buf = f.read()
    out["ram_bytes"] = len(buf)
    out["ram_nonzero"] = round(sum(1 for b in buf if b) / max(1, len(buf)), 4)
    img = decode_ram(buf, row["bpp"], row["lo"], vw, vh) if vw > 0 and vh > 0 else None
    if img is None:
        out["verdict"] = "indexed or unknown mode (bpp %d): not decoded" % row["bpp"]
        return out
    w, h, px = read_ppm(fp)
    lum = [[luma(px[(y * w + x) * 3], px[(y * w + x) * 3 + 1], px[(y * w + x) * 3 + 2]) for x in range(w)]
           for y in range(h)]
    rows_lit = [y for y in range(h) if any(v > 24 for v in lum[y])]
    cols_lit = [x for x in range(w) if any(lum[y][x] > 24 for y in range(h))]
    if not rows_lit or not cols_lit:
        out["verdict"] = "frame is black"
        return out
    y0, y1, x0, x1 = rows_lit[0], rows_lit[-1] + 1, cols_lit[0], cols_lit[-1] + 1
    out["box"] = [x0, y0, x1, y1]

    def sample(dx, dy):
        a, b = [], []
        for y in range(y0, y1):
            sy = (y - y0) * vh // max(1, y1 - y0)
            sy = (sy + dy) % vh
            for x in range(x0, x1):
                sx = (x - x0) * vw // max(1, x1 - x0)
                sx = (sx + dx) % vw
                a.append(img[sy][sx])
                b.append(lum[y][x])
        return pearson(a, b)

    r = sample(0, 0)
    r_null = sample(37, 23)
    out["r"] = round(r, 3)
    out["r_null"] = round(r_null, 3)
    out["verdict"] = "MATCH" if (r >= R_MATCH and r >= 3 * abs(r_null)) else "no match"
    return out


def classify(r, nb_bar):
    if r["lit"] < LIT_BLACK:
        return "black"
    if r["grn"] >= GRN_BAR:
        return "green"
    if r["nb"] >= nb_bar and r["lit"] >= LIT_NOISE:
        return "noise"
    return "picture"


def mode_key(r):
    return (r["start"], r["lo"], r["vga"], r["bpp"], r["cr28"])


def judge(d):
    rows = parse_log(os.path.join(d, "boot1045_log.txt"))
    res = {"dir": d, "presents": len(rows)}
    if not rows:
        res["verdict"] = "VOID: no presents in the log"
        return res
    ns = [r["n"] for r in rows]
    cov = {}
    cov["C1_starts_at_0"] = ns[0] == 0
    cov["C1_gaps"] = sum(1 for a, b in zip(ns, ns[1:]) if b != a + 1)
    first_pic = next((i for i, r in enumerate(rows) if r["src"] == "n" and r["lit"] >= LIT_PICTURE), None)
    cov["C2_rule"] = "src=n"
    if not any(r["src"] == "n" for r in rows):
        # Presenting by download: no src=n at all. The title's picture is the first lit picture at a start address
        # other than the first lit picture's (the kernel's logo). Classes need nb_bar, which is set below from the
        # tail; here a lit present with nb under NB_FLOOR is taken as a picture, the floor being the bar's minimum.
        cov["C2_rule"] = "download: start moved"
        pics = [i for i, r in enumerate(rows) if r["lit"] >= LIT_PICTURE and r["nb"] < NB_FLOOR]
        if pics:
            s0 = rows[pics[0]]["start"]
            first_pic = next((i for i in pics if rows[i]["start"] != s0), None)
    cov["C2_first_gpu_picture_n"] = rows[first_pic]["n"] if first_pic is not None else None
    cov["C3_tail_presents"] = (len(rows) - 1 - first_pic) if first_pic is not None else 0
    ok = (cov["C1_starts_at_0"] and cov["C1_gaps"] == 0 and first_pic is not None
          and cov["C3_tail_presents"] >= TAIL_PRESENTS)
    res["coverage"] = cov
    res["covered"] = ok

    t_end = rows[-1]["t_ms"]
    clean = [r for r in rows if r["t_ms"] >= 0.75 * t_end and r["lit"] >= LIT_BLACK]
    clean_nb = sorted(r["nb"] for r in clean)
    clean_grn = sorted(r["grn"] for r in clean)
    nb_bar = max(NB_FLOOR, 2 * clean_nb[-1]) if clean_nb else NB_FLOOR
    res["clean"] = {
        "count": len(clean),
        "nb_min_med_max": [clean_nb[0], clean_nb[len(clean_nb) // 2], clean_nb[-1]] if clean_nb else None,
        "grn_max": clean_grn[-1] if clean_grn else None,
        "nb_bar": nb_bar,
        "grn_bar_outside_spread": (GRN_BAR >= 2 * clean_grn[-1]) if clean_grn else None,
    }

    srcs = {}
    for r in rows:
        r["cls"] = classify(r, nb_bar)
        srcs.setdefault(r["src"], {}).setdefault(r["cls"], 0)
        srcs[r["src"]][r["cls"]] += 1
    res["by_source_and_class"] = srcs

    # Timeline: runs of the same (src, class).
    tl = []
    for r in rows:
        k = (r["src"], r["cls"])
        if tl and tl[-1]["key"] == k:
            tl[-1]["last_n"] = r["n"]
            tl[-1]["last_ms"] = r["t_ms"]
            tl[-1]["count"] += 1
        else:
            tl.append({"key": k, "first_n": r["n"], "last_n": r["n"], "first_ms": r["t_ms"], "last_ms": r["t_ms"],
                       "count": 1, "mode": "start=0x%08x lo=%d vga=%s bpp=%d cr28=%02x gr06=%02x ari=%02x "
                       "sr01=%02x cr17=%02x gc=%08x pv=%08x" % (r["start"], r["lo"], r["vga"], r["bpp"], r["cr28"],
                                                               r["gr06"], r["ari"], r["sr01"], r["cr17"], r["gc"],
                                                               r["pv"])})
    for t in tl:
        t["key"] = "%s/%s" % t["key"]
    res["timeline"] = tl

    eps = []
    i = 0
    while i < len(rows):
        if rows[i]["cls"] in ("noise", "green"):
            j = i
            while j + 1 < len(rows) and rows[j + 1]["cls"] in ("noise", "green"):
                j += 1
            seg = rows[i:j + 1]
            prev = rows[i - 1] if i > 0 else None
            near = rows[max(0, i - 2):min(len(rows), i + 3)]
            ep = {
                "first_n": seg[0]["n"], "last_n": seg[-1]["n"], "presents": len(seg),
                "ms": round(seg[-1]["t_ms"] - seg[0]["t_ms"], 1),
                "t_ms_first": seg[0]["t_ms"],
                "classes": sorted({r["cls"] for r in seg}),
                "sources": sorted({r["src"] for r in seg}),
                "nb_min_max": [min(r["nb"] for r in seg), max(r["nb"] for r in seg)],
                "grn_max": max(r["grn"] for r in seg),
                "mode_first": tl_mode(seg[0]),
                "mode_prev": tl_mode(prev) if prev else None,
                "mode_change_within_2": len({mode_key(r) for r in near}) > 1,
                "pvideo_in_use": any(r["pv"] & 1 for r in seg),
                "blanked": any(blanked(r) for r in seg),
                "blanked_prev": blanked(prev) if prev else None,
                "ram_nonzero_mean": round(sum(r["ram_nz"] for r in seg) / len(seg), 3),
                "ram_nb_mean": round(sum(r["ram_nb"] for r in seg) / len(seg), 1),
                "frames": [r["n"] for r in seg if r["dump"]][:20],
            }
            eps.append(ep)
            i = j + 1
        else:
            i += 1
    res["episodes"] = eps

    flash = [r for r in rows if r["cls"] in ("noise", "green")]
    h = {}
    if not flash:
        h["H1"] = h["H2"] = "no flash presents in this run"
    else:
        h["H1"] = "HIT" if all(r["src"] == "v" for r in flash) else "MISS (%d of %d flash presents are not src=v)" % (
            sum(1 for r in flash if r["src"] != "v"), len(flash))
        h["H2"] = "HIT (%d flash presents src=n)" % sum(1 for r in flash if r["src"] == "n") if any(
            r["src"] == "n" for r in flash) else "MISS"
        h["H3"] = "HIT" if any(r["pv"] & 1 for r in flash) else "MISS"
        h["H5_blanked_during_flash"] = any(e["blanked"] for e in eps)
        h["H5_blanked_before_flash"] = any(e["blanked_prev"] for e in eps)
        h["H6"] = "HIT" if any(e["mode_change_within_2"] for e in eps) else "MISS"
    fb = [r for r in rows if r["src"] == "v"]
    h["fallback_presents"] = len(fb)
    h["fallback_classes"] = srcs.get("v", {})
    res["hypotheses"] = h

    # The unblanked view: what the VGA texture held, before any screen-off blank.
    tv = [r for r in rows if r["src"] == "v" and r["tlit"] >= 0]
    for r in tv:
        r["tcls"] = classify({"lit": r["tlit"], "grn": r["tgrn"], "nb": r["tnb"]}, nb_bar)
    teps = []
    i = 0
    while i < len(tv):
        if tv[i]["tcls"] in ("noise", "green"):
            j = i
            while j + 1 < len(tv) and tv[j + 1]["tcls"] in ("noise", "green") and tv[j + 1]["n"] == tv[j]["n"] + 1:
                j += 1
            seg = tv[i:j + 1]
            teps.append({
                "first_n": seg[0]["n"], "last_n": seg[-1]["n"], "presents": len(seg),
                "ms": round(seg[-1]["t_ms"] - seg[0]["t_ms"], 1), "t_ms_first": seg[0]["t_ms"],
                "classes": sorted({r["tcls"] for r in seg}),
                "tnb_min_max": [min(r["tnb"] for r in seg), max(r["tnb"] for r in seg)],
                "tgrn_max": max(r["tgrn"] for r in seg),
                "screen_off_presents": sum(1 for r in seg if r["sr01"] & 0x20),
                "window_classes": sorted({r["cls"] for r in seg}),
                "mode_first": tl_mode(seg[0]),
            })
            i = j + 1
        else:
            i += 1
    res["unblanked"] = {"presents_with_texture_numbers": len(tv), "episodes": teps}

    res["ram_match"] = ram_matches(d, rows)
    return res


def blanked(r):
    return bool((r["sr01"] & 0x20) or not (r["ari"] & 0x20) or not (r["cr17"] & 0x80))


def tl_mode(r):
    return "start=0x%08x lo=%d vga=%s bpp=%d cr28=%02x gr06=%02x ari=%02x sr01=%02x cr17=%02x" % (
        r["start"], r["lo"], r["vga"], r["bpp"], r["cr28"], r["gr06"], r["ari"], r["sr01"], r["cr17"])


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    d = sys.argv[1]
    res = judge(d)
    print("dir: %s  presents: %d  covered: %s" % (d, res["presents"], res.get("covered")))
    print("coverage:", json.dumps(res.get("coverage")))
    print("clean:", json.dumps(res.get("clean")))
    print("by source/class:", json.dumps(res.get("by_source_and_class")))
    print("timeline (src/class runs):")
    for t in res.get("timeline", []):
        print("  n %5d-%5d  %8.1f-%8.1f ms  %4d x %-10s %s" % (t["first_n"], t["last_n"], t["first_ms"],
                                                              t["last_ms"], t["count"], t["key"], t["mode"]))
    print("episodes:")
    for e in res.get("episodes", []):
        print("  " + json.dumps(e))
    print("hypotheses:", json.dumps(res.get("hypotheses")))
    ub = res.get("unblanked", {})
    print("unblanked view (texture before any screen-off blank): %d presents with numbers" %
          ub.get("presents_with_texture_numbers", 0))
    for e in ub.get("episodes", []):
        print("  " + json.dumps(e))
    print("ram match:")
    for m in res.get("ram_match", []):
        print("  " + json.dumps(m))
    if "--json" in sys.argv:
        with open(sys.argv[sys.argv.index("--json") + 1], "w") as f:
            json.dump(res, f, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
