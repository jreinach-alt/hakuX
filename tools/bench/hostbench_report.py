#!/usr/bin/env python3
"""Tabulate HAKUX_HOSTBENCH / HAKUX_TOPO output from a result's logcat.

    hostbench_report.py RESULT_DIR_OR_LOGCAT [...]

Prints one row per CPU for the ISA bench (ns per op, and cycles per op at
the clock the core reported after the run), and per-thread placement and
cluster-clock summaries for the topology sampler. Joins topology tids with
the app's own `hakuX-threads` role lines where they are present.
"""
import os
import re
import sys
from collections import defaultdict

KV = re.compile(r"([\w/%]+)=([-\w.%/(),]+)")


def lines_of(p):
    f = os.path.join(p, "logcat.txt") if os.path.isdir(p) else p
    return open(f, errors="replace").read().splitlines()


def main(paths):
    for p in paths:
        L = lines_of(p)
        print("== %s" % p)
        cpus = defaultdict(dict)
        roles = {}
        topo = defaultdict(list)
        freq = []
        therm = []
        for l in L:
            if "hakuX-threads" in l:
                m = re.search(r"tid[= ](\d+)", l)
                r = re.search(r"role[= ]([\w.]+)", l) or re.search(r"\) *:? *([\w.]+)", l)
                if m:
                    roles[m.group(1)] = l.split(":", 3)[-1].strip()[:40]
            i = l.find("perfarch ")
            if i < 0:
                continue
            s = l[i + len("perfarch "):]
            if s.startswith("hb begin"):
                print("  " + s)
            elif s.startswith("hb cpu="):
                kv = dict(KV.findall(s))
                if " miss_ns " in s:
                    # miss_ns reuses the op names; keep them apart.
                    head, tail = s.split(" flush_ns ")
                    kv = {"miss_" + k: v for k, v in KV.findall(head)}
                    kv.update(KV.findall(tail))
                cpus[int(s.split()[1].split("=")[1])].update(kv)
            elif s.startswith("topo tid="):
                kv = dict(KV.findall(s))
                topo[kv["tid"]].append(kv)
            elif s.startswith("topo freq"):
                freq.append(s)
            elif s.startswith("topo thermal"):
                therm.append(s)
            elif s.startswith("hb end") or s.startswith("tso"):
                print("  " + s)
        if cpus:
            cols = ["ldr", "ldapr", "ldar", "str", "stlr", "dmb", "dmbld_ldr",
                    "dmb_str", "mix_plain", "mix_rcpc", "mix_revert",
                    "sl_plain", "sl_rcpc", "sl_rcsc", "sl_revert"]
            print("  cpu midr         idc dic MHz   alu   " +
                  " ".join("%9s" % c for c in cols))
            for c in sorted(cpus):
                kv = cpus[c]
                mhz = kv.get("khz", "-1/-1").split("/")[-1]
                mhz = int(mhz) // 1000 if mhz.lstrip("-").isdigit() else -1
                print("  %3d %-12s %3s %3s %5d %5s " % (
                    c, kv.get("midr"), kv.get("idc"), kv.get("dic"), mhz,
                    kv.get("alu")) +
                    " ".join("%9s" % kv.get(k, "-") for k in cols))
            print("  (ns per op; mix_* and sl_* are ns per unit)")
            print("  cpu  miss_ldr miss_ldapr miss_dmbld  flush b4/b64/b1k/b4k ns")
            for c in sorted(cpus):
                kv = cpus[c]
                print("  %3d %9s %10s %10s  %s/%s/%s/%s" % (
                    c, kv.get("miss_ldr"), kv.get("miss_ldapr"),
                    kv.get("miss_dmbld_ldr"), kv.get("b4"), kv.get("b64"),
                    kv.get("b1k"), kv.get("b4k")))
        if topo:
            print("  thread placement (per report window; cpu%% = cpu0/../cpu7):")
            for tid, rows in sorted(topo.items(),
                                    key=lambda kv: -sum(float(r["busy"].rstrip("%"))
                                                        for r in kv[1])):
                busy = [float(r["busy"].rstrip("%")) for r in rows]
                mig = [float(r["mig/s"]) for r in rows]
                print("  tid %-6s %-14s role=%-24s windows=%-3d busy mean %.0f%% "
                      "max %.0f%%  mig/s mean %.1f  last cpu%%=%s" % (
                          tid, rows[0]["comm"], roles.get(tid, "?")[:24],
                          len(rows), sum(busy) / len(busy), max(busy),
                          sum(mig) / len(mig), rows[-1]["cpu%"]))
        for s in freq[:3] + (["..."] if len(freq) > 6 else []) + freq[-3:]:
            print("  " + s)
        for s in therm[:2] + therm[-2:]:
            print("  " + s)


if __name__ == "__main__":
    main(sys.argv[1:])
