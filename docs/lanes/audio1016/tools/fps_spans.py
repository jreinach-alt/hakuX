#!/usr/bin/env python3
"""Median hakuX-perf gfps over a run's speech and idle spans.

  fps_spans.py RESULTS_DIR NAME=<id> ...

Spans are judge_cutscene.speech_span()'s: speech is the leading run of
letterboxed `cutscene` frames (+5 s); idle is from 12 s after the last
letterboxed frame to the last `cutscene` frame + 10 s. Prints n, median,
10th percentile and minimum gfps per span.
"""
import os
import re
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import judge_cutscene as jc  # noqa: E402

GFPS = re.compile(jc.TS + r".*hakuX-perf\(\s*\d+\): gfps=(\d+)")


def pct(x, p):
    x = sorted(x)
    return x[min(len(x) - 1, int(p * len(x)))] if x else float("nan")


def main():
    res = sys.argv[1]
    for kv in sys.argv[2:]:
        name, rid = kv.split("=", 1)
        d = os.path.join(res, rid)
        sp = jc.speech_span(d)
        cs = jc.frames(d)
        if not sp or not cs:
            print(f"{name}: no speech span")
            continue
        fps = []
        for ln in open(os.path.join(d, "logcat.txt"), errors="replace"):
            m = GFPS.match(ln)
            if m:
                fps.append((jc.secs(*m.groups()[:3]), int(m.group(4))))
        spans = {"speech": (sp[0], sp[1] + 5), "idle": (sp[1] + 12, cs[-1] + 10)}
        out = []
        for k, (a, b) in spans.items():
            x = [f for t, f in fps if a <= t <= b]
            out.append(f"{k} n={len(x)} median={statistics.median(x) if x else 'nan'} "
                       f"p10={pct(x, 0.1)} min={min(x) if x else 'nan'}")
        print(f"{name}: " + "; ".join(out))


if __name__ == "__main__":
    main()
