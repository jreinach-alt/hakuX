#!/usr/bin/env python3
"""lane.perdrawon1010's race-start reader: NFS Most Wanted on route nfs-mw-quickrace with
HAKUX_UNI_TOGGLE=<s>, read over the first seconds after each GO.

    startread.py RUN [RUN ...] [--expect PRED.json] [--window LO,HI] [--bins B1,B2,...]

The route starts a Quick Race, writes `mark gameplay` at the first GO and `mark go<N>` at each
later one, holds RT for the start, then restarts the race from the STANDINGS menu and does it
again, so one boot yields several race starts. The scene the owner asked about (10-10: "the FPS drops are in the first few seconds
of the race when other cars are on scene") is the first 10 s after GO.

Rows, the toggle flip log and the pure-row rule come from perdraw1009's togread.py/armread.py
(loaded at PERDRAW1009_REF with `git show`, as motionread.py does). A perflog row's time is the
END of its ~2-s window, so a row belongs to a start when its window [prev, t] lies inside
[go + LO, go + HI] (default LO=-0.5, HI=10.5: the first 10 s, half a second of slack either
side for the host-written mark landing a little off the GO banner). A row is pure when no flip
falls inside (prev, t]; its phase is the phase at prev.

Draws/frame climbs and falls through a start as the pack spreads, and with a toggle the two
states sample different moments of it, so every headline is also given per draws/frame bin and
as a bin-weighted (matched-work) difference: each bin's on-off weighted by its row count in
both states. Frame ms is wall time per guest frame over the pooled rows (1000 * rows / sum of
gfps, each row ~2 s), so a slow row counts by its frames, not as one vote.
"""
import os, statistics, subprocess, sys, tempfile, json, re

PERDRAW1009_REF = os.environ.get("PERDRAW1009_REF", "4ad1154e5528eb51455f8de1a597575a543216fb")


def git_show(ref, path):
    return subprocess.run(["git", "show", "%s:%s" % (ref, path)], cwd=os.path.dirname(os.path.abspath(__file__)),
                          capture_output=True, check=True, text=True).stdout


_tmp = tempfile.mkdtemp(prefix="startread-")
for _f in ("togread.py", "armread.py"):
    open(os.path.join(_tmp, _f), "w").write(git_show(PERDRAW1009_REF, "docs/lanes/perdraw1009/" + _f))
togread_py = os.path.join(_tmp, "togread.py")
src = open(togread_py).read().rsplit("\nmain()", 1)[0]
T_ = {"__name__": "togread", "__file__": togread_py}
exec(compile(src, togread_py, "exec"), T_)
read_run, read_toggle, phase_at, flips_in = T_["read_run"], T_["read_toggle"], T_["phase_at"], T_["flips_in"]
rdir, sec = T_["rdir"], T_["sec"]

WINDOW = (-0.5, 10.5)
BINS = (1100, 1400, 1700)


def go_marks(run):
    """device times of `hakuX-route: mark gameplay` (the first GO, labelled go1) and `mark go<N>`, in order."""
    out = []
    for ln in open(os.path.join(run["dir"], "logcat.txt"), errors="replace"):
        m = re.search(r"hakuX-route.*mark (gameplay|go\d+)\b", ln)
        if m:
            out.append(("go1" if m.group(1) == "gameplay" else m.group(1), sec(ln[6:18])))
    return out


def start_rows(run, window=WINDOW):
    """(go label, phase, row) for every pure row inside a start's window."""
    out, prev = [], None
    for r in run["rows"]:
        t = r["t"]
        if prev is not None and r.get("BE") and r.get("Draw") is not None and r.get("gfps"):
            for lab, g in run["go"]:
                if g + window[0] <= prev and t <= g + window[1] and not flips_in(run, prev, t):
                    p = phase_at(run, prev)
                    if p is not None:
                        out.append((lab, p, r))
        prev = t
    return out


def binof(be, bins):
    for i, b in enumerate(bins):
        if be < b:
            return i
    return len(bins)


def binname(i, bins):
    lo = bins[i - 1] if i > 0 else 0
    return ("<%d" % bins[0]) if i == 0 else ("%d+" % bins[-1]) if i == len(bins) else ("%d-%d" % (lo, bins[i]))


def summ(rows):
    if not rows:
        return None
    n = len(rows)
    be = sum(r["BE"] for r in rows)
    fr = sum(r["gfps"] for r in rows)
    m = lambda k: sum(r.get(k) or 0 for r in rows) / n
    g = [r["gfps"] for r in rows]
    return dict(n=n, gfps=fr / n, fms=1000.0 * n / fr, usd=1000 * sum(r["Draw"] for r in rows) / be,
                BE=be / n, Tot=m("Tot"), Idle=m("Idle"), Draw=m("Draw"), Fin=m("Fin"),
                gse=(statistics.pstdev(g) / n ** 0.5) if n > 1 else float("nan"),
                gmin=min(g), gmax=max(g))


def matched(rows_by_bin, key):
    """bin-weighted on-off of key over bins holding rows in both states; (diff, rows used)."""
    num = den = 0.0
    for b, (off, on) in rows_by_bin.items():
        so, sn = summ(off), summ(on)
        if so and sn:
            w = len(off) + len(on)
            num += w * (sn[key] - so[key])
            den += w
    return (num / den if den else float("nan")), int(den)


def main():
    a = sys.argv[1:]
    runs, exp, window, bins = [], {}, WINDOW, BINS
    while a:
        k = a.pop(0)
        if k == "--expect":
            exp = json.load(open(a.pop(0))).get("expect", {})
        elif k == "--window":
            window = tuple(float(x) for x in a.pop(0).split(","))
        elif k == "--bins":
            bins = tuple(int(x) for x in a.pop(0).split(","))
        else:
            runs.append(rdir(k))
    if not runs:
        sys.exit(__doc__.strip().splitlines()[2])
    e = lambda k, d: exp.get(k, d)
    R = [read_run(d) for d in runs]
    for r in R:
        read_toggle(r)
        r["go"] = go_marks(r)
        r["srows"] = start_rows(r, window)

    legs = []

    def leg(name, ok, text):
        legs.append((name, ok))
        print("%-3s %s  %s" % (name, "PASS" if ok else "FAIL", text))

    print("run                                      starts flips toggle_ms route fatal rows(off/on) apk")
    for r in R:
        n0 = sum(1 for _, p, _ in r["srows"] if p == 0)
        n1 = sum(1 for _, p, _ in r["srows"] if p == 1)
        print("%-40s %6d %5d %9s %5s %5d %5d/%-5d %s" % (
            r["id"][:40], len(r["go"]), len(r["flips"]), r["toggle_ms"], r["route_done"], r["fatal"], n0, n1, r["apk"]))

    bad = []
    for r in R:
        why = []
        if len(r["go"]) < e("V_min_starts", 2):
            why.append("%d go marks" % len(r["go"]))
        if r["fatal"]:
            why.append("%d fatal lines" % r["fatal"])
        if r["toggle_ms"] != e("V_toggle_ms", 4000):
            why.append("toggle_ms %s" % r["toggle_ms"])
        if r["go"] and any(r["go"][0][1] - 60 <= p <= r["go"][-1][1] + window[1] for p in r["pause"]):
            why.append("thermal pause across the starts")
        if why:
            bad.append("%s: %s" % (r["id"], ", ".join(why)))
    apks = set(r["apk"] for r in R)
    if len(apks) != 1:
        bad.append("apks differ: %s" % sorted(map(str, apks)))
    leg("V", not bad, "; ".join(bad) or "every run has its starts, no fatal, no thermal pause, toggling, one apk %s"
        % next(iter(apks)))

    pooled = [(p, row) for r in R for _, p, row in r["srows"]]
    st = {p: summ([row for pp, row in pooled if pp == p]) for p in (0, 1)}
    print("\nFIRST %.1f..%.1f s AFTER GO, pooled over %d runs, %d starts" % (
        window[0], window[1], len(R), sum(len(r["go"]) for r in R)))
    print("state bin         n  gfps (min-max)  frame_ms  us/draw  draws/f  Tot_ms  Idle_ms")
    by_bin = {}
    for i in range(len(bins) + 1):
        by_bin[i] = ([row for p, row in pooled if p == 0 and binof(row["BE"], bins) == i],
                     [row for p, row in pooled if p == 1 and binof(row["BE"], bins) == i])
    for p, name in ((0, "off"), (1, "on")):
        for i in range(len(bins) + 1):
            s = summ(by_bin[i][p])
            if s:
                print("%-5s %-10s %3d  %5.1f (%2d-%2d)  %8.1f  %7.2f  %7.0f  %6.1f  %7.1f" % (
                    name, binname(i, bins), s["n"], s["gfps"], s["gmin"], s["gmax"], s["fms"], s["usd"], s["BE"],
                    s["Tot"], s["Idle"]))
        s = st[p]
        if s:
            print("%-5s %-10s %3d  %5.1f (%2d-%2d)  %8.1f  %7.2f  %7.0f  %6.1f  %7.1f" % (
                name, "ALL", s["n"], s["gfps"], s["gmin"], s["gmax"], s["fms"], s["usd"], s["BE"], s["Tot"], s["Idle"]))

    print("\nper run, on-off over that run's start rows (the run-to-run band)")
    for r in R:
        o = summ([row for _, p, row in r["srows"] if p == 0])
        n = summ([row for _, p, row in r["srows"] if p == 1])
        if o and n:
            print("  %-40s gfps %+5.2f  frame_ms %+6.1f  us/draw %+5.2f  draws/f off %4.0f on %4.0f  (n %d/%d)" % (
                r["id"][:40], n["gfps"] - o["gfps"], n["fms"] - o["fms"], n["usd"] - o["usd"], o["BE"], n["BE"],
                o["n"], n["n"]))
        else:
            print("  %-40s one state missing" % r["id"][:40])

    off, on = st[0], st[1]
    ok = off and on
    mg, nused = matched(by_bin, "gfps")
    mf, _ = matched(by_bin, "fms")
    mu, _ = matched(by_bin, "usd")
    print("\nmatched-work (bin-weighted) on-off: gfps %+.2f, frame_ms %+.1f, us/draw %+.2f over %d rows" % (
        mg, mf, mu, nused))

    lo, hi = e("S1_us_per_draw_min", -4.0), e("S1_us_per_draw_max", 0.0)
    leg("S1", ok and lo <= mu <= hi, "matched-work us/draw on-off %+.2f, must be in [%+.1f, %+.1f]" % (mu, lo, hi))
    tol = e("S2_gfps_min", 0.0)
    leg("S2", ok and mg >= tol, "matched-work gfps on-off %+.2f, must be >= %+.1f (off %.1f n=%d, on %.1f n=%d)" % (
        mg, tol, off["gfps"] if off else float("nan"), off["n"] if off else 0, on["gfps"] if on else float("nan"),
        on["n"] if on else 0))
    min_n = e("S3_min_rows_per_state", 10)
    leg("S3", ok and off["n"] >= min_n and on["n"] >= min_n,
        "rows per state >= %d (off %d, on %d)" % (min_n, off["n"] if off else 0, on["n"] if on else 0))
    print("legs: %s" % " ".join("%s=%s" % (nm, "PASS" if ok_ else "FAIL") for nm, ok_ in legs))


main()
