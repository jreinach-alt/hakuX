#!/usr/bin/env python3
"""Group one thread's self-time profile by mechanism, and report that thread's
measured CPU placement, from a simpleperf perf.data.

    profile_categories.py [PERF_DATA] [TID]

Defaults: the 09-11 Crimson Skies capture (/home/justin/hakux-work/perf/
perf.data, profile_guest.sh, 20 s, cpu-clock 1 kHz, --call-graph fp) and its
vCPU thread (tid 20682, the one whose chains end in mttcg_cpu_thread_fn).
Categories are regexes over symbol names, first match wins, so the order
below is part of the definition. Every row that matches nothing is printed.
"""
import collections
import glob
import os
import re
import subprocess
import sys

SP = sorted(glob.glob(os.path.expanduser(
    "~/Android/Sdk/ndk/*/simpleperf/bin/linux/x86_64/simpleperf")))[-1]
DATA = sys.argv[1] if len(sys.argv) > 1 else "/home/justin/hakux-work/perf/perf.data"
TID = sys.argv[2] if len(sys.argv) > 2 else "20682"

CATS = [
    ("jit code (unknown DSO)", lambda d, s: d == "unknown"),
    ("code-write invalidation + dirty re-arm", lambda d, s: re.search(
        r"tlb_reset_dirty|tcg_flush_jmp_cache|tb_invalidate|do_tb_phys_invalidate|"
        r"notdirty|tb_remove|tb_page|test_and_clear_dirty|tb_phys|page_collection|"
        r"tb_jmp_unlink|tb_reset_jump|qht_remove|tlb_flush", s)),
    ("tb lookup + chaining", lambda d, s: re.search(
        r"lookup_tb_ptr|qht_lookup|tb_lookup|tb_tc_cmp|tb_code_hash|tb_htable|"
        r"get_tb_cpu_state|curr_cflags|tb_add_jump|q_tree_lookup|tcg_tb_lookup|"
        r"tb_cmp|tb_jmp_cache", s)),
    ("icache maintenance", lambda d, s: "flush_idcache" in s),
    ("softmmu slow path", lambda d, s: re.search(
        r"mmu_lookup|do_ld|do_st|probe_access|tlb_set_page|mmu_translate|"
        r"mem_access_callback|mem_check_access|get_page_addr_code|cpu_ld|cpu_st|"
        r"io_readx|io_writex|helper_ld|helper_st|tlb_fill|tlb_fill_align|"
        r"qemu_ram_block_from_host|address_space|memory_region|flatview|"
        r"mmu_watch|victim_tlb|ram_block", s)),
    ("translation (tb_gen_code and the tcg compiler)", lambda d, s: re.search(
        r"^tcg_|^tb_gen_code|translator_|disas_insn|^gen_|^tb_link|q_tree_insert|"
        r"^la_|liveness|reachable_code|^i386_tr|^decode_|^temp_|^tcg|^fold_|"
        r"^finish_|^init_ts|^copy_propagate|^reg_alloc|^tb_alloc|^tcg_op", s)
        and "helper" not in s),
    ("guest-op helpers (x87/SSE/flags/etc)", lambda d, s: s.startswith("helper_")),
    ("audio voice lock on the vCPU thread", lambda d, s: "voice" in s),
    ("host runtime: emutls, PLT, outline atomics, pthread TLS",
     lambda d, s: re.search(r"emutls|@plt|__aarch64_|pthread_getspecific|"
                            r"pthread_mutex|pthread_setspecific", s)),
    ("cpu_exec loop and misc exec", lambda d, s: re.search(
        r"cpu_exec|cpu_handle|cpu_loop|tcg_cpu_exec|mttcg|qemu_mutex|qemu_cond|"
        r"qemu_event|bql_|rcu_", s)),
    ("kernel", lambda d, s: "kernel" in d or "kallsyms" in s),
]


def main():
    # Count raw samples from report-sample. `report --sort symbol` rounds
    # every row to 0.01%, and the JIT's ~3,900 one-sample addresses each
    # round UP, which inflated the JIT share from 29% to 42% on this file.
    p = subprocess.Popen([SP, "report-sample", "-i", DATA],
                         stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                         text=True)
    per = collections.Counter()
    tid = dso = None
    for line in p.stdout:
        s = line.strip()
        if s.startswith("thread_id:"):
            tid = s.split(":", 1)[1].strip()
        elif s.startswith("file:"):
            dso = s.split(":", 1)[1].strip()
        elif s.startswith("symbol:") and tid == TID:
            sym = s.split(":", 1)[1].strip()
            if sym.startswith("unknown") or dso in ("unknown", "[unknown]"):
                dso = "unknown"
            per[(dso, sym)] += 1
            tid = None
    total = sum(per.values()) or 1
    rows = [(100.0 * n / total, d, s) for (d, s), n in per.items()]
    tot = collections.Counter()
    other = []
    for pct, dso, sym in rows:
        for name, f in CATS:
            if f(dso, sym):
                tot[name] += pct
                break
        else:
            tot["other"] += pct
            other.append((pct, dso.split("/")[-1], sym))
    print("self-time of tid %s by mechanism (%s):" % (TID, DATA))
    for name, _ in CATS + [("other", None)]:
        print("  %6.2f%%  %s" % (tot[name], name))
    print("  %6.2f%%  (sum)" % sum(tot.values()))
    for o in sorted(other, reverse=True)[:15]:
        print("      other %.2f%% %s %s" % o)

    # Placement: every sample record carries the CPU it was taken on.
    p = subprocess.Popen([SP, "dump", DATA], stdout=subprocess.PIPE,
                         stderr=subprocess.DEVNULL, text=True)
    cnt = collections.Counter()
    seq = []
    tid = t = None
    for line in p.stdout:
        s = line.strip()
        if s.startswith("pid ") and "tid" in s:
            tid = s.split("tid ")[1]
        elif s.startswith("time ") and tid:
            t = int(s.split()[1])
        elif s.startswith("cpu ") and tid:
            if tid == TID:
                c = int(s.split()[1].rstrip(","))
                cnt[c] += 1
                seq.append((t, c))
            tid = None
    seq.sort()
    n = sum(cnt.values()) or 1
    changes = sum(1 for a, b in zip(seq, seq[1:]) if a[1] != b[1])
    dur = (seq[-1][0] - seq[0][0]) / 1e9 if len(seq) > 1 else 1
    print("placement of tid %s over %d samples: %s" % (
        TID, n, " ".join("cpu%d=%.1f%%" % (c, 100.0 * v / n)
                         for c, v in sorted(cnt.items()))))
    print("core changes between consecutive samples: %d (%.1f/s) -- a LOWER "
          "bound on migrations at 1 kHz sampling" % (changes, changes / dur))


if __name__ == "__main__":
    main()
