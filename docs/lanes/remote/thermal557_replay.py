#!/usr/bin/env python3
"""Drive the #557 thermal governor core on the desktop.

    thermal557_replay.py --selftest
    thermal557_replay.py FILE... [--tau S] [--history] [--score]

It builds docs/lanes/remote/thermal557_harness.c, which includes
android/app/src/main/cpp/thermal_governor.c whole, with the host's cc ($CC).
Nothing here needs a device or an NDK.

--selftest runs four groups:
  sysfs     the harness's own checks: the reader against a fake
            /sys/class/thermal (the zone by type, the pause devices by
            prefix, in-place re-reads, unread values), and the tick (off
            unless HAKUX_THERMAL_ADAPT=1, tau and zone from the environment,
            rungs registered before and after the first tick, the config
            line after one status interval)
  scenario  synthetic traces with the step times the design fixes, worked
            out by hand below: a first-order climb, plateaus under and over
            72 C with noise, a cool-down, the dead band, a pause, a
            silence, unwired rungs, unread samples
  math      the C core's T_eq on every sample against an independent
            least-squares computation, to 1e-6
  model     the C core's events against an independent Python model of
            the policy (REF below) on 60 seeded random traces with pauses,
            unread samples, silences and random wiring: the same events at
            the same times, and the same T_eq

FILE is a thermal.jsonl (docs/testing/thermal_state.py's records), or the
extract format of #557's ask, several runs to a file:
    # RUN samples=N start=start
    SECONDS LABEL XO_C PAUSE        (seconds from the start sample)

THE REPLAY (registered on #557, 2026-09-28T15:35:33Z, comment 5873316950).
From each run's `start` sample on, because the governor starts with the
title. The samples, about 30-33 s apart, are fed at 1 Hz. Each new sample
is reached by a linear ramp from the previous one that lasts one sampling
interval. So the governor never sees a value before it was sampled, and
sees each one about 30 s late. The pause flag moves with it. Every time is
seconds from the start sample.
  t78   the last sample before the first one with xo-therm >= 78.0 C or a
        pause device set: the latest time the pause is known not to have
        begun
  lead  t78 - the first step-down
--score reads the legs of docs/testing/predictions/remote-557-replay.json
off the runs it names.
"""

import argparse
import json
import math
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
HARNESS = os.path.join(HERE, "thermal557_harness.c")
CORE = os.path.join(HERE, "..", "..", "..", "android", "app", "src", "main",
                    "cpp", "thermal_governor.c")

# thermal_governor_params_default()
DEFAULTS = dict(tau_s=210.0, window_s=60.0, min_span_s=45.0, down_c=72.0,
                down_hold_s=60.0, up_c=64.0, up_hold_s=300.0, min_gap_s=120.0,
                gap_reset_s=10.0, status_every_s=30.0)
NAMES = ["cap30", "no-occl", "scale1x", "rp-mode"]

# The registration's runs (#557, 5873316950).
PAUSED = ["4130828", "4130875", "4130912", "4130959", "4130999", "4131051",
          "4131088", "4131123"]
PLATEAU = "810152"   # hostops-810152: MechAssault 2 MAX from 46.9 C, 74.2 max
PILOT = "1257857"    # GTA default from 57.4 C, 450 s: read, not scored


def build(cc=None, out_dir=None):
    cc = cc or os.environ.get("CC") or "cc"
    out_dir = out_dir or tempfile.mkdtemp(prefix="thermal557-")
    exe = os.path.join(out_dir, "thermal557_harness")
    cmd = [cc, "-std=gnu11", "-O2", "-Wall", "-Wextra", "-Werror", "-o", exe,
           HARNESS, "-lm"]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        sys.exit("build failed: %s\n%s" % (" ".join(cmd), r.stderr))
    return exe


class Run:
    """What the harness printed for one feed."""

    def __init__(self, out):
        self.p = []       # (t, teq or nan, level)
        self.calls = []   # (t, rung, engaged)
        self.lines = []   # (t, text)
        for ln in out.splitlines():
            k, _, rest = ln.partition(" ")
            if k == "P":
                t, teq, lv = rest.split()
                self.p.append((float(t), float(teq), int(lv)))
            elif k == "C":
                t, r, e = rest.split()
                self.calls.append((float(t), int(r), int(e)))
            elif k == "L":
                t, _, text = rest.partition(" ")
                self.lines.append((float(t), text))

    def events(self):
        """[(t, 'down'|'up'|'floor', rung name)] from the log lines."""
        out = []
        for t, text in self.lines:
            m = re.match(r"\[thermal557\] (down|up|floor) rung=\d+/\d+ (\S+)", text)
            if m:
                out.append((t, m.group(1), m.group(2)))
        return out

    def downs(self):
        return [t for t, r, e in self.calls if e == 1]

    def ups(self):
        return [t for t, r, e in self.calls if e == 0]


def feed(exe, samples, params=None, wire=None):
    """samples: [(t, xo or None/nan, pause)]. Returns a Run."""
    script = ["param %s %r" % kv for kv in sorted((params or {}).items())]
    if wire is not None:
        script.append("wire " + " ".join(str(r) for r in wire))
    for t, xo, pause in samples:
        bad = xo is None or (isinstance(xo, float) and math.isnan(xo))
        script.append("s %r %s %d" % (t, "nan" if bad else repr(xo), pause))
    r = subprocess.run([exe, "feed"], input="\n".join(script) + "\n",
                       capture_output=True, text=True)
    if r.returncode:
        sys.exit("harness feed failed (%d): %s" % (r.returncode, r.stderr))
    return Run(r.stdout)


# --- an independent model of the policy, for the "model" group ---

def ls_slope(win):
    n = len(win)
    mt = sum(t for t, _ in win) / n
    mc = sum(c for _, c in win) / n
    sxx = sum((t - mt) ** 2 for t, _ in win)
    if not sxx > 0:
        return None
    return sum((t - mt) * (c - mc) for t, c in win) / sxx


def REF(samples, p, wire=(0, 1, 2, 3)):
    """The policy as #557 states it, written apart from the C.
    Returns ([(t, kind, rung name)], [teq per sample])."""
    win, engaged, events, teqs = [], [], [], []
    last_t = None
    last_change = -math.inf
    hot_since = cool_since = None
    floor_logged = False
    for t, xo, pause in samples:
        if last_t is None:
            last_t = t
        have_xo = not (xo is None or math.isnan(xo))
        # No temperature is no reading, unless a pause device is set: that
        # counts on its own (audit LOW-3).
        if not have_xo and pause <= 0:
            teqs.append(math.nan)
            continue
        if t - last_t > p["gap_reset_s"]:
            win, hot_since, cool_since = [], None, None
        last_t = t
        teq = math.nan
        if have_xo:
            win = [(a, c) for a, c in win if t - a <= p["window_s"]][-255:]
            win.append((t, xo))
            if len(win) >= 3 and win[-1][0] - win[0][0] >= p["min_span_s"]:
                s = ls_slope(win)
                if s is not None:
                    teq = xo + p["tau_s"] * s
        valid = not math.isnan(teq)
        hot = pause > 0 or (valid and teq > p["down_c"])
        cool = pause == 0 and valid and teq < p["up_c"]
        if not hot:
            hot_since, floor_logged = None, False
        elif hot_since is None:
            hot_since = t
        cool_since = (t if cool_since is None else cool_since) if cool else None
        may = t - last_change >= p["min_gap_s"]
        change = False
        if hot and may and t - hot_since >= p["down_hold_s"]:
            nxt = [r for r in range(4) if r in wire and r not in engaged]
            if nxt:
                engaged.append(nxt[0])
                events.append((t, "down", NAMES[nxt[0]]))
                change = True
            elif not floor_logged:
                events.append((t, "floor", "-"))
                floor_logged = True
        elif cool and may and engaged and t - cool_since >= p["up_hold_s"]:
            events.append((t, "up", NAMES[engaged.pop()]))
            change = True
        if change:
            last_change, hot_since, cool_since = t, None, None
        teqs.append(teq)
    return events, teqs


# --- synthetic traces ---

def first_order(t, t_start, c_start, c_inf, tau):
    return c_inf - (c_inf - c_start) * math.exp(-(t - t_start) / tau)


def plant(c0, segments, seconds):
    """A 1 Hz first-order trace from c0. From each segment's start second,
    (t_from, c_inf, tau), it relaxes toward c_inf from where it was."""
    out, c, active, t_seg, c_seg = [], c0, None, 0, c0
    for t in range(int(seconds) + 1):
        for seg in segments:
            if seg[0] == t:
                active, t_seg, c_seg = seg, t, c
        if active:
            c = first_order(t, t_seg, c_seg, active[1], active[2])
        out.append((float(t), c))
    return out


def with_pause(tc, pause=lambda t: 0):
    return [(t, c, pause(t)) for t, c in tc]


def check(results, ok, what):
    results.append((bool(ok), what))
    print("%s %s" % ("PASS" if ok else "FAIL", what))


def approx(ts, want, tol=1.0):
    return len(ts) == len(want) and all(abs(a - b) <= tol for a, b in zip(ts, want))


def scenarios(exe, res):
    tau = DEFAULTS["tau_s"]
    # S1: a first-order climb 60 -> 80 C with the governor's own tau. The
    # window is valid at 45 s, T_eq is ~80 > 72 from then on, so the dwell
    # ends at 105 s, and the 120 s gap spaces the rest: 105, 225, 345, 465.
    # xo reaches 78 C at 210 * ln(20/2) = 484 s. The floor is said once, at
    # 585 s, and never again while it stays hot.
    climb = plant(60.0, [(0, 80.0, tau)], 900)
    r = feed(exe, with_pause(climb))
    check(res, approx(r.downs(), [105, 225, 345, 465]) and not r.ups(),
          "S1 climb to 80 C: steps down at 105/225/345/465 s, none up (%s)" % r.downs())
    ev = r.events()
    check(res, [e[2] for e in ev if e[1] == "down"] == NAMES and
          [e[0] for e in ev if e[1] == "floor"] == [585.0],
          "S1 rungs engage in order, and the floor is logged once, at 585 s")
    check(res, all(x[1] - 80.0 >= -1e-9 for x in r.p if not math.isnan(x[1])),
          "S1 T_eq never under-reads a matched first-order climb (the 60 s "
          "window lags, so it reads early: max +%.2f C)" %
          max(x[1] - 80.0 for x in r.p if not math.isnan(x[1])))

    # S2: a climb to 68 C: T_eq stays under 72, so nothing happens.
    r = feed(exe, with_pause(plant(50.0, [(0, 68.0, tau)], 1800)))
    mx = max(x[1] for x in r.p if not math.isnan(x[1]))
    check(res, not r.calls and mx < 72.0,
          "S2 climb to 68 C: no change, max T_eq %.2f C < 72" % mx)

    # S3: plateaus with +-0.3 C of uniform noise: 70 C never steps, 74 C
    # steps on the S1 schedule and never up.
    rnd = random.Random(557)
    flat = lambda c: [(float(t), c + rnd.uniform(-0.3, 0.3), 0) for t in range(1801)]
    r70, r74 = feed(exe, flat(70.0)), feed(exe, flat(74.0))
    check(res, not r70.calls, "S3 70 C plateau with +-0.3 C noise: no change")
    check(res, approx(r74.downs(), [105, 225, 345, 465]) and not r74.ups(),
          "S3 74 C plateau with +-0.3 C noise: 105/225/345/465 s, none up (%s)"
          % r74.downs())

    # S4: the climb, then the device cools toward 55 C from 600 s. Once
    # T_eq is under 64 C, one rung comes back every 300 s, the last engaged
    # first.
    cool = plant(60.0, [(0, 80.0, tau), (600, 55.0, tau)], 2700)
    r = feed(exe, with_pause(cool))
    t64 = next(t for t, teq, _ in r.p if t > 600 and teq < 64.0)
    ups = [e for e in r.events() if e[1] == "up"]
    gaps = [b[0] - a[0] for a, b in zip(ups, ups[1:])]
    check(res, [e[2] for e in ups] == NAMES[::-1] and ups[0][0] - t64 >= 300 and
          all(299 <= g <= 302 for g in gaps),
          "S4 cool-down: up at %s s (T_eq < 64 from %.0f s), last engaged "
          "first" % ([e[0] for e in ups], t64))

    # S5: the dead band. Climb to 74 C, then settle toward 68 C from 600 s:
    # T_eq between 64 and 72 moves nothing.
    r = feed(exe, with_pause(plant(60.0, [(0, 74.0, tau), (600, 68.0, tau)], 2400)))
    check(res, len(r.downs()) == 4 and not [t for t, _, _ in r.calls if t > 600],
          "S5 dead band: four down by 465 s, then nothing for 30 min")

    # S6: a pause. xo falls 77 -> 66 C over 600 s with thermal-pause set, as
    # the kernel's pause makes it fall. The pause counts as hot, so the
    # rungs go down on the dwell alone (60/180/300/420 s), and nothing comes
    # up while it holds even though T_eq is under 64 near its end. After
    # the pause clears at 600 s the fall continues, and a rung comes back
    # 300 s after T_eq is under 64 with no pause.
    fall = [(float(t), 77.0 - 11.0 * t / 600.0, 1) for t in range(600)]
    fall += [(float(t), first_order(t, 600, 66.0, 55.0, tau), 0) for t in range(600, 1500)]
    r = feed(exe, fall)
    why = [text for _, text in r.lines if " down " in text]
    early_up = [t for t in r.ups() if t < 900]
    check(res, approx(r.downs(), [60, 180, 300, 420]) and
          all("why=pause" in w for w in why) and not early_up and r.ups(),
          "S6 pause: down at %s s on the pause, none up before 900 s, up "
          "at %s s" % (r.downs(), r.ups()))

    # S7: a 30 s silence (80-110 s) during the S1 climb restarts the window
    # and the dwell: valid again at 155 s, first step at 215 s.
    gap = [x for x in with_pause(climb) if not 80 < x[0] < 110]
    r = feed(exe, gap)
    check(res, r.downs() and abs(r.downs()[0] - 215) <= 1,
          "S7 a 30 s silence restarts the window: first step at %s s, not "
          "105" % (r.downs()[:1],))

    # S8: only rungs 0 and 2 wired: those two, in order, then the floor.
    r = feed(exe, with_pause(climb), wire=[0, 2])
    ev = r.events()
    check(res, [e[2] for e in ev if e[1] == "down"] == ["cap30", "scale1x"] and
          [e[1] for e in ev].count("floor") == 1 and
          {x[1] for x in r.calls} == {0, 2},
          "S8 unwired rungs are skipped: %s" % [(e[0], e[1], e[2]) for e in ev])

    # S9: every fifth sample unread (NAN): gaps of 2 s, so the dwell holds
    # and the schedule moves by at most a second.
    r = feed(exe, [(t, float("nan") if int(t) % 5 == 4 else c, 0) for t, c in climb])
    check(res, approx(r.downs(), [105, 225, 345, 465], tol=1.0),
          "S9 unread samples every 5 s: %s" % r.downs())

    # S10: a steady 0.5 C/min from 70 C, where the slope is exact: T_eq =
    # T + tau * 0.5/60. At tau 210 s that is T + 1.75, already 72.1 C when
    # the window turns valid at 45 s, so the first step is at 105 s. At tau
    # 60 s it is T + 0.5, which passes 72 at 180 s: first step at 240 s.
    slow = [(float(t), 70.0 + 0.5 * t / 60.0, 0) for t in range(600)]
    r = feed(exe, slow)
    check(res, r.downs() and abs(r.downs()[0] - 105) <= 1,
          "S10 0.5 C/min from 70 C: T_eq = T + 1.75 is over 72 once valid, "
          "first step at %s s" % r.downs()[:1])
    r = feed(exe, slow, params={"tau_s": 60.0})
    t72 = next(t for t, teq, _ in r.p if teq > 72.0)
    check(res, abs(t72 - 180.0) <= 1.0 and r.downs() and abs(r.downs()[0] - 240) <= 1,
          "S10 the same with tau 60 s: T_eq = T + 0.5 crosses 72 at %.0f s "
          "(180), first step at %s (240)" % (t72, r.downs()[:1]))


    # S11: a pause while xo-therm cannot be read (audit LOW-3). The pause
    # counts on its own, so the rungs go down on the dwell alone at
    # 60/180/300/420 s, as in S6. With the temperature gone as well, nothing
    # may come back up.
    blind = [(float(t), float("nan"), 1) for t in range(600)]
    r = feed(exe, blind)
    check(res, approx(r.downs(), [60, 180, 300, 420]) and not r.ups(),
          "S11 a pause with xo-therm unread still steps down: %s s" % r.downs())
    # ... but unread samples with no pause set are no reading at all: a
    # 30 s run of them is a silence, and restarts S1's window (first step at
    # 215 s, as S7).
    r = feed(exe, [(t, float("nan") if 80 < t < 110 else c, 0) for t, c in climb])
    check(res, r.downs() and abs(r.downs()[0] - 215) <= 1,
          "S11 30 s of unread samples with no pause is a silence: first step "
          "at %s s" % r.downs()[:1])


def math_group(exe, res):
    rnd = random.Random(1557)
    worst = 0.0
    for k in range(10):
        c = 55.0 + 10 * rnd.random()
        s = []
        for t in range(900):
            c += rnd.uniform(-0.2, 0.25)
            s.append((float(t) + rnd.uniform(-0.2, 0.2), c, 0))
        r = feed(exe, s, params={"tau_s": 150.0 + 30 * k})
        win = []
        for (t, c, _), (_, teq, _) in zip(s, r.p):
            win = [(a, b) for a, b in win if t - a <= 60.0] + [(t, c)]
            want = math.nan
            if len(win) >= 3 and win[-1][0] - win[0][0] >= 45.0:
                want = c + (150.0 + 30 * k) * ls_slope(win)
            if math.isnan(want) != math.isnan(teq):
                worst = math.inf
            elif not math.isnan(want):
                worst = max(worst, abs(want - teq))
    check(res, worst < 1e-6, "M1 T_eq matches an independent least-squares "
          "fit on 9000 jittered samples (max error %.2e C)" % worst)


def model_group(exe, res, n=60):
    bad = []
    kinds = {"down": 0, "up": 0, "floor": 0}
    for seed in range(n):
        rnd = random.Random(seed)
        # xo relaxes toward a target that jumps between a cool regime and a
        # hot one, so every trace both steps down and comes back up.
        t, c, pause, s = 0.0, rnd.uniform(50, 66), 0, []
        target, tau_p = rnd.uniform(74, 82), rnd.uniform(120, 400)
        while t < 5400:
            if rnd.random() < 1 / 600:
                target = rnd.choice([rnd.uniform(50, 60), rnd.uniform(74, 82)])
                tau_p = rnd.uniform(120, 400)
            if rnd.random() < (1 / 200 if pause else 1 / 1200):
                pause = 1 - pause
            dt = 1.0 + rnd.uniform(-0.2, 0.2)
            c += (target - c) * dt / tau_p + rnd.uniform(-0.1, 0.1)
            xo = float("nan") if rnd.random() < 0.01 else c
            pz = -1 if rnd.random() < 0.005 else pause
            s.append((round(t, 3), xo, pz))
            t += dt
            if rnd.random() < 0.002:
                t += rnd.uniform(5, 40)
        wire = sorted(rnd.sample(range(4), rnd.randint(1, 4)))
        p = dict(DEFAULTS)
        p["tau_s"] = rnd.choice([120.0, 210.0, 300.0])
        r = feed(exe, s, params=p, wire=wire)
        ev, teqs = REF(s, p, wire)
        got = r.events()
        for e in got:
            kinds[e[1]] += 1
        tq = all((math.isnan(a) and math.isnan(b)) or abs(a - b) < 1e-6
                 for a, (_, b, _) in zip(teqs, r.p))
        if got != ev or not tq:
            bad.append((seed, got[:3], ev[:3]))
    check(res, not bad and min(kinds.values()) >= 20,
          "R1 the C core and the Python model agree on %d random traces "
          "(%d down, %d up, %d floor)%s" % (
              n, kinds["down"], kinds["up"], kinds["floor"],
              "" if not bad else "; they differ: %s" % bad[:2]))


def selftest(cc=None):
    res = []
    out_dir = tempfile.mkdtemp(prefix="thermal557-")
    try:
        exe = build(cc, out_dir)
        r = subprocess.run([exe, "sysfs"], capture_output=True, text=True,
                           env=dict(os.environ, TMPDIR=out_dir))
        sys.stdout.write(r.stdout)
        check(res, r.returncode == 0, "sysfs: the harness's reader and tick checks")
        scenarios(exe, res)
        math_group(exe, res)
        model_group(exe, res)
    finally:
        shutil.rmtree(out_dir, ignore_errors=True)
    failed = [w for ok, w in res if not ok]
    print("%s: %d of %d groups' checks failed" % ("FAIL" if failed else "PASS",
                                                   len(failed), len(res)))
    return 1 if failed else 0


# --- the replay ---

def load_runs(path):
    """{run name: [(seconds from start, label, xo or None, pause or None)]}"""
    runs = {}
    text = open(path, encoding="utf-8", errors="replace").read()
    if text.lstrip().startswith("{"):
        recs = [json.loads(l) for l in text.splitlines() if l.strip()]
        st = next((r for r in recs if r.get("label") == "start"), recs[0] if recs else {})
        t0 = st.get("up")
        name = os.path.basename(os.path.dirname(os.path.abspath(path)))
        rows = []
        for r in recs:
            xo = next((z[2] / 1000.0 for z in r.get("tz") or [] if z[1] == "xo-therm"), None)
            up = r.get("up")
            if up is None or t0 is None:
                continue
            p = r.get("pause")
            rows.append((up - t0, r.get("label"), xo, None if p is None else int(bool(p))))
        runs[name] = rows
        return runs
    name = None
    for ln in text.splitlines():
        if ln.startswith("#"):
            m = re.match(r"#\s*(\S+)", ln)
            name = m.group(1) if m else "run%d" % len(runs)
            runs[name] = []
            continue
        f = ln.split()
        if len(f) != 4 or name is None or f[0] == "-":
            continue
        runs[name].append((float(f[0]), None if f[1] == "-" else f[1],
                           None if f[2] == "-" else float(f[2]),
                           None if f[3] == "-" else int(f[3])))
    return runs


def replay_feed(rows):
    """The registered causal feed: samples from `start` on, fed at 1 Hz."""
    smp = [(t, xo, 0 if p is None else p) for t, _, xo, p in rows
           if t >= 0 and xo is not None]
    feedv = []
    if len(smp) < 2:
        return smp, feedv
    t = smp[0][0]
    i = 0
    while t <= smp[-1][0] + (smp[-1][0] - smp[-2][0]):
        while i + 1 < len(smp) and smp[i + 1][0] <= t:
            i += 1
        ti, ci, pi = smp[i]
        if i == 0:
            feedv.append((t, ci, pi))
        else:
            tp, cp, pp = smp[i - 1]
            f = min(1.0, (t - ti) / (ti - tp))
            feedv.append((t, cp + (ci - cp) * f, pi if f >= 1.0 else pp))
        t += 1.0
    return smp, feedv


def t78_of(smp):
    """(t78, first sample time with xo >= 78 or paused), or (None, None)."""
    for j, (t, xo, p) in enumerate(smp):
        if xo >= 78.0 or p > 0:
            return (smp[j - 1][0] if j else None), t
    return None, None


def replay(exe, path_runs, tau=None, history=False):
    out = {}
    params = dict(DEFAULTS)
    if tau:
        params["tau_s"] = tau
    for name, rows in path_runs.items():
        smp, fv = replay_feed(rows)
        if len(smp) < 2:
            print("%s: fewer than two samples from start, not replayed" % name)
            continue
        r = feed(exe, fv, params=params)
        t78, first_hot = t78_of(smp)
        downs = r.downs()
        valid = [(t, teq) for t, teq, _ in r.p if not math.isnan(teq)]
        t72 = next((t for t, teq in valid if teq > 72.0), None)
        d = dict(name=name, n=len(smp), xo0=smp[0][1], xomax=max(x[1] for x in smp),
                 end=smp[-1][0], t78=t78, first_hot=first_hot, t72=t72,
                 first_down=downs[0] if downs else None,
                 lead=(t78 - downs[0]) if (t78 is not None and downs) else None,
                 before78=len([t for t in downs if t78 is not None and t < t78]),
                 teqmax=max((teq for _, teq in valid), default=None),
                 events=r.events())
        out[name] = d
        print("%s: %d samples, xo %.1f C at start, max %.1f C, %d s" % (
            name, d["n"], d["xo0"], d["xomax"], d["end"]))
        if t78 is None and first_hot is None:
            print("    no sample at 78 C or paused")
        elif t78 is None:
            print("    paused or at 78 C from the start sample")
        else:
            print("    t78 %.0f s (first sample at 78 C or paused: %.0f s)" % (t78, first_hot))
        print("    T_eq > 72 first at %s s; max T_eq %s C" % (
            "%.0f" % t72 if t72 is not None else "-",
            "%.2f" % d["teqmax"] if d["teqmax"] is not None else "-"))
        if d["first_down"] is not None:
            print("    first step down %.0f s; lead %s; %d step(s) before t78" % (
                d["first_down"], "%+.0f s" % d["lead"] if d["lead"] is not None else "-",
                d["before78"]))
        else:
            print("    no step down")
        if history:
            for t, kind, rung in d["events"]:
                line = next((txt for tt, txt in r.lines if tt == t and (" %s " % kind) in txt), "")
                m = re.search(r"xo=(\S+) dTdt=(\S+) teq=(\S+) pause=(\S+)", line)
                print("      %6.0f s  %-5s %-8s %s" % (
                    t, kind, rung, "xo %s dT/dt %s/min teq %s pause %s" % m.groups() if m else ""))
    return out


def pick(res, key):
    return next((v for k, v in res.items() if k == key or k.endswith("-" + key)), None)


def score(res):
    rows = [pick(res, k) for k in PAUSED]
    have = [r for r in rows if r is not None and r["t78"] is not None]
    missing = [k for k, r in zip(PAUSED, rows) if r is None or r["t78"] is None]
    print("\nLEGS (registered 2026-09-28T15:35:33Z, #557 5873316950)")
    if missing:
        print("  not in the input, or no t78 (dropped, legs scale): %s" % ", ".join(missing))
    leads = [r["lead"] for r in have]
    l1 = have and all(x is not None and x > 0 for x in leads)
    l2 = have and all(x is not None and x >= 60 for x in leads)
    two = len([r for r in have if r["before78"] >= 2])
    need = math.ceil(5 * len(have) / 8.0)
    print("  L1  first step-down before t78 on all %d: %s (leads %s)" % (
        len(have), "HOLDS" if l1 else "KILLED",
        ", ".join("%+.0f" % x if x is not None else "none" for x in leads)))
    print("  L2  lead >= 60 s on all %d: %s" % (len(have), "HOLDS" if l2 else "KILLED"))
    print("  L3  two or more steps before t78 on >= %d of %d: %d -> %s" % (
        need, len(have), two, "HOLDS" if two >= need else "KILLED"))
    c = pick(res, PLATEAU)
    if c is None:
        print("  L4a/L4b  %s not in the input" % PLATEAU)
    else:
        print("  L4a max T_eq on %s: %.2f C -> %s" % (
            c["name"], c["teqmax"], "HOLDS" if c["teqmax"] < 78.0 else "KILLED"))
        print("  L4b step-downs on %s: first at %s s -> %s" % (
            c["name"], "%.0f" % c["first_down"] if c["first_down"] is not None else "none",
            "HOLDS" if c["first_down"] is not None else "KILLED"))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("files", nargs="*")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--tau", type=float, help="override tau (s)")
    ap.add_argument("--history", action="store_true", help="print every rung change")
    ap.add_argument("--score", action="store_true", help="score the registered legs")
    ap.add_argument("--cc", help="C compiler (default $CC or cc)")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest(a.cc)
    if not a.files:
        ap.error("FILE... or --selftest")
    out_dir = tempfile.mkdtemp(prefix="thermal557-")
    try:
        exe = build(a.cc, out_dir)
        runs = {}
        for f in a.files:
            runs.update(load_runs(f))
        print("tau %.0f s%s\n" % (a.tau or DEFAULTS["tau_s"], "" if a.tau else " (default)"))
        res = replay(exe, runs, a.tau, a.history)
        if a.score:
            score(res)
    finally:
        shutil.rmtree(out_dir, ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
