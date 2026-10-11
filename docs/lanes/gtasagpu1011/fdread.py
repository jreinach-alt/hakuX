#!/usr/bin/env python3
"""Read a schema-4 live frame dump (framedump_<id>.jsonl) by draw.

  fdread.py DUMP targets            colour targets per frame, draws on each
  fdread.py DUMP draws F [A [B]]    frame F's draws A..B, state decoded
  fdread.py DUMP rtt                draws sampling a rendered surface, and
                                    draws sampling their own colour target
  fdread.py DUMP shader HASH        one shader record (combiners + GLSL)

The registers are written raw by fdump_log_draw_state (vk/renderer.c); the
decode here follows nv2a_regs.h and nv2a_diag_log_draw_call.
"""
import json
import sys
from collections import Counter, defaultdict

BF = ["0", "1", "SC", "1-SC", "SA", "1-SA", "DA", "1-DA", "DC", "1-DC",
      "SAS", "?11", "CC", "1-CC", "CA", "1-CA"]
EQ = ["SUB", "RSUB", "ADD", "MIN", "MAX", "RSUBS", "ADDS", "?7"]
FN = ["NEVER", "LT", "EQ", "LE", "GT", "NE", "GE", "ALWAYS"]
SOP = ["?0", "KEEP", "ZERO", "REPL", "INCS", "DECS", "INV", "INC", "DEC"]


def h(v):
    return int(v, 16) if isinstance(v, str) else v


def load(path):
    session, draws, frames, shaders = None, [], [], {}
    with open(path) as f:
        for line in f:
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            t = r.get("t")
            if t == "session":
                session = r
            elif t == "draw":
                draws.append(r)
            elif t == "frame":
                frames.append(r)
            elif t == "shader":
                shaders[r["shader"]] = r
    return session, draws, frames, shaders


def state(d):
    rs = d.get("rs") or {}
    c0, c1, c2 = h(rs.get("c0", 0)), h(rs.get("c1", 0)), h(rs.get("c2", 0))
    bl, sr = h(rs.get("blend", 0)), h(rs.get("sr", 0))
    out = []
    if bl & 8:
        out.append("blend %s*S %s %s*D" % (BF[(bl >> 4) & 15], EQ[bl & 7],
                                          BF[(bl >> 8) & 15]))
    else:
        out.append("noblend")
    if c0 & (1 << 14):
        out.append("z%s%s" % (FN[(c0 >> 16) & 7], "+w" if c0 & (1 << 24) else ""))
    else:
        out.append("noz" + ("+w" if c0 & (1 << 24) else ""))
    if c1 & 1:
        out.append("st %s ref%02x rm%02x wm%02x f/zf/zp %s/%s/%s" % (
            FN[(c1 >> 4) & 7], (c1 >> 8) & 255, (c1 >> 16) & 255,
            (c1 >> 24) & 255, SOP[min(c2 & 15, 8)],
            SOP[min((c2 >> 4) & 15, 8)], SOP[min((c2 >> 8) & 15, 8)]))
    m = "".join(ch for ch, b in (("R", 27), ("G", 28), ("B", 29), ("A", 26))
                if c0 & (1 << b))
    out.append("mask " + (m or "-"))
    if c0 & (1 << 12):
        out.append("atest %s %02x" % (FN[(c0 >> 8) & 7], c0 & 255))
    if sr & (1 << 28):
        out.append("cull %s" % ["?", "F", "B", "FB"][(sr >> 21) & 3])
    return " ".join(out)


def texs(d):
    out = []
    for t in d.get("tex", []):
        if not t.get("en"):
            continue
        fmt = h(t["fmt"])
        s = "t%d@%s c%02x %dx%d" % (t["s"], t["off"], (fmt >> 8) & 0x7f,
                                   1 << ((fmt >> 20) & 15),
                                   1 << ((fmt >> 24) & 15))
        srf = t.get("srf")
        if srf:
            s += " SRF[%dx%d f%d %s%s%s%s%s]" % (
                srf["w"], srf["h"], srf["fmt"],
                "col" if srf["color"] else "zeta",
                " swz" if srf["swizzle"] else "",
                " dirty" if srf["dirty"] else "",
                " upl" if srf["upl"] else "",
                " dlp" if srf["dlp"] else "")
        if t.get("s2t"):
            s += " s2t"
        out.append(s)
    return " | ".join(out)


def tgt(d):
    c = d.get("color")
    return (c["addr"], c["w"], c["h"], c["fmt"], c["swizzle"]) if c else None


def main(argv):
    if len(argv) < 3:
        print(__doc__)
        return 2
    session, draws, frames, shaders = load(argv[1])
    cmd = argv[2]
    print("schema=%s draws=%d frames=%d shaders=%d" % (
        session and session.get("schema"), len(draws), len(frames),
        len(shaders)))
    if cmd == "targets":
        per = defaultdict(Counter)
        for d in draws:
            per[d["f"]][tgt(d)] += 1
        for f in sorted(per):
            print("f%d: %s" % (f, ", ".join(
                "%s %sx%s f%s%s: %d" % (k[0], k[1], k[2], k[3],
                                        " swz" if k[4] else "", n)
                if k else "none: %d" % n for k, n in per[f].items())))
    elif cmd == "draws":
        f = int(argv[3])
        a = int(argv[4]) if len(argv) > 4 else 0
        b = int(argv[5]) if len(argv) > 5 else 10 ** 9
        for d in draws:
            if d["f"] != f or not a <= d["n"] <= b:
                continue
            t = tgt(d)
            z = d.get("zeta")
            print("n%-5d %-6s %5d prim%d sh %s -> %s%s | %s | %s" % (
                d["n"], d["kind"], d["count"], d["prim"], d["shader"][:8],
                "%s %sx%s f%s" % t[:4] if t else "-",
                " z%s" % z["addr"] if z else " noz",
                state(d), texs(d)))
    elif cmd == "rtt":
        for d in draws:
            t = tgt(d)
            hits = []
            for x in d.get("tex", []):
                if not x.get("en"):
                    continue
                own = t and h(x["off"]) == h(t[0])
                if x.get("srf") or own:
                    hits.append(x)
            if hits:
                own = any(t and h(x["off"]) == h(t[0]) for x in hits)
                print("f%d n%-5d -> %s %sx%s%s | %s | %s" % (
                    d["f"], d["n"], t[0] if t else "-", t[1] if t else "",
                    t[2] if t else "", " FEEDBACK" if own else "",
                    state(d), texs(d)))
    elif cmd == "shader":
        s = shaders.get(argv[3]) or next(
            (v for k, v in shaders.items() if k.startswith(argv[3])), None)
        if not s:
            print("no such shader")
            return 1
        for k, v in s.items():
            if k in ("vsh", "geom", "psh"):
                print("---- %s ----\n%s" % (k, v))
            else:
                print("%s: %s" % (k, v))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
