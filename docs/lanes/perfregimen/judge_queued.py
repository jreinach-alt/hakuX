#!/usr/bin/env python3
"""Judge the queued Thor Blinx pilot: two dispatcher soak results, REST then MAX.

    judge_queued.py <rest-result-dir> <max-result-dir> --prediction <json> [--window 135,245]

Each dir is $DISPATCH_DIR/results/<id>/ (result.json, logcat.txt,
perf_regimen.json). The fps is judge.py's: the median `gfps=N` value inside
the window, in seconds from the arm's first hakuX line.
"""
import argparse, json, math, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from judge import arm_fps  # noqa: E402


def load(d, name):
    try:
        return json.load(open(os.path.join(d, name)))
    except (OSError, ValueError):
        return {}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("rest"); ap.add_argument("max")
    ap.add_argument("--prediction", required=True)
    ap.add_argument("--window", default="135,245")
    a = ap.parse_args()
    e = json.load(open(a.prediction))["expect"]
    lo, hi = (float(x) for x in a.window.split(","))
    arms, legs = {}, []
    for name, d in (("rest", a.rest), ("max", a.max)):
        r, p = load(d, "result.json"), load(d, "perf_regimen.json")
        fps, n = arm_fps(os.path.join(d, "logcat.txt"), lo, hi)
        want = (e[name + "_perf"], e[name + "_fan"])
        got = (p.get("perf_mode"), p.get("fan_mode"))
        arms[name] = dict(fps=fps, n=n, apk=r.get("apk_sha"), dev=r.get("device_label"))
        print("%-4s %s dev=%s apk=%s regimen=%s ran=%s restored=%s fps=%.1f (%d lines)"
              % (name, d, r.get("device_label"), r.get("apk_sha"), p.get("regimen"),
                 got, p.get("perf_restored"), fps, n))
        legs.append(("M0 %s: thor, regimen %s, ran at %s, restored, >= %d lines"
                     % (name, name, want, e["M0/gfps_lines_min"]),
                     r.get("device_label") == "thor" and p.get("regimen") == name
                     and got == want and p.get("perf_restored") is True
                     and n >= e["M0/gfps_lines_min"]))
    legs.append(("M0 same apk_sha in both arms",
                 arms["rest"]["apk"] is not None and arms["rest"]["apk"] == arms["max"]["apk"]))
    void = not all(ok for _, ok in legs)
    ratio = arms["max"]["fps"] / arms["rest"]["fps"] if arms["rest"]["fps"] else math.nan
    legs.append(("P5 MAX/REST = %.3f >= %.2f" % (ratio, e["P5/max_over_rest_min"]),
                 ratio >= e["P5/max_over_rest_min"]))
    legs.append(("P6 (guess) MAX/REST = %.3f >= %.2f" % (ratio, e["P6/max_over_rest_guess"]),
                 ratio >= e["P6/max_over_rest_guess"]))
    for text, ok in legs:
        print("%s  %s" % ("PASS" if ok else "FAIL", text))
    print("VERDICT: %s" % ("VOID (an M0 leg failed)" if void else
                           "PASS" if all(ok for _, ok in legs) else
                           "P5 %s, P6 %s" % tuple("PASS" if ok else "FAIL" for _, ok in legs[-2:])))
    return 2 if void else 0


if __name__ == "__main__":
    sys.exit(main())
