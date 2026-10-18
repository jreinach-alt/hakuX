#!/usr/bin/env python3
"""The draws and reports of chosen frames of a dump, one compact line each (#1039).

usage: drawlist.py DUMP.jsonl ZREP.txt F [F ...] [--from N] [--tex]

Per draw: n kind prim count zq z-state cm blend-reg shader [tex0 hash];
per report: its offset and value (joined from HAKUX_ZREP by serial), so the
light tests sit in order among the draws around them. z-state is NV_PGRAPH
CONTROL_0's ZENABLE/ZFUNC/ZWRITE, cm its colour write mask (ARGB), blend the
BLEND register (bit 0..: enable and factors, as dumped). --from N skips draws
before n=N.
"""
import json
import sys

ZF = "never less eq le gt ne ge always".split()


def zs(c0):
    c0 = int(c0, 16)
    return (f"z{'on' if c0 & (1 << 14) else 'OFF'}:{ZF[(c0 >> 16) & 7]}"
            f"{':w' if c0 & (1 << 24) else ''} cm{(c0 >> 26) & 0xF:x}")


def main():
    a = sys.argv[1:]
    tex = "--tex" in a
    lo = 0
    if "--from" in a:
        lo = int(a[a.index("--from") + 1])
    pos = [x for i, x in enumerate(a) if not x.startswith("--")
           and (i == 0 or a[i - 1] != "--from")]
    dump, zrep, frames = pos[0], pos[1], {int(x) for x in pos[2:]}
    r = {}
    for line in open(zrep, errors="replace"):
        p = line.split()
        if len(p) == 6 and p[0] == "r":
            r[int(p[1])] = (p[3], int(p[4]), int(p[5]))
    for line in open(dump, errors="replace"):
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        if rec.get("f") not in frames:
            continue
        t = rec.get("t")
        if t == "draw" and rec["n"] >= lo:
            rs = rec["rs"]
            s = (f"f{rec['f']} n{rec['n']} {rec['kind']} p{rec['prim']} c{rec['count']} "
                 f"zq{rec.get('zq', -1)} {zs(rs['c0'])} bl{rs['blend']} sh{rec['shader'][:8]}")
            if tex and rec.get("tex"):
                s += " t0=" + (rec["tex"][0].get("gh") or "-")[:8]
            print(s)
        elif t == "rep":
            v = r.get(rec["rs"])
            print(f"f{rec['f']}   rep n{rec['n']} {'CLEAR' if rec['clr'] else ''} "
                  f"{('off ' + v[0] + ' = ' + str(v[1]) + (' early' if v[2] else '')) if v else ''}")
        elif t == "skip":
            print(f"f{rec['f']}   SKIP {json.dumps(rec)[:200]}")


if __name__ == "__main__":
    main()
