#!/usr/bin/env python3
"""Gate 4, post hoc: pair the two arms' [shd413] create windows by content.

    doa_matched.py <base result dir> <fix result dir>

The survey route's menu presses land differently in each arm, so the arms load
different fighters and their whole-run and fight-load sums compare different
work. A window whose kd vector (keys that differ from the previous pipeline, by
stage) and create count dpn are the same in both arms is taken as the same
load. Windows are paired in order of appearance, first match wins. Written after
the pair ran; it is a reading beside the registered legs, not one of them.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "shaderfb569"))
import fbwin  # noqa: E402

K = 1 - 1 / 6.26


def creates(d):
    lc, _ = fbwin.logcat_of(d)
    wins, _, _ = fbwin.parse(open(lc, errors="replace").read().splitlines())
    return [w for w in wins if w["dpn"] >= 1]


def main(bd, fd):
    b, f = creates(bd), creates(fd)
    used, pairs = set(), []
    for wb in b:
        for j, wf in enumerate(f):
            if j not in used and wf["kd"] == wb["kd"] and wf["dpn"] == wb["dpn"]:
                used.add(j)
                pairs.append((wb, wf))
                break
    print("%-12s %-12s %3s %-26s %8s %8s %6s %7s %7s %6s %6s" % (
        "base", "fix", "n", "kd", "dpc_b", "dpc_f", "b/f", "dvs_b", "dvs_f", "vs b/f", "model"))
    tot = dict(dpc_b=0.0, dpc_f=0.0, dvs_b=0.0, dvs_f=0.0, dgs_b=0.0, dgs_f=0.0, n=0)
    for wb, wf in pairs:
        model = wb["dpc_ms"] - K * wb["dvs_ms"]
        print("%-12s %-12s %3d %-26s %8.0f %8.0f %6.2f %7.0f %7.0f %6s %6.2f" % (
            wb["hms"], wf["hms"], wb["dpn"], ",".join("%d" % x for x in wb["kd"]),
            wb["dpc_ms"], wf["dpc_ms"], wb["dpc_ms"] / max(wf["dpc_ms"], 0.1),
            wb["dvs_ms"], wf["dvs_ms"],
            "%.2f" % (wb["dvs_ms"] / wf["dvs_ms"]) if wf["dvs_ms"] > 0 else "-",
            wf["dpc_ms"] / model if model > 0 else float("nan")))
        tot["n"] += wb["dpn"]
        for k, s in (("dpc_ms", "dpc"), ("dvs_ms", "dvs"), ("dgs_ms", "dgs")):
            tot[s + "_b"] += wb[k]
            tot[s + "_f"] += wf[k]
    model = tot["dpc_b"] - K * tot["dvs_b"]
    print("matched: %d pairs, %d creates each; base %d of %d creates, fix %d of %d" % (
        len(pairs), tot["n"], tot["n"], sum(w["dpn"] for w in b), tot["n"], sum(w["dpn"] for w in f)))
    print("matched dpc: base %.0f fix %.0f ms -> %.2fx; model %.0f ms, fix/model %.2f" % (
        tot["dpc_b"], tot["dpc_f"], tot["dpc_b"] / tot["dpc_f"], model, tot["dpc_f"] / model))
    print("matched dvs: base %.0f fix %.0f ms -> %.2fx; dgs %.0f -> %.0f (%.2f)" % (
        tot["dvs_b"], tot["dvs_f"], tot["dvs_b"] / tot["dvs_f"], tot["dgs_b"], tot["dgs_f"],
        tot["dgs_f"] / tot["dgs_b"]))


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
