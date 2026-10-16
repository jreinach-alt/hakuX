#!/usr/bin/env python3
"""Read-only hourly-report section for pm/title-locations.tsv (#433). Never rebuilds the table
(a rebuild can run a multi-minute 7z xbe-cert scan; that is a background job, not an hourly read)
-- it only reads what the last `title_locations.py build` wrote and reports on it.

    title_locations_report.py [--root W]
"""
import argparse
import datetime as dt
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
H = "/home/justin/hakux-work"  # pm/ and /mnt/d live here -- matches hourly_report.sh's own $H
R = "/home/justin/hakuX"       # the folded checkout title_locations.py lands in -- hourly_report.sh's own $R


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=H, help="pm/ root (default: %s, same as hourly_report.sh's $H)" % H)
    ap.add_argument("--repo", default=R, help="checkout title_locations.py lands in (default: %s, same as hourly_report.sh's $R)" % R)
    args = ap.parse_args()

    sys.path.insert(0, os.path.join(args.repo, "docs", "testing"))
    try:
        import title_locations as tl
    except ImportError:
        print("  title_locations.py not on this checkout yet (lands with lane.locations1014's fold)")
        return 0

    p = tl.Paths(args.root)
    hdr, rows = tl.read_table(p.table)
    if hdr is None:
        print("  pm/title-locations.tsv missing or not a generated table -- run `title_locations.py build`")
        return 0
    age_s = None
    gen = tl.parse_utc(hdr.get("generated_utc"))
    if gen:
        age_s = (dt.datetime.now(dt.timezone.utc) - gen).total_seconds()
    by_loc = {}
    for r in rows:
        n, u = by_loc.setdefault(r["location"], [0, 0])
        by_loc[r["location"]][0] += 1
        if r["title_id"] == "UNRESOLVED":
            by_loc[r["location"]][1] += 1
    print("  table age: %s (%d rows)" % (("%.1f h" % (age_s / 3600) if age_s is not None else "unknown"), len(rows)))
    for loc in tl.LOCATIONS:
        n, u = by_loc.get(loc, (0, 0))
        if n:
            print("    %-10s %4d rows, %d UNRESOLVED" % (loc, n, u))
    # Mirrors cmd_dcandidates's own filter exactly (a D: row, resolved, not queued, whose
    # verified other copy is specifically on console or in d-archive) -- a broader "matches
    # any other location" count once overcounted this 94 vs. the real command's 0, because a
    # match against another D: staging dir or the Nova is not a deletion candidate.
    try:
        d_locations = {"d-archive", "d-xiso", "d-cache", "d-other"}
        cands = 0
        for r in rows:
            if r["location"] not in d_locations or r["title_id"] == "UNRESOLVED":
                continue
            other = tl.copy_exists_elsewhere(r["title_id"], r["location"], r["bytes"], rows)
            if other and other["location"] in ("console", "d-archive") and other["location"] != r["location"]:
                cands += 1
        print("  dcandidates (a D: copy verified on console/d-archive, not yet queued): %d -- see `title_locations.py dcandidates`" % cands)
    except Exception as e:
        print("  dcandidates: could not compute (%s)" % e)
    return 0


if __name__ == "__main__":
    sys.exit(main())
