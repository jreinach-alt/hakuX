#!/usr/bin/env python3
"""The device's thermal state in one adb call, and whether a pause overlaps a window (#507).

    thermal_state.py <serial> [--label L]       one JSON line: every cooling device, every zone
    thermal_state.py --trips <serial>           every zone's trip points and bound cooling devices
    thermal_state.py --diff A B                 cooling devices whose cur_state rose from A to B
    thermal_state.py --summary FILE.jsonl       one `THERMAL:` line for run.log
    thermal_state.py --window FILE.jsonl LO HI  is a pause possible inside LO..HI s after
                                                FILE's first sample? exit 0 yes, 1 no, 2 unread

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
    "done; echo end"
)

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
    return s


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
    rel = (lambda t: "+%.0f s" % (t - t0)) if t0 is not None else (lambda t: "%.0f" % t)
    began = ("after %s and by %s" % (rel(ep["after"]), rel(ep["first"]))
             if ep["after"] is not None else "by %s (paused in the first reading)" % rel(ep["first"]))
    ended = ("; cleared by %s" % rel(ep["before"])) if ep["before"] is not None \
        else "; still paused at the last reading"
    return "%s began %s (device %s)%s" % (
        ",".join("%s %s" % kv for kv in sorted(ep["devices"].items())) or PAUSE_PREFIX,
        began, ep["first_rec"].get("dev_time"), ended)


def summary(recs):
    ok = [r for r in recs if paused(r) is not None and dev_ts(r) is not None]
    if not ok:
        return "THERMAL: unread -- no sample with a reading in %d lines" % len(recs)
    t0 = min(dev_ts(r) for r in ok)
    eps = episodes(recs)
    hot = max((z[2] for r in ok for z in r.get("tz") or []), default=None)
    fails = len(recs) - len(ok)
    tail = "; %d samples, %d unread, hottest zone %s" % (
        len(recs), fails, ("%.1f C" % (hot / 1000.0 if abs(hot) > 1000 else hot)) if hot is not None else "-")
    if not eps:
        return "THERMAL: no thermal-pause device above 0" + tail
    return "THERMAL: pause " + " | ".join(describe(e, t0) for e in eps) + tail


def diff(a, b):
    """Cooling devices whose cur_state rose from sample a to sample b."""
    before = {(c[0], c[1]): c[2] for c in a.get("cool") or []}
    return ["%s(cd%d) %d->%d/%d" % (c[1], c[0], before.get((c[0], c[1]), 0), c[2], c[3])
            for c in b.get("cool") or [] if c[2] > before.get((c[0], c[1]), 0)]


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
        ok = [dev_ts(r) for r in recs or [] if paused(r) is not None and dev_ts(r) is not None]
        if not ok:
            print("unread: no sample with a reading")
            return 2
        t0 = min(ok)
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
