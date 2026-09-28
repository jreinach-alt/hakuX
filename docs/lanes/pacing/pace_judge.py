#!/usr/bin/env python3
"""Judge #526's soak arms from dispatch results.

    pace_judge.py [--from S] [--to S | --to mark:NAME] [--json OUT]
                  --a RESULT [RESULT ...] --b RESULT [RESULT ...]

Windows are seconds after the route's `soak start` line; `--to mark:gameplay`
ends the window at that route mark (Kabuki's capped pre-fight minutes).

Per run it reads, from logcat.txt:
  [pace526] (hakuX-lane, every 10 s): rel, waited, late_gt1ms, late_p99_us,
            late_max_us, thr_cpu_ms, wait_cpu_ms, proc_cpu_ms, flips, pres,
            pres_1ms. A window counts when its line's timestamp is inside
            the range (the line reports the 10 s before it).
  [pace526] limiter / swap: the mode and swap interval actually in force.
  [rate526]: display mode and rate before, on change and 2 s after the
            surface's frame-rate request.
  hakuX-perf gfps, hakuX-pace vK counts in the window.
and thermal.jsonl: any sample with pause=true, and the hottest zone.

SILENCE IS VOID: a run with no [pace526] window in range is reported VOID,
never as zero. Nothing here reads the prediction file; the legs are applied
by a person against the printed table.
"""
import argparse, json, os, re, statistics, sys
from datetime import datetime

D = os.environ.get("DISPATCH_DIR", "/home/justin/hakux-work/dispatch")
LINE = re.compile(r"^(\d\d-\d\d \d\d:\d\d:\d\d\.\d+)\s+\S+/([\w.-]+)\(\s*\d+\):\s?(.*)$")


def ts(s):
    return datetime.strptime("2026-" + s, "%Y-%m-%d %H:%M:%S.%f").timestamp()


def kv(msg):
    return {k: v for k, v in re.findall(r"(\w+)=([^\s\[\]]+)", msg)}


def read_run(rid, t_from, t_to):
    d = os.path.join(D, "results", rid)
    out = dict(id=rid)
    try:
        res = json.load(open(os.path.join(d, "result.json")))
    except Exception as e:
        return dict(id=rid, void="no result.json (%s)" % e)
    out.update(apk=res.get("apk_sha"), device=res.get("device_label"),
               env=res.get("env"), title=(res.get("title") or "")[:40])
    lines = []
    try:
        for raw in open(os.path.join(d, "logcat.txt"), errors="replace"):
            m = LINE.match(raw.rstrip("\n"))
            if m:
                lines.append((ts(m.group(1)), m.group(2), m.group(3)))
    except FileNotFoundError:
        return dict(out, void="no logcat.txt")
    start = next((t for t, tag, msg in lines if tag == "hakuX-route" and msg.startswith("soak start")), None)
    if start is None:
        return dict(out, void="no soak start line")
    lo = start + t_from
    if isinstance(t_to, str):
        mark = t_to.split(":", 1)[1]
        hi = next((t for t, tag, msg in lines if tag == "hakuX-route" and msg.strip() == "mark " + mark), None)
        if hi is None:
            return dict(out, void="no route mark %r" % mark)
    else:
        hi = start + t_to
    out["window_s"] = round(hi - lo, 1)

    win = []
    for t, tag, msg in lines:
        if tag == "hakuX-lane" and "[pace526]" in msg:
            if " limiter mode=" in msg:
                out["limiter"] = msg.split("[pace526] ", 1)[1]
            elif " swap interval=" in msg:
                out["swap"] = msg.split("[pace526] ", 1)[1]
            elif lo <= t <= hi and "rel=" in msg:
                win.append(kv(msg))
        elif tag == "hakuX-lane" and "[rate526]" in msg:
            out.setdefault("rate", []).append(msg.split("[rate526] ", 1)[1][:200])
    g = [int(m.group(1)) for t, tag, msg in lines
         if tag == "hakuX-perf" and lo <= t <= hi for m in [re.search(r"gfps=(\d+)", msg)] if m]
    vb = [0] * 5
    for t, tag, msg in lines:
        if tag == "hakuX-pace" and lo <= t <= hi:
            k = kv(msg)
            if all("v%d" % i in k for i in range(5)) and float(k.get("f", 0)) > 60:
                for i in range(5):
                    vb[i] += int(k["v%d" % i])
    out["gfps_median"] = statistics.median(g) if g else None
    out["gfps_lines"] = len(g)
    out["pace_vb"] = vb
    if not win:
        return dict(out, void="no [pace526] window in range")

    def s(key, f=float):
        return sum(f(w.get(key, 0)) for w in win)
    rel, waited = s("rel", int), s("waited", int)
    flips, pres = s("flips", int), s("pres", int)
    out.update(
        windows=len(win), mode=win[-1].get("mode"), rel=rel, waited=waited,
        late_gt1ms=s("late_gt1ms", int),
        late_gt1ms_share=round(s("late_gt1ms", int) / waited, 5) if waited else None,
        late_p99_us_max=max(float(w["late_p99_us"]) for w in win),
        late_p99_us_median=statistics.median(float(w["late_p99_us"]) for w in win),
        late_p50_us_median=statistics.median(float(w["late_p50_us"]) for w in win),
        late_max_us=max(float(w["late_max_us"]) for w in win),
        thr_cpu_ms_per_display_frame=round(s("thr_cpu_ms") / rel, 4) if rel else None,
        wait_cpu_ms_per_display_frame=round(s("wait_cpu_ms") / rel, 4) if rel else None,
        thr_cpu_ms_per_flip=round(s("thr_cpu_ms") / flips, 4) if flips else None,
        proc_cpu_ms_per_flip=round(s("proc_cpu_ms") / flips, 3) if flips else None,
        proc_cpu_share=round(s("proc_cpu_ms") / (1000.0 * s("s")), 4),
        flips_per_s=round(flips / s("s"), 2),
        pres_1ms_share=round(s("pres_1ms", int) / pres, 4) if pres else None,
    )

    pauses, hottest = 0, 0
    try:
        for l in open(os.path.join(d, "thermal.jsonl")):
            j = json.loads(l)
            pauses += bool(j.get("pause"))
            for z in j.get("tz") or []:
                hottest = max(hottest, z[2])
        out["thermal"] = dict(pause_samples=pauses, hottest_c=hottest / 1000.0)
    except FileNotFoundError:
        out["thermal"] = None
    return out


def pooled(runs, key):
    v = [r[key] for r in runs if r.get(key) is not None and not r.get("void")]
    return round(statistics.mean(v), 4) if v else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="t_from", type=float, default=30.0)
    ap.add_argument("--to", dest="t_to", default="100000")
    ap.add_argument("--a", nargs="+", required=True)
    ap.add_argument("--b", nargs="+", required=True)
    ap.add_argument("--json")
    o = ap.parse_args()
    t_to = o.t_to if o.t_to.startswith("mark:") else float(o.t_to)
    arms = {"A": [read_run(r, o.t_from, t_to) for r in o.a],
            "B": [read_run(r, o.t_from, t_to) for r in o.b]}
    keys = ["mode", "window_s", "windows", "gfps_median", "flips_per_s", "waited", "late_gt1ms_share",
            "late_p50_us_median", "late_p99_us_median", "late_p99_us_max", "late_max_us",
            "thr_cpu_ms_per_display_frame", "wait_cpu_ms_per_display_frame", "thr_cpu_ms_per_flip",
            "proc_cpu_ms_per_flip", "proc_cpu_share", "pres_1ms_share"]
    for arm, runs in arms.items():
        for r in runs:
            print("%s %s dev=%s apk=%s env=%s" % (arm, r["id"], r.get("device"), r.get("apk"), r.get("env")))
            if r.get("void"):
                print("   VOID: %s" % r["void"])
                continue
            print("   limiter: %s | swap: %s" % (r.get("limiter"), r.get("swap")))
            print("   thermal: %s  pace_vb(v0..v4)=%s" % (r.get("thermal"), r.get("pace_vb")))
            for k in keys:
                print("   %-30s %s" % (k, r.get(k)))
            for x in r.get("rate", []):
                print("   rate526: %s" % x)
    print("\npooled (mean over non-void runs)")
    print("   %-30s %12s %12s" % ("", "A", "B"))
    for k in keys[3:]:
        print("   %-30s %12s %12s" % (k, pooled(arms["A"], k), pooled(arms["B"], k)))
    if o.json:
        json.dump(arms, open(o.json, "w"), indent=1)


if __name__ == "__main__":
    main()
