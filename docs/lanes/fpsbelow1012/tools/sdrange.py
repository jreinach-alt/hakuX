#!/usr/bin/env python3
"""Read a HAKUX_RANGELOG run's [sdrange] lines (lane.fpsbelow1012, NOTES.md section 10).

    sdrange.py <result id> [--after HH:MM:SS]

surface.c prints, every perflog period, a header
    [sdrange] frames=F calls=vtxV/othO shv=S inv=I full=X hz=H
and one line per (surface, caller) that a `range` download reached:
    [sdrange] s=ADDR WxH pP szN c|z [sw] [bound] by=vtx|+off n=N ex=E edge=G ovl=LO-HI last=START+SIZE
n counts that surface's downloads from that caller; ex those where one of the draw's EXACT vertex ranges overlaps
the surface (only meaningful with by=vtx and hz=1); edge those whose overlap lies inside the requested range's
first or last page. shv/inv are downloads of shelved and invalidated surfaces (not broken out per surface).

Prints totals per 60 frames over the window, then one row per (surface, caller) summed over it, largest n first,
and the hypothesis the totals read as (section 10's table): H1 by=vtx with ex << n and edge ~ n - ex; H2 by=vtx
with ex ~ n; H3 by=<offset>; H4 by=vtx with last=0+<VRAM size>.
"""
import os
import re
import sys
from collections import defaultdict

D = os.environ.get("DISPATCH_DIR", "/home/justin/hakux-work/dispatch") + "/results"
HDR = re.compile(r"\[sdrange\] frames=(\d+) calls=vtx(\d+)/oth(\d+) shv=(\d+) inv=(\d+) full=(\d+) hz=(-?\d+)")
ROW = re.compile(r"\[sdrange\] s=([0-9a-f]+) (\d+)x(\d+) p(\d+) sz(\d+) ([cz])( sw)?( bound)? by=(\S+) n=(\d+) "
                 r"ex=(\d+) edge=(\d+) ovl=([0-9a-f]+)-([0-9a-f]+) last=([0-9a-f]+)\+([0-9a-f]+)")
TS = re.compile(r"^\d\d-\d\d (\d\d:\d\d:\d\d)")


def main():
    rid = sys.argv[1]
    after = sys.argv[sys.argv.index("--after") + 1] if "--after" in sys.argv else None
    path = os.path.join(D, rid, "logcat.txt")
    tot = defaultdict(int)
    rows = {}
    hz = set()
    periods = 0
    lasts = defaultdict(int)
    for line in open(path, errors="replace"):
        if "[sdrange]" not in line:
            continue
        t = TS.match(line)
        if after and t and t.group(1) < after:
            continue
        m = HDR.search(line)
        if m:
            periods += 1
            for k, v in zip(("frames", "vtx", "oth", "shv", "inv", "full"), m.groups()[:6]):
                tot[k] += int(v)
            hz.add(int(m.group(7)))
            continue
        m = ROW.search(line)
        if not m:
            continue
        (s, w, h, p, sz, cz, sw, bound, by, n, ex, edge, lo, hi, ls, lsz) = m.groups()
        key = (s, by)
        e = rows.setdefault(key, dict(w=int(w), h=int(h), p=int(p), sz=int(sz), cz=cz, sw=bool(sw),
                                      bound=False, n=0, ex=0, edge=0, lo=int(lo, 16), hi=0, periods=0))
        e["bound"] |= bool(bound)
        e["n"] += int(n)
        e["ex"] += int(ex)
        e["edge"] += int(edge)
        e["lo"] = min(e["lo"], int(lo, 16))
        e["hi"] = max(e["hi"], int(hi, 16))
        e["periods"] += 1
        lasts[(by, int(ls, 16), int(lsz, 16))] += 1
        tot["n_" + ("vtx" if by == "vtx" else "oth")] += int(n)
        tot["ex"] += int(ex) if by == "vtx" else 0
        tot["edge_vtx"] += int(edge) if by == "vtx" else 0
    f = tot["frames"] or 1
    per = lambda k: tot[k] * 60.0 / f
    print("%s: %d periods, %d frames%s, hz=%s" % (rid, periods, tot["frames"],
                                                  " after " + after if after else "", sorted(hz)))
    print("per 60 frames: calls vtx %.0f oth %.0f | downloads by=vtx %.0f (ex %.0f, edge %.0f) by=oth %.0f | "
          "shv %.0f inv %.0f full %.0f" % (per("vtx"), per("oth"), per("n_vtx"), per("ex"), per("edge_vtx"),
                                            per("n_oth"), per("shv"), per("inv"), per("full")))
    print("%-9s %-10s %-6s %-9s %-2s %-6s %-9s %8s %8s %8s  %s" % ("surface", "dims", "pitch", "size", "cz",
                                                                   "bound", "by", "n/60f", "ex/60f",
                                                                   "edge/60f", "overlap (offset into surface)"))
    for (s, by), e in sorted(rows.items(), key=lambda kv: -kv[1]["n"]):
        print("%-9s %-10s %-6d %-9d %-2s %-6s %-9s %8.1f %8.1f %8.1f  %x-%x%s" % (
            s, "%dx%d" % (e["w"], e["h"]), e["p"], e["sz"], e["cz"] + ("s" if e["sw"] else ""),
            "yes" if e["bound"] else "", by, e["n"] * 60.0 / f, e["ex"] * 60.0 / f, e["edge"] * 60.0 / f,
            e["lo"], e["hi"], "" if s.endswith("000") or int(s, 16) % 4096 == 0 else "  (starts mid-page)"))
    print("most frequent last ranges (by, start, size): " + ", ".join(
        "%s %x+%x x%d" % (b, a, z, c) for (b, a, z), c in sorted(lasts.items(), key=lambda kv: -kv[1])[:8]))
    nv, ex, ed, no = tot["n_vtx"], tot["ex"], tot["edge_vtx"], tot["n_oth"]
    if nv + no == 0:
        print("reading: no range downloads in the window")
        return
    if no > nv:
        print("reading: H3, mostly another caller (by=<offset>)")
    elif any(b == "vtx" and z >= 0x4000000 for (b, a, z) in lasts):
        print("reading: check H4 -- a by=vtx range of >= 64 MiB (the flush path's whole-VRAM call) is present")
    if nv:
        print("by=vtx: ex/n %.2f, edge/(n-ex) %s" % (ex / nv, "%.2f" % (ed / (nv - ex)) if nv > ex else "-"))
        if 1 not in hz:
            print("reading: hz != 1, ex is not measured (HAKUX_VTX_HAZARD off)")
        elif ex < 0.2 * nv:
            print("reading: H1 (false overlap: the draw's exact ranges miss most surfaces downloaded)")
        elif ex > 0.8 * nv:
            print("reading: H2 (the draw's exact ranges reach the surfaces downloaded)")
        else:
            print("reading: mixed H1/H2")


if __name__ == "__main__":
    main()
