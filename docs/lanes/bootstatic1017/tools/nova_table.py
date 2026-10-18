#!/usr/bin/env python3
"""The Nova before/after table for #1045: judge_nova.judge on every finished request in nova_ids.tsv (the dispatcher
may have renamed a request with a priority prefix, so each id is found with any prefix), plus 1792282757.

usage: nova_table.py [--sheets DIR]
"""
import glob
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import judge_nova as jn  # noqa: E402

D = "/home/justin/hakux-work/dispatch/results"
IDS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "nova_ids.tsv")
EXTRA = [("before", "7ea8b80e71", "Halo CE (Blam), first run", "1792282757-lane.bootstatic1017-1714214")]


def rows_of_ids():
    out = list(EXTRA)
    for line in open(IDS):
        m = re.search(r"(17922842\d\d-lane\.bootstatic1017-\d+)", line)
        if m:
            f = line.split("\t")
            out.append((f[0], f[1], f[2], m.group(1)))
    return out


def main():
    a = sys.argv[1:]
    sheets = a[a.index("--sheets") + 1] if "--sheets" in a else None
    print("| request | arm | ref | title | verdict | Turnip / stock lines | title's first picture | screen-off presents "
          "to it | M1 (whole log) | M2 | M3 | undumped hashes |")
    print("|---|---|---|---|---|---|---|---|---|---|---|---|")
    notes = []
    seen = set()
    for arm, ref, title, rid in rows_of_ids():
        if rid in seen:
            continue
        seen.add(rid)
        hits = [p for p in glob.glob(os.path.join(D, "*" + rid)) if os.path.exists(os.path.join(p, "DONE"))]
        if not hits:
            print("| %s | %s | %s | %s | not finished | | | | | | | |" % (rid.split("-")[0], arm, ref, title))
            continue
        rd = hits[0]
        r = jn.judge(rd)
        fp = r.get("title_first_picture")
        print("| %s | %s | %s | %s | %s | %s / %s | %s | %s | %s (%s) | %s | %s | %s |" % (
            os.path.basename(rd).split("-lane")[0], arm, ref, title, r["verdict"].split(";")[0],
            r["V0_turnip_lines"], r["V0_stock_lines"],
            "n%d, %.1f s, %s" % (fp["n"], fp["t_ms"] / 1000, fp["start"]) if fp else "none",
            r.get("screen_off_presents_to_first_picture"), r.get("M1_to_first_picture"), r.get("M1_whole_log"),
            r.get("M2_to_first_picture"), r.get("M3_to_first_picture"), r.get("undumped_hashes_to_first_picture")))
        for e in r.get("episodes", []):
            notes.append("%s %s %s: M1 episode n%d-%d, %d presents, %.0f ms, starts %s, src %s, looks %s" % (
                rid.split("-")[0], arm, title.split(" (")[0], e["n"][0], e["n"][1], e["presents"], e["ms"],
                ",".join(e["starts"]), ",".join(e["src"]), ",".join(e["looks"]) or "-"))
        for k in ("M2_n", "M3_n"):
            if r.get(k):
                notes.append("%s %s: %s %s" % (rid.split("-")[0], arm, k, r[k]))
        if sheets:
            jn.sheet(r, os.path.join(sheets, "nova_%s_%s.png" % (rid.split("-")[0], arm)), os.path.join(rd, "pulled"))
    for n in notes:
        print(n)
    return 0


if __name__ == "__main__":
    sys.exit(main())
