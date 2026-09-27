#!/usr/bin/env python3
"""Judge the same-session Thor A/B of Blinx's attract demo for #372 (quadrant).

    abquad.py <A logcat> <B logcat> [--window 135,265]
              [--spec-a result.json] [--spec-b result.json]
              [--prediction docs/testing/predictions/blinx372e-demo-ab.json]
    abquad.py --selftest

A is master; B also copies the small zeta binding into the corner of the
large one on the flip back (vk/surface.c surface_quad_record). The stall line,
time zero, the demo fps and [evict372] are read by blinx372d/abread.py (which
reads them as blinx372c/stallread.py does), imported, so the three lanes read
the demo the same way. This file adds [quad372] and [surfwatch382]'s
lost_writes, both cumulative since boot and printed every 5 s: the window's
count is the last print in the window minus the last print before it.
"""
import json
import math
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "blinx372d"))
import abread  # noqa: E402
import stallread  # noqa: E402  (abread put blinx372c on the path)

QUAD = re.compile(r"\[quad372\] copies=(\d+) arms=(\d+) cpu_writes=(\d+) "
                  r"vram_changed=(\d+)")
WATCH = re.compile(r"\[surfwatch382\] .*lost_writes=(\d+)")
KEYS = ("copies", "arms", "cpu_writes", "vram_changed")

M_SMALL, M_ZDIM = 0x08, 0x40   # the demo's two flips (blinx372d sec 1)


def read_counters(path, lo, hi):
    """{name: (before, last)} for [quad372] fields and lost_writes."""
    t0, seen = None, {}
    for line in open(path, errors="replace"):
        strict = stallread.TS.match(line)
        if t0 is None and strict and strict.group(2).startswith("hakuX"):
            t0 = stallread.ts(strict.group(1))
        m = abread.TS_PADDED.match(line)
        if not m or t0 is None:
            continue
        t, body = stallread.ts(m.group(1)) - t0, m.group(3)
        vals = {}
        q = QUAD.search(body)
        if q:
            vals = dict(zip(KEYS, map(int, q.groups())))
        w = WATCH.search(body)
        if w:
            vals = {"lost_writes": int(w.group(1))}
        for k, v in vals.items():
            b, last = seen.get(k, (None, None))
            if t < lo:
                b = v
            elif t < hi:
                last = v
            seen[k] = (b, last)
    return {k: (None if last is None else last - (b or 0))
            for k, (b, last) in seen.items()}


def arm(path, lo, hi, spec):
    out = abread.arm(path, lo, hi, spec)
    c = read_counters(path, lo, hi)
    out.update({k: c.get(k) for k in KEYS + ("lost_writes",)})
    d = out["dirty_by_mask"] or {}
    out["dirty_small"] = d.get(M_SMALL, 0)
    out["dirty_zdim"] = d.get(M_ZDIM, 0)
    out["dirty_all"] = sum(d.values())
    # sd per flip, not per display frame: a faster B flips more often per
    # second, and sd/frame would move with the frame rate as well as the fix.
    flips = out["dirty_small"] + out["dirty_zdim"]
    out["sd_per_flip"] = (out["sd_per_frame"] * out["frames"] / flips
                          if flips else float("nan"))
    return out


def judge(a, b, pred):
    e = pred["expect"]
    legs = {}
    for name, o in (("A", a), ("B", b)):
        legs["M0/%s_spec_has_stall" % name] = (o["spec_has_stall"], o["spec_has_stall"] is True)
        legs["M0/%s_stall_lines" % name] = (o["lines"], o["lines"] >= e["M0/stall_lines_min"])
        legs["M0/%s_window_intact" % name] = (o["window_intact"], o["window_intact"] is True)
        legs["M1/%s_evict372_live" % name] = (o["evict372_lines"], o["evict372_lines"] is True)
    legs["M1/B_quad372_live"] = (b["copies"], b["copies"] is not None)
    legs["M1/B_lost_writes_live"] = (b["lost_writes"], b["lost_writes"] is not None)

    share = ((a["dirty_small"] + a["dirty_zdim"]) / a["dirty_all"]
             if a["dirty_all"] else float("nan"))
    legs["P0/A_flip_share_min"] = (share, share >= e["P0/A_flip_share_min"])
    legs["P0/A_sd_per_flip_min"] = (a["sd_per_flip"], a["sd_per_flip"] >= e["P0/A_sd_per_flip_min"])

    cover = (b["copies"] / b["dirty_small"]
             if b["copies"] is not None and b["dirty_small"] else float("nan"))
    legs["P1/B_copies_per_small_flip_min"] = (
        (b["copies"], b["dirty_small"], cover), cover >= e["P1/B_copies_per_small_flip_min"])
    legs["P1/B_sd_per_flip_max"] = (b["sd_per_flip"], b["sd_per_flip"] <= e["P1/B_sd_per_flip_max"])

    for k in ("cpu_writes", "vram_changed", "lost_writes", "fallbacks"):
        leg = "P2/B_%s_max" % k
        legs[leg] = (b[k], b[k] is not None and b[k] <= e[leg])

    ratio = b["fps"] / a["fps"] if a["fps"] else float("nan")
    legs["P3/fps_ratio_min"] = ((a["fps"], b["fps"], ratio), ratio >= e["P3/fps_ratio_min"])
    r = e["P3/B_fps_range"]
    legs["P3/B_fps_range"] = (b["fps"], r[0] <= b["fps"] <= r[1])
    void = not all(ok for k, (_, ok) in legs.items() if k.startswith(("M0/", "M1/")))
    return legs, void


def selftest():
    stall_body = ("RPBreaks:900 Finish:420(vtx0 sc3 sd{sd} buf0 fb0 pres60 flip0 flu0 "
                  "stl0 stlDef0 stlBat0) InlClr:0/0 PreDL:0 sd[ev0 noCb0 dl0 cDef{sd} "
                  "cDefC0 pDl0 dDl0] dlSrc[defFb0 ppdFb0 dirtyIf0] dif[ovl0 ovlSh0 exp0 "
                  "expSh0 blt0 flu0 dds0 oth0]")
    head = ("[evict372] dirty/clean by mask (1role 2fmt 4pitch 8small 10swz 20ovl "
            "40zdim): m08:{s}/0 m40:{z}/0 m10:14/0 overflow=0 handoffs=2 fallbacks=0")
    quad = "[quad372] copies={c} arms={a} cpu_writes=0 vram_changed={v}"
    watch = ("[surfwatch382] suspended=1 suspends=9 rearms=9 gap_writes=0 "
             "lost_writes={l}")
    lines = ["09-26 10:00:00.000 I/hakuX-vk( 1): boot"]
    lines.append("09-26 10:00:10.000 I/hakuX   ( 1): " + head.format(s=100, z=100))
    lines.append("09-26 10:00:10.000 I/hakuX   ( 1): " + quad.format(c=90, a=95, v=1))
    lines.append("09-26 10:00:10.000 I/hakuX   ( 1): " + watch.format(l=2))
    for i in range(10):
        s = 140 + 4 * i
        stamp = "09-26 10:%02d:%02d.000" % (s // 60, s % 60)
        lines.append(stamp + " I/hakuX-stall( 1): " + stall_body.format(sd=60))
        lines.append(stamp + " I/hakuX-perf( 1): gfps=15")
    lines.append("09-26 10:03:00.000 I/hakuX   ( 1): " + head.format(s=700, z=700))
    lines.append("09-26 10:03:00.000 I/hakuX   ( 1): " + quad.format(c=660, a=700, v=1))
    lines.append("09-26 10:03:00.000 I/hakuX   ( 1): " + watch.format(l=2))
    # After the window: must not count.
    lines.append("09-26 10:05:00.000 I/hakuX   ( 1): " + quad.format(c=9999, a=9999, v=7))
    path = "/tmp/abquad-selftest-%d.txt" % os.getpid()
    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")
    try:
        o = arm(path, 135, 265, True)
    finally:
        os.unlink(path)
    assert o["lines"] == 10 and o["window_intact"], o
    assert (o["dirty_small"], o["dirty_zdim"], o["dirty_all"]) == (600, 600, 1200), o
    assert (o["copies"], o["arms"], o["vram_changed"]) == (570, 605, 0), o
    assert o["cpu_writes"] == 0 and o["lost_writes"] == 0, o
    assert abs(o["sd_per_frame"] - 1.0) < 1e-9, o
    assert abs(o["sd_per_flip"] - 0.5) < 1e-9, o   # 600 sd over 1200 flips
    # A log with no [quad372] line reads None, not zero.
    assert read_counters(os.devnull, 135, 265).get("copies") is None
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
