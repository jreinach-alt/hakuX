#!/usr/bin/env python3
"""Read every modelled NV2A block on silicon and diff it against the tree.

Read-only, always. No write is issued, so nothing can be left changed, no
clock can be driven out of spec and nothing can wedge -- which is what makes
breadth affordable here. The block list comes from the generated window header,
so it is the emulator's own device model rather than a list somebody typed.

PRMFB and USER are skipped by default: 128 KiB and 8 MiB respectively, and USER
is the FIFO DMA-push area that phase one does not touch at all.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from probe_driver import ProbeServer, ProbeError          # noqa: E402
from sweep_writable_bits import CANARY_OFF, bswap32       # noqa: E402

BOOT0 = 0x02A000A3
SKIP_DEFAULT = {"PRMFB", "USER"}


def blocks_from_header(root: str):
    hdr = os.path.join(root, "tools", "nv2a_probe", "probe", "nv2a_window.h")
    out = []
    for m in re.finditer(r'\{\s*"(\w+)",\s*(0x[0-9a-f]+)u,\s*(0x[0-9a-f]+)u',
                         open(hdr, encoding="utf-8").read()):
        out.append((m.group(1), int(m.group(2), 16), int(m.group(3), 16)))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--workdir", required=True)
    ap.add_argument("--port", type=int, default=24242)
    ap.add_argument("--root", default=os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    ap.add_argument("--skip", action="append", default=sorted(SKIP_DEFAULT))
    ap.add_argument("--accept-timeout", type=float, default=600.0)
    args = ap.parse_args()

    root = os.path.abspath(args.root)
    blocks = [b for b in blocks_from_header(root) if b[0] not in set(args.skip)]
    total = sum(sz for _, _, sz in blocks) // 4
    os.makedirs(args.workdir, exist_ok=True)
    print("reading %d blocks, %d dwords, READ-ONLY" % (len(blocks), total))
    for n, o, sz in blocks:
        print("   %-9s %06X..%06X  %5d dwords" % (n, o, o + sz, sz // 4))

    srv = ProbeServer(args.workdir, port=args.port)
    print("\nlistening on %s:%d" % srv.addr)
    sess = srv.accept(timeout=args.accept_timeout)
    print("connected: %s" % sess.hello)
    canary = sess.read32(CANARY_OFF)
    print("canary %06X = %08X %s" % (CANARY_OFF, canary,
          "(matches the known constant)" if canary == BOOT0 else "*** UNEXPECTED ***"))

    t0 = time.time()
    done = 0
    try:
        for name, base, size in blocks:
            path = os.path.join(args.workdir, "%s.jsonl" % name)
            if os.path.exists(path):
                print("  %-9s already done, skipping" % name)
                continue
            nz = 0
            with open(path + ".part", "w", encoding="utf-8") as fh:
                for off in range(base, base + size, 4):
                    v = sess.read32(off)
                    done += 1
                    if v:
                        nz += 1
                    fh.write(json.dumps({"offset": off, "orig": v}) + "\n")
            # A read sweep cannot perturb anything, but confirming the canary
            # per block costs one read and proves the whole block was measured
            # through the same instrument.
            c = sess.read32(CANARY_OFF)
            if c != canary:
                print("  %-9s CANARY MOVED (%08X -> %08X)%s -- discarding"
                      % (name, canary, c,
                         " [byte-swapped]" if bswap32(c) == canary else ""))
                os.remove(path + ".part")
                break
            os.replace(path + ".part", path)
            print("  %-9s %5d dwords, %4d non-zero" % (name, size // 4, nz))
    except (ProbeError, OSError) as exc:
        print("  link died: %s" % exc)
    finally:
        try:
            sess.end_run()
        except Exception:
            pass
        srv.close()
    dt = time.time() - t0
    print("\nread %d dwords in %.0fs (%.0f/s)" % (done, dt, done / dt if dt else 0))
    return 0


if __name__ == "__main__":
    sys.exit(main())
