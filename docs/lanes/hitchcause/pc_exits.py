"""Per [rr425w]-cadence span: the count of TB exits tagged at each top 'e:' pc,
and the IRQ14 wake count from the same span, printed for spans with IRQ14 or
a worst frame >= 200 ms (from hitchwin's pace lines).

Usage: python3 pc_exits.py <logcat.txt>
'e:' = TB exit with tag pc (rr425_pc_note, cpu-exec.c); 'g:' = a translated
block returned at its pc. The pc-profile is a per-span top list (RR425_PC_BITS
hash, so counts are kept only for the hottest entries).
"""
import re
import sys

LINE = re.compile(r"^\d\d-\d\d (\d\d):(\d\d):(\d\d\.\d+) .*$")
PC = re.compile(r"\b([egrmo]):([0-9a-f]{8}):([0-9a-f]+):(\d+)")
RRW_IDE = re.compile(r"\[rr425w\].* ([0-9a-f]{2})\.([0-9a-f]{2}):(\d+):(\d+):")
PACE = re.compile(r"hakuX-pace.*max=([0-9.]+) ms=")
RRPC = re.compile(r"\[rr425pc\]")


def tod(h, m, s):
    return int(h) * 3600 + int(m) * 60 + float(s)


def main(path):
    spans = []  # (t, {pc: count}, ide_n, pace_max_list)
    pace = []
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
            if RRPC.search(line):
                counts = {}
                for kind, pc, _, n in PC.findall(line):
                    if kind == "e":
                        counts[pc] = counts.get(pc, 0) + int(n)
                spans.append([t, counts, 0])
    # attach the IRQ14 count of the rr425w line closing at the same time (same
    # 2 s span: rr425pc and rr425w are emitted together)
    with open(path, errors="replace") as fh:
        rw = []
        for raw in fh:
            line = raw.rstrip("\n")
            m = LINE.match(line)
            if not m or "[rr425w]" not in line:
                continue
            t = tod(*m.groups())
            ide = 0
            for vv, uu, cn, _ in RRW_IDE.findall(line):
                if vv == "3e" and uu == "00":
                    ide = int(cn)
            rw.append((t, ide))
    for s in spans:
        near = [ide for (t, ide) in rw if abs(t - s[0]) < 1.2]
        s[2] = near[0] if near else 0

    hot = ["80014385", "8001b02e", "80014f31", "8001440b", "80014158"]
    print("t        IRQ14  pace>=200  " + "  ".join("e:%s" % h for h in hot))
    for t, counts, ide in spans:
        worst = max([mv for pt, mv in pace if t - 2.1 < pt <= t + 0.6] or [0.0])
        if ide == 0 and worst < 200:
            continue
        hh, rem = divmod(int(t), 3600)
        mm, ss = divmod(rem, 60)
        print("%02d:%02d:%05.2f %6d  %9.0f  %s" % (
            hh, mm, ss + t % 1, ide, worst,
            "  ".join("%11d" % counts.get(h, 0) for h in hot)))
    # baseline median over spans with no IRQ14 and worst < 100
    base = [c for t, c, ide in spans if ide == 0 and max([mv for pt, mv in pace if t - 2.1 < pt <= t + 0.6] or [0.0]) < 100]
    if base:
        for h in hot:
            vals = sorted(c.get(h, 0) for c in base)
            print("baseline (no IRQ14, worst<100, n=%d) e:%s median=%d" % (len(base), h, vals[len(vals) // 2]))


if __name__ == "__main__":
    main(sys.argv[1])
