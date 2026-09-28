#!/usr/bin/env python3
"""Read #461's Crimson Skies A/B pairs: the figures F4b and its controls name.

    pair461_read.py RUN [RUN...] [--window 90,240]
    pair461_read.py --pair A_RUN B_RUN [--window 90,240]
    pair461_read.py --selftest

RUN is a soak's result directory (logcat.txt, thermal.jsonl, run.log), or a
logcat file with thermal.jsonl and run.log looked for beside it. Every figure
is taken over the window, 90 to 240 s after the first hakuX-perf line unless
--window says otherwise. The logcat is cut by docs/testing/phase_read_split.py's
THE WINDOW. A thermal.jsonl sample is placed by its device time, which is the
clock logcat stamps with.

THE FIGURES, per run:
  gfps   the median of hakuX-perf's gfps (flips counted over each second),
         and n, the lines it is the median of. The line prints every 60
         flips, so n x 60 is about the flips in the window.
  M      the median of hakuX-cpu's M: PGRAPH methods per frame (an EMA)
  Tq     the median of hakuX-perf's Tq: texture dirty-bitmap tests per frame
         (an EMA of check_texture_dirty() calls)
  BUSY   the mean of hakuX-phase's Surf + Draw + Fin, as phase_read_split.py
         defines it. TxH, Idle, Fr and St are the means of those fields.
  late   the share of flips that took 3 or more VBLANKs: v3 + v4 over
         v0 + ... + v4, summed over the window's hakuX-pace lines
  txh    hashed KiB per frame by reason, from tex461_read.py: mk, bit + bov,
         memo, and all reasons; txr's ct and bt per frame
  heat   run.log's COOLDOWN: line, xo-therm at thermal.jsonl's `start`
         sample, and each cooling device's highest cur_state over the samples
         inside the window
  tlb    per flip, summed over the window's `[tlb68]` lines (tag hakuX, one
         every 2 s or so from the vCPU thread, in every build) and divided by
         the flips the window's hakuX-pace lines count:
           rdo    tlb_reset_dirty() calls made on any thread but the vCPU's:
                  each is a dirty-bit clear, such as check_texture_dirty()'s,
                  that re-armed the guest's not-dirty write trap on its pages
           rdous  the microseconds those calls spent walking the TLB
           sd     tlb_set_dirty() calls: guest stores that took the slow path
                  and re-enabled a page

THE LEGS (--pair), registered on #461 at 2026-09-28T09:41:38Z (comment
5867400666), each read against A's own run:
  F4      B's gfps median minus A's is -1 or more. F4 on the first pair, F4b
          on the second, which runs B first.
  K1      thermal parity: every cooling device's highest cur_state in the
          window is the same in both runs. A control: a pair that fails it is
          thermally confounded, and its F4 is not attributed to the fix.
  K2      same scene: the larger M median is within 10% of the smaller.
  P1      B's Tq median is at least A's.
  P2      B's mk KiB per frame is below A's, and its bit + bov above A's.
  R       read only when F4 fails with K1 and K2 passing. B's BUSY - TxH
          more than 2 ms/frame above A's puts the frame on the render thread;
          otherwise the render thread is not where it went.
  V       each run's late share: how a drop shows, not where it came from.
  G       registered on #461 after the rest, before any `[tlb68]` line of
          either pair was read: the guest-side route needs B to clear more
          texture-dirty bits than A. B's rdo per flip above A's leaves the
          route possible, and sd then says how many slow stores it cost; at
          or below A's refutes it as the cause of a drop.

A leg whose inputs are missing reads UNREAD, never PASS.
"""
import argparse
import os
import re
import shutil
import statistics
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "testing"))
sys.path.insert(0, HERE)
import phase_read_split as prs  # noqa: E402
import tex461_read  # noqa: E402
import thermal_state  # noqa: E402

RE_GFPS = re.compile(r"gfps=(\d+)")
RE_TQ = re.compile(r"(?<![A-Za-z])Tq:(-?[\d.]+)")
RE_M = re.compile(r"(?<![A-Za-z])M:(-?[\d.]+)")
RE_PACE = re.compile(r"f=(\d+) v0=(\d+) v1=(\d+) v2=(\d+) v3=(\d+) v4=(\d+) vb=(\d+)")
TLB = ("dt", "rd", "rdo", "rdous", "sd")
RE_TLB = {k: re.compile(r"(?<![A-Za-z])%s=(\d+)" % k) for k in TLB}
XO = "xo-therm"
R_MS = 2.0
K2_RATIO = 1.10


def locate(run):
    """(logcat, thermal.jsonl, run.log) for a result dir or a logcat file."""
    if os.path.isdir(run):
        d, logcat = run, os.path.join(run, "logcat.txt")
    else:
        d, logcat = os.path.dirname(os.path.abspath(run)), run
    return logcat, os.path.join(d, "thermal.jsonl"), os.path.join(d, "run.log")


def median(xs):
    return statistics.median(xs) if xs else None


def mean(xs):
    return statistics.mean(xs) if xs else None


def read_run(run, window):
    logcat, thermal, runlog = locate(run)
    lines = open(logcat, errors="replace").read().splitlines()
    clock = prs.Clock(lines)
    if clock.t0 is None:
        sys.exit("%s: no logcat timestamps, so no window" % logcat)
    win = prs.window_lines(lines, window)
    # the result directory names the run; a bare logcat.txt would not
    r = {"name": os.path.basename(os.path.dirname(os.path.abspath(logcat)))}

    perf = [l for l in win if "hakuX-perf" in l and RE_GFPS.search(l)]
    r["gfps"] = median([int(RE_GFPS.search(l).group(1)) for l in perf])
    r["n"] = len(perf)
    r["Tq"] = median([float(m.group(1)) for l in perf for m in [RE_TQ.search(l)] if m])
    r["M"] = median([float(m.group(1)) for l in win if "hakuX-cpu" in l
                     for m in [RE_M.search(l)] if m])

    v = [0] * 5
    for l in win:
        m = RE_PACE.search(l) if "hakuX-pace" in l else None
        if m:
            v = [a + int(b) for a, b in zip(v, m.groups()[1:6])]
    r["pace"] = v
    r["late"] = (v[3] + v[4]) / float(sum(v)) if sum(v) else None

    tlb = [l for l in win if "[tlb68]" in l]
    r["tlb_n"] = len(tlb)
    got = [{k: RE_TLB[k].search(l) for k in TLB} for l in tlb]
    got = [{k: int(m.group(1)) for k, m in g.items()} for g in got if all(g.values())]
    for k in TLB:
        tot = sum(g[k] for g in got)
        r["tlb_" + k] = tot / float(sum(v)) if got and sum(v) and k != "dt" else None

    rows = prs.parse_lines(win)
    new = [d for d in rows if d["_new"]]
    r["phase_n"] = len(rows)
    for k in ("TxH", "Idle", "Fr", "St"):
        r[k] = mean([d[k] for d in new]) if k == "TxH" else mean([d[k] for d in rows])
    r["BUSY"] = mean([d["Surf"] + d["Draw"] + d["Fin"] for d in rows])
    # Only lines that carry TxH give BUSY - TxH: an older line has no TxH.
    r["busy_less_txh"] = mean([d["Surf"] + d["Draw"] + d["Fin"] - d["TxH"] for d in new])

    groups, _ = tex461_read.parse(win)
    r["txh_groups"] = len(groups)
    if groups:
        frames = 60.0 * len(groups)
        kib = {n: sum(g["txh"][n][1] for g in groups) / frames for n in tex461_read.TXH}
        r["mk"], r["bitbov"], r["memo"] = kib["mk"], kib["bit"] + kib["bov"], kib["memo"]
        r["hashed"] = sum(kib[n] for n in tex461_read.TXH if n not in ("eq", "rep"))
        r["ct"] = sum(g["txr"]["ct"] for g in groups) / frames
        r["bt"] = sum(g["txr"]["bt"] for g in groups) / frames
    else:
        r["mk"] = r["bitbov"] = r["memo"] = r["hashed"] = r["ct"] = r["bt"] = None

    r["cooldown"] = None
    if os.path.isfile(runlog):
        for l in open(runlog, errors="replace"):
            if l.startswith("COOLDOWN:"):
                r["cooldown"] = l.strip()
    recs = thermal_state.load(thermal) if os.path.isfile(thermal) else None
    r["heat"] = None if recs is None else heat(recs, clock, window)
    return r


def heat(recs, clock, window):
    """xo-therm at the `start` sample, and each cooling device's highest
    cur_state over the readable samples inside the window."""
    start = [x for x in recs if x.get("label") == "start" and not x.get("error")]
    h = {"xo_start": thermal_state.zone_c(start[0], XO) if start else None,
         "samples": 0, "unread": 0, "cool": {}}
    for x in recs:
        s = clock.since(x["dev_time"]) if x.get("dev_time") else None
        if s is None or not window[0] <= s <= window[1]:
            continue
        if x.get("error") or not x.get("cool"):
            h["unread"] += 1
            continue
        h["samples"] += 1
        for n, typ, cur, _mx in x["cool"]:
            k = "%s(cd%d)" % (typ, n)
            h["cool"][k] = max(cur, h["cool"].get(k, cur))
    return h


def verdict(ok):
    return "UNREAD" if ok is None else "PASS" if ok else "FAIL"


def legs(a, b):
    """{leg: (PASS/FAIL/UNREAD or a reading, detail)} for the pair."""
    out = {}
    if a["gfps"] is None or b["gfps"] is None:
        out["F4"] = ("UNREAD", "no gfps line in a window")
    else:
        dg = b["gfps"] - a["gfps"]
        out["F4"] = (verdict(dg >= -1), "B %g - A %g = %+g (bar -1)" % (b["gfps"], a["gfps"], dg))

    ha, hb = a["heat"], b["heat"]
    if not ha or not hb or not ha["samples"] or not hb["samples"]:
        out["K1"] = ("UNREAD", "no readable thermal.jsonl sample inside a window")
    elif set(ha["cool"]) != set(hb["cool"]):
        out["K1"] = ("UNREAD", "the runs read different cooling devices: %s" % ", ".join(
            sorted(set(ha["cool"]) ^ set(hb["cool"]))))
    else:
        diff = ["%s A %d / B %d" % (k, ha["cool"][k], hb["cool"][k])
                for k in sorted(ha["cool"]) if ha["cool"][k] != hb["cool"][k]]
        out["K1"] = (verdict(not diff), "; ".join(diff) or "%d devices, every highest cur_state equal"
                     % len(ha["cool"]))

    if a["M"] is None or b["M"] is None or min(a["M"], b["M"]) <= 0:
        out["K2"] = ("UNREAD", "no hakuX-cpu M in a window")
    else:
        q = max(a["M"], b["M"]) / min(a["M"], b["M"])
        out["K2"] = (verdict(q <= K2_RATIO), "M A %.0f / B %.0f, larger over smaller %.3f (bar %.2f)"
                     % (a["M"], b["M"], q, K2_RATIO))

    if a["Tq"] is None or b["Tq"] is None:
        out["P1"] = ("UNREAD", "no Tq in a window")
    else:
        out["P1"] = (verdict(b["Tq"] >= a["Tq"]), "Tq A %.0f / B %.0f" % (a["Tq"], b["Tq"]))

    if a["mk"] is None or b["mk"] is None:
        out["P2"] = ("UNREAD", "no txh lines in a window")
    else:
        out["P2"] = (verdict(b["mk"] < a["mk"] and b["bitbov"] > a["bitbov"]),
                     "mk KiB/frame A %.0f / B %.0f; bit+bov A %.0f / B %.0f"
                     % (a["mk"], b["mk"], a["bitbov"], b["bitbov"]))

    if a["busy_less_txh"] is None or b["busy_less_txh"] is None:
        out["R"] = ("UNREAD", "no phase line with TxH in a window")
    else:
        d = b["busy_less_txh"] - a["busy_less_txh"]
        detail = "BUSY-TxH A %.2f / B %.2f ms/frame, B %+.2f (bar %+.1f)" % (
            a["busy_less_txh"], b["busy_less_txh"], d, R_MS)
        if out["F4"][0] == "FAIL" and out["K1"][0] == "PASS" and out["K2"][0] == "PASS":
            out["R"] = ("render thread" if d > R_MS else "not the render thread", detail)
        else:
            out["R"] = ("not read", detail + "; read only when F4 fails with K1 and K2 passing")

    if a["tlb_rdo"] is None or b["tlb_rdo"] is None:
        out["G"] = ("UNREAD", "no [tlb68] line, or no hakuX-pace flips, in a window")
    else:
        out["G"] = ("route possible" if b["tlb_rdo"] > a["tlb_rdo"] else "route refuted",
                    "per flip: rdo A %.2f / B %.2f; rdous A %.1f / B %.1f; sd A %.2f / B %.2f"
                    % (a["tlb_rdo"], b["tlb_rdo"], a["tlb_rdous"], b["tlb_rdous"],
                       a["tlb_sd"], b["tlb_sd"]))

    out["V"] = ("A %s / B %s" % tuple("%.1f%%" % (100 * x["late"]) if x["late"] is not None
                                        else "unread" for x in (a, b)),
                "flips taking 3+ VBLANKs")
    return out


def fmt(x, f="%.1f"):
    return "-" if x is None else f % x


def report(r):
    print("\n=== %s ===" % r["name"])
    print("  gfps median %s over n=%d lines (about %d flips)" % (
        fmt(r["gfps"], "%g"), r["n"], 60 * r["n"]))
    print("  M %s   Tq %s   late (3+ VBLANKs) %s of %d flips (v0-v4 %s)" % (
        fmt(r["M"], "%.0f"), fmt(r["Tq"], "%.0f"),
        fmt(None if r["late"] is None else 100 * r["late"], "%.1f%%"), sum(r["pace"]),
        "/".join(str(x) for x in r["pace"])))
    print("  phase, %d lines: BUSY %s  TxH %s  BUSY-TxH %s  Idle %s (Fr %s St %s) ms/frame" % (
        r["phase_n"], fmt(r["BUSY"], "%.2f"), fmt(r["TxH"], "%.2f"), fmt(r["busy_less_txh"], "%.2f"),
        fmt(r["Idle"], "%.2f"), fmt(r["Fr"], "%.2f"), fmt(r["St"], "%.2f")))
    print("  txh, %d groups: hashed %s KiB/frame; mk %s, bit+bov %s, memo %s; ct %s, bt %s per frame" % (
        r["txh_groups"], fmt(r["hashed"], "%.0f"), fmt(r["mk"], "%.0f"), fmt(r["bitbov"], "%.0f"),
        fmt(r["memo"], "%.0f"), fmt(r["ct"]), fmt(r["bt"])))
    print("  tlb68, %d lines: per flip rdo %s, rdous %s, sd %s; vCPU-thread resets (rd) %s" % (
        r["tlb_n"], fmt(r["tlb_rdo"], "%.2f"), fmt(r["tlb_rdous"], "%.1f"),
        fmt(r["tlb_sd"], "%.2f"), fmt(r["tlb_rd"], "%.2f")))
    print("  %s" % (r["cooldown"] or "COOLDOWN: no line in run.log"))
    h = r["heat"]
    if h is None:
        print("  heat: no thermal.jsonl")
    else:
        print("  heat: xo-therm %s C at start; %d samples in the window (%d unread)" % (
            fmt(h["xo_start"]), h["samples"], h["unread"]))
        raised = ["%s %d" % (k, c) for k, c in sorted(h["cool"].items()) if c > 0]
        print("    cooling devices above 0 in the window: %s" % (", ".join(raised) or "none"))


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("runs", nargs="*")
    ap.add_argument("--pair", nargs=2, metavar=("A_RUN", "B_RUN"))
    ap.add_argument("--window", default="90,240", help="A,B seconds after the first hakuX-perf line")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    runs = a.pair or a.runs
    if not runs:
        ap.error("no input")
    w = tuple(float(x) for x in a.window.split(","))
    print("window: %g to %g s after the first hakuX-perf line" % w)
    rs = [read_run(x, w) for x in runs]
    for r in rs:
        report(r)
    if a.pair:
        print("\n=== the legs: A %s, B %s ===" % (rs[0]["name"], rs[1]["name"]))
        for k, (v, d) in legs(*rs).items():
            print("  %-3s %-22s %s" % (k, v, d))
    # A stock build prints no gfps line in a window: not a measurement.
    return 2 if any(r["gfps"] is None for r in rs) else 0


# --- selftest -------------------------------------------------------------

PHASE = ("Surf:{surf} Tex:0.5 TxH:{txh} Shd:0.0 Draw:{draw} [Vtx:1.0 Syn:1.0 Prw:0.5 "
         "Pipe:{pipe}(Tx:{tx} Sh:0.5 Lu:0.2) Desc:1.0 Setup:1.0 Cmd:1.0 Sfp:1.0 Mfp:0.5 FTx:0.5] "
         "Fin:2.0(Sub:1.0 Fen:0.5) Flip:0.1 Idle:{idle}(Fr:3.0 St:2.0) | Tot:{tot} "
         "GPU:9.0(R:8.0 X:1.0 RP:4 Pre:0.1 Post:0.1 MxG:1.0 g:1/0/0) ms")
PERF = ("gfps={gfps} G:38.0(33.0-50.0) D:16.7(16.0-17.0) S:1.0 J:0.2 Df:0 Vd:0.1 "
        "Ul:N Vpf:2.30 Ri:9.0 Tq:{tq}")
CPU = ("CPU: K:40 W:30.0K M:{m}(Fh:9000 Ni:100) Push:1.0ms [Pull:5.0(Lk:0.1 Mth:4.0 "
       "Fst:1.0)] SpH:10% TbH:99.0% Lw:0.1")
PACE = "f={f} v0=0 v1=0 v2={v2} v3={v3} v4=0 vb={vb} max=50.0 ms=2000.0"
TXH = ("txh[new0/0K rb0/0K srf0/0K mk{mk}/{mkk}K memo0/0K bit{bit}/{bitk}K bov0/0K oth0/0K "
       "eq{eq}/{eqk}K rep0/0K]")
TXU = "txu[n0/0K new0 rb0 chg0 oth0 lin0K bc0K s3tc0K pal0K cvt0K swz0K]"
TXR = "txr[ct300 bt600/200 dl0/0K sc0 scdl0 img0 pool0 s2tc0 s2td0]"
# accel/tcg/cputlb.c's hakux_tlb68_tick(), one line per window of about 2 s
TLB68 = ("[tlb68] w={w} dt=2000 cpu=1990 ff=0 ffe=0 cr3n=0 cr3s=0 cr0=0 cr4=0 a20=0 fo=0 "
         "pf=0 pfl=0 jc=0 jct=0 jci=0 jcx=0 jcus=0 rd=4 rdc=0 rde=400 rdm=4 rdh=0 rdus=10 "
         "rdo={rdo} rdoe=40000 rdous={rdous} sd={sd} dm=0x7 sz=0:256 tw=40400 tn=256 rs=0 "
         "ka=0 kafb=0 fx=rd1jc1ka1tb1 rt=0 cb=0 cbb=0")


def stamp_at(s):
    """A logcat stamp s seconds after 09-27 12:00:00."""
    return "09-27 12:%02d:%02d.000" % (s // 60, s % 60)


def write_run(d, gfps=26, tq=900, m=20000, txh=6.9, draw=18.0, surf=1.0, late=(40, 20),
              mk=(10, 1000), bit=(1, 100), cool_in=0, cool_after=0, thermal=True,
              tlb=(600, 3000, 900)):
    os.makedirs(d, exist_ok=True)
    out = []
    for s in range(10, 260, 5):
        t = s + 1
        out.append("%s I/hakuX-perf( 1): %s" % (stamp_at(t), PERF.format(gfps=gfps, tq=tq)))
        out.append("%s I/hakuX-pace( 1): %s" % (stamp_at(t), PACE.format(
            f=60 * s, v2=late[0], v3=late[1], vb=2 * late[0] + 3 * late[1])))
        out.append("%s I/hakuX-cpu( 1): %s" % (stamp_at(t), CPU.format(m=m)))
        # A line that holds phase_read_split_check.py's identities: the bind
        # (Tx) holds the hash, Pipe its children, Draw every sub-phase, and
        # Tot is profile.c's sum.
        tx = txh + 1.0
        pipe = tx + 0.5 + 0.2 + 0.3
        assert draw >= 7.5 + pipe, "a fixture Draw below its sub-phases"
        out.append("%s I/hakuX-phase( 1): %s" % (stamp_at(t), PHASE.format(
            surf=surf, txh=txh, draw=draw, idle=5.0, tx="%.1f" % tx, pipe="%.1f" % pipe,
            tot="%.1f" % (surf + 0.5 + 0.0 + draw + 2.0 + 0.1 + 5.0))))
        out.append("%s I/hakuX-stall( 1): %s" % (stamp_at(t), TXH.format(
            mk=mk[0], mkk=mk[1], bit=bit[0], bitk=bit[1], eq=mk[0] + bit[0], eqk=mk[1] + bit[1])))
        out.append("%s I/hakuX-stall( 1): %s" % (stamp_at(t), TXU))
        out.append("%s I/hakuX-stall( 1): %s" % (stamp_at(t), TXR))
        if tlb:
            out.append("%s W/hakuX( 1): %s" % (stamp_at(t), TLB68.format(
                w=s, rdo=tlb[0], rdous=tlb[1], sd=tlb[2])))
    # a line outside the window, which must not move the median
    out.insert(0, "%s I/hakuX-perf( 1): %s" % (stamp_at(5), PERF.format(gfps=1, tq=1)))
    with open(os.path.join(d, "logcat.txt"), "w") as f:
        f.write("\n".join(out) + "\n")
    with open(os.path.join(d, "run.log"), "w") as f:
        f.write("COOLDOWN: waited 0 s, xo 50.0 -> 50.0 C [xo-therm 50.0 C < 65 C]\n")
    if not thermal:
        return
    recs = []
    for s, label in [(0, "start")] + [(x, None) for x in range(30, 300, 30)]:
        cur = cool_in if 90 <= s - 6 <= 240 else cool_after if s - 6 > 240 else 0
        recs.append('{"t": %d, "label": %s, "dev_time": "%s", "up": 1.0, "cool": '
                    '[[0, "thermal-cpufreq-4", %d, 3], [1, "thermal-pause-F8", 0, 1]], '
                    '"tz": [[0, "xo-therm", 50000]], "pause": false}'
                    % (s, '"%s"' % label if label else "null", stamp_at(s)[:14], cur))
    with open(os.path.join(d, "thermal.jsonl"), "w") as f:
        f.write("\n".join(recs) + "\n")


def selftest():
    ok = True
    tmp = tempfile.mkdtemp(prefix="pair461-")
    try:
        w = (90.0, 240.0)

        def pair(a_kw, b_kw):
            a, b = os.path.join(tmp, "A"), os.path.join(tmp, "B")
            for d, kw in ((a, a_kw), (b, b_kw)):
                shutil.rmtree(d, ignore_errors=True)
                write_run(d, **kw)
            return legs(read_run(a, w), read_run(b, w))

        # The fix as the model has it: B slower, hashes less, tests more; the
        # render thread's non-hash time unchanged. The out-of-window gfps=1
        # line must not reach the median.
        b_fix = dict(gfps=22, tq=1100, txh=3.2, draw=14.3, late=(15, 45), mk=(5, 500), bit=(4, 400))
        L = pair({}, b_fix)
        ok &= L["F4"][0] == "FAIL" and "-4" in L["F4"][1]
        ok &= L["K1"][0] == "PASS" and L["K2"][0] == "PASS"
        ok &= L["P1"][0] == "PASS" and L["P2"][0] == "PASS"
        ok &= L["R"][0] == "not the render thread"
        ok &= L["V"][0] == "A 33.3% / B 75.0%"
        # G: 30 [tlb68] lines of 600 rdo over 30 pace lines of 60 flips is
        # 10 per flip on A. The same on B refutes the guest-side route.
        ok &= L["G"][0] == "route refuted" and "rdo A 10.00 / B 10.00" in L["G"][1]
        L = pair({}, dict(b_fix, tlb=(900, 4000, 1500)))
        ok &= L["G"][0] == "route possible" and "sd A 15.00 / B 25.00" in L["G"][1]
        # no [tlb68] line: G is UNREAD, never a verdict
        L = pair({}, dict(b_fix, tlb=None))
        ok &= L["G"][0] == "UNREAD"
        # the same drop with 3 ms/frame more non-hash work on B's render thread
        L = pair({}, dict(b_fix, draw=17.3))
        ok &= L["R"][0] == "render thread"
        # positive control, K1: a cpufreq cap inside B's window only
        L = pair({}, dict(b_fix, cool_in=1))
        ok &= L["K1"][0] == "FAIL" and "thermal-cpufreq-4(cd0) A 0 / B 1" in L["K1"][1]
        ok &= L["R"][0] == "not read"
        # ...but a cap that starts after the window does not count
        L = pair({}, dict(b_fix, cool_after=2))
        ok &= L["K1"][0] == "PASS"
        # no thermal.jsonl: K1 is UNREAD, never PASS
        L = pair({}, dict(b_fix, thermal=False))
        ok &= L["K1"][0] == "UNREAD"
        # positive control, K2: 15% more methods per frame on B
        L = pair({}, dict(b_fix, m=23000))
        ok &= L["K2"][0] == "FAIL"
        # positive controls, P1 and P2: the model's predictions reversed
        L = pair({}, dict(b_fix, tq=800, mk=(12, 1200)))
        ok &= L["P1"][0] == "FAIL" and L["P2"][0] == "FAIL"
        # F4 within the bar: R is not read
        L = pair({}, dict(b_fix, gfps=25))
        ok &= L["F4"][0] == "PASS" and L["R"][0] == "not read"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("selftest: %s" % ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
