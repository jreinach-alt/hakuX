#!/usr/bin/env python3
"""How concentrated one thread's guest-code (JIT) samples are.

    jithot.py PERF_DATA TID [BUCKET_BYTES]

Buckets the thread's `unknown`-DSO samples by host code address (default
256-byte buckets, about one small TB) and prints how many buckets hold
50 / 80 / 90% of them, and the top ten. A guest spin or poll loop is one or
two buckets; ordinary game code is hundreds.
"""
import collections
import glob
import os
import subprocess
import sys

SP = sorted(glob.glob(os.path.expanduser(
    "~/Android/Sdk/ndk/*/simpleperf/bin/linux/x86_64/simpleperf")))[-1]


def main():
    data, want = sys.argv[1], sys.argv[2]
    bucket = int(sys.argv[3]) if len(sys.argv) > 3 else 256
    p = subprocess.Popen([SP, "report-sample", "-i", data], stdout=subprocess.PIPE,
                         stderr=subprocess.DEVNULL, text=True)
    cnt = collections.Counter()
    tid = va = None
    for line in p.stdout:
        s = line.strip()
        if s.startswith("thread_id:"):
            tid = s.split(":", 1)[1].strip()
        elif s.startswith("vaddr_in_file:"):
            va = int(s.split(":", 1)[1].strip(), 16)
        elif s.startswith("file:") and tid == want:
            if s.split(":", 1)[1].strip() == "unknown":
                cnt[va // bucket] += 1
            tid = None
    n = sum(cnt.values())
    acc = 0
    marks = {}
    for i, (_, v) in enumerate(cnt.most_common(), 1):
        acc += v
        for q in (0.5, 0.8, 0.9):
            if q not in marks and acc >= q * n:
                marks[q] = i
    print("%s tid %s: %d JIT samples in %d buckets of %d B; 50%% in %s, "
          "80%% in %s, 90%% in %s" % (os.path.basename(data), want, n, len(cnt),
                                      bucket, marks.get(0.5), marks.get(0.8),
                                      marks.get(0.9)))
    lo = min(cnt)
    print("  lowest bucket %x holds %.1f%% (the TCG prologue/epilogue sits at "
          "the start of the code buffer)" % (lo * bucket, 100.0 * cnt[lo] / n))
    print("  top: " + " ".join("%x:%.1f%%" % (b * bucket, 100.0 * v / n)
                               for b, v in cnt.most_common(10)))


if __name__ == "__main__":
    main()
