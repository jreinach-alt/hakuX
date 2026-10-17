#!/usr/bin/env python3
"""Per-window timeline of the owner's Halo capture (lane.halo1016).

Reads a `logcat -v threadtime` dump and prints, per [rr425] window (2 s, the
vCPU thread's clock), the guest-side split next to the nearest draw-side lines.
Fields are read as their sources define them:

  [rr425]   accel/tcg/cpu-exec.c rr425_tick: it, e, eo, es, gapus, tbus, ip, iq
  [rr425w]  same file rrw_tick: idle_us, n (idle stretches ended by a wake)
  [rr425pc] top (cause, pc, bytes, count)
  gfps      hw/xbox/nv2a/pgraph/profile.c: one line per 60 guest flips;
            G = smoothed flip interval (EMA 0.2), min-max over the window
  [rdc]     tcpu = draw thread CPU ms over its 60 frames, dt = their wall ms

usage: timeline.py LOGCAT [PID]
"""
import re
import sys

path = sys.argv[1]
pid = sys.argv[2] if len(sys.argv) > 2 else None

TS = re.compile(r"^\d\d-\d\d (\d\d):(\d\d):(\d\d\.\d+)\s+(\d+)\s+(\d+)")


def secs(m):
    return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))


def kv(s):
    return dict(re.findall(r"(\w+)=(-?[\d.]+)", s))


rows = []          # rr425 windows
others = []        # (t, kind, text)
for line in open(path, errors="replace"):
    m = TS.match(line)
    if not m:
        continue
    if pid and m.group(4) != pid:
        continue
    t = secs(m)
    body = line[m.end():]
    if "[rr425] " in body:
        d = kv(body.split("[rr425]", 1)[1])
        rows.append({"t": t, **d})
    elif "[rr425w] " in body:
        d = kv(body.split("[rr425w]", 1)[1].split(" 3")[0])
        if rows:
            rows[-1]["idle_us"] = d.get("idle_us")
            rows[-1]["wn"] = d.get("n")
            keys = re.findall(r" ([0-9a-f]{2}\.[0-9a-f]{2}):(\d+):(\d+):(\d+):", body)
            rows[-1]["wk"] = " ".join("%s:%s/%sms" % (k, n, int(i) // 1000)
                                      for k, n, i, b in keys[:3] if int(n))
    elif "[rr425pc] " in body:
        top = re.findall(r" ([a-z]):([0-9a-f]{8}):([0-9a-f]{6}):(\d+)", body)
        if rows:
            rows[-1]["pc"] = " ".join("%s:%s:%s:%dk" % (c, p[-6:], b, int(n) // 1000)
                                      for c, p, b, n in top[:3])
    elif "gfps=" in body:
        g = re.search(r"gfps=(\d+) G:([\d.]+)\(([\d.]+)-([\d.]+)\).*Vpf:([\d.]+)", body)
        others.append((t, "gfps", "gfps=%s G=%s(%s-%s) Vpf=%s" % g.groups()))
    elif "[rdc]" in body:
        d = kv(body)
        others.append((t, "rdc", "tcpu=%s/%sms" % (d.get("tcpu"), d.get("dt"))))
    elif "[drawrec]" in body:
        d = kv(body)
        others.append((t, "drawrec", "redoKB=%s" % d.get("redoKB")))
    elif "[rwait526]" in body:
        d = kv(body)
        others.append((t, "rwait", "thr_cpu=%s" % d.get("thr_cpu_ms")))
    elif "fifoskew" in body:
        b = re.search(r"backlog\(mean=(\d+) max=(\d+)\) drain\(n=(\d+)", body)
        lost = re.search(r"lost=(\d+)", body)
        k = re.search(r"kicks=(\d+)", body)
        others.append((t, "fifo", "kicks=%s bl=%dK/%dK drain=%s lost=%s" % (
            k.group(1), int(b.group(1)) // 1024, int(b.group(2)) // 1024,
            b.group(3), lost.group(1) if lost else "?")))


def hms(t):
    h = int(t // 3600)
    m = int(t % 3600 // 60)
    return "%02d:%02d:%04.1f" % (h, m, t % 60)


oi = 0
for r in rows:
    while oi < len(others) and others[oi][0] <= r["t"]:
        print("    %s %-7s %s" % (hms(others[oi][0]), others[oi][1], others[oi][2]))
        oi += 1
    def g(k):
        return int(r.get(k, 0) or 0)
    print("%s it=%5dk e=%6dk eo=%5dk es=%5dk m=%4dk g=%5dk gap=%4dms tb=%4dms "
          "ip=%4d iq=%4d idle=%4dms wn=%4s %s | %s" % (
              hms(r["t"]), g("it") // 1000, g("e") // 1000, g("eo") // 1000,
              g("es") // 1000, g("m") // 1000, g("g") // 1000,
              g("gapus") // 1000, g("tbus") // 1000, g("ip"), g("iq"),
              g("idle_us") // 1000, r.get("wn", "-"), r.get("pc", ""),
              r.get("wk", "")))
