#!/usr/bin/env python3
"""Measure each NV2A register's writable mask on real silicon.

Per register, five operations:

    orig    = read(off)
    write(off, 0xFFFFFFFF);  ones  = read(off)
    write(off, 0x00000000);  zeros = read(off)
    write(off, orig);        final = read(off)

    writable = ones & ~zeros

A bit that reads back 1 after writing ones AND 0 after writing zeros followed
what we told it. Bits set in both are read-only ones; bits clear in both are
read-only zeros. The three are reported separately because "this bit is not
writable" and "this bit is wired high" are different facts about the hardware.

The sweep is resumable by construction. Every register's result is appended to
results.jsonl as it completes, so a reconnect skips what is already done, and a
register that killed the link is on the poison list and is skipped for good.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from probe_driver import ProbeServer, ProbeError   # noqa: E402

ONES = 0xFFFFFFFF


def load_done(path: str) -> dict[int, dict]:
    done = {}
    if os.path.exists(path):
        for line in open(path, encoding="utf-8"):
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
                done[r["offset"]] = r
            except Exception:
                continue
    return done


def sweep_one(sess, off: int) -> dict:
    rec = {"offset": off, "t": time.time()}
    orig = sess.read32(off)
    rec["orig"] = orig
    sess.write32(off, ONES)
    ones = sess.read32(off)
    sess.write32(off, 0)
    zeros = sess.read32(off)
    # Restore before anything else can go wrong with this register.
    sess.write32(off, orig)
    final = sess.read32(off)
    rec.update(
        ones=ones, zeros=zeros, final=final,
        writable=ones & ~zeros,
        stuck_ones=ones & zeros,
        stuck_zeros=(~ones & ~zeros) & 0xFFFFFFFF,
        restored=(final == orig),
    )
    return rec


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--workdir", required=True)
    ap.add_argument("--port", type=int, default=24242)
    ap.add_argument("--block", default="PMC",
                    help="label for the block being swept (default: PMC)")
    ap.add_argument("--start", default="0x000000")
    ap.add_argument("--end", default="0x001000",
                    help="exclusive; default is the end of PMC")
    ap.add_argument("--skip", action="append", default=[],
                    help="offset to leave alone, repeatable")
    ap.add_argument("--accept-timeout", type=float, default=300.0)
    args = ap.parse_args()

    start, end = int(args.start, 0), int(args.end, 0)
    skip = {int(s, 0) for s in args.skip}
    os.makedirs(args.workdir, exist_ok=True)
    results_path = os.path.join(args.workdir, "results.jsonl")

    srv = ProbeServer(args.workdir, port=args.port)
    print("listening on %s:%d -- launch the probe on the console" % srv.addr)
    print("sweeping %s 0x%06X..0x%06X (%d registers)"
          % (args.block, start, end, (end - start) // 4))

    done = load_done(results_path)
    if done:
        print("resuming: %d registers already recorded" % len(done))

    sess = None
    reconnects = 0
    hangs = []
    try:
        while True:
            todo = [o for o in range(start, end, 4)
                    if o not in done and o not in skip
                    and not srv.poison.is_poison(o, None)]
            if not todo:
                break
            if sess is None:
                print("waiting for the probe to dial in ...")
                try:
                    sess = srv.accept(timeout=args.accept_timeout)
                except (ProbeError, OSError) as exc:
                    # A connection that fails its handshake must not end the
                    # sweep. Anything on the LAN can open this port -- a scan,
                    # a stale retry, an operator testing reachability -- and
                    # losing an hour of sweeping to one bad greeting is a much
                    # worse outcome than waiting again. (Learned the hard way:
                    # a reachability check from this very host killed a run.)
                    print("  ignoring a connection that did not greet us: %s" % exc)
                    continue
                print("  connected: %s" % sess.hello)
                reconnects += 1
            try:
                for off in todo:
                    rec = sweep_one(sess, off)
                    done[off] = rec
                    with open(results_path, "a", encoding="utf-8") as fh:
                        fh.write(json.dumps(rec) + "\n")
                    if rec["writable"]:
                        print("  %06X writable=%08X orig=%08X%s"
                              % (off, rec["writable"], rec["orig"],
                                 "" if rec["restored"] else "  RESTORE FAILED"))
            except (ProbeError, OSError) as exc:
                orphan = srv.note_link_death(exc)
                if orphan:
                    hangs.append(orphan)
                    print("  LINK DIED with %08X=%08X in flight -- poisoned "
                          "and skipped on resume"
                          % (orphan["offset"], orphan["value"]))
                else:
                    print("  link died with nothing in flight: %s" % exc)
                try:
                    sess.close()
                except Exception:
                    pass
                sess = None
                continue
    finally:
        if sess:
            sess.close()
        srv.close()

    print("\nswept %d registers, %d sessions, %d suspected hangs"
          % (len(done), reconnects, len(hangs)))
    print("results: %s" % results_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
