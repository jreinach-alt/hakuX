#!/usr/bin/env python3
"""lane.perdrawon1010's MOTION-window reader: NFS Most Wanted on route nfs-mw with
HAKUX_UNI_TOGGLE=<s>, read over the 0-24 s RT-held window instead of togread.py's
parked STATIC window.

    motionread.py RUN [RUN ...] [--expect PRED.json] [--sheet OUT.png]

Why a new file, not an edit to togread.py: togread.py is perdraw1009's (out of this
lane's territory) and is hardcoded to STATIC = (30,120], the parked-against-a-wall
scene. perdraw1009's own armread.py already has a MOTION = (0,24] window and its
separate-arm run showed it is NOT a fixed scene: draws/frame there ranges 350 (just
after the mark, light) to ~1025 (seconds before the wall, heavy) as the car
accelerates away from a standing start (NOTES.md section 4, section 9 pair 2: 801-855
draws/frame, gfps 26.4->28.4, below the 30 fps cap -- the only place in either lane's
data where gfps moved at all). That ramp means a plain on-minus-off over the whole
window conflates the switches' effect with WHEN in the ramp each phase happened to
sample, which is why this reader bins pure rows by draws/frame (BE) as well as by
phase, instead of pooling the window flat the way togread.py's bins() does.

Rows, the mark, fatal lines, thermal pauses, the apk, the toggle flip log and the
pure-row rule (no flip inside a row's own 2-s interval) all come from togread.py's
and armread.py's own functions. perdraw1009 has not folded to master as of this
writing, so docs/lanes/perdraw1009/ does not exist in this worktree; PERDRAW1009_REF
(default below, the same build ref this lane's own runs use) is read with `git show
REF:path` and materialized into a temp dir so togread.py's own internal `open(...,
"armread.py")` beside it still resolves -- loaded at that ref, not copied into this
lane's history, and not re-fetched from a branch that may move before it folds.

MOTION = (0, 24] device seconds after the logcat mark, matching armread.py's own
constant (not reinvented). BE_SPLIT = 700: perdraw1009's single separate-arm sample
of this window ran 350-855 draws/frame in its lighter pair and 855-1025 in its
heavier one (NOTES.md section 9); 700 sits between the two pairs' overlap and is the
only split the brief's existing evidence supports before this lane's own rows are in
-- revisit it once pooled data is read if it puts fewer than a handful of rows on
either side.

A run this short (24 s of 2-s rows is at most 12 rows before any are dropped for
straddling a flip) cannot support the same per-run, per-state minimums togread.py
asks of its 90-s STATIC window; this reader pools PURE rows across every run given on
the command line before splitting by phase and bin, and reports n openly rather than
asserting a per-run floor.
"""
import os, statistics, subprocess, sys, tempfile, json

PERDRAW1009_REF = os.environ.get("PERDRAW1009_REF", "4ad1154e5528eb51455f8de1a597575a543216fb")


def git_show(ref, path):
    return subprocess.run(["git", "show", "%s:%s" % (ref, path)], cwd=os.path.dirname(os.path.abspath(__file__)),
                           capture_output=True, check=True, text=True).stdout


_tmp = tempfile.mkdtemp(prefix="motionread-")
for _f in ("togread.py", "armread.py"):
    open(os.path.join(_tmp, _f), "w").write(git_show(PERDRAW1009_REF, "docs/lanes/perdraw1009/" + _f))
togread_py = os.path.join(_tmp, "togread.py")
src = open(togread_py).read().rsplit("\nmain()", 1)[0]
T_ = {"__name__": "togread", "__file__": togread_py}
exec(compile(src, togread_py, "exec"), T_)
read_run, read_toggle, phase_at, flips_in = T_["read_run"], T_["read_toggle"], T_["phase_at"], T_["flips_in"]
rdir, regions, dmax, summ = T_["rdir"], T_["regions"], T_["dmax"], T_["summ"]

MOTION = (0.0, 24.0)
BE_SPLIT = 700


def pure_rows(run, window):
    out, prev = [], None
    for r in run["rows"]:
        t = r["t"]
        if prev is not None and r.get("BE") and r.get("Draw") is not None and run["mark"] is not None \
                and window[0] < t - run["mark"] <= window[1] and not flips_in(run, prev, t):
            p = phase_at(run, prev)
            if p is not None:
                out.append((p, r))
        prev = t
    return out


def bins_motion(runs, split=BE_SPLIT):
    """phase (0/1) x BE-bin ("lo"/"hi") -> pooled rows, across every run given."""
    out = {(p, b): [] for p in (0, 1) for b in ("lo", "hi")}
    for run in runs:
        for p, r in pure_rows(run, MOTION):
            out[(p, "hi" if r["BE"] >= split else "lo")].append(r)
    return out


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
        sys.exit("usage: motionread.py RUN [RUN ...] [--expect PRED.json] [--sheet OUT.png]")
    e = lambda k, d: exp.get(k, d)
    R = [read_run(d) for d in runs]
    for r in R:
        read_toggle(r)
    if out:
        T_["sheet"](R, out)

    legs = []

    def leg(name, ok, text):
        legs.append((name, ok))
        print("%-3s %s  %s" % (name, "PASS" if ok else "FAIL", text))

    print("run                                      flips toggle_ms route fatal apk")
    for r in R:
        print("%-40s %5d %9s %5s %5d %s" % (
            r["id"][:40], len([f for f in r["flips"] if r["mark"] and f[0] > r["mark"]]),
            r["toggle_ms"], r["route_done"], r["fatal"], r["apk"]))

    bad = []
    for r in R:
        why = []
        if r["mark"] is None:
            why.append("no mark")
        if not r["route_done"]:
            why.append("route did not finish")
        if r["fatal"]:
            why.append("%d fatal lines" % r["fatal"])
        if r["toggle_ms"] != e("V_toggle_ms", 4000):
            why.append("toggle_ms %s" % r["toggle_ms"])
        if r["mark"] is not None and any(r["mark"] - 60 <= p <= r["mark"] + MOTION[1] for p in r["pause"]):
            why.append("thermal pause in the window")
        if why:
            bad.append("%s: %s" % (r["id"], ", ".join(why)))
    apks = set(r["apk"] for r in R)
    if len(apks) != 1:
        bad.append("apks differ: %s" % sorted(map(str, apks)))
    leg("V", not bad, "; ".join(bad) or "every run marked, finished, no fatal, no thermal pause, toggling, one apk %s" % apks.pop())

    pooled = bins_motion(R)
    print("\nMOTION (0,24], pooled over %d runs, BE split at %d draws/frame" % (len(R), BE_SPLIT))
    print("phase bin    n us/d    se  gfps   BE   Tot  Idle")
    S = {}
    for p in (0, 1):
        for b in ("lo", "hi"):
            rows = pooled[(p, b)]
            s = summ(rows)
            S[(p, b)] = s
            if s:
                print("%5d %-4s %3d %5.2f %5.2f %5.1f %5.0f %5.2f %5.2f" % (
                    p, b, s["n"], s["usd"], s["se"], s["gfps"], s["BE"], s["Tot"], s["Idle"]))
            else:
                print("%5d %-4s   0" % (p, b))

    # all-MOTION pooled (no BE split), for the overall on-off headline
    flat = {p: summ([r for pp, r in [(p2, r2) for (p2, b2), rows in pooled.items() for r2 in rows] if pp == p])
            for p in (0, 1)}
    off, on = flat.get(0), flat.get(1)
    lo, hi = e("M1_us_per_draw_min", -3.0), e("M1_us_per_draw_max", 0.2)
    ok1 = off and on
    du = (on["usd"] - off["usd"]) if ok1 else float("nan")
    leg("M1", ok1 and lo <= du <= hi,
        "MOTION (all BE) Draw us/draw on-off %+.2f (off %.2f n=%s, on %.2f n=%s); must be in [%+.1f, %+.1f]"
        % (du, off["usd"] if off else float("nan"), off["n"] if off else 0,
           on["usd"] if on else float("nan"), on["n"] if on else 0, lo, hi))

    se = ((off["se"] ** 2 + on["se"] ** 2) ** 0.5) if ok1 and off["se"] == off["se"] and on["se"] == on["se"] else float("nan")
    k = e("M2_sep_over_se", 2.0)
    leg("M2", ok1 and se == se and abs(du) > k * se,
        "|on-off| %.2f us/draw against pooled-row SE %.2f (x%.1f needed)" % (abs(du), se, k))

    hi_off, hi_on = S.get((0, "hi")), S.get((1, "hi"))
    ok3 = hi_off and hi_on
    dhi = (hi_on["usd"] - hi_off["usd"]) if ok3 else float("nan")
    tol = e("M3_hi_gfps_min", -1.0)
    dg_hi = (hi_on["gfps"] - hi_off["gfps"]) if ok3 else float("nan")
    leg("M3", ok3 and dg_hi >= tol,
        "HI-BE bin (>= %d draws/frame) gfps on-off %+.2f (off %.1f n=%d, on %.1f n=%d), us/draw on-off %+.2f: no regression required (>= %+.1f); "
        "this bin is the closest this route reaches to the owner's profiled high-draw racing"
        % (BE_SPLIT, dg_hi, hi_off["gfps"] if hi_off else float("nan"), hi_off["n"] if hi_off else 0,
           hi_on["gfps"] if hi_on else float("nan"), hi_on["n"] if hi_on else 0, dhi, tol))

    min_n = e("M4_min_cell_n", 3)
    thin = [("%d/%s" % (p, b)) for (p, b), s in S.items() if not s or s["n"] < min_n]
    leg("M4", not thin, "every phase x BE-bin cell has >= %d pooled rows (thin: %s)" % (min_n, ", ".join(thin) or "none"))

    print("legs: %s" % " ".join("%s=%s" % (nm, "PASS" if ok_ else "FAIL") for nm, ok_ in legs))


main()
