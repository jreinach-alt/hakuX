#!/usr/bin/env python3
"""Read the `fifoskew` line: how far ahead of PGRAPH the guest is allowed to get.

    fifo_skew_report.py RESULT_DIR_OR_LOGCAT [...]
    fifo_skew_report.py --a A/logcat.txt --b B/logcat.txt

#44 resolved to a mechanism that is a timing property of the pushbuffer path:
the texture upload for draw N reads guest memory after the guest has begun
writing iteration N+1's surface to the same address, so the draw renders with
its successor's texture. The forward model explains 12,596 of 12,596 wrong
pixels across a ten-run noise floor. What nothing had measured is the quantity
the race is a function of -- how long a published pushbuffer segment sits
unread while the guest runs on.

Two numbers answer that, and the instrument in `pfifo.c` emits both:

  `drain`   the time from the guest publishing a segment (its DMA_PUT store)
            to PGRAPH having consumed it. That IS the skew, in nanoseconds,
            and it is the width of the window in which a guest store can beat
            PGRAPH's read of the same address.

  `ring`    the guest's own DMA object limit -- the only thing that bounds the
            skew without the `HAKUX_FIFO_SKEW_BOUND` hold, since nxdk spins on
            DMA_GET only once its pushbuffer ring is full. Reported so "the
            bound today is the ring" is a number rather than a claim.

`backlog` is the same question in bytes at the instant of publication, and
`behind`/`kicks` is the share of submissions made while PGRAPH was not yet
current -- the fraction of the guest's own submissions that are exposed at
all.

The rest of the fields only become non-zero with the bound enabled: `held` is
what the guest paid for it, `spun`/`slept` splits that into the cases where
the PFIFO thread was already awake and the cases that needed a futex, and
`gave` is the number of times the bound did NOT hold because the pusher parked
stalled -- the one hole in its guarantee, counted rather than argued.
"""
import argparse
import os
import re
import sys

SKEW = re.compile(
    r"fifoskew win=(?P<win>\d+)ms kicks=(?P<kicks>\d+) "
    r"behind=(?P<behind>\d+) wrap=(?P<wrap>\d+) ring=(?P<ring>\d+) "
    r"backlog\(mean=(?P<bmean>\d+) max=(?P<bmax>\d+)\) "
    r"drain\(n=(?P<dn>\d+) mean=(?P<dmean>\d+) p50=(?P<dp50>\d+) "
    r"p90=(?P<dp90>\d+) p99=(?P<dp99>\d+) max=(?P<dmax>\d+)\) "
    r"bound=(?P<bound>\d+) "
    r"held\(n=(?P<hn>\d+) mean=(?P<hmean>\d+) max=(?P<hmax>\d+) "
    r"spun=(?P<spun>\d+) slept=(?P<slept>\d+) gave=(?P<gave>\d+)\) "
    r"lost=(?P<lost>\d+)")

GFPS = re.compile(r"gfps=(\d+)")


def resolve(path):
    """Accept a dispatch result directory or a logcat path directly."""
    if os.path.isdir(path):
        for name in ("logcat.txt", "log.txt"):
            p = os.path.join(path, name)
            if os.path.isfile(p):
                return p
        sys.exit("no logcat.txt in %s" % path)
    return path


def load(path):
    rows, gfps = [], []
    with open(resolve(path), errors="replace") as fh:
        for line in fh:
            m = SKEW.search(line)
            if m:
                rows.append({k: int(v) for k, v in m.groupdict().items()})
                continue
            m = GFPS.search(line)
            if m:
                gfps.append(int(m.group(1)))
    return rows, gfps


def pooled(rows, n_key, mean_key):
    n = sum(r[n_key] for r in rows)
    if not n:
        return 0, 0
    return n, sum(r[n_key] * r[mean_key] for r in rows) // n


def pctile(vals, p):
    if not vals:
        return 0
    v = sorted(vals)
    i = min(len(v) - 1, max(0, int(round((p / 100.0) * (len(v) - 1)))))
    return v[i]


def summarise(label, rows, gfps):
    if not rows:
        print("%s: no fifoskew lines -- this ref predates the instrument"
              % label)
        return None

    kicks = sum(r["kicks"] for r in rows)
    behind = sum(r["behind"] for r in rows)
    span_ms = sum(r["win"] for r in rows)
    _, bmean = pooled(rows, "kicks", "bmean")
    dn, dmean = pooled(rows, "dn", "dmean")
    hn, hmean = pooled(rows, "hn", "hmean")
    rings = sorted({r["ring"] for r in rows})

    print("%s" % label)
    print("  windows                    %d over %.1f s" % (len(rows),
                                                           span_ms / 1000.0))
    print("  bound enabled              %s"
          % ("yes" if any(r["bound"] for r in rows) else "no"))
    print("  pushbuffer ring (limit)    %s bytes"
          % (", ".join(str(x) for x in rings) or "unseen"))
    print("  submissions                %d  (%.0f/s)"
          % (kicks, kicks * 1000.0 / span_ms if span_ms else 0))
    print("  ... with PGRAPH behind     %d  (%.1f%%)"
          % (behind, 100.0 * behind / kicks if kicks else 0))
    print("  backlog at publish         mean %d bytes, max %d"
          % (bmean, max(r["bmax"] for r in rows)))
    print("  SKEW (publish -> consumed) n=%d mean %d ns" % (dn, dmean))
    print("                             p50 %d  p90 %d  p99 %d  max %d ns"
          % (pctile([r["dp50"] for r in rows], 50),
             pctile([r["dp90"] for r in rows], 50),
             pctile([r["dp99"] for r in rows], 50),
             max(r["dmax"] for r in rows)))
    if hn:
        print("  guest held                 n=%d mean %d ns max %d ns"
              % (hn, hmean, max(r["hmax"] for r in rows)))
        print("  ... spun / slept / gave    %d / %d / %d"
              % (sum(r["spun"] for r in rows),
                 sum(r["slept"] for r in rows),
                 sum(r["gave"] for r in rows)))
    if any(r["lost"] for r in rows):
        print("  UNTIMED submissions        %d (pending ring overflowed; the "
              "skew mean is a floor)" % sum(r["lost"] for r in rows))
    if any(r["wrap"] for r in rows):
        print("  backlog unmeasurable       %d (a pushbuffer JMP; the byte "
              "mean excludes these, the skew does not)"
              % sum(r["wrap"] for r in rows))
    if gfps:
        print("  gfps                       p50 %d  p90 %d  max %d"
              % (pctile(gfps, 50), pctile(gfps, 90), max(gfps)))
    print()
    return dict(kicks=kicks, behind=behind, span_ms=span_ms, dn=dn,
                dmean=dmean, dmax=max(r["dmax"] for r in rows),
                hn=hn, hmean=hmean,
                gave=sum(r["gave"] for r in rows),
                gfps=gfps, rows=rows)


SELFTEST_LINE = (
    "09-13 14:00:00.000  1234  1240 I hakuX-perf: "
    "fifoskew win=2000ms kicks=13402 behind=9911 wrap=3 ring=524288 "
    "backlog(mean=812 max=19488) "
    "drain(n=13399 mean=412300 p50=150000 p90=1050000 p99=4550000 "
    "max=28194013) "
    "bound=0 held(n=0 mean=0 max=0 spun=0 slept=0 gave=0) lost=0")


def selftest():
    """Check the regex against the line pfifo.c actually prints.

    A tool that reads captures and silently matches nothing reports a soak
    that emitted numbers as a soak that emitted nothing, which reads exactly
    like a failed run. That has already cost this project two falsifiers on
    one day, so the parser carries its own subject.
    """
    m = SKEW.search(SELFTEST_LINE)
    if not m:
        print("SELFTEST FAIL: the regex does not match pfifo.c's own line")
        return 1
    want = {"kicks": 13402, "behind": 9911, "ring": 524288, "dn": 13399,
            "dmean": 412300, "dmax": 28194013, "bound": 0, "lost": 0}
    got = {k: int(v) for k, v in m.groupdict().items()}
    bad = {k: (v, got[k]) for k, v in want.items() if got[k] != v}
    if bad:
        print("SELFTEST FAIL: fields misread: %r" % bad)
        return 1
    print("selftest ok: %d fields, all %d checked values correct"
          % (len(got), len(want)))
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="*")
    ap.add_argument("--a")
    ap.add_argument("--b")
    ap.add_argument("--selftest", action="store_true",
                    help="check the parser against the emitter's own format")
    args = ap.parse_args()

    if args.selftest:
        return selftest()

    if args.a and args.b:
        ra, ga = load(args.a)
        rb, gb = load(args.b)
        sa = summarise("A  %s" % args.a, ra, ga)
        sb = summarise("B  %s" % args.b, rb, gb)
        if not (sa and sb):
            return 2
        print("%-28s %14s %14s" % ("", "A", "B"))
        print("%-28s %14d %14d" % ("skew mean (ns)", sa["dmean"], sb["dmean"]))
        print("%-28s %14d %14d" % ("skew max (ns)", sa["dmax"], sb["dmax"]))
        print("%-28s %13.1f%% %13.1f%%"
              % ("submissions with PGRAPH behind",
                 100.0 * sa["behind"] / sa["kicks"] if sa["kicks"] else 0,
                 100.0 * sb["behind"] / sb["kicks"] if sb["kicks"] else 0))
        print("%-28s %14d %14d" % ("guest held mean (ns)",
                                   sa["hmean"], sb["hmean"]))
        print("%-28s %14d %14d" % ("bound gave up (count)",
                                   sa["gave"], sb["gave"]))
        # The cost, on the ceiling and never the median: #64 measured the
        # median on this queue to be a measurement of device occupancy.
        print("%-28s %14d %14d" % ("gfps p90 (the cost leg)",
                                   pctile(sa["gfps"], 90),
                                   pctile(sb["gfps"], 90)))
        print("%-28s %14d %14d" % ("gfps max",
                                   max(sa["gfps"]) if sa["gfps"] else 0,
                                   max(sb["gfps"]) if sb["gfps"] else 0))
        print("%-28s %14d %14d" % ("gfps median (NOT judged)",
                                   pctile(sa["gfps"], 50),
                                   pctile(sb["gfps"], 50)))
        return 0

    if not args.paths:
        ap.error("give one or more result dirs, or --a and --b")
    for p in args.paths:
        rows, gfps = load(p)
        summarise(p, rows, gfps)
    return 0


if __name__ == "__main__":
    sys.exit(main())
