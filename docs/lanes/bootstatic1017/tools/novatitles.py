#!/usr/bin/env python3
"""For each candidate TitleID: its ISO on the Nova, and whether the profile gate admits a no-route soak.

usage: novatitles.py TID [TID ...]
"""
import os
import subprocess
import sys

TS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "testing", "titles", "titlestate.py")


def run(*a):
    p = subprocess.run([sys.executable, TS] + list(a), capture_output=True, text=True)
    return p.returncode, (p.stdout + p.stderr).strip().replace("\n", " | ")


def main():
    for tid in sys.argv[1:]:
        rc, iso = run("iso-for-tid", "--title-id", tid, "--device", "nova")
        arc, adm = run("admit", "--title-id", tid, "--device", "nova") if rc == 0 else (-1, "")
        print("%s iso=%s admit_rc=%s %s" % (tid, iso if rc == 0 else "NONE(%s)" % iso, arc, adm[:300]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
