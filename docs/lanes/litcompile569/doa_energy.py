#!/usr/bin/env python3
"""Gate 4, post hoc: fps, GPU ms per frame and energy per frame by scene.

    doa_energy.py <base dir> <fix dir> BASE_SEGS FIX_SEGS

*_SEGS as in doa_gpu_segments.py (name=HH:MM:SS-HH:MM:SS,...), from the route
frames. fps is flips over wall time from the [shd413] windows that close in the
segment with no pipeline miss (dpm == 0; 60 flips each), so a compile stall
does not lower it. Power is net: battery draw plus USB input, from the
thermal.jsonl samples inside the segment (every ~31 s, so a segment holds 1-4).
J per frame is that mean power over that fps. Written after the pair ran; the
fix arm's title_verdict.py is void (adb dropped at 00:48:51), so this is the
only j_per_frame the pair has.
"""
import json
import os
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import doa_gpu_segments as g  # noqa: E402
import fbwin  # noqa: E402  (put on sys.path by doa_gpu_segments)


def power(d):
    out = []
    for ln in open(os.path.join(d, "thermal.jsonl")):
        if not ln.strip():
            continue
        r = json.loads(ln)
        b = ((r.get("pw") or {}).get("battery") or {})
        u = ((r.get("pw") or {}).get("usb") or {})
        if r.get("label") != "hold" or b.get("current_now") is None:
            continue
        w = -b["current_now"] * b["voltage_now"] / 1e12
        if u.get("online"):
            w += u["current_now"] * u["voltage_now"] / 1e12
        out.append((g.hms(r["dev_time"].split()[1]), w))
    return out


def arm(d):
    lc, _ = fbwin.logcat_of(d)
    wins, _, _ = fbwin.parse(open(lc, errors="replace").read().splitlines())
    return wins, g.samples(d), power(d)


def seg(a, lo, hi):
    wins, gpu, pw = a
    ws = [w for w in wins if lo <= w["t"] <= hi and w["dt_ms"] > 0 and w["dpm"] == 0]
    fps = 60.0 * len(ws) / (sum(w["dt_ms"] for w in ws) / 1000.0) if ws else float("nan")
    gt = [v for t, v in gpu if lo <= t <= hi]
    p = [w for t, w in pw if lo <= t <= hi]
    mp = statistics.mean(p) if p else float("nan")
    return fps, (statistics.median(gt) if gt else float("nan")), len(gt), mp, len(p), mp / fps


def main(bd, fd, bs, fs):
    A, B = arm(bd), arm(fd)
    print("%-8s %22s %22s %22s %18s" % ("", "fps b -> f", "GPU ms/frame b -> f", "net W b -> f (n)",
                                         "J/frame b -> f"))
    for (name, a, b), (_, c, d) in zip(g.segs(bs), g.segs(fs)):
        x, y = seg(A, a, b), seg(B, c, d)
        print("%-8s %9.1f -> %5.1f (%.2f) %6.1f -> %5.1f (%.2f) %5.2f -> %5.2f (%d/%d) %6.3f -> %.3f (%.2f)" % (
            name, x[0], y[0], y[0] / x[0], x[1], y[1], y[1] / x[1], x[3], y[3], x[4], y[4],
            x[5], y[5], y[5] / x[5]))


if __name__ == "__main__":
    if len(sys.argv) != 5:
        sys.exit(__doc__)
    main(*sys.argv[1:])
