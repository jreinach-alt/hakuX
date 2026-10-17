#!/usr/bin/env python3
"""Question: has Antialiasing_tests::CPUWriteIgnoresSurfaceConfig ever come out
different from the checkerboard before gta3drive1017's pixel B arm?

Hashes the decoded pixels of that capture in every result dir that has it and
groups the dirs by hash, oldest first, so a second look (striped) stands out.
Usage: capture_history.py [capture file name]
"""
import hashlib
import os
import sys

from PIL import Image

RES = "/home/justin/hakux-work/dispatch/results"
NAME = sys.argv[1] if len(sys.argv) > 1 else "Antialiasing_tests::CPUWriteIgnoresSurfaceConfig.png"


def mtime(n):
    try:
        return os.path.getmtime(os.path.join(RES, n))
    except OSError:  # dangling alias
        return 0


def main():
    groups = {}
    for d in sorted(os.listdir(RES), key=mtime):
        base = os.path.join(RES, d)
        if not os.path.isdir(base):
            continue
        for sub in sorted(os.listdir(base)):
            p = os.path.join(base, sub, NAME)
            if not sub.startswith("captures") or not os.path.exists(p):
                continue
            try:
                im = Image.open(p).convert("RGB")
            except Exception as e:  # unreadable capture
                h = "unreadable:%s" % type(e).__name__
            else:
                h = hashlib.sha1(im.tobytes()).hexdigest()[:12]
            groups.setdefault(h, []).append("%s/%s" % (d, sub))
    for h, dirs in sorted(groups.items(), key=lambda kv: -len(kv[1])):
        print("%s  %3d  first %s  last %s" % (h, len(dirs), dirs[0], dirs[-1]))
        if len(dirs) <= 6:
            for x in dirs:
                print("        %s" % x)


if __name__ == "__main__":
    main()
