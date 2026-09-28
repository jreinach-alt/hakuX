#!/usr/bin/env python3
"""Every run on disk that holds the named captures, oldest first.

usage: caphistory.py [--since YYYY-MM-DD] <results dir> <capture.png> [...]
       (--since is a UTC date)

One line per run: the first 8 hex of each capture's sha256 ('-' when the
run has no such capture), the device and apk read back from result.json,
the request's env, the dispatcher's shader_cache field, and whether the
logcat holds a `Shader module warm-up` line.

It is for telling what a capture's content moves with. A content seen in
one run only moved with everything that run alone had, so print every
column that can differ (device, env, cache) before naming one as the cause.

Like capgroups.py it compares file bytes, not decoded pixels.
"""
import calendar
import hashlib
import json
import os
import re
import sys
import time


def load(path):
    try:
        with open(path) as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def main():
    args = sys.argv[1:]
    since = 0.0
    if args and args[0] == "--since":
        since = calendar.timegm(time.strptime(args[1], "%Y-%m-%d"))
        args = args[2:]
    if len(args) < 2:
        print(__doc__)
        return 2
    root, names = args[0], args[1:]
    rows = []
    for rid in os.listdir(root):
        p = os.path.join(root, rid)
        if not os.path.isdir(p):
            continue
        for sub in sorted(s for s in os.listdir(p) if s.startswith("captures")):
            hashes, mtime = [], None
            for n in names:
                fp = os.path.join(p, sub, n)
                if os.path.isfile(fp):
                    with open(fp, "rb") as fh:
                        hashes.append(hashlib.sha256(fh.read()).hexdigest()[:8])
                    mtime = os.stat(fp).st_mtime
                else:
                    hashes.append("-" * 8)
            if mtime is None or mtime < since:
                continue
            rs = load(os.path.join(p, "result.json"))
            rq = load(os.path.join(p, "request.json"))
            warm = "no logcat"
            lc = os.path.join(p, "logcat%s.txt" % sub[len("captures"):])
            if os.path.isfile(lc):
                with open(lc, errors="replace") as fh:
                    m = re.search(r"Shader module warm-up: (\d+)/(\d+) modules",
                                  fh.read())
                warm = "warm-up %s" % m.group(2) if m else "no warm-up"
            cache = str(rs.get("shader_cache") or "?").split(":")[0]
            env = rq.get("env")
            env = ",".join(env) if isinstance(env, list) else ""
            rows.append((mtime, hashes, rs.get("device_label") or "?",
                         rs.get("apk_sha") or "?", env or "-", cache, warm,
                         rid, sub))
    print("columns: time(UTC) %s device apk env cache logcat run"
          % " ".join(n[:8] for n in names))
    for r in sorted(rows):
        print(time.strftime("%m-%d %H:%M", time.gmtime(r[0])), " ".join(r[1]),
              r[2], r[3], r[4], r[5], "|", r[6], "|", r[7], r[8])
    print("runs:", len(rows))
    return 0


if __name__ == "__main__":
    sys.exit(main())
