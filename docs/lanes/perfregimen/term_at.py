#!/usr/bin/env python3
"""term_at.py HH:MM:SS <cmdline-substring>: at the given local time, send
SIGTERM to every process whose command line holds the substring (by PID,
never by pattern-kill), and print what was signalled."""
import os, signal, sys, time

hh, mm, ss = map(int, sys.argv[1].split(":"))
want = sys.argv[2]
now = time.localtime()
at = time.mktime((now.tm_year, now.tm_mon, now.tm_mday, hh, mm, ss, 0, 0, -1))
while time.time() < at:
    time.sleep(0.5)
me = str(os.getpid())
for p in os.listdir("/proc"):
    if not p.isdigit() or p == me:
        continue
    try:
        c = open("/proc/%s/cmdline" % p, "rb").read().replace(b"\0", b" ").decode(errors="replace")
    except OSError:
        continue
    if want in c and "term_at.py" not in c and c.startswith("bash "):
        os.kill(int(p), signal.SIGTERM)
        print(time.strftime("%H:%M:%S"), "TERM ->", p, c[:160], flush=True)
