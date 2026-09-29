#!/usr/bin/env python3
"""Judge docs/testing/predictions/litcompile569-doa-soak.json (#569 B1, device).

    doa_soak_judge.py <base result dir> <fix result dir>
                      [--base-span HH:MM:SS HH:MM:SS] [--fix-span HH:MM:SS HH:MM:SS]

Written before either arm ran. Reads each arm's [shd413] windows with
lane.shaderfb569's fbwin.py parser, the perflog `xemu-gpu` lines
("GPU: Tot:<ms> Rnd:<ms> ..." every 60 frames) and thermal.jsonl. The fight
load is fbwin.py's registered rule; --*-span places it from the route frames
where the rule finds none, and the report says which was used.
"""
import json
import os
import re
import statistics
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "shaderfb569"))
import fbwin  # noqa: E402

K = 1 - 1 / 6.26          # the registered model: B1 removes this share of VS stage time
GPU = re.compile(r"GPU: Tot:([\d.]+) Rnd:([\d.]+)")


def arm(d, span):
    lc, sc = fbwin.logcat_of(d)
    lines = open(lc, errors="replace").read().splitlines()
    wins, marks, bad = fbwin.parse(lines)
    rule = fbwin.fight_load(wins, marks)
    how = "rule"
    load = rule
    if span:
        load, how = fbwin.span_of(wins, span[0], span[1]), "frames %s-%s" % tuple(span)
    elif not rule:
        load, how = None, "none"
    # xemu-gpu lines, timed on fbwin's clock (same day-wrap as parse())
    gpu = []
    day, last = 0.0, None
    for ln in lines:
        t = fbwin.secs(ln)
        if t is None:
            continue
        if last is not None and t + day < last - 43200:
            day += 86400
        t += day
        last = t
        m = GPU.search(ln)
        if m:
            gpu.append((t, float(m.group(1))))
    play = [t for t, n in marks if n == "play"]
    quiet = []
    prev_t = None
    for w in wins:
        if prev_t is not None and w["dpm"] == 0 and play and w["t"] > play[0]:
            quiet.append((prev_t, w["t"]))
        prev_t = w["t"]
    gq = [g for t, g in gpu if any(a < t <= b for a, b in quiet)]
    th = [json.loads(x) for x in open(os.path.join(d, "thermal.jsonl"))] \
        if os.path.exists(os.path.join(d, "thermal.jsonl")) else []
    tv = None
    tvp = os.path.join(d, "verdict.json")
    if os.path.exists(tvp):
        tv = (json.load(open(tvp)).get("power") or {}).get("j_per_frame")
    T = lambda ws, k: sum(w[k] for w in ws)
    return {
        "sc": sc, "bad": bad, "n": len(wins),
        "dpc": T(wins, "dpc_ms"), "dpn": T(wins, "dpn"), "dvs": T(wins, "dvs_ms"),
        "dgs": T(wins, "dgs_ms"), "dfs": T(wins, "dfs_ms"),
        "load": load, "how": how,
        "gpu_q": statistics.median(gq) if gq else None, "gpu_n": len(gq),
        "paused": any(r.get("pause") for r in th), "th_n": len(th), "jpf": tv,
    }


def main(argv):
    spans = {"base": None, "fix": None}
    args = []
    i = 0
    while i < len(argv):
        if argv[i] in ("--base-span", "--fix-span"):
            spans[argv[i][2:].split("-")[0]] = (argv[i + 1], argv[i + 2])
            i += 3
        else:
            args.append(argv[i])
            i += 1
    B = arm(args[0], spans["base"])
    F = arm(args[1], spans["fix"])
    for n, a in (("base", B), ("fix", F)):
        print("%-4s cache=%s windows=%d unparsed=%d creates=%d dpc=%.0f vs=%.0f gs=%.0f fs=%.0f "
              "paused=%s (%d samples) gpu_tot_median=%s (%d) j_per_frame=%s load=%s" % (
                  n, a["sc"], a["n"], a["bad"], a["dpn"], a["dpc"], a["dvs"], a["dgs"], a["dfs"],
                  a["paused"], a["th_n"], a["gpu_q"], a["gpu_n"], a["jpf"], a["how"]))
    ok = lambda c: "PASS" if c else "FAIL"
    cold = all(a["sc"] and "cleared" in a["sc"] for a in (B, F))
    print("V   cold both: %s; thermal pause: base %s fix %s; creates base %d fix %d (%+.0f%%)" % (
        cold, B["paused"], F["paused"], B["dpn"], F["dpn"], 100 * (F["dpn"] / B["dpn"] - 1)))
    void = not cold or B["paused"] or F["paused"]
    if void:
        print("V   VOID: L1-L3 are void; re-run the pair from a cool start")
    pb = lambda a, k: a[k] / a["dpn"]
    want = (B["dpc"] - K * B["dvs"]) / B["dpn"]
    got = pb(F, "dpc")
    print("L1  fix dpc/create %.1f ms vs model %.1f ms (base %.1f): ratio %.2f -> %s; "
          "base/fix %.2fx" % (got, want, pb(B, "dpc"), got / want,
                              ok(abs(got / want - 1) <= 0.30), pb(B, "dpc") / got))
    if B["load"] and F["load"]:
        lb = fbwin.total(B["load"], "dpc_ms")
        lbv = fbwin.total(B["load"], "dvs_ms")
        lf = fbwin.total(F["load"], "dpc_ms")
        m = lb - K * lbv
        print("L2  load dpc: base %.0f ms (%s), fix %.0f ms (%s); model %.0f ms: ratio %.2f -> %s; "
              "base/fix %.2fx" % (lb, B["how"], lf, F["how"], m, lf / m,
                                  ok(abs(lf / m - 1) <= 0.30), lb / lf))
    else:
        print("L2  load not placed on both arms (base %s, fix %s): pass --base-span/--fix-span "
              "from the route frames" % (B["how"], F["how"]))
    for k in ("dgs", "dfs"):
        r = pb(F, k) / pb(B, k) if pb(B, k) else float("nan")
        print("L3  %s per create fix/base %.2f -> %s" % (k, r, ok(0.75 <= r <= 1.33)))
    r4 = pb(B, "dvs") / pb(F, "dvs")
    print("L4  dvs per create base/fix %.2fx -> %s (registered %.1f-%.1fx)" % (
        r4, ok(6.26 / 1.3 <= r4 <= 6.26 * 1.3), 6.26 / 1.3, 6.26 * 1.3))
    if B["gpu_q"] and F["gpu_q"]:
        e = F["gpu_q"] / B["gpu_q"] - 1
        word = "no change (within 10%)" if abs(e) < 0.10 else (
            "FALLS: an energy lever too" if e < 0 else "RISES: per-vertex ALU cost")
        print("E   GPU Tot ms/frame median over play windows with dpm == 0: base %.2f fix %.2f "
              "(%+.1f%%): %s" % (B["gpu_q"], F["gpu_q"], 100 * e, word))
    else:
        print("E   no xemu-gpu lines in the play windows (base %d, fix %d): not a perflog build?" % (
            B["gpu_n"], F["gpu_n"]))
    print("E   j_per_frame (title_verdict.py on a copy): base %s fix %s" % (B["jpf"], F["jpf"]))


if __name__ == "__main__":
    main(sys.argv[1:])
