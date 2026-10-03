#!/usr/bin/env python3
"""Leg S of memfast-drop-soak.json: the XBOX preamble and per-load test, keyed
on their instruction sequences (#507, lane.memfast).

    legs_read.py <capture dir> [--data rec-on.data] [--cover 0.95]

Why not jitmix.py's `preamble` role: it labels a TB's first instructions
`preamble` until it meets `mov w26, #0`, and gives up after 10. A build without
the preamble never emits that `mov`, so the role books the TB's first 10
instructions whatever they are, and reads 13% where the preamble is gone. Its
`xbox_fp` class has the matching blind spot: it keys on x26/x27 as operands,
and phase 1 returns both to the allocator.

This reader books a sample to the preamble or the per-load test only when the
instruction sits inside the emitted sequence:

  preamble   ldr w16,[x27,#0x8] ... mov w26,#0x0, found in the TB's first 12
             instructions, and only when both ends are present
  xboxchk    cbz x26 through the instruction before the softmmu LDP

and it reports the TB entry the same way on both builds, so that a stall
billed to a TB's first load can be seen to move rather than vanish:

  entry      the TB's start through the exit-request check's last instruction
             (sturb wzr,[x19,#-0xc]), which holds the hint, the preamble where
             there is one, and the check

  first      the TB's first instruction alone (the BTI landing pad), where the
             jump into the TB is billed

It also splits the softmmu compares into loads and stores, from the comparator
each one reads (CPUTLBEntry.addr_read at offset 0, addr_write at 8), which
sizes a loads-only fastmem against one with stores.

It prints the number of TBs holding each sequence. Zero TBs is the claim; a
share of 0 samples alone could be a TB that was not sampled.

Offline; reads files only. Reuses vcpuplan/jitmix.py and gta482/tbmap.py.
"""
import argparse
import bisect
import collections
import gzip
import glob
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "vcpuplan"))
sys.path.insert(0, os.path.join(HERE, "..", "gta482"))
import jitmix  # noqa: E402
import tbmap  # noqa: E402


def is_tlb_ldp(mn, ops):
    return mn == "ldp" and "[x19, #-" in ops


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dir")
    ap.add_argument("--data", default="rec-on.data")
    ap.add_argument("--cover", type=float, default=0.95)
    a = ap.parse_args()

    tbs, _ = tbmap.load_headers(a.dir)
    starts = [t[0] for t in tbs]
    tid, ips, nsamp = tbmap.jit_samples(os.path.join(a.dir, a.data), None)
    by_tb = collections.Counter()
    ip_by_tb = collections.defaultdict(list)
    for ip in ips:
        i = bisect.bisect_right(starts, ip) - 1
        if i >= 0 and ip < tbs[i][0] + tbs[i][1]:
            by_tb[i] += 1
            ip_by_tb[i].append(ip)
    mapped = sum(by_tb.values())

    bufs = []
    for f in sorted(glob.glob(os.path.join(a.dir, "codebuf-*.bin.gz"))):
        base = int(re.search(r"codebuf-([0-9a-f]+)", f).group(1), 16)
        bufs.append((base, gzip.open(f).read()))

    def code(start, size):
        for base, buf in bufs:
            if base <= start and start + size <= base + len(buf):
                return buf[start - base:start - base + size]
        return None

    chosen, acc = [], 0
    for i, n in by_tb.most_common():
        if acc >= a.cover * mapped:
            break
        chosen.append(i)
        acc += n
    blob, offs = bytearray(), {}
    for i in chosen:
        c = code(tbs[i][0], tbs[i][1])
        if c is None:
            continue
        offs[i] = len(blob)
        blob += c
        blob += b"\0" * ((-len(blob)) % 4)
    ins = jitmix.disasm(bytes(blob))

    n = collections.Counter()      # samples
    ninsn = collections.Counter()  # sample-weighted instructions per TB
    tb_with = collections.Counter()
    x2627 = collections.Counter()
    first_mn = collections.Counter()
    nkind = collections.Counter()  # sample-weighted compares per TB, by access
    skind = collections.Counter()  # samples inside compares, by access
    cov = 0
    for i in offs:
        o, size = offs[i], tbs[i][1]
        hits = collections.Counter((ip - tbs[i][0]) // 4 * 4 for ip in ip_by_tb[i])
        seq = [(addr - o, ins[addr]) for addr in range(o, o + size, 4) if addr in ins]
        w = by_tb[i]
        cov += w
        role = {}
        kinds = {}

        # the preamble, only with both ends in the first 12 instructions
        head = seq[:12]
        first = next((k for k, (_, (mn, ops)) in enumerate(head)
                      if mn == "ldr" and ops.startswith("w16, [x27, #0x8]")), None)
        last = next((k for k, (_, (mn, ops)) in enumerate(head)
                     if mn == "mov" and ops.startswith("w26, #0x0")), None)
        if first is not None and last is not None and first < last:
            tb_with["preamble"] += 1
            for k in range(first, last + 1):
                role[seq[k][0]] = "preamble"

        # the entry: TB start through the exit-request check
        end = next((k for k, (_, (mn, ops)) in enumerate(seq[:16])
                    if mn == "sturb" and "[x19, #-0xc]" in ops), None)
        if end is None:
            end = next((k + 1 for k, (_, (mn, ops)) in enumerate(seq[:16])
                        if mn == "ldur" and "[x19, #-0x10]" in ops), None)
        entry = set()
        if end is not None:
            tb_with["entry"] += 1
            entry = {seq[k][0] for k in range(0, min(end + 1, len(seq)))}

        k, had_chk = 0, False
        while k < len(seq):
            rel, (mn, ops) = seq[k]
            if mn == "cbz" and ops.startswith("x26"):
                j = k
                while j < len(seq) and not is_tlb_ldp(*seq[j][1]):
                    role[seq[j][0]] = "xboxchk"
                    j += 1
                had_chk = True
                k = j
                continue
            if is_tlb_ldp(mn, ops):
                # the comparator load names the access: CPUTLBEntry.addr_read
                # is at offset 0, addr_write at 8, addr_code at 16
                j, kind = k, "tlb_other"
                while j < len(seq):
                    m2, o2 = seq[j][1]
                    if m2 == "ldr" and re.match(r"[wx]16, \[x17\]$", o2):
                        kind = "tlb_load"
                    elif m2 == "ldr" and re.match(r"[wx]16, \[x17, #0x8\]$", o2):
                        kind = "tlb_store"
                    if m2 == "b.ne":
                        break
                    j += 1
                for q in range(k, min(j + 1, len(seq))):
                    role.setdefault(seq[q][0], "tlb")
                    kinds[seq[q][0]] = kind
                nkind[kind] += w
                k = j + 1
                continue
            k += 1
        if had_chk:
            tb_with["xboxchk"] += 1

        for rel, (mn, ops) in seq:
            if re.search(r"\b[xw]2[67]\b", ops):
                x2627[role.get(rel, "other")] += 1
        cnt = collections.Counter(role.values())
        for r, v in cnt.items():
            ninsn[r] += w * v
        ninsn["entry"] += w * len(entry)
        ninsn["all"] += w * len(seq)
        for rel, h in hits.items():
            n[role.get(rel, "body")] += h
            if rel in kinds and role.get(rel) == "tlb":
                skind[kinds[rel]] += h
            if rel in entry:
                n["entry"] += h
            if seq and rel == seq[0][0]:
                n["first"] += h
                first_mn[seq[0][1][0] + " " + seq[0][1][1]] += h

    jit = len(ips)
    tot = sum(v for r, v in n.items() if r not in ("entry", "first")) or 1
    # n holds roles only; the by-access split is kept apart in skind
    print(f"tid {tid}: {nsamp} samples, {jit} JIT ({100 * jit / nsamp:.1f}% of the thread), "
          f"{mapped} mapped, {cov} in {len(offs)} disassembled TBs")
    print(f"TBs holding the sequence: preamble {tb_with['preamble']}, "
          f"xboxchk {tb_with['xboxchk']}, entry check {tb_with['entry']} of {len(offs)}")
    print(f"instructions naming x26/x27, by role: {dict(x2627)}")
    print(f"\n{'role':10s} {'samples':>8s} {'% of JIT':>9s} {'% of thread':>12s} {'insns/TB':>9s}")
    for r in ("preamble", "xboxchk", "tlb", "body", "entry"):
        s = n[r]
        print(f"{r:10s} {s:8d} {100 * s / tot:9.1f} {100 * s / tot * jit / nsamp:12.1f} "
              f"{ninsn[r] / max(1, cov):9.1f}")
    print(f"{'all':10s} {tot:8d} {100.0:9.1f} {100 * jit / nsamp:12.1f} "
          f"{ninsn['all'] / max(1, cov):9.1f}")
    print("(entry overlaps preamble and body; it is not part of the 100%)")
    print("\nsoftmmu compares by access (what a loads-only fastmem would replace):")
    for kd in ("tlb_load", "tlb_store", "tlb_other"):
        print(f"  {kd:10s} {nkind[kd] / max(1, cov):6.2f} per executed TB, {skind[kd]:6d} samples, "
              f"{100 * skind[kd] / tot * jit / nsamp:5.1f}% of the thread")
    s = n["first"]
    print(f"\nthe TB's first instruction alone: {s} samples, {100 * s / tot:.1f}% of JIT, "
          f"{100 * s / tot * jit / nsamp:.1f}% of the thread; it is "
          + ", ".join(f"`{k}` {v}" for k, v in first_mn.most_common(3)))


if __name__ == "__main__":
    main()
