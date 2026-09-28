#!/usr/bin/env python3
"""smart_duty.py <dispatch results dir>

The duty SMART (fan_mode 4) drives under real titles, per device, from the
thermal.jsonl every soak writes since #554, binned by xo-therm. A soak counts
when its perf_regimen.json says the title ran at fan_mode 4, and its device
comes from result.json's device_label. Read-only.
"""
import collections, glob, json, os, sys

root = sys.argv[1]
bins = collections.defaultdict(list)       # (device, 5 C bin) -> duties
runs = collections.defaultdict(set)
for tj in glob.glob(os.path.join(root, "*", "thermal.jsonl")):
    d = os.path.dirname(tj)
    try:
        pr = json.load(open(os.path.join(d, "perf_regimen.json")))
        dev = json.load(open(os.path.join(d, "result.json"))).get("device_label")
    except (OSError, ValueError):
        continue
    if pr.get("fan_mode") != 4 or not dev:
        continue
    for line in open(tj):
        try:
            r = json.loads(line)
        except ValueError:
            continue
        if r.get("label") not in ("hold", "end"):
            continue
        duty = (r.get("fan") or {}).get("duty")
        xo = [t[2] for t in r.get("tz") or [] if t[1] == "xo-therm"]
        if not isinstance(duty, int) or not xo:
            continue
        b = int(xo[0] / 1000 // 5 * 5)
        bins[(dev, b)].append(duty)
        runs[(dev, b)].add(os.path.basename(d))
print("| device | xo-therm | samples | soaks | duty min | median | max |")
print("|---|---|---|---|---|---|---|")
for (dev, b) in sorted(bins):
    ds = sorted(bins[(dev, b)])
    print("| %s | %d-%d C | %d | %d | %d | %d | %d |" % (
        dev, b, b + 5, len(ds), len(runs[(dev, b)]), ds[0], ds[len(ds) // 2], ds[-1]))
