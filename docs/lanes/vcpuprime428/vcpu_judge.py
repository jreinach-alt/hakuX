#!/usr/bin/env python3
"""Judge the HAKUX_PLACE_VCPU=prime A/B on a routed gameplay window (#428).

    vcpu_judge.py [--expect PRED.json] --a RESULT ... --b RESULT ...
    vcpu_judge.py --one RESULT ...          # describe runs, no verdict

A RESULT is a dispatch result id or directory. Everything is read from the
run's logcat, and only inside the GAMEPLAY WINDOW: from the route's
`mark gameplay` to `soak end` (hakuX-route). perfarch's place_judge dropped
the first quarter of the run, which on a route with a 90 s boot is still boot.

Per run it reports:
  - held: soak start -> soak end, against the request's seconds (validity:
    perfarch's arm was refused because harness exits cut runs short);
  - fps over the window: flips / wall time from hakuX-pace (60 flips a line),
    and the median and p10 of the per-window gfps;
  - the vCPU thread (named by the `perfarch place vcpu tid=` line, which both
    arms log when HAKUX_TOPO is set): its X3 (cpu7) share, core changes/s,
    busy % and runqueue wait, mean over the sampler's windows in the window;
  - the X3 policy clock (p7 mean and its cap) and the hottest CPU zone, in
    the first and last sampler window of the gameplay window, and the mean.

Exit 0 all legs PASS, 1 a leg FAILS, 3 a validity gate refused.
"""
import argparse
import datetime
import json
import os
import re
import statistics
import sys

D = os.environ.get("DISPATCH_DIR", "/home/justin/hakux-work/dispatch") + "/results/"
TS = re.compile(r"^(\d\d)-(\d\d) (\d\d):(\d\d):(\d\d)\.(\d{3})")
ROUTE = re.compile(r"hakuX-route.*?: (soak start|soak end|mark (\S+))")
PACE = re.compile(r"hakuX-pace.*?: f=(\d+) v0=(\d+) v1=(\d+) v2=(\d+) v3=(\d+) v4=(\d+) "
                  r"vb=(\d+) max=([\d.]+) ms=([\d.]+)")
GFPS = re.compile(r"gfps=(\d+) G:([\d.]+)")
PLACE = re.compile(r"perfarch place vcpu tid=(\d+) spec=(\S+)(?: mask=(0x[0-9a-f]+))? -> (.+)$")
TOPO = re.compile(r"perfarch topo tid=(\d+) comm=\S+ busy=([\d.]+)% mig/s=([\d.]+) "
                  r"rqwait_ms/s=([\d.]+) cpu%=([\d/]+)")
FREQ = re.compile(r"perfarch topo freq .*?\bp7=(\d+)\((\d+)-(\d+),cap(\d+)\)")
THERM = re.compile(r"perfarch topo thermal .*?cpu_max_mC=(-?\d+)")


def ts(line):
    m = TS.match(line)
    if not m:
        return None
    mo, d, h, mi, s, ms = (int(x) for x in m.groups())
    return datetime.datetime(2026, mo, d, h, mi, s, ms * 1000).timestamp()


def path_of(r):
    return r if os.path.isdir(r) else D + r


def med(xs):
    return statistics.median(xs) if xs else None


def mean(xs):
    return statistics.mean(xs) if xs else None


def pct(xs, q):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(round(q / 100.0 * (len(xs) - 1))))] if xs else None


def read(r):
    p = path_of(r)
    req = json.load(open(os.path.join(p, "request.json")))
    try:
        res = json.load(open(os.path.join(p, "result.json")))
    except (OSError, ValueError):
        res = {}
    marks, pace, gfps, topo, freq, therm = {}, [], [], [], [], []
    tid = state = None
    for line in open(os.path.join(p, "logcat.txt"), errors="replace"):
        t = ts(line)
        m = ROUTE.search(line)
        if m and t:
            marks.setdefault(m.group(2) or m.group(1), t)
            continue
        m = PACE.search(line)
        if m and t:
            pace.append((t, float(m.group(9)), int(m.group(6)), float(m.group(8))))
            continue
        m = GFPS.search(line)
        if m and t:
            gfps.append((t, int(m.group(1)), float(m.group(2))))
            continue
        m = PLACE.search(line)
        if m:
            tid, state = m.group(1), m.group(4).strip()
            continue
        m = TOPO.search(line)
        if m and t:
            topo.append((t, m.group(1), float(m.group(2)), float(m.group(3)),
                         float(m.group(4)), [float(x) for x in m.group(5).split("/")]))
            continue
        m = FREQ.search(line)
        if m and t:
            freq.append((t, int(m.group(1)), int(m.group(4))))
            continue
        m = THERM.search(line)
        if m and t:
            therm.append((t, int(m.group(1))))
    g0 = marks.get("gameplay")
    g1 = marks.get("soak end") or (pace[-1][0] if pace else None)
    held = (marks["soak end"] - marks["soak start"]) if "soak end" in marks and "soak start" in marks else None

    def win(rows):
        return [x for x in rows if g0 and g1 and g0 <= x[0] <= g1]

    wp, wg, wf, wt = win(pace), win(gfps), win(freq), win(therm)
    if os.environ.get("TIMELINE"):
        for k in range(0, int((g1 - g0) // 30) + 1):
            b = [x[1] for x in wg if g0 + 30 * k <= x[0] < g0 + 30 * (k + 1)]
            v = [x for x in win(topo) if x[1] == tid and g0 + 30 * k <= x[0] < g0 + 30 * (k + 1)]
            fr = [x[1] for x in wf if g0 + 30 * k <= x[0] < g0 + 30 * (k + 1)]
            th = [x[1] for x in wt if g0 + 30 * k <= x[0] < g0 + 30 * (k + 1)]
            print("   t+%3ds gfps med %s  vcpu X3 %s%% busy %s%%  p7 %s  cpuC %s" % (
                30 * k, med(b), f(mean([x[5][-1] for x in v]), "%.0f"),
                f(mean([x[2] for x in v]), "%.0f"), f(mean(fr), "%.0f"),
                f(max(th) / 1000.0 if th else None)))
    vt = [x for x in win(topo) if x[1] == tid]
    # The first pace line after the mark straddles it; drop it.
    wp = wp[1:]
    flips = 60 * len(wp)
    secs = sum(x[1] for x in wp) / 1000.0
    return dict(
        id=os.path.basename(p.rstrip("/")), device=req.get("device"),
        env=" ".join(e for e in (req.get("env") or []) if "PLACE" in e) or "--",
        env_all=req.get("env") or [], ref=(req.get("ref") or "")[:10],
        apk=res.get("apk_sha"), seconds=req.get("seconds"), held=held,
        gameplay_s=(g1 - g0) if g0 and g1 else None,
        fps=flips / secs if secs else None,
        late_per_100=100.0 * sum(x[2] for x in wp) / flips if flips else None,
        worst_ms=max((x[3] for x in wp), default=None),
        gfps_med=med([x[1] for x in wg]), gfps_p10=pct([x[1] for x in wg], 10),
        g_med=med([x[2] for x in wg]), windows=len(wg),
        tid=tid, state=state, vwin=len(vt),
        prime=mean([x[5][-1] for x in vt]), mig=mean([x[3] for x in vt]),
        busy=mean([x[2] for x in vt]), rqwait=mean([x[4] for x in vt]),
        p7_first=wf[0][1] if wf else None, p7_last=wf[-1][1] if wf else None,
        p7_mean=mean([x[1] for x in wf]), p7_cap_min=min((x[2] for x in wf), default=None),
        t_first=wt[0][1] / 1000.0 if wt else None, t_last=wt[-1][1] / 1000.0 if wt else None,
        t_max=max((x[1] for x in wt), default=-1000) / 1000.0 if wt else None)


def f(v, fmt="%.1f"):
    return "-" if v is None else fmt % v


def show(label, r):
    print("%s %-44s %s apk=%s %s held=%s/%s play=%ss | fps=%s gfps p50/p10=%s/%s "
          "G_med=%s late/100=%s worst=%sms | vcpu %s %s X3=%s%% mig/s=%s busy=%s%% "
          "rqwait=%sms/s (n=%d) | p7 MHz %s->%s mean %s cap>=%s | cpu C %s->%s max %s" % (
              label, r["id"], r["device"], r["apk"], r["env"], f(r["held"], "%.0f"),
              r["seconds"], f(r["gameplay_s"], "%.0f"), f(r["fps"], "%.2f"),
              r["gfps_med"], r["gfps_p10"], f(r["g_med"], "%.2f"), f(r["late_per_100"]),
              f(r["worst_ms"]), r["tid"], r["state"], f(r["prime"], "%.0f"), f(r["mig"]),
              f(r["busy"], "%.0f"), f(r["rqwait"], "%.2f"), r["vwin"], r["p7_first"],
              r["p7_last"], f(r["p7_mean"], "%.0f"), r["p7_cap_min"], f(r["t_first"]),
              f(r["t_last"]), f(r["t_max"])))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--expect")
    ap.add_argument("--a", nargs="*", default=[])
    ap.add_argument("--b", nargs="*", default=[])
    ap.add_argument("--one", nargs="*", default=[])
    o = ap.parse_args()
    for r in o.one:
        show("-", read(r))
    if not (o.a and o.b):
        return 0
    A, B = [read(r) for r in o.a], [read(r) for r in o.b]
    for r in A:
        show("A", r)
    for r in B:
        show("B", r)
    exp = json.load(open(o.expect))["expect"] if o.expect else {}

    gates = []
    for r in A + B:
        if r["held"] is None or r["held"] < r["seconds"] - exp.get("V_held_slack_s", 15):
            gates.append("%s held %s of %s s: cut short" % (r["id"], f(r["held"], "%.0f"), r["seconds"]))
        if (r["gameplay_s"] or 0) < exp.get("V_min_gameplay_s", 300):
            gates.append("%s gameplay window %s s" % (r["id"], f(r["gameplay_s"], "%.0f")))
        if r["vwin"] < exp.get("V_min_topo_windows", 20):
            gates.append("%s only %d vCPU sampler windows" % (r["id"], r["vwin"]))
    if len({r["device"] for r in A + B}) != 1:
        gates.append("arms span devices")
    if len({r["apk"] for r in A + B}) != 1:
        gates.append("arms ran different apks")
    for g in gates:
        print("VALIDITY: " + g)
    if gates:
        print("VERDICT: REFUSED on validity")
        return 3

    legs = []
    a_prime, b_prime = mean([r["prime"] for r in A]), mean([r["prime"] for r in B])
    legs.append(("P0 every B run PINNED, vCPU >= %d%% on the X3" % exp["P0_b_min_on_prime_pct"],
                 all(r["state"] == "PINNED" and r["prime"] >= exp["P0_b_min_on_prime_pct"] for r in B)))
    legs.append(("P0 every A run NOT PINNED", all((r["state"] or "").startswith("NOT") for r in A)))
    legs.append(("P1 counter moved: B-A X3 share %s points >= %d" % (
        f(b_prime - a_prime), exp["P1_min_prime_shift_pts"]),
        b_prime - a_prime >= exp["P1_min_prime_shift_pts"]))
    a_fps, b_fps = mean([r["fps"] for r in A]), mean([r["fps"] for r in B])
    ch = b_fps / a_fps - 1
    legs.append(("P2 gameplay fps change %+.1f%% in [%+.0f%%, %+.0f%%] (A %.2f, B %.2f)" % (
        100 * ch, 100 * exp["P2_fps_change_min"], 100 * exp["P2_fps_change_max"], a_fps, b_fps),
        exp["P2_fps_change_min"] <= ch <= exp["P2_fps_change_max"]))
    a_sp = max(r["fps"] for r in A) - min(r["fps"] for r in A)
    b_sp = max(r["fps"] for r in B) - min(r["fps"] for r in B)
    legs.append(("P3 |B-A| fps %.2f exceeds within-arm spread (A %.2f, B %.2f)" % (
        abs(b_fps - a_fps), a_sp, b_sp), abs(b_fps - a_fps) > max(a_sp, b_sp)))
    legs.append(("P4 B's X3 clock sustained: last/first p7 >= %.2f in every B run" % exp["P4_p7_last_over_first_min"],
                 all(r["p7_first"] and r["p7_last"] / r["p7_first"] >= exp["P4_p7_last_over_first_min"] for r in B)))
    fails = 0
    for name, ok in legs:
        print("%s %s" % ("PASS" if ok else "FAIL", name))
        fails += not ok
    print("VERDICT: %s" % ("PASS" if not fails else "FAIL (%d legs)" % fails))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
