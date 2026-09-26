#!/usr/bin/env python3
"""Judge the HAKUX_PLACE_VCPU=prime soak A/B (lane.perfarch, #68).

    place_judge.py --expect docs/testing/predictions/perfarch-vcpu-prime.json \
                   --a RESULT_A1 [...] --b RESULT_B1 [...]

Both arms run the HAKUX_TOPO sampler, which names the vCPU tid
("place vcpu tid=N ...") and reports that tid's CPU residency every window,
so placement is MEASURED on both sides rather than assumed from the pin.
Thresholds come from the prediction's `expect` block.

Exit 0 all legs PASS, 1 any leg FAILS, 3 a validity gate refused.
"""
import argparse
import json
import os
import re
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tso_judge import load, pct  # noqa: E402  (same gfps/crash parsing)

PLACE = re.compile(r"perfarch place vcpu tid=(\d+) spec=(\S+)(?: mask=(0x[0-9a-f]+))? -> (\w+)")
TOPO = re.compile(r"perfarch topo tid=(\d+) comm=\S+ busy=([\d.]+)% mig/s=([\d.]+) "
                  r"rqwait_ms/s=([\d.]+) cpu%=([\d/]+)")
FREQ = re.compile(r"perfarch topo freq .*?\bp7=(\d+)\((\d+)-(\d+),cap(\d+)\)")


def placement(p):
    f = os.path.join(p, "logcat.txt") if os.path.isdir(p) else p
    tid, state, rows, freq = None, None, [], []
    for line in open(f, errors="replace"):
        m = PLACE.search(line)
        if m:
            tid, state = m.group(1), m.group(4)
            continue
        m = TOPO.search(line)
        if m and tid and m.group(1) == tid:
            cpu = [float(x) for x in m.group(5).split("/")]
            rows.append(dict(busy=float(m.group(2)), mig=float(m.group(3)),
                             wait=float(m.group(4)), cpu=cpu))
            continue
        m = FREQ.search(line)
        if m:
            freq.append(tuple(int(x) for x in m.groups()))
    prime = [r["cpu"][-1] for r in rows]
    return dict(tid=tid, state=state, windows=len(rows),
                prime_pct=statistics.mean(prime) if prime else None,
                mig=statistics.mean(r["mig"] for r in rows) if rows else None,
                busy=statistics.mean(r["busy"] for r in rows) if rows else None,
                wait=statistics.mean(r["wait"] for r in rows) if rows else None,
                p7=freq)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--expect", required=True)
    ap.add_argument("--a", nargs="+", required=True)
    ap.add_argument("--b", nargs="+", required=True)
    o = ap.parse_args()
    exp = json.load(open(o.expect))["expect"]
    A = [dict(load(p), **placement(p)) for p in o.a]
    B = [dict(load(p), **placement(p)) for p in o.b]

    for label, S in (("A", A), ("B", B)):
        for r in S:
            gf = [f for f, _ in r["body"]]
            p7 = r["p7"]
            print("%s %-40s dev=%s apk=%s windows=%d G_med=%s gfps p50/p90/max="
                  "%s/%s/%s | vcpu tid=%s %s on-prime=%s%% mig/s=%s busy=%s%% "
                  "rqwait=%sms/s | p7 MHz mean=%s cap(min)=%s" % (
                      label, os.path.basename(r["path"].rstrip("/")),
                      r["device"], r["apk"], r["n"],
                      "%.2f" % r["g_med"] if r["g_med"] else None,
                      pct(gf, 50), pct(gf, 90), max(gf) if gf else 0,
                      r["tid"], r["state"],
                      "%.0f" % r["prime_pct"] if r["prime_pct"] is not None else None,
                      "%.1f" % r["mig"] if r["mig"] is not None else None,
                      "%.0f" % r["busy"] if r["busy"] is not None else None,
                      "%.2f" % r["wait"] if r["wait"] is not None else None,
                      int(statistics.mean(x[0] for x in p7)) if p7 else None,
                      min(x[3] for x in p7) if p7 else None))

    gates = []
    for r in A + B:
        if len(r["body"]) < exp["V_min_windows"]:
            gates.append("%s: %d post-warm-up windows" % (r["path"], len(r["body"])))
        if r["prime_pct"] is None:
            gates.append("%s: no topology rows for the vCPU tid" % r["path"])
    if len({r["device"] for r in A + B}) > 1:
        gates.append("arms on different devices")
    if len({r["apk"] for r in A + B}) > 1:
        gates.append("arms ran different APKs -- this is an env A/B")
    if gates:
        print("REFUSED (validity):")
        for g in gates:
            print("  " + g)
        return 3

    fails = 0

    def leg(name, ok, text):
        nonlocal fails
        print("%-4s %s  %s" % (name, "PASS" if ok else "FAIL", text))
        fails += 0 if ok else 1

    leg("P0", all(r["state"] == "PINNED" and r["prime_pct"] >= exp["P0_b_min_on_prime_pct"] for r in B)
        and all(r["state"] == "NOT" and r["prime_pct"] <= exp["P0_a_max_on_prime_pct"] for r in A),
        "B pinned and >= %d%% of vCPU time on the prime core; A unpinned and <= %d%%"
        % (exp["P0_b_min_on_prime_pct"], exp["P0_a_max_on_prime_pct"]))

    a_mid = statistics.median(r["g_med"] for r in A)
    b_mid = statistics.median(r["g_med"] for r in B)
    gain = b_mid / a_mid - 1
    spread = max(max(r["g_med"] for r in S) - min(r["g_med"] for r in S) for S in (A, B))
    print("     G median A=%.2f ms B=%.2f ms change=%+.1f%%  within-arm spread %.2f ms"
          % (a_mid, b_mid, 100 * gain, spread))
    leg("P1", exp["P1_change_min"] <= gain <= exp["P1_change_max"],
        "game frame time change %+.1f%% within [%+.0f%%, %+.0f%%]"
        % (100 * gain, 100 * exp["P1_change_min"], 100 * exp["P1_change_max"]))
    leg("P2", spread < abs(b_mid - a_mid), "between-arm delta exceeds within-arm spread")

    # P3: no thermal collapse inside the soak -- B's late half against its early half.
    worst = 0.0
    for r in B:
        g = [x for _, x in r["body"]]
        h = len(g) // 2
        if h:
            worst = max(worst, statistics.median(g[h:]) / statistics.median(g[:h]) - 1)
    leg("P3", worst <= exp["P3_late_half_slowdown_max"],
        "B late-half G at most %+.0f%% over its early half (worst %+.1f%%)"
        % (100 * exp["P3_late_half_slowdown_max"], 100 * worst))

    a_p90 = min(pct([f for f, _ in r["body"]], 90) for r in A)
    b_p90 = min(pct([f for f, _ in r["body"]], 90) for r in B)
    leg("P4", b_p90 >= a_p90, "gfps p90 worst-B %d >= worst-A %d" % (b_p90, a_p90))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
