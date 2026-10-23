#!/usr/bin/env python3
"""Summarise hakuX-gpubrk lines (vk/draw.c, lane gpubreak1022, #433), one row per arm.

    gpubrk_sum.py [--bands] [--min-cmd N] [LABEL=]LOGCAT ...

Each LOGCAT is one arm's capture: `logcat -v time` (the dispatcher's), `-v
threadtime`, or a desktop stderr. LABEL defaults to the file's name. A row
holds the medians, over the arm's windows, of the fields that answer #433:

  mus     main-pass GPU us per draw command, in-pass (Iw - I0) / commands
  muso    the same over the outer pair (Ow - O0): binning, every tile, loads
  mrep    out/in; mode s (<1.3: sysmem or one tile), u (<1.6), t (tiled)
  p50/p90 us per draw command over the K-command segments, weighted
  drain   Iw - Ie, us: how far the TOP stamps ran ahead of the work
  min/oin main pass / other passes, GPU ms per flip (in-pass)
  r2      the per-window fit of segment time on the features (gpubrk.h)
  sh.*    each feature's share of us per draw command (the three largest)

--bands splits each arm by draw commands per flip (cmd=) into the Step 0
bands: <800, 800-1000, 1000-1200, 1200+. --min-cmd drops lighter windows.

Exit 0 with rows; 1 if no window line was found; 2 if a window line lacks a
field this script reads (the line's format and this parser drifted apart).
"""

import argparse
import os
import re
import statistics
import sys

TAG_RE = re.compile(r"hakuX-gpubrk\s*(?:\(\s*\d+\))?:\s(.*)$")

# Every field gb_win_format writes, in its order. A window line missing one is
# a format drift, never "no data": exit 2.
KEYS = (
    "fl s cb K wfi mp mcmd min mout mrep mrepmed mrepmax mode mus muso p50 p90 "
    "drain op ocmd oin oout fn r2 fit b sh fx fmt wh ld st mreqc mreqz pbind "
    "pchg dub dtx pushB uboK nvK cmd mhz busy drop kg perfquery"
).split()
LISTS = ("b", "sh", "fx")
TEXT = ("mode", "fit", "fmt", "wh", "ld", "st", "mreqc", "mreqz", "kg", "perfquery")
BANDS = ((0, 800, "<800"), (800, 1000, "800-1000"), (1000, 1200, "1000-1200"),
         (1200, float("inf"), "1200+"))


class FormatDrift(Exception):
    pass


def parse_window(msg, where):
    kv = {}
    for tok in msg.split():
        if "=" not in tok:
            raise FormatDrift("%s: token without '=': %r" % (where, tok))
        k, v = tok.split("=", 1)
        kv[k] = v
    missing = [k for k in KEYS if k not in kv]
    if missing:
        raise FormatDrift("%s: window line lacks %s" % (where, " ".join(missing)))
    w = {}
    for k in KEYS:
        v = kv[k]
        if k in LISTS:
            d = {}
            for item in v.split(","):
                name, _, num = item.partition(":")
                try:
                    d[name] = float(num)
                except ValueError:
                    raise FormatDrift("%s: %s=%r is not name:value,..." % (where, k, v))
            w[k] = d
        elif k in TEXT:
            w[k] = v
        else:
            try:
                w[k] = float(v)
            except ValueError:
                raise FormatDrift("%s: %s=%r is not a number" % (where, k, v))
    return w


def read_arm(path):
    """-> (windows, info lines). A window line starts with fl=."""
    wins, info = [], []
    with open(path, errors="replace") as fh:
        for n, line in enumerate(fh, 1):
            m = TAG_RE.search(line.rstrip("\n"))
            if not m:
                continue
            msg = m.group(1).strip()
            if msg.startswith("fl="):
                wins.append(parse_window(msg, "%s:%d" % (path, n)))
            else:
                info.append(msg)
    return wins, info


def med(ws, key):
    v = [w[key] for w in ws]
    return statistics.median(v) if v else 0.0


def row(label, ws):
    fps = [w["fl"] / w["s"] for w in ws if w["s"] > 0]
    modes = {}
    for w in ws:
        modes[w["mode"]] = modes.get(w["mode"], 0) + 1
    shares = {}
    for w in ws:
        for name, v in w["sh"].items():
            shares.setdefault(name, []).append(v)
    top = sorted(((statistics.median(v), k) for k, v in shares.items()), reverse=True)[:3]
    fit_ok = sum(1 for w in ws if w["fit"] == "ok")
    out = [
        ("arm", label),
        ("n", "%d" % len(ws)),
        ("fps", "%.1f" % (statistics.median(fps) if fps else 0)),
        ("cmd", "%.0f" % med(ws, "cmd")),
        ("mcmd", "%.0f" % med(ws, "mcmd")),
        ("mp", "%.2f" % med(ws, "mp")),
        ("min", "%.2f" % med(ws, "min")),
        ("mout", "%.2f" % med(ws, "mout")),
        ("mrep", "%.2f" % med(ws, "mrep")),
        ("mode", "/".join("%s%d" % (k, modes[k]) for k in sorted(modes))),
        ("mus", "%.2f" % med(ws, "mus")),
        ("muso", "%.2f" % med(ws, "muso")),
        ("p50", "%.2f" % med(ws, "p50")),
        ("p90", "%.2f" % med(ws, "p90")),
        ("drain", "%.1f" % med(ws, "drain")),
        ("oin", "%.2f" % med(ws, "oin")),
        ("oout", "%.2f" % med(ws, "oout")),
        ("r2", "%.3f" % med(ws, "r2")),
        ("fitok", "%d/%d" % (fit_ok, len(ws))),
        ("sh", ",".join("%s:%.2f" % (k, v) for v, k in top)),
        ("pchg", "%.1f" % med(ws, "pchg")),
        ("dub", "%.1f" % med(ws, "dub")),
        ("uboK", "%.1f" % med(ws, "uboK")),
        ("mhz", "%.0f" % med(ws, "mhz")),
        ("busy", "%.0f" % med(ws, "busy")),
        ("drop", "%.0f" % sum(w["drop"] for w in ws)),
        ("perfquery", ws[-1]["perfquery"] if ws else "-"),
    ]
    return " ".join("%s=%s" % kv for kv in out)


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--bands", action="store_true")
    ap.add_argument("--min-cmd", type=float, default=0)
    ap.add_argument("arms", nargs="+", metavar="[LABEL=]LOGCAT")
    a = ap.parse_args(argv)
    found = 0
    for spec in a.arms:
        label, sep, path = spec.partition("=")
        if not sep or not os.path.exists(path):
            label, path = os.path.basename(spec), spec
        try:
            wins, info = read_arm(path)
        except FormatDrift as e:
            print("gpubrk_sum: %s" % e, file=sys.stderr)
            return 2
        for msg in info:
            print("# %s: %s" % (label, msg))
        wins = [w for w in wins if w["cmd"] >= a.min_cmd]
        found += len(wins)
        if not wins:
            print("# %s: no hakuX-gpubrk window" % label)
            continue
        print(row(label, wins))
        if a.bands:
            for lo, hi, name in BANDS:
                b = [w for w in wins if lo <= w["cmd"] < hi]
                if b:
                    print(row("%s@%s" % (label, name), b))
    return 0 if found else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
