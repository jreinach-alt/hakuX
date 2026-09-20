#!/usr/bin/env python3
"""The canary catches a write that changes how the probe sees the hardware.

This is the regression test for the real incident: writing 0xFFFFFFFF to
0x000004 (NV_PMC_BOOT_1) flipped the MMIO endian switch, the sweep carried on
for 120 more registers, and two "findings" were published that turned out to be
declared bits seen through a byte swap.

A name-based hazard list could not have caught it -- BOOT_1 matches no
dangerous-sounding pattern. Re-reading a known constant after every write does,
and catches the whole class rather than that one instance.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sweep_writable_bits import (check_canary, bswap32, sweep_one,   # noqa: E402
                                 InstrumentPerturbed, CANARY_OFF)

BOOT0 = 0x02A000A3
fails = []


def check(cond, msg):
    print(("  ok   " if cond else "  FAIL ") + msg)
    if not cond:
        fails.append(msg)


class FlippySession:
    """Fake silicon. Writing ONES to `flip_at` byte-swaps every later access."""

    def __init__(self, flip_at=None):
        self.flip_at = flip_at
        self.flipped = False
        self.regs = {CANARY_OFF: BOOT0}

    def _view(self, v):
        return bswap32(v) if self.flipped else v

    def read32(self, off):
        return self._view(self.regs.get(off, 0))

    def write32(self, off, val):
        if off == self.flip_at and val == 0xFFFFFFFF:
            self.flipped = True
        self.regs[off] = val


def main() -> int:
    print("== an untouched canary raises nothing ==")
    s = FlippySession()
    try:
        check_canary(s, BOOT0, 0x100)
        check(True, "constant unchanged -> no alarm")
    except InstrumentPerturbed as e:
        check(False, "false alarm: %s" % e)

    print("== a byte-swapped canary is identified AS an endian flip ==")
    s = FlippySession(flip_at=0x004)
    s.write32(0x004, 0xFFFFFFFF)
    try:
        check_canary(s, BOOT0, 0x004)
        check(False, "the flip went undetected")
    except InstrumentPerturbed as e:
        check("ENDIANNESS FLIPPED" in str(e), "named as an endian flip, not a vague fault")
        check("000004" in str(e), "and blames the register that was just written")

    print("== any other canary change is caught too ==")
    s = FlippySession()
    s.regs[CANARY_OFF] = 0xDEADBEEF
    try:
        check_canary(s, BOOT0, 0x140)
        check(False, "a changed constant went undetected")
    except InstrumentPerturbed as e:
        check("ENDIANNESS" not in str(e), "not misreported as an endian flip")
        check("cannot be trusted" in str(e) or "changed how" in str(e),
              "says the later measurements are void")

    print("== the sweep stops AT the offending register, not 120 later ==")
    s = FlippySession(flip_at=0x004)
    ok_before = sweep_one(s, 0x100, canary=BOOT0)      # harmless register first
    check(ok_before["offset"] == 0x100, "a harmless register sweeps normally")
    try:
        sweep_one(s, 0x004, canary=BOOT0)
        check(False, "sweep_one returned instead of stopping")
    except InstrumentPerturbed as e:
        check(e.offset == 0x004, "stopped on the exact register that did it")

    print("== the sweep refuses to write its own canary ==")
    from sweep_writable_bits import load_hazards
    hz = load_hazards()
    check(CANARY_OFF in hz,
          "the canary register is on the hazard list, so no sweep can write it")

    print()
    if fails:
        print("%d check(s) failed" % len(fails))
        return 1
    print("canary suite OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
