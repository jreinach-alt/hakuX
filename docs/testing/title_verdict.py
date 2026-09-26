#!/usr/bin/env python3
"""title_verdict.py <result-dir> [--require screening|confirmation]
                                 [--reviewed-gameplay yes|no] [--targets FILE]

Judge one title soak: read run.log, logcat.txt, request.json/result.json and
titles/targets.toml, write verdict.json beside them, print one line.

THE BAR (the owner, 2026-09-25). A run passes when the title
  - booted, and reached gameplay by its route (`mark gameplay` in logcat,
    then at least one guest flip after it);
  - played for the required window after the mark (600 s screening,
    1200 s confirmation) with no crash, no hang and no real exit;
  - ran at >= 30 fps for >= 90% of the gameplay time;
  - played its audio with no dropouts (see AUDIO below).
A pass at surface_scale 1 is the `Playable` rating, at 2 `Playable (2x)`.
`Perfect` is a human's call: `human_review` is written empty and nothing here
ever fills it.

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
DEFAULT_TARGETS = os.path.join(HERE, "titles", "targets.toml")

# `logcat -v time`: "09-25 13:31:41.662 I/hakuX-perf( 1234): gfps=30 G:..."
LINE = re.compile(r"^(\d\d-\d\d \d\d:\d\d:\d\d\.\d{3})\s+([VDIWEF])/([^(\s]+)\s*\(\s*\d+\):\s?(.*)$")
PERF = re.compile(r"gfps=(\d+)\s+G:([\d.]+)\(([\d.]+)-([\d.]+)\)")
STARVE = re.compile(r"starve: (\d+)/(\d+) callbacks short \((\d+) empty\)")
SCALE = re.compile(r"surface_scale=(\d+)")

FRAMES_PER_LINE = 60          # profile.c: frame_count % 60
HANG_S = 10.0
AUDIO_SKIP_S = 10.0


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
    """(title_id, entry) for the ISO the request named, or (None, {})."""
    base = os.path.basename(iso or "")
    for tid, t in (targets.get("titles") or {}).items():
        isos = t.get("iso") or {}
        if base and base in [os.path.basename(v) for v in isos.values()]:
            return tid, t
    return None, {}


def parse_logcat(path):
    out = []
    try:
        with open(path, errors="replace") as f:
            for raw in f:
                m = LINE.match(raw.rstrip("\n"))
                if m:
                    out.append((ts(m.group(1)), m.group(2), m.group(3), m.group(4)))
    except OSError:
        pass
    return out


def contact_sheet(rdir, out_png):
    """Grid of the run's frames for a reviewer. None + reason when there is
    nothing to draw or no PIL (the jobs-selftest runner has none)."""
    frames = sorted(glob.glob(os.path.join(rdir, "route-frames", "*.png")))
    frames += sorted(glob.glob(os.path.join(rdir, "frames", "*.png")))
    if not frames:
        return None, "no frames: the route took none and --frames-every was 0"
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        return None, "PIL unavailable; %d frames on disk" % len(frames)
    if len(frames) > 36:          # evenly spaced, first and last kept
        step = (len(frames) - 1) / 35.0
        frames = [frames[round(i * step)] for i in range(36)]
    tw, th, cols = 320, 180, 6
    rows = (len(frames) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * tw, rows * (th + 16)), "black")
    draw = ImageDraw.Draw(sheet)
    for i, f in enumerate(frames):
        try:
            im = Image.open(f).convert("RGB")
            im.thumbnail((tw, th))
        except Exception:
            continue
        x, y = (i % cols) * tw, (i // cols) * (th + 16)
        sheet.paste(im, (x, y + 16))
        draw.text((x + 2, y + 2), os.path.basename(f)[:48], fill="white")
    sheet.save(out_png)
    return os.path.basename(out_png), None


def judge(rdir, require=None, reviewed=None, targets_path=DEFAULT_TARGETS):
    req = load_json(os.path.join(rdir, "request.json"))
    res = load_json(os.path.join(rdir, "result.json"))
    targets = load_targets(targets_path)
    defaults = targets.get("defaults") or {}
    bar_fps = float(defaults.get("playable_fps", 30))
    tol = float(defaults.get("fps_tolerance", 0.95))
    share_min = float(defaults.get("fps_share_min", 0.90))
    audio_max = float(defaults.get("audio_starve_max_share", 0.001))
    need = {"screening": float(defaults.get("screening_s", 600)),
            "confirmation": float(defaults.get("confirmation_s", 1200))}

    title = req.get("title") or res.get("title") or ""
    tid, entry = find_title(targets, title)
    own_target = float(entry.get("target_fps", bar_fps))

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
    route_marks_host = re.findall(r"^ROUTE \S+ mark (\S+)", runlog, re.M)

    lc = parse_logcat(os.path.join(rdir, "logcat.txt"))
    perf = [(t, PERF.search(msg)) for t, lv, tag, msg in lc if tag == "hakuX-perf"]
    perf = [(t, p) for t, p in perf if p]
    marks = [(t, msg[5:].strip()) for t, lv, tag, msg in lc
             if tag == "hakuX-route" and msg.startswith("mark ")]
    soak_end = [t for t, lv, tag, msg in lc if tag == "hakuX-route" and msg.strip() == "soak end"]
    crash_lines = [msg for t, lv, tag, msg in lc
                   if (tag == "hakuX-crash" and lv in "EF")
                   or (tag in ("libc", "DEBUG") and lv == "F")]
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

    v = dict(title=title, title_id=tid, name=entry.get("name"),
             device=res.get("device_label") or "", ref=res.get("ref") or req.get("ref"),
             apk_sha=res.get("apk_sha"), request_id=req.get("id") or os.path.basename(rdir.rstrip("/")),
             route=req.get("route_name") or None, surface_scale=scale,
             adb_failures=adb_failures, human_review="")
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
    windows = []
    for (t0, p0), (t1, p1) in zip(after, after[1:]):
        dt_s = t1 - t0
        if dt_s > 0:
            windows.append((dt_s, FRAMES_PER_LINE / dt_s, float(p1.group(2)), int(p1.group(1))))
    gameplay_s = (end_t - mark_t) if (mark_t is not None and end_t is not None) else 0.0
    v["gameplay_s"] = round(gameplay_s, 1)

    hang_gaps = []
    if mark_t is not None and flipped_after:
        pts = [mark_t] + [t for t, _ in after]
        if not died and end_t is not None:
            pts.append(end_t)
        hang_gaps = [round(b - a, 1) for a, b in zip(pts, pts[1:]) if b - a > HANG_S]
    elif mark_t is not None and not died and end_t is not None and end_t - mark_t > HANG_S:
        hang_gaps = [round(end_t - mark_t, 1)]
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
    v["below_own_target"] = bool(own_target > bar_fps and v["fps_ok_share"] is not None
                                 and v["fps_ok_share"] >= share_min
                                 and (own_share or 0) < share_min)

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

    # THE CRITERIA, IN ORDER. The first that fails is named; all are listed.
    if require is None:
        require = "confirmation" if gameplay_s >= need["confirmation"] else "screening"
    v["pass_kind"] = require
    fails = []
    if not v["booted"]:
        fails.append("booted: the guest never appeared or never flipped 60 frames")
    if v["reached_gameplay"] is None:
        fails.append("reached_gameplay: unconfirmed (generic route) -- review the contact sheet, "
                      "then rerun with --reviewed-gameplay yes|no")
    elif not v["reached_gameplay"]:
        why = "no `mark gameplay` in logcat"
        if route_not_played:
            why += " (route not played: %s)" % route_not_played.group(1)
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
        fails.append("duration: %.0f s of gameplay < %.0f s %s" % (gameplay_s, need[require], require))
    if v["fps_ok_share"] is None:
        if mark_t is not None and flipped_after:
            fails.append("fps: fewer than two perf lines after the mark")
    elif v["fps_ok_share"] < share_min:
        fails.append("fps: %.1f%% of gameplay at >= %g fps (bar %.0f%%)"
                     % (100 * v["fps_ok_share"], bar_fps, 100 * share_min))
    if mark_t is not None and not v["audio_measured"]:
        fails.append("audio: unmeasured -- no starve: line after the first 10 s")
    elif v["audio_starve_share"] is not None and v["audio_starve_share"] > audio_max:
        fails.append("audio: %.3f%% of callbacks short (max %.3f%%)"
                     % (100 * v["audio_starve_share"], 100 * audio_max))
    v["pass"] = not fails
    v["failing"] = fails[0] if fails else None
    v["failures"] = fails
    v["rating_candidate"] = None
    if v["pass"]:
        v["rating_candidate"] = {1: "Playable", 2: "Playable (2x)"}.get(scale)
        if v["rating_candidate"] is None:
            v["rating_note"] = "passed, but surface_scale %s is not 1 or 2 (or was not logged)" % scale

    sheet, why = contact_sheet(rdir, os.path.join(rdir, "contact.png"))
    v["contact_sheet"] = sheet
    if why:
        v["contact_sheet_note"] = why
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
    print("VERDICT %s %s %s gameplay=%ss fps_ok=%s crash=%s hang=%s audio_short=%s%s" % (
        v["name"] or v["title"] or "?", v["device"] or "?",
        ("PASS " + str(v["rating_candidate"])) if v["pass"] else "FAIL(%s)" % v["failing"],
        v["gameplay_s"], v["fps_ok_share"], v["crash"], v["hang"], v["audio_starve_share"],
        " below_own_target" if v["below_own_target"] else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
