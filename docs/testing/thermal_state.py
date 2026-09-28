#!/usr/bin/env python3
"""The device's thermal state in one adb call, and whether a pause overlaps a window (#507).

    thermal_state.py <serial> [--label L]       one JSON line: every cooling device, every zone
    thermal_state.py --trips <serial>           every zone's trip points and bound cooling devices
    thermal_state.py --diff A B                 cooling devices whose cur_state rose from A to B
    thermal_state.py --summary FILE.jsonl       one `THERMAL:` line for run.log
    thermal_state.py --window FILE.jsonl LO HI  is a pause possible inside LO..HI s after
                                                FILE's `start` sample (else its first)?
                                                exit 0 yes, 1 no, 2 unread
    thermal_state.py --cool FILE.jsonl ZONE C   is FILE's last sample cool enough to start a
                                                title? exit 0 yes, 1 no (hot or paused), 2 unread
    thermal_state.py --power FILE.jsonl LO HI   average power over LO..HI s after FILE's
                                                `start` sample, as JSON; exit 2 unread

WHY. On the Thor under the MAX regimen the kernel's thermal mitigation pauses
cpu3-7 a few minutes into a run: cooling device `thermal-pause-F8` goes 1/1,
every emulator thread moves to cpu0-2, and fps falls 5-7x (GTA 25.4 -> 3.57
fps, 2026-09-27 13:36:06 PDT). Nothing else shows it: cpu/online, the
cpusets, scaling_cur_freq and thermalservice all read normal. The cooling
device's cur_state is the one place it is visible, so soak_title.sh samples it
every 30 s into thermal.jsonl and title_verdict.py voids a scored window a
pause may overlap.

A SAMPLE is one `adb shell` running one sh script on the device: the device's
own clock (the clock logcat stamps with, so the verdict can compare), its
uptime, then `cd <n> <cur> <max> <type>` per cooling device and `tz <n>
<temp> <type>` per zone. The type goes last because it is the only field that
could hold a space. An adb failure is still a line, with `error` set and no
devices: a missing sample must widen a pause's bounds, never read as clean.

A PAUSE EPISODE is a run of samples in which any `thermal-pause*` device has
cur_state > 0. Sampled every 30 s, its onset is only known to lie after the
last clean sample before it and at or before the first paused one; its end,
at or after the last paused sample and before the next clean one. So the
span a pause may have covered is (last clean before, first clean after), open
at either end when no clean sample bounds it. A window is flagged when that
span overlaps it: a pause first seen at +250 s, last clean at +220 s, may have
begun at +221 s, inside a window ending at +240 s. Conservative on purpose: a
benchmark voided by a pause that began one second after its window costs a
rerun; one scored across a pause is a wrong fps in the 0.5 table.

A WINDOW IS COVERED when readable samples bound it on both sides with no gap
between them longer than MAX_GAP_S. An episode needs a paused sample, so a
window no readable sample reaches would otherwise read as clean: a pause at
+150 s, then every later `adb shell` failing (the WSL `UtilAcceptVsock`
case, while `adb logcat` keeps streaming perf lines), left one clean reading
before `am start` and scored the paused fps. coverage() names the gap;
--window exits 2 on it, and title_verdict.py VOIDS the window
(`thermal-unread: ...`) rather than scoring it, for the same reason a pause
it may overlap is void. MAX_GAP_S is three sample periods: one failed sample
(60 s) or soak_title.sh's foreground wait before the first hold sample still
counts as covered; two failures in a row do not. The window's end needs a
readable sample at or after it, less END_SLACK_S: dev_time is whole seconds
and `soak end` is a millisecond logcat stamp, so the `end` sample taken just
after it can read up to a second earlier.

THE COOL-DOWN GATE (--cool). The pause trips at xo-therm 78 C and clears near
70 C (8 C hysteresis). At MAX from 54 C, GTA took 9 min to reach the trip.
A run queued seconds after a hot one starts at 75 C or already paused, and
pauses in 2-4 min (#507). soak_title.sh therefore samples before it sets MAX
and waits while the named zone reads at or above the limit, or any pause
device is set. A device without the zone, or a sample with no reading, is
not gated (exit 2): the gate may cost minutes, but it must never cost the run.

POWER (`pw` in a sample, --power). The same adb call reads the battery's
`current_now` (uA) and `voltage_now` (uV), the USB input's, and Android's
thermal status. A frame rate reached by heating the device until it pauses is
not a playable one, so every fix is judged on energy per frame as well as fps.
  - SIGN. Both handhelds' kernels report battery `current_now` BELOW zero
    while the battery drains and above it while it charges (AGENTS.md: the
    Nova -459 mA under the emulator, +122 uA asleep). Battery power here is
    the opposite, so that the number grows with the load:
        battery W = -(current_now x voltage_now) / 1e12
        + the battery is DISCHARGING, - it is CHARGING.
  - USB INPUT is `usb/current_now` x `usb/voltage_now` when both read: a
    measurement. With neither, `input_current_limit` x 5 V is an upper
    bound, and is named as one (`usb_from`); a bound is not a value.
    `usb_bound` is true when any sample behind the average was a bound:
    usb_w, net_w and J per frame are then upper bounds too.
  - NET W = battery W + USB input W: what the device draws. On the 500 mA
    PC port that is about 2 W of input plus whatever the battery gives.
  - THE AVERAGE is time-weighted: power is taken as linear between two
    samples and held flat before the first and after the last, then
    integrated over the window. A plain mean of the samples inside the
    window would ignore up to 30 s at each edge.
  - IMPOSSIBLE ROW. A sample that says the battery is charging at more than
    SIGN_SLACK_W with no USB input cannot be true under the sign above. It
    is counted (`sign_suspect`), and a window holding one gives no J per
    frame: on a kernel with the other sign every number would be negated.

CLOCKS (`clk` in a sample, #414). Every cpufreq policy's scaling_cur_freq and
whichever of scaling_max_freq / cpuinfo_max_freq read (kHz), and the GPU's
gpuclk, max_gpuclk (Hz) and `throttling`. The kernel's junction-limit clock
cap (LMh/DCVS) sets no cooling device, so without these a core held at a
fraction of its clock at 95 C reads exactly like one at full speed. --summary
names each domain's range against its ceiling.
"""
import datetime as dt
import json
import os
import re
import subprocess
import sys
import time

PAUSE_PREFIX = "thermal-pause"
# The Thor also has one pause device per core (`pause-cpu0`..`pause-cpu7`),
# all 0/1 at rest beside the mask devices (`thermal-pause-F8` is cpu3-7).
# Either kind takes a core away from the emulator, so either is a pause.
PAUSE_PREFIXES = (PAUSE_PREFIX, "pause-cpu")

# soak_title.sh's THERMAL_EVERY_S default; see A WINDOW IS COVERED.
EVERY_S = 30
MAX_GAP_S = 3 * EVERY_S
END_SLACK_S = 1.0

# FAN (#507 Part D). Both handhelds drive the fan through this PWM, the node
# the OEM apps write. duty/period is the share of full speed (period 50000 on
# both: SPORT holds 25000, SMART follows a temperature curve). `speed` is the
# Nova's tach rpm; the Thor's reads 0. Sampled so SMART's real curve under
# load is on record beside every temperature it answers.
FAN_DIR = "/sys/class/gpio5_pwm2"

# CLOCKS (#414). Qualcomm's LMh/DCVS caps a core's clock near its junction
# limit without setting any cooling device, so no `cd` line shows it. Every
# cpufreq policy (policy0/3/7 on both handhelds: little, mid, big) is read
# for its current clock and both ceilings, and the GPU for its clock, its
# ceiling and kgsl's `throttling` switch. scaling_max_freq is permission-
# denied on the Thor's policy0: a field that does not read is left out.
CPUFREQ_DIR = "/sys/devices/system/cpu/cpufreq"
KGSL_DIR = "/sys/class/kgsl/kgsl-3d0"

# One sh script, one adb call. `2>/dev/null` per read: a zone whose temp
# read fails (some sensors return EINVAL while powered down) must not end the
# loop or leak an error line into the parse.
SAMPLE_SH = (
    "echo \"now $(date +'%m-%d %H:%M:%S') up $(cut -d' ' -f1 /proc/uptime)\"; "
    "for d in /sys/class/thermal/cooling_device*; do "
    "echo \"cd ${d##*cooling_device} $(cat $d/cur_state 2>/dev/null) $(cat $d/max_state 2>/dev/null) $(cat $d/type 2>/dev/null)\"; "
    "done; "
    "for z in /sys/class/thermal/thermal_zone*; do "
    "echo \"tz ${z##*thermal_zone} $(cat $z/temp 2>/dev/null) $(cat $z/type 2>/dev/null)\"; "
    "done; "
    # POWER. `ps <supply> <field> <value>`: the value goes last, usb_type
    # holds spaces. `dumpsys -t 3`: a thermal HAL that does not answer must
    # cost three seconds, not the sample.
    "for p in battery usb; do d=/sys/class/power_supply/$p; "
    "for f in status capacity current_now voltage_now online usb_type current_max input_current_limit; do "
    "[ -f $d/$f ] && echo \"ps $p $f $(cat $d/$f 2>/dev/null)\"; "
    "done; done; "
    "echo \"ths $(dumpsys -t 3 thermalservice 2>/dev/null | grep -m1 'Thermal Status')\"; "
    # FAN. `fan <field> <value>`; see FAN_DIR.
    "for f in duty period state speed; do [ -f " + FAN_DIR + "/$f ] && "
    "echo \"fan $f $(cat " + FAN_DIR + "/$f 2>/dev/null)\"; done; "
    # The OEM fan mode (devices.sh), so every sample says which mode drove
    # the duty beside it; soak_title.sh FAN_MODE is checked against this.
    "echo \"fan mode $(settings get system fan_mode 2>/dev/null)\"; "
    # CLOCKS. `clk <domain> <field> <value>`, kHz for cpu<N>, Hz for gpu.
    "for p in " + CPUFREQ_DIR + "/policy*; do [ -d $p ] || continue; "
    "for f in scaling_cur_freq scaling_max_freq cpuinfo_max_freq; do "
    "echo \"clk cpu${p##*policy} $f $(cat $p/$f 2>/dev/null)\"; done; done; "
    "for f in gpuclk max_gpuclk throttling; do [ -f " + KGSL_DIR + "/$f ] && "
    "echo \"clk gpu $f $(cat " + KGSL_DIR + "/$f 2>/dev/null)\"; done; "
    "echo end"
)

# See POWER. The USB input assumed when only its limit was read, and the
# charging power with no input above which a sample's sign is suspect.
USB_NOMINAL_V = 5.0
SIGN_SLACK_W = 0.25

# Read-only: each zone's trips, and which cooling devices each zone binds
# (thermal_zoneN/cdevM -> ../cooling_deviceK, with cdevM_trip_point naming
# the trip that drives it).
TRIPS_SH = (
    "for z in /sys/class/thermal/thermal_zone*; do n=${z##*thermal_zone}; "
    "echo \"tz $n $(cat $z/temp 2>/dev/null) $(cat $z/type 2>/dev/null)\"; "
    "for t in $z/trip_point_*_temp; do [ -f $t ] || continue; k=${t##*trip_point_}; k=${k%_temp}; "
    "echo \"trip $n $k $(cat $t 2>/dev/null) $(cat $z/trip_point_${k}_hyst 2>/dev/null || echo -) $(cat $z/trip_point_${k}_type 2>/dev/null)\"; done; "
    "for c in $z/cdev[0-9]*; do [ -L $c ] || continue; m=${c##*cdev}; "
    "echo \"bind $n $(cat $z/cdev${m}_trip_point 2>/dev/null) ${m} $(basename $(readlink $c)) $(cat $c/type 2>/dev/null)\"; done; "
    "done; echo end"
)


def adb_shell(serial, script, timeout=30):
    """(stdout, error or None)"""
    try:
        p = subprocess.run(["adb", "-s", serial, "shell", script], capture_output=True,
                           text=True, errors="replace", timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as e:
        return "", "adb: %s" % e.__class__.__name__
    out = p.stdout.replace("\r", "")
    if p.returncode != 0 or not re.search(r"^end$", out, re.M):
        return out, "adb: exit %d, %s" % (p.returncode, (p.stderr or out).strip().splitlines()[:1])
    return out, None


def parse_sample(text):
    s = {"dev_time": None, "up": None, "cool": [], "tz": []}
    for line in text.splitlines():
        m = re.match(r"now (\d\d-\d\d \d\d:\d\d:\d\d) up ([\d.]+)", line)
        if m:
            s["dev_time"], s["up"] = m.group(1), float(m.group(2))
            continue
        m = re.match(r"cd (\d+) (-?\d+) (-?\d+) (.*)$", line)
        if m:
            s["cool"].append([int(m.group(1)), m.group(4).strip(), int(m.group(2)), int(m.group(3))])
            continue
        # A pause device whose cur_state or max_state read failed: dropping
        # it would read the sample as clean, so the sample is unread.
        if line.startswith("cd ") and any(p in line for p in PAUSE_PREFIXES):
            s["bad_pause"] = line.strip()
            continue
        m = re.match(r"tz (\d+) (-?\d+) (.*)$", line)
        if m:
            s["tz"].append([int(m.group(1)), m.group(3).strip(), int(m.group(2))])
            continue
        # An empty value is a field that did not read: left out, never 0.
        m = re.match(r"ps (\S+) (\S+) (\S.*)$", line)
        if m:
            val = m.group(3).strip()
            s.setdefault("pw", {}).setdefault(m.group(1), {})[m.group(2)] = \
                int(val) if re.fullmatch(r"-?\d+", val) else val
            continue
        m = re.match(r"ths .*Thermal Status:\s*(\d+)", line)
        if m:
            s.setdefault("pw", {})["thermal_status"] = int(m.group(1))
            continue
        m = re.match(r"fan (\S+) (-?\d+)$", line)
        if m:
            s.setdefault("fan", {})[m.group(1)] = int(m.group(2))
            continue
        # A clock that did not read has no value and no match: left out.
        m = re.match(r"clk (\S+) (\S+) (-?\d+)$", line)
        if m:
            s.setdefault("clk", {}).setdefault(m.group(1), {})[m.group(2)] = int(m.group(3))
    return s


def clk_mhz(domain, hz):
    """A clock reading in MHz: cpufreq is in kHz, kgsl in Hz."""
    return hz / 1e3 if domain.startswith("cpu") else hz / 1e6


def clock_range(recs):
    """'clock MHz cpu0 300-2016, cpu7 1037-3187 of 3187, gpu 220-719 of 719,
    gpu throttling 1' over every sample that read a clock, or None. Each
    domain: min-max of its current clock, then `of` the lowest ceiling any
    sample read (scaling_max_freq, else cpuinfo_max_freq; max_gpuclk). A
    minimum well under that ceiling with no cooling device set is LMh/DCVS
    at work, or an idle core: the fps beside it says which."""
    cur, cap, thr = {}, {}, set()
    for r in recs:
        for dom, f in (r.get("clk") or {}).items():
            c = f.get("scaling_cur_freq", f.get("gpuclk"))
            if isinstance(c, int):
                cur.setdefault(dom, []).append(c)
            m = f.get("scaling_max_freq", f.get("cpuinfo_max_freq", f.get("max_gpuclk")))
            if isinstance(m, int):
                cap[dom] = min(cap.get(dom, m), m)
            if isinstance(f.get("throttling"), int):
                thr.add(f["throttling"])
    if not cur:
        return None
    key = lambda d: (d == "gpu", int(d[3:]) if d[3:].isdigit() else 0, d)
    parts = ["%s %.0f-%.0f%s" % (d, clk_mhz(d, min(v)), clk_mhz(d, max(v)),
                                 " of %.0f" % clk_mhz(d, cap[d]) if d in cap else "")
             for d, v in sorted(cur.items(), key=lambda kv: key(kv[0]))]
    if thr:
        parts.append("gpu throttling %s" % "/".join(map(str, sorted(thr))))
    return "clock MHz " + ", ".join(parts)


def fan_range(recs):
    """'fan duty 13700-29000 of 50000[ at fan_mode 4]' over every sample that
    read the fan, or None. The modes are every fan_mode a sample read."""
    fs = [r["fan"] for r in recs if isinstance((r.get("fan") or {}).get("duty"), int)]
    if not fs:
        return None
    ds = [f["duty"] for f in fs]
    periods = sorted({f["period"] for f in fs if isinstance(f.get("period"), int)})
    modes = sorted({f["mode"] for f in fs if isinstance(f.get("mode"), int)})
    return "fan duty %d-%d%s%s" % (min(ds), max(ds),
                                   " of %s" % "/".join(map(str, periods)) if periods else "",
                                   " at fan_mode %s" % "/".join(map(str, modes)) if modes else "")


def sample(serial, label=None):
    out, err = adb_shell(serial, SAMPLE_SH)
    s = parse_sample(out) if not err else {"dev_time": None, "up": None, "cool": [], "tz": []}
    if not err and s["dev_time"] is None:
        err = "no clock line in the device's answer"
    if not err and s.get("bad_pause"):
        err = "pause device unreadable: %s" % s["bad_pause"]
    rec = {"t": round(time.time(), 1), "label": label}
    rec.update(s)
    if err:
        rec["error"] = err
    rec["pause"] = paused(rec)
    return rec


def pause_devices(rec):
    """[(type, cur, max)] for every pause device with cur_state > 0."""
    return [(c[1], c[2], c[3]) for c in rec.get("cool") or []
            if c[1].startswith(PAUSE_PREFIXES) and c[2] > 0]


def paused(rec):
    """True, False, or None when the sample holds no reading (adb failed)."""
    if rec.get("error") or not rec.get("cool"):
        return None if rec.get("error") else False
    return bool(pause_devices(rec))


def dev_ts(rec):
    """Device time as title_verdict.py's ts() reads a logcat stamp."""
    if not rec.get("dev_time"):
        return None
    return dt.datetime.strptime("2000-" + rec["dev_time"], "%Y-%m-%d %H:%M:%S").timestamp()


def load(path):
    recs = []
    try:
        with open(path, errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    recs.append(json.loads(line))
                except ValueError:
                    continue
    except OSError:
        return None
    return recs


def episodes(recs):
    """Each pause episode, as a dict in device time (see A PAUSE EPISODE):
    after (last clean sample before, or None), first, last (paused samples),
    before (first clean sample after, or None), devices. Samples with no
    reading neither start, extend nor end an episode, so they widen it."""
    pts = [(dev_ts(r), paused(r), r) for r in recs]
    pts = [p for p in pts if p[0] is not None and p[1] is not None]
    pts.sort(key=lambda p: p[0])
    out, cur, last_clean = [], None, None
    for t, p, r in pts:
        if p:
            if cur is None:
                cur = {"after": last_clean, "first": t, "last": t, "before": None,
                       "first_rec": r, "devices": {}}
                out.append(cur)
            cur["last"] = t
            for typ, c, mx in pause_devices(r):
                cur["devices"][typ] = "%d/%d" % (c, mx)
        else:
            if cur is not None:
                cur["before"] = t
                cur = None
            last_clean = t
    return out


def overlaps(ep, lo, hi):
    """Could this episode have covered any part of (lo, hi)?"""
    a = ep["after"] if ep["after"] is not None else float("-inf")
    b = ep["before"] if ep["before"] is not None else float("inf")
    return a < hi and b > lo


def in_window(recs, lo, hi):
    """Episodes that may overlap device-time window (lo, hi)."""
    return [e for e in episodes(recs) if overlaps(e, lo, hi)]


def coverage(recs, lo, hi, t0=None):
    """None when readable samples cover device-time window (lo, hi) (see A
    WINDOW IS COVERED), else the gap, relative to t0 (default lo), as a phrase."""
    ts = sorted(dev_ts(r) for r in recs if paused(r) is not None and dev_ts(r) is not None)
    t0 = lo if t0 is None else t0
    rel = lambda t: "%+.0f s" % (t - t0)
    if not ts or ts[-1] < hi - END_SLACK_S:
        return "no reading at or after the window's end %s (last %s)" % (
            rel(hi), rel(ts[-1]) if ts else "none")
    before = [t for t in ts if t <= lo]
    chain = [before[-1] if before else lo] + [t for t in ts if lo < t < hi]
    after = [t for t in ts if t >= hi]
    if after:
        chain.append(after[0])
    for a, b in zip(chain, chain[1:]):
        if b - a > MAX_GAP_S:
            return "no reading from %s to %s (%.0f s > %d s)" % (rel(a), rel(b), b - a, MAX_GAP_S)
    return None


def describe(ep, t0=None):
    """`thermal-pause-F8 1/1 began after +220 s and by +250 s (device 09-27 13:04:10)`"""
    # %+: an episode in the cool-down samples lies before +0 and reads -60 s.
    rel = (lambda t: "%+.0f s" % (t - t0)) if t0 is not None else (lambda t: "%.0f" % t)
    began = ("after %s and by %s" % (rel(ep["after"]), rel(ep["first"]))
             if ep["after"] is not None else "by %s (paused in the first reading)" % rel(ep["first"]))
    ended = ("; cleared by %s" % rel(ep["before"])) if ep["before"] is not None \
        else "; still paused at the last reading"
    return "%s began %s (device %s)%s" % (
        ",".join("%s %s" % kv for kv in sorted(ep["devices"].items())) or PAUSE_PREFIX,
        began, ep["first_rec"].get("dev_time"), ended)


def origin(ok):
    """+0 s: the readable `start` sample (just before `am start`), not a
    cool-down sample before it; else the first readable sample."""
    starts = [dev_ts(r) for r in ok if r.get("label") == "start"]
    return min(starts) if starts else min(dev_ts(r) for r in ok)


def summary(recs):
    ok = [r for r in recs if paused(r) is not None and dev_ts(r) is not None]
    if not ok:
        return "THERMAL: unread -- no sample with a reading in %d lines" % len(recs)
    t0 = origin(ok)
    eps = episodes(recs)
    hot = max((z[2] for r in ok for z in r.get("tz") or []), default=None)
    fails = len(recs) - len(ok)
    tail = "; %d samples, %d unread, hottest zone %s" % (
        len(recs), fails, ("%.1f C" % (hot / 1000.0 if abs(hot) > 1000 else hot)) if hot is not None else "-")
    # From `start` to the last reading: the run, not the cool-down before it.
    pw = power_over(recs, t0, max(dev_ts(r) for r in ok))
    if pw["measured"]:
        tail += "; battery %+.2f W (+ is discharging)" % pw["battery_w"]
        if pw["net_w"] is not None:
            tail += ", usb in %.2f W, net %.2f W" % (pw["usb_w"], pw["net_w"])
    clk = clock_range(ok)
    if clk:
        tail += "; " + clk
    fan = fan_range(ok)
    if fan:
        tail += "; " + fan
    if not eps:
        return "THERMAL: no thermal-pause device above 0" + tail
    # An episode the cool-down gate waited out cannot touch a scored window.
    return "THERMAL: pause " + " | ".join(
        describe(e, t0) + (" [in the cool-down, over before the start]"
                           if e["before"] is not None and e["before"] <= t0 else "")
        for e in eps) + tail


def diff(a, b):
    """Cooling devices whose cur_state rose from sample a to sample b."""
    before = {(c[0], c[1]): c[2] for c in a.get("cool") or []}
    return ["%s(cd%d) %d->%d/%d" % (c[1], c[0], before.get((c[0], c[1]), 0), c[2], c[3])
            for c in b.get("cool") or [] if c[2] > before.get((c[0], c[1]), 0)]


def zone_c(rec, zone):
    """The first zone of this type in a sample, in C, or None."""
    for z in rec.get("tz") or []:
        if z[1] == zone:
            return z[2] / 1000.0 if abs(z[2]) > 1000 else float(z[2])
    return None


def cool(rec, zone, limit_c):
    """(exit code, phrase) for THE COOL-DOWN GATE."""
    if paused(rec) is None:
        return 2, "unread: %s" % (rec.get("error") or "no reading")
    c = zone_c(rec, zone)
    if c is None:
        return 2, "no %s zone" % zone
    if paused(rec):
        return 1, "%s %.1f C, paused (%s)" % (
            zone, c, ",".join("%s %d/%d" % d for d in pause_devices(rec)))
    if c >= limit_c:
        return 1, "%s %.1f C >= %g C" % (zone, c, limit_c)
    return 0, "%s %.1f C < %g C" % (zone, c, limit_c)


def first_episode(recs):
    """(episode, origin): the run's first pause episode and the origin() it is
    timed from, or None when no pause was sampled. An episode the cool-down
    gate waited out, over before the start, is not the run's. See A PAUSE
    EPISODE."""
    ok = [r for r in recs if paused(r) is not None and dev_ts(r) is not None]
    if not ok:
        return None
    t0 = origin(ok)
    eps = [e for e in episodes(recs) if e["before"] is None or e["before"] > t0]
    return (eps[0], t0) if eps else None


def first_pause(recs):
    """(after, by): first_episode()'s onset bounds in seconds from the run's
    origin() (after is None when the run started paused), or None when no
    pause was sampled."""
    fe = first_episode(recs)
    if fe is None:
        return None
    e, t0 = fe
    if e["first"] <= t0:
        return (None, 0.0)
    return (round(e["after"] - t0, 1) if e["after"] is not None else None, round(e["first"] - t0, 1))


def power(rec):
    """One sample's power, see POWER: dict(battery_w, usb_w, usb_from,
    suspect), or None when the battery's current or voltage did not read."""
    pw = rec.get("pw") or {}
    bat, usb = pw.get("battery") or {}, pw.get("usb") or {}
    i, v = bat.get("current_now"), bat.get("voltage_now")
    if not isinstance(i, int) or not isinstance(v, int):
        return None
    out = {"battery_w": -(i * v) / 1e12, "usb_w": None, "usb_from": None}
    ui, uv = usb.get("current_now"), usb.get("voltage_now")
    if isinstance(ui, int) and isinstance(uv, int):
        out.update(usb_w=(ui * uv) / 1e12, usb_from="usb current_now x voltage_now")
    elif usb.get("online") == 0:
        out.update(usb_w=0.0, usb_from="usb offline")
    elif isinstance(usb.get("input_current_limit"), int):
        out.update(usb_w=usb["input_current_limit"] * USB_NOMINAL_V / 1e6,
                   usb_from="upper bound: input_current_limit x %g V" % USB_NOMINAL_V)
    out["suspect"] = bool(out["usb_w"] is not None and out["usb_w"] < SIGN_SLACK_W
                          and out["battery_w"] < -SIGN_SLACK_W)
    return out


def mean_over(pts, lo, hi):
    """Time-weighted mean over (lo, hi) of the piecewise-linear curve through
    pts [(t, value)], held flat outside them. See POWER, THE AVERAGE."""
    pts = sorted(pts)
    if not pts or hi <= lo:
        return None

    def at(t):
        if t <= pts[0][0]:
            return pts[0][1]
        if t >= pts[-1][0]:
            return pts[-1][1]
        for (a, va), (b, vb) in zip(pts, pts[1:]):
            if a <= t <= b:
                return va if b == a else va + (vb - va) * (t - a) / (b - a)

    ts = [lo] + [t for t, _ in pts if lo < t < hi] + [hi]
    area = sum((at(a) + at(b)) / 2.0 * (b - a) for a, b in zip(ts, ts[1:]))
    return area / (hi - lo)


def power_over(recs, lo, hi):
    """Average power over device-time window (lo, hi), see POWER. `samples`
    counts the readings inside the window; with none, the window's power was
    not measured, whatever the readings outside it say."""
    pts = [(dev_ts(r), power(r), r) for r in recs or [] if dev_ts(r) is not None]
    pts = [p for p in pts if p[1] is not None]
    inside = [p for p in pts if lo <= p[0] <= hi]
    out = dict(measured=bool(inside), samples=len(inside),
               sign="battery_w: + discharging, - charging; net_w = battery_w + usb_w",
               battery_w=None, usb_w=None, usb_from=None, usb_bound=None, net_w=None,
               sign_suspect=sum(1 for p in inside if p[1]["suspect"]),
               thermal_status_max=max((p[2]["pw"]["thermal_status"] for p in inside
                                       if isinstance(p[2]["pw"].get("thermal_status"), int)),
                                      default=None))
    if not inside or hi <= lo:
        out["measured"] = False
        return out
    out["battery_w"] = round(mean_over([(t, p["battery_w"]) for t, p, _ in pts], lo, hi), 3)
    froms = sorted({p["usb_from"] for _, p, _ in pts if p["usb_from"]})
    if froms and all(p["usb_w"] is not None for _, p, _ in pts):
        out["usb_w"] = round(mean_over([(t, p["usb_w"]) for t, p, _ in pts], lo, hi), 3)
        out["usb_from"] = "; ".join(froms)
        # One bounded sample makes the average, and net_w with it, a bound.
        out["usb_bound"] = any(f.startswith("upper bound") for f in froms)
        out["net_w"] = round(out["battery_w"] + out["usb_w"], 3)
    return out


def read_one(arg):
    """A sample from a JSON string, or the last line of a file."""
    if os.path.isfile(arg):
        recs = load(arg) or []
        if not recs:
            raise SystemExit("thermal_state: no JSON line in %s" % arg)
        return recs[-1]
    return json.loads(arg)


def trips(serial):
    out, err = adb_shell(serial, TRIPS_SH, timeout=60)
    if err:
        raise SystemExit("thermal_state --trips: " + err)
    zones = {}
    for line in out.splitlines():
        m = re.match(r"tz (\d+) (-?\d*) (.*)$", line)
        if m:
            zones[int(m.group(1))] = {"type": m.group(3).strip(), "temp": m.group(2), "trips": [], "binds": []}
            continue
        m = re.match(r"trip (\d+) (\d+) (-?\d*) (\S+) (.*)$", line)
        if m and int(m.group(1)) in zones:
            zones[int(m.group(1))]["trips"].append(
                {"n": int(m.group(2)), "temp": m.group(3), "hyst": m.group(4), "type": m.group(5).strip()})
            continue
        m = re.match(r"bind (\d+) (-?\d*) (\d+) (\S+) (.*)$", line)
        if m and int(m.group(1)) in zones:
            zones[int(m.group(1))]["binds"].append(
                {"trip": m.group(2), "cdev": m.group(4), "type": m.group(5).strip()})
    return zones


def main(argv):
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0 if argv else 2
    if argv[0] == "--diff" and len(argv) == 3:
        rose = diff(read_one(argv[1]), read_one(argv[2]))
        print("\n".join(rose) if rose else "no cooling device rose")
        return 0
    if argv[0] == "--summary" and len(argv) == 2:
        recs = load(argv[1])
        print(summary(recs) if recs is not None else "THERMAL: unread -- %s is missing" % argv[1])
        return 0
    if argv[0] == "--window" and len(argv) == 4:
        recs = load(argv[1])
        ok = [r for r in recs or [] if paused(r) is not None and dev_ts(r) is not None]
        if not ok:
            print("unread: no sample with a reading")
            return 2
        t0 = origin(ok)
        lo, hi = t0 + float(argv[2]), t0 + float(argv[3])
        hit = in_window(recs, lo, hi)
        for e in hit:
            print("thermal-pause: " + describe(e, t0))
        if hit:
            return 0
        gap = coverage(recs, lo, hi, t0)
        if gap:
            print("unread: " + gap)
            return 2
        print("no pause may overlap +%s..+%s s" % (argv[2], argv[3]))
        return 1
    if argv[0] == "--cool" and len(argv) == 4:
        recs = load(argv[1]) or []
        rc, phrase = cool(recs[-1], argv[2], float(argv[3])) if recs else (2, "unread: no sample")
        print(phrase)
        return rc
    if argv[0] == "--power" and len(argv) == 4:
        recs = load(argv[1]) or []
        ok = [r for r in recs if paused(r) is not None and dev_ts(r) is not None]
        if not ok:
            print("unread: no sample with a reading")
            return 2
        t0 = origin(ok)
        pw = power_over(recs, t0 + float(argv[2]), t0 + float(argv[3]))
        print(json.dumps(pw, sort_keys=True))
        return 0 if pw["measured"] else 2
    if argv[0] == "--trips" and len(argv) == 2:
        zones = trips(argv[1])
        print(json.dumps({"serial": argv[1], "zones": zones}, sort_keys=True))
        return 0
    label = None
    if "--label" in argv:
        i = argv.index("--label")
        label = argv[i + 1] if i + 1 < len(argv) else None
        argv = argv[:i] + argv[i + 2:]
    if len(argv) != 1 or argv[0].startswith("-"):
        print(__doc__, file=sys.stderr)
        return 2
    rec = sample(argv[0], label)
    print(json.dumps(rec, separators=(",", ":")))
    return 1 if rec.get("error") else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
