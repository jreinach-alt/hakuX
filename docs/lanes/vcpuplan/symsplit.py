#!/usr/bin/env python3
"""The vCPU thread's samples in #507's buckets, by symbol (lane.vcpuplan).

    symsplit.py <rec-on.data> [--tid T] [--top 25]

Counts `simpleperf report-sample` records (not the rounded report
percentages; memory: simpleperf rounding inflates the JIT) for one thread
(default: the thread with the most JIT samples, which is the vCPU) and books
each sample's leaf symbol into a bucket:

  jit        anonymous executable memory (the TCG code buffer)
  lookup     tb_lookup*, helper_lookup_tb_ptr, qht_*, tb_htable*, tb_jmp_cache,
             cpu_get_tb_cpu_state, x86_get_tb_cpu_state, tb_lookup_cmp
  softmmu    tlb_*, *_mmu, probe_access*, get_page_addr_code*, x86_cpu_tlb_fill,
             mmu_translate, notdirty*, mem_access_callback*, do_ld*/do_st*
             (non-MMIO), store_helper, cpu_ld*/cpu_st*
  mmio       *mmio*, io_readx/io_writex, memory_region_dispatch*, address_space_*
  fp         helper_f*, helper_*ps/pd/ss/sd*, float32_*/float64_*/floatx80_*,
             helper_cvt*, update_fp_status, helper_ldmxcsr
  translate  tb_gen_code, gen_intermediate_code, tcg_gen_code, tcg_*opt*,
             translator_*, disas_*, tb_invalidate*, tb_phys_invalidate, tb_link*
  loop       cpu_exec*, cpu_handle_*, cpu_loop_exit*, cpu_tb_exec,
             helper_cc_compute*, other helper_* (counted separately below)
  kernel     [kernel.kallsyms] and unknown kernel addresses
  other      everything else (libc, the emulator's other code)

Offline; reads the file only.
"""
import argparse
import collections
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "gta482"))
import tbmap  # noqa: E402

RULES = [
    ("lookup", r"^(tb_lookup|helper_lookup_tb_ptr|qht_|tb_htable|tb_jmp_cache|cpu_get_tb_cpu_state|x86_get_tb_cpu_state|tb_cmp|tb_lookup_cmp)"),
    ("mmio", r"(mmio|^io_readx|^io_writex|^memory_region_dispatch|^address_space_|^flatview_|^memory_region_read|^memory_region_write|^access_with_adjusted)"),
    ("softmmu", r"^(tlb_|.*_mmu$|.*_mmu_|probe_access|get_page_addr_code|x86_cpu_tlb_fill|mmu_translate|get_physical_address|notdirty|mem_access_callback|do_ld|do_st|store_helper|load_helper|cpu_ld|cpu_st|helper_ld|helper_st|victim_tlb|tlb_fill|page_collection|cpu_physical_memory|mmu_lookup|qemu_ram_block_from_host)"),
    ("fp", r"^(helper_f|helper_\w+(ps|pd|ss|sd)(_xmm|_mmx)?$|float32_|float64_|floatx80_|helper_cvt|update_fp_status|update_mxcsr|helper_ldmxcsr|helper_rsqrt|helper_rcp|round_|parts_|soft_f)"),
    ("translate", r"^(tb_gen_code|gen_intermediate_code|tcg_gen_code|tcg_optimize|tcg_|translator_|disas_|i386_tr_|x86_tr_|tb_invalidate|tb_phys_invalidate|tb_link|tb_page|do_tb_phys|tb_remove|tcg_out|tier1_)"),
    ("loop", r"^(cpu_exec|cpu_handle_|cpu_loop_exit|cpu_tb_exec|cpu_io_recompile|helper_cc_compute|cc_compute|compute_all|helper_)"),
]


def bucket(dso, sym):
    if dso == "unknown" or dso.startswith("[anon") or dso.startswith("//anon") or "memfd" in dso:
        return "jit"
    if "kernel" in dso:
        return "kernel"
    for name, rx in RULES:
        if re.search(rx, sym):
            return name
    return "other"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("data")
    ap.add_argument("--tid")
    ap.add_argument("--top", type=int, default=25)
    ap.add_argument("--symfs", help="simpleperf --symfs dir holding the matching libxemu.so")
    a = ap.parse_args()
    cmd = [tbmap.SP, "report-sample", "-i", a.data]
    if a.symfs:
        cmd += ["--symfs", a.symfs]
    p = subprocess.Popen(cmd,
                         stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
    per = collections.defaultdict(collections.Counter)  # tid -> (dso, sym) -> n
    cur = dso = None
    for line in p.stdout:
        s = line.strip()
        if s.startswith("thread_id:"):
            cur = s.split()[1]
            dso = None
        elif s.startswith("file:") and dso is None:
            dso = s.split(None, 1)[1] if len(s.split()) > 1 else "unknown"
        elif s.startswith("symbol:") and cur is not None and dso is not None:
            sym = s.split(None, 1)[1] if len(s.split()) > 1 else "?"
            per[cur][(dso, sym)] += 1
            cur = None  # leaf frame only
    p.wait()
    tid = a.tid or max(per, key=lambda t: sum(n for (d, _), n in per[t].items() if bucket(d, "") == "jit"))
    c = per[tid]
    tot = sum(c.values())
    b = collections.Counter()
    for (d, s), n in c.items():
        b[bucket(d, s)] += n
    print(f"tid {tid}: {tot} samples")
    for k in ("jit", "lookup", "softmmu", "fp", "mmio", "translate", "loop", "kernel", "other"):
        print(f"  {k:9s} {b[k]:6d}  {100 * b[k] / max(1, tot):5.1f}%")
    print(f"\ntop symbols outside the JIT")
    for (d, s), n in [x for x in c.most_common() if bucket(*x[0]) != "jit"][:a.top]:
        print(f"  {100 * n / tot:5.2f}%  {bucket(d, s):9s} {s[:70]}  [{os.path.basename(d)}]")


if __name__ == "__main__":
    main()
