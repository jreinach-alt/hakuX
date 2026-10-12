#!/usr/bin/env python3
"""lane.perdraw1009's arm reader: NFS Most Wanted on route nfs-mw, HAKUX_UNI_* on (B) against off (A), one build.

    armread.py --a A1 [A2 ...] --b B1 [B2 ...] [--expect PRED.json] [--sheet OUT.png]

A run is a result dir or an id under $DISPATCH_DIR/results. Committed with the prediction it judges
(docs/testing/predictions/perdraw1009-nfs-soak.json) and not edited after an arm lands.

ROWS. One row per 2-s `hakuX-perf ... gfps=` line of the app's pid (the pid with the most of them),
with the `hakuX-phase` and `xemu-work` lines that follow it attached. Per row:
  us/draw     = Draw ms/frame * 1000 / BE (draws per frame), the renderer's per-draw dispatch cost
  pm/draw     = (Pipe + Mfp) * 1000 / BE. update_shader_uniforms runs in three timed places: Sh
                (inside Pipe), draw_mfp (Mfp), and the early pipeline hit (inside Pipe, outside
                Tx/Sh/Lu). Pipe + Mfp holds all three, so the whole saving lands in it.
A window's value is a ratio of sums (sum Draw / sum BE), so a heavy row weighs by its draws.

WINDOWS, in seconds of device clock after the logcat line `hakuX-route: mark gameplay` (the route's
`mark gameplay`, written by the app; a row's time is the end of its 2-s window):
  MOTION (0, 24]   RT held from the mark: the baseline (1-1791613176-perdraw1009-1735811) read
                   108 MPH at +10 s and 63 MPH at +21 s (host clock), and 0 MPH against the wall
                   from +31 s on.
  STATIC (40, 78]  the car wedged against the wall at 68% complete with RT held: one scene, the
                   baseline's us/draw 12.3 +- 0.2 over 120 rows. The matched-scene leg.
The frames say whether a run followed that script; --sheet writes each run's speedometer crops in a
row, to read by eye before any leg.

PIXELS (X). The route's frames in host-clock (38, 79] after run.log's `mark gameplay` (the STATIC
scene), paired across runs by order. Each frame is cut into 16 x 12 regions of 80 x 80 px and each
region's mean RGB taken; d = the largest channel difference of two means. The floor of a region is
the largest d between two runs of the SAME arm at that frame; a region fails when the largest
B-vs-A d exceeds floor + X_margin. With one run per arm there is no floor and the margin alone is
the bound. It sees a whole-scene shift (geometry, fog, lighting): a constant changed for a few
small draws moves no 80 px mean, and that is outside what it can see.
"""
import glob, json, os, re, statistics, sys

DISPATCH = os.environ.get("DISPATCH_DIR", "/home/justin/hakux-work/dispatch")
MOTION = (0.0, 24.0)
STATIC = (40.0, 78.0)
FRAMES_STATIC_HOST = (38.0, 79.0)
GRID = (16, 12)


def rdir(r):
    return r if os.path.isdir(r) else os.path.join(DISPATCH, "results", r)


def num(p, s):
    m = re.search(p, s)
    return float(m.group(1)) if m else None


def sec(t):
    h, m, s = t.split(":")
    return int(h) * 3600 + int(m) * 60 + float(s)


def read_run(d):
    lc = os.path.join(d, "logcat.txt")
    lines = open(lc, errors="replace").read().splitlines() if os.path.exists(lc) else []
    pids = {}
    for ln in lines:
        if "hakuX-perf" in ln and "gfps=" in ln:
            m = re.search(r"\(\s*(\d+)\)", ln)
            if m:
                pids[m.group(1)] = pids.get(m.group(1), 0) + 1
    pid = max(pids, key=pids.get) if pids else None
    run = dict(dir=d, id=os.path.basename(d.rstrip("/")), pid=pid, rows=[], mark=None, flags=None,
               fatal=0, route_done=False, host_mark=None, pause=[], apk=None, env=None)
    cur = None
    for ln in lines:
        t = ln[6:18]
        if "hakuX-route" in ln and "mark gameplay" in ln and run["mark"] is None:
            run["mark"] = sec(t)
        if "Fatal signal" in ln or "FATAL EXCEPTION" in ln:
            run["fatal"] += 1
        if pid is None or "(%s)" % pid not in ln.replace("( ", "("):
            continue
        if "[perdraw433]" in ln:
            m = re.search(r"bulk=(-?\d) ubercache=(-?\d) fogcache=(-?\d)", ln)
            if m:
                run["flags"] = tuple(int(x) for x in m.groups())
        if "hakuX-perf" in ln and "gfps=" in ln:
            cur = dict(t=sec(t), gfps=num(r"gfps=(\d+)", ln), G=num(r" G:([\d.]+)", ln))
            run["rows"].append(cur)
        elif cur is None:
            continue
        elif "hakuX-phase" in ln:
            for k in ("Draw", "Pipe", "Tx", "Sh", "Lu", "Desc", "Mfp", "Fin", "Sub", "Idle", "Tot"):
                cur[k] = num(r"[ \[(]" + k + r":([\d.]+)", ln)
        elif "xemu-work" in ln:
            cur["BE"] = num(r"BE:(\d+)", ln)
    rl = os.path.join(d, "run.log")
    if os.path.exists(rl):
        for ln in open(rl, errors="replace"):
            m = re.match(r"ROUTE (\d\d:\d\d:\d\d\.\d+) mark gameplay", ln)
            if m:
                run["host_mark"] = sec(m.group(1))
            if ln.startswith("ROUTE finished (rc 0)"):
                run["route_done"] = True
    th = os.path.join(d, "thermal.jsonl")
    if os.path.exists(th):
        for ln in open(th):
            try:
                j = json.loads(ln)
            except ValueError:
                continue
            if j.get("pause") and j.get("dev_time"):
                run["pause"].append(sec(j["dev_time"][6:]))
    for name, key in (("result.json", "apk_sha"), ("request.json", "env")):
        p = os.path.join(d, name)
        if os.path.exists(p):
            run["apk" if key == "apk_sha" else "env"] = json.load(open(p)).get(key)
    return run


def window(run, w):
    if run["mark"] is None:
        return []
    return [r for r in run["rows"] if r.get("BE") and r.get("Draw") is not None
            and w[0] < r["t"] - run["mark"] <= w[1]]


def summ(rows):
    if not rows:
        return None
    be = sum(r["BE"] for r in rows)
    s = lambda k: sum(r.get(k) or 0 for r in rows)
    m = lambda k: s(k) / len(rows)
    return dict(n=len(rows), usd=1000 * s("Draw") / be, pmd=1000 * (s("Pipe") + s("Mfp")) / be,
                shd=1000 * (s("Sh") + s("Mfp")) / be, Draw=m("Draw"), BE=be / len(rows),
                gfps=m("gfps"), Idle=m("Idle"), Tot=m("Tot"), Fin=m("Fin"), Desc=m("Desc"),
                rowsd=statistics.pstdev([1000 * r["Draw"] / r["BE"] for r in rows]))


def frames(run, lo, hi):
    out = []
    if run["host_mark"] is None:
        return out
    for f in sorted(glob.glob(os.path.join(run["dir"], "route-frames", "*.png"))):
        b = os.path.basename(f)
        m = re.match(r"(\d\d)(\d\d)(\d\d)-(.*)\.png", b)
        if not m or "drive" not in m.group(4):
            continue
        t = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + int(m.group(3))
        off = t - run["host_mark"]
        if off < -43200:
            off += 86400
        if lo < off <= hi:
            out.append(f)
    return out


def regions(path):
    from PIL import Image
    im = Image.open(path).convert("RGB")
    gw, gh = GRID
    small = im.resize((gw, gh), Image.BOX)
    return [small.getpixel((x, y)) for y in range(gh) for x in range(gw)]


def dmax(a, b):
    return [max(abs(p - q) for p, q in zip(x, y)) for x, y in zip(a, b)]


def sheet(runs, out):
    from PIL import Image
    crops = []
    for r in runs:
        fs = frames(r, -2, 200)
        crops.append([Image.open(f).convert("RGB").crop((900, 600, 1180, 880)).resize((112, 112)) for f in fs])
    w = max((len(c) for c in crops), default=0)
    sh = Image.new("RGB", (112 * max(w, 1), 112 * max(len(crops), 1)))
    for i, row in enumerate(crops):
        for j, c in enumerate(row):
            sh.paste(c, (112 * j, 112 * i))
    sh.save(out)
    print("sheet: %s (one row per run, in argument order: %s)" % (out, " ".join(r["id"] for r in runs)))


def main():
    a = sys.argv[1:]
    A, B, exp, out = [], [], {}, None
    tgt = None
    while a:
        k = a.pop(0)
        if k == "--a":
            tgt = A
        elif k == "--b":
            tgt = B
        elif k == "--expect":
            exp = json.load(open(a.pop(0))).get("expect", {})
            tgt = None
        elif k == "--sheet":
            out = a.pop(0)
            tgt = None
        elif tgt is not None:
            tgt.append(rdir(k))
        else:
            sys.exit("usage: armread.py --a A1 [A2 ...] --b B1 [B2 ...] [--expect PRED.json] [--sheet OUT.png]")
    e = lambda k, d: exp.get(k, d)
    RA = [read_run(d) for d in A]
    RB = [read_run(d) for d in B]
    if out:
        sheet(RA + RB, out)

    legs = []

    def leg(name, ok, text):
        legs.append((name, ok))
        print("%-3s %s  %s" % (name, "PASS" if ok else "FAIL", text))

    print("run                                      arm flags     apk           motion n us/d  pm/d gfps | static n us/d   sd  pm/d  sh/d  Draw   BE  gfps  Idle   Tot  Fin")
    for arm, rs in (("A", RA), ("B", RB)):
        for r in rs:
            mo, st = summ(window(r, MOTION)), summ(window(r, STATIC))
            r["mo"], r["st"] = mo, st
            f = lambda s, k, fmt: (fmt % s[k]) if s else "-"
            print("%-40s %s  %-9s %-13s %2s %5s %5s %4s | %2s %5s %4s %5s %5s %5s %4s %5s %5s %5s %4s" % (
                r["id"][:40], arm, r["flags"], r["apk"],
                f(mo, "n", "%d"), f(mo, "usd", "%.2f"), f(mo, "pmd", "%.2f"), f(mo, "gfps", "%.1f"),
                f(st, "n", "%d"), f(st, "usd", "%.2f"), f(st, "rowsd", "%.2f"), f(st, "pmd", "%.2f"),
                f(st, "shd", "%.2f"), f(st, "Draw", "%.2f"), f(st, "BE", "%.0f"), f(st, "gfps", "%.1f"),
                f(st, "Idle", "%.2f"), f(st, "Tot", "%.2f"), f(st, "Fin", "%.2f")))

    allr = RA + RB
    # V: validity, refuse rather than fail
    bad = []
    for r in allr:
        why = []
        if r["mark"] is None:
            why.append("no mark")
        if not r["route_done"]:
            why.append("route did not finish")
        if r["fatal"]:
            why.append("%d fatal lines" % r["fatal"])
        if (r.get("mo") or {}).get("n", 0) < e("V_min_motion_rows", 8):
            why.append("motion rows %s" % (r.get("mo") or {}).get("n", 0))
        if (r.get("st") or {}).get("n", 0) < e("V_min_static_rows", 15):
            why.append("static rows %s" % (r.get("st") or {}).get("n", 0))
        if r["mark"] is not None and any(r["mark"] - 60 <= p <= r["mark"] + STATIC[1] for p in r["pause"]):
            why.append("thermal pause in the windows")
        if why:
            bad.append("%s: %s" % (r["id"], ", ".join(why)))
    apks = set(r["apk"] for r in allr)
    if len(apks) != 1:
        bad.append("apks differ: %s" % sorted(map(str, apks)))
    leg("V", not bad and RA and RB, "; ".join(bad) or "every run marked, finished, no fatal, no thermal pause, rows in both windows, one apk %s" % apks.pop())

    leg("P0", all(r["flags"] == (0, 0, 0) for r in RA) and all(r["flags"] == (1, 1, 1) for r in RB),
        "A flags %s, B flags %s ([perdraw433] bulk ubercache fogcache)" % ([r["flags"] for r in RA], [r["flags"] for r in RB]))

    def arm(rs, w, k):
        v = [r[w][k] for r in rs if r.get(w)]
        return (sum(v) / len(v), max(v) - min(v)) if v else (float("nan"), float("nan"))

    (sa, spa), (sb, spb) = arm(RA, "st", "usd"), arm(RB, "st", "usd")
    (pa, _), (pb, _) = arm(RA, "st", "pmd"), arm(RB, "st", "pmd")
    (ma, mspa), (mb, mspb) = arm(RA, "mo", "usd"), arm(RB, "mo", "usd")
    (ga, _), (gb, _) = arm(RA, "st", "gfps"), arm(RB, "st", "gfps")
    (mga, _), (mgb, _) = arm(RA, "mo", "gfps"), arm(RB, "mo", "gfps")
    (ia, _), (ib, _) = arm(RA, "st", "Idle"), arm(RB, "st", "Idle")
    (ta, _), (tb, _) = arm(RA, "st", "Tot"), arm(RB, "st", "Tot")
    (da, _), (db, _) = arm(RA, "st", "Draw"), arm(RB, "st", "Draw")

    leg("P1", pb - pa <= e("P1_pm_per_draw_max", -0.8),
        "STATIC (Pipe+Mfp)/draw B-A %+.2f us (A %.2f, B %.2f); must be <= %+.2f: the saving lands where update_shader_uniforms is timed"
        % (pb - pa, pa, pb, e("P1_pm_per_draw_max", -0.8)))
    lo, hi = e("P2_us_per_draw_min", -3.0), e("P2_us_per_draw_max", -0.8)
    leg("P2", lo <= sb - sa <= hi,
        "STATIC Draw us/draw B-A %+.2f (A %.2f, B %.2f, %+.1f%%); Draw ms/frame B-A %+.2f; must be in [%+.1f, %+.1f]"
        % (sb - sa, sa, sb, 100 * (sb - sa) / sa if sa else 0, db - da, lo, hi))
    lo, hi = e("P3_motion_us_per_draw_min", -3.0), e("P3_motion_us_per_draw_max", -0.4)
    leg("P3", lo <= mb - ma <= hi,
        "MOTION Draw us/draw B-A %+.2f (A %.2f, B %.2f); must be in [%+.1f, %+.1f]" % (mb - ma, ma, mb, lo, hi))
    sep = max(spa if spa == spa else 0, spb if spb == spb else 0)
    leg("P4", abs(sb - sa) > e("P4_sep_over_spread", 3.0) * sep,
        "STATIC |B-A| %.2f us/draw against the larger within-arm run spread %.2f (x%.1f needed)"
        % (abs(sb - sa), sep, e("P4_sep_over_spread", 3.0)))
    tol = e("P5_static_gfps_tol", 0.5)
    leg("P5", abs(gb - ga) <= tol,
        "STATIC gfps B-A %+.2f (A %.2f, B %.2f): the scene sits at the 30 fps cap, so no gfps change is predicted (|d| <= %.1f); "
        "the renderer's Idle B-A %+.2f ms, Tot B-A %+.2f ms (where the saved time goes)" % (gb - ga, ga, gb, tol, ib - ia, tb - ta))
    leg("P6", mgb - mga >= e("P6_motion_gfps_min", -1.0),
        "MOTION gfps B-A %+.2f (A %.2f, B %.2f): no regression (>= %+.1f); a gain here is at most ~+1 and inside row noise"
        % (mgb - mga, mga, mgb, e("P6_motion_gfps_min", -1.0)))

    # X: pixels, regions not pixels
    fa = [frames(r, *FRAMES_STATIC_HOST) for r in RA]
    fb = [frames(r, *FRAMES_STATIC_HOST) for r in RB]
    nf = min(len(x) for x in fa + fb) if fa and fb else 0
    margin = e("X_margin", 8)
    fails, worst, floor_max = 0, 0, 0
    for i in range(nf):
        ra = [regions(x[i]) for x in fa]
        rb = [regions(x[i]) for x in fb]
        within = [dmax(p, q) for g in (ra, rb) for j, p in enumerate(g) for q in g[j + 1:]]
        cross = [dmax(p, q) for p in ra for q in rb]
        n = GRID[0] * GRID[1]
        fl = [max(w[k] for w in within) if within else 0 for k in range(n)]
        cr = [max(c[k] for c in cross) for k in range(n)]
        fails += sum(1 for k in range(n) if cr[k] > fl[k] + margin)
        worst = max(worst, max(cr))
        floor_max = max(floor_max, max(fl))
    leg("X", nf > 0 and fails <= e("X_max_failed_regions", 0),
        "%d STATIC frames x %d regions: %d regions B-vs-A above floor+%d; largest B-vs-A region d %d, largest within-arm floor %d"
        % (nf, GRID[0] * GRID[1], fails, margin, worst, floor_max))
    print("legs: %s" % " ".join("%s=%s" % (n, "PASS" if ok else "FAIL") for n, ok in legs))


main()
