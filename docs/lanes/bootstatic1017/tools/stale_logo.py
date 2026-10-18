#!/usr/bin/env python3
"""M4 for #1045: presents that show, at the title's own scan-out address, a picture first seen at the kernel's.

After R1 the Nova's R1+R2 runs drew black through every screen-off present and then, at the title's first present
at its own start, the window hash of the kernel's logo (698586ab) for one present, in all three titles: the Vulkan
display path's image from the previous refresh, which across the screen-off interval is the logo. R5 (2a012b14fc)
makes that present wait for a render of the current start. Written before any R5 run.

M4 counts presents with the screen on (SR01 bit 5 clear), at a start other than 0 and the kernel's (the start of the
first src=n present), whose window hash is a lit hash (window lit > 0) seen at the kernel's start. Silicon shows the
title's own picture there, so M4 is 0 on silicon. A title that draws the logo itself would count; none of the three
does (their first pictures are black or full-screen, lit 1.000).

usage: stale_logo.py RESULT_DIR_OR_LOG...
"""
import os
import re
import sys


def rows(path):
    if os.path.isdir(path):
        path = os.path.join(path, "pulled", "boot1045_log.txt")
    out = []
    for line in open(path, errors="replace"):
        m = dict(re.findall(r"(\w+)=(\S+)", line))
        if "n" in m and "h" in m and "start" in m and "sr01" in m:
            out.append({"n": int(m["n"]), "src": m.get("src"), "start": int(m["start"], 16),
                        "off": bool(int(m["sr01"], 16) & 0x20), "h": m["h"], "lit": float(m.get("lit", "0"))})
    return out


def m4(rs):
    kstart = next((r["start"] for r in rs if r["src"] == "n"), None)
    logo = {r["h"] for r in rs if r["start"] == kstart and r["lit"] > 0}
    hits = [r["n"] for r in rs if not r["off"] and r["start"] not in (0, kstart) and r["h"] in logo]
    return kstart, logo, hits


def main():
    for p in sys.argv[1:]:
        rs = rows(p)
        kstart, logo, hits = m4(rs)
        print("%s: presents %d, kernel start %s, lit hashes there %s, M4 %d %s" % (
            os.path.basename(p.rstrip("/")), len(rs), "0x%08x" % kstart if kstart is not None else "none",
            ",".join(sorted(logo)) or "-", len(hits), hits[:10]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
