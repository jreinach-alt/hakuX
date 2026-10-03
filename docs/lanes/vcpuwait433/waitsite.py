#!/usr/bin/env python3
"""Which wait owns the vCPU's off-CPU time, from a `--trace-offcpu` capture.

    waitsite.py <perf.data> [--tid T] [--top N] [--from-text report.txt]

The brief (#433, lane.vcpuwait433) names the candidate sites. This reader
charges every off-CPU interval of one thread (switch-out to next switch-in,
from the context-switch records, exactly as slowdown462's offcpu.py does) to
the sched_switch sample taken at that switch-out, then puts the interval in
the FIRST bucket below whose frame pattern appears anywhere in the
switch-out's call chain (the chain is innermost first, so a lock wait inside
pgraph_read lands in `pgraph.lock` even though cpu_exec is further out).

Without --tid it takes the thread with the most cpu-clock samples under a
`cpu_exec` frame: the vCPU (Tron's guest never idles, so it is also the
busiest thread). The verdict line follows the brief: a site that holds
>= 50% of the attributed off-CPU time OWNS the wait; below that, report
the split. Unsampled switch-outs (the sampler drops some) are printed as
their own row and are not attributed to anything.
"""
import argparse
import bisect
import collections
import glob
import os
import subprocess

# (bucket, frame substrings). First match in this order wins, so a narrower
# site goes before the frames it runs under.
BUCKETS = [
    # first: surface_access_callback also calls pgraph_lock_settled
    ("GPU surface download on guest access", ("surface_access_callback", "download_surfaces_in_range",
                                              "surface_download_if_dirty", "process_pending_downloads")),
    ("pgraph.lock in PGRAPH MMIO (#474)", ("pgraph_read", "pgraph_write", "pgraph_mmio_lock",
                                           "pgraph_lock_settled")),
    ("pfifo.lock in USER MMIO (DMA_PUT/GET)", ("user_read", "user_write")),
    ("pfifo.lock in PFIFO MMIO", ("pfifo_read", "pfifo_write")),
    ("fifo skew bound", ("fifo_skew", "pfifo_skew")),
    ("APU d->lock / APU MMIO", ("mcpx_apu", "apu_", "dsp_")),
    ("render-thread round trip (process_pending)", ("process_pending", "render_thread_enqueue")),
    ("TCG exclusive / mmap / tb locks", ("start_exclusive", "mmap_lock", "tb_lock", "cpu_exec_step_atomic",
                                         "page_collection", "tb_invalidate")),
    ("vCPU halt / io-event wait", ("qemu_wait_io_event", "rr_wait_io_event", "idlehalt", "cpu_thread_is_idle")),
    ("BQL", ("bql_lock", "qemu_mutex_lock_iothread")),
]

# bql_lock() is a macro over qemu_mutex_lock_impl, so on this build a BQL wait
# unwinds as a bare bionic mutex frame under its caller. These callers take no
# lock but the BQL (validated on slowdown462's doa3.data: 486 ms of mutex wait
# under cpu_exec_loop, which is the BQL taken for interrupts and exits).
BQL_CALLERS = ("cpu_exec_loop", "mttcg_cpu_thread_fn", "rr_cpu_thread_fn", "do_ld_mmio", "do_st_mmio",
               "prepare_mmio_access", "address_space_", "flatview_", "cpu_exec_setjmp", "io_readx",
               "io_writex", "int_ld_mmio", "int_st_mmio")

SKIP = ("[kernel", "syscall", "__futex", "futex", "pthread_cond", "__pthread", "pthread_mutex",
        "__epoll", "epoll", "__ioctl", "ioctl", "__kernel", "@plt", "__aarch64", "qemu_mutex_lock",
        "qemu_cond", "qemu_event", "qemu_futex", "qemu_sem", "NonPI::", "PI::", "pthread", "Mutex")


def simpleperf():
    ndk = sorted(glob.glob(os.path.expanduser("~/Android/Sdk/ndk/*")))[-1]
    return ndk + "/simpleperf/bin/linux/x86_64/simpleperf"


def records(lines):
    """Yield (kind, rec, chain) from `report-sample --show-callchain` text."""
    kind, rec, chain = None, {}, []
    for line in lines:
        s = line.strip()
        if s in ("sample:", "context_switch:"):
            if rec:
                yield kind, rec, chain
            kind = "sample" if s == "sample:" else "cs"
            rec, chain = {}, []
        elif s.startswith("switch_on:"):
            rec["on"] = s.endswith("true")
        elif s.startswith("time:"):
            rec["time"] = int(s.split(":", 1)[1])
        elif s.startswith("thread_id:"):
            rec["tid"] = s.split(":", 1)[1].strip()
        elif s.startswith("thread_name:"):
            rec["tname"] = s.split(":", 1)[1].strip()
        elif s.startswith("event_type:") and kind == "sample" and "ev" not in rec:
            rec["ev"] = s.split(":", 1)[1].strip()
        elif s.startswith("symbol:") and kind == "sample":
            chain.append(s.split(":", 1)[1].strip())
    if rec:
        yield kind, rec, chain


def bucket(chain):
    for name, pats in BUCKETS:
        for f in chain:
            if any(p in f for p in pats):
                if name == "BQL":
                    # name the caller: the first emulator frame outside the lock
                    i = chain.index(f)
                    callers = [c for c in chain[i + 1:] if not c.startswith(SKIP) and not c.startswith("*")
                               and "bql" not in c]
                    return "BQL <- " + (callers[0] if callers else "?")
                return name
    emu = [f for f in chain if not f.startswith(SKIP) and not f.startswith("*")]
    # a lock wait: a mutex frame inside (before) the first emulator frame
    inner = chain[:chain.index(emu[0])] if emu else chain
    locked = any("Mutex" in f or "mutex_lock" in f for f in inner)
    if locked and emu and emu[0].startswith(BQL_CALLERS):
        return "BQL <- " + emu[0]
    return "other: " + (" <- ".join(emu[:3]) or "(no emulator frame)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("data")
    ap.add_argument("--tid")
    ap.add_argument("--top", type=int, default=15)
    ap.add_argument("--from-text", help="read saved report-sample output instead of running simpleperf")
    a = ap.parse_args()
    if a.from_text:
        src = open(a.from_text, errors="replace")
    else:
        src = subprocess.Popen([simpleperf(), "report-sample", "--show-callchain", "-i", a.data],
                               stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True).stdout

    cs = collections.defaultdict(list)       # tid -> [(time, on)]
    outs = collections.defaultdict(list)     # tid -> [(time, chain)]
    exec_samples = collections.Counter()     # tid -> cpu-clock samples under cpu_exec
    oncpu = collections.Counter()
    names = {}
    for kind, rec, chain in records(src):
        tid, t = rec.get("tid"), rec.get("time")
        if tid is None or t is None:
            continue
        if "tname" in rec:
            names[tid] = rec["tname"]
        if kind == "cs":
            cs[tid].append((t, bool(rec.get("on"))))
        elif rec.get("ev") == "sched:sched_switch":
            outs[tid].append((t, chain))
        elif rec.get("ev") == "cpu-clock":
            oncpu[tid] += 1
            if any("cpu_exec" in f for f in chain):
                exec_samples[tid] += 1

    tid = a.tid or (exec_samples.most_common(1)[0][0] if exec_samples else None)
    if tid is None:
        raise SystemExit("no cpu_exec samples and no --tid: is this a capture of the emulator?")
    print("threads by cpu_exec samples:", ", ".join("%s(%s)=%d" % (t, names.get(t, "?"), n)
                                                  for t, n in exec_samples.most_common(4)))
    sw = sorted(cs[tid])
    so = sorted(outs[tid], key=lambda x: x[0])
    stimes = [t for t, _ in so]
    on_ms = off_ms = 0.0
    by = collections.Counter()
    n_by = collections.Counter()
    for (t0, on0), (t1, _) in zip(sw, sw[1:]):
        dt = (t1 - t0) / 1e6
        if on0:
            on_ms += dt
            continue
        off_ms += dt
        i = bisect.bisect_right(stimes, t0) - 1
        if i >= 0 and t0 - stimes[i] <= 200000:
            k = bucket(so[i][1])
        else:
            k = "(unsampled switch-out)"
        by[k] += dt
        n_by[k] += 1
    if not sw:
        raise SystemExit("tid %s has no context-switch records: was --trace-offcpu on?" % tid)
    span = (sw[-1][0] - sw[0][0]) / 1e6
    attributed = off_ms - by["(unsampled switch-out)"]
    print("tid %s (%s): span %.0f ms, on-CPU %.0f ms, off-CPU %.0f ms (%.1f%%); attributed %.0f ms" % (
        tid, names.get(tid, "?"), span, on_ms, off_ms, 100 * off_ms / max(span, 1), attributed))
    print("  %9s %6s %6s %7s  %s" % ("ms", "%off", "%attr", "n", "site"))
    for k, v in by.most_common(a.top):
        print("  %9.0f %6.1f %6s %7d  %s" % (v, 100 * v / max(off_ms, 1),
              "-" if k.startswith("(unsampled") else "%.1f" % (100 * v / max(attributed, 1)), n_by[k], k))
    top = [(k, v) for k, v in by.most_common() if not k.startswith("(unsampled")]
    if top and attributed > 0:
        k, v = top[0]
        share = v / attributed
        verdict = "OWNS the wait (>= 50%)" if share >= 0.5 else "no single site >= 50%: report the split"
        print("VERDICT: %s holds %.1f%% of attributed off-CPU -> %s" % (k, 100 * share, verdict))


if __name__ == "__main__":
    main()
