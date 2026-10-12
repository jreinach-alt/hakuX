#!/usr/bin/env python3
"""Read a HAKUX_ZETA_D24 A/B (lane.fpsbelow1012, NOTES section 5) from the
runs' logcats, one title at a time.

    zread.py <A-id> <B-id> [--from S] [--until S] [--expect <prediction.json> --key <title key>]

Per run:
  zfmt    the renderer's init line `nv2a: Z24S8 host format 0x..`: 0x82 is
          D32_SFLOAT_S8_UINT (master), 0x81 D24_UNORM_S8_UINT (the switch).
  gfps    hakuX-perf `gfps=` lines (one a second): median and share >= 55.
  G       the same lines' `G:`, the guest's smoothed flip-to-flip interval in
          ms (profile.c game_frame_ms): median. Frame time, not GPU time.
  in/out  xemu-xfr `XFR rp` lines (HAKUX_GPUXFR=1): the window's mean in-pass
          span over its mean outer span. A two-tile GMEM pass stamps only its
          last tile in-pass, so it reads ~0.5; one tile or sysmem reads >= 0.8
          (vk/draw.c, the census comment).
  out     the same lines' outer render-pass span, GPU ms per command buffer
          (mean of the lines' means). This is what the replay costs the GPU.
--from/--until are seconds after the run's first hakuX-perf line, so the two
arms of one route are read over the same stretch of it.

With --expect, applies prediction["expect"][key]:
  V  both arms' zfmt as named (a_zfmt, b_zfmt) and >= min_perf perf lines
  M  A's in/out <= a_inout_max and B's in/out >= b_inout_min (the tile count
     moved; read only when A is in the class)
  P  B's mean outer span <= A's * out_ratio_max (the GPU did less per pass)
  W  B's median G <= A's * g_ratio_max, or B's median gfps >= A's + gfps_gain_min
"""
import json
import os
import re
import statistics as st
import sys

D = os.environ.get("DISPATCH_DIR", "/home/justin/hakux-work/dispatch") + "/results"
LINE = re.compile(r"\d\d-\d\d (\d\d):(\d\d):(\d\d\.\d+) \w/([\w-]+)\s*\(\s*\d+\): (.*)")


def opt(name, conv=str, default=None):
    if name in sys.argv:
        return conv(sys.argv[sys.argv.index(name) + 1])
    return default


def read(rid, t_from, t_until):
    zfmt = None
    perf = []      # (t, gfps, G)
    rp = []        # (t, in_mean, out_mean)
    seen = set()
    t0 = None
    for line in open(os.path.join(D, rid, "logcat.txt"), errors="replace"):
        m = LINE.match(line)
        if not m:
            continue
        h, mi, s, tag, body = m.groups()
        t = int(h) * 3600 + int(mi) * 60 + float(s)
        if (t, body) in seen:
            continue
        seen.add((t, body))
        z = re.search(r"nv2a: Z24S8 host format (0x[0-9a-f]+)", body)
        if z:
            zfmt = z.group(1)
        elif tag == "hakuX-perf" and body.startswith("gfps="):
            g = re.search(r"G:([\d.]+)", body)
            t0 = t if t0 is None else t0
            perf.append((t, int(re.match(r"gfps=(\d+)", body).group(1)),
                         float(g.group(1)) if g else None))
        elif body.startswith("xemu-xfr XFR rp "):
            v = dict((k, float(mean)) for k, med, mean, p90 in re.findall(
                r"(?<![\w])(in|out) ([\d.-]+) ([\d.-]+) ([\d.-]+)", body))
            if "in" in v and "out" in v:
                rp.append((t, v["in"], v["out"]))
    if t0 is None:
        return {"rid": rid, "zfmt": zfmt, "n": 0}
    lo = t0 + (t_from or 0)
    hi = t0 + t_until if t_until is not None else 1e9
    perf = [p for p in perf if lo <= p[0] <= hi]
    rp = [r for r in rp if lo <= r[0] <= hi]
    gf = [p[1] for p in perf]
    G = [p[2] for p in perf if p[2] is not None]
    out_sum = sum(r[2] for r in rp)
    return {
        "rid": rid, "zfmt": zfmt, "n": len(perf),
        "gfps_med": st.median(gf) if gf else None,
        "gfps55": sum(1 for x in gf if x >= 55) / len(gf) if gf else None,
        "G_med": st.median(G) if G else None,
        "inout": sum(r[1] for r in rp) / out_sum if out_sum else None,
        "out_ms": out_sum / len(rp) if rp else None,
        "rp_lines": len(rp),
    }


def show(tag, r):
    f = lambda v, p="%.2f": "-" if v is None else p % v
    print("%s %-38s zfmt %-5s perf %4d gfps med %s (>=55: %s) G med %s ms in/out %s out %s ms (%d rp lines)" % (
        tag, r["rid"], r["zfmt"] or "-", r["n"], f(r.get("gfps_med"), "%.0f"),
        f(r.get("gfps55")), f(r.get("G_med"), "%.1f"), f(r.get("inout")), f(r.get("out_ms")),
        r.get("rp_lines", 0)))


def main():
    a_id, b_id = sys.argv[1], sys.argv[2]
    t_from, t_until = opt("--from", float), opt("--until", float)
    A, B = read(a_id, t_from, t_until), read(b_id, t_from, t_until)
    show("A", A)
    show("B", B)
    exp_path, key = opt("--expect"), opt("--key")
    if not exp_path:
        return 0
    e = json.load(open(exp_path))["expect"][key]
    legs = []
    v = A["zfmt"] == e["a_zfmt"] and B["zfmt"] == e["b_zfmt"] and \
        min(A["n"], B["n"]) >= e["min_perf"]
    legs.append(("V", v, "zfmt A %s B %s, perf lines %d/%d" % (A["zfmt"], B["zfmt"], A["n"], B["n"])))
    if A.get("inout") is not None and B.get("inout") is not None:
        m = A["inout"] <= e["a_inout_max"] and B["inout"] >= e["b_inout_min"]
        legs.append(("M", m, "in/out A %.2f B %.2f" % (A["inout"], B["inout"])))
    else:
        legs.append(("M", False, "no census in one arm"))
    if A.get("out_ms") and B.get("out_ms") is not None:
        legs.append(("P", B["out_ms"] <= A["out_ms"] * e["out_ratio_max"],
                     "outer span A %.2f B %.2f ms (x%.2f)" % (A["out_ms"], B["out_ms"], B["out_ms"] / A["out_ms"])))
    else:
        legs.append(("P", False, "no census in one arm"))
    w = False
    why = []
    if A.get("G_med") and B.get("G_med"):
        w = w or B["G_med"] <= A["G_med"] * e["g_ratio_max"]
        why.append("G %.1f -> %.1f ms (x%.2f)" % (A["G_med"], B["G_med"], B["G_med"] / A["G_med"]))
    if A.get("gfps_med") is not None and B.get("gfps_med") is not None:
        w = w or B["gfps_med"] >= A["gfps_med"] + e["gfps_gain_min"]
        why.append("gfps %.0f -> %.0f" % (A["gfps_med"], B["gfps_med"]))
    legs.append(("W", w, ", ".join(why)))
    for name, ok, txt in legs:
        print("%s %s  %s" % (name, "PASS" if ok else "FAIL", txt))
    return 0 if all(ok for _, ok, _ in legs) else 1


if __name__ == "__main__":
    sys.exit(main())
