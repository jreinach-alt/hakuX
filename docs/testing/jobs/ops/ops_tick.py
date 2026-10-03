#!/usr/bin/env python3
"""ops_tick.py -- the model-free ops layer's one tick (#433).

    ops_tick.py             detect jams, apply a scripted remedy where one is
                            known, escalate what survives or has none
    ops_tick.py --shadow    detect and log what it WOULD do; act on nothing

WHY. hostops (a `claude -p` session) was ticking 42 times/24h at ~$1.70 each
(~$110/day) to do work that is almost entirely mechanical: read local files,
compare them to a threshold or a systemd state, run one known command. The
owner (2026-10-02): "It's clearly lighting tokens on fire." This script is
the model-free replacement for that loop. It reads ONLY local truth -- no
`gh`, no network -- because GitHub has been suspended since 2026-09-29 and
every local-truth equivalent already exists (see docs/lanes/opsrebuild/
NOTES.md's inventory table for what each old hostops check maps to here).

THE JAM MODEL. Every tick, each detector below returns zero or more Jam
instances (class, subject, message, remedy). A detected jam is looked up by
(class, subject) in jams.tsv's open rows:
  - new                      -> open a row, run its remedy (if any) once
  - still open, remedy tried -> re-check; if it has survived the remedy (or,
                                 for a no-remedy class, survived at all) past
                                 ESCALATE_AFTER_MIN, hand it to ops_escalate.sh
  - no longer detected        -> close the row (cleared_at, time_to_clear_s)
A remedy is applied AT MOST ONCE per open jam -- it is re-checked, not
re-applied, so a flapping jam does not re-run its remedy every 5 minutes.

AUTHORITY. Same as hostops had (host-tools/hostops-preamble.md): it may act
on local jams, but it must never queue device work to fill idle time, resume
a lane whose brief carries a STOPPED marker, use `gh`, or edit
offline_fold.py / territory.toml / nv2a_issues.toml directly -- a territory
gap is a written request, not a self-service edit.
"""
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import time

W = os.environ.get("HAKUX_WORK", "/home/justin/hakux-work")
REPO = os.environ.get("HAKUX_REPO_DIR", "/home/justin/hakuX")
D = os.environ.get("DISPATCH_DIR", W + "/dispatch")
JOBS = os.path.dirname(os.path.abspath(__file__))  # .../docs/testing/jobs/ops
TESTING = os.path.dirname(JOBS)                     # .../docs/testing/jobs -> jobs
STATE_DIR = os.environ.get("OPS_STATE_DIR", W + "/host-tools/ops-state")
INBOX = os.environ.get("OPS_INBOX", W + "/host-tools/hostops-inbox.md")
BRIEFS = os.environ.get("OPS_BRIEFS", W + "/briefs")
FOLD_FAILURES = os.environ.get("OPS_FOLD_FAILURES", W + "/offline-git/fold-failures.log")
REALITY = os.environ.get("OPS_DEVICE_REALITY", W + "/host-tools/.device-reality.json")
LANE_SH = os.environ.get("OPS_LANE_SH", REPO + "/docs/testing/lane.sh")
HOLD_SH = os.environ.get("OPS_HOLD_SH", TESTING + "/hold.sh")
JAMCHECK_SH = os.environ.get("OPS_JAMCHECK_SH", W + "/host-tools/dispatch_jamcheck.sh")
ESCALATE_SH = os.environ.get("OPS_ESCALATE_SH", os.path.join(JOBS, "ops_escalate.sh"))
# Overridable so selftest.d/87-ops-tick.sh can point this at a fixture shim
# without touching selftest.sh's shared $T/bin/systemctl (which only knows
# `is-active` -> active; this script also needs list-timers/list-units shapes).
SYSTEMCTL = os.environ.get("OPS_SYSTEMCTL", "systemctl --user")

DEVICES = os.environ.get("OPS_DEVICES", "thor,nova").split(",")
NOW = time.time()

# Hold tags the owner takes on purpose -- never a jam (ported from
# harness_health.py's OWNER_HOLD_TAGS; keep the two lists in sync by hand
# until hostops retires for good).
OWNER_HOLD_TAGS = ("owner", "lanelocal-topup", "lanelocal-fanwait")
# ops_tick's own battery-hold tag, distinct from device_reality.sh's
# "battery-hostops" so the two never fight over the same file.
BATTERY_TAG = "ops.battery"
BATTERY_FLOOR = int(os.environ.get("OPS_BATTERY_FLOOR", "15"))
BATTERY_LIFT = int(os.environ.get("OPS_BATTERY_LIFT", "20"))
DISK_FLOOR_GB = float(os.environ.get("OPS_DISK_FLOOR_GB", "20"))
QUEUE_STALE_MIN = int(os.environ.get("OPS_QUEUE_STALE_MIN", "60"))
HOLD_DEFAULT_BOUND_MIN = int(os.environ.get("OPS_HOLD_BOUND_MIN", "90"))
ESCALATE_AFTER_MIN = int(os.environ.get("OPS_ESCALATE_AFTER_MIN", "30"))


def sh(cmd, timeout=30):
    try:
        p = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return p.stdout, p.returncode
    except Exception:
        return "", 1


def say(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


class Jam:
    def __init__(self, cls, subject, msg, remedy=None, remedy_label=""):
        self.cls = cls
        self.subject = subject
        self.msg = msg
        self.remedy = remedy          # callable() -> str (what happened), or None
        self.remedy_label = remedy_label


# ------------------------------------------------------------------ detectors

def det_hold_overbound():
    """A hold past its stated bound with no live holder process."""
    jams = []
    for dev in DEVICES:
        hp = os.path.join(D, "hold", dev)
        if not os.path.isfile(hp):
            continue
        tag = open(hp).read().strip()
        if not tag or tag in OWNER_HOLD_TAGS:
            continue
        why_p = hp + ".why"
        why = open(why_p).read() if os.path.isfile(why_p) else ""
        m = re.search(r"(\d+)[- ]?min", why)
        bound_min = int(m.group(1)) if m else HOLD_DEFAULT_BOUND_MIN
        age_min = (NOW - os.path.getmtime(hp)) / 60
        if age_min <= bound_min:
            continue
        m2 = re.match(r"^lane\.(\S+)$", tag)
        if not m2:
            continue  # unrecognised tag shape: log nothing rather than guess wrong
        lane = m2.group(1)
        out, _ = sh("%s is-active hakux-lane-%s.service" % (SYSTEMCTL, lane))
        if out.strip() == "active":
            continue  # the holder is still alive; a long hold with a live owner is not this jam
        msg = "%s held %.0f min by %s (bound ~%d min) and hakux-lane-%s is not active: nothing will lift it" \
              % (dev, age_min, tag, bound_min, lane)

        def remedy(dev=dev, tag=tag):
            out, rc = sh("bash %s release %s %s" % (HOLD_SH, dev, tag))
            return "hold.sh release %s %s -> rc=%d %s" % (dev, tag, rc, out.strip()[:200])

        jams.append(Jam("hold-overbound", dev, msg, remedy, "release the hold"))
    return jams


def _lane_unit_active(name):
    out, _ = sh("%s is-active hakux-lane-%s.service" % (SYSTEMCTL, name))
    return out.strip() == "active"


def _stopped_marker(name):
    return bool(glob.glob(os.path.join(BRIEFS, name + ".md.STOPPED-by-owner-*")))


def _resume_lane(name, addendum):
    """Append `addendum` to the lane's brief and resume it once. Returns a status string."""
    brief = os.path.join(BRIEFS, name + ".md")
    if not os.path.isfile(brief):
        return "no brief at %s; cannot resume" % brief
    try:
        with open(brief, "a") as f:
            f.write("\n\n---\n\n" + addendum + "\n")
    except OSError as e:
        return "could not append addendum: %s" % e
    out, rc = sh("bash %s resume %s" % (LANE_SH, name), timeout=60)
    return "lane.sh resume %s -> rc=%d %s" % (name, rc, out.strip()[:200])


def det_stranded_lanes():
    """A lane unit ended with its PR.md draft and no blocker: resume ONCE."""
    jams = []
    out, _ = sh("git -C %s for-each-ref --format='%%(refname:short)' refs/remotes/origin/lane" % REPO)
    for ref in out.split():
        name = ref.split("/", 2)[-1]
        if _lane_unit_active(name) or _stopped_marker(name):
            continue
        pr_text, rc = sh("git -C %s show %s:docs/lanes/%s/PR.md" % (REPO, ref, name))
        if rc != 0:
            continue  # no PR.md on this branch: not this job's to act on (see local-board.md)
        state = (re.search(r"^State:\s*(\w+)", pr_text, re.M) or [None, "?"])[1]
        if state.lower() != "draft":
            continue
        msg = "lane.%s is stopped with its PR.md still 'draft' and no running unit: stranded" % name

        def remedy(name=name):
            addendum_path = W + "/host-tools/bg-addendum.md"
            addendum = open(addendum_path).read() if os.path.isfile(addendum_path) else \
                "## Resumed by ops_tick: your session ended with your PR.md still in draft and nothing running.\nCheck what your last session left behind; finish the definition of done or mark the PR ready."
            return _resume_lane(name, addendum)

        jams.append(Jam("stranded-lane", name, msg, remedy, "resume once"))
    return jams


FOLD_CLASSIFIERS = (
    (re.compile(r"outside \[lane\.(\S+)\]'s files"), "territory"),
    (re.compile(r"no \[lane\.(\S+)\] row on origin/board"), "rowless"),
    (re.compile(r"merge conflict with master"), "conflict"),
    (re.compile(r"selftest failed"), "selftest"),
    (re.compile(r"no finished, non-void dispatch run"), "no-device-run"),
    (re.compile(r"another offline_fold\.py is running|^not ready:|need exactly one"), "transient"),
)


def _classify_fold_line(line):
    m_branch = re.search(r"FAILED (\S+) @ (\S+):", line)
    if not m_branch:
        return None
    branch, head = m_branch.group(1), m_branch.group(2)
    if not re.fullmatch(r"[0-9a-f]{4,40}", head):
        return None  # the head is interpolated into a shell command below: hex only
    reason = line[m_branch.end():]
    for pat, cls in FOLD_CLASSIFIERS:
        mm = pat.search(reason)
        if mm:
            return branch, head, cls, reason.strip()
    return branch, head, "other", reason.strip()


def _load_json(path, default):
    if os.path.isfile(path):
        try:
            return json.load(open(path))
        except Exception:
            pass
    return default


def _save_json(path, data):
    tmp = path + ".tmp"
    json.dump(data, open(tmp, "w"), indent=1)
    os.replace(tmp, path)


def det_fold_failures():
    """Classify fold-failures.log: territory/rowless -> inbox; conflict/selftest/
    no-device-run -> route to the lane (addendum + resume once); the rest is logged only.

    A fold failure is not re-stated by the log every tick (each FAILED line is read once,
    at its cursor position), so unlike the other detectors this one keeps its OWN open set
    (fold_open.json, keyed by branch) and re-emits a Jam for every branch still in it every
    tick, the same contract the generic jams.tsv loop expects of every detector. A branch
    leaves the open set only when a later FOLDED line names it -- the lane fixed it."""
    jams = []
    os.makedirs(STATE_DIR, exist_ok=True)
    cursor_p = os.path.join(STATE_DIR, "fold.cursor")
    open_p = os.path.join(STATE_DIR, "fold_open.json")
    cursor = int(open(cursor_p).read()) if os.path.isfile(cursor_p) else 0
    open_branches = _load_json(open_p, {})

    if os.path.isfile(FOLD_FAILURES):
        size = os.path.getsize(FOLD_FAILURES)
        if size < cursor:
            cursor = 0  # the log was rotated
        with open(FOLD_FAILURES) as f:
            f.seek(cursor)
            new_lines = f.readlines()
            new_cursor = f.tell()
        open(cursor_p, "w").write(str(new_cursor))

        for line in new_lines:
            m_folded = re.search(r"FOLDED (\S+):", line)
            if m_folded:
                open_branches.pop(m_folded.group(1), None)
                continue
            parsed = _classify_fold_line(line)
            if not parsed:
                continue
            branch, head, cls, reason = parsed
            if cls == "transient":
                continue
            open_branches[branch] = {"cls": cls, "head": head, "reason": reason[:300]}

        # A branch that pushed a new commit since its recorded failure has moved on: the
        # failure's head is stale, and the lane may already have fixed it and be waiting on
        # a retry, not stuck. Drop it rather than route a human or a session at old evidence;
        # if it fails again, the new FAILED line (new head) will reopen it fresh.
        for branch in list(open_branches):
            cur_head, rc = sh("git -C %s rev-parse origin/%s" % (REPO, branch))
            if rc != 0 or not cur_head.strip().startswith(open_branches[branch]["head"][:10]):
                del open_branches[branch]
                continue
            # Already folded, not stuck: the failed head is an ancestor of master, so the content
            # it was refused for has landed. The FOLDED line may sit outside the cursor window or
            # never have been written (snapdrive, usagemode, ibcache all came up this way).
            _, anc_rc = sh("git -C %s merge-base --is-ancestor %s origin/master" % (REPO, open_branches[branch]["head"]))
            if anc_rc == 0:
                del open_branches[branch]
        _save_json(open_p, open_branches)

    for branch, entry in open_branches.items():
        cls, head, reason = entry["cls"], entry["head"], entry["reason"]
        lane = branch.split("/", 1)[-1]
        msg = "%s @ %s: %s (%s)" % (branch, head[:10], reason[:200], cls)

        if cls in ("territory", "rowless"):
            def remedy(lane=lane, cls=cls, reason=reason, branch=branch):
                os.makedirs(os.path.dirname(INBOX), exist_ok=True)
                with open(INBOX, "a") as f:
                    f.write("\n## %s -- fold-failure:%s (ops_tick)\n%s: %s\nNeeds a board-territory edit (private worktree, gated push) widening [lane.%s]'s files, or a new row.\n"
                            % (time.strftime("%Y-%m-%d %H:%M"), cls, branch, reason[:300], lane))
                return "wrote host-tools/hostops-inbox.md"
            jams.append(Jam("fold-failure:" + cls, branch, msg, remedy, "write inbox request"))
        elif cls in ("conflict", "selftest", "no-device-run"):
            def remedy(lane=lane, cls=cls, reason=reason):
                if _stopped_marker(lane):
                    return "lane.%s is STOPPED-by-owner: not resumed" % lane
                texts = {
                    "conflict": "## Resumed by ops_tick: your last fold attempt hit a merge conflict with master.\nMerge origin/master into your branch, resolve, push, and your PR.md fold will retry.",
                    "selftest": "## Resumed by ops_tick: your last fold attempt failed docs/testing/jobs/selftest.sh.\n%s\nFix it, push, and the fold will retry." % reason[:300],
                    "no-device-run": "## Resumed by ops_tick: your last fold attempt found no finished, non-void dispatch run built from your head.\nQueue one device run on your head commit, then your PR.md fold will retry.",
                }
                return _resume_lane(lane, texts[cls])
            jams.append(Jam("fold-failure:" + cls, branch, msg, remedy, "route to the lane"))
        else:
            jams.append(Jam("fold-failure:other", branch, msg, None, ""))
    return jams


def _device_busy_requests(dev):
    hits = []
    for p in glob.glob(os.path.join(D, "running", "*.req")):
        try:
            if json.load(open(p)).get("device") == dev:
                hits.append(p)
        except Exception:
            pass
    return hits


def det_queue_stale():
    """A queued request older than 60 min with a free device: nudge the dispatcher."""
    jams = []
    held = {dev for dev in DEVICES if os.path.isfile(os.path.join(D, "hold", dev))}
    free_devices = [dev for dev in DEVICES if dev not in held and not _device_busy_requests(dev)]
    if not free_devices:
        return jams
    for p in glob.glob(os.path.join(D, "queue", "*.req")):
        name = os.path.basename(p)
        if name.startswith("."):
            continue
        age_min = (NOW - os.path.getmtime(p)) / 60
        if age_min <= QUEUE_STALE_MIN:
            continue
        try:
            req = json.load(open(p))
        except Exception:
            continue
        pinned = req.get("device")
        if pinned and pinned not in free_devices:
            continue
        msg = "%s queued %.0f min (requester %s) with %s free: dispatcher looks stuck" \
              % (name, age_min, req.get("requester", "?"), ",".join(free_devices))

        def remedy():
            out, rc = sh("bash %s --nudge" % JAMCHECK_SH, timeout=60)
            return "dispatch_jamcheck.sh --nudge -> rc=%d %s" % (rc, out.strip()[:200])

        jams.append(Jam("queue-stale", name, msg, remedy, "nudge dispatcher"))
        break  # one nudge covers the whole queue; do not fire it once per stale request
    return jams


def det_timer_unanchored():
    """A hakux-*.timer with no next run, whose paired service is not mid-run."""
    jams = []
    out, _ = sh("%s list-timers 'hakux-*' --no-legend --all" % SYSTEMCTL)
    for line in out.splitlines():
        parts = line.split()
        if not parts:
            continue
        next_field = parts[0]
        unit = parts[-1] if parts[-1].endswith(".timer") else None
        if not unit:
            m = re.search(r"(hakux-\S+\.timer)", line)
            unit = m.group(1) if m else None
        if not unit:
            continue
        if next_field not in ("n/a", "-"):
            continue
        svc = unit.replace(".timer", ".service")
        state, _ = sh("%s is-active %s" % (SYSTEMCTL, svc))
        if state.strip() in ("active", "activating"):
            continue  # a oneshot mid-run has no next elapse by design
        msg = "%s has no next run and %s is not active" % (unit, svc)

        def remedy(svc=svc):
            out, rc = sh("%s start --no-block %s" % (SYSTEMCTL, svc))
            return "systemctl start --no-block %s -> rc=%d" % (svc, rc)

        jams.append(Jam("timer-unanchored", unit, msg, remedy, "start the service"))
    return jams


UNIT_TOKEN_RE = re.compile(r"\b(hakux-\S+?\.(?:service|timer|socket|path|target|mount))\b")


def det_failed_unit():
    """A failed hakux unit: no safe scripted fix, so no remedy -- escalates on sight."""
    jams = []
    out, _ = sh("%s list-units 'hakux-*' --state=failed --no-legend" % SYSTEMCTL)
    for line in out.splitlines():
        # systemctl prefixes a failed unit's row with a bullet glyph (●), so the first token is
        # not the unit name. Match the hakux-* unit token wherever it sits on the line.
        m = UNIT_TOKEN_RE.search(line)
        if not m:
            continue
        unit = m.group(1)
        jams.append(Jam("failed-unit", unit, "%s has failed" % unit, None, ""))
    return jams


def det_battery_floor():
    """A device below its battery floor with no hold at all: take one; release ops_tick's own
    hold once the device climbs back above the lift threshold."""
    jams = []
    if not os.path.isfile(REALITY):
        return jams
    try:
        reality = json.load(open(REALITY))
    except Exception:
        return jams
    for dev in DEVICES:
        info = reality.get(dev) or {}
        try:
            level = int(info.get("level"))
        except (TypeError, ValueError):
            continue
        hp = os.path.join(D, "hold", dev)
        tag = open(hp).read().strip() if os.path.isfile(hp) else ""
        if level < BATTERY_FLOOR and not tag:
            msg = "%s at %d%% (< floor %d%%) and unheld" % (dev, level, BATTERY_FLOOR)

            def remedy(dev=dev, level=level):
                # Bare "<" and "(" are shell metacharacters under shell=True (redirection, and a
                # syntax error as a bare word) -- "below" and no parens keep this a plain
                # argument list hold.sh's "${*:4}" can join back into one reason string.
                out, rc = sh("bash %s take %s %s battery floor %d%% below %d%% ops_tick" % (HOLD_SH, dev, BATTERY_TAG, level, BATTERY_FLOOR))
                return "hold.sh take %s %s -> rc=%d %s" % (dev, BATTERY_TAG, rc, out.strip()[:200])

            jams.append(Jam("battery-floor", dev, msg, remedy, "hold the device"))
        elif level >= BATTERY_LIFT and tag == BATTERY_TAG:
            msg = "%s at %d%% (>= lift %d%%) still held by ops_tick's own %s" % (dev, level, BATTERY_LIFT, BATTERY_TAG)

            def remedy(dev=dev):
                out, rc = sh("bash %s release %s %s" % (HOLD_SH, dev, BATTERY_TAG))
                return "hold.sh release %s %s -> rc=%d %s" % (dev, BATTERY_TAG, rc, out.strip()[:200])

            jams.append(Jam("battery-lift", dev, msg, remedy, "release the hold"))
    return jams


def _disk_free_gb(path):
    try:
        return shutil.disk_usage(path).free / (1024 ** 3)
    except OSError:
        return None


def det_disk_low():
    """Disk below threshold on / (and C: if mounted under WSL): no safe auto remedy."""
    jams = []
    for path, label in ((os.environ.get("OPS_ROOT", "/"), "/"), (os.environ.get("OPS_CDRIVE", "/mnt/c"), "C:")):
        free = _disk_free_gb(path)
        if free is None:
            continue
        if free < DISK_FLOOR_GB:
            jams.append(Jam("disk-low", label, "%s has %.1f GB free (< floor %.0f GB)" % (label, free, DISK_FLOOR_GB), None, ""))
    return jams


def det_stopped_lane_queued():
    """A STOPPED lane with device work still queued or running for it: no safe auto remedy
    (cancelling someone's in-flight run needs judgement) -- escalates on sight."""
    jams = []
    stopped = glob.glob(os.path.join(BRIEFS, "*.md.STOPPED-by-owner-*"))
    for s in stopped:
        name = os.path.basename(s).split(".md.STOPPED-by-owner-")[0]
        for p in glob.glob(os.path.join(D, "queue", "*.req")) + glob.glob(os.path.join(D, "running", "*.req")):
            try:
                req = json.load(open(p))
            except Exception:
                continue
            purpose = str(req.get("purpose", ""))
            if name in os.path.basename(p) or re.search(r"\b" + re.escape(name) + r"\b", purpose):
                jams.append(Jam("stopped-lane-queued", name, "lane.%s is STOPPED but %s names it (%s)" % (name, os.path.basename(p), purpose[:120]), None, ""))
    return jams


DETECTORS = (det_hold_overbound, det_stranded_lanes, det_fold_failures, det_queue_stale,
             det_timer_unanchored, det_failed_unit, det_battery_floor, det_disk_low,
             det_stopped_lane_queued)

# No-remedy classes escalate the first time they are SEEN (there is nothing to try and
# re-check), rather than waiting ESCALATE_AFTER_MIN like a jam whose remedy might still work.
NO_REMEDY_ESCALATES_IMMEDIATELY = True


# --------------------------------------------------------------------- jams.tsv

JAMS_COLUMNS = ("opened", "class", "subject", "remedy_tried", "cleared_at", "time_to_clear_s")


def load_jams(path):
    rows = {}
    if not os.path.isfile(path):
        return rows
    with open(path) as f:
        for line in f:
            line = line.rstrip("\n")
            if not line or line.startswith("#"):
                continue
            parts = line.split("\t")
            if len(parts) != len(JAMS_COLUMNS):
                continue
            row = dict(zip(JAMS_COLUMNS, parts))
            rows[(row["class"], row["subject"])] = row
    return rows


def _tsv_safe(s):
    # remedy_tried carries a command's stdout (truncated, but not scrubbed) -- a literal tab or
    # newline in there would misalign every column after it, so flatten whitespace per field.
    return " ".join(str(s).split())


def save_jams(path, rows):
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        f.write("#" + "\t".join(JAMS_COLUMNS) + "\n")
        for row in sorted(rows.values(), key=lambda r: r["opened"]):
            f.write("\t".join(_tsv_safe(row.get(c, "")) for c in JAMS_COLUMNS) + "\n")
    os.replace(tmp, path)


def load_escalations(path):
    if os.path.isfile(path):
        try:
            return json.load(open(path))
        except Exception:
            return {}
    return {}


def save_escalations(path, data):
    tmp = path + ".tmp"
    json.dump(data, open(tmp, "w"), indent=1)
    os.replace(tmp, path)


def write_summary(jams_path, summary_path, escalations):
    rows = load_jams(jams_path).values()
    today = time.strftime("%Y-%m-%d")
    open_now = [r for r in rows if not r["cleared_at"]]
    cleared_today = [r for r in rows if r["cleared_at"].startswith(today)]
    ttcs = sorted(int(r["time_to_clear_s"]) for r in cleared_today if r["time_to_clear_s"])
    median_ttc = ttcs[len(ttcs) // 2] if ttcs else 0
    esc_today = [e for e in escalations.values() if e.get("last_ts", "").startswith(today)]
    cost_today = sum(float(e.get("cost_usd_total", 0)) for e in esc_today)
    with open(summary_path, "w") as f:
        f.write("ops summary %s: open=%d cleared_today=%d median_ttc_s=%d escalations_today=%d cost_today_usd=%.2f\n"
                % (today, len(open_now), len(cleared_today), median_ttc, len(esc_today), cost_today))
        for r in open_now:
            f.write("  OPEN  %s %s (opened %s, remedy: %s)\n" % (r["class"], r["subject"], r["opened"], r["remedy_tried"] or "none"))


# ------------------------------------------------------------------------ main

def run(shadow):
    os.makedirs(STATE_DIR, exist_ok=True)
    # Shadow keeps its OWN jams and escalations files beside the real ones. Without them every
    # shadow tick saw every jam as new and re-announced it (the 10-02 overnight log: 90x each), and
    # a would-be escalation never advanced its count. It never touches the real jams.tsv, which a
    # cutover tick would have to reconcile, and it writes no summary.txt.
    sfx = ".shadow" if shadow else ""
    jams_path = os.path.join(STATE_DIR, "jams%s.tsv" % sfx)
    esc_path = os.path.join(STATE_DIR, "escalations%s.json" % sfx)
    summary_path = os.path.join(STATE_DIR, "summary.txt")
    shadow_log = os.path.join(STATE_DIR, "shadow.log")

    detected = []
    for det in DETECTORS:
        try:
            detected.extend(det())
        except Exception as e:
            say("DETECTOR ERROR in %s: %r" % (det.__name__, e))
    by_key = {(j.cls, j.subject): j for j in detected}

    rows = load_jams(jams_path)
    escalations = load_escalations(esc_path)
    now_iso = time.strftime("%Y-%m-%dT%H:%M:%S")
    actions = []

    for jam in by_key.values():
        row = rows.get((jam.cls, jam.subject))
        if row is not None and row["cleared_at"]:
            row = None  # a previously-cleared (class, subject) that is back is a NEW instance,
            # not a re-check of the old one -- otherwise its age would be measured from the
            # first time this key ever jammed, and it would never re-run its remedy.
        is_new = row is None
        if is_new:
            row = {"opened": now_iso, "class": jam.cls, "subject": jam.subject,
                   "remedy_tried": "", "cleared_at": "", "time_to_clear_s": ""}
            rows[(jam.cls, jam.subject)] = row
            say("NEW JAM %s %s: %s" % (jam.cls, jam.subject, jam.msg))
            if jam.remedy and not shadow:
                result = jam.remedy()
                row["remedy_tried"] = result[:300]
                say("  remedy: %s" % result)
            elif jam.remedy:
                row["remedy_tried"] = ("[shadow] would: %s" % jam.remedy_label)[:300]
                actions.append("[shadow] would run remedy for %s %s: %s" % (jam.cls, jam.subject, jam.remedy_label))
            # A remedy-bearing jam gets its remedy applied before anything decides whether to
            # escalate it (below) -- a no-remedy jam falls straight through to that same check
            # on this SAME tick, since there is no remedy to wait on.

        # maybe escalate: a no-remedy class on sight, or anything that has outlived its
        # (already-applied, possibly on this very tick) remedy by ESCALATE_AFTER_MIN.
        opened_ts = time.mktime(time.strptime(row["opened"], "%Y-%m-%dT%H:%M:%S"))
        age_min = (NOW - opened_ts) / 60
        no_remedy = jam.remedy is None
        past_escalate = age_min >= ESCALATE_AFTER_MIN
        if no_remedy and is_new:
            actions.append("[shadow] no remedy for %s %s (escalate class)" % (jam.cls, jam.subject) if shadow else "no remedy for %s %s" % (jam.cls, jam.subject))
        if (no_remedy and NO_REMEDY_ESCALATES_IMMEDIATELY) or past_escalate:
            esc_key = jam.cls + "\t" + jam.subject
            esc = escalations.get(esc_key, {"count": 0})
            # Escalate again only once the previous escalation session has had time to run
            # (ESCALATE_AFTER_MIN) -- otherwise a jam open for hours would spawn one session
            # per 5-minute tick. A no-remedy jam re-escalates on the same cadence.
            last_ts = esc.get("last_epoch", 0)
            if NOW - last_ts >= ESCALATE_AFTER_MIN * 60:
                model = "claude-opus-5-5" if esc["count"] >= 1 else "claude-sonnet-5"
                if shadow:
                    cost = 0.0
                    actions.append("[shadow] would escalate %s %s on %s (count would become %d)" % (jam.cls, jam.subject, model, esc["count"] + 1))
                else:
                    cost = run_escalation(jam, row, model, esc["count"] + 1)
                    say("ESCALATED %s %s on %s ($%.2f)" % (jam.cls, jam.subject, model, cost))
                # Shadow advances the same count and clock a real escalation would, so the
                # model switch and the re-escalation cadence show what the cutover would do.
                esc["count"] += 1
                esc["last_epoch"] = NOW
                esc["last_ts"] = now_iso
                esc["cost_usd_total"] = float(esc.get("cost_usd_total", 0)) + cost
                escalations[esc_key] = esc

    # anything in rows no longer detected is cleared
    for k, row in list(rows.items()):
        if not row["cleared_at"] and k not in by_key:
            row["cleared_at"] = now_iso
            try:
                opened_ts = time.mktime(time.strptime(row["opened"], "%Y-%m-%dT%H:%M:%S"))
                row["time_to_clear_s"] = str(int(NOW - opened_ts))
            except ValueError:
                row["time_to_clear_s"] = ""
            say("CLEARED %s %s" % (row["class"], row["subject"]))

    save_jams(jams_path, rows)
    save_escalations(esc_path, escalations)
    if shadow:
        with open(shadow_log, "a") as f:
            f.write("%s tick: %d jam(s) detected\n" % (now_iso, len(by_key)))
            for a in actions:
                f.write("  " + a + "\n")
    else:
        write_summary(jams_path, summary_path, escalations)
    return len(by_key), actions


def run_escalation(jam, row, model, escnum):
    evidence = os.path.join(STATE_DIR, "evidence-%s-%s.txt" % (re.sub(r"\W+", "_", jam.cls), re.sub(r"\W+", "_", jam.subject)))
    with open(evidence, "w") as f:
        f.write("class: %s\nsubject: %s\nmessage: %s\nremedy tried: %s\nopened: %s\n"
                % (jam.cls, jam.subject, jam.msg, row.get("remedy_tried", ""), row.get("opened", "")))
    out, rc = sh("bash %s %s %s %s %s %d 2>&1" % (ESCALATE_SH, jam.cls, jam.subject, evidence, model, escnum), timeout=1500)
    m = re.search(r"COST_USD=([\d.]+)", out)
    return float(m.group(1)) if m else 0.0


if __name__ == "__main__":
    shadow = "--shadow" in sys.argv
    n, actions = run(shadow)
    say("tick done: %d jam(s) open%s" % (n, " (shadow)" if shadow else ""))
    for a in actions:
        say(" ", a)
