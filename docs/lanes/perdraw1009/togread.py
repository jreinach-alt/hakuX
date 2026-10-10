#!/usr/bin/env python3
"""lane.perdraw1009's toggle reader: NFS Most Wanted on route nfs-mw with HAKUX_UNI_TOGGLE=<s>, the three
HAKUX_UNI_* switches flipping together, off and on, within ONE run.

    togread.py RUN [RUN ...] [--expect PRED.json] [--sheet OUT.png]

Why: separate runs of nfs-mw stop the car against different walls (A/B arms 1-1791614079, -071 and -081:
68% chevron, 65% plain wall, 66% billboard; 439, 438 and 801 draws/frame), so an arm-vs-arm comparison
compares scenes as well as switches. With the toggle, both states are measured on the same wall.

Rows, the mark, fatal lines, thermal pauses and the apk come from armread.py's own functions (loaded from
the file beside this one, not copied). The build logs `[perdraw433] phase=<0|1>` at every flip (the switch
is polled every 32 draws, i.e. within a few ms). A 2-s perf row is PURE when no flip falls between the
previous row's time and its own; only pure rows are counted, binned by the phase they lie in.

STATIC = (30, 120] device seconds after the logcat mark: the A/B arms' cars had stopped by +21..+31 s (frames),
and the route releases RT at ~+123 s. Per run and state: us/draw = sum Draw / sum BE * 1000 over pure rows,
pm/draw the same for Pipe + Mfp, sh/draw for Sh + Mfp; gfps, Idle, Tot means. The delta is on - off per run;
the verdict uses the mean over runs. SE of a run's delta = sqrt(se_on^2 + se_off^2), se = row sd / sqrt(n).

PIXELS (XT). The route shoots about every 5.6 s from +20 s. Each frame's device time is run.log's shot time
plus (logcat mark - run.log mark); frames within 1.5 s of a flip are dropped (that offset is good to a few
hundred ms), the rest are binned by phase. Each frame is cut into 16 x 12 regions of 80 x 80 px and the
region mean RGB taken; d = largest channel difference of two means. The parked scene still drifts (tyre
smoke, the car rocking, HUD digits: B2's frames 10 s apart differ by up to 32, 40 s apart by up to 66), so
only pairs at most X_pair_gap_max s apart are used, SAME-phase and CROSS-phase pairs alike, which keeps
their gaps matched. Per run and region: median same d and median cross d. A region counts UP when cross >
same + X_margin, DOWN when same > cross + X_margin. With no switch effect the two are exchangeable, so DOWN
is the control for how often the scene alone puts a region over the margin; a switch that changes shading
raises UP and lowers DOWN. Fail when UP - DOWN > X_excess_regions over all runs, or when a run has fewer
than X_min_pairs pairs of either kind. It sees a lasting shift of a few regions' colour by more than the
margin over their drift; it cannot see a shift smaller than the smoke's drift in the smoky regions, or a
change confined to a few small draws inside an 80 px region.
"""
import bisect, glob, json, os, re, statistics, sys

here = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(here, "armread.py")).read().rsplit("\nmain()", 1)[0]
A_ = {"__name__": "armread"}
exec(compile(src, os.path.join(here, "armread.py"), "exec"), A_)
read_run, rdir, sec, regions, dmax = A_["read_run"], A_["rdir"], A_["sec"], A_["regions"], A_["dmax"]

STATIC = (30.0, 120.0)
EDGE = 1.5
GRID = (16, 12)


def read_toggle(run):
    lines = open(os.path.join(run["dir"], "logcat.txt"), errors="replace").read().splitlines()
    run["flips"], run["toggle_ms"] = [], None
    for ln in lines:
        if run["pid"] is None or "(%s)" % run["pid"] not in ln.replace("( ", "("):
            continue
        m = re.search(r"\[perdraw433\] phase=(\d)", ln)
        if m:
            run["flips"].append((sec(ln[6:18]), int(m.group(1))))
        m = re.search(r"\[perdraw433\] .*toggle_ms=(\d+)", ln)
        if m:
            run["toggle_ms"] = int(m.group(1))
    run["shots"] = {}
    for ln in open(os.path.join(run["dir"], "run.log"), errors="replace"):
        m = re.match(r"ROUTE (\d\d:\d\d:\d\d\.\d+) shot \S+ -> (\S+\.png)", ln)
        if m:
            run["shots"][m.group(2)] = sec(m.group(1))


def phase_at(run, t):
    ts = [f[0] for f in run["flips"]]
    i = bisect.bisect_right(ts, t) - 1
    return run["flips"][i][1] if i >= 0 else None


def flips_in(run, lo, hi):
    return [f for f in run["flips"] if lo < f[0] <= hi]


def bins(run):
    out = {0: [], 1: []}
    prev = None
    for r in run["rows"]:
        t = r["t"]
        if prev is not None and r.get("BE") and r.get("Draw") is not None and run["mark"] is not None \
                and STATIC[0] < t - run["mark"] <= STATIC[1] and not flips_in(run, prev, t):
            p = phase_at(run, prev)
            if p is not None:
                out[p].append(r)
        prev = t
    return out


def summ(rows):
    if not rows:
        return None
    be = sum(r["BE"] for r in rows)
    s = lambda k: sum(r.get(k) or 0 for r in rows)
    per = [1000 * r["Draw"] / r["BE"] for r in rows]
    return dict(n=len(rows), usd=1000 * s("Draw") / be, pmd=1000 * (s("Pipe") + s("Mfp")) / be,
                shd=1000 * (s("Sh") + s("Mfp")) / be, BE=be / len(rows), Draw=s("Draw") / len(rows),
                gfps=s("gfps") / len(rows), Idle=s("Idle") / len(rows), Tot=s("Tot") / len(rows),
                se=(statistics.pstdev(per) / len(per) ** 0.5) if len(per) > 1 else float("nan"))


def frames(run):
    """(device time, phase, path) for the drive frames inside STATIC, flips +-EDGE excluded."""
    if run["mark"] is None or run["host_mark"] is None:
        return []
    off = run["mark"] - run["host_mark"]
    out = []
    for f in sorted(glob.glob(os.path.join(run["dir"], "route-frames", "*drive*.png"))):
        th = run["shots"].get(os.path.basename(f))
        if th is None:
            continue
        td = th + off
        if not (STATIC[0] < td - run["mark"] <= STATIC[1]):
            continue
        if any(abs(td - ft) < EDGE for ft, _ in run["flips"]):
            continue
        p = phase_at(run, td)
        if p is not None:
            out.append((td, p, f))
    return out


def sheet(runs, out):
    from PIL import Image
    rows = [frames(r) for r in runs]
    w = max((len(x) for x in rows), default=1)
    sh = Image.new("RGB", (240 * max(w, 1), 196 * max(len(rows), 1)))
    for i, fr in enumerate(rows):
        for j, (_, p, f) in enumerate(fr):
            im = Image.open(f).convert("RGB").resize((240, 180))
            sh.paste(im, (240 * j, 196 * i))
            sh.paste((0, 200, 0) if p else (200, 0, 0), (240 * j, 196 * i + 180, 240 * j + 240, 196 * i + 196))
    sh.save(out)
    print("sheet: %s (one row per run; bar green = switches on, red = off)" % out)


def main():
    a = sys.argv[1:]
    runs, exp, out = [], {}, None
    while a:
        k = a.pop(0)
        if k == "--expect":
            exp = json.load(open(a.pop(0))).get("expect", {})
        elif k == "--sheet":
            out = a.pop(0)
        else:
            runs.append(rdir(k))
    if not runs:
        sys.exit("usage: togread.py RUN [RUN ...] [--expect PRED.json] [--sheet OUT.png]")
    e = lambda k, d: exp.get(k, d)
    R = [read_run(d) for d in runs]
    for r in R:
        read_toggle(r)
    if out:
        sheet(R, out)
    legs = []

    def leg(name, ok, text):
        legs.append((name, ok))
        print("%-3s %s  %s" % (name, "PASS" if ok else "FAIL", text))

    print("run                                      state  n  us/d    se  pm/d  sh/d  Draw    BE  gfps  Idle   Tot")
    for r in R:
        b = bins(r)
        r["off"], r["on"] = summ(b[0]), summ(b[1])
        for st in ("off", "on"):
            s = r[st]
            if s:
                print("%-40s %-4s %3d %5.2f %5.2f %5.2f %5.2f %5.2f %5.0f %5.1f %5.2f %5.2f" % (
                    r["id"][:40], st, s["n"], s["usd"], s["se"], s["pmd"], s["shd"], s["Draw"], s["BE"], s["gfps"], s["Idle"], s["Tot"]))
            else:
                print("%-40s %-4s   0" % (r["id"][:40], st))
        print("%-40s flips %d after the mark, toggle_ms %s, flags line %s" % (
            "", len([f for f in r["flips"] if r["mark"] and f[0] > r["mark"]]), r["toggle_ms"], r["flags"]))

    bad = []
    for r in R:
        why = []
        if r["mark"] is None:
            why.append("no mark")
        if not r["route_done"]:
            why.append("route did not finish")
        if r["fatal"]:
            why.append("%d fatal lines" % r["fatal"])
        if r["toggle_ms"] != e("V_toggle_ms", 10000):
            why.append("toggle_ms %s" % r["toggle_ms"])
        for st in ("off", "on"):
            if (r[st] or {}).get("n", 0) < e("V_min_rows_per_state", 6):
                why.append("%s rows %d" % (st, (r[st] or {}).get("n", 0)))
        if r["off"] and r["on"] and abs(r["on"]["BE"] / r["off"]["BE"] - 1) > e("V_be_match", 0.10):
            why.append("draws/frame on %.0f vs off %.0f: not one scene" % (r["on"]["BE"], r["off"]["BE"]))
        if r["mark"] is not None and any(r["mark"] - 60 <= p <= r["mark"] + STATIC[1] for p in r["pause"]):
            why.append("thermal pause in the window")
        if why:
            bad.append("%s: %s" % (r["id"], ", ".join(why)))
    apks = set(r["apk"] for r in R)
    if len(apks) != 1:
        bad.append("apks differ: %s" % sorted(map(str, apks)))
    leg("V", not bad, "; ".join(bad) or "every run marked, finished, no fatal, no thermal pause, toggling, rows in both states, one scene per run, one apk %s" % apks.pop())

    ok = [r for r in R if r["off"] and r["on"]]
    mean = lambda v: sum(v) / len(v) if v else float("nan")
    d = lambda k: [r["on"][k] - r["off"][k] for r in ok]
    du, dp, dg = d("usd"), d("pmd"), d("gfps")
    ses = [(r["on"]["se"] ** 2 + r["off"]["se"] ** 2) ** 0.5 for r in ok]
    lo, hi = e("T1_us_per_draw_min", -3.0), e("T1_us_per_draw_max", -0.9)
    leg("T1", ok and lo <= mean(du) <= hi, "STATIC Draw us/draw on-off %+.2f (per run %s; off %.2f -> %+.1f%%); must be in [%+.1f, %+.1f]"
        % (mean(du), " ".join("%+.2f" % x for x in du), mean([r["off"]["usd"] for r in ok]),
           100 * mean(du) / mean([r["off"]["usd"] for r in ok]) if ok else 0, lo, hi))
    leg("T2", ok and mean(dp) <= e("T2_pm_per_draw_max", -0.9),
        "STATIC (Pipe+Mfp)/draw on-off %+.2f (per run %s); must be <= %+.2f" % (mean(dp), " ".join("%+.2f" % x for x in dp), e("T2_pm_per_draw_max", -0.9)))
    k = e("T3_sep_over_se", 4.0)
    se = (sum(s ** 2 for s in ses) ** 0.5 / len(ses)) if ses else float("nan")
    leg("T3", ok and abs(mean(du)) > k * se and len(set(x < 0 for x in du)) == 1,
        "|on-off| %.2f us/draw against the rows' SE %.2f (x%.1f needed), and one sign in every run (%s)"
        % (abs(mean(du)), se, k, " ".join("%+.2f" % x for x in du)))
    tol = e("T4_gfps_tol", 1.0)
    leg("T4", ok and abs(mean(dg)) <= tol, "STATIC gfps on-off %+.2f (per run %s): at or near the 30 fps cap no change is predicted (|d| <= %.1f); Idle on-off %+.2f ms"
        % (mean(dg), " ".join("%+.2f" % x for x in dg), tol, mean(d("Idle"))))

    margin, gap, npair = e("X_margin", 8), e("X_pair_gap_max", 7.0), e("X_min_pairs", 3)
    up, down, short, nfr, lines = 0, 0, False, 0, []
    n = GRID[0] * GRID[1]
    for r in R:
        fr = frames(r)
        nfr += len(fr)
        rg = [(t, p, regions(f)) for t, p, f in fr]
        near = [(a[1] == b[1], dmax(a[2], b[2])) for i, a in enumerate(rg) for b in rg[i + 1:] if b[0] - a[0] <= gap]
        same = [dd for sm, dd in near if sm]
        cross = [dd for sm, dd in near if not sm]
        if len(same) < npair or len(cross) < npair:
            lines.append("%s: %d frames, %d same-phase / %d cross pairs within %.0f s, fewer than %d" % (r["id"][-14:], len(fr), len(same), len(cross), gap, npair))
            short = True
            continue
        ms = [statistics.median(w[j] for w in same) for j in range(n)]
        mc = [statistics.median(c[j] for c in cross) for j in range(n)]
        hi_ = sorted(((mc[j] - ms[j], j) for j in range(n) if mc[j] > ms[j] + margin), reverse=True)
        lo_ = sum(1 for j in range(n) if ms[j] > mc[j] + margin)
        up, down = up + len(hi_), down + lo_
        lines.append("%s: %d frames, %d same / %d cross pairs, cross over same+%d in %d regions (worst %s), same over cross+%d in %d"
                     % (r["id"][-14:], len(fr), len(same), len(cross), margin, len(hi_),
                        " ".join("c%dr%d+%.0f" % (j % GRID[0], j // GRID[0], x) for x, j in hi_[:4]) or "-", margin, lo_))
    k = e("X_excess_regions", 8)
    leg("XT", not short and up - down <= k, "%d frames; %s; regions cross>same %d against the control same>cross %d (excess %d, at most %d)"
        % (nfr, "; ".join(lines), up, down, up - down, k))
    print("legs: %s" % " ".join("%s=%s" % (nm, "PASS" if ok_ else "FAIL") for nm, ok_ in legs))


main()
