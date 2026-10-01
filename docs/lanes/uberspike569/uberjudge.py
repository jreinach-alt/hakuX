#!/usr/bin/env python3
"""#569 uber ladder: score the DOA soaks against
docs/testing/predictions/uberspike569-gpl-doa-soak.json.

    uberjudge.py --a <A dir> --b <B dir> [--h <H dir>]
    uberjudge.py --selftest

A is HAKUX_GPL=0 (the monolithic path), B is HAKUX_GPL=3 (the ladder), H is
HAKUX_GPL=4 (every covered draw held on the uber vertex stage). Each is one
dispatcher result dir of a --perflog title soak. The per-arm readings are
gpl569's (docs/lanes/gpl569/gpljudge.py: cleared, [shd413] pc_ms and pm, the
first load after `mark play`, the play-span median GPU Tot ms and gfps), plus:

  uber_init   the first `vsh-uber: family module` line (the stage compiled)
  last_uber   the last [uber569] line (links, cold, libs, next, uncovered)
  stalls      [shd413] windows whose dpc_ms (draw-path create time within
              the window) is >= STALL_MS: a window in which the draw thread
              waited that long on creates, i.e. frames did not flip for it
  stall_ms    their summed dpc_ms

Legs, factors in FACTORS, all fixed before any run:
  M0  validity: A and B cold; >= min_lines [shd413] windows each; B has the
      family-module line and a last [uber569] line with mode=3 and links > 0;
      H (when given) mode=4 and links > 0
  N1  whole run: B's pc_ms <= n1_max x A's (pc_ms, not per miss: under GPL
      pm counts library and link creates, gpl569)
  N2  the first load after `mark play`: B's dpc_ms <= n2_max x A's
  N3  B's stall windows <= its uber cold count + n3_slack (each cold miss is
      one monolithic create on the draw thread, by design; any other stall
      window is a create the ladder should have taken off the draw path)
  G   H's play-span median GPU Tot ms <= g_max x A's, and H's gfps >= g_fps x
      A's: the uber stage's GPU price while it stands in
  X   (reading) B's swaps (next=../../swapped) and next_ms: the specialised
      pipelines built behind the uber link
"""
import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "gpl569"))
import gpljudge  # noqa: E402

KV = re.compile(r"(\w+)=(\S+)")
STALL_MS = 100.0
FACTORS = {"min_lines": 20, "n1_max": 0.25, "n2_max": 0.20, "n3_slack": 2,
           "g_max": 1.50, "g_fps": 0.80}


def uber_read(lines):
    r = {"uber_init": None, "last_uber": None}
    for line in lines:
        if "vsh-uber: family module" in line and r["uber_init"] is None:
            r["uber_init"] = line.strip()
        i = line.find("[uber569]")
        if i >= 0:
            r["last_uber"] = dict(KV.findall(line[i:]))
    return r


def stalls(lines):
    a = gpljudge.parse(lines)
    w = [x for x in a["wins"] if x["dpc_ms"] >= STALL_MS]
    return len(w), sum(x["dpc_ms"] for x in w)


def score(lines, sc):
    r = gpljudge.score_arm(lines, sc)
    r.update(uber_read(lines))
    r["stalls"], r["stall_ms"] = stalls(lines)
    return r


def ival(d, k):
    try:
        return int((d or {}).get(k, ""))
    except ValueError:
        return None


def verdicts(A, B, H, f):
    v = {}
    lb = B.get("last_uber") or {}
    v["M0"] = bool(A.get("cleared") and B.get("cleared") and
                   A.get("lines", 0) >= f["min_lines"] and
                   B.get("lines", 0) >= f["min_lines"] and B.get("uber_init") and
                   lb.get("mode") == "3" and (ival(lb, "links") or 0) > 0)
    if H is not None:
        lh = H.get("last_uber") or {}
        v["M0_H"] = bool(H.get("uber_init") and lh.get("mode") == "4" and
                         (ival(lh, "links") or 0) > 0)
    r1 = gpljudge.ratio(B.get("pc_ms"), A.get("pc_ms"))
    v["N1_ratio"], v["N1"] = r1, r1 is not None and r1 <= f["n1_max"]
    r2 = gpljudge.ratio(B.get("load_dpc_ms"), A.get("load_dpc_ms"))
    v["N2_ratio"], v["N2"] = r2, r2 is not None and r2 <= f["n2_max"]
    cold = ival(lb, "cold")
    v["N3_stalls"], v["N3_cold"] = B.get("stalls"), cold
    v["N3"] = cold is not None and B.get("stalls", 1 << 30) <= cold + f["n3_slack"]
    if H is not None:
        rg = gpljudge.ratio(H.get("play_gpu_ms"), A.get("play_gpu_ms"))
        rf = gpljudge.ratio(H.get("play_gfps"), A.get("play_gfps"))
        v["G_gpu_ratio"], v["G_gfps_ratio"] = rg, rf
        v["G"] = (rg is not None and rg <= f["g_max"] and
                  rf is not None and rf >= f["g_fps"])
    v["X_next"], v["X_next_ms"] = lb.get("next"), lb.get("next_ms")
    return v


def selftest():
    def arm(mode, pc, dpcs, gpu, gfps, uber=None):
        L = ["09-28 10:00:10.000 I/hakuX-route( 1): mark play\n"]
        t = 20
        for i, d in enumerate(dpcs):
            L.append("09-28 10:00:%02d.000 I/hakuX-perf( 1): [shd413] f=%d dt_ms=1000 "
                     "ph=0 pm=%d dph=0 dpm=%d pc_ms=%.1f dpc_ms=%.1f\n"
                     % (t, i, 9, 1 if d else 0, pc, d))
            t += 1
        for s in range(75, 90, 5):
            L.append("09-28 10:01:%02d.000 I/xemu-gpu( 1): GPU: Tot:%.1f Rnd:1 Xfr:1 RP:3\n"
                     % (s - 60, gpu))
            L.append("09-28 10:01:%02d.000 I/hakuX-perf( 1): gfps=%d G:1\n" % (s - 60, gfps))
        if uber:
            L.insert(0, "09-28 10:00:01.000 I/hakuX-perf( 1): vsh-uber: family module 1: "
                        "50000 bytes GLSL, 40.0 ms\n")
            L.append("09-28 10:01:59.000 I/hakuX-perf( 1): [uber569] mode=%d links=%d "
                     "cold=%d libs=2 lib_fail=0 lib_ms=2400.0 next=%s next_ms=9.0 "
                     "uncovered=0 queued=0\n" % uber)
        return L
    A = score(arm(0, 50000.0, [0, 600, 500, 0, 700, 0, 0, 0, 800, 0] + [0] * 12,
                  10.0, 30), "cleared: a")
    B = score(arm(3, 3000.0, [0, 150, 20, 0, 12, 0, 0, 0, 15, 0] + [0] * 12,
                  10.2, 30, uber=(3, 40, 1, "40/0/40")), "cleared: b")
    H = score(arm(4, 9000.0, [0, 900, 20] + [0] * 19, 13.0, 27,
                  uber=(4, 50, 0, "0/0/0")), "kept")
    assert A["stalls"] == 4 and B["stalls"] == 1, (A["stalls"], B["stalls"])
    v = verdicts(A, B, H, FACTORS)
    assert v["M0"] and v["M0_H"] and v["N1"] and v["N2"] and v["N3"] and v["G"], v
    # the other side of each threshold
    Bbad = score(arm(3, 20000.0, [0, 600, 500, 0, 700, 0, 0, 0, 400, 0] + [0] * 12,
                     10.2, 30, uber=(3, 40, 1, "40/0/40")), "cleared: b")
    v = verdicts(A, Bbad, None, FACTORS)
    assert not v["N1"] and not v["N2"] and not v["N3"], v
    Hslow = score(arm(4, 9000.0, [0] * 22, 16.0, 30, uber=(4, 50, 0, "0/0/0")), "kept")
    assert not verdicts(A, B, Hslow, FACTORS)["G"]
    Boff = score(arm(0, 3000.0, [0] * 22, 10.0, 30), "cleared: b")
    assert not verdicts(A, Boff, None, FACTORS)["M0"]
    print("selftest ok")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--a")
    ap.add_argument("--b")
    ap.add_argument("--h")
    ap.add_argument("--selftest", action="store_true")
    o = ap.parse_args()
    if o.selftest:
        selftest()
        return
    A = score(*gpljudge.load_dir(o.a))
    B = score(*gpljudge.load_dir(o.b))
    H = score(*gpljudge.load_dir(o.h)) if o.h else None
    print(json.dumps({"A": A, "B": B, "H": H, "factors": FACTORS,
                      "verdicts": verdicts(A, B, H, FACTORS)}, indent=1, default=str))


if __name__ == "__main__":
    main()
