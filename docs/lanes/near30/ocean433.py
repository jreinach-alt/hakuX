#!/usr/bin/env python3
"""lane.near30: decompose a held Blinx 2 run's logcat between hakuX-route marks (#433).

    python3 ocean433.py <logcat.txt> <start_mark>:<end_mark> [...]

Each window is cut on the device clock. Per window: fps from the hakuX-pace
frame counter (frames / interval), renderer ms per frame from hakuX-phase
(Tot, Draw, Fin, Idle, GPU), guest busy share from [rr425w], and the vCPU
thread's on-CPU share from [idlehalt] (run_us / span_us).
"""
import re
import sys

LINE = re.compile(r"^(\d\d-\d\d) (\d\d:\d\d:\d\d\.\d+) +\d+ +\d+ \w (\S+)\s*: (.*)$")
KV = re.compile(r"(\w+)=(-?\d+(?:\.\d+)?)")
PH = re.compile(r"(\w+):(\d+(?:\.\d+)?)")


def ts(s):
    hh, mm, rest = s.split(":")
    return int(hh) * 3600 + int(mm) * 60 + float(rest)


def load(path):
    rows = []
    for line in open(path, errors="replace"):
        m = LINE.match(line.rstrip("\n"))
        if not m:
            continue
        rows.append((ts(m.group(2)), m.group(3), m.group(4)))
    return rows


def window(rows, t0, t1):
    pace, phase, rr, idle, work = [], [], [], [], []
    marks = {}
    for t, tag, body in rows:
        if not (t0 <= t <= t1):
            continue
        if tag == "hakuX-pace":
            kv = dict((k, float(v)) for k, v in KV.findall(body))
            if "f" in kv and "ms" in kv:
                pace.append((t, kv["f"], kv["ms"]))
        elif tag == "hakuX-phase":
            kv = dict((k, float(v)) for k, v in PH.findall(body))
            if "Tot" in kv:
                phase.append(kv)
        elif tag == "xemu-work":
            kv = dict((k, float(v)) for k, v in PH.findall(body))
            if "BE" in kv:
                work.append(kv)
        elif tag == "hakuX":
            if "[rr425w]" in body:
                kv = dict((k, float(v)) for k, v in KV.findall(body))
                if "busy_us" in kv:
                    rr.append(kv)
            elif "[idlehalt]" in body:
                kv = dict((k, float(v)) for k, v in KV.findall(body))
                if "run_us" in kv and "span_us" in kv:
                    idle.append(kv)
    out = {}
    if len(pace) > 1:
        frames = sum(b[1] - a[1] for a, b in zip(pace, pace[1:]) if b[1] >= a[1])
        ms = sum(b[2] for a, b in zip(pace, pace[1:]) if b[1] >= a[1])
        out["fps"] = frames / (ms / 1000.0) if ms else 0
        out["n_pace"] = len(pace)
    if phase:
        for k in ("Tot", "Draw", "Fin", "Idle", "GPU"):
            vals = [p[k] for p in phase if k in p]
            if vals:
                out[k] = sum(vals) / len(vals)
    if work:
        for k in ("BE", "TexU", "PBnd", "UBOd"):
            out[k] = sum(w[k] for w in work if k in w) / len(work)
    if rr:
        b = sum(r["busy_us"] for r in rr)
        i = sum(r["idle_us"] for r in rr)
        out["guest_busy_share"] = b / (b + i) if b + i else 0
    if idle:
        run = sum(r["run_us"] for r in idle)
        span = sum(r["span_us"] for r in idle)
        out["vcpu_on_cpu_share"] = run / span if span else 0
    return out


def main():
    rows = load(sys.argv[1])
    marks = {}
    for t, tag, body in rows:
        if tag == "hakuX-route" and body.startswith("mark "):
            marks[body[5:].strip()] = t
    for spec in sys.argv[2:]:
        a, b = spec.split(":")
        if a not in marks or b not in marks:
            print(spec, "missing mark")
            continue
        w = window(rows, marks[a], marks[b])
        print(spec, round(marks[b] - marks[a], 1), "s", {k: round(v, 3) for k, v in w.items()})


if __name__ == "__main__":
    main()
