#!/usr/bin/env python3
"""Where each thread's on-CPU samples go in a simpleperf record, host side (#413).

    hostsplit.py <rec.data> [--tid T] [--top 25]

Prints every thread's sample count and share of the record, then for one
thread (default: the one with the most JIT samples, the vCPU) its samples by
leaf: JIT code (anonymous), each named leaf symbol, and a fixed set of
"chain contains" classes, where a sample counts once for every class that has
a frame anywhere in its callchain:

  mmio      io_readx / io_writex / memory_region_dispatch_* / int_ld*_mmu io paths
  iorecomp  cpu_io_recompile
  translate tb_gen_code / tcg_gen_code / gen_intermediate_code
  invalid   tb_invalidate_* / tb_phys_invalidate / page_collection_*
  ide       ide_* / ahci / ata / bmdma / cd_read / blk_* / bdrv_* / pread
  lock      qemu_mutex_lock* / bql_lock* / pthread_mutex_lock
  halt      qemu_wait_io_event / qemu_cond_wait / helper_hlt

The classes overlap (an MMIO read of an IDE register is mmio and ide), so they
do not sum to 100.
"""
import argparse
import collections
import glob
import os
import re
import subprocess

NDK = sorted(glob.glob(os.path.expanduser("~/Android/Sdk/ndk/*")))[-1]
SP = NDK + "/simpleperf/bin/linux/x86_64/simpleperf"
CLASSES = [
    ("mmio", re.compile(r"^(io_readx|io_writex|do_ld_mmio|do_st_mmio|memory_region_dispatch_(read|write)|address_space_(ld|st|read|write)|int_ld_mmio|int_st_mmio|do_ld\d*_mmio|do_st\d*_mmio|helper_(in|out)[bwl])")),
    ("iorecomp", re.compile(r"^cpu_io_recompile")),
    ("translate", re.compile(r"^(tb_gen_code|tcg_gen_code|gen_intermediate_code|translator_loop|setjmp_gen_code)")),
    ("invalid", re.compile(r"^(tb_invalidate|tb_phys_invalidate|page_collection|do_tb_phys_invalidate|tb_flush)")),
    ("ide", re.compile(r"^(ide_|ahci|ata_|bmdma|cd_read|blk_|bdrv_|raw_co_|handle_aiocb|pread|preadv|__pread)")),
    ("lock", re.compile(r"^(qemu_mutex_lock|bql_lock|qemu_bql_lock|pthread_mutex_lock|__pthread_mutex_lock)")),
    ("halt", re.compile(r"^(qemu_wait_io_event|qemu_cond_wait|qemu_cond_timedwait|helper_hlt|qemu_sem_timedwait)")),
]


def is_jit(f):
    return f == "unknown" or f.startswith("[anon") or f.startswith("//anon") or "memfd" in f


def samples(data):
    """yield (tid, tname, time, [(file, symbol), ...] leaf first)"""
    p = subprocess.Popen([SP, "report-sample", "-i", data, "--show-callchain"],
                         stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
    cur = None
    f = None
    for line in p.stdout:
        s = line.strip()
        if s == "sample:":
            if cur:
                yield cur
            cur = [None, None, None, []]
        elif cur is None:
            continue
        elif s.startswith("thread_id:"):
            cur[0] = s.split()[1]
        elif s.startswith("thread_name:"):
            cur[1] = s.split(None, 1)[1] if len(s.split()) > 1 else ""
        elif s.startswith("time:"):
            cur[2] = int(s.split()[1])
        elif s.startswith("file:"):
            f = s.split(None, 1)[1] if len(s.split()) > 1 else ""
        elif s.startswith("symbol:"):
            cur[3].append((f, s.split(None, 1)[1] if len(s.split()) > 1 else ""))
    if cur:
        yield cur
    p.wait()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("data")
    ap.add_argument("--tid")
    ap.add_argument("--top", type=int, default=25)
    a = ap.parse_args()

    per = collections.Counter()
    names = {}
    jit = collections.Counter()
    by_tid = collections.defaultdict(list)
    t0 = t1 = None
    for tid, tname, t, chain in samples(a.data):
        per[tid] += 1
        names[tid] = tname
        if t is not None:
            t0 = t if t0 is None else min(t0, t)
            t1 = t if t1 is None else max(t1, t)
        if chain and is_jit(chain[0][0]):
            jit[tid] += 1
        by_tid[tid].append(chain)
    n = sum(per.values())
    span = (t1 - t0) / 1e9 if t0 else 0
    print(f"{n} samples over {span:.2f} s")
    print(f"  {'tid':>6} {'thread':18} {'samples':>8} {'cpu %':>6} {'JIT':>6}")
    for tid, c in per.most_common(14):
        print(f"  {tid:>6} {names[tid][:18]:18} {c:8d} {100 * c / 1000 / max(span, 1e-9):6.1f} {jit[tid]:6d}")
    tid = a.tid or (jit.most_common(1)[0][0] if jit else per.most_common(1)[0][0])
    chains = by_tid[tid]
    m = len(chains)
    print(f"\nthread {tid} ({names.get(tid)}): {m} samples, {100 * m / 1000 / max(span, 1e-9):.1f}% of one CPU")
    leaf = collections.Counter()
    cls = collections.Counter()
    for ch in chains:
        if not ch:
            continue
        f, sym = ch[0]
        leaf["[JIT]" if is_jit(f) else sym] += 1
        hit = set()
        for _, s in ch:
            for k, rx in CLASSES:
                if rx.search(s):
                    hit.add(k)
        for k in hit:
            cls[k] += 1
    print("  chain contains (overlapping):")
    for k, _ in CLASSES:
        print(f"    {k:10} {cls[k]:6d}  {100 * cls[k] / max(1, m):5.1f}%")
    print(f"  top leaves:")
    for s, c in leaf.most_common(a.top):
        print(f"    {c:6d}  {100 * c / max(1, m):5.1f}%  {s[:90]}")


if __name__ == "__main__":
    main()
