#!/usr/bin/env python3
"""Generate the probe's write allow-list from this tree's NV2A device model.

The allow-list is DERIVED, never transcribed. hw/xbox/nv2a/nv2a.c owns the
block table; this reads it and emits nv2a_window.h. Run with --check in CI to
fail if the header has drifted from the model.

Why generated: a hand-copied address that is one digit wrong is a write into
whatever lives next door, and on this machine "next door" eventually means
flash or the SMC. A transcription cannot be re-verified; a derivation can.
"""
import argparse, os, re, sys

ENTRY = re.compile(
    r"ENTRY\(\s*(\w+)\s*,\s*\w+\s*,\s*(0x[0-9a-fA-F]+)\s*,\s*(0x[0-9a-fA-F]+)\s*\)")
WINDOW = re.compile(
    r'memory_region_init\(\s*&d->mmio\s*,[^,]*,\s*"nv2a-mmio"\s*,\s*(0x[0-9a-fA-F]+)\s*\)')

# Blocks whose writes phase one refuses even though they sit inside the window.
# Each needs a reason; an unexplained exclusion is one somebody deletes later.
PHASE1_WRITE_EXCLUDED = {
    "USER": "FIFO DMA-push user area: a write here submits pushbuffer work, "
            "which phase one explicitly does not do.",
}

# PRAMIN (0x700000, 1 MiB) is real silicon but its ENTRY is commented out in
# nv2a.c, so this tree models nothing there and a measured mask would have no
# counterpart to disagree with. strip_comments() keeps it out of the list
# entirely rather than listing it as unwritable, because "absent from the
# model" and "modelled but refused" are different facts.

def strip_comments(src):
    """Remove C comments before matching.

    Not cosmetic. nv2a.c carries a commented-out block:

        // ENTRY(PRAMIN,   pramin,   0x700000, 0x100000),

    and a regex over raw text happily matches it, which would have put a block
    this tree does not model into the WRITE allow-list. A generator that reads
    disabled code is no safer than the transcription it replaced.
    """
    src = re.sub(r"/\*.*?\*/", " ", src, flags=re.S)
    src = re.sub(r"//[^\n]*", " ", src)
    return src


def parse(nv2a_c):
    src = strip_comments(open(nv2a_c, encoding="utf-8").read())
    m = WINDOW.search(src)
    if not m:
        sys.exit("gen_window: could not find the nv2a-mmio memory_region_init "
                 "in %s -- the model changed shape, so this generator must be "
                 "updated rather than guessed around." % nv2a_c)
    size = int(m.group(1), 16)
    # Only the blocktable initialiser, not every ENTRY-looking macro in the file.
    start = src.index("blocktable[NV_NUM_BLOCKS] = {")
    end = src.index("};", start)
    blocks = [(n, int(o, 16), int(s, 16)) for n, o, s in ENTRY.findall(src[start:end])]
    if not blocks:
        sys.exit("gen_window: blocktable parsed to zero entries")
    for n, o, s in blocks:
        if o + s > size:
            sys.exit("gen_window: block %s (0x%06x+0x%06x) runs past the 0x%x "
                     "window" % (n, o, s, size))
    return size, sorted(blocks, key=lambda b: b[1])

# Registers a BLIND write sweep must not touch, by name pattern, each with the
# reason it is here. Derived against nv2a_regs.h rather than listed by address,
# so a header change cannot silently unprotect one.
#
# This list exists because the first hardware run wrote 0 to NV_PMC_ENABLE and
# stopped the console dead -- CPU included, so the watchdog could not help and
# it took a power cycle. The hazard had been reasoned about beforehand and the
# sweep was allowed to hit it anyway, trusting a recovery path that had never
# been exercised on hardware. Reasoning about a hazard is not the same as
# refusing it.
#
# The PLL entries are the serious ones. A blind 0xFFFFFFFF into a memory- or
# core-clock coefficient is not a hang, it is an out-of-spec clock, and the
# sweep would have reached them the moment it widened past PMC.
HAZARD_PATTERNS = [
    (r"_ENABLE$",        "engine enable: clearing it stops PFIFO/PGRAPH and the "
                         "machine with them (measured: full lockup, power cycle)"),
    (r"PLL_COEFF$",      "clock PLL coefficient: a blind value is an out-of-spec "
                         "core, memory or video clock, not merely a hang"),
    (r"PLL_TEST",        "PLL test path: same clock domain as the coefficients"),
    (r"_RESET",          "reset control"),
    (r"^NV_PFIFO_CACHE", "pushbuffer cache/DMA control: phase one does not submit "
                         "pushbuffer work and must not start by accident"),
    (r"^NV_PMC_BOOT",    "chip straps/identity; 0x004 latched and would not restore"),
]


# Hazards MEASUREMENT found, which a name-based rule cannot see because these
# registers are not declared in nv2a_regs.h at all. Keyed by absolute BAR
# offset. This list only grows by someone running into something.
EMPIRICAL_HAZARDS = {
    0x000200: "NV_PMC_ENABLE: writing 0 stopped the console dead on 2026-09-20 "
              "-- no ICMP, ARP FAILED, watchdog could not help because the CPU "
              "was gone too. Power cycle required.",
    0x000004: "NV_PMC_BOOT_1: its low bit is the MMIO endian switch. Writing "
              "ones here byte-swapped every subsequent access, the sweep ran on "
              "for 120 more registers, and two 'findings' were published that "
              "were declared bits seen through a byte swap. Note what this one "
              "proves: a NAME-based list could never have caught it, because "
              "BOOT_1 is not spelled like anything dangerous. It is hazardous "
              "for its SEMANTICS -- a write that redefines how every later "
              "access is interpreted. The general defence is the canary in "
              "sweep_writable_bits.py, not this entry.",
}


def parse_hazards(regs_h, blocks):
    """Absolute BAR offsets of hazardous registers, derived from the header."""
    import re as _re
    base = {name: off for name, off, _size in blocks}
    reg_re = _re.compile(r"^#define\s+(NV_(\w+?)_\w+|NV_\w+)\s+(0x[0-9A-Fa-f]+)\s*$")
    out = {}
    for line in open(regs_h, encoding="utf-8"):
        m = _re.match(r"^#define\s+(NV_\w+)\s+(0x[0-9A-Fa-f]+)\s*$", line.rstrip())
        if not m:
            continue
        name, off = m.group(1), int(m.group(2), 16)
        blk = None
        for b in base:
            if name.startswith("NV_" + b + "_") or name == "NV_" + b:
                if blk is None or len(b) > len(blk):
                    blk = b
        if blk is None:
            continue
        for pat, why in HAZARD_PATTERNS:
            if _re.search(pat, name):
                out[base[blk] + off] = (name, why)
                break
    for off, why in EMPIRICAL_HAZARDS.items():
        out.setdefault(off, ("(measured)", why))
    return out


def render(size, blocks, nv2a_c, hazards=None):
    w = [b for b in blocks if b[0] not in PHASE1_WRITE_EXCLUDED]
    out = []
    A = out.append
    A("/* GENERATED by tools/nv2a_probe/gen_window.py -- do not edit.")
    A(" *")
    A(" * Source of truth: %s" % nv2a_c)
    A(" * Regenerate:      python3 tools/nv2a_probe/gen_window.py --write")
    A(" * Verify:          python3 tools/nv2a_probe/gen_window.py --check")
    A(" *")
    A(" * The NV2A MMIO BAR is %d MiB. Everything outside it is refused by the" % (size >> 20))
    A(" * probe itself. Flash is mirrored at 0xff000000 and the SMC, SMBus and")
    A(" * EEPROM are I2C devices behind I/O ports -- none of them is MMIO, so an")
    A(" * MMIO-only probe cannot reach them even if this list were wrong.")
    A(" */")
    A("#ifndef NV2A_WINDOW_H")
    A("#define NV2A_WINDOW_H")
    A("")
    A("#include <stdint.h>")
    A("#include <stdbool.h>")
    A("")
    A("#define NV2A_MMIO_SIZE 0x%08xu" % size)
    A("")
    A("typedef struct { const char *name; uint32_t offset, size; bool writable; } nv2a_block_t;")
    A("")
    A("static const nv2a_block_t kNv2aBlocks[] = {")
    for n, o, s in blocks:
        excl = n in PHASE1_WRITE_EXCLUDED
        A('    { "%s",%s 0x%06xu, 0x%06xu, %s },' %
          (n, " " * max(0, 9 - len(n)), o, s, "false" if excl else "true"))
    A("};")
    A("#define NV2A_NUM_BLOCKS %d" % len(blocks))
    A("")
    for n, why in sorted(PHASE1_WRITE_EXCLUDED.items()):
        A("/* write-excluded: %s -- %s */" % (n, why))
    A("")
    A("/* Reads may be wider than writes: any offset inside the BAR. */")
    A("static inline bool nv2a_offset_readable(uint32_t off)")
    A("{")
    A("    return off + 4u > off && off + 4u <= NV2A_MMIO_SIZE;")
    A("}")
    A("")
    A("/* Registers a blind sweep must never write. Refused in the PROBE, not")
    A(" * only in the driver, because the host is the thing most likely to have")
    A(" * a bug in it. See gen_window.py for why each is here. */")
    A("typedef struct { uint32_t offset; const char *name; } nv2a_hazard_t;")
    A("static const nv2a_hazard_t kNv2aHazards[] = {")
    for off, (name, _why) in sorted((hazards or {}).items()):
        A('    { 0x%06xu, "%s" },' % (off, name))
    A("};")
    A("#define NV2A_NUM_HAZARDS %d" % len(hazards or {}))
    A("")
    A("static inline const char *nv2a_hazard_name(uint32_t off)")
    A("{")
    A("    for (int i = 0; i < NV2A_NUM_HAZARDS; ++i)")
    A("        if (kNv2aHazards[i].offset == off) return kNv2aHazards[i].name;")
    A("    return 0;")
    A("}")
    A("")
    A("/* Writes must land inside a modelled, write-enabled block. */")
    A("static inline bool nv2a_offset_writable(uint32_t off)")
    A("{")
    A("    if (off & 3u) return false;              /* unaligned */")
    A("    if (off + 4u <= off) return false;       /* wrap */")
    A("    for (int i = 0; i < NV2A_NUM_BLOCKS; ++i) {")
    A("        const nv2a_block_t *b = &kNv2aBlocks[i];")
    A("        if (!b->writable) continue;")
    A("        if (off >= b->offset && off + 4u <= (uint32_t)(b->offset + b->size))")
    A("            return true;")
    A("    }")
    A("    return false;")
    A("}")
    A("")
    A("/* The check the probe actually applies to a write. */")
    A("static inline bool nv2a_offset_write_allowed(uint32_t off)")
    A("{")
    A("    return nv2a_offset_writable(off) && nv2a_hazard_name(off) == 0;")
    A("}")
    A("")
    A("#endif /* NV2A_WINDOW_H */")
    return "\n".join(out) + "\n"

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--root", default=os.path.join(os.path.dirname(__file__), "..", ".."))
    p.add_argument("--write", action="store_true")
    p.add_argument("--check", action="store_true")
    p.add_argument("--print-blocks", action="store_true")
    a = p.parse_args()
    root = os.path.abspath(a.root)
    nv2a_c = os.path.join(root, "hw", "xbox", "nv2a", "nv2a.c")
    rel = os.path.relpath(nv2a_c, root)
    size, blocks = parse(nv2a_c)
    hazards = parse_hazards(os.path.join(root, "hw", "xbox", "nv2a", "nv2a_regs.h"),
                            blocks)
    text = render(size, blocks, rel, hazards)
    hdr = os.path.join(root, "tools", "nv2a_probe", "probe", "nv2a_window.h")
    if a.write:
        hz = os.path.join(root, "tools", "nv2a_probe", "host", "hazards.json")
        os.makedirs(os.path.dirname(hz), exist_ok=True)
        import json as _json
        _json.dump({"%06X" % o: {"name": n, "why": w}
                    for o, (n, w) in sorted(hazards.items())},
                   open(hz, "w", encoding="utf-8"), indent=2)
    if a.print_blocks:
        print("window 0x%08x (%d MiB), %d blocks" % (size, size >> 20, len(blocks)))
        for n, o, s in blocks:
            mark = "" if n not in PHASE1_WRITE_EXCLUDED else "   [writes refused]"
            print("  %-9s 0x%06x .. 0x%06x  (0x%06x)%s" % (n, o, o + s, s, mark))
        return 0
    if a.check:
        if not os.path.exists(hdr):
            print("nv2a_window.h missing; run --write", file=sys.stderr); return 1
        if open(hdr, encoding="utf-8").read() != text:
            print("nv2a_window.h is stale: %s changed. Run "
                  "tools/nv2a_probe/gen_window.py --write" % rel, file=sys.stderr)
            return 1
        print("nv2a_window.h matches %s" % rel); return 0
    if a.write:
        os.makedirs(os.path.dirname(hdr), exist_ok=True)
        open(hdr, "w", encoding="utf-8").write(text)
        print("wrote %s" % os.path.relpath(hdr, root)); return 0
    p.error("one of --write / --check / --print-blocks")

if __name__ == "__main__":
    sys.exit(main())
