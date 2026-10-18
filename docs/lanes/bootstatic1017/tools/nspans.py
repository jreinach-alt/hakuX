#!/usr/bin/env python3
"""Runs of presents with the same (src, start, sr01, window hash) in a [boot1045] probe log, to a limit: which picture
the window held, and with the screen on or off. Prints n range, t, src, start, sr01, hash, window lit/grn, dumped n.

usage: nspans.py LOG [MAX_N]
"""
import re
import sys


def main():
    log, mx = sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 600
    spans, prev = [], None
    for line in open(log, errors="replace"):
        m = dict(re.findall(r"(\w+)=(\S+)", line))
        if "n" not in m or "h" not in m:
            continue
        n = int(m["n"])
        if n > mx:
            break
        k = (m["src"], m["start"], m["sr01"], m["h"])
        if k != prev:
            spans.append({"a": n, "b": n, "t": float(m["t_ms"]), "k": k, "lit": m["lit"], "grn": m["grn"],
                          "dumps": []})
            prev = k
        else:
            spans[-1]["b"] = n
        if m.get("dump") == "1":
            spans[-1]["dumps"].append(n)
    for s in spans:
        print("n%d-%d t %.2f s src %s start %s sr01 %s h %s lit %s grn %s dumps %s" % (
            s["a"], s["b"], s["t"] / 1000, *s["k"], s["lit"], s["grn"], s["dumps"][:3]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
