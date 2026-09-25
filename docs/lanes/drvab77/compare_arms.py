#!/usr/bin/env python3
"""The arm comparison for #77's driver A/B, from the scored rates.

Separate from `score_arms.py` on purpose: that file turns result dirs into
rates and must stay usable by the next lane without inheriting this one's
verdict arithmetic. The rates below are transcribed from its output and the
run ids are in `NOTES.md`, so every number here is re-derivable by re-running
`score_arms.py` over the six result dirs.

    python3 compare_arms.py
"""
import statistics as st

# (run id suffix, per-100 rate). `t30_prev` is lane.diagsoak77's four runs
# (PR #165), same spec and device, driver read off their dumps as T30.
FULL = {
    "t30_prev": [("C3", 9.6), ("C4", 6.8), ("C5", 16.4), ("C6", 6.6)],
    "t30": [("t30-1", 9.5), ("t30-2", 5.4)],
    "t26": [("t26-1", 5.1), ("t26-2", 8.4)],
    "stock": [("stock-1", 4.8), ("stock-2", 9.2)],
}
LOWER = {
    "t30_prev": [("C3", 27.4), ("C4", 30.1), ("C5", 23.3), ("C6", 22.4)],
    "t30": [("t30-1", 23.8), ("t30-2", 16.3)],
    "t26": [("t26-1", 15.4), ("t26-2", 22.9)],
    "stock": [("stock-1", 20.2), ("stock-2", 23.7)],
}
ARMS = ("t30", "t26", "stock")


def report(name, d):
    print("== %s" % name)
    t30all = [v for _, v in d["t30_prev"] + d["t30"]]
    sd = st.stdev(t30all)
    mean30 = st.mean(t30all)
    print("  T30, all 6 runs: %s" % sorted(t30all))
    print("    mean %.2f  sd %.2f  range %.1f-%.1f"
          % (mean30, sd, min(t30all), max(t30all)))

    means = {}
    for a in ARMS:
        v = [x for _, x in d[a]]
        means[a] = st.mean(v)
        print("  %-5s (this lane): %s  mean %.2f  within-arm difference %.1f"
              % (a, v, means[a], abs(v[0] - v[1])))

    pairs = (("t30", "t26"), ("t30", "stock"), ("t26", "stock"))
    gaps = [(abs(means[a] - means[b]), a, b) for a, b in pairs]
    print("  between-arm mean gaps: %s"
          % ", ".join("%s/%s %.2f" % (a, b, g) for g, a, b in gaps))
    within = [abs(d[a][0][1] - d[a][1][1]) for a in ARMS]
    print("    largest between-arm gap %.2f vs smallest within-arm "
          "difference %.2f" % (max(g for g, _, _ in gaps), min(within)))

    # What two runs against this spread could have seen. se of a 2-run mean is
    # sd/sqrt(2); of a difference between two such means, sd. Stated as 2 se
    # because a null is only as good as the effect it could have excluded.
    se_diff = sd
    print("  sensitivity: 2 se of an arm-vs-T30 difference = %.1f per 100, "
          "%.0f%% of the T30 mean" % (2 * se_diff, 100 * 2 * se_diff / mean30))

    today = [x for a in ARMS for _, x in d[a]]
    prev = [v for _, v in d["t30_prev"]]
    print("  six runs, three drivers, one hour: %.1f-%.1f (%.2fx)"
          % (min(today), max(today), max(today) / min(today)))
    print("  four runs, ONE driver, diagsoak77:  %.1f-%.1f (%.2fx)"
          % (min(prev), max(prev), max(prev) / min(prev)))


def main():
    report("R_full (whole frame, the pre-registered primary)", FULL)
    report("R_lower (0,288,640,480, the pre-registered secondary)", LOWER)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
