#!/usr/bin/env python3
"""Off-CPU time of one thread, split into BLOCKED and PREEMPTED (lane.gta482, #482).

    offsplit.py <perf.data from --trace-offcpu> <tid> [--top N] [--depth D]
    offsplit.py --selftest

slowdown462's offcpu.py charges each off-CPU interval (switch-out to the next
switch-in, from the context_switch records) to the switch-out sample's
emulator frames. It does not ask whether the thread WANTED to leave the CPU.
This reader does, from the sample's first user frame:

  blocked     the first user frame is a libc syscall wrapper (futex, ppoll,
              ioctl, nanosleep, read, ...): the thread went to sleep in the
              kernel, and the emulator frames under it say on what
  preempted   the first user frame is anything else (JIT code, a helper, the
              exec loop): the thread was running and the scheduler took the
              CPU away; it stayed runnable and waited for a core

A thread confined to too few cores shows as preempted. `hoststate.py` reads
the same split from /proc schedstat (run-queue wait), which is the check on
this classification.
"""
import argparse
import bisect
import collections
import glob
import os
import subprocess
import sys

NDK = sorted(glob.glob(os.path.expanduser("~/Android/Sdk/ndk/*")))[-1]
SP = NDK + "/simpleperf/bin/linux/x86_64/simpleperf"
SYSCALLS = ("syscall", "__futex", "futex", "__ppoll", "ppoll", "__epoll_pwait", "epoll", "__ioctl",
            "ioctl", "nanosleep", "__nanosleep", "clock_nanosleep", "__clock_nanosleep", "read",
            "write", "pread", "pwrite", "__pread", "__pwrite", "recv", "send", "__rt_sig",
            "sched_yield", "usleep", "poll", "__poll", "fsync", "fdatasync", "madvise", "mprotect",
            "munmap", "mmap", "__openat", "close", "__sched", "wait4", "preadv", "pwritev", "msync",
            "eventfd", "sigsuspend", "__clone", "tgkill", "getrusage", "clock_gettime", "membarrier")
LIBC_SKIP = ("pthread_", "__pthread", "NonPI::", "PI::", "__futex", "futex", "syscall", "@plt",
             "__aarch64", "__timed", "sem_", "__bionic")


def read(stream, tid):
    """-> (cs [(t, on)], outs [(t, [(file, symbol)])], n cpu-clock samples, tmin, tmax)"""
    cs, outs = [], []
    oncpu = 0
    tmin = tmax = None
    kind = None
    rec, chain = {}, []
    cur_file = None

    def flush():
        nonlocal oncpu, tmin, tmax
        if not rec:
            return
        t = rec.get("time")
        if t is not None:
            tmin = t if tmin is None else min(tmin, t)
            tmax = t if tmax is None else max(tmax, t)
        if rec.get("tid") != tid:
            return
        if kind == "cs":
            cs.append((t, bool(rec.get("on"))))
        elif kind == "sample" and rec.get("ev") == "sched:sched_switch":
            outs.append((t, list(chain)))
        elif kind == "sample" and rec.get("ev") == "cpu-clock":
            oncpu += 1

    for line in stream:
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
        elif s.startswith("file:") and kind == "sample":
            cur_file = s.split(":", 1)[1].strip()
        elif s.startswith("symbol:") and kind == "sample":
            chain.append((cur_file or "", s.split(":", 1)[1].strip()))
    flush()
    cs.sort()
    outs.sort(key=lambda x: x[0])
    return cs, outs, oncpu, tmin, tmax


def classify(chain, depth):
    """-> ('blocked'|'preempted'|'kernel-only', label)"""
    user = [(f, s) for f, s in chain if "kernel" not in f and not s.startswith("[kernel")]
    if not user:
        return "kernel-only", "(no user frame)"
    f0, s0 = user[0]
    base = s0.split("(")[0]
    if f0.endswith("libc.so") and base.startswith(SYSCALLS):
        emu = [s for f, s in user if not (f.endswith("libc.so") or s.split("(")[0].startswith(LIBC_SKIP))]
        return "blocked", (base + " <- " + " <- ".join(x.split("(")[0] for x in emu[:depth])) if emu else base
    where = os.path.basename(f0) if f0 else "?"
    if s0.startswith(("*", "unknown")) or "[+" in s0 or not f0.endswith(".so"):
        return "preempted", f"in {where or 'anon'} (JIT or unsymbolized)"
    return "preempted", f"in {base} ({where})"


def split(cs, outs, depth):
    stimes = [t for t, _ in outs]
    tot = collections.Counter()
    by = {"blocked": collections.Counter(), "preempted": collections.Counter(),
          "kernel-only": collections.Counter(), "unsampled": collections.Counter()}
    n = collections.Counter()
    on = 0.0
    for (t0, on0), (t1, _) in zip(cs, cs[1:]):
        dt = (t1 - t0) / 1e6
        if on0:
            on += dt
            continue
        i = bisect.bisect_right(stimes, t0 + 200000) - 1
        if i >= 0 and abs(t0 - stimes[i]) <= 200000:
            k, label = classify(outs[i][1], depth)
        else:
            k, label = "unsampled", "(switch-out with no sample)"
        tot[k] += dt
        by[k][label] += dt
        n[k] += 1
    return on, tot, by, n


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--selftest":
        return selftest()
    ap = argparse.ArgumentParser()
    ap.add_argument("data")
    ap.add_argument("tid")
    ap.add_argument("--top", type=int, default=12)
    ap.add_argument("--depth", type=int, default=3)
    ap.add_argument("--flips", type=int, default=0, help="flips in the span, for ms/frame")
    a = ap.parse_args()
    p = subprocess.Popen([SP, "report-sample", "--show-callchain", "-i", a.data],
                         stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, errors="replace")
    cs, outs, oncpu, tmin, tmax = read(p.stdout, a.tid)
    p.wait()
    if not cs:
        sys.exit(f"no context_switch record for tid {a.tid}: not a --trace-offcpu record, or a wrong tid")
    on, tot, by, n = split(cs, outs, a.depth)
    span = (cs[-1][0] - cs[0][0]) / 1e6
    off = sum(tot.values())
    per = (lambda ms: f" = {ms / a.flips:6.1f} ms/frame") if a.flips else (lambda ms: "")
    print(f"{a.data} tid {a.tid}: {len(cs)} switch records over {span:.0f} ms; "
          f"{oncpu} cpu-clock samples; {len(outs)} switch-out samples")
    print(f"  on-CPU     {on:9.0f} ms {100 * on / span:5.1f}%{per(on)}")
    for k in ("blocked", "preempted", "kernel-only", "unsampled"):
        print(f"  {k:<10} {tot[k]:9.0f} ms {100 * tot[k] / span:5.1f}%{per(tot[k])}   ({n[k]} intervals)")
    print(f"  off-CPU    {off:9.0f} ms {100 * off / span:5.1f}%")
    for k in ("blocked", "preempted", "kernel-only"):
        if not by[k]:
            continue
        print(f"{k}, by where:")
        for label, v in by[k].most_common(a.top):
            print(f"  {v:9.0f} ms {100 * v / span:5.1f}%{per(v)}  {label}")


FIXTURE = """\
context_switch:
  switch_on: true
  time: 1000000
  thread_id: 7
sample:
  event_type: sched:sched_switch
  time: 11000000
  thread_id: 7
  callchain:
    vaddr_in_file: 1
    file: [kernel.kallsyms]
    symbol: [kernel.kallsyms][+ffffffe5a1e3c094]
    vaddr_in_file: 2
    file: /apex/com.android.runtime/lib64/bionic/libc.so
    symbol: syscall
    vaddr_in_file: 3
    file: /apex/com.android.runtime/lib64/bionic/libc.so
    symbol: __futex_wait_ex(void volatile*, bool, int, bool, timespec const*)
    vaddr_in_file: 4
    file: /data/app/x/lib/arm64/libxemu.so
    symbol: qemu_mutex_lock_impl
    vaddr_in_file: 5
    file: /data/app/x/lib/arm64/libxemu.so
    symbol: pgraph_read
context_switch:
  switch_on: false
  time: 11000000
  thread_id: 7
context_switch:
  switch_on: true
  time: 16000000
  thread_id: 7
sample:
  event_type: sched:sched_switch
  time: 36000000
  thread_id: 7
  callchain:
    vaddr_in_file: 1
    file: [kernel.kallsyms]
    symbol: [kernel.kallsyms][+ffffffe5a1e3c094]
    vaddr_in_file: 2
    file: [anon:jit]
    symbol: [anon:jit][+1234]
    vaddr_in_file: 3
    file: /data/app/x/lib/arm64/libxemu.so
    symbol: cpu_exec_loop
context_switch:
  switch_on: false
  time: 36000000
  thread_id: 7
context_switch:
  switch_on: true
  time: 66000000
  thread_id: 7
context_switch:
  switch_on: false
  time: 70000000
  thread_id: 7
context_switch:
  switch_on: true
  time: 72000000
  thread_id: 7
sample:
  event_type: sched:sched_switch
  time: 11000000
  thread_id: 8
  callchain:
    vaddr_in_file: 2
    file: /data/app/x/lib/arm64/libxemu.so
    symbol: other_thread
"""


def selftest():
    cs, outs, oncpu, tmin, tmax = read(FIXTURE.splitlines(), "7")
    on, tot, by, n = split(cs, outs, 3)
    want = {"blocked": 5.0, "preempted": 30.0, "unsampled": 2.0}
    got = {k: round(v, 3) for k, v in tot.items()}
    ok = (got == want and round(on, 3) == 34.0 and len(outs) == 2
          and list(by["blocked"]) == ["syscall <- qemu_mutex_lock_impl <- pgraph_read"]
          and list(by["preempted"])[0].startswith("in [anon:jit]"))
    print("selftest", "ok" if ok else f"FAIL: on={on} tot={got} by={dict(by)}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
