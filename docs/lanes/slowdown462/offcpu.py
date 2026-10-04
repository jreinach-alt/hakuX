#!/usr/bin/env python3
"""Where a thread BLOCKS, from a `simpleperf record --trace-offcpu` capture.

    offcpu.py <perf.data> <tid> [--top N] [--depth D]

simpleperf's own `report` weights an off-CPU sample by the time to the
thread's NEXT sample, which folds the on-CPU run after the wake-up into the
block. On a thread that switches out 20,000 times in 13 s for microseconds
each (AUF's vCPU), that reads it as 57% blocked while its cpu-clock samples
cover 92% of the span. This reader instead takes each sched_switch sample
(the thread switching out, with its call chain) and charges it the interval
to that thread's next `context_switch switch_on: true` record: the time it
was actually off the CPU.

Prints: the span, on-CPU ms (cpu-clock samples x 1 ms at -f 1000), off-CPU ms
(sum of intervals), and the off-CPU ms grouped by the first D non-kernel,
non-libc frames of the switch-out chain (the emulator frames that blocked).
"""
import argparse
import bisect
import collections
import glob
import os
import subprocess

NDK = sorted(glob.glob(os.path.expanduser("~/Android/Sdk/ndk/*")))[-1]
SP = NDK + "/simpleperf/bin/linux/x86_64/simpleperf"
SKIP = ("[kernel", "syscall", "__futex", "futex", "pthread_cond", "__pthread", "pthread_mutex",
        "__epoll", "epoll", "__ioctl", "ioctl", "__kernel", "@plt", "__aarch64")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("data")
    ap.add_argument("tid")
    ap.add_argument("--top", type=int, default=20)
    ap.add_argument("--depth", type=int, default=3)
    a = ap.parse_args()
    p = subprocess.Popen([SP, "report-sample", "--show-callchain", "-i", a.data],
                         stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
    ons = []          # switch_on times for the tid
    cs = []           # (time, on?) every context_switch record for the tid
    outs = []         # (time, chain) sched_switch samples for the tid
    oncpu = 0
    tmin = tmax = None
    kind = None
    rec = {}
    chain = []

    def flush():
        nonlocal oncpu, tmin, tmax
        if not rec:
            return
        t = rec.get("time")
        if t is not None:
            tmin = t if tmin is None else min(tmin, t)
            tmax = t if tmax is None else max(tmax, t)
        if rec.get("tid") != a.tid:
            return
        if kind == "cs":
            cs.append((t, bool(rec.get("on"))))
            if rec.get("on"):
                ons.append(t)
        elif kind == "sample" and rec.get("ev") == "sched:sched_switch":
            outs.append((t, list(chain)))
        elif kind == "sample" and rec.get("ev") == "cpu-clock":
            oncpu += 1

    for line in p.stdout:
        s = line.strip()
        if s in ("sample:", "context_switch:"):
            flush()
            kind = "sample" if s == "sample:" else "cs"
            rec, chain = {}, []
        elif s.startswith("switch_on:"):
            rec["on"] = s.endswith("true")
        elif s.startswith("time:"):
            rec["time"] = int(s.split(":", 1)[1])
        elif s.startswith("thread_id:"):
            rec["tid"] = s.split(":", 1)[1].strip()
        elif s.startswith("event_type:") and kind == "sample" and "ev" not in rec:
            rec["ev"] = s.split(":", 1)[1].strip()
        elif s.startswith("symbol:") and kind == "sample":
            chain.append(s.split(":", 1)[1].strip())
    flush()
    ons.sort()
    off = collections.Counter()
    total = 0.0
    unmatched = 0
    for t, ch in outs:
        i = bisect.bisect_right(ons, t)
        if i >= len(ons):
            unmatched += 1
            continue
        dt = (ons[i] - t) / 1e6
        total += dt
        emu = [f for f in ch if not f.startswith(SKIP) and not f.startswith("*")]
        off[" <- ".join(emu[:a.depth]) or "(no emulator frame)"] += dt
    span = (tmax - tmin) / 1e6 if tmin is not None else 0
    # from the switch records alone: time between switch_on and the next switch-out, and back
    cs.sort()
    on_cs = off_cs = 0.0
    for (t0, on0), (t1, _) in zip(cs, cs[1:]):
        if on0:
            on_cs += (t1 - t0) / 1e6
        else:
            off_cs += (t1 - t0) / 1e6
    if cs:
        print("switch records: %d, first +%.0f ms, last +%.0f ms; on-CPU %.0f ms, off-CPU %.0f ms between them" % (
            len(cs), (cs[0][0] - tmin) / 1e6, (cs[-1][0] - tmin) / 1e6, on_cs, off_cs))
    # Every off interval from the switch records, charged to the sched_switch
    # sample taken at its switch-out (within 0.2 ms) or to "(unsampled)": the
    # sampler drops switch-out samples, and the unsampled share is printed so
    # the attributed rows are read against it rather than against the span.
    stimes = [t for t, _ in outs]
    full = collections.Counter()
    for (t0, on0), (t1, _) in zip(cs, cs[1:]):
        if on0:
            continue
        dt = (t1 - t0) / 1e6
        i = bisect.bisect_right(stimes, t0) - 1
        if i >= 0 and t0 - stimes[i] <= 200000:
            emu = [f for f in outs[i][1] if not f.startswith(SKIP) and not f.startswith("*")]
            full[" <- ".join(emu[:a.depth]) or "(no emulator frame)"] += dt
        else:
            full["(unsampled switch-out)"] += dt
    if full:
        print("every off-CPU interval, charged to its switch-out sample (%.0f ms):" % sum(full.values()))
        for k, v in full.most_common(a.top):
            print("  %8.0f ms %5.1f%% of off  %s" % (v, 100.0 * v / max(off_cs, 1), k))
        print("by sampled switch-outs only (the older view):")
    print("%s tid %s: span %.0f ms; on-CPU %d ms (cpu-clock samples); off-CPU %.0f ms in %d switch-outs "
          "(%d with no later switch-in, not counted)" % (a.data, a.tid, span, oncpu, total, len(outs), unmatched))
    for k, v in off.most_common(a.top):
        print("  %8.0f ms %5.1f%% of span  %s" % (v, 100.0 * v / span if span else 0, k))


if __name__ == "__main__":
    main()
