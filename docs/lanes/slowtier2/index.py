#!/usr/bin/env python3
"""Every title soak for the #462 phase-2 titles, one line each, with the
conditions a reading needs before it can be called the title's speed.

    index.py [pattern ...]      (default: the sixteen titles of the brief)

Per result: id, device, ref, apk, requester, seconds, regimen, verdict fps,
whether the logcat spec carries the perflog tags (hakuX-phase), whether
thermal.jsonl exists, and the start xo-therm when it does.
"""
import json
import os
import re
import sys

D = os.environ.get("DISPATCH_DIR", "/home/justin/hakux-work/dispatch")
TITLES = ["Jet_Set|JSRF", "MechAssault_2", "Arctic_Thunder", "BloodRayne", "Alias",
          "Xtreme_Beach", "Conker", "Crash_Twinsanity", "Dead_or_Alive_3|DOA3|Alive 3",
          "Project_Gotham_Racing\\.", "Brute_Force", "Otogi", "41430006-Burnout",
          "45410083-Black", "Midtown_Madness_3", "Crimson"]


def load(p):
    try:
        return json.load(open(p))
    except Exception:
        return None


def verdict_fps(v):
    if not v:
        return "no-verdict"
    out = ["%s=%s" % (k, v[k]) for k in sorted(v) if "fps" in k and not isinstance(v[k], (dict, list))]
    th = v.get("thermal") or {}
    if th:
        out.append("pauses=%d in_window=%s" % (len(th.get("pauses") or []), th.get("in_window")))
    if v.get("void"):
        out.append("VOID")
    return " ".join(out)


def start_therm(p):
    """xo-therm (C) at the start row, and the max over the file."""
    if not os.path.exists(p):
        return None
    first = hi = None
    paused = 0
    for line in open(p, errors="replace"):
        try:
            j = json.loads(line)
        except Exception:
            continue
        xo = next((x[2] for x in j.get("tz", []) if x[1] == "xo-therm"), None)
        if xo is None:
            continue
        xo /= 1000.0
        first = xo if first is None else first
        hi = xo if hi is None else max(hi, xo)
        paused += bool(j.get("pause"))
    return "xo %.1f->max %.1f paused_rows %d" % (first, hi, paused) if first is not None else "no-xo"


def main():
    pats = [re.compile(p, re.I) for p in (sys.argv[1:] or TITLES)]
    rows = []
    for d in os.listdir(f"{D}/results"):
        rd = f"{D}/results/{d}"
        r = load(f"{rd}/result.json")
        if not r or not r.get("title"):
            continue
        t = r["title"]
        hit = [p.pattern for p in pats if p.search(t)]
        if not hit:
            continue
        reg = load(f"{rd}/perf_regimen.json") or {}
        v = load(f"{rd}/verdict.json")
        spec = (r.get("logcat") or {}).get("spec", "")
        rows.append((hit[0], d, r.get("device_label"), r.get("ref"), r.get("apk_sha"), r.get("requester"),
                     r.get("seconds"), reg.get("regimen"), verdict_fps(v),
                     "perflog" if "hakuX-phase" in spec else "-",
                     start_therm(f"{rd}/thermal.jsonl"), (r.get("env") or [])))
    for row in sorted(rows):
        print(" | ".join(str(x) for x in row))


if __name__ == "__main__":
    main()
