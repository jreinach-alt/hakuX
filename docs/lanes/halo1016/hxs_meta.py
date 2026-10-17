#!/usr/bin/env python3
"""Print a .hxs save state's metadata (layout: android/.../savestate/hxs.c).

The loader (hxs_load_slot -> check_meta) refuses a file unless title_id, disc,
controllers and schema equal the running machine's, and the disk_snap it names
exists in the running hard disk image (a qcow2 internal snapshot). This prints
those fields so a test can be planned against them.

usage: hxs_meta.py FILE.hxs [...]
"""
import struct
import sys

for path in sys.argv[1:]:
    with open(path, "rb") as f:
        f.seek(0, 2)
        size = f.tell()
        f.seek(0)
        h = f.read(48)
        magic, hlen, codec, level, raw_len, pay_len, meta_len, chunk, flags, _ = \
            struct.unpack("<4sIIIQQIIII", h)
        f.seek(size - 8)
        tmagic, tlen = struct.unpack("<4sI", f.read(8))
        f.seek(size - 8 - tlen)
        m = f.read(tlen)
    print("%s: %s codec=%d raw=%d payload=%d meta=%d trailer=%s" % (
        path, magic, codec, raw_len, pay_len, meta_len, tmagic))
    n, = struct.unpack_from("<I", m, 0)
    o = 4
    for _ in range(n):
        kl = m[o]
        o += 1
        k = m[o:o + kl].decode(errors="replace")
        o += kl
        vl, = struct.unpack_from("<H", m, o)
        o += 2
        v = m[o:o + vl].decode(errors="replace")
        o += vl
        print("  %s = %s" % (k, v))
