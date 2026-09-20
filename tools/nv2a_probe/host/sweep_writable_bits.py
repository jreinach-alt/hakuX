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


class RestoreFailed(RuntimeError):
    def __init__(self, offset, msg):
        super().__init__(msg)
        self.offset = offset


class InstrumentPerturbed(RuntimeError):
    """A write changed how the probe itself sees the hardware."""

    def __init__(self, offset, msg):
        super().__init__(msg)
        self.offset = offset


# NV_PMC_BOOT_0 sits at absolute offset 0 of the BAR and reads a constant --
# 0x02A000A3, the value pmc.c hardcodes and whose low byte is this console's
# GPU revision. That makes it a universal canary for any block, not just PMC.
CANARY_OFF = 0x000000


def bswap32(v: int) -> int:
    return int.from_bytes(v.to_bytes(4, "little"), "big")


def check_canary(sess, expected: int, after: int) -> None:
    """Re-read a known constant. If it moved, the instrument moved.

    This is the general defence that name patterns cannot provide. A register
    is dangerous if writing to it changes how every LATER access is
    interpreted, and nothing in its spelling says so: 0x000004 is
    NV_PMC_BOOT_1, whose low bit is the MMIO endian switch, and writing ones to
    it byte-swapped every subsequent read. The sweep carried on for 120 more
    registers and published two findings that were the same declared bits seen
    through a byte swap.

    Checking a constant after every write turns that from a retraction weeks
    later into a stop on the very next operation, and it catches the whole
    class -- endian switches, aperture and window selects, banking, anything
    whose write redefines the address space -- without anyone having to
    enumerate it in advance.
    """
    got = sess.read32(CANARY_OFF)
    if got == expected:
        return
    if bswap32(got) == expected:
        raise InstrumentPerturbed(after,
            "ENDIANNESS FLIPPED. The canary at %06X reads %08X, the byte-swap "
            "of its constant %08X, immediately after writing %06X. Every "
            "measurement from here would be a byte-swapped lie."
            % (CANARY_OFF, got, expected, after))
    raise InstrumentPerturbed(after,
        "canary at %06X reads %08X, expected its constant %08X, immediately "
        "after writing %06X. Something about that write changed how this probe "
        "sees the hardware; nothing measured after it can be trusted."
        % (CANARY_OFF, got, expected, after))


def load_hazards() -> dict:
    hz = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hazards.json")
    if not os.path.exists(hz):
        raise SystemExit("hazards.json missing; run gen_window.py --write")
    return {int(k, 16): v for k, v in json.load(open(hz, encoding="utf-8")).items()}


def read_one(sess, off: int) -> dict:
    """Read a register and write nothing at all.

    A read sweep carries no risk -- it cannot wedge the console, cannot leave a
    register holding a value it did not start with, and cannot drive a clock
    out of spec -- and it still answers a real question: which registers return
    data on silicon that this tree models as zero. 0x000160 was found that way,
    reading a constant 0x01000000 where pmc.c has no case at all.
    """
    return {"offset": off, "t": time.time(), "mode": "read",
            "orig": sess.read32(off)}


def sweep_one(sess, off: int, canary: int | None = None) -> dict:
    rec = {"offset": off, "t": time.time()}
    orig = sess.read32(off)
    rec["orig"] = orig
    sess.write32(off, ONES)
    if canary is not None:
        check_canary(sess, canary, off)
    ones = sess.read32(off)
    sess.write32(off, 0)
    if canary is not None:
        check_canary(sess, canary, off)
    zeros = sess.read32(off)
    # Restore before anything else can go wrong with this register.
    sess.write32(off, orig)
    if canary is not None:
        check_canary(sess, canary, off)
    final = sess.read32(off)
    rec.update(
        ones=ones, zeros=zeros, final=final,
        writable=ones & ~zeros,
        stuck_ones=ones & zeros,
        stuck_zeros=(~ones & ~zeros) & 0xFFFFFFFF,
        restored=(final == orig),
    )
    if final != orig:
        # STOP. A register that will not go back to the value it had is a
        # register whose function we did not understand, and the next one along
        # is no safer. The first hardware run left 0x000004 holding 0x01000001
        # instead of 0 and swept 120 more registers afterwards as if nothing
        # had happened; the run that wedged the console came later, and this
        # would have stopped before it.
        raise RestoreFailed(off,
            "%06X did not restore: was %08X, now %08X. Stopping rather than "
            "continuing past a register we evidently do not understand."
            % (off, orig, final))
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
    ap.add_argument("--read-only", action="store_true",
                    help="read every register in the range and write NOTHING. "
                         "Zero risk, and it still finds registers silicon "
                         "answers where this tree returns 0.")
    ap.add_argument("--write-scope", choices=("declared", "all"), default="declared",
                    help="which registers may be WRITTEN. 'declared' (default) "
                         "writes only registers nv2a_regs.h names, so a blind "
                         "value never lands in something nobody has identified. "
                         "Reads are unrestricted either way, so undeclared "
                         "registers are still discovered, just not poked.")
    args = ap.parse_args()

    start, end = int(args.start, 0), int(args.end, 0)
    skip = {int(s, 0) for s in args.skip}
    os.makedirs(args.workdir, exist_ok=True)
    results_path = os.path.join(args.workdir, "results.jsonl")

    hazards = load_hazards()
    declared = set()
    if args.read_only:
        print("READ-ONLY sweep: no write will be issued, so no register can be "
              "left changed and nothing can wedge.")
    elif args.write_scope == "declared":
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import compare_masks as _cm
        root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
        regs = _cm.parse_regs(os.path.join(root, "hw", "xbox", "nv2a", "nv2a_regs.h"),
                              "NV_" + args.block.upper() + "_")
        declared = set(regs)
        print("write scope: declared only -- %d registers of %s are named in "
              "nv2a_regs.h" % (len(declared), args.block))
    if not args.read_only and CANARY_OFF not in hazards:
        raise SystemExit(
            "refusing to run: the canary at %06X is not on the hazard list, so "
            "the sweep could write to the very register it uses to detect that "
            "something has gone wrong." % CANARY_OFF)

    srv = ProbeServer(args.workdir, port=args.port)
    print("hazard list: %d registers will not be written at all" % len(hazards))
    print("listening on %s:%d -- launch the probe on the console" % srv.addr)
    print("sweeping %s 0x%06X..0x%06X (%d registers)"
          % (args.block, start, end, (end - start) // 4))

    done = load_done(results_path)
    if done:
        print("resuming: %d registers already recorded" % len(done))

    sess = None
    canary = None
    reconnects = 0
    hangs = []
    try:
        while True:
            if args.read_only:
                todo = [o for o in range(start, end, 4)
                        if o not in done and o not in skip]
            else:
                todo = [o for o in range(start, end, 4)
                        if o not in done and o not in skip
                        and o not in hazards
                        and (args.write_scope == "all" or o in declared)
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
                if not args.read_only:
                    canary = sess.read32(CANARY_OFF)
                    print("  canary %06X = %08X (re-checked after every write)"
                          % (CANARY_OFF, canary))
            try:
                for off in todo:
                    rec = (read_one(sess, off) if args.read_only
                           else sweep_one(sess, off, canary))
                    done[off] = rec
                    with open(results_path, "a", encoding="utf-8") as fh:
                        fh.write(json.dumps(rec) + "\n")
                    if args.read_only:
                        if rec["orig"]:
                            print("  %06X reads %08X" % (off, rec["orig"]))
                    elif rec["writable"]:
                        print("  %06X writable=%08X orig=%08X%s"
                              % (off, rec["writable"], rec["orig"],
                                 "" if rec["restored"] else "  RESTORE FAILED"))
            except InstrumentPerturbed as exc:
                print("\n  *** %s" % exc)
                srv.poison.add(exc.offset, None,
                               "writing here perturbs the instrument itself")
                print("  register banned and sweep stopped. Everything already "
                      "recorded is still good; nothing after this write would "
                      "have been.")
                break
            except RestoreFailed as exc:
                print("\n  *** %s" % exc)
                srv.poison.add(exc.offset, None,
                               "did not restore after a sweep write")
                print("  register banned; stopping rather than sweeping on.")
                break
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
            sess.end_run()
        srv.close()

    print("\nswept %d registers, %d sessions, %d suspected hangs"
          % (len(done), reconnects, len(hangs)))
    print("results: %s" % results_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
