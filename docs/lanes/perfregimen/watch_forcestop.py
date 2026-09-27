#!/usr/bin/env python3
"""Sample /proc every 0.2 s for any process whose command line holds
`force-stop` or targets a serial, and print it with its parent chain.
watch_forcestop.py <seconds> [serial]"""
import os, sys, time

end = time.time() + float(sys.argv[1])
serial = sys.argv[2] if len(sys.argv) > 2 else "ee317437"
seen = set()


def cmd(p):
    try:
        return open("/proc/%s/cmdline" % p, "rb").read().replace(b"\0", b" ").decode(errors="replace").strip()
    except OSError:
        return ""


def ppid(p):
    try:
        for line in open("/proc/%s/status" % p):
            if line.startswith("PPid:"):
                return line.split()[1]
    except OSError:
        pass
    return "0"


while time.time() < end:
    for p in os.listdir("/proc"):
        if not p.isdigit() or p in seen:
            continue
        c = cmd(p)
        if "force-stop" in c or ("am " in c and serial in c):
            seen.add(p)
            chain, q = [], ppid(p)
            for _ in range(8):
                if q in ("0", "1"):
                    break
                chain.append("%s:%s" % (q, cmd(q)[:160]))
                q = ppid(q)
            print(time.strftime("%H:%M:%S"), p, c[:200], flush=True)
            for x in chain:
                print("    <-", x, flush=True)
    time.sleep(0.2)
