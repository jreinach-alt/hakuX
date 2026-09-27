#!/usr/bin/env python3
"""Leg F1: per-arm vCPU-thread samples in emutls, outline atomics, PLT stubs
and pthread TLS, counted per sample record from report-sample.

    f1.py a.data b.data

The vCPU thread is the tid with the most chains through mttcg_cpu_thread_fn.
Only the leaf frame is classified, so each sample counts once.
"""
import collections
import glob
import os
import re
import subprocess
import sys

SP = sorted(glob.glob(os.path.expanduser(
    "~/Android/Sdk/ndk/*/simpleperf/bin/linux/x86_64/simpleperf")))[-1]

KEYS = [
    ("emutls", re.compile(r"__emutls_get_address|emutls")),
    ("outline atomics", re.compile(r"^__aarch64_(cas|swp|ld)")),
    ("pthread TLS", re.compile(r"pthread_getspecific|pthread_setspecific")),
    ("PLT stub", re.compile(r"@plt")),
]


def samples(path):
    """Yield (tid, [(dso, sym), ...]) per sample; frame 0 is the leaf."""
    p = subprocess.Popen([SP, "report-sample", "--show-callchain", "-i", path],
                         stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                         text=True)
    tid = dso = None
    chain = []
    for line in p.stdout:
        s = line.strip()
        if s.startswith("sample:"):
            if tid is not None:
                yield tid, chain
            tid, chain = None, []
        elif s.startswith("thread_id:"):
            tid = s.split(":", 1)[1].strip()
        elif s.startswith("file:"):
            dso = s.split(":", 1)[1].strip()
        elif s.startswith("symbol:"):
            chain.append((dso, s.split(":", 1)[1].strip()))
    if tid is not None:
        yield tid, chain


def main():
    for path in sys.argv[1:]:
        per_tid = collections.defaultdict(list)
        vcpu_votes = collections.Counter()
        for tid, chain in samples(path):
            per_tid[tid].append(chain)
            if any("mttcg_cpu_thread_fn" in s for _, s in chain):
                vcpu_votes[tid] += 1
        tid = vcpu_votes.most_common(1)[0][0]
        rows = per_tid[tid]
        n = len(rows)
        cnt = collections.Counter()
        by_dso = collections.defaultdict(collections.Counter)
        top = collections.Counter()
        for chain in rows:
            dso, sym = chain[0]
            for name, rx in KEYS:
                if rx.search(sym):
                    cnt[name] += 1
                    top[sym] += 1
                    by_dso[name][dso.split("/")[-1]] += 1
                    break
        print("%s  vCPU tid %s  samples %d  (chains via mttcg: %d)" % (
            path, tid, n, vcpu_votes[tid]))
        for name, _ in KEYS:
            print("  %-16s %6d  %5.2f%%" % (name, cnt[name], 100.0 * cnt[name] / n))
        s = sum(cnt.values())
        print("  %-16s %6d  %5.2f%%" % ("sum", s, 100.0 * s / n))
        for name, _ in KEYS:
            print("  %-16s by dso: %s" % (name, dict(by_dso[name])))
        print("  top:", top.most_common(8))


if __name__ == "__main__":
    main()
