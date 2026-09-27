#!/usr/bin/env python3
"""Per-title exec-loop cost from one simpleperf capture, counted per sample.

    loopshare.py PERF_DATA [TID]
    loopshare.py PERF_DATA PERF_DATA ...

The vCPU thread is the tid with the most `cpu_exec_loop` self samples unless a
tid is given. Plain `report-sample` records (no --show-callchain: that drops
the JIT samples whose unwind fails, aufire412b's NOTES). Prints the thread's
samples split into:

  jit        file `unknown` (guest code, TCG prologue/epilogue)
  loop       cpu_exec_loop self (everything inlined into it: the interrupt
             check and its barrier, tb_lookup from the loop, tier1, [tlb68])
  loop.top   the three cpu_exec_loop addresses with the most samples, as a
             share of the thread: on arm64 the `stlrh; dmb ish; ldar` of
             cpu_handle_interrupt lands its stall on one or two addresses
  tbexec     cpu_tb_exec self (the call into the TB and the return decode)
  helper     helper_lookup_tb_ptr self (indirect branches, the hit path)
  lookup     other TB-lookup symbols (qht, tb_htable_lookup, tb_lookup_cmp,
             x86_get_tb_cpu_state, curr_cflags), whichever caller
  gen        tb_gen_code, translator and TCG backend self (translation)
  other      the rest
"""
import collections
import glob
import os
import re
import subprocess
import sys

SP = sorted(glob.glob(os.path.expanduser(
    "~/Android/Sdk/ndk/*/simpleperf/bin/linux/x86_64/simpleperf")))[-1]
LOOKUP = re.compile(r"^(tb_lookup|qht_lookup|tb_lookup_cmp|tb_htable_lookup|"
                    r"x86_get_tb_cpu_state|curr_cflags|get_page_addr_code|"
                    r"tb_hash_func|qemu_xxhash)")
GEN = re.compile(r"^(tb_gen_code|setjmp_gen_code|gen_intermediate_code|"
                 r"translator_|i386_tr_|disas_insn|tcg_gen_code|tcg_optimize|"
                 r"tcg_out|tcg_reg_alloc|liveness_pass|tcg_la_)")


def records(data):
    p = subprocess.Popen([SP, "report-sample", "-i", data], stdout=subprocess.PIPE,
                         stderr=subprocess.DEVNULL, text=True)
    tid = dso = va = None
    for line in p.stdout:
        s = line.strip()
        if s.startswith("thread_id:"):
            tid = s.split(":", 1)[1].strip()
        elif s.startswith("vaddr_in_file:"):
            va = s.split(":", 1)[1].strip()
        elif s.startswith("file:"):
            dso = s.split(":", 1)[1].strip()
        elif s.startswith("symbol:") and tid is not None:
            yield tid, dso, s.split(":", 1)[1].strip(), va
            tid = None


def classify(dso, sym):
    if dso == "unknown":
        return "jit"
    if sym == "cpu_exec_loop":
        return "loop"
    if sym == "cpu_tb_exec":
        return "tbexec"
    if sym == "helper_lookup_tb_ptr":
        return "helper"
    if LOOKUP.match(sym):
        return "lookup"
    if GEN.match(sym):
        return "gen"
    return "other"


def main():
    args = sys.argv[1:]
    if args and args[-1].isdigit():
        report(args[0], args[-1])
    else:
        for data in args:
            report(data, None)


def report(data, want):
    per = collections.defaultdict(collections.Counter)
    loopva = collections.defaultdict(collections.Counter)
    others = collections.defaultdict(collections.Counter)
    for tid, dso, sym, va in records(data):
        c = classify(dso, sym)
        per[tid][c] += 1
        if c == "loop":
            loopva[tid][va] += 1
        elif c == "other":
            others[tid][sym] += 1
    tid = want or max(per, key=lambda t: per[t]["loop"])
    cnt = per[tid]
    n = sum(cnt.values())
    pct = lambda v: 100.0 * v / max(1, n)
    out = ["%s tid %s: %d samples" % (os.path.basename(data), tid, n)]
    for k in ("jit", "loop", "tbexec", "helper", "lookup", "gen", "other"):
        out.append("  %-7s %6d %5.1f%%" % (k, cnt[k], pct(cnt[k])))
    top = loopva[tid].most_common(3)
    out.append("  loop.top " + " ".join("%s:%.1f%%" % (a, pct(v)) for a, v in top))
    for s, v in others[tid].most_common(12):
        out.append("    other %-40s %5d %5.2f%%" % (s[:40], v, pct(v)))
    # The helpers behind each gen_eob() plain exit: a cause that returns
    # millions of times a second shows its helper's own samples here.
    for s in ("helper_fldcw__hard", "helper_fldenv__hard",
              "helper_fninit__hard", "update_fp_status", "cpu_set_fpuc",
              "helper_write_eflags", "helper_iret_protected",
              "helper_load_seg", "helper_rdtsc", "helper_cpuid"):
        if s not in dict(others[tid].most_common(12)):
            out.append("    other %-40s %5d %5.2f%%" % (s, others[tid][s],
                                                     pct(others[tid][s])))
    print("\n".join(out))


if __name__ == "__main__":
    main()
