#!/usr/bin/env python3
"""List or extract files from an XISO (Xbox game partition) image.

  xiso_ls.py IMAGE                 list every file: size, path
  xiso_ls.py IMAGE PATTERN OUTDIR  extract files whose path matches the regex

Read-only on the image. Handles both a rebuilt xiso (partition at 0) and a
redump image (partition at 0x18300000).
"""
import os
import re
import struct
import sys

SECTOR = 2048
MAGIC = b"MICROSOFT*XBOX*MEDIA"


def find_base(f):
    for base in (0, 0x18300000, 0x2080000, 0xFD90000):
        f.seek(base + 32 * SECTOR)
        if f.read(20) == MAGIC:
            return base
    raise SystemExit("no XISO header found")


def walk(f, base, sector, size, prefix):
    f.seek(base + sector * SECTOR)
    data = f.read(size)
    seen = set()
    stack = [0]
    while stack:
        off = stack.pop()
        if off in seen or off + 14 > len(data):
            continue
        seen.add(off)
        left, right, start, fsize, attr, nlen = struct.unpack_from(
            "<HHIIBB", data, off)
        if left == 0xFFFF and right == 0xFFFF:
            continue
        name = data[off + 14:off + 14 + nlen].decode("latin-1")
        path = prefix + name
        if attr & 0x10:
            if fsize:
                yield from walk(f, base, start, fsize, path + "/")
        else:
            yield path, start, fsize
        if left and left != 0xFFFF:
            stack.append(left * 4)
        if right and right != 0xFFFF:
            stack.append(right * 4)


def main():
    img = sys.argv[1]
    with open(img, "rb") as f:
        base = find_base(f)
        f.seek(base + 32 * SECTOR + 20)
        root_sector, root_size = struct.unpack("<II", f.read(8))
        files = sorted(walk(f, base, root_sector, root_size, ""))
        if len(sys.argv) == 2:
            for path, start, size in files:
                print(f"{size:12d}  {path}")
            return
        pat = re.compile(sys.argv[2], re.I)
        out = sys.argv[3]
        for path, start, size in files:
            if not pat.search(path):
                continue
            dst = os.path.join(out, path)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            f.seek(base + start * SECTOR)
            with open(dst, "wb") as o:
                left = size
                while left:
                    chunk = f.read(min(left, 1 << 20))
                    o.write(chunk)
                    left -= len(chunk)
            print(f"extracted {size:12d}  {path}")


if __name__ == "__main__":
    main()
