#!/usr/bin/env python3
"""Which host CPUs a recording's threads ran on (lane.gta482, #482).

    cpuof.py <perf.data> [tid ...]

Reads `simpleperf dump` (the sample records carry `cpu N`) and prints, per
thread and event, the share of its samples on each CPU. The question it
answers: did the slow regime's threads run on other cores than the fast
regime's (a cpuset, or a migration to the little cores)? That would raise
every thread's unit cost at once with no change in the guest's work.

What it cannot see: a core's frequency. A thread on the same core at a lower
clock reads the same here; that needs scaling_cur_freq read during the window
(capture_gta.sh's `hoststate`).

With --trace-offcpu the record has sched_switch samples too. They are listed
apart: a switch-out sample is on the CPU the thread left.
"""
import collections
import glob
import os
import re
import subprocess
import sys

NDK = sorted(glob.glob(os.path.expanduser("~/Android/Sdk/ndk/*")))[-1]
SP = NDK + "/simpleperf/bin/linux/x86_64/simpleperf"


def parse(stream):
    """-> (per[(tid, event)][cpu] = n, names[tid], n samples)"""
    per = collections.defaultdict(collections.Counter)
    names = {}
    id_event = {}
    event = None
    in_sample = False
    tid = ev = None
    n = 0
    for line in stream:
        s = line.strip()
        if s.startswith("event_attr: for event type "):
            event = s.split("event type ", 1)[1]
            continue
        if s.startswith("ids: ") and event is not None:
            for i in s[5:].split():
                id_event[int(i)] = event
            continue
        if s.startswith("record "):
            in_sample = s.startswith("record sample:")
            tid = ev = None
            continue
        if in_sample:
            m = re.match(r"pid (\d+), tid (\d+)$", s)
            if m:
                tid = int(m[2])
                continue
            m = re.match(r"id (\d+)$", s)
            if m:
                ev = id_event.get(int(m[1]), "?")
                continue
            m = re.match(r"cpu (\d+), res", s)
            if m and tid is not None:
                per[(tid, ev)][int(m[1])] += 1
                n += 1
                in_sample = False
        else:
            m = re.match(r"pid (\d+), tid (\d+), comm (.*)", s)
            if m:
                names[int(m[2])] = m[3]
    return per, names, n


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--selftest":
        return selftest()
    data = sys.argv[1]
    want = {int(t) for t in sys.argv[2:]}
    p = subprocess.Popen([SP, "dump", data], stdout=subprocess.PIPE,
                         stderr=subprocess.DEVNULL, text=True, errors="replace")
    per, names, n = parse(p.stdout)
    p.wait()
    if not n:
        sys.exit("no sample with a cpu field in " + data)
    events = sorted({k[1] or "?" for k in per})
    print(f"{n} samples; events {events}")
    tot = collections.Counter()
    for (t, _), c in per.items():
        tot[t] += sum(c.values())
    tids = sorted(want) if want else [t for t, _ in tot.most_common(12)]
    cpus = sorted({c for v in per.values() for c in v})
    print(f"{'tid':<7} {'name':<17} {'event':<19} {'n':<7}" + " ".join(f"cpu{c:<3}" for c in cpus))
    for t in tids:
        for e in events:
            c = per.get((t, e))
            if not c:
                continue
            k = sum(c.values())
            print(f"{t:<7} {names.get(t, '?')[:16]:<17} {e[:18]:<19} {k:<7}"
                  + " ".join(f"{100 * c[i] / k:5.1f}%" for i in cpus))


FIXTURE = """\
attr 1:
  event_attr: for event type cpu-clock
  ids: 10 11
attr 2:
  event_attr: for event type sched:sched_switch
  ids: 20 21
record comm: type 3, misc 0x0, size 40
  pid 5, tid 7, comm CPU 0/TCG
record sample: type 9, misc 0x2, size 328
  pid 5, tid 7
  time 1
  id 11
  cpu 6, res 0
record sample: type 9, misc 0x2, size 328
  pid 5, tid 7
  time 2
  id 10
  cpu 1, res 0
record sample: type 9, misc 0x2, size 328
  pid 5, tid 7
  time 3
  id 21
  cpu 6, res 0
record sample: type 9, misc 0x2, size 328
  pid 5, tid 8
  time 3
  id 10
  cpu 0, res 0
"""


def selftest():
    per, names, n = parse(FIXTURE.splitlines())
    want = {(7, "cpu-clock"): {6: 1, 1: 1}, (7, "sched:sched_switch"): {6: 1},
            (8, "cpu-clock"): {0: 1}}
    got = {k: dict(v) for k, v in per.items()}
    ok = got == want and n == 4 and names.get(7) == "CPU 0/TCG"
    print("selftest", "ok" if ok else f"FAIL: {got} n={n} names={names}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
