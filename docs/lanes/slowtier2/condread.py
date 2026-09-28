#!/usr/bin/env python3
"""One title reading, read for its conditions and for where the frame goes,
from the lines every build logs (no perflog needed).

    condread.py <result-id> [--window lo,hi] [--bins 30] [--split S]

Window: the scored window of title_verdict.py (the route's `mark gameplay`,
else `mark play`, to `soak end`); for a result the status page read as a
"soak" (no mark), 90-240 s after the first hakuX-perf line, as
status_html.py's _soak_median does. --window overrides it (seconds after
logcat line 1). --split S also reads the window in two halves at S seconds
after line 1 (before / after a fall).

Conditions:
  - device, ref, apk, requester, env, regimen (run.log `PERF: regimen=`)
  - thermal.jsonl (runs after #508): xo-therm at start and at the mark, and
    the first sample with a pause cooling device above 0, relative to the mark
  - no thermal.jsonl: the previous run on the same device (from the result
    dirs' request.json / DONE mtimes): how long before this one it ended and
    how long it ran. A run started within minutes of a long one is a warm start.
  - 30 s bins of fps from `soak start` (60 flips per gfps line, as
    title_verdict.py counts them) and lane.thermal507's #507 shape test: at
    200 s or later, the three preceding bins' median >= 10 and every later
    bin < a third of it.

Counters over the window (medians of per-line values):
  fps          60 flips / time between gfps lines (title_verdict's windows)
  G, Ri        smoothed guest frame ms and renderer (PFIFO) idle ms per frame
  busy         G - Ri: the PFIFO thread's non-idle ms per frame (wall, includes
               its GPU waits)
  Vpf          VBLANKs per flip
  vcpu%        [tlb68] cpu/dt: the vCPU thread's on-CPU share
  rd_ms, rdo_ms  [tlb68] rdus/rdous per frame: TLB dirty resets on the vCPU /
               on other threads (the render thread's, #548)
  ff/s, pf/s   full TLB flushes and page flushes per second
  inval/s, disc/s  hakuX-pages code invalidations and TBs discarded per second (#424 churn)
  kicks/s, backlog  fifoskew pusher kicks per second, mean bytes behind
  idlehalt     [idlehalt] lines, if any (#525 builds)
  starve%      hakuX-audiocap zero-filled output share
"""
import argparse
import json
import os
import re
import statistics
from datetime import datetime

D = os.environ.get("DISPATCH_DIR", "/home/justin/hakux-work/dispatch")
TS = re.compile(r"^(\d\d-\d\d \d\d:\d\d:\d\d\.\d+)\s+\w/([\w-]+)\s*\(\s*\d+\): ?(.*)$")
GF = re.compile(r"gfps=(\d+)\s+G:([\d.]+)\(([\d.]+)-([\d.]+)\).*?Vpf:([\d.]+) Ri:([\d.]+)")


def ts(s):
    return datetime.strptime("2026-" + s, "%Y-%m-%d %H:%M:%S.%f").timestamp()


def num(pat, s):
    m = re.search(pat, s)
    return float(m.group(1)) if m else None


def load(p):
    try:
        return json.load(open(p))
    except Exception:
        return None


def med(xs):
    xs = [x for x in xs if x is not None]
    return statistics.median(xs) if xs else None


def claimed(rdir):
    """When the device took the request: route.txt is written into the
    result dir at the claim; request.json's mtime is the QUEUE time (it
    equals the id's epoch), so it is only the fallback."""
    for f in ("route.txt", "run.log", "request.json"):
        p = f"{rdir}/{f}"
        if os.path.exists(p):
            return os.path.getmtime(p), f
    raise OSError(rdir)


def device_runs(dev):
    """(start, end, rid, title, seconds) for every result on dev, from mtimes."""
    out = []
    root = f"{D}/results"
    for d in os.listdir(root):
        r = load(f"{root}/{d}/result.json")
        if not r or r.get("device_label") != dev:
            continue
        try:
            end = os.path.getmtime(f"{root}/{d}/DONE")
            start = claimed(f"{root}/{d}")[0]
        except OSError:
            continue
        out.append((start, end, d, r.get("title") or r.get("disc_id") or "-", r.get("seconds")))
    return sorted(out, key=lambda x: x[1])


def thermal(rdir, mark_abs):
    p = f"{rdir}/thermal.jsonl"
    if not os.path.exists(p):
        return None
    rows = []
    for line in open(p, errors="replace"):
        try:
            j = json.loads(line)
        except Exception:
            continue
        xo = next((x[2] / 1000.0 for x in j.get("tz", []) if x[1] == "xo-therm"), None)
        paused = [c[1] for c in j.get("cool", []) if "pause" in c[1] and c[2] > 0]
        rows.append((j.get("t"), j.get("label"), xo, paused))
    if not rows:
        return "thermal.jsonl empty"
    s = "start xo-therm %.1f C" % rows[0][2] if rows[0][2] is not None else "start xo-therm ?"
    if mark_abs is not None:
        at = [r for r in rows if r[0] and r[0] >= mark_abs]
        if at:
            s += ", at the mark %.1f C" % at[0][2]
    s += ", max %.1f C, %d samples" % (max(r[2] for r in rows if r[2] is not None), len(rows))
    first = next((r for r in rows if r[3]), None)
    if first:
        rel = (first[0] - mark_abs) if (mark_abs and first[0]) else None
        s += "; FIRST PAUSE %s at %s (label %s)" % (
            ",".join(first[3]), ("mark%+.0f s" % rel) if rel is not None else "?", first[1])
    else:
        s += "; no pause device above 0"
    return s


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("rid")
    ap.add_argument("--window")
    ap.add_argument("--bins", type=float, default=30.0)
    ap.add_argument("--split", type=float)
    ap.add_argument("--under", type=float, help="read the counters only inside windows under this fps")
    ap.add_argument("--status", action="store_true",
                    help="use the status page's soak window (90-240 s after the first perf line) even if a mark exists")
    a = ap.parse_args()
    rdir = f"{D}/results/{a.rid}"
    r = load(f"{rdir}/result.json") or {}
    print("== %s: %s | %s ref %s apk %s | %s | %ss | env %s | shader_cache %s" % (
        a.rid, r.get("title"), r.get("device_label"), r.get("ref"), r.get("apk_sha"),
        r.get("requester"), r.get("seconds"), r.get("env"), r.get("shader_cache", "-")))
    reg = [l.strip() for l in open(f"{rdir}/run.log", errors="replace") if l.startswith(("PERF:", "THERMAL:"))] \
        if os.path.exists(f"{rdir}/run.log") else []
    print("run.log:", " / ".join(reg) or "no PERF line (regimen unrecorded)")

    # logcat
    t0 = None
    marks = {}
    gf, tlb, pages, fsk, ih, starve = [], [], [], [], [], []
    seen = set()
    for line in open(f"{rdir}/logcat.txt", errors="replace"):
        # title_verdict.py drops repeated lines (logcat restarts re-dump the buffer)
        if line in seen:
            continue
        seen.add(line)
        m = TS.match(line)
        if not m:
            continue
        t = ts(m.group(1))
        t0 = t if t0 is None else t0
        tag, msg = m.group(2), m.group(3)
        rt = t - t0
        if tag == "hakuX-route":
            marks.setdefault(msg.strip(), rt)
        elif tag == "hakuX-perf" and msg.startswith("gfps="):
            g = GF.search(msg)
            if g:
                gf.append((rt, float(g.group(2)), float(g.group(5)), float(g.group(6))))
        elif tag == "hakuX-perf" and msg.startswith("fifoskew"):
            w = num(r"win=(\d+)", msg)
            fsk.append((rt, num(r"kicks=(\d+)", msg) * 1000 / w if w else None, num(r"backlog\(mean=(\d+)", msg)))
        elif tag == "hakuX" and msg.startswith("[tlb68]"):
            dt = num(r"dt=(\d+)", msg)
            if dt:
                tlb.append((rt, 100 * num(r"cpu=(\d+)", msg) / dt, num(r"rdus=(\d+)", msg) / 1000 / dt,
                            num(r"rdous=(\d+)", msg) / 1000 / dt, num(r" ff=(\d+)", msg) * 1000 / dt,
                            num(r" pf=(\d+)", msg) * 1000 / dt))
        elif tag == "hakuX" and msg.startswith("[idlehalt]"):
            ih.append((rt, msg))
        elif tag == "hakuX-pages" and msg.startswith("inval"):
            pages.append((rt, num(r"ev=(\d+)", msg), num(r"di=(\d+)", msg)))
        elif tag == "hakuX-audiocap" and msg.startswith("starve"):
            starve.append((rt, num(r"= ([\d.]+)% of output", msg)))
    ss = marks.get("soak start", 0.0)
    mk_label = "mark gameplay" if "mark gameplay" in marks else ("mark play" if "mark play" in marks else None)
    mark = marks.get(mk_label) if mk_label else None
    end = marks.get("soak end", gf[-1][0] if gf else None)
    if a.window:
        lo, hi = (float(x) for x in a.window.split(","))
        wsrc = "given"
    elif mark is not None and not a.status:
        lo, hi, wsrc = mark, end, "verdict (%s -> soak end)" % mk_label
    elif gf:
        lo, hi, wsrc = gf[0][0] + 90, gf[0][0] + 240, "status soak (90-240 s after the first perf line)"
    else:
        print("no gfps lines")
        return
    print("marks: soak start %.0f, %s %s, soak end %s; window %.0f-%.0f s (%s)" % (
        ss, mk_label, "%.0f" % mark if mark is not None else "-", "%.0f" % end if end else "-", lo, hi, wsrc))

    # conditions
    mark_abs = None
    if t0 is not None and mark is not None:
        mark_abs = t0 + mark
    th = thermal(rdir, mark_abs)
    if th:
        print("thermal:", th)
    else:
        dev = r.get("device_label")
        try:
            me, src = claimed(rdir)
            runs = device_runs(dev)
            prev = [x for x in runs if x[1] <= me + 60 and x[2] != a.rid]
            if prev:
                txt = "; ".join("%s (%s, %ss) ended %.0f s before" % (p[2], p[3][:30], p[4], me - p[1])
                                for p in reversed(prev[-2:]))
                print("thermal: no thermal.jsonl. Claim (%s mtime): previous %s runs: %s" % (src, dev, txt))
        except OSError:
            pass

    # bins
    # (start, end, fps) per 60-flip window, as title_verdict.py forms them:
    # a window is in the scored span when its opening line is at or after lo.
    fw_all = [(t0_, t1, 60.0 / (t1 - t0_)) for (t0_, *_), (t1, *_) in zip(gf, gf[1:]) if t1 > t0_]
    fl = [(t1, f) for _, t1, f in fw_all]
    bins = {}
    for t, f in fl:
        bins.setdefault(int((t - ss) // a.bins), []).append(f)
    keys = sorted(bins)
    bm = [(k, statistics.median(bins[k])) for k in keys]
    print("bins (%ds from soak start, median fps):" % a.bins,
          " ".join("%d:%.1f" % (k * a.bins, v) for k, v in bm))
    flag = None
    for i in range(3, len(bm)):
        if bm[i][0] * a.bins < 200:
            continue
        pre = statistics.median(v for _, v in bm[i - 3:i])
        if pre >= 10 and all(v < pre / 3 for _, v in bm[i:]):
            flag = (bm[i][0] * a.bins, pre, statistics.median(v for _, v in bm[i:]))
            break
    print("#507 shape:", "YES, fall at %.0f s from soak start: %.1f -> %.1f fps" % flag if flag else "no")

    def read(lo, hi, name):
        w = [f for s, e, f in fw_all if s >= lo and e <= hi + 1]
        # With --under F, the counters are read only inside the 60-flip
        # windows slower than F fps (the title's slow play, not its menus,
        # cutscenes at the cap or a pause), and the fps line still reports
        # every window, as the verdict does.
        spans = [(s, e) for s, e, f in fw_all if s >= lo and e <= hi + 1 and (a.under is None or f < a.under)]

        def inside(t):
            return any(s <= t <= e for s, e in spans)
        g = [x for x in gf if inside(x[0])]
        tl = [x for x in tlb if inside(x[0])]
        fk = [x for x in fsk if inside(x[0])]
        pg = [x for x in pages if lo <= x[0] <= hi]
        sv = [x[1] for x in starve if inside(x[0])]
        if a.under is not None:
            print("  counters from the %d windows under %.0f fps (%.0f s of %.0f)" % (
                len(spans), a.under, sum(e - s for s, e in spans), hi - lo))
        if not w:
            print("  %s: no fps windows" % name)
            return
        fw = sorted(w)
        G = med(x[1] for x in g)
        Ri = med(x[3] for x in g)
        fpsm = fw[len(fw) // 2]
        frame = 1000.0 / fpsm
        span = (pg[-1][0] - pg[0][0]) if len(pg) > 1 else None
        inv = sum(x[1] for x in pg[1:]) / span if span else None
        disc = sum(x[2] for x in pg[1:]) / span if span else None
        q = lambda p: fw[min(len(fw) - 1, int(p * len(fw)))]
        print("  %s %.0f-%.0f s: fps median %.2f (title_verdict's element; n=%d, min %.1f, p10/25/75/90 %.1f/%.1f/%.1f/%.1f)"
              " = %.1f ms/frame | G %.1f Ri %.1f busy %.1f Vpf %.2f"
              % (name, lo, hi, fpsm, len(w), fw[0], q(.1), q(.25), q(.75), q(.9), frame, G or -1, Ri or -1,
                 (G - Ri) if G and Ri is not None else -1, med(x[2] for x in g) or -1))
        if tl:
            rd = med(x[2] for x in tl)
            rdo = med(x[3] for x in tl)
            print("    vcpu %.1f%% (%.1f ms/frame on-CPU) | TLB resets vCPU %.2f ms/frame, other threads %.2f ms/frame"
                  " | ff/s %.0f pf/s %.0f"
                  % (med(x[1] for x in tl), med(x[1] for x in tl) * frame / 100, rd * frame, rdo * frame,
                     med(x[4] for x in tl), med(x[5] for x in tl)))
        if fk:
            print("    fifoskew kicks/s %.0f backlog mean %.0f B" % (med(x[1] for x in fk), med(x[2] for x in fk)))
        if inv is not None:
            print("    #424 churn: %.0f invalidations/s, %.0f TBs discarded/s" % (inv, disc))
        if sv:
            print("    audio zero-filled %.1f%%" % med(sv))
        hh = [x[1] for x in ih if lo <= x[0] <= hi]
        if hh:
            print("    idlehalt %d lines, last: %s" % (len(hh), hh[-1][:200]))

    read(lo, hi, "window")
    if a.split:
        read(lo, a.split, "before")
        read(a.split, hi, "after")


if __name__ == "__main__":
    main()
