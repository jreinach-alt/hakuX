#!/usr/bin/env python3
"""#569 ubershader-by-default confirmation soaks: score the cold first-launch
pairs against docs/testing/predictions/uberdefault569-soaks.json.

    judge.py --pair TITLE A_DIR B_DIR [--pair ...] [--json OUT]
    judge.py --selftest

A is the ubershader off (HAKUX_GPL=0), B is on (the build's default, 3).
Every arm is a cold first launch: HAKUX_PREBUILD=0 and HAKUX_PLC_WIPE=1, or
(for the two A arms taken from runs already on disk) the title's first play
on the device after the dispatcher cleared the shader cache.

Readings per arm, all from the dispatcher's result dir:
  gpl         the `[gpl569] ext=...` line: requested and mode
  cold        `[pb569] start` pre-built nothing (enabled=0, records=0 or
              jobs=0) AND no pipeline cache file came in (the HAKUX_PLC_WIPE
              line says removed or absent, or result.json's shader_cache
              says cleared)
  uber        the last `[uber569]` line (links, cold, next, uncovered)
  hang/crash  verdict.json's own `hang` and `crash`
  gameplay    verdict.json `reached_gameplay`
  fps_ok      verdict.json `fps_ok_share` (share of scored time at >= 30 fps)
  dpc_ms      summed `[shd413]` dpc_ms over the whole run: time the draw path
              spent creating pipelines
  stalls      `[shd413]` windows with dpc_ms >= STALL_MS
  h120        hitch_report.find_hitches over the first 120 s after the
              route's `mark gameplay`; `h120_shader` counts the hitches it
              classes shader or both

Legs, factors in FACTORS, fixed before any run:
  V   validity, per pair: B requested=3 mode=3 and uber links > 0; A mode=0;
      both cold. A pair that fails V is VOID and scores no other leg.
  H   no freeze, per B arm: no hang, no crash, and reached gameplay if A
      did (doa3's route has never been played on the Nova).
  S1  per pair: B dpc_ms <= s1_max x A dpc_ms.
  S2  summed over valid pairs: B's h120_shader < A's; and per pair B's
      h120_shader <= A's + s2_slack.
  F   per pair not listed in NO_FPS: B fps_ok >= A fps_ok - f_band.
"""
import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "testing"))
import hitch_report as hr  # noqa: E402
import title_verdict as tv  # noqa: E402

KV = re.compile(r"(\w+)=(\S+)")
STALL_MS = 100.0
MARK = "gameplay"
FACTORS = {"s1_max": 0.50, "s2_slack": 1, "f_band": 0.10}
# Tron's A arm hung (#672 run 6), so its fps share is not a reading.
NO_FPS = {"tron"}


def fnum(s):
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


def read_lines(lines, verdict, shader_cache=None):
    r = {"shader_cache": shader_cache, "gpl": None, "cold": None, "uber": None, "dpc_ms": 0.0, "stalls": 0,
         "wipe": None, "pb_start": None}
    for _t, _lv, _tag, msg in lines:
        if "[gpl569] ext=" in msg and r["gpl"] is None:
            r["gpl"] = dict(KV.findall(msg[msg.find("[gpl569]"):]))
        elif "[pb569] start" in msg and r["pb_start"] is None:
            r["pb_start"] = dict(KV.findall(msg[msg.find("[pb569]"):]))
        elif "[pb569] HAKUX_PLC_WIPE=1" in msg and r["wipe"] is None:
            r["wipe"] = msg.split("vk_pipeline_cache.bin", 1)[-1].strip()
        elif "[uber569] mode=" in msg:
            r["uber"] = dict(KV.findall(msg[msg.find("[uber569]"):]))
        elif "[shd413]" in msg:
            d = fnum(dict(KV.findall(msg[msg.find("[shd413]"):])).get("dpc_ms")) or 0.0
            r["dpc_ms"] += d
            if d >= STALL_MS:
                r["stalls"] += 1
    pb = r["pb_start"] or {}
    # Nothing pre-built, and no pipeline cache file carried in.
    r["cold"] = bool((pb.get("enabled") == "0" or pb.get("records") == "0" or
                      pb.get("jobs") == "0") and
                     (r["wipe"] in ("removed", "absent") or
                      str(shader_cache or "").startswith("cleared")))
    r["dpc_ms"] = round(r["dpc_ms"], 1)
    marks = [t for t, _lv, tag, msg in lines
             if tag == "hakuX-route" and msg.strip() == "mark " + MARK]
    ends = [t for t, _lv, tag, msg in lines
            if tag == "hakuX-route" and msg.strip() == "soak end"]
    end_t = ends[-1] if ends else (lines[-1][0] if lines else None)
    r["h120"] = r["h120_shader"] = r["h120_worst_ms"] = None
    if marks and end_t is not None:
        hs = [h for h in hr.find_hitches(lines, marks[0], end_t) if h["off_s"] < 120.0]
        r["h120"] = len(hs)
        r["h120_shader"] = sum(1 for h in hs if h["class"] in ("shader", "both"))
        r["h120_worst_ms"] = round(max((h["max_ms"] for h in hs), default=0.0), 1)
    v = verdict or {}
    for k in ("hang", "crash", "reached_gameplay", "fps_ok_share", "fps_window_median"):
        r[k] = v.get(k)
    return r


def load(rdir, name):
    try:
        return json.load(open(os.path.join(rdir, name)))
    except (OSError, ValueError):
        return None


def read_dir(rdir):
    lines, _gaps, _open = tv.parse_logcat(os.path.join(rdir, "logcat.txt"))
    r = read_lines(lines, load(rdir, "verdict.json"),
                   (load(rdir, "result.json") or {}).get("shader_cache"))
    r["dir"] = os.path.basename(rdir.rstrip("/"))
    return r


def legs(pairs, f=FACTORS):
    """pairs: [(title, A reading, B reading)] -> verdict dict."""
    out = {"pairs": {}, "H": True, "S1": True, "F": True}
    sa = sb = 0
    nvalid = 0
    for title, A, B in pairs:
        p = {}
        ga, gb, ub = A["gpl"] or {}, B["gpl"] or {}, B["uber"] or {}
        p["V"] = bool(gb.get("requested") == "3" and gb.get("mode") == "3" and
                      (fnum(ub.get("links")) or 0) > 0 and ga.get("mode") == "0" and
                      A["cold"] and B["cold"])
        p["H"] = bool(not B["hang"] and not B["crash"] and
                      (B["reached_gameplay"] or not A["reached_gameplay"]))
        out["H"] = out["H"] and p["H"]
        if not p["V"]:
            out["pairs"][title] = p
            continue
        nvalid += 1
        r1 = B["dpc_ms"] / A["dpc_ms"] if A["dpc_ms"] else None
        p["S1_ratio"] = None if r1 is None else round(r1, 4)
        p["S1"] = r1 is not None and r1 <= f["s1_max"]
        out["S1"] = out["S1"] and p["S1"]
        if A["h120_shader"] is not None and B["h120_shader"] is not None:
            sa += A["h120_shader"]
            sb += B["h120_shader"]
            p["S2_pair"] = B["h120_shader"] <= A["h120_shader"] + f["s2_slack"]
        else:
            p["S2_pair"] = None
        if title.lower().split()[0] in NO_FPS:
            p["F"] = None
        elif A["fps_ok_share"] is None or B["fps_ok_share"] is None:
            p["F"] = False
        else:
            p["F"] = B["fps_ok_share"] >= A["fps_ok_share"] - f["f_band"]
        if p["F"] is False:
            out["F"] = False
        out["pairs"][title] = p
    out["valid_pairs"] = nvalid
    out["S2_sum"] = {"A": sa, "B": sb}
    out["S2"] = bool(nvalid and sb < sa and
                     all(p.get("S2_pair") is not False for p in out["pairs"].values()))
    if not nvalid:
        out["S1"] = out["F"] = False
    return out


def selftest():
    def arm(gpl, dpcs, hitch_ms, uber=None, cold=True, hang=False, fps=0.7):
        L = ["10-02 18:00:00.000 I/hakuX-build( 1): [gpl569] ext=1 lib=1 fast=1 "
             "interp=1 requested=%d mode=%d" % (gpl, gpl),
             "10-02 18:00:00.200 I/hakuX-perf( 1): [pb569] start title=1 records=9 "
             "jobs=%d enabled=%d" % ((0, 0) if cold else (9, 1)),
             "10-02 18:00:10.000 I/hakuX-route( 1): mark gameplay"]
        if cold:
            L.insert(1, "10-02 18:00:00.100 I/hakuX-perf( 1): [pb569] HAKUX_PLC_WIPE=1: "
                        "vk_pipeline_cache.bin removed")
        for i, (d, h) in enumerate(zip(dpcs, hitch_ms)):
            s = 11 + i
            L.append("10-02 18:00:%02d.000 I/hakuX-pace( 1): f=%d v0=1 v1=0 v2=1 v3=0 "
                     "v4=0 vb=60 max=%.1f ms=1000.0" % (s, 60 * (i + 1), h))
            L.append("10-02 18:00:%02d.000 I/hakuX-perf( 1): [shd413] f=%d dsm=%d "
                     "dpc_ms=%.1f dpn=0 dfb=0 dfbh=0 dfb_ms=0.0 dvs_ms=0.0 dgs_ms=0.0 "
                     "dfs_ms=%.1f"
                     % (s, 60 * (i + 1), 3 if d else 0, d, d))
        if uber:
            L.append("10-02 18:01:00.000 I/hakuX-perf( 1): [uber569] mode=3 links=%d "
                     "cold=2 libs=3 next=1/0/1 uncovered=0" % uber)
        L.append("10-02 18:01:01.000 I/hakuX-route( 1): soak end")
        lines = []
        for raw in L:
            m = hr.LINE.match(raw)
            lines.append((hr.ts(m.group(1)), m.group(2), m.group(3), m.group(4)))
        return read_lines(lines, {"hang": hang, "crash": False, "reached_gameplay": not hang,
                                  "fps_ok_share": fps})
    A = arm(0, [900.0, 400.0, 0.0], [950.0, 450.0, 20.0])
    B = arm(3, [5.0, 0.0, 0.0], [40.0, 30.0, 20.0], uber=50, fps=0.65)
    assert A["stalls"] == 2 and A["dpc_ms"] == 1300.0 and A["cold"], A
    assert A["h120_shader"] == 2 and B["h120_shader"] == 0, (A, B)
    v = legs([("Kabuki", A, B)])
    assert v["pairs"]["Kabuki"]["V"] and v["H"] and v["S1"] and v["S2"] and v["F"], v
    # the other side of each threshold
    Bbad = arm(3, [800.0, 400.0, 0.0], [950.0, 450.0, 300.0], uber=50, fps=0.5)
    v = legs([("Kabuki", A, Bbad)])
    assert v["pairs"]["Kabuki"]["V"] and not v["S1"] and not v["S2"] and not v["F"], v
    Bhang = arm(3, [5.0], [40.0], uber=50, hang=True)
    assert not legs([("Kabuki", A, Bhang)])["H"]
    # B that never ran the ladder, or a warm arm, is VOID
    assert not legs([("Kabuki", A, arm(0, [5.0], [40.0]))])["pairs"]["Kabuki"]["V"]
    assert not legs([("Kabuki", A, arm(3, [5.0], [40.0], uber=0))])["pairs"]["Kabuki"]["V"]
    Awarm = arm(0, [900.0], [950.0], cold=False)
    assert not Awarm["cold"]
    assert not legs([("Kabuki", Awarm, B)])["pairs"]["Kabuki"]["V"]
    # Tron is not scored on fps
    assert legs([("Tron 2.0", A, Bbad)])["pairs"]["Tron 2.0"]["F"] is None
    print("selftest ok")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pair", nargs=3, action="append", metavar=("TITLE", "A", "B"))
    ap.add_argument("--json")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        selftest()
        return 0
    if not a.pair:
        ap.error("--pair TITLE A_DIR B_DIR, at least once")
    readings = [(t, read_dir(x), read_dir(y)) for t, x, y in a.pair]
    out = {"factors": FACTORS, "readings": {t: {"A": x, "B": y} for t, x, y in readings},
           "legs": legs(readings)}
    s = json.dumps(out, indent=1, default=str)
    if a.json:
        open(a.json, "w").write(s + "\n")
    print(s)
    return 0


if __name__ == "__main__":
    sys.exit(main())
