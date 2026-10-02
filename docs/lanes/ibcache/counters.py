#!/usr/bin/env python3
"""The jump-cache, helper-call and probe counters of one capture session (#507, lane.ibcache).

    counters.py <capture_gta.sh session dir> [--last 40]

Reads the session's logcat.txt and prints, over the last N lines of each tag
(the profile window sits at the end of the s4 route):

  [jc425]   the jump cache's outcome per helper lookup: ih hit, ie empty slot,
            ip pc mismatch, is stale, ik key mismatch; if/in the QHT after a miss;
            as shares and as lookups per second
  [rr425]   hc, helper_lookup_tb_ptr calls per 2 s window, as a rate
  [ibc507]  the probe's switch line and its hit counter (HAKUX_IBC=2)

and the soak's pw samples from thermal.jsonl. Offline; reads files only.
"""
import argparse
import json
import os
import re
import statistics


def series(lines, tag):
    out = []
    for line in lines:
        if tag in line:
            out.append({k: int(v) for k, v in re.findall(r"(\w+)=(\d+)", line)})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dir")
    ap.add_argument("--last", type=int, default=40)
    a = ap.parse_args()
    lines = open(os.path.join(a.dir, "logcat.txt"), errors="replace").read().splitlines()

    jc = series(lines, "[jc425]")[-a.last:]
    # h/e/p/s/k are the probe's outcome, one per lookup; f/n are the QHT
    # lookup that follows a miss (found / none), so they are not in the total.
    keys = ["ih", "ie", "ip", "is", "ik"]
    sums = dict((k, sum(r.get(k, 0) for r in jc)) for k in keys + ["if", "in"])
    tot = sum(sums[k] for k in keys)
    secs = sum(r.get("dt", 0) for r in jc) / 1000.0
    print("[jc425] helper caller, %d lines, %.0f s, %.2fM lookups/s" % (len(jc), secs, tot / secs / 1e6))
    for k in keys:
        print("  %-3s %6.2f%%" % (k, 100.0 * sums[k] / tot))
    print("  after a miss: QHT found %d, none %d" % (sums["if"], sums["in"]))

    rr = series(lines, "[rr425]")[-a.last:]
    hc = [r.get("hc", 0) for r in rr]
    print("[rr425] hc per 2 s window: mean %.0f, median %.0f (%.2fM/s)"
          % (statistics.mean(hc), statistics.median(hc), statistics.mean(hc) / 2e6))

    ibc = [line for line in lines if "[ibc507]" in line]
    print("[ibc507] %d lines" % len(ibc))
    for line in ibc[:1] + ibc[-3:]:
        print("  " + line[line.index("[ibc507]"):])

    tj = os.path.join(a.dir, "thermal.jsonl")
    if os.path.exists(tj):
        # pw: battery current_now is negative when discharging (uA, uV).
        bat, usb = [], []
        for raw in open(tj):
            pw = json.loads(raw).get("pw") or {}
            b, u = pw.get("battery") or {}, pw.get("usb") or {}
            if "current_now" in b and "voltage_now" in b:
                bat.append(-b["current_now"] * b["voltage_now"] / 1e12)
            if u.get("online") and "current_now" in u and "voltage_now" in u:
                usb.append(u["current_now"] * u["voltage_now"] / 1e12)
        if bat:
            print("pw: %d samples, battery out %.2f W (median), USB in %.2f W (median)"
                  % (len(bat), statistics.median(bat), statistics.median(usb) if usb else 0.0))


if __name__ == "__main__":
    main()
