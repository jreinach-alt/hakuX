#!/usr/bin/env python3
"""Per-thread split of one simpleperf capture, from raw report-sample records.

    profread.py <perf.data> [--top N] [--under SYM ...] [--tid TID]

Two passes, on purpose (aufire412b's rule: never take --show-callchain counts
as a denominator, it drops the samples whose DWARF unwind fails, mostly JIT):

  1. plain report-sample: every sample, by thread: total, and the top N self
     symbols (guest JIT code is file `unknown`). This is the denominator.
  2. report-sample --show-callchain: for each --under SYM, the samples of each
     thread whose chain contains SYM (inclusive), and under the first such SYM
     the top callee frames one level down. Printed with the number of samples
     the callchain pass kept for that thread, so the inclusive share is read
     against the pass it came from.

Threads are keyed by tid and named by thread_name; a thread with a JIT share
and `cpu_exec_loop` is the vCPU.
"""
import argparse
import collections
import glob
import os
import subprocess

NDK = sorted(glob.glob(os.path.expanduser("~/Android/Sdk/ndk/*")))[-1]
SP = NDK + "/simpleperf/bin/linux/x86_64/simpleperf"


def samples(data, chain):
    """Yield (tid, name, [frames]) with frames[0] the sampled symbol, then callers outward."""
    args = [SP, "report-sample", "-i", data] + (["--show-callchain"] if chain else [])
    p = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
    tid = name = None
    frames = []
    dso = None
    insample = False
    for line in p.stdout:
        s = line.strip()
        if s == "sample:":
            if insample and tid:
                yield tid, name, frames
            insample, tid, name, frames = True, None, None, []
        elif s.startswith("thread_id:"):
            tid = s.split(":", 1)[1].strip()
        elif s.startswith("thread_name:"):
            name = s.split(":", 1)[1].strip()
        elif s.startswith("file:"):
            dso = s.split(":", 1)[1].strip()
        elif s.startswith("symbol:"):
            sym = s.split(":", 1)[1].strip()
            if dso == "unknown":
                sym = "[guest JIT]"
            elif dso and "kallsyms" in dso:
                sym = "[kernel]"
            frames.append(sym)
    if insample and tid:
        yield tid, name, frames


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("data")
    ap.add_argument("--top", type=int, default=15)
    ap.add_argument("--under", action="append", default=[])
    ap.add_argument("--tid", default=None)
    a = ap.parse_args()
    tot = collections.Counter()
    names = {}
    selfc = collections.defaultdict(collections.Counter)
    for tid, name, fr in samples(a.data, False):
        tot[tid] += 1
        names[tid] = name
        selfc[tid][fr[0] if fr else "?"] += 1
    n = sum(tot.values())
    print("%s: %d samples, %d threads" % (a.data, n, len(tot)))
    for tid, c in tot.most_common(8 if not a.tid else None):
        if a.tid and tid != a.tid:
            continue
        print("\n== tid %s %s: %d samples (%.1f%% of all)" % (tid, names[tid], c, 100.0 * c / n))
        for sym, k in selfc[tid].most_common(a.top):
            print("  %7d %5.1f%%  %s" % (k, 100.0 * k / c, sym))
    if not a.under:
        return
    kept = collections.Counter()
    inc = collections.defaultdict(collections.Counter)
    below = collections.defaultdict(collections.Counter)
    for tid, name, fr in samples(a.data, True):
        kept[tid] += 1
        seen = False
        for u in a.under:
            if u in fr:
                inc[tid][u] += 1
                if not seen:
                    i = fr.index(u)
                    below[tid][fr[i - 1] if i > 0 else "(self)"] += 1
                    seen = True
    print("\n-- inclusive (callchain pass; share of that thread's kept samples)")
    for tid, c in tot.most_common(8 if not a.tid else None):
        if a.tid and tid != a.tid:
            continue
        if not inc[tid]:
            continue
        print("tid %s %s: kept %d of %d" % (tid, names[tid], kept[tid], c))
        for u in a.under:
            print("  %7d %5.1f%%  under %s" % (inc[tid][u], 100.0 * inc[tid][u] / max(kept[tid], 1), u))
        print("  one frame below the first --under hit:")
        for sym, k in below[tid].most_common(a.top):
            print("    %7d %5.1f%%  %s" % (k, 100.0 * k / max(kept[tid], 1), sym))


if __name__ == "__main__":
    main()
