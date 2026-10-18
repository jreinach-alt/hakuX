#!/usr/bin/env python3
"""Judge one Nova launch for #1045 from its [boot1045] probe: what the window showed while the guest had the screen off,
and every distinct picture from the first present to the title's first picture.

usage: judge_nova.py RESULT_DIR [--sheet out.png] [--json out.json]
       judge_nova.py --desktop PROBE_DIR [--sheet out.png] [--json out.json]

RESULT_DIR is a dispatcher result with pulled/boot1045_log.txt, pulled/boot1045_f*.ppm and logcat.txt. --desktop takes
a deskboot.py probe dir (boot1045_log.txt and the dumps in it, no logcat): V0 is not asked, and a window is also
black when the dump of its hash has no lit pixel below the top 5% (xemu's menubar, which fades over the first seconds
of a desktop run, so the desktop's window hash is never the all-black one; found on the first --desktop pass).

Written after the first Nova "before" run (1792282757, Halo CE, 7ea8b80e71) and before any "after" data, because both
of the probe's own window classifiers are blind on the Nova (NOTES.md has the frames):
  - the green look on Halo is horizontal streaks in the top and bottom thirds of the window, and the probe's numbers
    (nb, lit, grn) are taken over the centre half, where that frame is black (lit 0.023, grn 0.005);
  - the static is drawn into a 1280 x 960 window by a bilinear 2x upscale, which halves the neighbour difference: window
    nb 14.8, under NB_FLOOR 20, so judge_boot classes the static "picture" (its texture, tnb 47.8, is "noise").
So the primary measure is the fix's own variable, read from the registers and the window hash, with no look classifier:

  M1  presents with the screen off (sr01 bit 5) whose window is not exactly black, i.e. whose h (FNV-1a of the
      whole window, subsampled to <= 320 wide) is not the hash of an all-zero image of that size. Silicon shows black
      for every one of them. Counted to the title's first picture and over the whole log.
  M2  presents with the screen on, to the title's first picture, whose window is noise or green by judge_boot's
      classify (the desktop's one-present leak at the screen-on edge, if Android had it).
  M3  (added after 1792282757, before any after data) presents with the screen on, to the title's first picture,
      whose dumped frame's whole-frame look is static or streaks: M2 over the whole window, for a leak of the green
      look, which the centre half does not see. Only dumped presents can be looked at; the count of distinct window
      hashes to the first picture with no dump is printed beside it.

The verdict: VOID unless V0 (Turnip: a "Loading custom Vulkan driver", "GPU: PurpleVK" or "[gpl569] ext=1 ... mode=3"
line in logcat.txt and no stock-driver device line), C1 (presents from n=0 with no gaps) and coverage (a title's first
picture and TAIL_PRESENTS presents after it) all hold; else CLEAN when M1, M2 and M3 are all 0, FLASH otherwise.
nb_bar is judge_boot's: max(NB_FLOOR, 2 x the largest nb among lit presents in the last quarter of the log's time).

The title's first picture: as desk_ab.py, the first present at a non-zero start that is not the kernel's (the first
non-zero start with bpp > 0) whose window is lit (lit >= LIT_PICTURE) and not noise (nb < NB_FLOOR).

Descriptive, not part of the verdict: each run of M1 presents (an episode) lists its starts, sources, distinct
hashes, and the full-frame numbers of the dumped frames inside it: lit, grn (as the probe's), nbh and nbv (mean
|horizontal| and |vertical| neighbour difference per channel over the dump). The looks, named from the three
frames of 1792282757 only (a fit to one run, to be checked on the others): static nbh >= 20 and lit >= 0.10;
streaks nbv >= 5 and nbv >= 4 x nbh and lit >= 0.05; a picture otherwise. --sheet writes every dumped frame from the
first present to 30 presents past the title's first picture, labelled, for a person to look at.
"""
import json
import os
import re
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import judge_boot as jb  # noqa: E402

TURNIP = re.compile(r"GPU: PurpleVK|Loading custom Vulkan driver|\[gpl569\] ext=1.*mode=3")
STOCK = re.compile(r"Qualcomm Adreno Vulkan Driver|GPU: Adreno \(TM\)")


def black_hash(win):
    w, h = (int(x) for x in win.split("x"))
    step = max(1, (w + 319) // 320)
    n = (w // step) * (h // step) * 3
    v = 2166136261
    for _ in range(n):
        v = (v * 16777619) & 0xFFFFFFFF
    return "%08x" % v


MENUBAR_ROWS = 0.05


def lit_below_menubar(path):
    """Lit pixels in a desktop dump below its top 5%: xemu's menubar (rows 0-10 of a 240-row dump of a 640 x 480
    window, d3's n0) fades over the first seconds of every desktop run, so no desktop window is ever exactly black."""
    from PIL import Image
    a = np.asarray(Image.open(path).convert("RGB"))
    return int((a[int(a.shape[0] * MENUBAR_ROWS) + 1:].max(2) > 24).sum())


def full_frame(path):
    from PIL import Image
    a = np.asarray(Image.open(path).convert("RGB")).astype(np.int16)
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    lit = float((np.maximum(np.maximum(r, g), b) > 24).mean())
    grn = float(((g >= 48) & (g > r + 32) & (g > b + 32)).mean())
    nbh = float(np.abs(a[:, 1:] - a[:, :-1]).mean())
    nbv = float(np.abs(a[1:] - a[:-1]).mean())
    if nbh >= 20 and lit >= 0.10:
        look = "static"
    elif nbv >= 5 and nbv >= 4 * nbh and lit >= 0.05:
        look = "streaks"
    elif lit < jb.LIT_BLACK:
        look = "black"
    else:
        look = "picture"
    return {"lit": round(lit, 3), "grn": round(grn, 3), "nbh": round(nbh, 1), "nbv": round(nbv, 1), "look": look}


def nb_bar_of(rows):
    t_end = rows[-1]["t_ms"]
    clean = [r["nb"] for r in rows if r["t_ms"] >= 0.75 * t_end and r["lit"] >= jb.LIT_BLACK]
    return max(jb.NB_FLOOR, 2 * max(clean, default=0.0))


def judge(rd, desktop=False):
    res = {"dir": rd}
    pd = rd if desktop else os.path.join(rd, "pulled")
    plog = os.path.join(pd, "boot1045_log.txt")
    turnip = stock = 0
    lc = os.path.join(rd, "logcat.txt")
    if not desktop and os.path.exists(lc):
        with open(lc, errors="replace") as f:
            for line in f:
                turnip += bool(TURNIP.search(line))
                stock += bool(STOCK.search(line))
    res["V0_turnip_lines"], res["V0_stock_lines"] = ("desktop", "desktop") if desktop else (turnip, stock)
    if not os.path.exists(plog):
        res["verdict"] = "VOID: no pulled/boot1045_log.txt"
        return res
    rows = jb.parse_log(plog)
    if not rows:
        res["verdict"] = "VOID: no presents in the log"
        return res
    ns = [r["n"] for r in rows]
    c1 = ns[0] == 0 and all(b == a + 1 for a, b in zip(ns, ns[1:]))
    nb_bar = nb_bar_of(rows)
    kstart = next((r["start"] for r in rows if r["bpp"] > 0 and r["start"] != 0), None)
    fp = next((i for i, r in enumerate(rows) if r["start"] not in (0, kstart) and r["lit"] >= jb.LIT_PICTURE
               and r["nb"] < jb.NB_FLOOR), None)
    tail = len(rows) - 1 - fp if fp is not None else 0
    covered = c1 and fp is not None and tail >= jb.TAIL_PRESENTS
    bh = {}
    dump_of = {}
    for r in rows:
        p = os.path.join(pd, "boot1045_f%05d.ppm" % r["n"])
        if r["dump"] and os.path.exists(p):
            dump_of.setdefault(r["raw"].get("h", ""), p)
    below_cache = {}
    for r in rows:
        r["h"] = r["raw"].get("h", "")
        if r["win"] not in bh:
            bh[r["win"]] = black_hash(r["win"])
        r["black"] = r["h"] == bh[r["win"]]
        if desktop and not r["black"] and r["h"] in dump_of:
            if r["h"] not in below_cache:
                below_cache[r["h"]] = lit_below_menubar(dump_of[r["h"]])
            r["black"] = below_cache[r["h"]] == 0
        r["off"] = bool(r["sr01"] & 0x20)
    upto = rows[: fp + 1] if fp is not None else rows
    m1_all = [r for r in rows if r["off"] and not r["black"]]
    m1 = [r for r in upto if r["off"] and not r["black"]]
    m2 = [r for r in upto if not r["off"] and jb.classify(r, nb_bar) in ("noise", "green")]
    m3, undumped, seen = [], set(), set()
    for r in upto:
        p = os.path.join(pd, "boot1045_f%05d.ppm" % r["n"])
        dumped = r["dump"] and os.path.exists(p)
        if not dumped and r["h"] not in seen and not r["black"]:
            undumped.add(r["h"])
        if dumped:
            seen.add(r["h"])
            undumped.discard(r["h"])
            if not r["off"] and full_frame(p)["look"] in ("static", "streaks"):
                m3.append(r)
    res.update({
        "M3_to_first_picture": len(m3), "M3_n": [r["n"] for r in m3],
        "undumped_hashes_to_first_picture": len(undumped),
        "presents": len(rows), "C1": c1, "nb_bar": nb_bar,
        "kernel_start": "%08x" % kstart if kstart is not None else None,
        "title_first_picture": None if fp is None else {"n": rows[fp]["n"], "t_ms": rows[fp]["t_ms"],
                                                          "start": "%08x" % rows[fp]["start"]},
        "tail": tail, "covered": covered,
        "screen_off_presents_to_first_picture": sum(1 for r in upto if r["off"]),
        "M1_to_first_picture": len(m1), "M1_whole_log": len(m1_all),
        "M2_to_first_picture": len(m2), "M2_n": [r["n"] for r in m2],
    })
    # Episodes of M1 over the whole log.
    eps, cur = [], None
    for i, r in enumerate(rows):
        bad = r["off"] and not r["black"]
        if bad and cur is None:
            cur = [i, i]
        elif bad:
            cur[1] = i
        elif cur is not None:
            eps.append(cur)
            cur = None
    if cur is not None:
        eps.append(cur)
    out = []
    for a, b in eps:
        seg = rows[a: b + 1]
        dumps = []
        for r in seg:
            p = os.path.join(pd, "boot1045_f%05d.ppm" % r["n"])
            if r["dump"] and os.path.exists(p):
                d = full_frame(p)
                d["n"] = r["n"]
                dumps.append(d)
        out.append({"n": [seg[0]["n"], seg[-1]["n"]], "t_ms": [seg[0]["t_ms"], seg[-1]["t_ms"]],
                    "ms": round(seg[-1]["t_ms"] - seg[0]["t_ms"] + 16.7, 1), "presents": len(seg),
                    "before_title_first_picture": fp is not None and b <= fp,
                    "starts": sorted({"%08x" % r["start"] for r in seg}), "src": sorted({r["src"] for r in seg}),
                    "hashes": len({r["h"] for r in seg}), "looks": sorted({d["look"] for d in dumps}),
                    "dumps": dumps})
    res["episodes"] = out
    v0 = desktop or (turnip > 0 and stock == 0)
    if not (v0 and c1 and covered):
        res["verdict"] = "VOID: " + ", ".join(k for k, v in (("V0", v0), ("C1", c1), ("coverage", covered)) if not v)
    else:
        res["verdict"] = "CLEAN" if not m1 and not m2 and not m3 else "FLASH"
    res["verdict"] += "; M1 %d to the first picture (%d whole log), M2 %d, M3 %d" % (
        len(m1), len(m1_all), len(m2), len(m3))
    res["_rows"] = rows
    res["_fp"] = fp
    return res


def sheet(res, path, pd):
    from PIL import Image, ImageDraw
    rows, fp = res["_rows"], res["_fp"]
    last = (fp if fp is not None else len(rows) - 1) + 30
    pics = []
    for r in rows[: last + 1]:
        p = os.path.join(pd, "boot1045_f%05d.ppm" % r["n"])
        if r["dump"] and os.path.exists(p):
            pics.append((r, Image.open(p).convert("RGB").resize((160, 120))))
    if not pics:
        return 0
    cols = 8
    W, H = 160, 134
    im = Image.new("RGB", (cols * W, ((len(pics) + cols - 1) // cols) * H), (40, 40, 40))
    dr = ImageDraw.Draw(im)
    for k, (r, t) in enumerate(pics):
        x, y = (k % cols) * W, (k // cols) * H
        im.paste(t, (x, y))
        dr.text((x + 2, y + 121), "n%d %s sr%02x %s" % (r["n"], r["src"], r["sr01"], "OFF" if r["off"] else ""),
                fill=(255, 255, 0) if r["off"] else (255, 255, 255))
    im.save(path)
    return len(pics)


def main():
    a = sys.argv[1:]
    desktop = "--desktop" in a
    rd = a[a.index("--desktop") + 1] if desktop else a[0]
    res = judge(rd, desktop)
    print("verdict:", res["verdict"])
    for k in ("V0_turnip_lines", "V0_stock_lines", "presents", "C1", "covered", "kernel_start", "title_first_picture",
              "screen_off_presents_to_first_picture", "M1_to_first_picture", "M1_whole_log", "M2_to_first_picture",
              "M2_n", "M3_to_first_picture", "M3_n", "undumped_hashes_to_first_picture", "nb_bar"):
        if k in res:
            print("%s: %s" % (k, res[k]))
    for e in res.get("episodes", []):
        d = dict(e)
        d["dumps"] = ["n%d %s lit %.3f grn %.3f nbh %.1f nbv %.1f" % (x["n"], x["look"], x["lit"], x["grn"], x["nbh"],
                                                                     x["nbv"]) for x in e["dumps"]]
        print("episode:", json.dumps(d))
    if "--sheet" in a and "_rows" in res:
        n = sheet(res, a[a.index("--sheet") + 1], rd if desktop else os.path.join(rd, "pulled"))
        print("sheet: %d frames -> %s" % (n, a[a.index("--sheet") + 1]))
    if "--json" in a:
        with open(a[a.index("--json") + 1], "w") as f:
            json.dump({k: v for k, v in res.items() if not k.startswith("_")}, f, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
