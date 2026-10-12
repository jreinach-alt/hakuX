#!/usr/bin/env python3
"""measure_report.py <result-dir> -- the save-state measurement table (#433).

Reads the `[savestate] measure ...` and `win begin/end` lines that
HAKUX_SAVESTATE_TEST=...:measure writes (android/app/src/main/cpp/savestate/
hxs.c, test_measure), and the hakuX-pace lines in the same logcat.

Per option, over all cycles:
  save pause_ms         the machine stopped (median, p95)
  durable_ms            until the file the player keeps is fsynced: the save
                        line for a and b; for c the raw file is safe at the
                        save line's durable_ms and the compressed one at the
                        job's compressed_ms; for d the job's durable_ms
  MB                    the final file
  cpu_ms                compression CPU (the save line for b, the job for c/d)
  load                  pause, total, read, decompress, undo, goto, restore
  after the save        the 10 s window that follows each save:
    lag_ms              wall time of the window's hakuX-pace lines minus
                        16.667 ms per flip, minus the save's own pause: frames
                        lost to anything after the machine resumed (the fsync
                        of a, the worker of c and d)
    hitches             pace lines that start inside the window with
                        max >= 100 ms (hitch_report.HITCH_MS)
    worst_ms            the worst flip interval in those lines

The base row is the same window after a load with no save. p95 is the
nearest rank: with 20 cycles, the 19th value.
"""
import math
import os
import re
import statistics
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "..", "testing"))
from hitch_report import LINE, PACE, HITCH_MS, ts  # noqa: E402

KV = re.compile(r"(\w+)=([^\s]+)")
FLIP_MS = 1000.0 / 60.0


def p95(v):
    v = sorted(v)
    return v[max(0, math.ceil(0.95 * len(v)) - 1)] if v else None


def med(v):
    return statistics.median(v) if v else None


def fmt(x, nd=0):
    return "-" if x is None else f"{x:.{nd}f}"


def parse(path):
    saves, jobs, loads, wins, pace = [], [], [], {}, []
    with open(path, errors="replace") as f:
        for line in f:
            m = LINE.match(line.rstrip("\n"))
            if not m:
                continue
            t, tag, msg = ts(m.group(1)), m.group(3), m.group(4)
            if tag == "hakuX-pace":
                p = PACE.search(msg)
                if p:
                    pace.append((t, float(p.group(2)), float(p.group(3))))
                continue
            if "[savestate] " not in msg:
                continue
            body = msg.split("[savestate] ", 1)[1]
            kv = dict(KV.findall(body))
            if body.startswith("measure save "):
                saves.append(kv)
            elif body.startswith("measure job "):
                jobs.append(kv)
            elif body.startswith("measure load "):
                loads.append(kv)
            elif body.startswith("win begin ") or body.startswith("win end "):
                key = (kv["opt"], int(kv["cycle"]))
                wins.setdefault(key, {})["b" if "begin" in body else "e"] = t
    return saves, jobs, loads, wins, pace


def window(pace, t0, b, e, pause_ms):
    # No pace line is logged while the machine is stopped, so the first line
    # after t0 (the stop) is the one that carries the pause.
    inside = [(t, mx, ms) for t, mx, ms in pace if t0 < t <= e]
    if not inside:
        return None
    lag = sum(ms - 60 * FLIP_MS for _, _, ms in inside) - pause_ms
    clean = [(t, mx, ms) for t, mx, ms in inside if t - ms / 1000.0 >= b]
    hitches = sum(1 for _, mx, _ in clean if mx >= HITCH_MS)
    worst = max((mx for _, mx, _ in clean), default=None)
    return lag, hitches, worst


def main(argv):
    rdir = argv[1]
    saves, jobs, loads, wins, pace = parse(os.path.join(rdir, "logcat.txt"))
    opts = []
    for s in saves:
        if s["opt"] not in opts:
            opts.append(s["opt"])
    job_by = {(j["opt"], j["cycle"]): j for j in jobs}
    load_by = {(l["opt"], l["cycle"]): l for l in loads}

    hdr = ("| Option | n | pause med | pause p95 | durable med | durable p95 "
           "| MB | CPU ms | load pause | load total | read | decompress "
           "| undo | goto | restore | lag after (med / p95 ms) | hitches "
           "| worst ms |")
    print(hdr)
    print("|" + "---|" * (hdr.count("|") - 1))

    base = [window(pace, w["b"], w["b"], w["e"], 0.0)
            for (o, c), w in wins.items()
            if o == "base" and "b" in w and "e" in w]
    base = [x for x in base if x]
    if base:
        print("| base (no save) | %d | | | | | | | | | | | | | | %s / %s | %d | %s |"
              % (len(base), fmt(med([x[0] for x in base])),
                 fmt(p95([x[0] for x in base])), sum(x[1] for x in base),
                 fmt(max((x[2] for x in base if x[2] is not None),
                         default=None))))

    for o in opts:
        ss = [s for s in saves if s["opt"] == o and s.get("ok") == "1"]
        pause = [float(s["pause_ms"]) for s in ss]
        durable, mb, cpu, win = [], [], [], []
        for s in ss:
            j = job_by.get((o, s["cycle"]))
            if o.startswith("c") and j:
                durable.append(float(j["compressed_ms"]))
                mb.append(int(j["bytes"]) / 1e6)
                cpu.append(float(j["cpu_ms"]))
            elif o.startswith("d") and j:
                durable.append(float(j["durable_ms"]))
                mb.append(int(j["bytes"]) / 1e6)
                cpu.append(float(j["cpu_ms"]))
            else:
                durable.append(float(s["durable_ms"]))
                mb.append(int(s["bytes"]) / 1e6)
                cpu.append(float(s["cpu_ms"]))
            w = wins.get((o, int(s["cycle"])), {})
            if "b" in w and "e" in w:
                # hxs_save returns at the later of the resume and the
                # durable point it waits for: the stop is that long before.
                back = max(float(s["pause_ms"]), float(s["durable_ms"]))
                x = window(pace, w["b"] - back / 1000.0, w["b"], w["e"],
                           float(s["pause_ms"]))
                if x:
                    win.append(x)
        ll = [load_by[(o, s["cycle"])] for s in ss
              if (o, s["cycle"]) in load_by
              and load_by[(o, s["cycle"])].get("ok") == "1"]

        def lm(k):
            return fmt(med([float(l[k]) for l in ll]))

        print("| %s | %d | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s "
              "| %s | %s | %s | %s / %s | %d | %s |"
              % (o, len(ss), fmt(med(pause), 1), fmt(p95(pause), 1),
                 fmt(med(durable)), fmt(p95(durable)), fmt(med(mb), 1),
                 fmt(med(cpu)), lm("pause_ms"), lm("total_ms"), lm("read_ms"),
                 lm("decompress_ms"), lm("undo_ms"), lm("goto_ms"),
                 lm("restore_ms"), fmt(med([x[0] for x in win])),
                 fmt(p95([x[0] for x in win])), sum(x[1] for x in win),
                 fmt(max((x[2] for x in win if x[2] is not None),
                         default=None))))
    if any(s.get("ok") != "1" for s in saves):
        print("\nfailed saves: %d" % sum(s.get("ok") != "1" for s in saves))
    if any(l.get("ok") != "1" for l in loads):
        print("failed loads: %d" % sum(l.get("ok") != "1" for l in loads))


if __name__ == "__main__":
    main(sys.argv)
