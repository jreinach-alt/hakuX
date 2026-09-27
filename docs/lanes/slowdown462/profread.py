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
    w = 0
    for line in p.stdout:
        s = line.strip()
        if s == "sample:":
            if insample and tid:
                yield tid, name, frames, w
            insample, tid, name, frames, w = True, None, None, [], 0
        elif s.startswith("event_count:") and not frames:
            w = int(s.split(":", 1)[1])
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
        yield tid, name, frames, w


# Every count is in ms of thread time: a sample weighs its event_count (ns for
# cpu-clock; 1 ms per sample at -f 1000). Under --trace-offcpu the off-CPU
# samples carry the time the thread spent switched out, so a thread's total is
# its wall time, and the symbol a blocked sample lands on is where it blocked.
def UNIT(w):
    return w / 1e6


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("data")
    ap.add_argument("--top", type=int, default=15)
    ap.add_argument("--under", action="append", default=[])
    ap.add_argument("--tid", default=None)
    ap.add_argument("--callers", action="append", default=[],
                    help="for samples whose own symbol is SYM, the top caller chains (3 frames up)")
    a = ap.parse_args()
    tot = collections.Counter()
    names = {}
    selfc = collections.defaultdict(collections.Counter)
    for tid, name, fr, w in samples(a.data, False):
        tot[tid] += UNIT(w)
        names[tid] = name
        selfc[tid][fr[0] if fr else "?"] += UNIT(w)
    n = sum(tot.values())
    print("%s: %.0f thread-ms, %d threads" % (a.data, n, len(tot)))
    for tid, c in tot.most_common(8 if not a.tid else None):
        if a.tid and tid != a.tid:
            continue
        print("\n== tid %s %s: %.0f ms (%.1f%% of all)" % (tid, names[tid], c, 100.0 * c / n))
        for sym, k in selfc[tid].most_common(a.top):
            print("  %7.0f %5.1f%%  %s" % (k, 100.0 * k / c, sym))
    if a.callers:
        chains = collections.defaultdict(collections.Counter)
        seen = collections.Counter()
        for tid, name, fr, w in samples(a.data, True):
            if a.tid and tid != a.tid:
                continue
            if fr and fr[0] in a.callers:
                seen[fr[0]] += UNIT(w)
                chains[fr[0]][" <- ".join(fr[1:4]) or "(no chain)"] += UNIT(w)
        for sym in a.callers:
            print("\n-- callers of %s (%.0f ms kept by the callchain pass%s)" % (
                sym, seen[sym], ", tid " + a.tid if a.tid else ""))
            for ch, k in chains[sym].most_common(a.top):
                print("  %6.0f %5.1f%%  %s" % (k, 100.0 * k / max(seen[sym], 1), ch))
    if not a.under:
        return
    kept = collections.Counter()
    inc = collections.defaultdict(collections.Counter)
    below = collections.defaultdict(collections.Counter)
    for tid, name, fr, w in samples(a.data, True):
        kept[tid] += UNIT(w)
        seen = False
        for u in a.under:
            if u in fr:
                inc[tid][u] += UNIT(w)
                if not seen:
                    i = fr.index(u)
                    below[tid][fr[i - 1] if i > 0 else "(self)"] += UNIT(w)
                    seen = True
    print("\n-- inclusive (callchain pass; share of that thread's kept samples)")
    for tid, c in tot.most_common(8 if not a.tid else None):
        if a.tid and tid != a.tid:
            continue
        if not inc[tid]:
            continue
        print("tid %s %s: kept %.0f of %.0f ms" % (tid, names[tid], kept[tid], c))
        for u in a.under:
            print("  %7.0f %5.1f%%  under %s" % (inc[tid][u], 100.0 * inc[tid][u] / max(kept[tid], 1), u))
        print("  one frame below the first --under hit:")
        for sym, k in below[tid].most_common(a.top):
            print("    %7.0f %5.1f%%  %s" % (k, 100.0 * k / max(kept[tid], 1), sym))


if __name__ == "__main__":
    main()
