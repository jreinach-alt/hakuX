"""Concentration of the translated-block profile ([rr425pc] 'g:' entries) per span.

A poll or spin loop puts most of its block executions on a handful of pcs
(high top-3 share). Real compute spreads them over many pcs. For each
[rr425pc] line, print: the number of g-entries listed, the top-1 and top-3
share of the listed g-count, and the top g pc; then compare hitch spans with
baseline spans (worst frame < 100 ms).

Usage: python3 g_conc.py <logcat.txt>
"""
import re
import statistics
import sys

LINE = re.compile(r"^\d\d-\d\d (\d\d):(\d\d):(\d\d\.\d+) .*$")
PC = re.compile(r"\b([egrmo]):([0-9a-f]{8}):([0-9a-f]+):(\d+)")
PACE = re.compile(r"hakuX-pace.*max=([0-9.]+) ms=")


def tod(h, m, s):
    return int(h) * 3600 + int(m) * 60 + float(s)


def main(path):
    pace, spans = [], []
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
            if "[rr425pc]" in line:
                gs = [int(n) for kind, pc, _, n in PC.findall(line) if kind == "g"]
                if not gs:
                    continue
                gs.sort(reverse=True)
                tot = sum(gs)
                spans.append((t, len(gs), gs[0] / tot, sum(gs[:3]) / tot, tot))

    hitch, base = [], []
    for t, n, top1, top3, tot in spans:
        worst = max([mv for pt, mv in pace if t - 2.1 < pt <= t + 0.6] or [0.0])
        (hitch if worst >= 200 else base if worst < 100 else []).append((t, n, top1, top3, tot, worst))

    def med(rows, i):
        return statistics.median(r[i] for r in rows) if rows else float("nan")

    print("spans: hitch(>=200 ms) n=%d, baseline(<100 ms) n=%d" % (len(hitch), len(base)))
    print("median listed g-pcs:     hitch %5.0f   baseline %5.0f" % (med(hitch, 1), med(base, 1)))
    print("median top-1 share:      hitch %5.2f   baseline %5.2f" % (med(hitch, 2), med(base, 2)))
    print("median top-3 share:      hitch %5.2f   baseline %5.2f" % (med(hitch, 3), med(base, 3)))
    print("median g-count per span: hitch %9.0f   baseline %9.0f" % (med(hitch, 4), med(base, 4)))
    print("\nhitch spans:")
    for t, n, top1, top3, tot, worst in hitch:
        hh, rem = divmod(int(t), 3600)
        mm, ss = divmod(rem, 60)
        print("  %02d:%02d:%05.2f worst=%5.0f pcs=%3d top1=%.2f top3=%.2f g=%d" % (
            hh, mm, ss + t % 1, worst, n, top1, top3, tot))


if __name__ == "__main__":
    main(sys.argv[1])
