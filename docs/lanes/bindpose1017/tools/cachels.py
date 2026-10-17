#!/usr/bin/env python3
"""List an Xbox disk image's utility-drive caches (X:, Y:, Z:) and one title's
E:\\UDATA and E:\\TDATA, with a damage check per file, off the device.

    cachels.py <image> [<TitleID>...]

<image> is a qcow2 (Android's x1box/hdd.img, the dispatcher's titles.qcow2) or
a raw image. Per file it prints size, modified time, sha1 (first 12), the
number of clusters in its FAT chain against the number its size needs, and how
many of those clusters are entirely zero. A file the guest created but never
finished writing shows as a short chain or as zero clusters, the two ways an
interrupted copy into a cache drive survives on disk.

Before the partitions it prints the nonzero words of sectors 4-7 (0x800-0xfff)
of the disk, where XAPI keeps which title owns which cache partition.
"""

import hashlib
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "..", "testing"))
import extract_results as er  # noqa: E402


def files(fs, cluster, prefix=""):
    for name, attrs, first, size, mtime, _ctime in fs.listdir(cluster):
        rel = prefix + name
        if attrs & er.ATTR_DIRECTORY:
            yield rel + "/", True, 0, mtime, first
            yield from files(fs, first, rel + "/")
        else:
            yield rel, False, size, mtime, first


def check(fs, first, size):
    need = -(-size // fs.bytes_per_cluster) if size else 0
    sha = hashlib.sha1()
    chain = zero = 0
    left = size
    try:
        for c in fs._chain(first):
            chain += 1
            data = fs._cluster_bytes(c)
            if not any(data):
                zero += 1
            if left > 0:
                sha.update(data[:left])
                left -= len(data)
    except er.ExtractError as e:
        return need, chain, zero, "ERR " + str(e)
    return need, chain, zero, sha.hexdigest()[:12]


def show(fs, cluster, label):
    n = 0
    for rel, is_dir, size, mtime, first in files(fs, cluster):
        n += 1
        if is_dir:
            print(f"  {label}{rel}  dir  {mtime}")
            continue
        need, chain, zero, sha = check(fs, first, size) if first else (0, 0, 0, "-")
        flag = ""
        if chain < need:
            flag += " SHORT-CHAIN"
        if zero:
            flag += f" ZERO-CLUSTERS={zero}"
        print(f"  {label}{rel}  {size}  {mtime}  {sha}  chain {chain}/{need}{flag}")
    if not n:
        print(f"  {label}(empty)")


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    image = er.open_image(argv[1])
    titles = [t.upper() for t in argv[2:]]
    db = image.read(0x800, 0x800)
    words = struct.unpack("<512I", db)
    print("cache db (sector 4-7), nonzero words:")
    for i in range(0, 512, 4):
        row = words[i:i + 4]
        if any(row):
            print(f"  0x{0x800 + i * 4:04x}: " + " ".join(f"{w:08x}" for w in row))
    # read on the images to hand: two header words, then {title id, partition
    # 0/1/2 = X/Y/Z, in use} per entry
    for i in range(2, 2 + 3 * 3, 3):
        tid, part, used = words[i:i + 3]
        if tid:
            print(f"  owner: {tid:08X} -> {'XYZ'[part] if part < 3 else part} (in use {used})")
    for letter in ("X", "Y", "Z"):
        off, size = er.PARTITIONS[letter]
        print(f"{letter}: (0x{off:x})")
        try:
            fs = er.Fatx(image, off, size)
        except er.ExtractError as e:
            print(f"  not FATX: {e}")
            continue
        show(fs, fs.root_cluster, f"{letter}:/")
    if titles:
        off, size = er.PARTITIONS["E"]
        fs = er.Fatx(image, off, size)
        for top in ("UDATA", "TDATA"):
            for t in titles:
                try:
                    attrs, cluster, _ = fs.resolve(f"{top}/{t}")
                except er.ExtractError as e:
                    print(f"E:/{top}/{t}: {e}")
                    continue
                print(f"E:/{top}/{t}:")
                show(fs, cluster, f"E:/{top}/{t}/")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
