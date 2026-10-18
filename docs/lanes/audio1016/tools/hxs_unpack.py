#!/usr/bin/env python3
"""Unpack a hakuX save state (.hxs, format HXS1) to its raw migration stream.

  hxs_unpack.py STATE.hxs OUT.stream

Prints the header and the metadata entries, then writes the decompressed
stream. zstd chunks go through libzstd by ctypes (no python module needed);
lz4 is not handled. Format: android/app/src/main/cpp/savestate/hxs.c.
"""
import ctypes
import ctypes.util
import struct
import sys


def zstd_lib():
    name = ctypes.util.find_library("zstd") or "libzstd.so.1"
    lib = ctypes.CDLL(name)
    lib.ZSTD_decompress.restype = ctypes.c_size_t
    lib.ZSTD_decompress.argtypes = [ctypes.c_void_p, ctypes.c_size_t,
                                    ctypes.c_void_p, ctypes.c_size_t]
    lib.ZSTD_isError.restype = ctypes.c_uint
    lib.ZSTD_isError.argtypes = [ctypes.c_size_t]
    return lib


def main():
    src, dst = sys.argv[1], sys.argv[2]
    data = open(src, "rb").read()
    (magic, hlen, codec, level, stream_len, payload_len, meta_len, chunk,
     flags, _res) = struct.unpack_from("<4sIIIQQIIII", data, 0)
    if magic != b"HXS1":
        raise SystemExit("not HXS1: %r" % magic)
    print(f"header: len {hlen} codec {codec} level {level} stream {stream_len} "
          f"payload {payload_len} meta {meta_len} chunk {chunk} flags {flags:#x}")
    payload = data[hlen:hlen + payload_len]
    meta = data[hlen + payload_len:hlen + payload_len + meta_len]
    n, = struct.unpack_from("<I", meta, 0)
    off = 4
    for _ in range(n):
        kl = meta[off]
        key = meta[off + 1:off + 1 + kl].decode("utf-8", "replace")
        off += 1 + kl
        vl, = struct.unpack_from("<H", meta, off)
        val = meta[off + 2:off + 2 + vl].decode("utf-8", "replace")
        off += 2 + vl
        print(f"meta: {key} = {val}")
    if codec == 0:
        out = payload
    elif codec == 2 and flags & 1:
        lib = zstd_lib()
        parts = []
        off = 0
        while off < len(payload):
            raw, stored = struct.unpack_from("<II", payload, off)
            off += 8
            blk = payload[off:off + stored]
            off += stored
            if stored == raw:
                parts.append(blk)
                continue
            buf = ctypes.create_string_buffer(raw)
            r = lib.ZSTD_decompress(buf, raw, blk, stored)
            if lib.ZSTD_isError(r) or r != raw:
                raise SystemExit(f"zstd chunk failed at {off}: {r}")
            parts.append(buf.raw)
        out = b"".join(parts)
    else:
        raise SystemExit(f"codec {codec} flags {flags:#x} not handled")
    if len(out) != stream_len:
        print(f"WARNING: stream {len(out)} != header {stream_len}")
    open(dst, "wb").write(out)
    print(f"wrote {len(out)} bytes to {dst}")


if __name__ == "__main__":
    main()
