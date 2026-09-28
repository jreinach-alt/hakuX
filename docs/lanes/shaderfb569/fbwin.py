#!/usr/bin/env python3
"""#569 P1: the [shd413] windows of a soak, with the pipeline creation feedback
fields, scored against docs/testing/predictions/shaderfb569-doa-feedback.json.

    fbwin.py <result dir | logcat.txt> [--excess-ms 14800]
    fbwin.py --selftest

Each [shd413] line closes a window of 60 flips (pgraph/profile.c). This reads
the #413 fields (dt_ms, dpm, dsm, dvm) and the #569 ones appended after W=
(dpc_ms, dpn, dfb, dfbh, dfb_ms, dvs/dgs/dfs_ms, dsru, dsrum, dsru_ms, dsnu,
dsnum, dsnu_ms, dgl_ms, dsmod_ms, dsv_ms, kd=a/b/c/d/e/f/g/h/i, dins_us).

The fight load, fixed before any run. The steady fight is the first run of
three windows in a row with dpm == 0 and dt_ms >= 4000 that comes after a
window with dpm >= 1 after `mark play`. The load ends at the last dpm >= 1
window before the steady fight, and starts at the first dpm >= 1 window after
the last run of four dpm == 0 windows in a row before that end (or after
`mark play`). On pipeline413's ring-out soak this is 09:37:30-09:37:49, the
span its frames show as black screen -> GET READY. Its own excess, as
pipeline413 section 7 computed it: the sum of dt_ms over the span's windows
with dpm >= 1, minus that many times the median dt_ms of the span's dpm == 0
windows (none: the excess is not computed).
"""
import json
import os
import re
import statistics
import sys

TS = re.compile(r"^\d\d-\d\d (\d\d):(\d\d):(\d\d\.\d+) ")
MARK = re.compile(r"hakuX-route.*: mark (\S+)")
KV = re.compile(r"(\w+)=(\S+)")
KD = ("VP", "FF", "CB", "TX", "FL", "PO", "GE", "NONE", "NOPREV")
FIGHT_DT_MS = 4000   # a steady-fight window: 60 flips at the fight's ~11 fps take ~5.3 s
QUIET_RUN = 4        # zero-miss windows in a row that separate the load from the menus
NEED = ("f", "dt_ms", "dpm", "dsm", "dvm", "pc_ms", "dpc_ms", "dpn", "dfb", "dfbh",
        "dfb_ms", "dvs_ms", "dgs_ms", "dfs_ms", "dsru", "dsrum", "dsru_ms", "dsnu",
        "dsnum", "dsnu_ms", "dgl_ms", "dsmod_ms", "dsv_ms", "kd", "dins_us")


def secs(line):
    m = TS.match(line)
    return None if not m else int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))


def parse(lines):
    wins, marks, bad = [], [], 0
    day, last = 0.0, None
    for line in lines:
        t = secs(line)
        if t is None:
            continue
        if last is not None and t + day < last - 43200:
            day += 86400
        t += day
        last = t
        m = MARK.search(line)
        if m:
            marks.append((t, m.group(1)))
            continue
        i = line.find("[shd413]")
        if i < 0:
            continue
        kv = dict(KV.findall(line[i:]))
        try:
            w = {k: float(kv[k]) for k in NEED if k != "kd"}
            kd = [int(x) for x in kv["kd"].split("/")]
            if len(kd) != len(KD):
                raise ValueError
        except (KeyError, ValueError):
            bad += 1
            continue
        w["kd"] = kd
        w["t"], w["hms"] = t, line[6:18]
        wins.append(w)
    return wins, marks, bad


def fight_load(wins, marks):
    """The span defined in the module docstring, or None."""
    play = [t for t, n in marks if n == "play"]
    if not play:
        return None
    idx = [i for i, w in enumerate(wins) if w["t"] > play[0]]
    if not idx:
        return None
    first = idx[0]
    seen_miss, fight = False, None
    for i in range(first, len(wins) - 2):
        if wins[i]["dpm"] >= 1:
            seen_miss = True
        elif seen_miss and all(wins[j]["dpm"] == 0 and wins[j]["dt_ms"] >= FIGHT_DT_MS
                               for j in (i, i + 1, i + 2)):
            fight = i
            break
    if fight is None:
        return None
    end = max(j for j in range(first, fight) if wins[j]["dpm"] >= 1)
    start, zeros = first, 0
    for j in range(end, first - 1, -1):
        zeros = zeros + 1 if wins[j]["dpm"] == 0 else 0
        if zeros >= QUIET_RUN:
            start = j + QUIET_RUN
            break
    while wins[start]["dpm"] == 0:
        start += 1
    return wins[start:end + 1]


def total(ws, k):
    return sum(w[k] for w in ws)


def kd_sum(ws):
    return [sum(w["kd"][i] for w in ws) for i in range(len(KD))]


def score(wins, marks, bad, shader_cache, excess_ms):
    r = {"lines": len(wins), "unparsed": bad, "shader_cache": shader_cache}
    r["monotonic"] = all(b["pc_ms"] >= a["pc_ms"] for a, b in zip(wins, wins[1:]))
    r["fb_valid"] = total(wins, "dfb")
    r["creates"] = total(wins, "dpn")
    r["M0"] = bool(shader_cache and shader_cache.startswith("cleared") and len(wins) >= 20
                   and bad == 0 and r["monotonic"])
    load = fight_load(wins, marks)
    r["load"] = load
    if load:
        dpc = total(load, "dpc_ms")
        miss = [w for w in load if w["dpm"] >= 1]
        zero = [w for w in load if w["dpm"] == 0]
        own = (total(miss, "dt_ms") - len(miss) * statistics.median(w["dt_ms"] for w in zero)
               if zero else None)
        r.update(load_dpc_ms=dpc, load_dpm=total(load, "dpm"), load_dt_ms=total(load, "dt_ms"),
                 own_excess_ms=own, load_dgl_ms=total(load, "dgl_ms"),
                 load_kd=kd_sum(load))
        r["C1"] = abs(dpc - excess_ms) <= 0.2 * excess_ms
        r["C1own"] = None if own is None else abs(dpc - own) <= 0.2 * own
        r["C2"] = dpc > 0 and total(load, "dgl_ms") <= 0.05 * dpc
    ru, rum = total(wins, "dsru"), total(wins, "dsrum")
    nu, num = total(wins, "dsnu"), total(wins, "dsnum")
    r.update(stage_reused=ru, stage_reused_miss=rum, stage_new=nu, stage_new_miss=num,
             reused_ms_each=total(wins, "dsru_ms") / ru if ru else None,
             new_ms_each=total(wins, "dsnu_ms") / nu if nu else None,
             run_dpc_ms=total(wins, "dpc_ms"), run_dgl_ms=total(wins, "dgl_ms"),
             run_dsmod_ms=total(wins, "dsmod_ms"), run_dsv_ms=total(wins, "dsv_ms"),
             run_dfb_ms=total(wins, "dfb_ms"), run_kd=kd_sum(wins),
             run_dins_us=total(wins, "dins_us"))
    r["C3_share"] = rum / ru if ru else None
    r["C3"] = (None if r["C3_share"] is None else
               ">=50% (GPL bound 1/2-2/3 of a miss)" if r["C3_share"] >= 0.5 else
               "<=10% (drop P5)" if r["C3_share"] <= 0.1 else "between 10% and 50%")
    r["O_us_per_create"] = r["run_dins_us"] / r["creates"] if r["creates"] else None
    return r


def logcat_of(path):
    if os.path.isdir(path):
        rj = os.path.join(path, "result.json")
        sc = None
        if os.path.exists(rj):
            j = json.load(open(rj))
            sc = j.get("shader_cache")
            print("result: shader_cache=%s device=%s apk=%s ref=%s" % (
                sc, j.get("device_label") or j.get("device"), j.get("apk_sha"), j.get("ref")))
        return os.path.join(path, "logcat.txt"), sc
    return path, None


def fmt_kd(kd):
    return " ".join("%s=%d" % (n, v) for n, v in zip(KD, kd))


def main():
    if "--selftest" in sys.argv:
        return selftest()
    path, sc = logcat_of(sys.argv[1])
    excess = float(sys.argv[sys.argv.index("--excess-ms") + 1]) if "--excess-ms" in sys.argv else 14800.0
    wins, marks, bad = parse(open(path, errors="replace"))
    print("%d [shd413] lines with #569 fields, %d unparsed" % (len(wins), bad))
    mi = 0
    print("hms          dt_ms dpm dsm dvm   dpc_ms  dpn dfb dfbh  dfb_ms   dvs  dfs   sru/m  snu/m  dgl_ms dsmod dsv_ms  kd                 dins_us")
    for w in wins:
        while mi < len(marks) and marks[mi][0] <= w["t"]:
            print("   -- mark %s" % marks[mi][1])
            mi += 1
        print("%s %6d %3d %3d %3d %8.1f %4d %3d %3d %8.1f %5.0f %5.0f %3d/%-3d %3d/%-3d %6.1f %6.1f %6.1f  %-18s %6.1f" % (
            w["hms"], w["dt_ms"], w["dpm"], w["dsm"], w["dvm"], w["dpc_ms"], w["dpn"], w["dfb"],
            w["dfbh"], w["dfb_ms"], w["dvs_ms"], w["dfs_ms"], w["dsru"], w["dsrum"], w["dsnu"],
            w["dsnum"], w["dgl_ms"], w["dsmod_ms"], w["dsv_ms"], "/".join(map(str, w["kd"])),
            w["dins_us"]))
    r = score(wins, marks, bad, sc, excess)
    print("\nM0 %s: cold=%s lines=%d unparsed=%d monotonic=%s; creates=%d with valid feedback=%d" % (
        "PASS" if r["M0"] else "FAIL", sc, r["lines"], r["unparsed"], r["monotonic"],
        r["creates"], r["fb_valid"]))
    if r["load"]:
        L = r["load"]
        print("fight load: %s .. %s, %d windows, dt %.0f ms, dpm %d" % (
            L[0]["hms"], L[-1]["hms"], len(L), r["load_dt_ms"], r["load_dpm"]))
        print("C1  %s: load dpc_ms %.0f vs registered excess %.0f (ratio %.2f)" % (
            "PASS" if r["C1"] else "FAIL", r["load_dpc_ms"], excess, r["load_dpc_ms"] / excess))
        if r["own_excess_ms"] is not None:
            print("C1' %s: vs this run's own excess %.0f (ratio %.2f)" % (
                "PASS" if r["C1own"] else "FAIL", r["own_excess_ms"],
                r["load_dpc_ms"] / r["own_excess_ms"] if r["own_excess_ms"] else float("inf")))
        else:
            print("C1' not computed: no dpm == 0 window inside the load")
        print("C2  %s: load glslang %.1f ms = %.2f%% of dpc_ms" % (
            "PASS" if r["C2"] else "FAIL", r["load_dgl_ms"],
            100 * r["load_dgl_ms"] / r["load_dpc_ms"] if r["load_dpc_ms"] else float("nan")))
        print("C4  load key-diff classes: %s" % fmt_kd(r["load_kd"]))
    else:
        print("fight load: NOT FOUND (no mark play, no miss after it, or no steady fight): C1, C2, C4 VOID")
    print("C3  reused-module stages %d, driver cache misses %d -> share %s: %s" % (
        r["stage_reused"], r["stage_reused_miss"],
        "%.1f%%" % (100 * r["C3_share"]) if r["C3_share"] is not None else "-", r["C3"]))
    print("    new-module stages %d, misses %d; ms per stage: reused %s, new %s" % (
        r["stage_new"], r["stage_new_miss"],
        "%.1f" % r["reused_ms_each"] if r["reused_ms_each"] is not None else "-",
        "%.1f" % r["new_ms_each"] if r["new_ms_each"] is not None else "-"))
    print("run: dpc %.0f ms, feedback %.0f ms, glslang %.1f ms, module %.1f ms, cache saves %.1f ms, kd %s" % (
        r["run_dpc_ms"], r["run_dfb_ms"], r["run_dgl_ms"], r["run_dsmod_ms"], r["run_dsv_ms"],
        fmt_kd(r["run_kd"])))
    print("O   instrument: %.1f us over %d creates = %s us each" % (
        r["run_dins_us"], r["creates"],
        "%.2f" % r["O_us_per_create"] if r["O_us_per_create"] is not None else "-"))


def selftest():
    lines = []

    def L(h, dt, dpm, dpc, pc, kd="0/0/0/0/0/0/0/0/0", sru=0, srum=0, snu=0, snum=0, gl=0.0, ins=5.0):
        lines.append(
            "09-28 %s I/hakuX-perf( 1): [shd413] f=60 dt_ms=%d ph=1 pm=1 dph=0 dpm=%d sh=0 sm=0 dsh=0 "
            "dsm=%d vh=0 vm=0 dvh=0 dvm=0 L=N W=0 pc_ms=%.1f dpc_ms=%.1f dpn=%d dfb=%d dfbh=0 "
            "dfb_ms=%.1f dvs_ms=1.0 dgs_ms=0.0 dfs_ms=2.0 dsru=%d dsrum=%d dsru_ms=%.1f dsnu=%d "
            "dsnum=%d dsnu_ms=%.1f dgl_ms=%.1f dsmod_ms=1.0 dsv_ms=0.0 kd=%s dins_us=%.1f" % (
                h, dt, dpm, dpm, pc, dpc, dpm, dpm, dpc, sru, srum, sru * 10.0, snu, snum,
                snu * 100.0, gl, kd, ins))
    pc = 0.0
    for i in range(17):
        L("05:00:%02d.000" % i, 1000, 0, 0.0, pc)
    lines.append("09-28 05:00:30.000 I/hakuX-route( 2): mark play")
    # a menu miss after mark play and four short quiet windows: not the load
    pc += 3000; L("05:00:31.000", 6000, 7, 3000.0, pc, "0/7/0/0/0/0/0/0/0")
    for i in range(4):
        L("05:00:3%d.000" % (2 + i), 1000, 0, 0.0, pc)
    # the load: miss, zero, miss, zero, miss; then the steady fight
    pc += 6000; L("05:00:40.000", 8000, 10, 6000.0, pc, "5/0/4/1/0/0/0/0/1", 8, 6, 12, 12, 50.0)
    L("05:00:42.500", 2500, 0, 0.0, pc)
    pc += 4000; L("05:00:48.000", 6000, 6, 4000.0, pc, "0/0/6/0/0/0/0/0/0", 4, 2, 8, 8, 30.0)
    L("05:00:50.500", 2500, 0, 0.0, pc)
    pc += 2000; L("05:00:55.000", 4500, 3, 2000.0, pc, "3/0/0/0/0/0/0/0/0", 2, 0, 4, 4, 20.0)
    for i in range(3):
        L("05:01:0%d.000" % i, 5300, 0, 0.0, pc)
    lines.append("09-28 05:02:00.000 I/hakuX-perf( 1): [shd413] f=garbage")
    wins, marks, bad = parse(lines)
    ok = True

    def check(c, msg):
        nonlocal ok
        print(("ok   " if c else "FAIL ") + msg)
        ok = ok and c
    check(len(wins) == 30 and bad == 1, "30 windows, 1 unparsed")
    check(not score(wins, marks, bad, "cleared: apk a -> b", 14800.0)["M0"],
          "M0 fails with an unparsed line")
    wins, marks, bad = parse(lines[:-1])
    r = score(wins, marks, bad, "cleared: apk a -> b", 14800.0)
    check(r["M0"], "M0 passes on a cold, clean, monotonic run")
    check(r["load"] is not None and len(r["load"]) == 5 and r["load"][0]["hms"] == "05:00:40.000",
          "the load is the 5 windows from 05:00:40, not the menu miss before them")
    check(r["load_dpc_ms"] == 12000.0, "load dpc_ms 12000")
    # own excess: miss windows 8000+6000+4500 = 18500 - 3 * median(2500, 2500) = 11000
    check(r["own_excess_ms"] == 11000.0, "own excess 18500 - 3 x 2500 = 11000")
    check(r["C1"] is True, "C1: 12000 is within 20% of 14800 (0.81)")
    check(r["C1own"] is True, "C1': 12000 within 20% of 11000")
    check(r["C2"] is True, "C2: glslang 100 ms <= 5% of 12000")
    check(r["load_kd"] == [8, 0, 10, 1, 0, 0, 0, 0, 1], "C4 sums per class over the load")
    check(r["stage_reused"] == 14 and r["stage_reused_miss"] == 8, "C3 counts over the run")
    check(abs(r["C3_share"] - 8 / 14) < 1e-9 and r["C3"].startswith(">=50%"), "C3 share 57% reads >= 50%")
    check(r["reused_ms_each"] == 10.0 and r["new_ms_each"] == 100.0, "ms per reused / new stage")
    r2 = score(wins, marks, bad, "kept: same apk", 14800.0)
    check(not r2["M0"], "M0 fails on a kept cache")
    r3 = score(wins, marks, bad, "cleared: x", 20000.0)
    check(r3["C1"] is False, "C1 fails at 12000 vs 20000 (0.60)")
    r4 = score(wins, [], bad, "cleared: x", 14800.0)
    check(r4["load"] is None and "C1" not in r4, "no mark play: the load legs are void, not scored")
    k = next(i for i, x in enumerate(lines) if "05:00:42.500" in x)
    bad_mono = parse(lines[:k] + [lines[k].replace("pc_ms=9000.0", "pc_ms=1.0")] + lines[k + 1:-1])
    check(not score(*bad_mono, "cleared: x", 14800.0)["monotonic"], "a decreasing pc_ms is caught")
    print("selftest %s" % ("PASSED" if ok else "FAILED"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main() or 0)
