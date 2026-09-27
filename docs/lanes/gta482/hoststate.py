#!/usr/bin/env python3
"""Read hoststate.sh's output: one row per read, then per-thread deltas (lane.gta482, #482).

    hoststate.py <hoststate-timeline.txt> [--threads N]
    hoststate.py --selftest

Per read: the time, online/isolated CPUs, the emulator's cpuset and
Cpus_allowed, each cluster's current and allowed-max frequency (MHz), the
hottest thermal zone, the active cooling devices.

Per pair of consecutive reads, for the N busiest threads: the CPU it last ran
on, and from schedstat the share of the interval it RAN and the share it
WAITED on a run queue. A thread that is runnable but waits for a CPU is not
blocked: simpleperf's off-CPU time holds both, and this separates them.
"""
import re
import sys


def parse(text):
    reads = []
    cur = None
    for line in text.splitlines():
        line = line.rstrip()
        m = re.match(r"== hoststate (\S+) t=(\S+) up=(\S+)", line)
        if m:
            cur = {"mode": m[1], "t": m[2], "up": float(m[3]), "cpu": {}, "cpuset": {},
                   "task": {}, "tz": [], "cool": [], "proc": "", "label": None}
            reads.append(cur)
            continue
        if cur is None:
            continue
        m = re.match(r"online=(\S*) offline=(\S*) isolated=(\S*)", line)
        if m:
            cur["online"], cur["offline"], cur["isolated"] = m[1], m[2], m[3]
            continue
        m = re.match(r"cpu(\d+) online=(\S*) cur=(\d*) max=(\d*) hwmax=(\d*) gov=(\S*)", line)
        if m:
            cur["cpu"][int(m[1])] = {"online": m[2], "cur": int(m[3] or 0), "max": int(m[4] or 0),
                                     "hwmax": int(m[5] or 0), "gov": m[6]}
            continue
        m = re.match(r"cpuset/(\S+) cpus=(\S*)", line)
        if m:
            cur["cpuset"][m[1]] = m[2]
            continue
        if line.startswith("proc "):
            cur["proc"] = line[5:]
            continue
        m = re.match(r"task (\d+) cpuset=(\S*) schedstat=(\d+),(\d+),(\d+) stat=\d+ \((.*)\) (.*)", line)
        if m:
            f = m[7].split()
            # stat fields after the comm: f[0] is field 3 (state); field 39 (processor) is f[36]
            cur["task"][int(m[1])] = {"cpuset": m[2], "run": int(m[3]), "wait": int(m[4]),
                                      "slices": int(m[5]), "comm": m[6], "state": f[0],
                                      "cpu": int(f[36]) if len(f) > 36 else -1}
            continue
        m = re.match(r"tz (\d+) (\S+) (-?\d+)", line)
        if m:
            cur["tz"].append((int(m[3]), m[2]))
            continue
        m = re.match(r"cool (\d+) (\S+) cur=(\d+) max=(\d*)", line)
        if m:
            cur["cool"].append(f"{m[2]}={m[3]}/{m[4]}")
            continue
        m = re.match(r"# label (.*)", line)
        if m:
            cur["label"] = m[1]
    return reads


def clusters(cpu):
    """group CPUs by hwmax -> [(cpus, cur MHz of the fastest, allowed max MHz, hw max MHz)]"""
    by = {}
    for c, v in sorted(cpu.items()):
        by.setdefault(v["hwmax"], []).append(c)
    out = []
    for hw, cs in sorted(by.items()):
        out.append((cs, max(cpu[c]["cur"] for c in cs) // 1000, max(cpu[c]["max"] for c in cs) // 1000, hw // 1000))
    return out


def report(reads, nthreads):
    print(f"{len(reads)} reads")
    for r in reads:
        cl = " ".join(f"cpu{cs[0]}-{cs[-1]}:{cur}/{mx}/{hw}" for cs, cur, mx, hw in clusters(r["cpu"]))
        hot = max(r["tz"], default=(0, "-"))
        t = hot[0] / 1000 if abs(hot[0]) > 1000 else hot[0]
        print(f"{r['t']} up={r['up']:.0f} online={r.get('online')} isolated={r.get('isolated') or '-'} "
              f"[cur/allowed/hw MHz {cl}] hot={t:.0f}C({hot[1]}) cool={','.join(r['cool']) or '-'} "
              f"{r['proc']}")
    print()
    print("per interval, busiest threads: cpu last run on, run share, run-queue wait share")
    for a, b in zip(reads, reads[1:]):
        dt = (b["up"] - a["up"]) * 1e9
        if dt <= 0:
            continue
        rows = []
        for tid, tb in b["task"].items():
            ta = a["task"].get(tid)
            if not ta:
                continue
            rows.append((tb["run"] - ta["run"], tb["wait"] - ta["wait"], tid, tb))
        rows.sort(reverse=True)
        print(f"{a['t']} -> {b['t']} ({dt / 1e9:.1f} s)")
        for run, wait, tid, tb in rows[:nthreads]:
            print(f"    {tid:<7} {tb['comm'][:15]:<16} cpu{tb['cpu']} {tb['cpuset']:<12} "
                  f"run {100 * run / dt:5.1f}%  wait {100 * wait / dt:5.1f}%  "
                  f"neither {100 * (1 - (run + wait) / dt):5.1f}%")


FIXTURE = """\
== hoststate light t=13:00:00 up=100.00
online=0-7 offline= isolated=
cpu0 online=1 cur=2016000 max=2016000 hwmax=2016000 gov=performance core_ctl[active= min= max= need=]
cpu7 online=1 cur=3187200 max=3187200 hwmax=3187200 gov=performance core_ctl[active= min= max= need=]
cpuset/top-app cpus=0-7
cpuset/background cpus=0-2
pid=500
proc cpuset=/top-app oom_score_adj=0 Cpus_allowed_list: 0-7
task 501 cpuset=/top-app schedstat=1000000000,100000000,50 stat=501 (CPU 0/TCG) R 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20 21 22 23 24 25 26 27 28 29 30 31 32 33 34 35 7 0 0
tz 0 cpu-1-0 45000
tz 1 skin 38000
== end
== hoststate light t=13:00:10 up=110.00
online=0-7 offline= isolated=3-7
cpu0 online=1 cur=2016000 max=2016000 hwmax=2016000 gov=performance core_ctl[active= min= max= need=]
cpu7 online=1 cur=1000000 max=1000000 hwmax=3187200 gov=performance core_ctl[active= min= max= need=]
cpuset/top-app cpus=0-7
cpuset/background cpus=0-2
pid=500
proc cpuset=/background oom_score_adj=200 Cpus_allowed_list: 0-2
task 501 cpuset=/background schedstat=8000000000,3100000000,90 stat=501 (CPU 0/TCG) R 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20 21 22 23 24 25 26 27 28 29 30 31 32 33 34 35 2 0 0
tz 0 cpu-1-0 95000
cool 3 cpu-isolate7 cur=1 max=1
== end
"""


def selftest():
    r = parse(FIXTURE)
    a, b = r
    ok = (len(r) == 2 and a["task"][501]["cpu"] == 7 and b["task"][501]["cpu"] == 2
          and a["task"][501]["comm"] == "CPU 0/TCG"
          and b["isolated"] == "3-7" and a["isolated"] == ""
          and b["proc"].startswith("cpuset=/background")
          and b["cpu"][7]["max"] == 1000000 and max(b["tz"])[0] == 95000
          and b["cool"] == ["cpu-isolate7=1/1"]
          and b["task"][501]["run"] - a["task"][501]["run"] == 7000000000
          and b["task"][501]["wait"] - a["task"][501]["wait"] == 3000000000)
    report(r, 3)
    print("selftest", "ok" if ok else "FAIL")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--selftest":
        selftest()
    n = 8
    if "--threads" in sys.argv:
        n = int(sys.argv[sys.argv.index("--threads") + 1])
    report(parse(open(sys.argv[1], errors="replace").read()), n)
