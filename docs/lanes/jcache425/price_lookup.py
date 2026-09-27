#!/usr/bin/env python3
"""Price #425's levers from one simpleperf capture, by counting samples.

    price_lookup.py PERF_DATA [THREAD_NAME]

Counts `report-sample` records of one thread (default `qemu_main`, the guest
thread) rather than reading `simpleperf report`'s rounded percentages. It then
splits them four ways:

  lookup     self samples in the TB lookup path (helper_lookup_tb_ptr,
             tb_lookup, qht_lookup*, tb_lookup_cmp, tb_htable*, the state
             getters), each attributed to its entry point: the indirect
             branch helper, the exec loop, or tb_gen_code's recycle probe;
  jcflush    self samples in tcg_flush_jmp_cache;
  flags      self samples in the lazy-flags helpers (helper_cc_compute_*,
             helper_read_eflags, helper_write_eflags, cc_compute_*,
             compute_all_*, compute_c_*);
  total      every sample of the thread.

The attribution walks the callchain from the leaf outwards and takes the
first frame that names an entry point. A chain that does not unwind that far
is counted as `unattributed`, not guessed.

What it cannot see: flag work the JIT emits inline (cc_op materialisation in
generated code) is in the `unknown` DSO and cannot be separated from other
guest code here.
"""
import collections
import glob
import os
import re
import subprocess
import sys

SP = sorted(glob.glob(os.path.expanduser(
    "~/Android/Sdk/ndk/*/simpleperf/bin/linux/x86_64/simpleperf")))[-1]
DATA = sys.argv[1]
TNAME = sys.argv[2] if len(sys.argv) > 2 else "qemu_main"
# Several threads can carry one name; pick the tid with the most samples
# under that name unless a numeric tid is given as argv[3].
TID = sys.argv[3] if len(sys.argv) > 3 else None

LOOKUP = re.compile(r"^(helper_lookup_tb_ptr|tb_lookup|qht_lookup|tb_lookup_cmp|"
                    r"tb_htable_lookup|tb_htable_lookup_common|"
                    r"x86_get_tb_cpu_state|curr_cflags|get_page_addr_code|"
                    r"tb_hash_func|qemu_xxhash)")
FLAGS = re.compile(r"^(helper_cc_compute|helper_read_eflags|helper_write_eflags|"
                   r"cc_compute|compute_all_|compute_c_)")
ENTRY = [
    ("indirect (helper_lookup_tb_ptr)", re.compile(r"^helper_lookup_tb_ptr")),
    ("recycle probe (tb_gen_code)", re.compile(r"^(inv_tb_htable_lookup|tb_gen_code)")),
    ("exec loop (cpu_exec_loop)", re.compile(r"^(cpu_exec_loop|cpu_exec_setjmp|cpu_exec)\b")),
]


def samples():
    p = subprocess.Popen([SP, "report-sample", "--show-callchain", "-i", DATA],
                         stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                         text=True)
    cur = None
    in_chain = False
    for line in p.stdout:
        s = line.strip()
        if s == "sample:":
            if cur:
                yield cur
            cur = {"tname": None, "tid": None, "sym": None, "dso": None, "chain": []}
            in_chain = False
        elif cur is None:
            continue
        elif s.startswith("thread_id:") and not in_chain:
            cur["tid"] = s.split(":", 1)[1].strip()
        elif s.startswith("thread_name:"):
            cur["tname"] = s.split(":", 1)[1].strip()
        elif s == "callchain:":
            in_chain = True
        elif s.startswith("symbol:"):
            sym = s.split(":", 1)[1].strip()
            if in_chain:
                cur["chain"].append(sym)
            elif cur["sym"] is None:
                cur["sym"] = sym
        elif s.startswith("file:") and not in_chain and cur["dso"] is None:
            cur["dso"] = s.split(":", 1)[1].strip()
    if cur:
        yield cur


def main():
    allsmp = [x for x in samples() if x["tname"] == TNAME]
    tids = collections.Counter(x["tid"] for x in allsmp)
    tid = TID or tids.most_common(1)[0][0]
    print("tids named %s: %s; using %s" % (TNAME, dict(tids), tid))
    tot = 0
    lookup = collections.Counter()
    lookup_by_sym = collections.Counter()
    flags = collections.Counter()
    jcf = 0
    for smp in allsmp:
        if smp["tid"] != tid:
            continue
        tot += 1
        sym = smp["sym"] or ""
        if sym.startswith("tcg_flush_jmp_cache"):
            jcf += 1
        elif FLAGS.match(sym):
            flags[sym] += 1
        elif LOOKUP.match(sym) or sym.startswith("qht_lookup"):
            # the helper itself is its own entry point
            frames = [sym] + smp["chain"]
            where = "unattributed"
            for f in frames:
                for name, rx in ENTRY:
                    if rx.match(f):
                        where = name
                        break
                if where != "unattributed":
                    break
            lookup[where] += 1
            lookup_by_sym[sym] += 1
    pct = lambda n: 100.0 * n / max(1, tot)
    print("%s thread %s: %d samples" % (DATA, TNAME, tot))
    print("  tcg_flush_jmp_cache  %6d  %5.2f%%" % (jcf, pct(jcf)))
    n = sum(lookup.values())
    print("  lookup path          %6d  %5.2f%%" % (n, pct(n)))
    for k, v in lookup.most_common():
        print("      via %-34s %6d  %5.2f%%" % (k, v, pct(v)))
    for k, v in lookup_by_sym.most_common(8):
        print("      sym %-34s %6d  %5.2f%%" % (k, v, pct(v)))
    n = sum(flags.values())
    print("  lazy-flags helpers   %6d  %5.2f%%" % (n, pct(n)))
    for k, v in flags.most_common(8):
        print("      sym %-34s %6d  %5.2f%%" % (k, v, pct(v)))


if __name__ == "__main__":
    main()
