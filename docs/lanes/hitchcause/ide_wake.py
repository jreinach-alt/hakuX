"""Test the IRQ14 (vector 0x3e, the Xbox primary IDE channel) wake burst
against the worst frame, over the whole hold.

[rr425w] keys its buckets by vec | units<<8 (cpu-exec.c rrw_wake). Printed as
"vv.uu": vector vv, NV2A units uu. 0x30 is IRQ0 (PIT), 0x3e is IRQ14 (IDE
primary), 0x33.44 is IRQ3 with NV2A units. A bucket's busy_us is the busy time
that followed wakes of that key (until the next idle halt).

For each [rr425w] line (2 s) print the IRQ14 wake count and busy, and the
largest hakuX-pace max among the pace windows that close within the same span.
Stdlib only. Usage: python3 ide_wake.py <logcat.txt>
"""
import re
import sys

LINE = re.compile(r"^\d\d-\d\d (\d\d):(\d\d):(\d\d\.\d+) .*$")
RRW = re.compile(r"\[rr425w\] w=(\d+) idlepc=\w+ idle_us=(\d+) busy_us=(\d+) n=(\d+) nb=(\d+) drop=(\d+)(.*)$")
BKT = re.compile(r" ([0-9a-f]{2})\.([0-9a-f]{2}):(\d+):(\d+):(\d+):")
PACE = re.compile(r"hakuX-pace.*max=([0-9.]+) ms=")


def tod(h, m, s):
    return int(h) * 3600 + int(m) * 60 + float(s)


def main(path):
    rrw = []   # (t, ide_n, ide_busy_ms, busy_ms, other)
    pace = []  # (t, max)
    with open(path, errors="replace") as fh:
        for raw in fh:
            line = raw.rstrip("\n")
            m = LINE.match(line)
            if not m:
                continue
            t = tod(*m.groups())
            p = PACE.search(line)
            if p:
                pace.append((t, float(p.group(1))))
                continue
            r = RRW.search(line)
            if not r:
                continue
            w, idle, busy, n, nb, drop, rest = r.groups()
            ide_n = ide_busy = 0
            buckets = {}
            for vv, uu, cn, bi, bb in re.findall(r" ([0-9a-f]{2})\.([0-9a-f]{2}):(\d+):(\d+):(\d+)", rest):
                buckets[(vv, uu)] = (int(cn), int(bb))
                if vv == "3e" and uu == "00":
                    ide_n, ide_busy = int(cn), int(bb) / 1000.0
            rrw.append((t, ide_n, ide_busy, int(busy) / 1000.0, buckets))

    print("t(PDT)       IRQ14_n  IRQ14_busy_ms  busy_ms  pace_max_ms(window closing in span)")
    for t, ide_n, ide_busy, busy, _ in rrw:
        # the 2 s rr425w span is (t-2.1, t]; take every pace window closing in it
        mx = [mv for pt, mv in pace if t - 2.1 < pt <= t + 0.6]
        hh, rem = divmod(int(t), 3600)
        mm, ss = divmod(rem, 60)
        print("%02d:%02d:%05.2f  %7d  %13.0f  %7.0f  %s" % (
            hh, mm, ss + t % 1, ide_n, ide_busy, busy,
            ("%.0f" % max(mx)) if mx else "-"))

    # Correlation test: IRQ14 busy versus the worst frame in the span
    xs, ys = [], []
    for t, ide_n, ide_busy, busy, _ in rrw:
        mx = [mv for pt, mv in pace if t - 2.1 < pt <= t + 0.6]
        if mx:
            xs.append(ide_busy)
            ys.append(max(mx))
    n = len(xs)
    if n > 2:
        mx_, my_ = sum(xs) / n, sum(ys) / n
        sxy = sum((x - mx_) * (y - my_) for x, y in zip(xs, ys))
        sxx = sum((x - mx_) ** 2 for x in xs)
        syy = sum((y - my_) ** 2 for y in ys)
        r = sxy / ((sxx * syy) ** 0.5) if sxx and syy else float("nan")
        print("\nspans n=%d  r(IRQ14_busy_ms, worst_frame_ms)=%.3f" % (n, r))
        big = [(x, y) for x, y in zip(xs, ys) if y >= 200]
        small = [(x, y) for x, y in zip(xs, ys) if y < 100]
        if big:
            print("IRQ14 busy median, spans with worst >= 200 ms: %.0f ms (n=%d)" % (
                sorted(x for x, _ in big)[len(big) // 2], len(big)))
        if small:
            print("IRQ14 busy median, spans with worst < 100 ms:  %.0f ms (n=%d)" % (
                sorted(x for x, _ in small)[len(small) // 2], len(small)))


if __name__ == "__main__":
    main(sys.argv[1])
