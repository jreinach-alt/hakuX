#!/usr/bin/env python3
"""Disassemble the guest code behind TB pcs, from a session's dumps (#413).

    guestcode.py <session dir> <pc hex> [<pc hex> ...] [--before 32] [--after 48]

The TB headers in codebuf-*.bin.gz (layout in docs/lanes/gta482/tbmap.py) give
each pc's physical page (page_addr[0], offset 72). The guest RAM is whichever
ram-*.bin.gz holds, at that physical page, the bytes the header's pc implies:
checked, not assumed, by requiring the TB's own bytes to decode to the TB's
instruction count (icount, offset 26). Prints the region around each pc,
32-bit x86, with objdump.
"""
import glob
import gzip
import os
import re
import subprocess
import sys
import tempfile

HDR = 192


def headers(d):
    out = {}
    for f in sorted(glob.glob(os.path.join(d, "codebuf-*.bin.gz"))):
        base = int(re.search(r"codebuf-([0-9a-f]+)\.bin", f).group(1), 16)
        buf = gzip.open(f).read()
        for off in range(0, len(buf) - HDR, 64):
            tcptr = int.from_bytes(buf[off + 40:off + 48], "little")
            if tcptr != base + off + HDR:
                continue
            pc = int.from_bytes(buf[off:off + 8], "little") & 0xffffffff
            gsize = int.from_bytes(buf[off + 24:off + 26], "little")
            icount = int.from_bytes(buf[off + 26:off + 28], "little")
            page0 = int.from_bytes(buf[off + 72:off + 80], "little")
            out.setdefault(pc, (gsize, icount, page0))
    return out


def objdump(code, vma):
    with tempfile.NamedTemporaryFile(suffix=".bin") as t:
        t.write(code)
        t.flush()
        r = subprocess.run(["objdump", "-D", "-b", "binary", "-m", "i386", "-M", "intel",
                            f"--adjust-vma={vma:#x}", t.name], capture_output=True, text=True)
    return [l for l in r.stdout.splitlines() if re.match(r"^\s+[0-9a-f]+:", l)]


def main():
    d = sys.argv[1]
    args = sys.argv[2:]
    before, after = 32, 48
    pcs = []
    i = 0
    while i < len(args):
        if args[i] == "--before":
            before = int(args[i + 1]); i += 2
        elif args[i] == "--after":
            after = int(args[i + 1]); i += 2
        else:
            pcs.append(int(args[i], 16)); i += 1
    hdr = headers(d)
    rams = [gzip.open(f).read() for f in sorted(glob.glob(os.path.join(d, "ram-*.bin.gz")))]
    for pc in pcs:
        if pc not in hdr:
            print(f"{pc:08x}: no header")
            continue
        gsize, icount, page0 = hdr[pc]
        # page_addr is a ram_addr_t: an offset in QEMU's RAM-block space, not a
        # guest physical address. On this build the kernel's idle loop
        # (virtual 0x8001b030, physical 0x1b030) has page_addr 0x401b030, so
        # main RAM sits at ram_addr 0x4000000; the offset is tried, and the
        # TB's own bytes must decode to its icount.
        ra = (page0 & ~0xfff) + (pc & 0xfff)
        print(f"== pc {pc:08x}: {gsize} B, {icount} insns, ram_addr {ra:#x}")
        done = False
        for base in (0x4000000, 0, 0x8000000):
            phys = ra - base
            for ri, ram in enumerate(rams):
                if phys < 0 or phys + gsize > len(ram):
                    continue
                own = objdump(ram[phys:phys + gsize], pc)
                if len(own) != icount:
                    continue
                lo = max(0, phys - before)
                print(f"   ram {ri}, guest phys {phys:#x} (TB bytes decode to its {icount} insns):")
                for l in objdump(ram[lo:phys + gsize + after], pc - (phys - lo)):
                    mark = ">>" if pc <= int(l.split(":")[0], 16) < pc + gsize else "  "
                    print(f"   {mark} {l.strip()}")
                done = True
                break
            if done:
                break
        if not done:
            print("   no RAM dump holds bytes that decode to this TB")


if __name__ == "__main__":
    main()
