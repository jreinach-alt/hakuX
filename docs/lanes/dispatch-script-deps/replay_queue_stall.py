#!/usr/bin/env python3
"""Replay the dispatch queue's real history through fleet.queue_stall().

    replay_queue_stall.py [--dispatch DIR] [--step SECONDS] [--settle SECONDS]

WHY. The queue-stall guard wakes the board, and a guard that fires on a
healthy fleet costs a model session every twenty minutes. Fixtures hold only
the cases their author imagined. So this rebuilds the dispatch directory as it
stood every --step seconds, from what the real directory still records, and
asks the REAL queue_stall() about each moment -- none of its logic is copied
here. The two earlier rules are scored on the same moments, so the comparison
is between rules on one history, not between histories.

WHAT IS RECONSTRUCTED, AND FROM WHERE
  written   results/<id>/request.json mtime. request.sh writes a temp file and
            renames it into queue/, and every later rename keeps that mtime.
  claimed   results/<id>/ birth time (stat %W). serve_one mkdirs it right
            after the claim; on 1789968297-arms-primpv13-fix-2094234 it is the
            same second as the log's `request <id> from` line.
  finished  results/<id>/DONE, else ERROR, else result.json -- NOT the
            directory's mtime, which a later re-score bumps (z-tip-001's is
            09-13 11:06, seven hours after its DONE at 04:35).
  owner     result.json device_label, else the request's own `device`, else
            "unknown" -- a label no claimer has, so a device that was really
            busy with it reads as idle here. That can only ADD stalls.
  holds     dispatcher.log `HELD by .../hold/<label>`, released by the next
            `hold released` (last held, first released).
  lanes     nova from the log's first line; thor from its first `starting
            worker for bdc158a5`; each restart re-registers both. The desktop
            lane is left out: one claimer fewer can only ADD stalls.

WHAT IT CANNOT SEE, so read every episode against dispatcher.log:
  - requests withdrawn or never claimed (they have no results/<id>);
  - the host being off: WSL2 shut down leaves the directory looking idle and a
    queued request looking passed over, while no board tick ran at all;
  - a device absent while its worker churned (09-13 10:45, eight requeues).
"""
import argparse
import datetime
import json
import os
import re
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
TESTING = os.path.normpath(os.path.join(HERE, "..", "..", "testing"))
SERIALS = {"bdc158a5": "thor", "ee317437": "nova"}

ap = argparse.ArgumentParser(description=__doc__,
                             formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("--dispatch", default="/home/justin/hakux-work/dispatch")
ap.add_argument("--step", type=int, default=300)
ap.add_argument("--settle", type=int, default=120)
ap.add_argument("--year", type=int, default=2026,
                help="dispatcher.log stamps carry no year")
args = ap.parse_args()

RES = os.path.join(args.dispatch, "results")
LOG = os.path.join(args.dispatch, "logs", "dispatcher.log")


def load(p):
    try:
        with open(p) as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


# ------------------------------------------------------------ the requests
names = sorted(e.name for e in os.scandir(RES) if e.is_dir())
paths = [os.path.join(RES, n) for n in names]
stat = subprocess.run(["stat", "-c", "%W %Y %n"] + paths,
                      capture_output=True, text=True, check=True).stdout
reqs, skipped = [], []
for line in stat.splitlines():
    birth, mtime, p = line.split(" ", 2)
    n = os.path.basename(p)
    rq = os.path.join(p, "request.json")
    if int(birth) <= 0 or not os.path.exists(rq):
        skipped.append(n)
        continue
    req = load(rq)
    meta = load(os.path.join(p, "result.json"))
    owner = (meta.get("device_label") or "").strip() or \
            (req.get("device") or "").strip() or "unknown"
    claimed, finished = float(birth), float(mtime)
    for marker in ("DONE", "ERROR", "result.json"):
        if os.path.exists(os.path.join(p, marker)):
            finished = os.stat(os.path.join(p, marker)).st_mtime
            break
    written = min(os.stat(rq).st_mtime, claimed)
    reqs.append(dict(id=n, written=written, claimed=claimed,
                     finished=max(finished, claimed), owner=owner, req=req))

# --------------------------------------------------------- the log's events
stamp = re.compile(r"^(\d\d)-(\d\d) (\d\d):(\d\d):(\d\d) (.*)$")
events = []                      # (time, order, kind, payload)
first_log, held_stack = None, []
for line in open(LOG, errors="replace"):
    m = stamp.match(line.rstrip("\n"))
    if not m:
        continue
    mo, dd, hh, mi, ss, rest = m.groups()
    t = time.mktime(datetime.datetime(args.year, int(mo), int(dd), int(hh),
                                      int(mi), int(ss)).timetuple())
    if first_log is None:
        first_log = t
        events.append((t, 0, "register", "nova"))
    w = re.search(r"starting worker for (\w+)", rest)
    if w and w.group(1) in SERIALS:
        events.append((t, 0, "register", SERIALS[w.group(1)]))
    h = re.search(r"HELD by \S*/hold/(\w+);", rest)
    if h:
        held_stack.append(h.group(1))
        events.append((t, 0, "hold", h.group(1)))
    if rest.startswith("hold released") and held_stack:
        events.append((t, 0, "release", held_stack.pop()))
for r in reqs:
    events.append((r["written"], 1, "write", r))
    events.append((r["claimed"], 2, "claim", r))
    events.append((r["finished"], 3, "finish", r))
events.sort(key=lambda e: (e[0], e[1]))

# ------------------------------------------------- the simulated directory
S = tempfile.mkdtemp(prefix="replay-dispatch-")
for d in ("queue", "running", "results", "lanes", "hold"):
    os.makedirs(os.path.join(S, d))
os.environ["DISPATCH_DIR"] = S
sys.path.insert(0, TESTING)
import fleet  # noqa: E402  (reads DISPATCH_DIR at import)
assert fleet.D == S, "fleet.py must read the replay's directory"

me = str(os.getpid())            # a pid that is alive: serving() does kill -0
held = set()


def stamp_dir(d, t):
    os.utime(os.path.join(S, d), (t, t))


def apply(t, kind, x):
    if kind == "register":
        if x in held:
            return
        p = os.path.join(S, "lanes", x)
        with open(p, "w") as f:
            f.write(me + "\n")
        os.utime(p, (t, t))
        stamp_dir("lanes", t)
    elif kind == "hold":
        held.add(x)
        open(os.path.join(S, "hold", x), "w").close()
        stamp_dir("hold", t)
        if os.path.exists(os.path.join(S, "lanes", x)):
            os.unlink(os.path.join(S, "lanes", x))    # lane_release on hold
            stamp_dir("lanes", t)
    elif kind == "release":
        held.discard(x)
        os.unlink(os.path.join(S, "hold", x))
        stamp_dir("hold", t)
        apply(t, "register", x)
    elif kind == "write":
        p = os.path.join(S, "queue", x["id"] + ".req")
        with open(p, "w") as f:
            json.dump(x["req"], f)
        os.utime(p, (x["written"], x["written"]))
    elif kind == "claim":
        q = os.path.join(S, "queue", x["id"] + ".req")
        r = os.path.join(S, "running", x["id"] + ".req")
        if os.path.exists(q):
            os.rename(q, r)                              # keeps its mtime
        o = os.path.join(S, "running", x["id"] + ".owner")
        with open(o, "w") as f:
            f.write(x["owner"] + "\n")
        os.utime(o, (t, t))
        os.makedirs(os.path.join(S, "results", x["id"]), exist_ok=True)
        stamp_dir(os.path.join("results", x["id"]), t)
    elif kind == "finish":
        r = os.path.join(S, "running", x["id"] + ".req")
        if os.path.exists(r):
            os.rename(r, os.path.join(S, "results", x["id"], "request.json"))
        o = os.path.join(S, "running", x["id"] + ".owner")
        if os.path.exists(o):
            os.unlink(o)
        stamp_dir(os.path.join("results", x["id"]), t)


# --------------------------------------------- the two earlier rules, scored
def old_rule(now):
    """PR #206 as audited (4229a1216d): age > 120 min, a result newer."""
    out = []
    newest = max([os.stat(os.path.join(S, "results", n)).st_mtime
                  for n in os.listdir(os.path.join(S, "results"))] or [0])
    for n in sorted(os.listdir(os.path.join(S, "queue"))):
        if n.startswith("z-"):
            continue
        w = os.stat(os.path.join(S, "queue", n)).st_mtime
        if now - w > 7200 and newest > w:
            out.append(n[:-4])
    lanes = set(os.listdir(os.path.join(S, "lanes")))
    hold = set(os.listdir(os.path.join(S, "hold")))
    return [] if (lanes and lanes <= hold) else out


def audit_rule(now):
    """Audit pass 1's H1 remedy: a COMPLETED request queued after me."""
    done = []
    for n in os.listdir(os.path.join(S, "results")):
        if os.path.exists(os.path.join(S, "results", n, "request.json")):
            e = n.split("-", 1)[0]
            if e.isdigit():
                done.append(int(e))
    top = max(done or [0])
    out = []
    for n in sorted(os.listdir(os.path.join(S, "queue"))):
        e = n.split("-", 1)[0]
        if n.startswith("z-") or not e.isdigit():
            continue
        w = os.stat(os.path.join(S, "queue", n)).st_mtime
        if now - w > 7200 and top > int(e):
            out.append(n[:-4])
    return out


# ------------------------------------------------------------------ replay
start = min(e[0] for e in events)
end = max(e[0] for e in events)
t, i = start, 0
episodes = {"new": [], "held": [], "old": [], "audit": []}
open_ep = {}
samples = queued_samples = 0
while t <= end + args.step:
    while i < len(events) and events[i][0] <= t:
        apply(*events[i][0:1], *events[i][2:])
        i += 1
    samples += 1
    if os.listdir(os.path.join(S, "queue")):
        queued_samples += 1
        stalled, on_hold, blind = fleet.queue_stall(now=t, settle_s=args.settle)
        assert blind is None, blind
        verdict = {"new": {r[0]: r[2] for r in stalled},
                   "held": {r[0]: "held: " + r[2] for r in on_hold},
                   "old": {r: "" for r in old_rule(t)},
                   "audit": {r: "" for r in audit_rule(t)}}
    else:
        verdict = {"new": {}, "held": {}, "old": {}, "audit": {}}
    for rule, ids in verdict.items():
        ep = open_ep.get(rule)
        if ids and ep is None:
            open_ep[rule] = ep = {"start": t, "ids": {}, "samples": 0}
        if ids:
            ep["end"] = t
            ep["samples"] += 1
            for k, why in ids.items():
                ep["ids"].setdefault(k, why)
        elif ep is not None:
            episodes[rule].append(ep)
            open_ep[rule] = None
    t += args.step
for rule, ep in open_ep.items():
    if ep is not None:
        episodes[rule].append(ep)

fmt = lambda x: datetime.datetime.fromtimestamp(x).strftime("%m-%d %H:%M")
print("replayed %s .. %s, %d requests (%d without a birth time or request "
      "skipped), %d samples every %ds, %d with a non-empty queue, settle %ds"
      % (fmt(start), fmt(end), len(reqs), len(skipped), samples, args.step,
         queued_samples, args.settle))
for rule in ("new", "held", "old", "audit"):
    eps = episodes[rule]
    print("\n== %s rule: %d episode(s), %d FAIL sample(s)"
          % (rule, len(eps), sum(e["samples"] for e in eps)))
    for e in eps:
        print("  %s .. %s  %3d sample(s)  %d request(s)"
              % (fmt(e["start"]), fmt(e["end"]), e["samples"], len(e["ids"])))
        for k, why in sorted(e["ids"].items())[:6]:
            print("      %s%s" % (k, ("  <- " + why) if why else ""))
        if len(e["ids"]) > 6:
            print("      ... and %d more" % (len(e["ids"]) - 6))
