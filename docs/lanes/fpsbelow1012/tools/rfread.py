#!/usr/bin/env python3
"""Read a run's `range` completions after its gameplay mark (lane.fpsbelow1012, NOTES.md sections 11 and 13).

    rfread.py <result id>                                    one run
    rfread.py <A> <B> --expect <prediction.json> --key <K>   judge a pair against expect[K]

The window is every [sdcall] period (frames >= 50) after the route's `mark gameplay` line in logcat.txt.

One run prints, per 60 frames over the window:
  - `range`'s completions (fin + fence + pre), downloads and wait from the [sdcall] line, as the median over periods
    and as the window total (sum / frames x 60);
  - the [sdrfin] split (surface.c, perf builds), as window totals: why each completion completed its batch. own:
    the lookup recorded a download. dest: it recorded none, and the range overlaps a pending download's destination.
    clean: neither, so the precise rule (L4c) would not complete. tscan: the texture scan's own test.
  - the HAKUX_VTX_EXACT init line.

A pair is judged with these legs, B against A:
  V  A's init line reads expect.a_vtx_exact and B's reads expect.b_vtx_exact; both have the mark and at least
     expect.min_periods periods after it. An arm that fails V is VOID (exit 2).
  C  A's median `range` downloads per 60 frames >= expect.a_dl_min. Below it A is NOT IN THE CLASS (exit 3): the
     run did not show the downloads the lever removes, and the pair is not judged.
  M  B's median `range` downloads per 60 frames <= expect.dl_ratio_max x A's.
  P  B's median `range` wait per 60 frames <= expect.wait_ratio_max x A's.
Exit 0 when M and P pass, 1 when one fails.
"""
import json
import os
import re
import statistics
import sys

D = os.environ.get("DISPATCH_DIR", "/home/justin/hakux-work/dispatch") + "/results"
SDC = re.compile(r"\[sdcall\] frames=(\d+)")
RNG = re.compile(r" range=fin(\d+)/fence(\d+)/pre(\d+)/dl(\d+)/([\d.]+)ms")
RF = re.compile(r"\[sdrfin\] frames=(\d+) rec=(\d+) own=n(\d+)/dl(\d+)/([\d.]+)ms dest=n(\d+)/dl(\d+)/([\d.]+)ms "
                r"clean=n(\d+)/dl(\d+)/([\d.]+)ms tscan=n(\d+)/dl(\d+)/([\d.]+)ms")
VX = re.compile(r"HAKUX_VTX_EXACT=(\d)")
CLS = ("own", "dest", "clean", "tscan")


def read(rid):
    r = {"rid": rid, "mark": None, "vx": None, "per": [], "frames": 0, "tot": [0, 0, 0.0],
         "rf": {c: [0, 0, 0.0] for c in CLS}, "rec": 0, "rf_frames": 0}
    for line in open(os.path.join(D, rid, "logcat.txt"), errors="replace"):
        if r["vx"] is None:
            m = VX.search(line)
            if m:
                r["vx"] = int(m.group(1))
        if "hakuX-route" in line and "mark gameplay" in line and r["mark"] is None:
            r["mark"] = line[:18]
            continue
        if r["mark"] is None:
            continue
        m = SDC.search(line)
        if m:
            fr = int(m.group(1))
            if fr < 50:
                continue
            k = 60.0 / fr
            g = RNG.search(line)
            n, dl, w = ((int(g.group(1)) + int(g.group(2)) + int(g.group(3)), int(g.group(4)), float(g.group(5)))
                        if g else (0, 0, 0.0))
            r["per"].append((n * k, dl * k, w * k))
            r["frames"] += fr
            r["tot"][0] += n
            r["tot"][1] += dl
            r["tot"][2] += w
            continue
        m = RF.search(line)
        if m and int(m.group(1)) >= 50:
            v = m.groups()
            r["rf_frames"] += int(v[0])
            r["rec"] += int(v[1])
            for i, c in enumerate(CLS):
                r["rf"][c][0] += int(v[2 + 3 * i])
                r["rf"][c][1] += int(v[3 + 3 * i])
                r["rf"][c][2] += float(v[4 + 3 * i])
    return r


def med(r, i):
    return statistics.median([p[i] for p in r["per"]]) if r["per"] else 0.0


def show(r):
    f = r["frames"] or 1
    print("%s: mark %s, HAKUX_VTX_EXACT=%s, %d periods, %d frames" % (r["rid"], r["mark"], r["vx"], len(r["per"]),
                                                                     r["frames"]))
    print("  range per 60 frames, median: n %.0f, dl %.0f, wait %.0f ms;  window total: n %.0f, dl %.0f, wait %.0f "
          "ms (%.1f ms/frame)" % (med(r, 0), med(r, 1), med(r, 2), r["tot"][0] * 60 / f, r["tot"][1] * 60 / f,
                                  r["tot"][2] * 60 / f, r["tot"][2] / f))
    rf = r["rf_frames"]
    if not rf:
        print("  [sdrfin]: none in the window")
        return
    allms = sum(r["rf"][c][2] for c in CLS) or 1
    print("  [sdrfin] per 60 frames over %d frames: recorded by own lookups %.0f" % (rf, r["rec"] * 60 / rf))
    for c in CLS:
        n, dl, ms = r["rf"][c]
        print("    %-5s n %6.0f  dl %6.0f  dl/n %5.1f  %6.0f ms  (%4.1f ms/frame, %3.0f%% of the split's time)" % (
            c, n * 60 / rf, dl * 60 / rf, dl / n if n else 0, ms * 60 / rf, ms / rf, 100 * ms / allms))


def main():
    a = sys.argv[1]
    if len(sys.argv) < 3 or sys.argv[2].startswith("--"):
        show(read(a))
        return 0
    b = sys.argv[2]
    pred = json.load(open(sys.argv[sys.argv.index("--expect") + 1]))
    e = pred["expect"][sys.argv[sys.argv.index("--key") + 1]]
    A, B = read(a), read(b)
    show(A)
    show(B)
    for arm, want, name in ((A, e["a_vtx_exact"], "A"), (B, e["b_vtx_exact"], "B")):
        if arm["vx"] != want or arm["mark"] is None or len(arm["per"]) < e["min_periods"]:
            print("V FAIL: %s init %s (want %s), mark %s, %d periods (want >= %d): VOID" % (
                name, arm["vx"], want, arm["mark"], len(arm["per"]), e["min_periods"]))
            return 2
    print("V pass")
    if med(A, 1) < e["a_dl_min"]:
        print("C: A's median range dl %.0f < %d per 60 frames: NOT IN THE CLASS" % (med(A, 1), e["a_dl_min"]))
        return 3
    print("C pass: A's median range dl %.0f >= %d" % (med(A, 1), e["a_dl_min"]))
    ok = True
    for leg, i, lim in (("M", 1, e["dl_ratio_max"]), ("P", 2, e["wait_ratio_max"])):
        ratio = med(B, i) / med(A, i) if med(A, i) else 0
        good = ratio <= lim
        ok &= good
        print("%s %s: B/A %.3f (B %.0f, A %.0f; limit %.2f)" % (leg, "pass" if good else "FAIL", ratio, med(B, i),
                                                                med(A, i), lim))
    return 0 if ok else 1


sys.exit(main())
