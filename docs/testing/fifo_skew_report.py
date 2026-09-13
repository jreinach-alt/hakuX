#!/usr/bin/env python3
"""Read the `fifoskew` line: how far ahead of PGRAPH the guest is allowed to get.

    fifo_skew_report.py RESULT_DIR_OR_LOGCAT [...]
    fifo_skew_report.py --a A1/logcat.txt --a A2/logcat.txt \
                        --b B1/logcat.txt --b B2/logcat.txt

`--a` and `--b` are repeatable, one per RUN of the arm. A soak has no oracle,
so a claim from a single run is a one-sample noise floor, and the replicate is
the run rather than the window: the performance lane measured absolute
per-window counts varying 3-5x inside one soak, so a figure pooled over a
run's windows is a property of that run. Every figure below is printed per
run, and the cost comparison is worst-case across the cross product.

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
import glob
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
    # The selective bound's pre-scan, and the `gave` split. BOTH OPTIONAL, and
    # that is not laziness: three line shapes are in flight at once and all
    # three have to be readable by one tool. The mode-1 arms
    # (1789303629-skew-bound-cost-*) have neither group, the draw-only
    # mechanism commit has `scan(` and not `gaveby(`, and the tip has both.
    # A tool that could only read the newest shape would report the published
    # comparison as a soak that emitted nothing.
    r"(?:scan\(n=(?P<sn>\d+) words=(?P<swords>\d+) wmax=(?P<swmax>\d+) "
    r"ns=(?P<sns>\d+) draw=(?P<sdraw>\d+) nodraw=(?P<snodraw>\d+) "
    r"wrap=(?P<swrap>\d+) big=(?P<sbig>\d+)\) )?"
    r"(?:gaveby\(flip=(?P<gflip>\d+) nop=(?P<gnop>\d+) "
    r"ctxsw=(?P<gctxsw>\d+) noaccess=(?P<gnoaccess>\d+) "
    r"other=(?P<gother>\d+)\) )?"
    r"lost=(?P<lost>\d+)")

GFPS = re.compile(r"gfps=(\d+)")


def resolve(path):
    """Accept a dispatch result directory or a logcat path directly.

    A dispatcher result holds `logcat.txt` for a soak and `logcat<N>.txt` per
    run for a multi-run disc request, and callers pass both shapes. Getting
    this wrong is the failure AGENTS.md records twice: a tool that reads a
    result directory and silently finds nothing reports a run full of numbers
    as a run that emitted none, which reads exactly like a failed render. So
    every candidate is returned and the caller reads all of them, and a
    directory with no logcat at all is an error rather than an empty answer.
    """
    if not os.path.isdir(path):
        return [path]
    named = [os.path.join(path, n) for n in ("logcat.txt", "log.txt")]
    found = [p for p in named if os.path.isfile(p)]
    if not found:
        found = sorted(glob.glob(os.path.join(path, "logcat*.txt")),
                       key=lambda p: int("".join(c for c in
                                                 os.path.basename(p)
                                                 if c.isdigit()) or 0))
    if not found:
        sys.exit("no logcat.txt or logcat<N>.txt in %s" % path)
    return found


def load(path):
    rows, gfps = [], []
    for f in resolve(path):
        with open(f, errors="replace") as fh:
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
        print("SELFTEST FAIL: the regex does not match the frozen sample")
        return 1
    want = {"kicks": 13402, "behind": 9911, "ring": 524288, "dn": 13399,
            "dmean": 412300, "dmax": 28194013, "bound": 0, "lost": 0}
    got = {k: int(v) for k, v in m.groupdict().items() if v is not None}
    bad = {k: (v, got.get(k)) for k, v in want.items() if got.get(k) != v}
    if bad:
        print("SELFTEST FAIL: fields misread: %r" % bad)
        return 1

    rc = selftest_against_source()
    if rc:
        return rc
    print("selftest ok: %d fields on the frozen sample, and every field the "
          "live pfifo.c prints is accounted for" % len(got))
    return 0


def selftest_against_source():
    """Check the regex against the format string `pfifo.c` ACTUALLY prints.

    This function exists because the docstring above it was false. The
    selftest checked a FROZEN SAMPLE LINE held in this file, so when the
    `fifoskew` line gained `scan(...)` and `gaveby(...)` the regex stopped
    matching the real thing and the selftest went on reporting ok. A reader
    that silently matches nothing reports a soak full of numbers as a soak
    that emitted none -- which is exactly what this tool's own comment warns
    about, and it was one arm away from happening to the draw-only cost pair.

    "The parser carries its own subject" has to mean the SOURCE, not a copy
    of the source taken once. So: lift the format string out of pfifo.c,
    synthesise a line from it, and require the regex to match that and to
    account for every `name=` token in it.
    """
    import os
    here = os.path.dirname(os.path.abspath(__file__))
    src = os.path.join(here, "..", "..", "hw", "xbox", "nv2a", "pfifo.c")
    try:
        text = open(src, errors="replace").read()
    except OSError as exc:
        print("SELFTEST FAIL: cannot read pfifo.c: %s" % exc)
        return 1

    i = text.find('"fifoskew win=')
    if i < 0:
        print("SELFTEST FAIL: pfifo.c no longer prints a fifoskew line")
        return 1

    # Gather the adjacent string literals that make up the format string.
    fmt, j = "", i
    while True:
        a = text.find('"', j)
        if a < 0:
            break
        b = a + 1
        while b < len(text) and (text[b] != '"' or text[b - 1] == "\\"):
            b += 1
        chunk = text[a + 1:b]
        fmt += chunk
        # Stop once the statement's argument list begins.
        rest = text[b + 1:b + 40]
        if "," in rest.split("\n")[0] and '"' not in rest.split(",")[0]:
            break
        j = b + 1
        if text[j:].lstrip()[:1] != '"':
            break

    line = re.sub(r"%(?:ll|l)?[dux]", "7", fmt)
    line = "09-13 15:00:00.000 1 2 I hakuX-perf: " + line

    if not SKEW.search(line):
        print("SELFTEST FAIL: the regex does NOT match the line pfifo.c "
              "prints. Format string synthesised as:\n  %s" % line)
        return 1

    # Every `name=` token in the source line must be captured, or explicitly
    # known to be ignored. This is the check that would have caught the
    # scan(...) addition.
    tokens = set(re.findall(r"([A-Za-z_][A-Za-z0-9_]*)=", fmt))
    captured = set(SKEW.groupindex)
    alias = {"win": "win", "mean": None, "max": None, "n": None,
             "p50": None, "p90": None, "p99": None, "flip": "gflip",
             "nop": "gnop", "ctxsw": "gctxsw", "noaccess": "gnoaccess",
             "other": "gother", "words": "swords", "wmax": "swmax",
             "ns": "sns", "draw": "sdraw", "nodraw": "snodraw",
             "big": "sbig"}
    missing = []
    for t in sorted(tokens):
        if t in captured:
            continue
        if t in alias:
            a = alias[t]
            if a is None or a in captured:
                continue
        missing.append(t)
    if missing:
        print("SELFTEST FAIL: pfifo.c prints fields this reader does not "
              "account for: %s" % ", ".join(missing))
        return 1
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="*")
    ap.add_argument("--a", action="append", help="arm A logcat; repeatable")
    ap.add_argument("--b", action="append", help="arm B logcat; repeatable")
    ap.add_argument("--selftest", action="store_true",
                    help="check the parser against the emitter's own format")
    args = ap.parse_args()

    if args.selftest:
        return selftest()

    if args.a and args.b:
        SA = [summarise("A  %s" % p, *load(p)) for p in args.a]
        SB = [summarise("B  %s" % p, *load(p)) for p in args.b]
        if not all(SA) or not all(SB):
            return 2

        def col(rows, f):
            return "".join("%14s" % f(r) for r in rows)

        w = max(len(SA), len(SB))
        print("%-3s %-30s%s" % ("", "", "".join("%14s" % ("run %d" % (i + 1))
                                                for i in range(w))))
        for arm, rows in (("A", SA), ("B", SB)):
            for label, f in (
                ("submissions/s", lambda r: "%d" % (r["kicks"] * 1000
                                                     // max(r["span_ms"], 1))),
                ("PGRAPH behind (%)", lambda r: "%.1f" % (
                    100.0 * r["behind"] / r["kicks"] if r["kicks"] else 0)),
                ("SKEW mean (ns)", lambda r: "%d" % r["dmean"]),
                ("SKEW max (ns)", lambda r: "%d" % r["dmax"]),
                ("guest held mean (ns)", lambda r: "%d" % r["hmean"]),
                ("guest held (n)", lambda r: "%d" % r["hn"]),
                ("bound gave up (n)", lambda r: "%d" % r["gave"]),
                ("gfps p90 / max / p50", lambda r: "%d/%d/%d" % (
                    pctile(r["gfps"], 90), max(r["gfps"]) if r["gfps"] else 0,
                    pctile(r["gfps"], 50))),
            ):
                print("%-3s %-30s%s" % (arm, label, col(rows, f)))
            print()

        # C1, the cost leg: the CEILING and never the median, worst case across
        # the cross product. #64 measured the median on this queue to be a
        # measurement of device occupancy, and the performance lane has since
        # shown two Galleon soaks on one device at medians 27 and 17 with an
        # identical p90 of 29 and max of 29.
        pa = max(pctile(r["gfps"], 90) for r in SA)
        pb_ = min(pctile(r["gfps"], 90) for r in SB)
        xa = max(max(r["gfps"]) if r["gfps"] else 0 for r in SA)
        xb = min(max(r["gfps"]) if r["gfps"] else 0 for r in SB)
        print("C1  gfps p90 best-A %d vs worst-B %d (fall %d, max allowed 2)"
              % (pa, pb_, pa - pb_))
        print("C1  gfps max best-A %d vs worst-B %d (fall %d, max allowed 2)"
              % (xa, xb, xa - xb))
        print("C1  %s" % ("HOLDS" if (pa - pb_) <= 2 and (xa - xb) <= 2
                          else "FAILS"))
        # C2, did it execute.
        fr = min(r["hn"] / float(r["kicks"]) if r["kicks"] else 0 for r in SB)
        print("C2  arm B held(n)/kicks, worst run %.3f (need >= 0.90)  %s"
              % (fr, "HOLDS" if fr >= 0.90 else "FAILS"))
        return 0

    if not args.paths:
        ap.error("give one or more result dirs, or --a and --b")
    for p in args.paths:
        rows, gfps = load(p)
        summarise(p, rows, gfps)
    return 0


if __name__ == "__main__":
    sys.exit(main())
