#!/usr/bin/env python3
"""Judge the same-session Thor A/B of Blinx's attract demo for #372.

    abread.py <A logcat> <B logcat> [--window 135,265]
              [--spec-a result.json] [--spec-b result.json]
              [--prediction docs/testing/predictions/blinx372d-demo-ab.json]
    abread.py --selftest

A carries the [evict372] counter only; B also hands evictions to the shelved
partner on the GPU (vk/surface.c surface_handoff_record). Time zero, the stall
line and the demo fps are blinx372c/stallread.py's, imported, so the two lanes
read the demo the same way.

[evict372] is cumulative since boot and printed every 5 s. The window's count
is the last print in the window minus the last print before it.
"""
import json
import math
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "blinx372c"))
import stallread  # noqa: E402

HEAD = re.compile(r"\[evict372\] dirty/clean by mask \([^)]*\):(.*?) "
                  r"overflow=(\d+) handoffs=(\d+) fallbacks=(\d+)")
MASK = re.compile(r"m([0-9a-f]{2}):(\d+)/(\d+)")
PAIR = re.compile(r"\[evict372\] pair(\d+) n=(\d+) m([0-9a-f]{2}) "
                  r"([CZ]) f(\d+) (sz|ln) p(\d+) (\d+)x(\d+) b(\d+) -> "
                  r"([CZ]) f(\d+) (sz|ln) p(\d+) (\d+)x(\d+) b(\d+)")
TS_PADDED = re.compile(r"^(\d\d-\d\d \d\d:\d\d:\d\d\.\d{3})\s+\w/([\w-]+)\s*"
                       r"\(\s*\d+\):\s?(.*)$")
TOT = re.compile(r"Tot:([\d.]+) GPU:([\d.]+)")
SUB = re.compile(r"Sub:([\d.]+)")


def read_evict(path, lo, hi):
    """(before, last, pairs_at_last, tot_gpu_sub) for the window."""
    t0, before, last, pairs, cur_pairs, tgs = None, None, None, [], [], []
    for line in open(path, errors="replace"):
        # Time zero exactly as stallread takes it; its regex needs the tag
        # flush against "(", and SURF92_LOG's plain "hakuX" tag is padded.
        strict = stallread.TS.match(line)
        if t0 is None and strict and strict.group(2).startswith("hakuX"):
            t0 = stallread.ts(strict.group(1))
        m = TS_PADDED.match(line)
        if not m or t0 is None:
            continue
        t, tag, body = stallread.ts(m.group(1)), m.group(2), m.group(3)
        t -= t0
        h = HEAD.search(body)
        if h:
            rec = {"t": t,
                   "dirty": {int(k, 16): int(dv) for k, dv, _ in MASK.findall(h.group(1))},
                   "clean": {int(k, 16): int(cv) for k, _, cv in MASK.findall(h.group(1))},
                   "handoffs": int(h.group(3)), "fallbacks": int(h.group(4))}
            if t < lo:
                before = rec
            elif t < hi:
                last = rec
                cur_pairs = []
            continue
        p = PAIR.search(body)
        if p and lo <= t < hi:
            g = p.groups()
            cur_pairs.append({
                "n": int(g[1]), "mask": int(g[2], 16),
                "from": dict(zip("role vk swz pitch w h bpp".split(),
                                 (g[3], int(g[4]), g[5], int(g[6]), int(g[7]),
                                  int(g[8]), int(g[9])))),
                "to": dict(zip("role vk swz pitch w h bpp".split(),
                               (g[10], int(g[11]), g[12], int(g[13]), int(g[14]),
                                int(g[15]), int(g[16])))),
            })
            pairs = cur_pairs
            continue
        if tag == "hakuX-phase" and lo <= t < hi:
            a, s = TOT.search(body), SUB.search(body)
            if a and s:
                tgs.append((float(a.group(1)), float(a.group(2)), float(s.group(1))))
    return before, last, pairs, tgs


def delta(before, last, key):
    if last is None:
        return None
    b = before[key] if before else ({} if isinstance(last[key], dict) else 0)
    if isinstance(last[key], dict):
        return {k: v - b.get(k, 0) for k, v in last[key].items() if v - b.get(k, 0)}
    return last[key] - b


def same_geometry(pair):
    f, t = pair["from"], pair["to"]
    return all(f[k] == t[k] for k in ("swz", "pitch", "w", "h", "bpp"))


def arm(path, lo, hi, spec):
    stall, gfps, phase = stallread.read(path, lo, hi)
    out = stallread.summarize(stall, gfps, phase, spec)
    before, last, pairs, tgs = read_evict(path, lo, hi)
    frames = out["frames"]
    dirty = delta(before, last, "dirty")
    out["evict372_lines"] = last is not None
    out["dirty_by_mask"] = dirty
    out["dirty_per_frame"] = (sum(dirty.values()) / frames
                              if dirty is not None and frames else float("nan"))
    h = delta(before, last, "handoffs")
    out["handoffs_per_frame"] = h / frames if h is not None and frames else float("nan")
    out["fallbacks"] = delta(before, last, "fallbacks")
    top = max(pairs, key=lambda p: p["n"]) if pairs else None
    out["top_pair"] = top
    out["top_pair_same_geometry"] = same_geometry(top) if top else None
    out["tot_ms_median"] = stallread.med([x[0] for x in tgs])
    out["gpu_ms_median"] = stallread.med([x[1] for x in tgs])
    out["sub_ms_median"] = stallread.med([x[2] for x in tgs])
    return out


def judge(a, b, pred):
    e = pred["expect"]
    legs = {}
    for name, o in (("A", a), ("B", b)):
        legs["M0/%s_spec_has_stall" % name] = (o["spec_has_stall"], o["spec_has_stall"] is True)
        legs["M0/%s_stall_lines" % name] = (o["lines"], o["lines"] >= e["M0/stall_lines_min"])
        legs["M0/%s_window_intact" % name] = (o["window_intact"], o["window_intact"] is True)
        legs["M1/%s_evict372_live" % name] = (o["evict372_lines"], o["evict372_lines"] is True)
    r = e["P0/A_sd_per_frame_range"]
    legs["P0/A_sd_per_frame_range"] = (a["sd_per_frame"], r[0] <= a["sd_per_frame"] <= r[1])
    legs["P0/A_dirty_evict_per_frame_min"] = (
        a["dirty_per_frame"], a["dirty_per_frame"] >= e["P0/A_dirty_evict_per_frame_min"])
    legs["P1/A_top_pair_same_geometry_is"] = (
        a["top_pair"], a["top_pair_same_geometry"] is e["P1/A_top_pair_same_geometry_is"])
    legs["P2/B_sd_per_frame_max"] = (b["sd_per_frame"], b["sd_per_frame"] <= e["P2/B_sd_per_frame_max"])
    legs["P2/B_handoffs_per_frame_min"] = (
        b["handoffs_per_frame"], b["handoffs_per_frame"] >= e["P2/B_handoffs_per_frame_min"])
    legs["P3/B_fallbacks_max"] = (b["fallbacks"], b["fallbacks"] is not None and
                                  b["fallbacks"] <= e["P3/B_fallbacks_max"])
    legs["P3/B_sum_mismatch_lines_max"] = (b["p1_bad_lines"], b["p1_bad_lines"] <= e["P3/B_sum_mismatch_lines_max"])
    ratio = b["fps"] / a["fps"] if a["fps"] else float("nan")
    legs["P4/fps_ratio_min"] = ((a["fps"], b["fps"], ratio), ratio >= e["P4/fps_ratio_min"])
    r = e["P4/B_fps_range"]
    legs["P4/B_fps_range"] = (b["fps"], r[0] <= b["fps"] <= r[1])
    void = not all(ok for k, (_, ok) in legs.items() if k.startswith(("M0/", "M1/")))
    return legs, void


def selftest():
    stall_body = ("RPBreaks:900 Finish:420(vtx0 sc3 sd{sd} buf0 fb0 pres60 flip0 flu0 "
                  "stl0 stlDef0 stlBat0) InlClr:0/0 PreDL:0 sd[ev0 noCb0 dl0 cDef{sd} "
                  "cDefC0 pDl0 dDl0] dlSrc[defFb0 ppdFb0 dirtyIf0] dif[ovl0 ovlSh0 exp0 "
                  "expSh0 blt0 flu0 dds0 oth0]")
    head = ("[evict372] dirty/clean by mask (1role 2fmt 4pitch 8small 10swz 20ovl "
            "40zdim): m03:{d}/0 m04:5/1 overflow=0 handoffs={h} fallbacks=0")
    pair = ("[evict372] pair0 n={n} m03 C f44 ln p2560 640x480 b4 -> "
            "Z f129 ln p2560 640x480 b4")
    lines = ["09-26 10:00:00.000 I/hakuX-vk( 1): boot"]
    # Before the window, then two prints and ten stall lines in it.
    lines.append("09-26 10:00:10.000 I/hakuX   ( 1): " + head.format(d=100, h=7))
    for i in range(10):
        s = 140 + 4 * i
        stamp = "09-26 10:%02d:%02d.000" % (s // 60, s % 60)
        lines.append(stamp + " I/hakuX-stall( 1): " + stall_body.format(sd=120))
        lines.append(stamp + " I/hakuX-perf( 1): gfps=15")
    lines.append("09-26 10:03:00.000 I/hakuX   ( 1): " + head.format(d=1300, h=1207))
    lines.append("09-26 10:03:00.000 I/hakuX   ( 1): " + pair.format(n=1200))
    path = "/tmp/abread-selftest-%d.txt" % os.getpid()
    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")
    try:
        o = arm(path, 135, 265, True)
    finally:
        os.unlink(path)
    assert o["lines"] == 10 and o["window_intact"], o
    assert o["dirty_by_mask"] == {3: 1200}, o["dirty_by_mask"]
    assert abs(o["dirty_per_frame"] - 2.0) < 1e-9, o
    assert abs(o["handoffs_per_frame"] - 2.0) < 1e-9, o
    assert o["top_pair_same_geometry"] is True, o["top_pair"]
    assert abs(o["sd_per_frame"] - 2.0) < 1e-9, o
    # The rival geometry must read as not the same.
    p = PAIR.search(pair.replace("-> Z f129 ln p2560", "-> Z f129 ln p1280").format(n=1))
    g = p.groups()
    assert g[13] == "1280"
    print("selftest ok")


def main(a):
    if a[:1] == ["--selftest"]:
        return selftest()
    pa, pb = a[0], a[1]
    lo, hi = 135.0, 265.0
    if "--window" in a:
        lo, hi = map(float, a[a.index("--window") + 1].split(","))

    def spec(flag):
        if flag not in a:
            return None
        meta = json.load(open(a[a.index(flag) + 1]))
        return "hakuX-stall" in (meta.get("logcat") or {}).get("spec", "")

    oa = arm(pa, lo, hi, spec("--spec-a"))
    ob = arm(pb, lo, hi, spec("--spec-b"))
    nan = lambda x: None if isinstance(x, float) and math.isnan(x) else x  # noqa: E731
    print(json.dumps({"A": oa, "B": ob}, indent=1, default=nan))
    if "--prediction" in a:
        pred = json.load(open(a[a.index("--prediction") + 1]))
        legs, void = judge(oa, ob, pred)
        for k, (got, ok) in legs.items():
            print("%-36s %-5s %s" % (k, "PASS" if ok else "FAIL", got))
        print("VERDICT", "VOID" if void else
              ("PASS" if all(ok for _, ok in legs.values()) else "FAIL"))


if __name__ == "__main__":
    main(sys.argv[1:])
