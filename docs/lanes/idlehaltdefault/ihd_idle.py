#!/usr/bin/env python3
"""Guest idle share and flipless time per run, over the judge's window.

    ihd_idle.py RESULT_ID [RESULT_ID ...]

Reads the copies ihd_judge.py made (docs/lanes/idlehaltdefault/.copies), so
run the judge first. Window: the first `mark gameplay` (else `mark play`) to
`soak end`, the same one every leg is read over. Descriptive, not a leg.

Per run:
  - idle share: sum of `[rr425w]` idle_us over idle_us + busy_us.
  - no-flip seconds: the stretches of more than 8 s between two 60-flip perf
    lines, summed, with each stretch's start (seconds after the mark), length
    and the guest idle share inside it.
  - slept share (halt on): sum of `[idlehalt]` slept_us over span_us.
"""
import os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(HERE, "..", "..", "testing")))
import title_verdict as tv  # noqa: E402

COPIES = os.path.join(HERE, ".copies")


def kv(msg):
    return dict(re.findall(r"(\w+)=([^\s\[\],]+)", msg))


def num(d, k):
    try:
        return float(d.get(k, 0))
    except ValueError:
        return 0.0


def share(rows, lo, hi):
    idle = sum(i for t, i, b in rows if lo <= t <= hi)
    busy = sum(b for t, i, b in rows if lo <= t <= hi)
    return idle / (idle + busy) if idle + busy else None


def fmt(x):
    return "-" if x is None else "%.2f" % x


for rid in sys.argv[1:]:
    dst = os.path.join(COPIES, rid)
    if not os.path.isfile(os.path.join(dst, "logcat.txt")):
        print(rid, "VOID: no copy (run ihd_judge.py first)")
        continue
    lc, gaps, _ = tv.parse_logcat(os.path.join(dst, "logcat.txt"))
    marks = [(t, m[5:].strip()) for t, lv, tag, m in lc if tag == "hakuX-route" and m.startswith("mark ")]
    gp = [t for t, m in marks if m == "gameplay"] or [t for t, m in marks if m == "play"]
    if not gp:
        print(rid, "VOID: no mark gameplay/play")
        continue
    end = [t for t, lv, tag, m in lc if tag == "hakuX-route" and m.strip() == "soak end"]
    lo, hi = gp[0], (end[-1] if end else lc[-1][0])
    rr, slept, span = [], 0.0, 0.0
    for t, lv, tag, m in lc:
        if "[rr425w]" in m:
            d = kv(m)
            rr.append((t, num(d, "idle_us"), num(d, "busy_us")))
        elif "[idlehalt]" in m and lo <= t <= hi:
            d = kv(m)
            slept += num(d, "slept_us")
            span += num(d, "span_us")
    perf = [t for t, lv, tag, m in lc if tag == "hakuX-perf" and tv.PERF.search(m) and lo <= t <= hi]
    pts = [lo] + perf + [hi]
    longs = [(a, b) for a, b in zip(pts, pts[1:]) if b - a > 8]
    print("%s window %.0f s  idle share %s  slept share %s  no-flip %.0f s %s" % (
        rid, hi - lo, fmt(share(rr, lo, hi)), fmt(slept / span if span else None),
        sum(b - a for a, b in longs),
        ["%d s +%.1f s idle %s" % (a - lo, b - a, fmt(share(rr, a, b))) for a, b in longs]))
