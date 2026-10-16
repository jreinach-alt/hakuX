#!/usr/bin/env python3
"""Which runs pay `range` finishes for downloads the range lookup did not record (lane.fpsbelow1012, NOTES.md
section 11).

pgraph_vk_download_surfaces_in_range_if_dirty() (vk/surface.c) completes every pending download when the looked-up
range overlaps ANY surface (`found_overlap`, draw_dirty or not) and a download is pending, or when the range
overlaps a pending download's destination (deferred_downloads_overlap_range). Since forza414 an eviction's download
waits for the next finish (surface_update_may_defer_downloads), so a lookup that only touches a clean surface
completes a batch it does not read. `[sdcall] range=finF/.../dlD/Wms` counts the finishes, the downloads they
completed and the wait. A range lookup that records its own downloads completes them one finish each (MC3: dl ~ fin);
a batch recorded by evictions completes several per finish (dl/fin >> 1). `scdl` (hakuX-stall txr) is the texture
scan's own downloads.

Usage: rangefin.py [--since <epoch>] [--all]   One row per run with [sdcall] lines after --since (default: the
fastpaths fold, 2026-10-11 16:13 UTC): title, run, windows, medians per 60 frames of range fin, range dl, dl/fin,
range wait ms, scan dl, su_deferred; rows with range wait >= 120 ms per 60 frames unless --all.
`tools/rangefin.out` is sdrange.py on Forza's master run, then this with `--since 1791450000` (10-08);
`tools/rangefin-all.out` is the same with --all.
"""
import json
import os
import re
import statistics
import sys

RES = os.environ.get("DISPATCH_DIR", "/home/justin/hakux-work/dispatch") + "/results"
SINCE = int(sys.argv[sys.argv.index("--since") + 1]) if "--since" in sys.argv else 1791735180
ALL = "--all" in sys.argv
RNG = re.compile(r"range=fin(\d+)/fence(\d+)/pre(\d+)/dl(\d+)/([\d.]+)ms")
FR = re.compile(r"\[sdcall\] frames=(\d+)")
SUD = re.compile(r"su_deferred=(\d+)")
SCDL = re.compile(r"scdl(\d+)")


def med(xs):
    return statistics.median(xs) if xs else 0


def epoch_of(rid):
    m = re.search(r"(?:^|-)(17\d{8})-", rid)
    return int(m.group(1)) if m else 0


def scan(d):
    rows, scdl = [], []
    try:
        f = open(os.path.join(d, "logcat.txt"), errors="replace")
    except OSError:
        return None
    for line in f:
        if "[sdcall]" in line:
            fr = FR.search(line)
            if not fr or int(fr.group(1)) < 50:
                continue
            k = 60.0 / int(fr.group(1))
            m = RNG.search(line)
            s = SUD.search(line)
            fin, dl, w = (int(m.group(1)), int(m.group(4)), float(m.group(5))) if m else (0, 0, 0.0)
            rows.append((fin * k, dl * k, w * k, (int(s.group(1)) * k) if s else 0))
        elif "txr[" in line:
            m = SCDL.search(line)
            if m:
                scdl.append(int(m.group(1)))
    return rows, scdl


def main():
    out = []
    for rid in sorted(os.listdir(RES)):
        if epoch_of(rid) < SINCE:
            continue
        d = os.path.join(RES, rid)
        r = scan(d)
        if not r or not r[0]:
            continue
        rows, scdl = r
        # the busy half: windows at or above the run's median range wait
        ws = sorted(rows, key=lambda x: x[2])
        busy = ws[len(ws) // 2:]
        fin, dl, w, sud = (med([x[i] for x in busy]) for i in range(4))
        if w < 120 and not ALL:
            continue
        try:
            title = json.load(open(os.path.join(d, "request.json"))).get("title", "?")
        except (OSError, ValueError):
            title = "?"
        out.append((title[:38], rid, len(rows), fin, dl, dl / fin if fin else 0, w, med(scdl), sud))
    for t in sorted(out, key=lambda x: (x[0], x[1])):
        print("%-38s %-48s n%-4d fin%-6.0f dl%-6.0f dl/fin %-5.1f wait %6.0f ms  scdl %-5.0f su_def %.0f" % t)


main()
