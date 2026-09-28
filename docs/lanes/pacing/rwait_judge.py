#!/usr/bin/env python3
"""Judge #526's render-wait soak arms (pacing-rwait-soak.json).

    rwait_judge.py [--mark gameplay] [--json OUT]
                   --a RESULT [RESULT ...] --b RESULT [RESULT ...]

The window runs from the route's `mark <NAME>` line to its `soak end` line
(to the end of the logcat if there is none). Per run it reads, from
logcat.txt:
  [rwait526] render wait mode=...: the mode actually in force.
  [rwait526] mode=... (hakuX-lane, every 10 s): flips, thr_cpu_ms and
            wait_cpu_ms of the PFIFO thread, and per site (deferred, rotate)
            calls, waits, spun, blocked, wakes, wait_ms, p50_us, p99_us,
            max_us. A window counts when its line's timestamp is inside the
            range (the line reports the 10 s before it).
  hakuX-perf gfps in the window, and the largest gap between hakuX-perf
            lines after the mark (leg H0).
and verdict.json's thermal and power blocks, when the verdict has run.

SILENCE IS VOID: a run with no [rwait526] window in range is reported VOID,
never as zero. Nothing here reads the prediction file; the legs are applied
by a person against the printed table.
"""
import argparse, json, os, re, statistics
from datetime import datetime

D = os.environ.get("DISPATCH_DIR", "/home/justin/hakux-work/dispatch")
LINE = re.compile(r"^(\d\d-\d\d \d\d:\d\d:\d\d\.\d+)\s+\S+/([\w.-]+)\(\s*\d+\):\s?(.*)$")
SITES = ("deferred", "rotate")


def ts(s):
    return datetime.strptime("2026-" + s, "%Y-%m-%d %H:%M:%S.%f").timestamp()


def kv(msg):
    return {k: v for k, v in re.findall(r"(\w+)=([^\s\[\]|]+)", msg)}


def parse_window(msg):
    parts = msg.split(" | ")
    w = {"all": kv(parts[0])}
    for p in parts[1:]:
        name = p.split(" ", 1)[0]
        if name in SITES:
            w[name] = kv(p)
    return w


def read_run(rid, mark):
    d = os.path.join(D, "results", rid)
    out = dict(id=rid)
    try:
        res = json.load(open(os.path.join(d, "result.json")))
    except Exception as e:
        return dict(id=rid, void="no result.json (%s)" % e)
    out.update(apk=res.get("apk_sha"), device=res.get("device_label"),
               env=res.get("env"), title=(res.get("title") or "")[:40])
    if os.path.exists(os.path.join(d, "VOID.txt")):
        out["void_txt"] = open(os.path.join(d, "VOID.txt"), errors="replace").read().strip()[:200]
    lines = []
    try:
        for raw in open(os.path.join(d, "logcat.txt"), errors="replace"):
            m = LINE.match(raw.rstrip("\n"))
            if m:
                lines.append((ts(m.group(1)), m.group(2), m.group(3)))
    except FileNotFoundError:
        return dict(out, void="no logcat.txt")
    lo = next((t for t, tag, msg in lines
               if tag == "hakuX-route" and msg.strip() == "mark " + mark), None)
    if lo is None:
        return dict(out, void="no route mark %r" % mark)
    hi = next((t for t, tag, msg in lines
               if tag == "hakuX-route" and msg.startswith("soak end")), lines[-1][0])
    out["window_s"] = round(hi - lo, 1)

    win = []
    for t, tag, msg in lines:
        if tag == "hakuX-lane" and "[rwait526]" in msg:
            body = msg.split("[rwait526] ", 1)[1]
            if body.startswith("render wait mode="):
                out["mode_line"] = body
            elif lo <= t <= hi and body.startswith("mode="):
                win.append(parse_window(body))
    perf = [(t, msg) for t, tag, msg in lines if tag == "hakuX-perf" and lo <= t <= hi]
    g = [int(m.group(1)) for t, msg in perf for m in [re.search(r"gfps=(\d+)", msg)] if m]
    out["gfps_median"] = statistics.median(g) if g else None
    out["gfps_lines"] = len(g)
    pt = [t for t, _ in perf]
    out["perf_gap_max_s"] = round(max(b - a for a, b in zip(pt, pt[1:])), 1) if len(pt) > 1 else None
    if not win:
        return dict(out, void="no [rwait526] window in range")

    def s(site, key, f=float):
        return sum(f(w.get(site, {}).get(key, 0)) for w in win)
    flips = s("all", "flips", int)
    out.update(
        windows=len(win), modes=sorted({w["all"].get("mode") for w in win}), flips=flips,
        flips_per_s=round(flips / s("all", "s"), 2) if s("all", "s") else None,
        thr_cpu_ms_per_flip=round(s("all", "thr_cpu_ms") / flips, 4) if flips else None,
        wait_cpu_ms_per_flip=round(s("all", "wait_cpu_ms") / flips, 4) if flips else None,
        thr_cpu_share=round(s("all", "thr_cpu_ms") / (1000.0 * s("all", "s")), 4),
    )
    for site in SITES:
        waits, blocked = s(site, "waits", int), s(site, "blocked", int)
        p99 = [float(w[site]["p99_us"]) for w in win if site in w and int(w[site].get("waits", 0))]
        p50 = [float(w[site]["p50_us"]) for w in win if site in w and int(w[site].get("waits", 0))]
        out[site] = dict(
            calls=s(site, "calls", int), waits=waits, spun=s(site, "spun", int), blocked=blocked,
            wakes_per_blocked=round(s(site, "wakes", int) / blocked, 2) if blocked else None,
            waits_per_flip=round(waits / flips, 3) if flips else None,
            wait_ms_per_flip=round(s(site, "wait_ms") / flips, 4) if flips else None,
            p50_us_median=statistics.median(p50) if p50 else None,
            p99_us_median=statistics.median(p99) if p99 else None,
            max_us=max((float(w[site].get("max_us", 0)) for w in win if site in w), default=None),
        )

    try:
        v = json.load(open(os.path.join(d, "verdict.json")))
        th, pw = v.get("thermal") or {}, v.get("power") or {}
        out["thermal"] = dict(regimen=th.get("regimen"), first_pause_s=th.get("first_pause_s"),
                              failed_sustained=th.get("failed_sustained"), in_window=th.get("in_window"))
        out["power"] = {k: pw.get(k) for k in ("measured", "net_w", "battery_w", "usb_w", "usb_bound",
                                                 "j_per_frame", "j_per_frame_battery", "sign_suspect")}
    except (OSError, ValueError):
        out["thermal"] = out["power"] = None
    return out


def pooled(runs, key, site=None):
    v = []
    for r in runs:
        if r.get("void"):
            continue
        x = (r.get(site) or {}).get(key) if site else r.get(key)
        if x is not None:
            v.append(x)
    return round(statistics.mean(v), 4) if v else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mark", default="gameplay")
    ap.add_argument("--a", nargs="+", required=True)
    ap.add_argument("--b", nargs="+", required=True)
    ap.add_argument("--json")
    o = ap.parse_args()
    arms = {"A": [read_run(r, o.mark) for r in o.a], "B": [read_run(r, o.mark) for r in o.b]}
    keys = ["modes", "window_s", "windows", "gfps_median", "gfps_lines", "perf_gap_max_s", "flips_per_s",
            "thr_cpu_ms_per_flip", "wait_cpu_ms_per_flip", "thr_cpu_share"]
    for arm, runs in arms.items():
        for r in runs:
            print("%s %s dev=%s apk=%s env=%s" % (arm, r["id"], r.get("device"), r.get("apk"), r.get("env")))
            if r.get("void_txt"):
                print("   VOID.txt: %s" % r["void_txt"])
            if r.get("void"):
                print("   VOID: %s" % r["void"])
                continue
            print("   mode line: %s" % r.get("mode_line"))
            print("   thermal: %s" % r.get("thermal"))
            print("   power: %s" % r.get("power"))
            for k in keys:
                print("   %-24s %s" % (k, r.get(k)))
            for site in SITES:
                print("   %-24s %s" % (site, r.get(site)))
    print("\npooled (mean over non-void runs)")
    print("   %-34s %12s %12s" % ("", "A", "B"))
    for k in keys[3:]:
        print("   %-34s %12s %12s" % (k, pooled(arms["A"], k), pooled(arms["B"], k)))
    for site in SITES:
        for k in ("waits_per_flip", "wait_ms_per_flip", "wakes_per_blocked", "p50_us_median",
                  "p99_us_median", "max_us"):
            print("   %-34s %12s %12s" % (site + "." + k, pooled(arms["A"], k, site),
                                         pooled(arms["B"], k, site)))
    if o.json:
        json.dump(arms, open(o.json, "w"), indent=1)


if __name__ == "__main__":
    main()
