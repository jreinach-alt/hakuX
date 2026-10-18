#!/usr/bin/env python3
"""Each visibility test in a frame dump, joined to its count (#1039).

usage: vistests.py DUMP.jsonl ZREP.txt [--all] [--off HEX] [--draws]

A GET_REPORT's count is the sum of the occlusion queries since the last
CLEAR_REPORT_VALUE (reports.c ra_run: ra.sum, reset by a clear), so report R
counts the queries with serial in (qs of the last clear, qs of R]. The dump
(schema 11; r1-r5 were written as 10 before the merge with #1038's schema 10)
gives every draw's query serial ("zq") and every report's serials
("rep": rs, qs); HAKUX_ZREP gives each query's samples ("q") and each report's
value ("r"). Joined, each report says which draws it counted, with their depth
state (NV_PGRAPH_CONTROL_0), zeta and colour target, and what it came to.

Prints one line per report (nonzero ones only unless --all):
  rs off value early nq ndraws zstate zeta color draw-range
and with --draws, one line per counted draw under it.
"""
import json
import sys

ZF = "never less eq le gt ne ge always".split()


def c0_state(c0):
    c0 = int(c0, 16)
    zen = bool(c0 & (1 << 14))
    zw = bool(c0 & (1 << 24))
    cm = (c0 >> 26) & 0xF  # A R G B write enables
    return f"z{'on' if zen else 'OFF'}:{ZF[(c0 >> 16) & 7]}{':w' if zw else ''}" \
           f" cm{cm:x}"


def load_zrep(path):
    q, r, c = {}, {}, {}
    for line in open(path, errors="replace"):
        p = line.split()
        if not p:
            continue
        if p[0] == "q" and len(p) == 3:
            q[int(p[1])] = int(p[2])
        elif p[0] == "r" and len(p) == 6:
            r[int(p[1])] = (int(p[2]), p[3], int(p[4]), int(p[5]))
        elif p[0] == "c" and len(p) == 3:
            c[int(p[1])] = int(p[2])
    return q, r, c


def main():
    a = sys.argv[1:]
    show_all = "--all" in a
    show_draws = "--draws" in a
    off_f = None
    if "--off" in a:
        off_f = int(a[a.index("--off") + 1], 16)
    dump, zrep = [x for i, x in enumerate(a) if not x.startswith("--")
                  and (i == 0 or a[i - 1] != "--off")][:2]
    q, r, c = load_zrep(zrep)

    draws_by_q = {}
    reps = []
    for line in open(dump, errors="replace"):
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        t = rec.get("t")
        if t == "draw" and rec.get("zq", -1) >= 0:
            draws_by_q.setdefault(rec["zq"], []).append(rec)
        elif t == "rep":
            reps.append(rec)

    nz = nrep = nclr = missing = 0
    lo = None
    for rep in reps:
        rs, qs = rep["rs"], rep["qs"]
        if rep["clr"]:
            nclr += 1
            lo = qs
            continue
        nrep += 1
        if rs not in r:
            missing += 1
            continue
        _, off, value, early = r[rs]
        if off_f is not None and int(off, 16) != off_f:
            continue
        base = lo if lo is not None else qs
        qser = list(range(base + 1, qs + 1))
        ds = [d for s in qser for d in draws_by_q.get(s, [])]
        if value:
            nz += 1
        if not value and not show_all:
            continue
        zst = sorted({c0_state(d["rs"]["c0"]) for d in ds})
        zeta = sorted({d["zeta"]["addr"] if d.get("zeta") else "-" for d in ds})
        col = sorted({d["color"]["addr"] if d.get("color") else "-" for d in ds})
        rng = f"{ds[0]['n']}-{ds[-1]['n']}" if ds else "-"
        qsum = sum(q.get(s, 0) for s in qser)
        print(f"rs {rs} off {off} value {value} early {early} nq {len(qser)} "
              f"qsum {qsum} ndraws {len(ds)} {'/'.join(zst) or '-'} "
              f"zeta {','.join(zeta)} color {','.join(col)} draws {rng}"
              f"{'' if lo is not None else ' (no clear seen)'}")
        if show_draws:
            for d in ds:
                print(f"    n {d['n']} q {d['zq']} samples {q.get(d['zq'])} "
                      f"{d['kind']} prim {d['prim']} count {d['count']} "
                      f"{c0_state(d['rs']['c0'])} zmin {d['rs']['zmin']} "
                      f"zmax {d['rs']['zmax']} shader {d['shader']}")
    print(f"# reports {nrep} clears {nclr} nonzero {nz} "
          f"not-in-zrep {missing}")


if __name__ == "__main__":
    main()
