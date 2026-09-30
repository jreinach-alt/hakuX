#!/usr/bin/env python3
"""#569 P3: score a two-launch pre-build soak pair against
docs/testing/predictions/shaderprebuild569-<title>-soak.json.

    pbjudge.py --l1 <result dir> --l2 <result dir> --boot-mark booted
               [--load-mark play]
    pbjudge.py --selftest

L1 and L2 are two --perflog title soaks of ONE ref on the Nova, queued back to
back, both with --env HAKUX_PLC_WIPE=1. L1 is the apk's first run, so the
dispatcher cleared every shader cache before it (cold: the title's pipeline
records are written). L2 is the same apk's next run: the dispatcher keeps
spv_cache/ and the key files, the app removes vk_pipeline_cache.bin
(HAKUX_PLC_WIPE=1), so any pipeline L2 finds in the driver's cache was put
there by the pre-build in that same launch.

Read per launch (gpljudge.py's readings, plus):
  cleared/kept  result.json shader_cache
  wipe          the `[pb569] HAKUX_PLC_WIPE=1: vk_pipeline_cache.bin X` line
  start         the `[pb569] start` fields (records, jobs, unresolved)
  done_t        the time of the `[pb569] done` line, and its fields
  recs          every `[pb569] rec known|new us=N` line: one per draw-path
                pipeline create, known = in the title's records at launch
  boot_t        the first `mark <boot-mark>` line
  after_boot    the rec lines after boot_t: count and mean us, per kind
  pre_gfps      median gfps= from the first gfps line to boot_t
  pc_ms         the last [shd413] line's running draw-path create ms
  load_dpc_ms   the first load after `mark <load-mark>` (gpljudge.first_load)

Legs, factors in FACTORS, all fixed before any run:
  V   validity: L1 cleared, L2 kept; L2's wipe line says removed; L1's start
      has records=0; L2's start has records >= min_records and unresolved
      <= max_unresolved x records; >= min_lines [shd413] windows each; both
      have the boot mark; L2 has >= min_known known recs after it; L1 has
      >= min_known new recs after it. Anything else is VOID, not a verdict.
  W4  the falsifier: L2's mean known create us after the boot mark
      <= w4_max x L1's mean new create us after it. A known pipeline the
      pre-build built is a driver-cache hit; one it did not reach, or built
      under a different cache key, costs what L1 paid.
  W1  whole run: L2 pc_ms <= w1_max x L1 pc_ms (includes pipelines L2 met
      that L1 never did: the route is not deterministic). With --load-mark,
      also W1b: L2's first load after it, load_dpc_ms <= w1_max x L1's.
  W2  L2's `[pb569] done` comes before its boot mark.
  W3  L2's pre_gfps >= w3_min x L1's (the pre-build must not slow the boot).
  X   readings: L2's done fields, new recs after the boot mark and their ms,
      both launches' [plc569] saves, stall windows (dpc_ms >= 100).
"""
import argparse
import json
import os
import re
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "gpl569"))
import gpljudge  # noqa: E402

KV = re.compile(r"(\w+)=(\S+)")
REC = re.compile(r"\[pb569\] rec (known|new) us=(-?\d+)")
WIPE = re.compile(r"\[pb569\] HAKUX_PLC_WIPE=1: vk_pipeline_cache\.bin (\w+)")
SAVE = re.compile(r"\[plc569\] save=(\w+)")
STALL_MS = 100.0
FACTORS = {"min_lines": 20, "min_records": 20, "max_unresolved": 0.10,
           "min_known": 20, "w4_max": 0.10, "w1_max": 0.25, "w3_min": 0.90}


def score(lines, shader_cache, boot_mark, load_mark):
    r = gpljudge.score_arm(lines, shader_cache)
    r["kept"] = isinstance(shader_cache, str) and shader_cache.startswith("kept")
    a = gpljudge.parse(lines)
    boot = [t for t, n in a["marks"] if n == boot_mark]
    r["boot_t"] = boot[0] if boot else None
    if load_mark:
        r.pop("load_dpc_ms", None)
        load = [t for t, n in a["marks"] if n == load_mark]
        if load and a["wins"]:
            ld = gpljudge.first_load(a["wins"], load[0])
            if ld:
                r["load_dpc_ms"] = sum(w["dpc_ms"] for w in ld)
                r["load_dpm"] = sum(w["dpm"] for w in ld)
    r["stalls"] = sum(1 for w in a["wins"] if w["dpc_ms"] >= STALL_MS)
    r["wipe"], r["start"], r["done"], r["done_t"] = None, None, None, None
    recs, saves = [], {}
    day, last = 0.0, None
    for line in lines:
        t = gpljudge.secs(line)
        if t is None:
            continue
        if last is not None and t + day < last - 43200:
            day += 86400
        t += day
        last = t
        m = REC.search(line)
        if m:
            recs.append((t, m.group(1), int(m.group(2))))
            continue
        m = WIPE.search(line)
        if m:
            r["wipe"] = m.group(1)
            continue
        m = SAVE.search(line)
        if m:
            saves[m.group(1)] = saves.get(m.group(1), 0) + 1
            continue
        i = line.find("[pb569] start")
        if i >= 0:
            r["start"] = dict(KV.findall(line[i:]))
            continue
        i = line.find("[pb569] done")
        if i >= 0 and r["done_t"] is None:
            r["done"] = dict(KV.findall(line[i:]))
            r["done_t"] = t
    r["saves"] = saves
    r["recs"] = len(recs)
    for kind in ("known", "new"):
        us = [u for t, k, u in recs
              if k == kind and r["boot_t"] is not None and t > r["boot_t"]]
        r[kind + "_after_boot"] = len(us)
        r[kind + "_after_boot_ms"] = sum(us) / 1000.0
        r[kind + "_after_boot_mean_us"] = statistics.mean(us) if us else None
    g = [v for t, v in a["gfps"] if r["boot_t"] is not None and t <= r["boot_t"]]
    r["pre_gfps"] = statistics.median(g) if g else None
    r["pre_gfps_n"] = len(g)
    return r


def ival(d, k):
    try:
        return int((d or {}).get(k, ""))
    except ValueError:
        return None


def verdicts(L1, L2, f, load_mark):
    v = {}
    s1, s2 = L1.get("start") or {}, L2.get("start") or {}
    rec2 = ival(s2, "records") or 0
    unres2 = ival(s2, "unresolved")
    v["V"] = bool(
        L1.get("cleared") and L2.get("kept") and L2.get("wipe") == "removed" and
        ival(s1, "records") == 0 and rec2 >= f["min_records"] and
        unres2 is not None and unres2 <= f["max_unresolved"] * rec2 and
        L1.get("lines", 0) >= f["min_lines"] and
        L2.get("lines", 0) >= f["min_lines"] and
        L1.get("boot_t") is not None and L2.get("boot_t") is not None and
        L2.get("known_after_boot", 0) >= f["min_known"] and
        L1.get("new_after_boot", 0) >= f["min_known"])
    r4 = gpljudge.ratio(L2.get("known_after_boot_mean_us"),
                        L1.get("new_after_boot_mean_us"))
    v["W4_ratio"], v["W4"] = r4, r4 is not None and r4 <= f["w4_max"]
    r1 = gpljudge.ratio(L2.get("pc_ms"), L1.get("pc_ms"))
    v["W1_ratio"], v["W1"] = r1, r1 is not None and r1 <= f["w1_max"]
    if load_mark:
        rb = gpljudge.ratio(L2.get("load_dpc_ms"), L1.get("load_dpc_ms"))
        v["W1b_ratio"], v["W1b"] = rb, rb is not None and rb <= f["w1_max"]
    v["W2_done_minus_boot_s"] = (
        None if L2.get("done_t") is None or L2.get("boot_t") is None
        else L2["done_t"] - L2["boot_t"])
    v["W2"] = (v["W2_done_minus_boot_s"] is not None and
               v["W2_done_minus_boot_s"] <= 0)
    r3 = gpljudge.ratio(L2.get("pre_gfps"), L1.get("pre_gfps"))
    v["W3_ratio"], v["W3"] = r3, r3 is not None and r3 >= f["w3_min"]
    v["X"] = {"done": L2.get("done"), "new_after_boot": L2.get("new_after_boot"),
              "new_after_boot_ms": L2.get("new_after_boot_ms"),
              "saves_l1": L1.get("saves"), "saves_l2": L2.get("saves"),
              "stalls_l1": L1.get("stalls"), "stalls_l2": L2.get("stalls")}
    return v


def selftest():
    def launch(start_records, recs, dpcs, pre_gfps, done_s=None, wipe="removed",
               boot_s=64):
        L = []
        if wipe:
            L.append("09-30 10:00:00.500 I/hakuX-perf( 1): [pb569] "
                     "HAKUX_PLC_WIPE=1: vk_pipeline_cache.bin %s\n" % wipe)
        L.append("09-30 10:00:01.000 I/hakuX-perf( 1): [pb569] start "
                 "title=54430006 records=%d jobs=%d unresolved=0 modules=9 "
                 "workers=3 pb_workers=3 enabled=1 setup_ms=20.0\n"
                 % (start_records, start_records))
        if done_s is not None:
            L.append("09-30 10:00:%02d.000 I/hakuX-perf( 1): [pb569] done "
                     "title=54430006 jobs=%d ok=%d fail=0 met=0 create_ms=9000.0 "
                     "wall_ms=%d.0\n" % (done_s, start_records, start_records,
                                         done_s * 1000))
        for s in range(2, boot_s, 2):
            L.append("09-30 10:%02d:%02d.000 I/hakuX-perf( 1): gfps=%d G:1\n"
                     % (s // 60, s % 60, pre_gfps))
        L.append("09-30 10:01:%02d.000 I/hakuX-route( 1): mark booted\n"
                 % (boot_s - 60))
        L.append("09-30 10:01:%02d.500 I/hakuX-route( 1): mark play\n"
                 % (boot_s - 60))
        t = boot_s + 1
        for kind, us in recs:
            L.append("09-30 10:%02d:%02d.000 I/hakuX-perf( 1): [pb569] rec %s "
                     "us=%d known=0 known_ms=0.0 new=0 new_ms=0.0\n"
                     % (t // 60, t % 60, kind, us))
            t += 1
        pc = 0.0
        for i, d in enumerate(dpcs):
            pc += d
            L.append("09-30 10:%02d:%02d.000 I/hakuX-perf( 1): [shd413] f=%d "
                     "dt_ms=1000 ph=0 pm=%d dph=0 dpm=%d pc_ms=%.1f dpc_ms=%.1f\n"
                     % (t // 60, t % 60, i, i, 1 if d else 0, pc, d))
            t += 1
        L.append("09-30 10:%02d:%02d.000 I/hakuX-perf( 1): [plc569] save=quiet "
                 "n=1 ms=40.0\n" % (t // 60, t % 60))
        return L

    cold_recs = [("new", 177000)] * 40
    cold_dpc = [0, 600, 500, 0, 700, 0, 0, 0, 800] + [0] * 20
    L1 = score(launch(0, cold_recs, cold_dpc, 59), "cleared: a -> b",
               "booted", "play")
    warm_recs = [("known", 300)] * 38 + [("new", 170000)] * 2
    L2 = score(launch(150, warm_recs, [0, 60, 5, 0, 20, 0, 0, 0, 30] + [0] * 20,
                      58, done_s=30), "kept: same apk", "booted", "play")
    v = verdicts(L1, L2, FACTORS, "play")
    assert v["V"] and v["W4"] and v["W1"] and v["W1b"] and v["W2"] and v["W3"], v
    assert L2["known_after_boot"] == 38 and L2["new_after_boot"] == 2, L2

    # the other side of each threshold
    bad_recs = [("known", 150000)] * 38 + [("new", 170000)] * 2
    L2b = score(launch(150, bad_recs, cold_dpc, 50, done_s=70), "kept: same apk",
                "booted", "play")
    v = verdicts(L1, L2b, FACTORS, "play")
    assert v["V"] and not v["W4"] and not v["W1"] and not v["W1b"], v
    assert not v["W2"] and not v["W3"], v
    # VOID: L2 cleared (another apk ran between), no wipe, too few known
    for bad in (dict(sc="cleared: x -> y"), dict(wipe="absent"),
                dict(recs=[("known", 300)] * 5)):
        L2v = score(launch(150, bad.get("recs", warm_recs), cold_dpc, 58,
                           done_s=30, wipe=bad.get("wipe", "removed")),
                    bad.get("sc", "kept: same apk"), "booted", "play")
        assert not verdicts(L1, L2v, FACTORS, "play")["V"], bad
    # L1 must be cold with no records
    L1w = score(launch(12, cold_recs, cold_dpc, 59), "cleared: a -> b",
                "booted", "play")
    assert not verdicts(L1w, L2, FACTORS, "play")["V"]
    print("selftest ok")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--l1")
    ap.add_argument("--l2")
    ap.add_argument("--boot-mark", default="booted")
    ap.add_argument("--load-mark", default=None)
    ap.add_argument("--selftest", action="store_true")
    o = ap.parse_args()
    if o.selftest:
        selftest()
        return
    L1 = score(*gpljudge.load_dir(o.l1), o.boot_mark, o.load_mark)
    L2 = score(*gpljudge.load_dir(o.l2), o.boot_mark, o.load_mark)
    print(json.dumps({"L1": L1, "L2": L2, "factors": FACTORS,
                      "verdicts": verdicts(L1, L2, FACTORS, o.load_mark)},
                     indent=1, default=str))


if __name__ == "__main__":
    main()
