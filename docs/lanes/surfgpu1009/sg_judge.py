#!/usr/bin/env python3
"""Judge one HAKUX_SURFGPU soak pair against its registered prediction.

    sg_judge.py --expect docs/testing/predictions/surfgpu1009-<t>-soak.json \
                --a <flag-off id> --b <flag-on id> [--floor <older flag-off id>]

Scores the named rules in the prediction's `expect` block, and nothing else:
a rule this script does not know is printed as UNKNOWN and fails the
verdict, so a misspelt leg cannot pass by being skipped. The thresholds live
in the prediction, not here.

Readouts, all restricted to the logcat at or after the route's
`mark gameplay` line:
  - gfps and ph_* from docs/lanes/near30/decompose.py (its `all` row), and its
    THERMAL line;
  - every `[sdcall]` caller's wait, ms per flip, median over windows (a
    window without the caller counts 0), as surfdl1008's
    postmark_sdsurvey.py does; and the SUM over all callers per window, so a
    wait that moved to another caller is still counted;
  - `[surfgpu]` detach= and nodisp= per flip, and `spl=` up/dl/cmpl per flip.
With --floor, route-frame regions (gpunonrender/regioncheck.py) for B vs A
and for A vs the older flag-off run on the same route, the noise floor. The
pixel leg is read by eye from those two tables and the hold frames; this
script prints them and does not score them.

Reads result directories only; writes nothing.
"""
import argparse
import json
import os
import re
import statistics
import subprocess
import sys

D = os.environ.get("DISPATCH_DIR", "/home/justin/hakux-work/dispatch")
HERE = os.path.dirname(os.path.abspath(__file__))
LANES = os.path.dirname(HERE)
TS = re.compile(r'^\d+-\d+ (\d+):(\d+):([\d.]+) ')
CALLER = re.compile(r' (\w+)=fin(\d+)/fence(\d+)/pre(\d+)/dl(\d+)/([\d.]+)ms')


def secs(h, m, s):
    return int(h) * 3600 + int(m) * 60 + float(s)


def med(xs):
    return statistics.median(xs) if xs else 0.0


def read_log(rid):
    p = os.path.join(D, "results", rid, "logcat.txt")
    out = {"on": False, "mark": None, "win": [], "sg": [], "spl": []}
    for line in open(p, errors="replace"):
        if "[surfgpu] on" in line:
            out["on"] = True
        if "hakuX-route" in line and "mark gameplay" in line:
            m = TS.match(line)
            if m:
                out["mark"] = secs(*m.groups())
        if out["mark"] is None:
            continue
        m = TS.match(line)
        if not m or secs(*m.groups()) < out["mark"]:
            continue
        if "[sdcall]" in line:
            fm = re.search(r'frames=(\d+)', line)
            fr = int(fm.group(1)) if fm else 60
            w = {"frames": fr, "callers": {}}
            for name, fin, fence, pre, dl, ms in CALLER.findall(line):
                w["callers"][name] = {"fin": int(fin), "fence": int(fence),
                                      "pre": int(pre), "dl": int(dl),
                                      "ms": float(ms)}
            sm = re.search(r'spl=def(\d+)/up(\d+)/dl(\d+)/(\d+)kB/cmpl(\d+)',
                           line)
            if sm:
                out["spl"].append((fr,) + tuple(int(x) for x in sm.groups()))
            out["win"].append(w)
        elif "[surfgpu] frames=" in line:
            gm = re.search(r'frames=(\d+) detach=(\d+) nodisp=(\d+)', line)
            if gm:
                out["sg"].append(tuple(int(x) for x in gm.groups()))
    return out


def per_frame(log, caller, field="ms"):
    return med([w["callers"].get(caller, {}).get(field, 0) / w["frames"]
                for w in log["win"] if w["frames"]])


def wait_sum(log):
    per = [sum(c["ms"] for c in w["callers"].values()) / w["frames"]
           for w in log["win"] if w["frames"]]
    tot_ms = sum(sum(c["ms"] for c in w["callers"].values())
                 for w in log["win"])
    tot_fr = sum(w["frames"] for w in log["win"])
    return med(per), (tot_ms / tot_fr if tot_fr else 0.0)


def sg_rate(log, i):
    return med([g[i] / g[0] for g in log["sg"] if g[0]])


def decompose(rid):
    p = subprocess.run([sys.executable, os.path.join(LANES, "near30",
                                                     "decompose.py"),
                        os.path.join(D, "results", rid)],
                       capture_output=True, text=True)
    hdr, row, thermal = None, None, ""
    for line in p.stdout.splitlines():
        s = line.split()
        if s and s[0] == "group":
            hdr = s
        elif s and s[0] == "all" and hdr:
            row = dict(zip(hdr, s))
        elif "THERMAL:" in line:
            thermal = line.strip()
    return row or {}, thermal, p.stdout


def result_field(rid, k):
    try:
        return json.load(open(os.path.join(D, "results", rid,
                                           "result.json"))).get(k)
    except OSError:
        return None


def fnum(row, k):
    try:
        return float(row[k])
    except (KeyError, ValueError):
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--expect", required=True)
    ap.add_argument("--a", required=True, help="flag-off run id")
    ap.add_argument("--b", required=True, help="flag-on run id")
    ap.add_argument("--floor", help="an older flag-off run on the same route")
    a_ = ap.parse_args()
    exp = json.load(open(a_.expect))
    rules = exp.get("expect") or {}
    if not rules:
        sys.exit("the prediction's `expect` block is empty: nothing to judge")

    la, lb = read_log(a_.a), read_log(a_.b)
    ra, tha, _ = decompose(a_.a)
    rb, thb, _ = decompose(a_.b)
    sa, sb = wait_sum(la), wait_sum(lb)

    print("prediction %s (registered %s, a_ref %s, b_ref %s)" % (
        a_.expect, exp.get("registered_utc"), exp.get("a_ref", "")[:10],
        exp.get("b_ref", "")[:10]))
    for tag, rid, lg, row, th in (("A", a_.a, la, ra, tha),
                                  ("B", a_.b, lb, rb, thb)):
        print("\n== %s %s  apk %s  shader_cache: %s" % (
            tag, rid, result_field(rid, "apk_sha"),
            result_field(rid, "shader_cache")))
        print("   %s" % (th or "THERMAL: (no line)"))
        print("   [surfgpu] on: %s; post-mark [sdcall] windows %d, "
              "[surfgpu] windows %d" % (lg["on"], len(lg["win"]),
                                        len(lg["sg"])))
        print("   gfps %s  ph_GPU %s  ph_Draw %s  ph_Fin %s  ph_Idle %s  "
              "ph_Tot %s" % tuple(row.get(k, "?") for k in (
                  "fps", "ph_GPU", "ph_Draw", "ph_Fin", "ph_Idle", "ph_Tot")))
        names = sorted({n for w in lg["win"] for n in w["callers"]},
                       key=lambda n: -per_frame(lg, n))
        for n in names:
            print("   %-8s wait %6.2f ms/flip  fin %.2f fence %.2f pre %.2f "
                  "dl %.2f per flip" % (
                      n, per_frame(lg, n), per_frame(lg, n, "fin"),
                      per_frame(lg, n, "fence"), per_frame(lg, n, "pre"),
                      per_frame(lg, n, "dl")))
        s = wait_sum(lg)
        print("   all callers: %.2f ms/flip (median of windows), %.2f "
              "(total ms / total flips)" % s)
        if lg["sg"]:
            print("   [surfgpu] detach %.2f/flip  nodisp %.2f/flip" % (
                sg_rate(lg, 1), sg_rate(lg, 2)))
        if lg["spl"]:
            print("   spl= up %.2f dl %.2f cmpl %.2f per flip" % tuple(
                med([x[i] / x[0] for x in lg["spl"] if x[0]])
                for i in (2, 3, 5)))

    def thermal_paused(th):
        return not th.startswith("THERMAL: no thermal-pause device above 0")

    got = {
        "V1.B_surfgpu_on": lb["on"],
        "V2.A_surfgpu_on": la["on"],
        "V3.postmark_sdcall_windows_min": min(len(la["win"]), len(lb["win"])),
        "V4.thermal_pause": thermal_paused(tha) or thermal_paused(thb),
        "P0.A_reuse_ms_per_frame_min": per_frame(la, "reuse"),
        "P0.A_surfupd_ms_per_frame_min": per_frame(la, "surfupd"),
        "P1.B_reuse_ms_per_frame_max": per_frame(lb, "reuse"),
        "P1.B_detach_per_frame_min": sg_rate(lb, 1),
        "P1.B_surfupd_ms_per_frame_max": per_frame(lb, "surfupd"),
        "P1.B_nodisp_per_frame_min": sg_rate(lb, 2),
        "P2.sdcall_wait_sum_ratio_max": (sb[0] / sa[0]) if sa[0] else None,
        "P3.ph_Fin_drop_ms_min": (
            fnum(ra, "ph_Fin") - fnum(rb, "ph_Fin")
            if fnum(ra, "ph_Fin") is not None and
            fnum(rb, "ph_Fin") is not None else None),
        "P4.gfps_gain_min": (
            fnum(rb, "fps") - fnum(ra, "fps")
            if fnum(ra, "fps") is not None and
            fnum(rb, "fps") is not None else None),
    }

    print("\n== legs (thresholds from the prediction's `expect`)")
    ok = True
    failed = set()
    for k, want in rules.items():
        if k not in got:
            print("   UNKNOWN %-34s registered %r: this judge has no reader "
                  "for it" % (k, want))
            ok = False
            failed.add(k.split(".")[0])
            continue
        v = got[k]
        if v is None:
            res = "NO DATA"
        elif isinstance(want, bool):
            res = "PASS" if bool(v) == want else "FAIL"
        elif k.endswith("_min"):
            res = "PASS" if v >= want else "FAIL"
        elif k.endswith("_max"):
            res = "PASS" if v <= want else "FAIL"
        else:
            res = "UNKNOWN"
        ok = ok and res == "PASS"
        if res != "PASS":
            failed.add(k.split(".")[0])
        vs = ("%.2f" % v) if isinstance(v, float) else str(v)
        print("   %-7s %-34s measured %-8s registered %r" % (res, k, vs, want))
    # The legs' order of reading: a V failure voids the pair, a P0 failure
    # means the scene never reached the wait, and only then is P1-P4 a verdict.
    if any(f.startswith("V") for f in failed):
        verdict = "VOID (a V leg failed: identify why, do not rerun blind)"
    elif "P0" in failed:
        verdict = "NOT SCORED (P0: flag-off did not reproduce the wait)"
    else:
        verdict = "PASS" if ok else "FAIL"
    print("\nVERDICT (scored legs only): %s" % verdict)
    print("Not scored here: the pixel leg (regions below and the hold frames, "
          "by eye), and that the player moves (the hold frames, by eye).")

    if a_.floor:
        rc = os.path.join(LANES, "gpunonrender", "regioncheck.py")
        for x, y, what in ((a_.a, a_.b, "B vs A (the leg)"),
                           (a_.floor, a_.a, "A vs older flag-off run "
                                            "(noise floor)")):
            print("\n== route-frame regions, %s: %s vs %s" % (what, x, y))
            p = subprocess.run([sys.executable, rc, x, y],
                               capture_output=True, text=True)
            sys.stdout.write(p.stdout + p.stderr)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
