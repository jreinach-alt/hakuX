#!/usr/bin/env python3
"""#569 uber ladder on Kabuki Warriors: score the cold fight soaks against
docs/testing/predictions/uberspike569-gpl-kabuki-soak.json.

    kabjudge.py --a <A dir> --b <B dir>
    kabjudge.py --selftest

A is HAKUX_GPL=0 (the monolithic path), B is HAKUX_GPL=3 (the ladder). Each is
one dispatcher result dir of a --perflog soak on the kabuki-warriors route.
Every reading is taken after the route's `mark gameplay` (the round start):

  gp_dpc_ms   summed [shd413] dpc_ms: draw-path create time in the fight
  gp_dpm      summed [shd413] dpm: pipeline misses in the fight
  gmax_ms     the largest G max of the gfps lines: the longest gap between
              two guest flips (the `G:avg(min-max)` field, lane.kabukistall's
              ks_windows.py reads the same)
  gaps5       gfps lines whose G max is >= 5000 ms
  stalls      [shd413] windows with dpc_ms >= 100 (uberjudge's STALL_MS)
  last_uber   the last [uber569] line (links, cold, libs, next, uncovered)

Legs, factors in FACTORS, fixed before any run:
  K0  validity: A and B cleared; both reach `mark gameplay`; A's gp_dpm >=
      min_dpm (the fight met cold content, as K1's 678 did); B has the family
      module line and a last [uber569] line with mode=3 and links > 0
  K1  the addendum's acceptance: B has no flip gap over 5 s (gaps5 == 0).
      K1 on master already read 4.4 s at most (kabukistall section 8), so K1
      alone cannot show the ladder did anything; K2 and K3 can
  K2  B's gp_dpc_ms <= k2_max x A's
  K3  B's gmax_ms <= k3_max x A's
"""
import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "gpl569"))
import gpljudge  # noqa: E402
import uberjudge  # noqa: E402

KV = re.compile(r"(\w+)=(\S+)")
GFPS = re.compile(r"gfps=(\d+) G:([\d.]+)\(([\d.]+)-([\d.]+)\)")
MARK = "mark gameplay"
FACTORS = {"min_dpm": 100, "gap_ms": 5000.0, "k2_max": 0.25, "k3_max": 0.50}


def read(lines, shader_cache):
    r = {"cleared": str(shader_cache or "").startswith("cleared"),
         "shader_cache": shader_cache, "mark": False, "gp_dpc_ms": 0.0,
         "gp_dpm": 0, "gmax_ms": None, "gaps5": 0, "stalls": 0, "wins": 0}
    r.update(uber_read_all(lines))
    for line in lines:
        if "hakuX-route" in line and MARK in line:
            r["mark"] = True
            continue
        if not r["mark"]:
            continue
        i = line.find("[shd413]")
        if i >= 0:
            kv = dict(KV.findall(line[i:]))
            d = gpljudge.num(kv.get("dpc_ms", "0")) or 0.0
            r["gp_dpc_ms"] += d
            r["gp_dpm"] += int(gpljudge.num(kv.get("dpm", "0")) or 0)
            r["wins"] += 1
            if d >= uberjudge.STALL_MS:
                r["stalls"] += 1
            continue
        m = GFPS.search(line)
        if m:
            g = float(m.group(4))
            r["gmax_ms"] = g if r["gmax_ms"] is None else max(r["gmax_ms"], g)
            if g >= FACTORS["gap_ms"]:
                r["gaps5"] += 1
    return r


def uber_read_all(lines):
    return uberjudge.uber_read(lines)


def verdicts(A, B, f):
    v = {}
    lb = B.get("last_uber") or {}
    v["K0"] = bool(A["cleared"] and B["cleared"] and A["mark"] and B["mark"] and
                   A["gp_dpm"] >= f["min_dpm"] and B.get("uber_init") and
                   lb.get("mode") == "3" and (uberjudge.ival(lb, "links") or 0) > 0)
    v["K1"] = B["mark"] and B["gmax_ms"] is not None and B["gaps5"] == 0
    r2 = gpljudge.ratio(B["gp_dpc_ms"], A["gp_dpc_ms"])
    v["K2_ratio"], v["K2"] = r2, r2 is not None and r2 <= f["k2_max"]
    r3 = gpljudge.ratio(B["gmax_ms"], A["gmax_ms"])
    v["K3_ratio"], v["K3"] = r3, r3 is not None and r3 <= f["k3_max"]
    v["X_cold"], v["X_uncovered"] = lb.get("cold"), lb.get("uncovered")
    v["X_next"], v["X_stalls_B"] = lb.get("next"), B["stalls"]
    return v


def selftest():
    def arm(dpcs, gmaxes, uber=None, mark=True):
        L = ["09-29 10:00:01.000 I/hakuX-route( 1): mark booted\n"]
        if uber:
            L.append("09-29 10:00:02.000 I/hakuX-perf( 1): vsh-uber: family module 1: "
                     "44646 bytes GLSL, 19.4 ms\n")
        # a pre-mark stall that must not count
        L.append("09-29 10:00:05.000 I/hakuX-perf( 1): [shd413] f=1 dpm=90 dpc_ms=90000.0\n")
        L.append("09-29 10:00:05.000 I/hakuX-perf( 1): gfps=0 G:900(1-9000)\n")
        if mark:
            L.append("09-29 10:00:10.000 I/hakuX-route( 1): mark gameplay\n")
        for i, (d, g) in enumerate(zip(dpcs, gmaxes)):
            L.append("09-29 10:00:%02d.000 I/hakuX-perf( 1): gfps=20 G:50(16-%.0f)\n"
                     % (11 + i, g))
            L.append("09-29 10:00:%02d.000 I/hakuX-perf( 1): [shd413] f=%d dpm=%d "
                     "dpc_ms=%.1f\n" % (11 + i, i, 60 if d else 0, d))
        if uber:
            L.append("09-29 10:01:59.000 I/hakuX-perf( 1): [uber569] mode=%d links=%d "
                     "cold=%d libs=4 next=%s uncovered=0\n" % uber)
        return L
    A = read(arm([20000.0, 60000.0, 0.0], [4300.0, 4400.0, 200.0]), "cleared: a")
    B = read(arm([400.0, 1200.0, 0.0], [600.0, 900.0, 200.0], uber=(3, 300, 5, "300/0/200")),
             "cleared: b")
    assert A["gp_dpm"] == 120 and A["gmax_ms"] == 4400.0 and A["stalls"] == 2, A
    v = verdicts(A, B, FACTORS)
    assert v["K0"] and v["K1"] and v["K2"] and v["K3"], v
    # the other side of each threshold
    Bbad = read(arm([9000.0, 12000.0, 0.0], [5200.0, 3000.0, 200.0],
                    uber=(3, 300, 50, "300/0/200")), "cleared: b")
    v = verdicts(A, Bbad, FACTORS)
    assert v["K0"] and not v["K1"] and not v["K2"] and not v["K3"], v
    Boff = read(arm([400.0], [600.0]), "cleared: b")
    assert not verdicts(A, Boff, FACTORS)["K0"]
    Awarm = read(arm([20000.0, 60000.0], [4300.0, 4400.0]), "kept")
    assert not verdicts(Awarm, B, FACTORS)["K0"]
    Anomark = read(arm([20000.0, 60000.0], [4300.0, 4400.0], mark=False), "cleared: a")
    assert Anomark["gp_dpm"] == 0 and not verdicts(Anomark, B, FACTORS)["K0"]
    print("selftest ok")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--a")
    ap.add_argument("--b")
    ap.add_argument("--selftest", action="store_true")
    o = ap.parse_args()
    if o.selftest:
        selftest()
        return
    A = read(*gpljudge.load_dir(o.a))
    B = read(*gpljudge.load_dir(o.b))
    print(json.dumps({"A": A, "B": B, "factors": FACTORS,
                      "verdicts": verdicts(A, B, FACTORS)}, indent=1, default=str))


if __name__ == "__main__":
    main()
