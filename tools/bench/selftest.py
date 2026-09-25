#!/usr/bin/env python3
"""Fixture test for tso_judge.py and hostbench_report.py. Synthetic logcats in
the exact line formats the app writes; the judge must PASS a B arm inside the
registered band, FAIL one above it, FAIL one whose mode never executed, and
REFUSE a pair from two devices. Thresholds are read from the real prediction.
"""
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "../.."))
PRED = os.path.join(ROOT, "docs/testing/predictions/perfarch-tso-rcpc-cost.json")


def mk(d, name, g_ms, tso=None, device="nova", apk="abc", windows=40):
    p = os.path.join(d, name)
    os.makedirs(p)
    L = []
    if tso:
        L.append("09-25 21:00:00.000 I/hakuX-lane(1): perfarch tso mode=rcpc "
                 "requested lrcpc=1 -> %s" % tso)
    for i in range(windows):
        # a slow first quarter the judge must discard, then the steady state
        g = g_ms * (3 if i < windows // 4 else 1) + (i % 3) * 0.1
        L.append("09-25 21:00:%02d.000 I/hakuX-perf(1): gfps=%d G:%.1f(1.0-9.0) "
                 "D:16.7(16.7-16.7) S:1 J:1 Df:1 Vd:0 Ul:N Vpf:1 Ri:1 Tq:1"
                 % (i % 60, int(1000 / g), g))
        if tso == "ON" and i == windows // 2:
            L.append("09-25 21:00:00.000 I/hakuX-lane(1): perfarch tso rcpc "
                     "emitted ld=100000 st=31072 pair=10 slow=5")
    L.append("09-25 21:01:00.000 I/hakuX-pages(1): slow stores 1 (1 reached) "
             "since last: [blocks discarded 0 of 0 visited, generated 0 of 0 "
             "calls] [mb emitted 0, total %d]" % (12 if tso == "ON" else 0))
    open(os.path.join(p, "logcat.txt"), "w").write("\n".join(L) + "\n")
    json.dump({"env": ["HAKUX_TCG_TSO=rcpc"] if tso else [],
               "device_label": device, "apk_sha": apk},
              open(os.path.join(p, "result.json"), "w"))
    return p


def judge(a, b):
    r = subprocess.run([sys.executable, os.path.join(HERE, "tso_judge.py"),
                        "--expect", PRED, "--a"] + a + ["--b"] + b,
                       capture_output=True, text=True)
    return r.returncode, r.stdout + r.stderr


def main():
    exp = json.load(open(PRED))["expect"]
    lo, hi = exp["T1b_cost_min"], exp["T1b_cost_max"]
    mid = (lo + hi) / 2
    fails = 0
    with tempfile.TemporaryDirectory() as d:
        a = [mk(d, "a1", 50.0), mk(d, "a2", 50.2)]
        cases = [
            ("in band", [mk(d, "b1", 50.1 * (1 + mid), "ON"),
                         mk(d, "b2", 50.1 * (1 + mid), "ON")], a, 0),
            ("above band", [mk(d, "c1", 50.1 * (1 + hi + 0.1), "ON"),
                            mk(d, "c2", 50.1 * (1 + hi + 0.1), "ON")], a, 1),
            ("never ran", [mk(d, "e1", 50.1 * (1 + mid), None),
                           mk(d, "e2", 50.1 * (1 + mid), None)], a, 1),
            ("two devices", [mk(d, "f1", 50.1 * (1 + mid), "ON", "thor"),
                             mk(d, "f2", 50.1 * (1 + mid), "ON", "thor")], a, 3),
        ]
        for name, b, aa, want in cases:
            rc, out = judge(aa, b)
            ok = rc == want
            fails += not ok
            print("%-12s want %d got %d  %s" % (name, want, rc,
                                               "ok" if ok else "WRONG"))
            if not ok:
                print(out)
        # Middle-element check: the judge must use the MEDIAN run, so a
        # three-run B with one outlier each side still lands in band.
        b3 = [mk(d, "m1", 50.1 * (1 + lo - 0.05), "ON"),
              mk(d, "m2", 50.1 * (1 + mid), "ON"),
              mk(d, "m3", 50.1 * (1 + hi + 0.2), "ON")]
        rc, out = judge(a, b3)
        line = [l for l in out.splitlines() if "cost=" in l]
        print("median-of-3 %s" % (line[0].strip() if line else out))
        got = float(line[0].split("cost=")[1].split("%")[0]) / 100 if line else 9
        ok = abs(got - mid) < 0.01
        fails += not ok
        print("median-of-3  %s" % ("ok" if ok else "WRONG"))
        # hostbench_report must parse its own formats without crashing.
        hb = os.path.join(d, "hb.txt")
        open(hb, "w").write(
            "I/hakuX-lane(1): perfarch hb begin ncpu=8 hwcap=0x1 hwcap2=0x0 "
            "lse=1 lrcpc=1 ilrcpc=1 uscat=1 sve2=1\n"
            "I/hakuX-lane(1): perfarch hb cpu=7 midr=0x411fd4e0 ctr=0x9444c004 "
            "idc=1 dic=0 khz=3187200/3187200 alu=0.100\n"
            "I/hakuX-lane(1): perfarch hb cpu=7 op_ns ldr=0.1 ldapr=0.2 "
            "ldar=0.3 str=0.1 stlr=0.9 dmb=5.0 dmbld_ldr=4.0 dmb_str=6.0\n"
            "I/hakuX-lane(1): perfarch hb cpu=7 unit_ns mix_plain=1 mix_rcpc=2 "
            "mix_revert=9 sl_plain=1 sl_rcpc=2 sl_rcsc=3 sl_revert=9\n"
            "I/hakuX-lane(1): perfarch hb cpu=7 miss_ns ldr=1.5 ldapr=2.5 "
            "dmbld_ldr=30.0 flush_ns b4=50.0 b64=60.0 b1k=300.0 b4k=900.0\n"
            "I/hakuX-lane(1): perfarch topo tid=42 comm=qemu_main busy=85.0% "
            "mig/s=0.1 rqwait_ms/s=1.00 cpu%=0/0/0/0/0/0/0/100\n"
            "I/hakuX-lane(1): perfarch topo freq win_s=10.0 p0=1000(300-2000,cap2000)\n")
        r = subprocess.run([sys.executable,
                            os.path.join(HERE, "hostbench_report.py"), hb],
                           capture_output=True, text=True)
        ok = (r.returncode == 0 and "0.9" in r.stdout and "30.0" in r.stdout
              and "900.0" in r.stdout and "qemu_main" in r.stdout)
        fails += not ok
        print("report       %s" % ("ok" if ok else "WRONG\n" + r.stdout + r.stderr))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
