#!/usr/bin/env python3
"""Flip ``RunAll(false)`` to ``RunAll(true)`` in a prebuilt nxdk_pgraph_tests XBE.

Why this exists
---------------
``Blend tests`` registers the 1,568 ``<sfactor>_<eqn>_<dfactor>`` triples and
marks each one interactive-only (``blend_tests.cpp:92``).  The automated entry
point, ``TestDriver::RunAllTestsNonInteractive`` (``test_driver.cpp:132``),
calls ``suite->RunAll(false)`` unconditionally, and the runtime config on the
disc can only ever *remove* tests (``RuntimeConfig::ApplyConfig`` calls
``TestSuite::DisableTests``), so no config reaches them.  In compiled x86 the
argument is a single ``push $0x0``; flipping the immediate to 1 lifts the
per-test filter without a toolchain.

**Read `docs/investigations/test-coverage-gaps.md` before using this.** The
1,568 are already reachable with the ``v2025-03-14`` release disc, which
predates the retirement, and 1,568 captures from it are on disk. This tool is
for getting them out of the *current* binary, so they share a test revision
with every other suite -- not for closing a gap that is already closed.

Safety
------
Two things make the patch narrow, and both are re-verified here rather than
assumed:

* ``interactive_only_tests_`` is inserted into by exactly two files --
  ``blend_tests.cpp:92`` and ``clipping_precision_tests.cpp:32`` -- and
  ``Clipping precision`` is *also* suite-level interactive-only, so
  ``test_driver.cpp:120`` skips it before ``RunAll`` is ever called.  The same
  is true of ``PVIDEO``.  So the flip adds Blend's 1,568 and nothing else.
* There are two ``RunAll(false)`` call sites.  The other is
  ``MenuItemSuite::ActivateCurrentSuite`` (``menu_item.cpp:259``), the
  interactive menu's own "run all", which an automated disc never reaches.
  Patching it would do nothing visible, so this refuses to run unless it can
  tell the two apart by the code around them.

Nothing is modified in place: the input image is opened read-only and a new
image is written.  XBE section digests are all zero in an nxdk build (checked,
not assumed), so a one-byte ``.text`` edit needs no digest recomputation, and
XISO carries no per-file checksum.
"""

import argparse
import importlib.util
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

_spec = importlib.util.spec_from_file_location(
    "make_test_iso", os.path.join(HERE, "make_test_iso.py"))
mti = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mti)

# The two log lines that bracket the call in RunAllTestsNonInteractive. The
# menu site has no such neighbours, which is what makes the two separable.
ANCHOR_BEFORE = b"DEBUG: [TestDriver] Starting suite "
ANCHOR_AFTER = b"DEBUG: [TestDriver] Completed suite "

# mov (%ebx),%ecx ; push $0x0 ; call rel32
#   -- this = *iterator over test_suites_, then the boolean, then the call.
SITE = bytes.fromhex("8b0b6a00e8")
PUSH_IMM_AT = 3          # index of the 0x00 inside SITE
CALL_AT = 4              # index of the 0xE8 inside SITE

# Immediately before: call *0x4(%eax)   -> suite->Initialize()   (vtable +4)
PRE_INITIALIZE = bytes.fromhex("ff5004")
# Immediately after:  mov (%ebx),%ecx ; mov (%ecx),%eax ; call *0x8(%eax)
#                                      -> suite->Deinitialize() (vtable +8)
POST_DEINITIALIZE = bytes.fromhex("8b0b8b01ff5008")


class PatchError(Exception):
    pass


class Xbe:
    """Just enough XBE to map virtual addresses to offsets in the file."""

    def __init__(self, data):
        if data[:4] != b"XBEH":
            raise PatchError("not an XBE: magic is %r" % data[:4])
        self.data = data
        self.base = struct.unpack_from("<I", data, 0x0104)[0]
        self.header_size = struct.unpack_from("<I", data, 0x0108)[0]
        n = struct.unpack_from("<I", data, 0x011C)[0]
        table = struct.unpack_from("<I", data, 0x0120)[0] - self.base
        self.sections = []
        for i in range(n):
            p = table + i * 56
            flags, vaddr, vsize, raw, rawsz, nameaddr = struct.unpack_from(
                "<IIIIII", data, p)
            name = ""
            if nameaddr:
                q = nameaddr - self.base
                if 0 <= q < len(data):
                    name = data[q:data.index(b"\0", q)].decode("latin-1")
            self.sections.append(dict(
                name=name, flags=flags, vaddr=vaddr, vsize=vsize,
                raw=raw, rawsz=rawsz, digest=data[p + 0x24:p + 0x38]))

    def section(self, name):
        for s in self.sections:
            if s["name"] == name:
                return s
        raise PatchError("no %s section" % name)

    def off_to_va(self, off):
        for s in self.sections:
            if s["raw"] <= off < s["raw"] + s["rawsz"]:
                return s["vaddr"] + (off - s["raw"])
        return None


def _find_one(haystack, needle, what):
    first = haystack.find(needle)
    if first < 0:
        raise PatchError("%s not found" % what)
    if haystack.find(needle, first + 1) >= 0:
        raise PatchError("%s is not unique" % what)
    return first


def _callers_of(text, seg, target_va):
    """Every ``call rel32`` in .text whose destination is ``target_va``."""
    out = []
    for i in range(len(seg) - 5):
        if seg[i] != 0xE8:
            continue
        rel = struct.unpack_from("<i", seg, i + 1)[0]
        va = text["vaddr"] + i
        if va + 5 + rel == target_va:
            out.append((va, text["raw"] + i))
    return out


def locate(xbe):
    """Return (xbe_offset_of_immediate, report_lines). Refuses when unsure."""
    log = []
    text = xbe.section(".text")
    rdata = xbe.section(".rdata")
    seg = xbe.data[text["raw"]:text["raw"] + text["rawsz"]]
    rseg = xbe.data[rdata["raw"]:rdata["raw"] + rdata["rawsz"]]

    # 1. The two log strings, and the code that references them. Each is
    #    pushed twice per use (once for strlen, once for the append), so two
    #    references apiece is the expected count.
    bounds = []
    for needle, label in ((ANCHOR_BEFORE, "before"), (ANCHOR_AFTER, "after")):
        off = _find_one(rseg, needle, "anchor string %r" % needle.decode())
        va = rdata["vaddr"] + off
        pat = struct.pack("<I", va)
        refs = []
        pos = 0
        while True:
            i = rseg and seg.find(pat, pos)
            if i < 0:
                break
            refs.append(text["vaddr"] + i)
            pos = i + 1
        if not refs:
            raise PatchError("anchor %s at 0x%X is never referenced" % (label, va))
        bounds.append((min(refs), max(refs)))
        log.append("anchor %-6s %r at va=0x%X, %d code refs 0x%X..0x%X"
                   % (label, needle.decode(), va, len(refs), min(refs), max(refs)))
    lo, hi = bounds[0][0], bounds[1][1]
    if not lo < hi:
        raise PatchError("anchor strings are not in source order (0x%X, 0x%X)" % (lo, hi))
    log.append("RunAllTestsNonInteractive body bounded by va 0x%X .. 0x%X" % (lo, hi))

    # 2. The call site pattern, required to be unique in the whole of .text.
    at = _find_one(seg, SITE, "call-site pattern %s" % SITE.hex(" "))
    site_va = text["vaddr"] + at
    if not lo < site_va < hi:
        raise PatchError("call site va=0x%X is outside the anchored body "
                         "0x%X..0x%X -- refusing" % (site_va, lo, hi))
    log.append("call site   va=0x%X (inside the anchored body)" % site_va)

    # 3. Initialize() before it and Deinitialize() after it, the two virtual
    #    calls that bracket RunAll in both C++ sites. Their presence here plus
    #    the anchors is what names this site rather than the menu's.
    if seg[at - len(PRE_INITIALIZE):at] != PRE_INITIALIZE:
        raise PatchError("no `call *0x4(%%eax)` (Initialize) immediately before "
                         "the call site; found %s"
                         % seg[at - len(PRE_INITIALIZE):at].hex(" "))
    after = at + len(SITE) + 4
    if seg[after:after + len(POST_DEINITIALIZE)] != POST_DEINITIALIZE:
        raise PatchError("no `call *0x8(%%eax)` (Deinitialize) immediately after "
                         "the call site; found %s"
                         % seg[after:after + len(POST_DEINITIALIZE)].hex(" "))
    log.append("bracketed by Initialize (vtable+4) and Deinitialize (vtable+8)")

    # 4. The callee must be TestSuite::RunAll, and it must have exactly the
    #    two call sites the source has. Three would mean this is some other
    #    function and the identification is wrong.
    rel = struct.unpack_from("<i", seg, at + CALL_AT + 1)[0]
    callee = site_va + CALL_AT + 5 + rel
    callers = _callers_of(text, seg, callee)
    log.append("callee      va=0x%X, %d call sites: %s"
               % (callee, len(callers), ", ".join("0x%X" % v for v, _ in callers)))
    if len(callers) != 2:
        raise PatchError("TestSuite::RunAll should have exactly 2 call sites "
                         "(test_driver.cpp:132 and menu_item.cpp:259); found %d"
                         % len(callers))
    others = [v for v, _ in callers if v != site_va + CALL_AT]
    if len(others) != 1:
        raise PatchError("cannot separate the two call sites")
    other_va, other_off = [(v, o) for v, o in callers if v != site_va + CALL_AT][0]
    # The menu site inlines SetSavingAllowed(true) between Initialize and
    # RunAll -- `movb $0x1,0x21(%eax)` -- which the driver site does not have.
    pre = xbe.data[other_off - 16:other_off]
    if bytes.fromhex("c6402101") not in pre:
        log.append("WARNING: the other call site 0x%X does not show the inlined "
                   "SetSavingAllowed(true) store that identifies "
                   "MenuItemSuite::ActivateCurrentSuite; its preceding bytes are %s"
                   % (other_va, pre.hex(" ")))
    else:
        log.append("other site  va=0x%X is MenuItemSuite::ActivateCurrentSuite "
                   "(inlined SetSavingAllowed(true) store present) -- LEFT ALONE"
                   % other_va)

    imm_off = text["raw"] + at + PUSH_IMM_AT
    if xbe.data[imm_off - 1] != 0x6A or xbe.data[imm_off] != 0x00:
        raise PatchError("the immediate at 0x%X is not `push $0x0`: %s"
                         % (imm_off - 1, xbe.data[imm_off - 1:imm_off + 1].hex(" ")))
    log.append("push insn   xbe offset 0x%X is `6a 00` (push $0x0); the immediate "
               "byte to flip to 0x01 is xbe offset 0x%X"
               % (imm_off - 1, imm_off))

    nonzero = [s["name"] for s in xbe.sections if s["digest"].strip(b"\0")]
    if nonzero:
        raise PatchError("sections %s carry a non-zero digest; a .text edit "
                         "would invalidate it and this tool does not recompute "
                         "digests" % ", ".join(nonzero))
    log.append("all section digests are zero -- no digest to recompute")
    return imm_off, log


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("iso", help="base nxdk_pgraph_tests XISO image (read-only)")
    p.add_argument("-o", "--output", help="image to write; omit for --dry-run")
    p.add_argument("--dry-run", action="store_true",
                   help="locate and report, write nothing")
    args = p.parse_args(argv)
    if not args.dry_run and not args.output:
        p.error("need -o/--output, or --dry-run")
    if args.output and os.path.abspath(args.output) == os.path.abspath(args.iso):
        p.error("refusing to write over the input image")

    data = bytearray(open(args.iso, "rb").read())
    root_sector, root_size = mti.read_header(data)
    entries = mti.read_directory(data, root_sector, root_size)
    hit = [e for e in entries if e[0].lower() == "default.xbe"]
    if len(hit) != 1:
        raise PatchError("expected exactly one default.xbe in the root, found %d"
                         % len(hit))
    _name, sector, length, _attr = hit[0]
    xbe_base = sector * mti.SECTOR
    xbe = Xbe(bytes(data[xbe_base:xbe_base + length]))

    imm_off, log = locate(xbe)
    iso_off = xbe_base + imm_off
    print("base iso    %s (%d bytes)" % (args.iso, len(data)))
    print("default.xbe sector %d, %d bytes, at iso offset 0x%X"
          % (sector, length, xbe_base))
    for line in log:
        print("  " + line)
    print("iso offset  0x%X" % iso_off)
    if args.dry_run:
        print("dry run: nothing written")
        return 0

    assert data[iso_off] == 0x00
    data[iso_off] = 0x01
    with open(args.output, "wb") as fh:
        fh.write(data)
    print("wrote %s" % args.output)
    print("RunAll now receives true at test_driver.cpp:132; the interactive "
          "menu's own RunAll(false) is unchanged.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except PatchError as exc:
        sys.exit("refusing to patch: %s" % exc)
