#!/usr/bin/env python3
"""Count one thread's simpleperf samples by where they land, from raw
report-sample records (never `report`'s rounded percentages).

    vcpucount.py <perf.data> <tid> [<libxemu.so for addr2line>]

Prints the thread's total, guest JIT code (file `unknown`), cpu_exec_loop
self, cpu_tb_exec self, and the cpu_exec_loop self samples grouped by the
innermost inlined source line when a libxemu.so with debug info is given
(the APK's own copy has it).

The denominator is PLAIN report-sample. With --show-callchain, simpleperf
drops the samples whose DWARF unwind fails, and those are mostly JIT samples:
on AUF p2 it dropped 3,511 of 26,139, which reads the exec loop as 62.5%
instead of 54.1% and JIT as 16.5% instead of 26.2%.
"""
import collections
import glob
import os
import subprocess
import sys

NDK = sorted(glob.glob(os.path.expanduser("~/Android/Sdk/ndk/*")))[-1]
SP = NDK + "/simpleperf/bin/linux/x86_64/simpleperf"
A2L = NDK + "/toolchains/llvm/prebuilt/linux-x86_64/bin/llvm-addr2line"


def main():
    data, want = sys.argv[1], sys.argv[2]
    lib = sys.argv[3] if len(sys.argv) > 3 else None
    p = subprocess.Popen([SP, "report-sample", "-i", data], stdout=subprocess.PIPE,
                         stderr=subprocess.DEVNULL, text=True)
    n = 0
    cls = collections.Counter()
    loop_va = collections.Counter()
    tid = dso = va = None
    for line in p.stdout:
        s = line.strip()
        if s.startswith("thread_id:"):
            tid = s.split(":", 1)[1].strip()
        elif s.startswith("vaddr_in_file:"):
            va = s.split(":", 1)[1].strip()
        elif s.startswith("file:"):
            dso = s.split(":", 1)[1].strip()
        elif s.startswith("symbol:") and tid == want:
            sym = s.split(":", 1)[1].strip()
            n += 1
            if dso == "unknown":
                cls["guest JIT code"] += 1
            elif sym == "cpu_exec_loop":
                cls["cpu_exec_loop self"] += 1
                loop_va[va] += 1
            elif sym == "cpu_tb_exec":
                cls["cpu_tb_exec self"] += 1
            else:
                cls["other"] += 1
            tid = None
    print("tid %s: %d samples (%s)" % (want, n, data))
    for k, v in cls.most_common():
        print("  %7d %5.1f%%  %s" % (v, 100.0 * v / n, k))
    if not lib:
        return
    byline = collections.Counter()
    for a, c in loop_va.items():
        o = subprocess.run([A2L, "-e", lib, "-f", "-i", a], capture_output=True,
                           text=True).stdout.splitlines()
        byline["%s @ %s" % (o[0], o[1].split("/")[-1]) if len(o) > 1 else a] += c
    print("  cpu_exec_loop self by innermost inlined line:")
    for k, v in byline.most_common(12):
        print("  %7d %5.1f%%  %s" % (v, 100.0 * v / n, k))


if __name__ == "__main__":
    main()
