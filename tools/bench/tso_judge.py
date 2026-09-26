#!/usr/bin/env python3
"""Judge the HAKUX_TCG_TSO=rcpc soak A/B (lane.perfarch, #68).

    tso_judge.py --expect docs/testing/predictions/perfarch-tso-rcpc-cost.json \
                 --a RESULT_A1 [RESULT_A2 ...] --b RESULT_B1 [RESULT_B2 ...]

Each RESULT is a dispatch result directory (logcat.txt inside) or a logcat
file. Reads only the always-on lines: hakuX-perf `gfps=N G:mean(min-max)`,
hakuX-pages `[mb emitted N, total M]`, and this lane's hakuX-lane
`perfarch tso ...` lines. Legs and thresholds come from the prediction's
`expect` block, never from this file, so the judge cannot move a bar.

Exit 0 all legs PASS, 1 any leg FAILS, 3 a validity gate refused.
"""
import argparse
import json
import os
import re
import statistics
import sys

GFPS = re.compile(r"hakuX-perf.*?gfps=(\d+) G:([\d.]+)\(")
PAGES_MB = re.compile(r"hakuX-pages.*\[mb emitted (\d+), total (\d+)\]")
TSO_ON = re.compile(r"perfarch tso mode=rcpc requested lrcpc=(\d) -> (ON|OFF)")
TSO_EMIT = re.compile(r"perfarch tso rcpc emitted ld=(\d+) st=(\d+) "
                      r"pair=(\d+) slow=(\d+)")
CRASH = re.compile(r"hakuX-crash|Fatal signal|F DEBUG|F/DEBUG|F libc|F/libc")


def logcat_of(p):
    if os.path.isdir(p):
        return os.path.join(p, "logcat.txt")
    return p


def env_of(p):
    rj = os.path.join(p, "result.json") if os.path.isdir(p) else None
    if rj and os.path.exists(rj):
        r = json.load(open(rj))
        return r.get("env") or [], r.get("device_label"), r.get("apk_sha")
    return None, None, None


def load(p):
    rows, mb_total, on, emit, crash = [], 0, None, None, []
    for line in open(logcat_of(p), errors="replace"):
        m = GFPS.search(line)
        if m:
            rows.append((int(m.group(1)), float(m.group(2))))
            continue
        m = PAGES_MB.search(line)
        if m:
            mb_total = int(m.group(2))
            continue
        m = TSO_ON.search(line)
        if m:
            on = m.group(2)
            continue
        m = TSO_EMIT.search(line)
        if m:
            emit = tuple(int(x) for x in m.groups())
            continue
        if CRASH.search(line):
            crash.append(line.strip()[:160])
    # The first quarter is boot and warm-up, as in tcg-barriers-elided.md.
    body = rows[len(rows) // 4:]
    env, dev, apk = env_of(p)
    return dict(path=p, n=len(rows), body=body, mb_total=mb_total, on=on,
                emit=emit, crash=crash, env=env, device=dev, apk=apk,
                g_med=statistics.median([g for _, g in body]) if body else None,
                gfps_med=statistics.median([f for f, _ in body]) if body else None)


def pct(xs, q):
    xs = sorted(xs)
    if not xs:
        return 0
    return xs[min(len(xs) - 1, int(round(q / 100.0 * (len(xs) - 1))))]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--expect", required=True)
    ap.add_argument("--a", nargs="+", required=True)
    ap.add_argument("--b", nargs="+", required=True)
    o = ap.parse_args()
    exp = json.load(open(o.expect))["expect"]
    A = [load(p) for p in o.a]
    B = [load(p) for p in o.b]

    for label, S in (("A", A), ("B", B)):
        for r in S:
            gf = [f for f, _ in r["body"]]
            print("%s %-50s dev=%s apk=%s env=%s windows=%d G_med=%s "
                  "gfps p50/p90/max=%s/%s/%s tso=%s emit=%s mb_total=%d "
                  "crash_lines=%d" % (
                      label, os.path.basename(r["path"].rstrip("/")),
                      r["device"], r["apk"], r["env"], r["n"],
                      "%.2f" % r["g_med"] if r["g_med"] else None,
                      pct(gf, 50), pct(gf, 90), max(gf) if gf else 0,
                      r["on"], r["emit"], r["mb_total"], len(r["crash"])))

    # Validity gates: a pair that cannot be read is not a verdict.
    gates = []
    for r in A + B:
        if len(r["body"]) < exp["V_min_windows"]:
            gates.append("%s: %d post-warm-up windows < %d" % (
                r["path"], len(r["body"]), exp["V_min_windows"]))
    devs = {r["device"] for r in A + B}
    if len(devs) > 1:
        gates.append("arms ran on different devices: %s" % sorted(devs))
    apks = {r["apk"] for r in A + B}
    if len(apks) > 1:
        gates.append("arms ran different APKs: %s -- this is an env A/B"
                     % sorted(apks))
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

    # T0: the mode executed in B and did not in A.
    b_on = all(r["on"] == "ON" and r["emit"] and
               r["emit"][0] + r["emit"][1] >= exp["T0_min_emitted"] for r in B)
    a_off = all(r["on"] is None and r["emit"] is None for r in A)
    leg("T0", b_on and a_off,
        "B: ON with >= %d ld+st emitted on every run; A: no tso line at all"
        % exp["T0_min_emitted"])

    # T1: the cost, on game frame time, worst case across runs.
    a_best = min(r["g_med"] for r in A)
    a_worst = max(r["g_med"] for r in A)
    b_best = min(r["g_med"] for r in B)
    b_worst = max(r["g_med"] for r in B)
    a_mid = statistics.median([r["g_med"] for r in A])
    b_mid = statistics.median([r["g_med"] for r in B])
    cost = b_mid / a_mid - 1
    spread = max(a_worst - a_best, b_worst - b_best)
    print("     G median A=%.2f ms B=%.2f ms cost=%+.1f%%  within-arm spread "
          "%.2f ms vs between-arm %.2f ms" % (a_mid, b_mid, 100 * cost,
                                             spread, b_mid - a_mid))
    leg("T1a", cost < exp["T1a_cost_max_vs_full_revert"],
        "cost %+.1f%% < %.1f%% (the full barrier revert, #54)"
        % (100 * cost, 100 * exp["T1a_cost_max_vs_full_revert"]))
    leg("T1b", exp["T1b_cost_min"] <= cost <= exp["T1b_cost_max"],
        "cost %+.1f%% within the registered band [%.0f%%, %.0f%%]"
        % (100 * cost, 100 * exp["T1b_cost_min"], 100 * exp["T1b_cost_max"]))
    leg("T1c", spread < abs(b_mid - a_mid) or abs(cost) < exp["T1b_cost_min"],
        "between-arm delta exceeds within-arm spread (else the cost is noise)")

    # T2: no new crash, and B lived as long as A.
    b_crash = sum(len(r["crash"]) for r in B)
    a_crash = sum(len(r["crash"]) for r in A)
    min_b = min(r["n"] for r in B)
    min_a = min(r["n"] for r in A)
    leg("T2", b_crash <= a_crash and min_b >= exp["T2_min_life_frac"] * min_a,
        "B crash lines %d <= A %d; B windows %d >= %.0f%% of A's %d"
        % (b_crash, a_crash, min_b, 100 * exp["T2_min_life_frac"], min_a))

    # T3 (report): what the MFENCE-only barrier count came to in B.
    print("T3   report: mb_total A=%s B=%s (full revert: 347,473)"
          % ([r["mb_total"] for r in A], [r["mb_total"] for r in B]))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
