#!/usr/bin/env python3
"""title_verdict.py <result-dir> [--require screening|confirmation]
                                 [--reviewed-gameplay yes|no] [--targets FILE]

Judge one title soak: read run.log, logcat.txt, request.json/result.json and
titles/targets.toml, write verdict.json beside them, print one line.

THE BAR (the owner, 2026-09-25). A run passes when the title
  - booted, and reached gameplay by its route (`mark gameplay` in logcat,
    then at least one guest flip after it);
  - played for the required window after the mark (600 s screening,
    600 s confirmation by default -- see CONFIRMATION LENGTH below) with no
    crash, no hang and no real exit;
  - ran at >= 30 fps for >= 90% of the gameplay time;
  - played its audio with no dropouts (see AUDIO below);
  - did not hitch, and was actually gameplay the whole scored window (see
    HITCHES and WHOLE-WINDOW LIVENESS below).
A pass at surface_scale 1 is the `Playable` rating, at 2 `Playable (2x)`.
`Perfect` is a human's call: `human_review` is written empty and nothing here
ever fills it.

HITCHES AND WHOLE-WINDOW LIVENESS (the owner, 2026-10-01, #433). A frame-rate
pass is not a smooth pass: the TIME-weighted fps share above can pass a 600 s
window carrying one sub-second stall, which is exactly what the owner saw
playing Sonic Heroes and the share could not. `hitch_report.py` (its module
doc has the counters and the rule) lists every hitch in the scored window
from hakuX-pace/[shd413]/[rdc] already in logcat.txt, classifies each as
shader, texture, both or unexplained, and fails the run as "hitches" past the
owner's bars, unless the title's targets.toml entry carries `hitch_allowance`.
Separately, `static_window()` catches a scored window that never left a menu
(Super Monkey Ball and Castlevania both scored PASS on one, because
`reached_gameplay` only reads the mark frame) by asking whether the window's
own route-frames ever drift from their first frame; see that module's doc
for why a plain frame-to-frame diff does not separate a looping menu
animation from real gameplay, and NOTES.md for the survey of titles these
bars do and do not separate.

TIMELINE (the owner, 2026-10-01, #433: "we're getting bad FPS data if half
the time is spent in a menu"). A route whose play is a `drive` step
(titles/drive.py) writes `hakuX-route: state=<s> t=<n>` to logcat on every
change of the screen it sees (play, paused, main_menu, cutscene, stalled ...).
From those lines, over the scored window (mark to `soak end`):
  - `timeline.play_share` = seconds in `play` / scored seconds, with the
    seconds per state in `timeline.by_state`. A confirmation whose
    play_share is under `play_share_min` (targets.toml [defaults], else 0.90)
    FAILS as "menu time", named before the fps bar because it is why the fps
    data would be wrong.
  - fps is judged over `play` seconds only: a perf window counts when its
    midpoint lies in a `play` span. `timeline.fps_excluded_s` and
    `fps_excluded_windows` say how much was left out.
A route with no `drive` step (the blind routes) writes no state line and is
judged exactly as before; `timeline` reads "none" and the printed line says
`timeline: none`.

CONFIRMATION LENGTH (the owner, 2026-09-30, #433). Re-scoring every
full-length confirmation as if cut at 300 s and 600 s found no verdict
change on the Nova (6/6 runs, which plateaus near 49 C and never pauses) at
5 or 10 minutes; on the Thor, Azurik read 99.6% at 10 minutes and failed at
15.6 minutes on the heat pause. So `confirmation_s` defaults to 600 s
(targets.toml `[defaults]`), 20 minutes only where it earns its cost:
  - a title flagged for slow-building defects (Forza's invalid-list decay
    and memory growth, Kabuki Warriors' random stalls) carries its own
    `confirmation_s = 1200` in targets.toml;
  - a run whose scored window was STILL HEATING at the end -- its last 180 s
    show xo-therm or the battery zone rising faster than 1.0 C/min, or a
    thermal pause overlapped it -- needs the full 1200 s regardless of the
    title's own confirmation_s, because a device still climbing may pause
    minutes after a short window ends. Such a run reads
    "confirmation: 1200 s needed -- the device was still heating at the end".
Process, not code: lane.verdict433 re-runs every 5th 600-s pass at the full
1200 s, as an audit. Existing verdicts are not re-judged: a pass already
recorded at 1200 s stays a pass.

FRAME RATE: WHICH FIELD, AND WHY NOT G. hakuX-perf (pgraph/profile.c) prints
one line every 60 guest FLIP_STALLs -- `g_nv2a_stats.frame_count` counts
flips, not host frames. So the time between two consecutive lines IS the
time those 60 guest frames took, and 60 / dt is an exact per-window frame
rate from logcat's own timestamps. That is the number judged here.
  - G is `game_frame_ms`, an exponential average (x0.8 + x0.2 per frame): it
    carries the past into every window and lags a stall by several windows.
    It is reported, never judged.
  - gfps is `increment_fps`, counted over the last >= 250 ms before the
    line: a quarter-second sample of a two-second window. Reported only.
The share is TIME-weighted (seconds of gameplay in windows at or above the
bar, over all gameplay seconds). Counting windows would under-weight exactly
the slow stretches, because a 60-frame window at 10 fps lasts six times as
long as one at 60. The window-count share is reported beside it.

HANG: no hakuX-perf line for more than 10 s after the mark while the process
lived -- i.e. fewer than 60 guest flips in 10 s. The trailing gap (last line
to `soak end`) counts too, unless the process died, which is a crash.

CAPTURE GAPS. soak_title.sh restarts a dropped logcat stream and writes a
CAPTURE_BREAK line into logcat.txt where it did. The restart asks the ring for
everything from the last captured stamp, so a restart that reprints the last
line before the break lost nothing (the ring evicts oldest first); one that
does not is a gap, from the last line before the break to the first after,
in device time. Nothing is known about the guest inside a gap, so a gap is
neither a hang nor slow frames: a window spanning one is not scored, and a
hang gap is measured with the capture gap subtracted. Exact duplicate lines
(the replayed overlap) are read once. The gaps are reported, never judged.
A break that no line follows, in a capture with no `soak end`, is a
TRUNCATED capture: the restarts ran out and the rest of the run is unseen.
That run is not judged on what little was captured -- it fails as
`capture: truncated`, named first, so a short capture never reads as a short
run or a missing mark. `capture_truncated_s` estimates the unseen span from
`soak start` plus the hold run.log reports (host clock, so approximate).

DISPLAY. A run whose display 0 was not hakuX's is VOID, not slow: `void`
names why, it is the first failure, and every fps field is null. Two ways in:
soak_title.sh refused to start (`display-covered:` in run.log, from
devices.sh display_clear), or every route frame is under 12 KB (a 1920x1080
all-black PNG is 10,899 B; `display-black:` in run.log, or the frames
themselves). On 2026-09-27 a foreign overlay on the Thor's display 0 did both.
A third: the route was aborted because hakuX did not hold display 0 and
input focus (`not-foreground:` in run.log, from soak_title.sh's foreground
guard); its input went to, or would have gone to, another app.
A fourth: the device was THERMALLY PAUSED inside the scored window
(thermal.jsonl, from soak_title.sh's thermal_state.py samples, #507). Under
MAX the Thor's kernel pauses cpu3-7 a few minutes in and fps falls 5-7x; that
is the device's temperature, not the title's frame rate. A pause is sampled
every 30 s, so its span is bounded by the clean samples either side, and a
window that span may overlap is void (thermal_state.py, A PAUSE EPISODE). So
is a window the readable samples do not cover (`thermal-unread:`, A WINDOW IS
COVERED): adb failing after a pause began would otherwise read as clean. A
run with no thermal.jsonl is judged as before, with `thermal.measured` false.
`thermal.first_pause_s` is the time from the run's start (the `start` sample,
just before `am start`) to the first pause, as the two bounds sampling gives:
`after` (the last clean reading) and `by` (the first paused one).
UNDER THE DEVICE'S DEFAULTS the pause is not a fault of the measurement but
the thing measured. A run whose perf_regimen.json says `regimen: default`
(soak_title.sh PERF_REGIMEN=default: performance_mode 0, fan SMART) is not
voided by a pause; it FAILS, `thermal.failed_sustained` is true, and the
failure names the pause and when it began, from the run's start. Its fps
windows stand: they are what a player at the defaults got. Any pause from the
start on counts, in or out of the scored window (one the cool-down gate waited
out before the start does not). The owner's ruling, 2026-09-27 (#433):
Playable is sustained play in the heat budget, and the fps bar is unchanged.
`failed_sustained` is null when the run is not a `default` run or no sample
read; a `default` run whose window is `thermal-unread` is still void.

POWER (`power`, from the same samples; thermal_state.py, POWER). Reaching the
frame rate by heating the handheld until it pauses is not playing, so a run
reports what its frames cost, over the scored window (mark to `soak end`):
  - `battery_w`: average battery power. SIGN: + the battery is DISCHARGING,
    - it is CHARGING.
  - `usb_w`: the USB input, and `usb_from`, how it was read (a measurement,
    or an upper bound from the input current limit). `usb_bound` true means
    usb_w, net_w and j_per_frame are upper bounds.
  - `net_w` = battery_w + usb_w: what the device drew.
  - `j_per_frame` = net_w x scored seconds / guest flips, and
    `j_per_frame_battery` the same from battery_w alone. Scored seconds and
    flips are those of the fps windows, so a capture gap costs both alike.
Reported, never judged: no bar is set on it yet. A void run reports its
watts and no J per frame (its flips are not the title's), and so does a
window holding a reading the sign convention cannot explain (`sign_suspect`).
Samples older than this field give `power.measured` false, never 0 W.
Black frames are NOT void when run.log says `render-black:`: the soak
re-ran display_clear and hakux_in_front at the end of the hold and both were
clear, so hakuX itself drew black. That run is judged (its fps stands) and
fails on the `render-black:` line, a title failure rather than a re-queue.

AUDIO: the APU's `starve:` lines (hakuX-audiocap) each carry the callbacks
and the short callbacks since the previous line. The share is short/total
over lines stamped more than 10 s after the mark. No starve line there at
all means the instrument said nothing -- `audio_measured: false`, and a run
the ruler cannot hear does not pass.
"""
import argparse
import datetime as dt
import glob
import json
import os
import re
import sys

try:
    import tomllib
except ImportError:            # python < 3.11
    tomllib = None

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import thermal_state  # noqa: E402
import hitch_report  # noqa: E402
DEFAULT_TARGETS = os.path.join(HERE, "titles", "targets.toml")

# `logcat -v time`: "09-25 13:31:41.662 I/hakuX-perf( 1234): gfps=30 G:..."
LINE = re.compile(r"^(\d\d-\d\d \d\d:\d\d:\d\d\.\d{3})\s+([VDIWEF])/([^(\s]+)\s*\(\s*(\d+)\):\s?(.*)$")
PERF = re.compile(r"gfps=(\d+)\s+G:([\d.]+)\(([\d.]+)-([\d.]+)\)")
STARVE = re.compile(r"starve: (\d+)/(\d+) callbacks short \((\d+) empty\)")
SCALE = re.compile(r"surface_scale=(\d+)")
CAPTURE_BREAK = "# hakuX-capture: stream ended"   # soak_title.sh writes it
BLACK_FRAME_B = 12288      # a 1920x1080 all-black PNG is 10,899 B

FRAMES_PER_LINE = 60          # profile.c: frame_count % 60
HANG_S = 10.0
AUDIO_SKIP_S = 10.0

# STILL HEATING (see CONFIRMATION LENGTH in the module doc, #433).
HEATING_WINDOW_S = 180.0
HEATING_RATE_C_PER_MIN = 1.0
HEATING_ZONES = ("xo-therm", "battery")


def ts(stamp):
    # Year 2000 is a leap year, so a 02-29 stamp parses; only differences
    # are used. A run spanning New Year would need the year, and none does.
    return dt.datetime.strptime("2000-" + stamp, "%Y-%m-%d %H:%M:%S.%f").timestamp()


def load_json(path):
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def load_targets(path):
    if not os.path.isfile(path):
        return {}
    if tomllib is None:
        raise SystemExit("title_verdict: python has no tomllib; need 3.11+")
    with open(path, "rb") as f:
        return tomllib.load(f)


def find_title(targets, iso):
    """(title_id, entry) for the ISO the request named, or (None, {}).
    An ISO no entry's `iso` map names, but whose file name leads with a
    registered title ID (`<TID>-<Name>.xiso.iso`, the pipeline's), is that
    title: a verdict scored before the map listed it must not come out
    nameless (#397, 2026-09-27)."""
    base = os.path.basename(iso or "")
    titles = targets.get("titles") or {}
    for tid, t in titles.items():
        isos = t.get("iso") or {}
        if base and base in [os.path.basename(v) for v in isos.values()]:
            return tid, t
    m = re.match(r"([0-9A-Fa-f]{8})-", base)
    if m and m.group(1).upper() in titles:
        return m.group(1).upper(), titles[m.group(1).upper()]
    return None, {}


def parse_logcat(path, pids=None):
    """(lines, capture gaps, open break). See CAPTURE GAPS above. The open
    break is the device time of the last line before a break that no line
    follows, else None. A list passed as `pids` gets each kept line's
    logging pid, one per line, in step with the lines."""
    out, gaps, seen = [], [], set()
    last_t = pending = None
    overlap = False
    try:
        with open(path, errors="replace") as f:
            for raw in f:
                raw = raw.rstrip("\n")
                if raw.startswith(CAPTURE_BREAK):
                    if pending is None:
                        pending, overlap = last_t, False
                    continue
                m = LINE.match(raw)
                if not m:
                    continue
                if raw in seen:
                    if pending is not None:
                        overlap = True
                    continue
                seen.add(raw)
                t = ts(m.group(1))
                if pending is not None:
                    if not overlap and t > pending:
                        gaps.append((pending, t))
                    pending = None
                out.append((t, m.group(2), m.group(3), m.group(5)))
                if pids is not None:
                    pids.append(m.group(4))
                last_t = t
    except OSError:
        pass
    return out, gaps, pending


# WHOSE CRASH. `libc` and `DEBUG` at F are the whole device's: crash_dump logs
# a tombstone under DEBUG for any native crash, and three Nova runs on
# 2026-10-02 (1790951866-titleroutes2-46925, 1790951914-titleroutes2-68595,
# 1790953776-titleroutes2-447685) failed as crashes for Android's own
# media.extractor aborting while hakuX played on; 0-0-x-1790465684-lane.remote-
# 2069760 did the same for surfaceflinger. Such a line is hakuX's only when it
# names hakuX's process or comes from it:
#  - a tombstone, from its `*** ***` line to the next, by its `Cmdline:` (or,
#    without one, its `>>> name <<<`). crash_dump logs it under its own pid.
#  - a libc line by its pid. hakuX's handler (android_crash_handler.cpp)
#    re-raises under SIG_DFL, so a hakuX crash leaves no tombstone and only
#    "FORTIFY: ..." or "exiting due to SIG_DFL handler ..." under libc, from
#    the crashing pid: every one in results/ through 2026-10-02 (the 09-29
#    memfast, ibcache and verdict433 runs) came from a pid that also logs
#    hakuX's tags. hakuX-route is not one of them: route.sh and soak_title.sh
#    write it from an adb shell.
#  - a libc "Fatal signal ... pid N (name)" also by that name, which is
#    /proc/<pid>/comm: the last 15 characters of a longer process name.
# A tombstone that names no process (a capture that starts mid-block) is not
# hakuX's: a missed crash costs a reviewer a look, a false one fails a title.
HAKUX_PROCS = tuple(p + s for p in ("com.jreinach.hakux", "com.jreinach.hakux.debug",
                                    "com.jreinach.hakux.debug2")
                    for s in ("", ":xemu"))   # build.gradle.kts; AndroidManifest.xml
TOMBSTONE_START = "*** *** ***"
TOMBSTONE_NAME = re.compile(r"^Cmdline:\s*(\S+)|>>> (\S+) <<<")
FATAL_PROC = re.compile(r"\bpid \d+ \(([^)]*)\)")


def is_hakux_proc(name):
    return any(name == p or (len(name) == 15 and p.endswith(name)) for p in HAKUX_PROCS)


def crash_lines_of(lc, pids):
    """The crash lines that are hakuX's, in log order. See WHOSE CRASH."""
    own = {p for (t, lv, tag, msg), p in zip(lc, pids)
           if tag.startswith(("hakuX", "xemu")) and tag != "hakuX-route"}
    block, names = [], {}     # tombstone number of each DEBUG/F line; its process
    for t, lv, tag, msg in lc:
        if tag == "DEBUG" and lv == "F":
            n = len(names) if msg.startswith(TOMBSTONE_START) else len(names) - 1
            if n == len(names):
                names[n] = None
            block.append(n)
            m = TOMBSTONE_NAME.search(msg)
            if m and n >= 0 and names[n] is None:
                names[n] = m.group(1) or m.group(2)
    out, k = [], 0
    for (t, lv, tag, msg), pid in zip(lc, pids):
        if tag == "hakuX-crash" and lv in "EF":
            out.append(msg)
        elif tag == "libc" and lv == "F":
            m = FATAL_PROC.search(msg)
            if pid in own or (m and is_hakux_proc(m.group(1))):
                out.append(msg)
        elif tag == "DEBUG" and lv == "F":
            n, k = block[k], k + 1
            if n >= 0 and names[n] and is_hakux_proc(names[n]):
                out.append(msg)
    return out


def lost_in(a, b, gaps):
    """Seconds of (a, b) that fall inside a capture gap."""
    return sum(max(0.0, min(b, g1) - max(a, g0)) for g0, g1 in gaps)


STATE_LINE = re.compile(r"^state=([a-z_]+) t=\d+")


def play_timeline(lc, mark_t, end_t):
    """drive.py's state timeline over the scored window, or "none" for a
    route with no `drive` step. Each `hakuX-route: state=<s>` line starts a
    span that lasts to the next one; the state in force at the mark is the
    last line before it; `state=end` (drive.py stopped) is not play."""
    changes = [(t, STATE_LINE.match(msg).group(1)) for t, lv, tag, msg in lc
               if tag == "hakuX-route" and STATE_LINE.match(msg)]
    if not changes:
        return "none"
    if mark_t is None or end_t is None or end_t <= mark_t:
        return dict(play_s=0.0, scored_s=0.0, play_share=None, by_state={}, play_spans=[], changes=len(changes))
    spans, by = [], {}
    cur = None
    for t, s in changes:
        if t <= mark_t:
            cur = s
    pts = [(mark_t, cur)] + [(t, s) for t, s in changes if mark_t < t < end_t] + [(end_t, None)]
    for (a, s), (b, _) in zip(pts, pts[1:]):
        key = s or "no-timeline"
        by[key] = by.get(key, 0.0) + (b - a)
        if s == "play":
            spans.append((a, b))
    play_s = by.get("play", 0.0)
    scored = end_t - mark_t
    return dict(play_s=round(play_s, 1), scored_s=round(scored, 1),
                play_share=round(play_s / scored, 4) if scored > 0 else None,
                by_state={k: round(x, 1) for k, x in sorted(by.items(), key=lambda kv: -kv[1])},
                play_spans=[(round(a, 3), round(b, 3)) for a, b in spans], changes=len(changes))


def in_spans(t, spans):
    return any(a <= t < b for a, b in spans)


def heating_rate(samples, zone, lo, hi):
    """C/min between `zone`'s first and last reading in device-time window
    (lo, hi), or None with fewer than two readings in it."""
    pts = sorted((thermal_state.dev_ts(r), thermal_state.zone_c(r, zone)) for r in samples)
    pts = [(t, c) for t, c in pts if t is not None and c is not None and lo <= t <= hi]
    if len(pts) < 2:
        return None
    dt_min = (pts[-1][0] - pts[0][0]) / 60.0
    return (pts[-1][1] - pts[0][1]) / dt_min if dt_min > 0 else None


SHEET_GROUPS = (("route-frames", "--- route frames ---"),
                ("frames", "--- boot samples (30 s from boot) ---"))


def contact_sheet(rdir, out_png):
    """Grid of the run's frames for a reviewer. None + reason when there is
    nothing to draw or no PIL (the jobs-selftest runner has none).

    The two sources are drawn as separate groups under their own header, so a
    boot title screen in `frames/` is never read as a second game start. Each
    tile is labelled with its own clock time (HH:MM:SS from the file name)."""
    groups = []
    for sub, header in SHEET_GROUPS:
        fs = sorted(glob.glob(os.path.join(rdir, sub, "*.png")))
        if fs:
            groups.append((header, fs))
    if not groups:
        return None, "no frames: the route took none and --frames-every was 0"
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        return None, "PIL unavailable; %d frames on disk" % sum(len(fs) for _, fs in groups)
    items = [(h, f) for h, fs in groups for f in fs]
    if len(items) > 36:           # evenly spaced over both groups, first and last kept
        step = (len(items) - 1) / 35.0
        picked = [items[round(i * step)] for i in range(36)]
        groups = []
        for h, f in picked:
            if groups and groups[-1][0] == h:
                groups[-1][1].append(f)
            else:
                groups.append((h, [f]))
    tw, th, cols, head = 320, 180, 6, 22
    height = sum(head + ((len(fs) + cols - 1) // cols) * (th + 16) for _, fs in groups)
    sheet = Image.new("RGB", (cols * tw, height), "black")
    draw = ImageDraw.Draw(sheet)
    y0 = 0
    for header, fs in groups:
        draw.text((4, y0 + 6), header, fill="yellow")
        y0 += head
        for i, f in enumerate(fs):
            x, y = (i % cols) * tw, y0 + (i // cols) * (th + 16)
            m = hitch_report.FRAME_NAME.match(os.path.basename(f))
            when = ("%s:%s:%s" % m.groups()) if m else os.path.basename(f)[:20]
            draw.text((x + 2, y + 2), when, fill="white")
            try:
                im = Image.open(f).convert("RGB")
                im.thumbnail((tw, th))
            except Exception:
                continue
            sheet.paste(im, (x, y + 16))
        y0 += ((len(fs) + cols - 1) // cols) * (th + 16)
    sheet.save(out_png)
    return os.path.basename(out_png), None


def judge(rdir, require=None, reviewed=None, targets_path=DEFAULT_TARGETS, write_contact_sheet=True):
    req = load_json(os.path.join(rdir, "request.json"))
    res = load_json(os.path.join(rdir, "result.json"))
    targets = load_targets(targets_path)
    defaults = targets.get("defaults") or {}
    bar_fps = float(defaults.get("playable_fps", 30))
    tol = float(defaults.get("fps_tolerance", 0.95))
    share_min = float(defaults.get("fps_share_min", 0.90))
    audio_max = float(defaults.get("audio_starve_max_share", 0.001))
    play_share_min = float(defaults.get("play_share_min", 0.90))

    title = req.get("title") or res.get("title") or ""
    tid, entry = find_title(targets, title)
    own_target = float(entry.get("target_fps", bar_fps))
    # CONFIRMATION LENGTH (see module doc): a title's own confirmation_s,
    # else the default; a still-heating window (computed below, once mark_t
    # and end_t are known) bumps a sub-1200 s figure up to 1200 regardless.
    need = {"screening": float(defaults.get("screening_s", 600)),
            "confirmation": float(entry.get("confirmation_s", defaults.get("confirmation_s", 600)))}

    try:
        with open(os.path.join(rdir, "run.log"), errors="replace") as f:
            runlog = f.read()
    except OSError:
        runlog = ""
    m = re.search(r"^adb_failures=(\d+)", runlog, re.M)
    adb_failures = int(m.group(1)) if m else None
    never = "guest never appeared" in runlog
    exited = re.search(r"^guest exited after (\d+)s", runlog, re.M)
    route_not_played = re.search(r"^ROUTE NOT PLAYED: (.*)$", runlog, re.M)
    route_marks_host = re.findall(r"^ROUTE \S+ mark ([A-Za-z0-9_.-]+)$", runlog, re.M)
    route_marks_failed = re.findall(r"^ROUTE \S+ mark ([A-Za-z0-9_.-]+): logcat write FAILED$", runlog, re.M)

    # VOID: the display or the input was not hakuX's (see DISPLAY above). The
    # frames on disk decide too, so a run.log older than the guard is judged
    # the same.
    void = None
    rframes = glob.glob(os.path.join(rdir, "route-frames", "*.png"))
    m = re.search(r"^(display-covered|display-black|not-foreground): .*$", runlog, re.M)
    render_black = re.search(r"^render-black: .*$", runlog, re.M)
    if m:
        void = m.group(0)
    elif render_black:
        pass    # black frames, display 0 clear and hakuX focused: hakuX's own failure
    elif rframes and all(os.path.getsize(f) < BLACK_FRAME_B for f in rframes):
        void = "display-black: all %d route frames under %d B" % (len(rframes), BLACK_FRAME_B)

    held = re.search(r"^(?:held \S.* for|guest exited after) (\d+)s", runlog, re.M)
    pids = []
    lc, cap_gaps, open_break = parse_logcat(os.path.join(rdir, "logcat.txt"), pids)
    perf = [(t, PERF.search(msg)) for t, lv, tag, msg in lc if tag == "hakuX-perf"]
    perf = [(t, p) for t, p in perf if p]
    marks = [(t, msg[5:].strip()) for t, lv, tag, msg in lc
             if tag == "hakuX-route" and msg.startswith("mark ")]
    soak_end = [t for t, lv, tag, msg in lc if tag == "hakuX-route" and msg.strip() == "soak end"]
    crash_lines = crash_lines_of(lc, pids)
    crash_warn = sum(1 for t, lv, tag, msg in lc if tag == "hakuX-crash" and lv not in "EF")
    scale = None
    for t, lv, tag, msg in lc:
        if tag == "hakuX":
            s = SCALE.search(msg)
            if s:
                scale = int(s.group(1))

    # WHERE THE SCORED WINDOW STARTS. `mark gameplay` from a title's own
    # route; the generic route's `mark play` only provisionally, until a
    # reviewer has looked at the contact sheet.
    gp = [t for t, lab in marks if lab == "gameplay"]
    play = [t for t, lab in marks if lab == "play"]
    if gp:
        mark_t, gameplay_by = gp[0], "route"
    elif play and reviewed == "yes":
        mark_t, gameplay_by = play[0], "review"
    elif play:
        mark_t, gameplay_by = play[0], None
    else:
        mark_t, gameplay_by = None, None
    end_t = soak_end[-1] if soak_end else (lc[-1][0] if lc else None)

    # THERMAL: a pause that may overlap the scored window voids it (see
    # DISPLAY above). Every episode is reported, in or out of the window.
    therm = thermal_state.load(os.path.join(rdir, "thermal.jsonl"))
    read = [r for r in therm or [] if thermal_state.paused(r) is not None
            and thermal_state.dev_ts(r) is not None]
    eps = thermal_state.episodes(therm or [])
    windowed = bool(read) and mark_t is not None and end_t is not None
    hit = thermal_state.in_window(therm, mark_t, end_t) if windowed else []
    # A measured window no readable sample covers is void too (thermal_state.py,
    # A WINDOW IS COVERED): a pause there would leave no paused sample.
    gap = thermal_state.coverage(therm, mark_t, end_t) if windowed and not hit else None
    thermal = dict(measured=bool(read), samples=len(therm or []), unread=len(therm or []) - len(read),
                   pauses=[thermal_state.describe(e, mark_t if mark_t is not None else
                                                  thermal_state.origin(read))
                           for e in eps], in_window=bool(hit),
                   window_covered=(None if not windowed else gap is None), gap=gap)
    fp = thermal_state.first_pause(therm or [])
    thermal["first_pause_s"] = dict(after=fp[0], by=fp[1]) if fp else None
    try:
        with open(os.path.join(rdir, "perf_regimen.json")) as f:
            regimen = json.load(f).get("regimen")
    except (OSError, ValueError, AttributeError):
        regimen = None
    thermal["regimen"] = regimen
    at_defaults = regimen == "default"
    thermal["failed_sustained"] = (fp is not None) if at_defaults and read else None
    sustained_fail = None
    if thermal["failed_sustained"]:
        e0, t0 = thermal_state.first_episode(therm or [])
        sustained_fail = ("thermal: sustained play failed at the device's defaults -- %s, from the run's start"
                          % thermal_state.describe(e0, t0))
    if hit and void is None and not at_defaults:
        void = "thermal-pause: %s, relative to the mark" % thermal_state.describe(hit[0], mark_t)
    elif gap and void is None:
        void = "thermal-unread: %s, relative to the mark" % gap

    # STILL HEATING (see CONFIRMATION LENGTH above): the window's last
    # HEATING_WINDOW_S show a HEATING_ZONES reading climbing faster than
    # HEATING_RATE_C_PER_MIN, or a pause overlapped the window at all. Needs
    # `windowed` (readable samples and a scored window), same as the void
    # checks above.
    still_heating = bool(hit)
    if windowed and not still_heating:
        tail_lo = end_t - HEATING_WINDOW_S
        rates = [heating_rate(read, zone, tail_lo, end_t) for zone in HEATING_ZONES]
        still_heating = any(r is not None and r > HEATING_RATE_C_PER_MIN for r in rates)
    thermal["still_heating"] = still_heating if windowed else None
    heating_bump = windowed and still_heating and need["confirmation"] < 1200.0
    if heating_bump:
        need["confirmation"] = 1200.0

    v = dict(title=title, title_id=tid, name=entry.get("name"),
             device=res.get("device_label") or "", ref=res.get("ref") or req.get("ref"),
             apk_sha=res.get("apk_sha"), request_id=req.get("id") or os.path.basename(rdir.rstrip("/")),
             route=req.get("route_name") or None, surface_scale=scale,
             adb_failures=adb_failures, thermal=thermal, human_review="")
    v["booted"] = (not never) and bool(perf) and bool(lc)
    after = [(t, p) for t, p in perf if mark_t is not None and t >= mark_t]
    flipped_after = bool(after)
    if gameplay_by in ("route", "review"):
        v["reached_gameplay"] = flipped_after
    elif mark_t is not None:
        v["reached_gameplay"] = None          # unconfirmed: needs review
    else:
        v["reached_gameplay"] = False
    v["gameplay_by"] = gameplay_by if v["reached_gameplay"] else None
    died = bool(crash_lines) or bool(exited)
    v["crash"] = died
    v["crash_detail"] = (crash_lines[:3] or ([exited.group(0)] if exited else []))
    v["crash_warnings"] = crash_warn

    # Windows: consecutive perf lines BOTH inside the scored window. The line
    # that straddles the mark belongs to pre-mark play and is not counted.
    # A window that spans a capture gap is not a measurement of the guest.
    windows = []
    # A void run has no windows: its flips were drawn under someone else's
    # window, and no field below may carry them as a frame rate.
    for (t0, p0), (t1, p1) in ([] if void else zip(after, after[1:])):
        dt_s = t1 - t0
        if dt_s > 0 and not lost_in(t0, t1, cap_gaps):
            windows.append((dt_s, FRAMES_PER_LINE / dt_s, float(p1.group(2)), int(p1.group(1)), t0, t1))
    gameplay_s = (end_t - mark_t) if (mark_t is not None and end_t is not None) else 0.0
    v["gameplay_s"] = round(gameplay_s, 1)

    # PLAY TIMELINE (see TIMELINE above): fps over `play` seconds only.
    tl = play_timeline(lc, mark_t, end_t)
    v["timeline"] = tl
    if tl != "none":
        kept = [w for w in windows if in_spans((w[4] + w[5]) / 2.0, tl["play_spans"])]
        tl["fps_excluded_s"] = round(sum(w[0] for w in windows) - sum(w[0] for w in kept), 1)
        tl["fps_excluded_windows"] = len(windows) - len(kept)
        tl["play_spans"] = len(tl["play_spans"])
        windows = kept
    in_play = [(a, b) for a, b in cap_gaps
               if mark_t is not None and end_t is not None and b > mark_t and a < end_t]
    v["capture_gaps_s"] = [round(b - a, 1) for a, b in in_play][:20]
    v["capture_lost_s"] = round(sum(b - a for a, b in in_play), 1)
    # A break with nothing after it, and no `soak end`: see CAPTURE GAPS.
    truncated = open_break is not None and not soak_end
    v["capture_truncated"] = truncated
    v["capture_truncated_s"] = None
    if truncated:
        start = [t for t, lv, tag, msg in lc if tag == "hakuX-route" and msg.strip() == "soak start"]
        if start and held:
            v["capture_truncated_s"] = round(max(0.0, start[0] + int(held.group(1)) - open_break), 1)
            v["capture_lost_s"] = round(v["capture_lost_s"] + v["capture_truncated_s"], 1)

    hang_gaps = []
    if mark_t is not None and flipped_after:
        pts = [mark_t] + [t for t, _ in after]
        if not died and end_t is not None:
            pts.append(end_t)
        seen_s = [(b - a) - lost_in(a, b, cap_gaps) for a, b in zip(pts, pts[1:])]
        hang_gaps = [round(g, 1) for g in seen_s if g > HANG_S]
    elif mark_t is not None and not died and end_t is not None \
            and (end_t - mark_t) - lost_in(mark_t, end_t, cap_gaps) > HANG_S:
        hang_gaps = [round((end_t - mark_t) - lost_in(mark_t, end_t, cap_gaps), 1)]
    v["hang"] = bool(hang_gaps)
    v["hang_gaps_s"] = hang_gaps[:10]

    def share(thr):
        if not windows:
            return None, None
        tot = sum(w[0] for w in windows)
        ok_t = sum(w[0] for w in windows if w[1] >= thr * tol)
        ok_n = sum(1 for w in windows if w[1] >= thr * tol)
        return round(ok_t / tot, 4), round(ok_n / len(windows), 4)
    v["fps_windows"] = len(windows)
    v["fps_bar"] = bar_fps
    v["fps_ok_share"], v["fps_ok_window_share"] = share(bar_fps)
    if windows:
        fs = sorted(w[1] for w in windows)
        v["fps_window_median"] = round(fs[len(fs) // 2], 2)
        v["fps_window_min"] = round(fs[0], 2)
        v["g_fps_mean_reported_not_judged"] = round(
            sum(1000.0 / w[2] for w in windows if w[2] > 0) / len(windows), 2)
    v["target_fps"] = own_target
    own_share = share(own_target)[0] if own_target > bar_fps else v["fps_ok_share"]
    v["own_target_share"] = own_share
    v["confirmation_need_s"] = need["confirmation"]
    v["below_own_target"] = bool(own_target > bar_fps and v["fps_ok_share"] is not None
                                 and v["fps_ok_share"] >= share_min
                                 and (own_share or 0) < share_min)

    # POWER over the scored window (see POWER above). Reported, never judged.
    power = thermal_state.power_over(therm or [], mark_t, end_t) \
        if mark_t is not None and end_t is not None else thermal_state.power_over([], 0, 0)
    scored_s = float(sum(w[0] for w in windows))
    flips = FRAMES_PER_LINE * len(windows)
    power.update(scored_s=round(scored_s, 1), flips=flips, j_per_frame=None, j_per_frame_battery=None)
    if power["measured"] and flips and not power["sign_suspect"]:
        power["j_per_frame_battery"] = round(power["battery_w"] * scored_s / flips, 4)
        if power["net_w"] is not None:
            power["j_per_frame"] = round(power["net_w"] * scored_s / flips, 4)
    v["power"] = power

    starve = []
    for t, lv, tag, msg in lc:
        if tag == "hakuX-audiocap" and mark_t is not None and t >= mark_t + AUDIO_SKIP_S:
            s = STARVE.search(msg)
            if s:
                starve.append((int(s.group(1)), int(s.group(2)), int(s.group(3))))
    calls = sum(c for _, c, _ in starve)
    v["audio_measured"] = bool(starve) and calls > 0
    v["audio_starve_share"] = round(sum(s for s, _, _ in starve) / calls, 6) if calls else None
    v["audio_empty_calls"] = sum(e for _, _, e in starve)

    pace = [msg for t, lv, tag, msg in lc if tag == "hakuX-pace" and mark_t is not None and t >= mark_t]
    if pace:
        # profile.c's format, agreed in docs/lanes/perfbase/NOTES.md: parse by
        # key. vK = flips that took exactly K VBLANKs (v4 = 4+), so for a title
        # whose nominal is N VBLANKs a flip (1 at 60 fps, 2 at 30) the late
        # flips are the sum of vK for K > N. f=60 is a process's first window,
        # whose first delta is taken from zero; it is not steady state.
        nominal = max(1, round(60.0 / (v.get("target_fps") or 30.0)))
        late = flips = 0
        worst = None
        for m_ in pace:
            kv = dict(re.findall(r"(\w+)=([\d.]+)", m_))
            if not all("v%d" % k in kv for k in range(5)) or float(kv.get("f", 0)) <= 60:
                continue
            counts = [int(kv["v%d" % k]) for k in range(5)]
            flips += sum(counts)
            late += sum(counts[k] for k in range(nominal + 1, 5))
            if "max" in kv:
                worst = max(worst or 0.0, float(kv["max"]))
        v["pace"] = dict(lines=len(pace), nominal_vblanks=nominal,
                         late_per_100=(round(100.0 * late / flips, 2) if flips else None),
                         worst_stall=worst, last=pace[-1][:200])
    else:
        v["pace"] = None

    # HITCHES (#433, 2026-10-01): a frame-rate pass is not a smooth pass --
    # see hitch_report.py's module doc for the counters and the rule. A void
    # window's flips are not the title's, so it is not scanned for hitches
    # either, same as the fps windows above.
    hitches = [] if void else hitch_report.find_hitches(lc, mark_t, end_t)
    hrep = hitch_report.report(hitches, gameplay_s)
    v["hitches"] = hrep
    hitch_allowance = entry.get("hitch_allowance")
    v["hitch_allowance"] = hitch_allowance

    # WHOLE-WINDOW LIVENESS (#433): did the scored window ever move on, or
    # is it sitting on a menu the whole time (Super Monkey Ball, Castlevania:
    # `reached_gameplay` only reads the mark frame and cannot see this).
    static = hitch_report.static_window(rdir, mark_t, end_t)
    v["static_window"] = static
    # POSITION (#433, 2026-10-03): the scene must change across the window and
    # between its samples. Same samples as the liveness test above.
    position = hitch_report.position_change(rdir, mark_t, end_t)
    v["position"] = position

    # THE CRITERIA, IN ORDER. The first that fails is named; all are listed.
    if require is None:
        require = "confirmation" if gameplay_s >= need["confirmation"] else "screening"
    v["pass_kind"] = require
    fails = []
    v["void"] = void
    if void:
        fails.append("void: " + void)
    elif render_black:
        fails.append(render_black.group(0))
    if sustained_fail and not void:
        fails.append(sustained_fail)
    if truncated:
        at = ("%.0f s after the mark" % (open_break - mark_t)) if mark_t is not None \
            else "before any `mark gameplay` was captured"
        fails.append("capture: truncated -- the logcat stream broke %s and never resumed%s; "
                     "what follows judges only the captured part (see LOGCAT: in run.log)"
                     % (at, (", about %.0f s unseen" % v["capture_truncated_s"])
                        if v["capture_truncated_s"] is not None else ""))
    if not v["booted"]:
        fails.append("booted: the guest never appeared or never flipped 60 frames")
    if v["reached_gameplay"] is None:
        fails.append("reached_gameplay: unconfirmed (generic route) -- review the contact sheet, "
                      "then rerun with --reviewed-gameplay yes|no")
    elif not v["reached_gameplay"]:
        why = "no `mark gameplay` in logcat"
        lost = [lab for lab in route_marks_failed if lab not in {x for _, x in marks}]
        if route_not_played:
            why += " (route not played: %s)" % route_not_played.group(1)
        elif lost:
            why += " (the route played `mark %s`, but its logcat write FAILED after its "\
                   "retries: see run.log)" % ",".join(lost)
        elif route_marks_host and not marks:
            why += " (the route marked %s in run.log, but logcat has no hakuX-route line: "\
                   "the LOGCAT_SPEC dropped the tag)" % ",".join(route_marks_host)
        elif mark_t is not None:
            why = "no guest flip after the mark"
        elif reviewed == "no":
            why = "a reviewer judged the contact sheet not gameplay"
        fails.append("reached_gameplay: " + why)
    if died:
        fails.append("crash: " + (v["crash_detail"][0] if v["crash_detail"] else "exit")[:120])
    if v["hang"]:
        fails.append("hang: %s s without 60 guest flips after the mark" % hang_gaps[0])
    if mark_t is not None and gameplay_s < need[require]:
        if require == "confirmation" and heating_bump:
            fails.append("confirmation: %.0f s needed -- the device was still heating at the end"
                         % need["confirmation"])
        else:
            fails.append("duration: %.0f s of gameplay < %.0f s %s" % (gameplay_s, need[require], require))
    if tl != "none" and require == "confirmation" and mark_t is not None and not void \
            and (tl["play_share"] is None or tl["play_share"] < play_share_min):
        fails.append("menu time: %s of the scored window in `play` (bar %.0f%%; %s)"
                     % ("none" if tl["play_share"] is None else "%.1f%%" % (100 * tl["play_share"]),
                        100 * play_share_min,
                        ", ".join("%s %.0f s" % kv for kv in list(tl["by_state"].items())[:4])))
    if v["fps_ok_share"] is None:
        if tl != "none" and mark_t is not None and flipped_after and not void:
            fails.append("fps: fewer than two perf lines inside `play` (%.0f s excluded as not play)"
                         % tl["fps_excluded_s"])
        elif mark_t is not None and flipped_after and not void:
            fails.append("fps: fewer than two perf lines after the mark")
    elif v["fps_ok_share"] < share_min:
        fails.append("fps: %.1f%% of gameplay at >= %g fps (bar %.0f%%)"
                     % (100 * v["fps_ok_share"], bar_fps, 100 * share_min))
    if mark_t is not None and not v["audio_measured"]:
        fails.append("audio: unmeasured -- no starve: line after the first 10 s")
    elif v["audio_starve_share"] is not None and v["audio_starve_share"] > audio_max:
        fails.append("audio: %.3f%% of callbacks short (max %.3f%%)"
                     % (100 * v["audio_starve_share"], 100 * audio_max))
    if mark_t is not None and not void:
        hfail, hwhy = hitch_report.hitch_fail(hrep, hitch_allowance)
        if hfail:
            fails.append(hwhy)
        sfail, swhy = hitch_report.static_window_fail(static)
        if sfail:
            fails.append(swhy)
        ufail, uwhy = hitch_report.static_window_unmeasured(static)
        if ufail:
            fails.append(uwhy)
        pfail, pwhy = hitch_report.position_fail(position)
        if pfail:
            fails.append(pwhy)
    v["pass"] = not fails
    v["failing"] = fails[0] if fails else None
    v["failures"] = fails
    v["rating_candidate"] = None
    if v["pass"]:
        v["rating_candidate"] = {1: "Playable", 2: "Playable (2x)"}.get(scale)
        if v["rating_candidate"] is None:
            v["rating_note"] = "passed, but surface_scale %s is not 1 or 2 (or was not logged)" % scale

    if write_contact_sheet:
        sheet, why = contact_sheet(rdir, os.path.join(rdir, "contact.png"))
        v["contact_sheet"] = sheet
        if why:
            v["contact_sheet_note"] = why
    else:
        v["contact_sheet"] = None
        v["contact_sheet_note"] = "not generated: a live score (status_html.py) never writes into a result dir"
    v["judged_utc"] = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return v


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("rdir")
    ap.add_argument("--require", choices=["screening", "confirmation"])
    ap.add_argument("--reviewed-gameplay", choices=["yes", "no"])
    ap.add_argument("--targets", default=DEFAULT_TARGETS)
    a = ap.parse_args(argv)
    v = judge(a.rdir, a.require, a.reviewed_gameplay, a.targets)
    tmp = os.path.join(a.rdir, ".verdict.json.tmp")
    with open(tmp, "w") as f:
        json.dump(v, f, indent=2)
    json.load(open(tmp))
    os.replace(tmp, os.path.join(a.rdir, "verdict.json"))
    pw = v["power"]
    hrep = v["hitches"]
    sw = v["static_window"]
    tl = v["timeline"]
    print("VERDICT %s %s %s gameplay=%ss fps_ok=%s crash=%s hang=%s audio_short=%s "
          "hitches=%d/%spm worst_ms=%.1f static_frac=%s %s%s%s%s%s" % (
        v["name"] or v["title"] or "?", v["device"] or "?",
        ("PASS " + str(v["rating_candidate"])) if v["pass"] else "FAIL(%s)" % v["failing"],
        v["gameplay_s"], v["fps_ok_share"], v["crash"], v["hang"], v["audio_starve_share"],
        hrep["n_after_warmup"], hrep["per_min_after_warmup"], hrep["worst_ms"],
        sw["frozen_frac"] if sw["measured"] else "unmeasured",
        "timeline: none" if tl == "none" else "play_share=%s fps_excluded=%ss" % (
            tl["play_share"], tl.get("fps_excluded_s")),
        " below_own_target" if v["below_own_target"] else "",
        (" capture_lost=%ss" % v["capture_lost_s"]) if v["capture_lost_s"] else "",
        " capture_truncated" if v["capture_truncated"] else "",
        (" battery_w=%+.2f net_w=%s j_per_frame=%s" % (pw["battery_w"], pw["net_w"], pw["j_per_frame"]))
        if pw["measured"] else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
