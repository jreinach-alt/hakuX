#!/usr/bin/env python3
"""lane.texscan1010's arm reader: NFS Most Wanted on route nfs-mw-quickrace, HAKUX_TEXSCAN=1 (on) against
no env (off), one build, read over the first seconds after each GO.

    texread.py RUN [RUN ...] [--expect PRED.json] [--window LO,HI] [--bins B1,B2,...]

Each run is one fixed state. The state comes from request.json's `env`, and the build must agree: an on
run logs `[texscan] on` once, an off run never does. Runs, go marks, phase rows (draws/frame, gfps)
and the matched-work machinery are startread.py's (this directory), which takes them from
perdraw1009's togread.py/armread.py.

A 60-frame line belongs to a start when its window [previous line, this line] lies inside
[mark + LO, mark + HI] (default 1.5, 12.0: GO + 0 .. GO + 10.5, as startread.py). Read per state:

  range     `[sdcall] frames=60 range=fin../dl../<ms>ms`: the range scan's synchronous wait, ms per frame
  sdl+scan  `txw[...] sdl<ms> scan<ms>` (perflog): create_texture()'s two download sites, ms per frame
  period    `hakuX-pace f=.. v0..v4 vb ms=`: wall ms per guest frame over the pooled lines (sum ms / sum f)
  vN        share of frames that took N vblanks (v4 is 4 or more); 30 fps is every frame at v2
  gfps      startread.py's phase rows (perflog `hakuX-phase`, ~2 s each), pooled and matched-work: each
            draws/frame bin's on-off weighted by its row count in both states
  ts[...]   the route's own counters in `[tsc] f60` (cp = faces copied, fb = refusals that downloaded)

Queue the arms on, off, off, on (or off, on, on, off): the second arm of a pair inherits the first's
shader cache, so neither state is always the warm one.
"""
import json, os, re, statistics, sys

_here = os.path.dirname(os.path.abspath(__file__))
_src = open(os.path.join(_here, "startread.py")).read().rsplit("\nmain()", 1)[0]
S_ = {"__name__": "startread", "__file__": os.path.join(_here, "startread.py")}
exec(compile(_src, S_["__file__"], "exec"), S_)
read_run, rdir, sec = S_["read_run"], S_["rdir"], S_["sec"]
go_marks, start_rows, summ, matched = S_["go_marks"], S_["start_rows"], S_["summ"], S_["matched"]
binof, binname, WINDOW, BINS = S_["binof"], S_["binname"], S_["WINDOW"], S_["BINS"]


def state_of(run):
    """(state from request.json env, state from the build's log line): 1 on, 0 off, None unknown."""
    req = None
    try:
        env = json.load(open(os.path.join(run["dir"], "request.json"))).get("env") or []
        if isinstance(env, dict):
            env = ["%s=%s" % kv for kv in env.items()]
        req = 1 if "HAKUX_TEXSCAN=1" in env else 0
    except (OSError, ValueError):
        pass
    log = 0
    for ln in open(os.path.join(run["dir"], "logcat.txt"), errors="replace"):
        if "[texscan] on" in ln:
            log = 1
            break
    return req, log


def in_start(run, prev, t, window):
    return prev is not None and any(g + window[0] <= prev and t <= g + window[1] for _, g in run["go"])


def windows(run, window):
    """the 60-frame lines inside a start, by kind."""
    out = dict(pace=[], sdc=[], txw=[], tsc=[])
    prev = dict(pace=None, sdc=None, txw=None, tsc=None)
    pid = run["pid"]
    for ln in open(os.path.join(run["dir"], "logcat.txt"), errors="replace"):
        if pid is not None and "(%s)" % pid not in ln.replace("( ", "("):
            continue
        if "hakuX-pace" in ln and " f=" in ln:
            k = "pace"
        elif "[sdcall] frames=" in ln:
            k = "sdc"
        elif "txw[f" in ln:
            k = "txw"
        elif "[tsc] f60" in ln:
            k = "tsc"
        else:
            continue
        t = sec(ln[6:18])
        if in_start(run, prev[k], t, window):
            out[k].append(ln)
        prev[k] = t
    return out


def pace(lines):
    v = [0] * 5
    ms = vb = 0.0
    for ln in lines:
        d = dict(re.findall(r"\b(v\d|vb|ms)=([0-9.]+)", ln))
        for i in range(5):
            v[i] += int(d.get("v%d" % i, 0))
        ms += float(d.get("ms", 0))
        vb += float(d.get("vb", 0))
    f = sum(v)
    if not f:
        return None
    return dict(lines=len(lines), frames=f, period=ms / f, fps=1000.0 * f / ms,
                share=[x / f for x in v], vbpf=vb / f)


def sdcall(lines):
    per = []
    for ln in lines:
        m = re.search(r"frames=(\d+) range=fin(\d+)/fence\d+/pre\d+/dl(\d+)/([0-9.]+)ms", ln)
        if m:
            per.append((float(m.group(4)) / int(m.group(1)), int(m.group(2)), int(m.group(3))))
    if not per:
        return None
    ms = [p[0] for p in per]
    return dict(n=len(per), mean=statistics.mean(ms), med=statistics.median(ms), max=max(ms),
                fin=sum(p[1] for p in per) / len(per), dl=sum(p[2] for p in per) / len(per))


def txw(lines):
    g = lambda k, s: float(re.search(k + r"([0-9.]+)/", s).group(1))
    rows = [(g(" ct", ln), g(" sdl", ln), g(" scan", ln)) for ln in lines if " sdl" in ln]
    if not rows:
        return None
    return dict(n=len(rows), ct=statistics.mean(r[0] for r in rows), sdl=statistics.mean(r[1] for r in rows),
                scan=statistics.mean(r[2] for r in rows))


def tsc(lines):
    tot = dict(dl=0, sdl=0, bind=0, cp=0, keep=0, force=0, faf=0, cmpl=0, fb=0)
    for ln in lines:
        for k in ("dl", "sdl"):
            m = re.search(r"\b%s(\d+)\b" % k, ln)
            if m:
                tot[k] += int(m.group(1))
        m = re.search(r"ts\[bind(\d+) cp(\d+) keep(\d+) force(\d+) faf(\d+) cmpl(\d+) fb(\d+)\]", ln)
        if m:
            for k, x in zip(("bind", "cp", "keep", "force", "faf", "cmpl", "fb"), m.groups()):
                tot[k] += int(x)
    tot["n"] = len(lines)
    return tot


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
        r["req"], r["log"] = state_of(r)
        r["arm"] = r["req"] if r["req"] is not None else r["log"]
        r["flips"] = [(0.0, r["arm"])]
        r["go"] = go_marks(r)
        r["srows"] = start_rows(r, window)
        r["w"] = windows(r, window)

    legs = []

    def leg(name, ok, text):
        legs.append((name, ok))
        print("%-3s %s  %s" % (name, "PASS" if ok else "FAIL", text))

    print("run                                      state starts route fatal rows pace sdcall apk")
    for r in R:
        print("%-40s %-5s %6d %5s %5d %4d %4d %6d %s" % (
            r["id"][:40], {1: "on", 0: "off"}.get(r["arm"], "?"), len(r["go"]), r["route_done"], r["fatal"],
            len(r["srows"]), len(r["w"]["pace"]), len(r["w"]["sdc"]), r["apk"]))

    bad = []
    for r in R:
        why = []
        if len(r["go"]) < e("V_min_starts", 12):
            why.append("%d go marks" % len(r["go"]))
        if not r["route_done"]:
            why.append("route did not finish")
        if r["fatal"]:
            why.append("%d fatal lines" % r["fatal"])
        if r["req"] is not None and r["req"] != r["log"]:
            why.append("request env says %s, build logged %s" % (r["req"], r["log"]))
        if r["go"] and any(r["go"][0][1] - 60 <= p <= r["go"][-1][1] + window[1] for p in r["pause"]):
            why.append("thermal pause across the starts")
        t = tsc(r["w"]["tsc"])
        if r["arm"] == 1 and not t["cp"]:
            why.append("on, but the route copied no face in the starts")
        if r["arm"] == 0 and (t["cp"] or t["bind"]):
            why.append("off, but the route ran")
        if why:
            bad.append("%s: %s" % (r["id"], ", ".join(why)))
    apks = set(r["apk"] for r in R)
    if len(apks) != 1:
        bad.append("apks differ: %s" % sorted(map(str, apks)))
    if set(r["arm"] for r in R) != {0, 1}:
        bad.append("both states needed, got %s" % sorted(map(str, set(r["arm"] for r in R))))
    leg("V", not bad, "; ".join(bad) or "every run has its starts, finished its route, no fatal, no thermal pause, "
        "env and build agree, the route copied faces only when on, one apk %s" % next(iter(apks)))

    print("\nMARK + %.1f .. MARK + %.1f s (GO is ~1.5 s after the mark), pooled over %d runs, %d starts" % (
        window[0], window[1], len(R), sum(len(r["go"]) for r in R)))
    P, D, X, T = {}, {}, {}, {}
    for p, name in ((0, "off"), (1, "on")):
        rs = [r for r in R if r["arm"] == p]
        P[p] = pace([ln for r in rs for ln in r["w"]["pace"]])
        D[p] = sdcall([ln for r in rs for ln in r["w"]["sdc"]])
        X[p] = txw([ln for r in rs for ln in r["w"]["txw"]])
        T[p] = tsc([ln for r in rs for ln in r["w"]["tsc"]])
        if P[p]:
            print("%-4s pace  lines %3d frames %5d  period %5.1f ms (%4.1f fps)  v1 %4.1f%%  v2 %4.1f%%  v3 %4.1f%%  "
                  "v4+ %4.1f%%  vblanks/frame %.2f" % (
                      name, P[p]["lines"], P[p]["frames"], P[p]["period"], P[p]["fps"], 100 * P[p]["share"][1],
                      100 * P[p]["share"][2], 100 * P[p]["share"][3], 100 * P[p]["share"][4], P[p]["vbpf"]))
        if D[p]:
            print("%-4s range lines %3d  %.2f ms/frame (median %.2f, max %.2f)  fin %.1f dl %.1f per 60 frames" % (
                name, D[p]["n"], D[p]["mean"], D[p]["med"], D[p]["max"], D[p]["fin"], D[p]["dl"]))
        else:
            print("%-4s range none in the starts" % name)
        if X[p]:
            print("%-4s txw   lines %3d  ct %.2f  sdl %.2f  scan %.2f ms/frame" % (
                name, X[p]["n"], X[p]["ct"], X[p]["sdl"], X[p]["scan"]))
        n = max(T[p]["n"], 1)
        print("%-4s tsc   lines %3d  dl %.1f sdl %.1f | bind %.1f cp %.1f keep %.1f force %.1f faf %.1f cmpl %.1f "
              "fb %.1f per 60 frames" % (name, T[p]["n"], T[p]["dl"] / n, T[p]["sdl"] / n, T[p]["bind"] / n,
                                         T[p]["cp"] / n, T[p]["keep"] / n, T[p]["force"] / n, T[p]["faf"] / n,
                                         T[p]["cmpl"] / n, T[p]["fb"] / n))

    print("\nphase rows: state bin  n  gfps (min-max)  frame_ms  us/draw  draws/f  Tot_ms")
    pooled = [(p, row) for r in R for _, p, row in r["srows"]]
    by_bin = {}
    for i in range(len(bins) + 1):
        by_bin[i] = ([row for p, row in pooled if p == 0 and binof(row["BE"], bins) == i],
                     [row for p, row in pooled if p == 1 and binof(row["BE"], bins) == i])
    st = {p: summ([row for pp, row in pooled if pp == p]) for p in (0, 1)}
    for p, name in ((0, "off"), (1, "on")):
        for i in range(len(bins) + 1):
            s = summ(by_bin[i][p])
            if s:
                print("  %-4s %-10s %3d  %5.1f (%2d-%2d)  %8.1f  %7.2f  %7.0f  %6.1f" % (
                    name, binname(i, bins), s["n"], s["gfps"], s["gmin"], s["gmax"], s["fms"], s["usd"], s["BE"],
                    s["Tot"]))
        s = st[p]
        if s:
            print("  %-4s %-10s %3d  %5.1f (%2d-%2d)  %8.1f  %7.2f  %7.0f  %6.1f" % (
                name, "ALL", s["n"], s["gfps"], s["gmin"], s["gmax"], s["fms"], s["usd"], s["BE"], s["Tot"]))
    print("\nper run, over that run's starts")
    for r in R:
        pr, dr = pace(r["w"]["pace"]), sdcall(r["w"]["sdc"])
        s = summ([row for _, _, row in r["srows"]])
        print("  %-40s %-3s period %5.1f  v2 %4.1f%% v3 %4.1f%% v4+ %4.1f%%  range %5.2f  gfps %5.1f  draws/f %4.0f" % (
            r["id"][:40], "on" if r["arm"] else "off", pr["period"] if pr else float("nan"),
            100 * pr["share"][2] if pr else float("nan"), 100 * pr["share"][3] if pr else float("nan"),
            100 * pr["share"][4] if pr else float("nan"), dr["mean"] if dr else 0.0,
            s["gfps"] if s else float("nan"), s["BE"] if s else float("nan")))

    mg, nused = matched(by_bin, "gfps")
    mf, _ = matched(by_bin, "fms")
    print("\nmatched-work (bin-weighted) on-off: gfps %+.2f, frame_ms %+.1f over %d rows" % (mg, mf, nused))

    ok = P[0] and P[1]
    ron = D[1]["mean"] if D[1] else 0.0
    roff = D[0]["mean"] if D[0] else 0.0
    leg("R", ok and ron <= e("R_on_max", 0.5) and roff >= e("R_off_min", 2.0),
        "range ms/frame on %.2f (predicted <= %.2f), off %.2f (predicted >= %.2f)" % (
            ron, e("R_on_max", 0.5), roff, e("R_off_min", 2.0)))
    dp = (P[1]["period"] - P[0]["period"]) if ok else float("nan")
    leg("P", ok and e("P_dperiod_min", -99.0) <= dp <= e("P_dperiod_max", 0.0),
        "period on-off %+.1f ms (off %.1f, on %.1f), predicted in [%+.1f, %+.1f]" % (
            dp, P[0]["period"] if P[0] else float("nan"), P[1]["period"] if P[1] else float("nan"),
            e("P_dperiod_min", -99.0), e("P_dperiod_max", 0.0)))
    slow = lambda q: q["share"][3] + q["share"][4]
    dh = 100 * (slow(P[1]) - slow(P[0])) if ok else float("nan")
    d2 = 100 * (P[1]["share"][2] - P[0]["share"][2]) if ok else float("nan")
    leg("H", ok and dh <= e("H_dslow_max", 0.0) and d2 >= e("H_dv2_min", 0.0),
        "v3+v4 share on-off %+.1f points (predicted <= %+.1f), v2 share on-off %+.1f points (predicted >= %+.1f)" % (
            dh, e("H_dslow_max", 0.0), d2, e("H_dv2_min", 0.0)))
    leg("F", st[0] and st[1] and e("F_gfps_min", 0.0) <= mg <= e("F_gfps_max", 99.0),
        "matched-work gfps on-off %+.2f over %d rows, predicted in [%+.1f, %+.1f]" % (
            mg, nused, e("F_gfps_min", 0.0), e("F_gfps_max", 99.0)))
    min_n = e("V_min_pace_lines", 30)
    leg("N", ok and P[0]["lines"] >= min_n and P[1]["lines"] >= min_n,
        "pace lines per state >= %d (off %d, on %d)" % (min_n, P[0]["lines"] if P[0] else 0,
                                                       P[1]["lines"] if P[1] else 0))
    print("legs: %s" % " ".join("%s=%s" % (nm, "PASS" if ok_ else "FAIL") for nm, ok_ in legs))


main()
