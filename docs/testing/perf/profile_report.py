#!/usr/bin/env python3
"""Report a profile_guest.sh capture: thread split, the guest thread's top
self symbols, the lever groups, and who calls the top items.

    profile_report.py PERF_DATA [--symfs DIR] [--top 25] [--callers N]
                      [--tid TID] [--symbol SYM ...]

The guest thread is the busiest thread named `qemu_main` unless --tid names
one; the 2026-09-11 profile's guest thread was the 35.6% `qemu_main`, and
the renderer is `Thread-6`. The thread split is printed so the choice can be
checked by eye.

Groups (first match wins, in this order; the patterns are the whole model,
so read them before quoting a group share):

  generated   samples whose dso is not a file: JIT'd guest code
  tc-maint    translation-cache maintenance: invalidation, dirty tracking,
              jump-cache flushes, TB lookups, I-cache flushes, TLB flushes
  translate   building new TBs (tb_gen_code, the TCG front and back end)
  softmmu     softmmu slow paths: TLB misses and fills, MMIO, page walks
  helpers     the remaining helper_* and softfloat
  other       everything else (kernel, libc, locks, audio, ...)

--symbol prints the callers of a symbol (callee graph); the top --callers
self symbols get the same, plus every tlb_flush* entry point that sampled.
"""
import argparse
import csv
import io
import re
import subprocess
import sys

SIMPLEPERF = ("/home/justin/Android/Sdk/ndk/29.0.14206865/simpleperf/bin/"
              "linux/x86_64/simpleperf")

GROUPS = [
    ("tc-maint", r"^(tlb_reset_dirty|tcg_flush_jmp_cache|tlb_flush|"
                 r"tlb_flush_\w+|tlb_protect\w*|tlb_unprotect\w*|"
                 r"tb_invalidate\w*|tb_phys_invalidate\w*|"
                 r"do_tb_phys_invalidate|tb_remove\w*|tb_jmp_\w+|"
                 r"tb_page_\w+|page_collection\w*|tb_lookup\w*|"
                 r"tb_htable\w*|tb_tc_cmp|tb_code_hash_func|tb_link_page|"
                 r"tcg_tb_lookup|tcg_tb_remove|tcg_tb_insert|qht_\w+|"
                 r"q_tree_\w+|g_tree_\w+|flush_idcache_range|"
                 r"__clear_cache|helper_lookup_tb_ptr|notdirty_write|"
                 r"cpu_physical_memory_\w*dirty\w*|"
                 r"physical_memory_\w*dirty\w*|tb_invalidate_phys\w*|"
                 r"x86_get_tb_cpu_state|curr_cflags|tb_flush\w*|"
                 r"tcg_flush_\w+|find_next_bit|invalidate_page_bitmap|"
                 r"page_find_alloc|page_find|tb_page_addr\w*)$"),
    ("translate", r"^(tb_gen_code|setjmp_gen_code|gen_intermediate_code|"
                  r"translator_\w+|tcg_gen_\w+|tcg_optimize\w*|"
                  r"tcg_code_gen\w*|tcg_reg_alloc\w*|liveness_pass\w*|"
                  r"tcg_out\w*|tcg_la_\w+|tcg_func_start|tcg_temp_\w+|"
                  r"tcg_op_\w+|tcg_emit_\w+|reachable_code_pass|"
                  r"disas_insn\w*|gen_\w+|i386_tr_\w+|"
                  r"cpu_ld\w*_code\w*|get_page_addr_code\w*|"
                  r"translator_ld\w*|la_\w+|tcg_constant\w*)$"),
    ("softmmu", r"^(mmu_lookup\w*|probe_access\w*|do_ld\w*_mmu|do_st\w*_mmu|"
                r"do_ld_\w+|do_st_\w+|helper_ld\w*_mmu|helper_st\w*_mmu|"
                r"helper_[lsd]\w*_mmu|cpu_ld\w*_mmu|cpu_st\w*_mmu|"
                r"mmu_translate|tlb_set_page\w*|tlb_fill\w*|"
                r"x86_cpu_tlb_fill|get_physical_address|"
                r"address_space_\w+|flatview_\w+|memory_region_\w+|"
                r"io_readx|io_writex|int_ld\w*|int_st\w*|"
                r"qemu_ram_block_from_host|qemu_ram_addr_from_host\w*|"
                r"mem_access_callback\w*|mem_check_access\w*|"
                r"victim_tlb_hit|tlb_hit\w*|ptw_\w+|"
                r"prepare_host_addr|cpu_mmu_index\w*|"
                r"phys_page_find|address_space_translate_internal)$"),
    ("helpers", r"^(helper_\w+|float\d+_\w+|floatx80_\w+|parts\w*_\w+|"
                r"cpu_cc_compute_\w+|compute_\w+|"
                r"cpu_x86_\w+|do_interrupt\w*|raise_\w+)$"),
]
GROUP_RE = [(g, re.compile(p)) for g, p in GROUPS]
ORDER = ["generated", "tc-maint", "translate", "softmmu", "helpers", "other"]


def run(args):
    r = subprocess.run([SIMPLEPERF, "report"] + args, capture_output=True,
                       text=True)
    if r.returncode:
        sys.exit("simpleperf report %s failed:\n%s" % (" ".join(args),
                                                       r.stderr[-2000:]))
    return r.stdout


def rows(text):
    """Parse --csv output into dicts, skipping simpleperf's header lines."""
    lines = text.splitlines()
    start = next(i for i, ln in enumerate(lines) if ln.startswith("Overhead"))
    return list(csv.DictReader(io.StringIO("\n".join(lines[start:]))))


def classify(dso, sym):
    # TCG's code buffer is an anonymous mapping, which simpleperf reports as
    # dso `unknown`. [vdso] and [kernel.kallsyms] are not generated code.
    if dso == "unknown" or dso.startswith(("[anon", "//anon", "/memfd:")):
        return "generated"
    base = sym.split("(")[0].strip()
    for g, rx in GROUP_RE:
        if rx.match(base):
            return g
    return "other"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("data")
    ap.add_argument("--symfs")
    ap.add_argument("--top", type=int, default=25)
    ap.add_argument("--callers", type=int, default=3)
    ap.add_argument("--tid")
    ap.add_argument("--symbol", action="append", default=[])
    a = ap.parse_args()
    base = ["-i", a.data] + (["--symfs", a.symfs] if a.symfs else [])

    threads = rows(run(base + ["--csv", "-n", "--sort", "comm,tid"]))
    print("== thread split (share of all samples)")
    for t in threads[:12]:
        print("  %7s  %-24s %s" % (t["Overhead"], t["Command"], t["Tid"]))
    tid = a.tid or next((t["Tid"] for t in threads
                         if t["Command"] == "qemu_main"), None)
    if tid is None:
        sys.exit("no thread named qemu_main in the split; pass --tid")
    total = sum(int(t["Sample"]) for t in threads)
    gs = next((int(t["Sample"]) for t in threads if t["Tid"] == tid), None)
    if gs is None:
        sys.exit("--tid %s is not a thread in the split" % tid)
    print("guest thread tid %s: %d of %d samples (%.1f%%)"
          % (tid, gs, total, 100.0 * gs / total))

    syms = rows(run(base + ["--csv", "-n", "--tids", tid,
                            "--sort", "dso,symbol"]))
    print("\n== guest thread, top %d self symbols (share of the guest "
          "thread)" % a.top)
    for s in syms[:a.top]:
        print("  %7s  %-10s %-40s %s" % (s["Overhead"],
                                         classify(s["Shared Object"],
                                                  s["Symbol"]),
                                         s["Symbol"][:40],
                                         s["Shared Object"].split("/")[-1]))
    # Shares from sample counts, not from the printed percentages: a
    # thread has thousands of JIT addresses at 0.01% each, and summing the
    # rounded column over-counts the group by ten points or more.
    gsum = sum(int(s["Sample"]) for s in syms)
    groups = dict.fromkeys(ORDER, 0)
    members = {g: [] for g in ORDER}
    for s in syms:
        g = classify(s["Shared Object"], s["Symbol"])
        groups[g] += int(s["Sample"])
        members[g].append(s)
    print("\n== lever groups (share of the guest thread, %d samples)" % gsum)
    for g in ORDER:
        top = ", ".join("%s %s" % (m["Symbol"].split("(")[0][:28],
                                   m["Overhead"]) for m in members[g][:4])
        print("  %6.2f%%  %-10s %s" % (100.0 * groups[g] / gsum, g, top))

    want = [s["Symbol"] for s in syms[:a.callers]]
    want += [s["Symbol"] for s in syms
             if s["Symbol"].split("(")[0].startswith("tlb_flush")
             and s["Symbol"] not in want]
    want += [w for w in a.symbol if w not in want]
    for w in want:
        print("\n== callers of %s (guest thread, callee graph)" % w)
        out = run(base + ["--tids", tid, "--sort", "symbol", "-g", "callee",
                          "--symbols", w, "--percent-limit", "0.5",
                          "--max-stack", "8"])
        body = out.splitlines()
        i = next((k for k, ln in enumerate(body) if ln.startswith("Overhead")),
                 0)
        for ln in body[i:i + 60]:
            print("  " + ln)
    return 0


if __name__ == "__main__":
    sys.exit(main())
