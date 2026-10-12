#!/usr/bin/env python3
"""lane.perdraw1009's generalisation reader: Battlefield 2 MC on route bf2mc, HAKUX_UNI_* on (B) against
off (A), one build.

    genread.py --a A1 [A2 ...] --b B1 [B2 ...] [--expect PRED.json] [--sheet OUT.png]

Rows, flags, the mark, fatal lines, thermal pauses and the apk are read by armread.py's own functions
(loaded from the file beside this one, not copied), so both readers count a row the same way.

WINDOW. GAME = (0, 70] device seconds after the logcat `mark gameplay`: the route's repeat-forever
walk/turn/fire loop until the soak's 420 s cut (prior runs' last rows at +41..+63 s). The loop swings the
view between a heavy side (BE >= 1800, 14-19 fps) and a light side (BE < 1200, at the 30 fps cap), and
when each lands differs run to run, so:
  us/draw   = the MEDIAN over GAME rows of Draw*1000/BE per row (a mix-free per-draw cost; prior runs:
              heavy and light rows sit within ~0.5 us/draw of each other). The ratio of sums is printed.
  pm/draw   = (Pipe + Mfp) * 1000 / BE, ratio of sums over GAME rows.
  heavy     = GAME rows with BE >= 1800 (bf2stall433's convention): gfps, Idle, Fin there.

PIXELS. The two runs of one arm do not see the same view at the same second (prior pair: one run against
a fogged wall, the other in the square), so a region-by-region comparison would compare views, not
renderers. XB checks only gross breakage: each run's last three periodic frames (frames/, every 20 s;
the last three fall after the mark) have mean luma >= 12 and luma sd >= 8 (not black, not one flat
colour). --sheet puts every run's last four frames in a row, to read by eye. NFS's X leg
(armread.py, a fixed scene) is the pixel test of record; this one cannot see a shading change.
"""
import glob, json, os, statistics, sys

here = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(here, "armread.py")).read().rsplit("\nmain()", 1)[0]
A_ = {"__name__": "armread"}
exec(compile(src, os.path.join(here, "armread.py"), "exec"), A_)
read_run, rdir, summ = A_["read_run"], A_["rdir"], A_["summ"]

GAME = (0.0, 70.0)
HEAVY = 1800


def game_rows(run):
    if run["mark"] is None:
        return []
    return [r for r in run["rows"] if r.get("BE") and r.get("Draw") is not None
            and GAME[0] < r["t"] - run["mark"] <= GAME[1]]


def last_frames(run, n):
    return sorted(glob.glob(os.path.join(run["dir"], "frames", "f*.png")))[-n:]


def luma(path):
    from PIL import Image
    im = Image.open(path).convert("L").resize((160, 120), Image.BOX)
    px = list(im.tobytes())
    return statistics.mean(px), statistics.pstdev(px)


def sheet(runs, out):
    from PIL import Image
    sh = Image.new("RGB", (320 * 4, 240 * max(len(runs), 1)))
    for i, r in enumerate(runs):
        for j, f in enumerate(last_frames(r, 4)):
            sh.paste(Image.open(f).convert("RGB").resize((320, 240)), (320 * j, 240 * i))
    sh.save(out)
    print("sheet: %s (one row per run, in argument order: %s)" % (out, " ".join(r["id"] for r in runs)))


def main():
    a = sys.argv[1:]
    A, B, exp, out, tgt = [], [], {}, None, None
    while a:
        k = a.pop(0)
        if k == "--a":
            tgt = A
        elif k == "--b":
            tgt = B
        elif k == "--expect":
            exp, tgt = json.load(open(a.pop(0))).get("expect", {}), None
        elif k == "--sheet":
            out, tgt = a.pop(0), None
        elif tgt is not None:
            tgt.append(rdir(k))
        else:
            sys.exit("usage: genread.py --a A1 [A2 ...] --b B1 [B2 ...] [--expect PRED.json] [--sheet OUT.png]")
    e = lambda k, d: exp.get(k, d)
    RA = [read_run(d) for d in A]
    RB = [read_run(d) for d in B]
    if out:
        sheet(RA + RB, out)
    legs = []

    def leg(name, ok, text):
        legs.append((name, ok))
        print("%-3s %s  %s" % (name, "PASS" if ok else "FAIL", text))

    print("run                                      arm flags     apk            n  med us/d  se   ros us/d  pm/d | heavy n  gfps  Idle   Fin  Draw    BE")
    for arm, rs in (("A", RA), ("B", RB)):
        for r in rs:
            g = game_rows(r)
            per = [1000 * x["Draw"] / x["BE"] for x in g]
            r["n"] = len(g)
            r["med"] = statistics.median(per) if per else float("nan")
            r["se"] = 1.25 * statistics.pstdev(per) / len(per) ** 0.5 if len(per) > 1 else float("nan")
            r["all"] = summ(g)
            r["hv"] = summ([x for x in g if x["BE"] >= HEAVY])
            s, h = r["all"] or {}, r["hv"] or {}
            print("%-40s %s  %-9s %-13s %2d  %7.2f %5.2f  %7.2f %5.2f | %7s %5s %5s %5s %5s %5s" % (
                r["id"][:40], arm, r["flags"], r["apk"], r["n"], r["med"], r["se"],
                s.get("usd", float("nan")), s.get("pmd", float("nan")), h.get("n", 0),
                "%.1f" % h["gfps"] if h else "-", "%.1f" % h["Idle"] if h else "-",
                "%.1f" % h["Fin"] if h else "-", "%.1f" % h["Draw"] if h else "-", "%.0f" % h["BE"] if h else "-"))

    allr = RA + RB
    bad = []
    for r in allr:
        why = []
        if r["mark"] is None:
            why.append("no mark")
        if r["fatal"]:
            why.append("%d fatal lines" % r["fatal"])
        if r["n"] < e("V_min_rows", 15):
            why.append("GAME rows %d" % r["n"])
        if (r["hv"] or {}).get("n", 0) < e("V_min_heavy_rows", 4):
            why.append("heavy rows %d" % (r["hv"] or {}).get("n", 0))
        if r["mark"] is not None and any(r["mark"] - 60 <= p <= r["mark"] + GAME[1] for p in r["pause"]):
            why.append("thermal pause in the window")
        if why:
            bad.append("%s: %s" % (r["id"], ", ".join(why)))
    apks = set(r["apk"] for r in allr)
    if len(apks) != 1:
        bad.append("apks differ: %s" % sorted(map(str, apks)))
    leg("V", not bad and RA and RB, "; ".join(bad) or "every run marked, no fatal, no thermal pause, rows and heavy rows in GAME, one apk %s" % apks.pop())
    leg("P0", all(r["flags"] == (0, 0, 0) for r in RA) and all(r["flags"] == (1, 1, 1) for r in RB),
        "A flags %s, B flags %s ([perdraw433] bulk ubercache fogcache)" % ([r["flags"] for r in RA], [r["flags"] for r in RB]))

    mean = lambda v: sum(v) / len(v) if v else float("nan")
    ma, mb = mean([r["med"] for r in RA]), mean([r["med"] for r in RB])
    pa = mean([r["all"]["pmd"] for r in RA if r["all"]])
    pb = mean([r["all"]["pmd"] for r in RB if r["all"]])
    lo, hi = e("G1_us_per_draw_min", -3.0), e("G1_us_per_draw_max", -0.3)
    leg("G1", lo <= mb - ma <= hi, "GAME median us/draw B-A %+.2f (A %.2f, B %.2f, %+.1f%%); must be in [%+.1f, %+.1f]"
        % (mb - ma, ma, mb, 100 * (mb - ma) / ma if ma else 0, lo, hi))
    leg("G2", pb - pa <= e("G2_pm_per_draw_max", -0.3),
        "GAME (Pipe+Mfp)/draw B-A %+.2f (A %.2f, B %.2f); must be <= %+.2f" % (pb - pa, pa, pb, e("G2_pm_per_draw_max", -0.3)))
    spread = max([max(v) - min(v) for v in ([r["med"] for r in RA], [r["med"] for r in RB]) if len(v) > 1] or [0])
    se = (mean([r["se"] ** 2 for r in RA]) + mean([r["se"] ** 2 for r in RB])) ** 0.5
    k = e("G3_sep", 3.0)
    leg("G3", abs(mb - ma) > k * max(spread, se),
        "|B-A| %.2f us/draw against the larger of the within-arm run spread %.2f and the rows' SE of the difference %.2f (x%.1f needed)"
        % (abs(mb - ma), spread, se, k))
    hg = lambda rs, key: mean([r["hv"][key] for r in rs if r["hv"]])
    leg("G4", hg(RB, "gfps") - hg(RA, "gfps") >= e("G4_heavy_gfps_min", -1.0),
        "heavy-row gfps B-A %+.2f (A %.2f, B %.2f), no regression (>= %+.1f); heavy Draw B-A %+.2f ms, Idle B-A %+.2f ms, Fin B-A %+.2f ms"
        % (hg(RB, "gfps") - hg(RA, "gfps"), hg(RA, "gfps"), hg(RB, "gfps"), e("G4_heavy_gfps_min", -1.0),
           hg(RB, "Draw") - hg(RA, "Draw"), hg(RB, "Idle") - hg(RA, "Idle"), hg(RB, "Fin") - hg(RA, "Fin")))
    xs = []
    for r in allr:
        for f in last_frames(r, 3):
            m, s = luma(f)
            if m < 12 or s < 8:
                xs.append("%s/%s luma %.0f sd %.0f" % (r["id"][-12:], os.path.basename(f), m, s))
    nfr = sum(len(last_frames(r, 3)) for r in allr)
    leg("XB", nfr == 3 * len(allr) and not xs, "%d gameplay frames; %s" % (nfr, "; ".join(xs) or "none black or flat"))
    print("legs: %s" % " ".join("%s=%s" % (n, "PASS" if ok else "FAIL") for n, ok in legs))


main()
