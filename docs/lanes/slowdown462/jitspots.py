#!/usr/bin/env python3
"""How concentrated a thread's guest-JIT samples are, by host address.

    jitspots.py <perf.data> <tid> [bucket bytes, default 256]

A guest spinning in one tight loop puts most of its JIT samples in a few
host-code buckets; a guest running a broad workload spreads them. Prints how
many buckets hold 50/80/90% of the JIT samples and the top 15 buckets, with
the vCPU's JIT sample count as the denominator. Host addresses only: the
guest PC behind a bucket needs a guest-side profile.
"""
import collections
import glob
import os
import subprocess
import sys

NDK = sorted(glob.glob(os.path.expanduser("~/Android/Sdk/ndk/*")))[-1]
SP = NDK + "/simpleperf/bin/linux/x86_64/simpleperf"
data, tid = sys.argv[1], sys.argv[2]
bucket = int(sys.argv[3]) if len(sys.argv) > 3 else 256

p = subprocess.Popen([SP, "report-sample", "-i", data], stdout=subprocess.PIPE,
                     stderr=subprocess.DEVNULL, text=True)
cnt = collections.Counter()
cur_tid = None
want = False
for line in p.stdout:
    s = line.strip()
    if s.startswith("thread_id:"):
        cur_tid = s.split()[1]
    elif s.startswith("vaddr_in_file:"):
        vaddr = s.split()[1]
    elif s.startswith("file:"):
        f = s.split(None, 1)[1] if len(s.split()) > 1 else ""
        want = cur_tid == tid and ("unknown" in f or f.startswith("[anon") or f.startswith("//anon") or "code_gen" in f or "jit" in f.lower())
    elif s.startswith("symbol:") and want:
        cnt[int(vaddr, 16) // bucket] += 1
        want = False
p.wait()
tot = sum(cnt.values())
if not tot:
    sys.exit(f"no JIT samples for tid {tid}")
ranked = cnt.most_common()
acc = 0
marks = {}
for i, (_, n) in enumerate(ranked, 1):
    acc += n
    for q in (0.5, 0.8, 0.9):
        if q not in marks and acc >= q * tot:
            marks[q] = i
print(f"tid {tid}: {tot} JIT samples in {len(ranked)} buckets of {bucket} B; "
      + ", ".join(f"{int(q * 100)}% in {marks[q]}" for q in sorted(marks)))
for b, n in ranked[:15]:
    print(f"  0x{b * bucket:x}  {n:6d}  {100 * n / tot:5.1f}%")
