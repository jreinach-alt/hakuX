#!/usr/bin/env python3
"""Compact view of a boot1045_log.txt: one row per change of (start, sr01, window class, texture class, ram_nz bucket).

usage: logpeek.py LOG [N0 N1]

Prints n, t_ms, vt_ms (guest virtual clock), start, sr01, ram_nz fraction, window lit/nb, texture tlit/tnb, for the
first present of every run of identical keys, so a 4000-line log reads as its phases.
"""
import re
import sys


def cls(lit, nb):
    if lit < 0.02:
        return "black"
    if nb >= 20:
        return "noise"
    return "pic"


def main():
    log = sys.argv[1]
    n0, n1 = (int(sys.argv[2]), int(sys.argv[3])) if len(sys.argv) > 3 else (0, 1 << 30)
    prev, run = None, 0
    for line in open(log):
        d = dict(re.findall(r"(\w+)=(\S+)", line))
        if "n" not in d or not (n0 <= int(d["n"]) <= n1):
            continue
        a, b = d["ram_nz"].split("/")
        rz = float(a) / max(1, float(b))
        key = (d["start"], d["sr01"], cls(float(d["lit"]), float(d["nb"])),
               cls(float(d.get("tlit", -1)), float(d.get("tnb", 0))), round(rz, 1))
        if key != prev:
            if prev is not None:
                print("      ... %d presents" % run)
            print("n=%-5s t=%8s vt=%7s start=%s sr01=%s ram_nz=%.3f win=%s lit=%s nb=%s tex=%s tlit=%s tnb=%s" % (
                d["n"], d["t_ms"], d.get("vt_ms", "?"), d["start"], d["sr01"], rz, key[2], d["lit"], d["nb"],
                key[3], d.get("tlit", "?"), d.get("tnb", "?")))
            prev, run = key, 0
        run += 1
    print("      ... %d presents" % run)


if __name__ == "__main__":
    main()
