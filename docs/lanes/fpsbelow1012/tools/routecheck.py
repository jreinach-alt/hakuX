#!/usr/bin/env python3
"""For each Nova title in belowbar1012.tsv: its golden, the routes the
dispatch history ran on it, and what the profile gate (titlestate.admit,
the same call request.sh makes) says about each route that is still on
disk. Read-only: admit() and title_routes() only read.

    python3 routecheck.py [belowbar1012.tsv] > routecheck.tsv
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TITLES = os.path.normpath(os.path.join(HERE, "..", "..", "..", "testing", "titles"))
sys.path.insert(0, TITLES)
import titlestate as ts  # noqa: E402

TSV = sys.argv[1] if len(sys.argv) > 1 else \
    "/home/justin/hakux-work/briefs/fpsbelow1012-tools/belowbar1012.tsv"


def rows():
    with open(TSV) as fh:
        hdr = None
        for line in fh:
            if line.startswith("#"):
                continue
            f = line.rstrip("\n").split("\t")
            if hdr is None:
                hdr = f
                continue
            yield dict(zip(hdr, f))


def tid_of(r, targs):
    if r["tid"]:
        return r["tid"]
    m = re.match(r"n-([0-9A-F]{8})-", r["result"])
    if m:
        return m.group(1)
    name = r["title"].lower()
    for tid, t in targs.items():
        if (t.get("name") or "").lower().startswith(name[:12]):
            return tid
    return ""


def main():
    targs = ts.targets()
    rd = ts.routes_root()
    print("\t".join(["tid", "title", "golden", "routes_on_disk", "admitted", "refused"]))
    for r in rows():
        if "nova" not in r["copied_on"]:
            continue
        tid = tid_of(r, targs)
        g = ts.golden(tid) if tid else None
        cands = ts.title_routes(tid) if tid else []
        on_disk = [c for c in cands if os.path.exists(os.path.join(rd, f"{c}.route"))]
        adm, ref = [], []
        for c in on_disk + [None]:
            a = ts.admit(tid, route_name=c, device="nova")
            label = c or "(no route)"
            if a["admit"]:
                adm.append(f"{label}:{a['clause']}:{a['state']}")
            else:
                ref.append(f"{label}")
        print("\t".join([tid, r["title"], (g or {}).get("save") or "-", ",".join(on_disk) or "-",
                         " ".join(adm) or "-", " ".join(ref) or "-"]))


if __name__ == "__main__":
    main()
