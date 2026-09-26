#!/usr/bin/env python3
"""What every agent is doing, what is waiting on the orchestrator, and what
could be dispatched right now and is not.

WHY THIS EXISTS. The orchestrator tracked the fleet in its own context. That
fails in four ways, all of which happened on 2026-09-14:

  - `ListAgents` ages out completed subagents. Six ran; three were listed.
  - A report says what an agent DID. Nothing recorded what it was ASKED, so
    after a context compaction the brief is gone and the work cannot be
    judged against it.
  - Nothing recorded that an agent was BLOCKED ON THE ORCHESTRATOR.
    lane.padwrite needed one line in vk/instance.c -- a file outside its
    four -- and said so in its final report. It sat until somebody read prose.
  - Nothing recorded whether a lane's output had been FOLDED. A lane that has
    reported and not been folded is invisible: territory still shows its claim,
    coverage still shows its issues owned, and the branch does not have its work.

And the failure that prompted this: #54 and #77 were reported as Nova-blocked
for a whole session on a claim -- "Galleon lives only on that handheld" --
that one read-only `device_titles thor` refutes. Nothing on disk could say
"these are dispatchable and nobody has dispatched them", so nobody asked.

WHERE THE FACTS COME FROM, AND WHY NOT FROM A REGISTRY ANY MORE.

Until 2026-09-19 every section below was computed from $DISPATCH_DIR/fleet/
<lane>.json, "written by the ORCHESTRATOR when it dispatches and updated when
a report lands". ORCHESTRATION-DESIGN.md §4 then deleted that role, and
nothing took over this piece: `lane.sh` had never written a registry entry,
so the file set froze on 09-14/09-18 and stayed frozen.

Measured 2026-09-19T06:20Z, with eight lanes running as systemd units: this
script reported four lanes RUNNING, of which two were not running at all and
one had been folded and merged twenty minutes earlier. Not one of the eight
appeared. Because the board wakes on the FAIL lines at the bottom of this
file, and all four were computed from that registry, six consecutive board
ticks logged `nothing actionable` -- and would have logged it just the same
with the fleet idle or with eight lanes in flight. A blind sensor reports
calm.

So every fact that decides a FAIL is now derived from the thing itself:

  RUNNING            systemctl --user list-units 'hakux-lane-*'
  READY, NOT FOLDED  REST /pulls: an open lane PR that is not a draft
  BLOCKED            REST /pulls: an open lane PR labelled `blocked`
  REMOTE LANES       a territory row carrying `remote`
  territory rows     board_files.load("territory.toml")

AND A LANE PR IS NOT DEFINED BY ITS BRANCH NAME. `lane/*` was a proxy for "a
branch a lane owns" and it failed on the one real lane that does not use the
prefix: `lane.remote`, a cloud session on `claude/...`, was counted in no PR
section and listed as a claim with no agent on every tick. Its liveness is not
a systemd unit and never can be, so subtracting the unit set says nothing about
it -- and this section is what a reader uses to decide a claim is stale, on a
row whose files a live session pushes to hourly.

A unit that is active is running; there is no state for it to be in that a
file could disagree with. A lane that has finished is one whose unit is gone,
and whether its work landed is a question about its PR, which GitHub answers.
Neither fact can go stale, because neither is recorded anywhere.

THE REGISTRY SURVIVES, DEMOTED. $DISPATCH_DIR/fleet/<lane>.json is now
written by `lane.sh` at start and cleared by it at exit, and holds only what
lane.sh knows first-hand: the brief it was handed (`asked`), the issues, the
attempt, the model, the branch and worktree. It carries NO `state` field,
because state is the thing that went stale. Here it is decoration on a lane
that systemd already says is running, plus the issue list that keeps a
running lane's issue out of DISPATCHABLE. An entry whose unit is not active
is ignored outright -- it can never create a lane, revive one, or suppress
work -- so the 38 pre-2026-09-19 entries are inert. `lane.sh fleet-gc`
deletes them; leaving them costs only disk.

  lane, unit, branch, worktree, brief, asked, issues[], attempt, model,
  started_utc   (and ended_utc/rc for the moment between exit and unlink)
"""
import datetime, json, os, subprocess, sys, time, tomllib

HERE = os.path.dirname(os.path.abspath(__file__))
D = os.environ.get("DISPATCH_DIR", "/home/justin/hakux-work/dispatch")
# Overridable so the issue-blind path can be exercised without unplugging the
# network. A gate whose failure branch has never run is not a gate.
REPO = os.environ.get("HAKUX_REPO", "jreinach-alt/hakuX")

# BESIDE THIS FILE, NOT ON THE CWD: selftest.d/93 and /55 both run this script
# from a scratch directory holding copies of it and its siblings. The `jobs/`
# display helper imported in main() is OPTIONAL for exactly that reason and
# this one is NOT -- it is how the script talks to GitHub at all, and a
# ModuleNotFoundError is the right, loud answer to a copy that left it behind.
sys.path.insert(0, HERE)
import gh_rest  # noqa: E402  (after the sys.path line it depends on)


def load_fleet():
    """The registry, keyed by lane. Decoration only -- see the header."""
    out = {}
    fdir = os.path.join(D, "fleet")
    if not os.path.isdir(fdir):
        return out
    for fn in sorted(os.listdir(fdir)):
        if not fn.endswith(".json"):
            continue
        try:
            e = json.load(open(os.path.join(fdir, fn)))
        except Exception as e2:
            print("  UNREADABLE %s: %s" % (fn, e2), file=sys.stderr)
            continue
        if isinstance(e, dict) and e.get("lane"):
            out[e["lane"]] = e
    return out


def sc(*args, timeout=15):
    """systemctl --user, or None if the user manager cannot be reached.

    None is NOT an empty fleet. Every caller distinguishes them, because
    reporting "nothing is running" when the question could not be asked is
    exactly the failure this file was rewritten to end: it would empty
    RUNNING, fill LANE CLAIMED WITH NO RUNNING AGENT, and hand DISPATCHABLE
    every issue a live lane already owns.
    """
    try:
        r = subprocess.run(["systemctl", "--user"] + list(args),
                           capture_output=True, text=True, timeout=timeout)
    except Exception:
        return None
    return r.stdout if r.returncode == 0 else None


def lane_units():
    """{lane: seconds-running-or-None}, or None if systemd could not answer.

    Two cheap calls, both under 50ms measured on the host: list-units to
    discover the names, then ONE keyed `show` for all of their start times.
    The board runs this file every twenty minutes under a 60s timeout, so a
    per-lane call is not affordable and is not made.
    """
    out = sc("list-units", "hakux-lane-*", "--state=active,activating",
             "--no-legend", "--plain")
    if out is None:
        return None
    names = [ln.split()[0] for ln in out.splitlines() if ln.split()]
    lanes = {n[len("hakux-lane-"):-len(".service")]: None for n in names
             if n.startswith("hakux-lane-") and n.endswith(".service")}
    if not names:
        return lanes
    # ActiveEnterTimestampMonotonic, not ActiveEnterTimestamp: the latter is
    # local time with a tz ABBREVIATION ("PDT"), which strptime %Z cannot be
    # trusted to read, and --timestamp=utc needs systemd 247.
    show = sc("show", *names, "--property=Id,ActiveEnterTimestampMonotonic")
    try:
        up = float(open("/proc/uptime").read().split()[0])
    except Exception:
        up = None
    if show and up is not None:
        ident = None
        for ln in show.splitlines():
            k, _, v = ln.partition("=")
            if k == "Id":
                ident = v
            elif k == "ActiveEnterTimestampMonotonic" and ident:
                lane = ident[len("hakux-lane-"):-len(".service")]
                try:
                    if lane in lanes and int(v) > 0:
                        lanes[lane] = up - int(v) / 1e6
                except ValueError:
                    pass
    return lanes


def age_s(secs):
    return "?" if secs is None else "%.1fh" % (secs / 3600.0)


def age(iso):
    # `iso` is the registry's started_utc, written and kept in UTC. Nothing
    # here needs converting: the output is a RELATIVE duration, and both sides
    # of the subtraction are tz-aware, so the answer is the same in any zone.
    try:
        t = datetime.datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ") \
            .replace(tzinfo=datetime.timezone.utc)
        h = (datetime.datetime.now(datetime.timezone.utc) - t).total_seconds() / 3600
        return "%.1fh" % h
    except Exception:
        return "?"


# A REQUEST NOBODY EVER CLAIMS LOOKS EXACTLY LIKE A BUSY FLEET.
#
# status.sh renders "N arms on a device, M queued" every tick and its own
# header says why it exists: "a jammed fleet and a running fleet rendered
# identically". It solved the RENDERING. Nothing escalated the numbers, so on
# 2026-09-20 four arms sat unclaimed -- the oldest for eighteen hours -- with
# two healthy handhelds, and the page said so the whole time. The cause was a
# stale $DISPATCH_DIR/bin/affinity.py pinning them to `desktop`, which claims
# only desktop pins. That is one cause; the check is deliberately about the
# SYMPTOM, because any cause that leaves work unclaimed looks the same from
# here and all of them are worth waking the board for.
#
# AGE IS NOT THE SYMPTOM, AND NEITHER IS LATER WORK FINISHING FIRST. The first
# version of this check fired on "a result landed after this was queued",
# which on a queue served in arrival order is true of every request that is
# not at the head (PR #206, audit pass 1, H1). Ranking queue epochs instead --
# "something queued after me was served first" -- fails one level down:
# affinity.py pins an A/B pair to one handheld, so the other handheld serves
# later work, correctly, while the pair waits for its own device.
# selftest.d/98 holds that case, and both of those rules fail it.
#
# WHAT SEPARATES THE TWO IS WHAT EACH CLAIMER DOES. A worker walks the queue in
# glob order and claims the first request affinity lets it have (the worker
# loop in dispatcher.sh; desktop_channel.sh's serve loop is the same
# protocol). So a claimer that is running X -- claimed after R was queued, X
# sorting after R -- walked past R: R was not its to take. So did a claimer
# that has sat idle for longer than a worker tick with R queued. When EVERY
# live claimer has done one or the other, nothing is going to claim R.
# Anything less, and R may be waiting for the one that has not.
#
# That evidence goes stale when something that decides R's pin changes: the
# set of live lanes (lanes/, hold/), or, for a request naming a prediction,
# where its siblings run or ran (running/, results/ -- affinity.py's rule 2).
# Evidence older than the last such change is not counted.
#
# A HOLD IS NOT A STALL. A request only a held device can take is reported as
# waiting on the hold, on stdout, and never costs a FAIL.
#
# The glob order is the workers' own: they run with LANG=C.UTF-8 (read from
# /proc/<pid>/environ on 2026-09-24), so bash sorts `queue/*.req` by
# codepoint, which is what sorting the file names here does. Names are
# compared WITH the `.req`, as the glob sees them: `123-a.req` sorts after
# `123-a-b.req`, while the bare ids sort the other way round.
#
# QUEUE_SETTLE_S is a few worker ticks. An idle worker walks the queue every
# ~20s at most (a 10s sleep on an empty queue, 5s after a pass that claimed
# nothing, plus the walk), so a request younger than this, or a claimer quiet
# for less than this, has not provably been seen by a whole walk.
QUEUE_SETTLE_S = int(os.environ.get("FLEET_QUEUE_SETTLE_S", "120"))


def _mtime(path):
    try:
        return os.stat(path).st_mtime
    except OSError:
        return 0.0


def _req(path):
    """(request, pin, rule-2 key) the way affinity.py reads them.

    An unreadable or malformed request reads as unpinned, which is also what
    the workers make of it: affinity.py prints nothing for it, or dies, and
    either way dispatcher.sh's `want` is empty and any worker may claim it.
    """
    try:
        with open(path) as fh:
            req = json.load(fh)
    except Exception:
        return {}, "", ""
    if not isinstance(req, dict):
        return {}, "", ""
    s = lambda v: v.strip() if isinstance(v, str) else ""
    return req, s(req.get("device")), os.path.basename(s(req.get("expect")))


def queue_stall(now=None, settle_s=None):
    """Queued requests that every live claimer has walked past.

    Returns (stalled, on_hold, blind):
      stalled  [(id, age_s, evidence)] -- nothing is going to claim these;
      on_hold  [(id, age_s, labels)]   -- only a held device can take these;
      blind    None, or why the queue could not be judged at all.
    Both lists oldest first. Never raises: this file also runs from scratch
    copies (selftest.d/93, /55) whose $DISPATCH_DIR has no queue at all.
    """
    now = time.time() if now is None else now
    settle_s = QUEUE_SETTLE_S if settle_s is None else settle_s
    qdir = os.path.join(D, "queue")
    try:
        queued = sorted(n for n in os.listdir(qdir) if n.endswith(".req"))
    except OSError:
        return [], [], None
    if not queued:
        return [], [], None
    # Liveness is affinity.py's own kill -0 test, not a second copy of it: the
    # scheduler decides who is serving, and this has to agree with it.
    # Imported here and not at the top because the scratch copies above carry
    # no affinity.py -- and have no queue, so they never reach this line.
    try:
        import affinity
    except ImportError as e:
        return [], [], ("affinity.py is not beside fleet.py (%s), so liveness "
                        "cannot be read the way the scheduler reads it" % e)
    live = set(affinity.serving(D))
    try:
        held = {h for h in os.listdir(os.path.join(D, "hold"))
                if not h.endswith(".why") and h != "lifted"}
    except OSError:
        held = set()
    pooled_unheld = set(affinity.pooled(D)) - held
    handhelds_held = held - set(affinity.OFFPOOL)

    # What each claimer is running, and when it claimed it. The owner file is
    # written at the claim (dispatcher.sh's serve_one, desktop_channel.sh's
    # dc_serve_one), and the rename into running/ keeps the request's own
    # mtime, so the two times are the claim and the queueing.
    rdir = os.path.join(D, "running")
    busy, between, last, sib = {}, set(), 0.0, {}
    try:
        owners = [n for n in os.listdir(rdir) if n.endswith(".owner")]
    except OSError:
        owners = []
    for n in owners:
        op = os.path.join(rdir, n)
        try:
            with open(op) as fh:
                lane = fh.read().strip()
        except OSError:
            continue
        claimed = _mtime(op)
        last = max(last, claimed)
        rq = n[:-len(".owner")] + ".req"
        if not os.path.exists(os.path.join(rdir, rq)):
            # The request has left running/ and its owner file is not swept
            # yet: that claimer is between two requests, not idle.
            between.add(lane)
            continue
        _, _, key = _req(os.path.join(rdir, rq))
        busy.setdefault(lane, []).append((rq, claimed, _mtime(os.path.join(rdir, rq))))
        if key:
            sib[key] = max(sib.get(key, 0.0), claimed)
    # Every claim and every finish adds an entry to results/<id>/, so the
    # newest directory mtime is the last time any claimer did anything. Only
    # a result newer than some running claim can re-pin that claim's siblings
    # (affinity.py rule 2), so only those request files are opened.
    first_claim = min((c for runs in busy.values() for _, c, _ in runs),
                      default=None)
    try:
        entries = list(os.scandir(os.path.join(D, "results")))
    except OSError:
        entries = []
    for e in entries:
        try:
            if not e.is_dir():
                continue
            m = e.stat().st_mtime
        except OSError:
            continue
        last = max(last, m)
        if first_claim is not None and m >= first_claim:
            _, _, key = _req(os.path.join(e.path, "request.json"))
            if key:
                sib[key] = max(sib.get(key, 0.0), m)
    # The last time the set of claimers changed: a lane registering or
    # releasing (lanes/), a worker restarting under a new pid (its own lane
    # file), a hold placed or lifted (hold/).
    epoch = max([_mtime(os.path.join(D, "lanes")), _mtime(os.path.join(D, "hold"))]
                + [_mtime(os.path.join(D, "lanes", l)) for l in live])

    stalled, on_hold = [], []
    for name in queued:
        path = os.path.join(qdir, name)
        written = _mtime(path)
        age = now - written
        if not written or age <= settle_s:
            continue                   # no whole walk has provably seen it
        rid = name[:-len(".req")]
        _, pin, key = _req(path)
        if pin:                        # affinity.py rule 1
            if pin in held:
                on_hold.append((rid, age, pin))
                continue
            claimers = {pin} & live
        elif handhelds_held and not pooled_unheld:
            on_hold.append((rid, age, ",".join(sorted(handhelds_held))))
            continue
        else:
            claimers = set(live)
        if not claimers:
            if now - epoch > settle_s:
                stalled.append((rid, age, (
                    "pinned to %s, which no live worker serves and nobody "
                    "has held" % pin) if pin else
                    "no dispatch worker is alive and no device is held"))
            continue
        changed = max(epoch, sib.get(key, 0.0))
        quiet_since = max(written, last, epoch)
        evidence = []
        for lane in sorted(claimers):
            ev = None
            if lane in busy:
                for x, claimed, xw in busy[lane]:
                    if x > name and claimed > changed and \
                            (xw > written or claimed > written + settle_s):
                        ev = "%s claimed %s after it" % (lane, x[:-len(".req")])
                        break
            elif lane not in between and now - quiet_since > settle_s:
                ev = "%s idle, nothing claimed or finished for %s" \
                     % (lane, age_s(now - quiet_since))
            if ev is None:
                break                  # this one may yet take it
            evidence.append(ev)
        else:
            stalled.append((rid, age, "; ".join(evidence)))
    stalled.sort(key=lambda r: -r[1])
    on_hold.sort(key=lambda r: -r[1])
    return stalled, on_hold, None


# A PR the machine has already picked up is not the board's to act on. These
# are exactly the labels roles/board.md names in its own rule: "a PR that is
# not a draft and has no needs-audit-*, needs-remediation, fold-ready or
# folded label -> needs-audit-1". `needs-rebase` and `claimed:cloud` are here
# for the same reason -- another job holds it.
IN_FLIGHT = {"needs-audit-1", "needs-audit-2", "needs-remediation",
             "fold-ready", "folded", "needs-rebase", "claimed:cloud"}


def remote_lanes(terr):
    """{branch: lane} for every territory row marked `remote`.

    A LANE IS A ROW IN territory.toml, NOT A BRANCH NAME. `lane.remote` is a
    cloud session on `claude/docs-tooling-agentic-coding-u152m1`; before this
    it was counted in no PR section and reported in LANE CLAIMED WITH NO
    RUNNING AGENT every tick, because its liveness is not a `hakux-lane-*`
    unit and never can be. The board could therefore dispatch a local lane
    onto files that lane holds, with territory.toml the only thing in the way.

    The marker's VALUE is the branch (`remote = "claude/..."`); `remote = true`
    means the conventional `lane/<row name>`. See jobs/remote-lane.sh, which is
    the same rule for the shell jobs -- a boolean alone cannot answer the
    question this function is asked, which is "whose branch is this?".
    """
    out = {}
    for lane, meta in (terr.get("lane") or {}).items():
        r = meta.get("remote")
        if r is True:
            out["lane/" + lane] = lane
        elif isinstance(r, str) and r.strip():
            out[r.strip()] = lane
    return out


def lane_prs(remote=None):
    """Open PRs a lane owns, or None if gh could not answer.

    A `lane/*` head, or a head some territory row names as its remote lane's.
    One LIST, not a call per lane: everything the READY-NOT-FOLDED and BLOCKED
    sections need comes out of it. (One HTTP call per hundred PRs, since REST
    pages -- see gh_rest.)

    OVER REST, because `gh pr list` is GraphQL and a Claude Code cloud
    session's proxy refuses GraphQL outright -- so there this returned None on
    every call and the report was permanently PR-BLIND. That at least PRINTS
    what it could not see, which is why this half of the defect was survivable
    and check_coverage.py's silent `ok` was not; it was still wrong, and the
    same credential answers over REST. gh_rest.open_prs normalises the field
    names back onto the `gh pr list --json` spellings used below -- including
    `head.ref` back to `headRefName`, which is what the `remote` map is keyed
    on, so a remote lane's branch is matched over REST exactly as it was over
    GraphQL.

    NO PULL-REQUEST FILTER IS NEEDED HERE and its absence is not an oversight:
    /pulls returns only pull requests. It is /issues that returns both, which
    is gh_rest.open_issues' problem and is documented there.
    """
    remote = remote or {}
    rows, err = gh_rest.open_prs(REPO)
    if rows is None:
        print("gh pr list did not answer (%s)" % err, file=sys.stderr)
        return None
    out = []
    for p in rows:
        ref = p.get("headRefName") or ""
        if ref in remote:
            p["lane"] = remote[ref]
            p["remote"] = True
        elif ref.startswith("lane/"):
            p["lane"] = ref[len("lane/"):]
            p["remote"] = False
        else:
            continue
        p["labelset"] = {l.get("name") for l in (p.get("labels") or [])}
        out.append(p)
    return out


def pr_state(n):
    """(head sha, mergeable, ci) for one PR, or None if gh could not answer.

    `mergeable` is GitHub's: True, False (CONFLICTING) or None (not computed
    yet). `ci` is one word about the check runs on the head: "green", "red:
    <names>", "running", or "never ran". A PR with no check run at all has no
    verdict, and that is not the same as a green one: a merge conflict creates
    no workflow run (AGENTS.md), and neither did the retired skip-ci marker.
    """
    pr, err = gh_rest._api("repos/%s/pulls/%d" % (REPO, n))
    if err or not isinstance(pr, dict):
        return None
    if pr.get("mergeable") is None:
        # GitHub computes mergeability lazily: the first GET after the base
        # moves answers null and starts the job. Measured on #321, the PR
        # this rule was written about: null on the first ask.
        time.sleep(float(os.environ.get("FLEET_MERGEABLE_WAIT", "3")))
        again, err = gh_rest._api("repos/%s/pulls/%d" % (REPO, n))
        if not err and isinstance(again, dict):
            pr = again
    sha = (pr.get("head") or {}).get("sha") or ""
    runs, err = gh_rest._api("repos/%s/commits/%s/check-runs?per_page=100"
                             % (REPO, sha))
    if err or not isinstance(runs, dict):
        return None
    runs = runs.get("check_runs") or []
    red = sorted({r.get("name") or "?" for r in runs
                  if r.get("conclusion") in ("failure", "cancelled",
                                             "timed_out", "action_required")})
    if not runs:
        ci = "never ran"
    elif red:
        ci = "red: " + ", ".join(red)
    elif any(r.get("status") != "completed" for r in runs):
        ci = "running"
    else:
        ci = "green"
    return sha, pr.get("mergeable"), ci


def labelled_at(n, label):
    """When `label` was last added to PR/issue n, as a UTC datetime, or None."""
    rows, err = gh_rest._paged(REPO, "issues/%d/events" % n, "")
    if err:
        return None
    when = None
    for e in rows:
        if e.get("event") == "labeled" and \
                (e.get("label") or {}).get("name") == label:
            when = e.get("created_at") or when
    if not when:
        return None
    return datetime.datetime.strptime(when, "%Y-%m-%dT%H:%M:%SZ") \
                   .replace(tzinfo=datetime.timezone.utc)


FOLD_STUCK_S = 3600


def fold_watch(prs, terr, units, now=None):
    """What the fold pipeline is waiting on, from each PR's live state.

    -> (release, stuck, unread)

      release  [(lane, pr, [files])]  a READY lane PR -- out of draft, CI
               green on its head, its unit gone -- whose territory row still
               holds files it has not released. roles/board.md: those files go
               in `released = [...]` on the row, and the next lane may take
               them. The row keeps them in `files`, for the audit and the fold.
      stuck    [(pr, lane, age_s or None, reason, fixer)]  a `fold-ready` PR
               that is CONFLICTING (at once: it cannot fold until someone
               merges), or that has carried the label for FOLD_STUCK_S with
               anything else in the way.
      unread   int  PRs whose state gh would not give; said, never guessed.

    WHY RELEASE AT READY. On 2026-09-26 this report counted 31 dispatchable
    issues, 4 lanes running under a cap of 24, and every board tick said
    "every issue needs a file another lane holds". Nine hot files were held
    by lanes whose code was finished and waiting for two audits and the
    one-at-a-time fold -- hours per PR, serialising the whole backlog.
    """
    now = now or datetime.datetime.now(datetime.timezone.utc)
    rows = terr.get("lane") or {}
    release, stuck, unread = [], [], 0
    for p in prs:
        if p.get("isDraft"):
            continue
        n = p["number"]
        folding = "fold-ready" in p["labelset"]
        meta = rows.get(p["lane"]) or {}
        todo = [f for f in meta.get("files", [])
                if f not in meta.get("released", [])]
        # A remote lane's liveness is not a local unit, so "its unit is gone"
        # is never known of it; its files are released by hand, if at all.
        # And units=None (FLEET-BLIND) means no lane is known to have stopped.
        cand = (todo and not p.get("remote") and units is not None
                and p["lane"] not in units)
        if not (folding or cand):
            continue
        st = pr_state(n)
        if st is None:
            unread += 1
            continue
        sha, mergeable, ci = st
        if cand and ci == "green":
            release.append((p["lane"], n, todo))
        if not folding:
            continue
        since = labelled_at(n, "fold-ready")
        age = (now - since).total_seconds() if since else None
        if mergeable is False:
            stuck.append((n, p["lane"], age, "CONFLICTING with master",
                          "host-tools/unjam_index.sh if only the nv2a index "
                          "conflicts, else handback.sh sends it back to the "
                          "lane to merge master"))
            continue
        if age is None or age < FOLD_STUCK_S:
            continue
        if ci == "never ran":
            why = "CI never ran on %s" % sha[:10]
            fix = ("check mergeability first (no run is what a conflict "
                   "leaves); else the lane pushes an empty commit "
                   "'ci: build this head'")
        elif ci.startswith("red"):
            why = "CI %s on %s" % (ci, sha[:10])
            fix = "handback.sh resumes the lane; read the failing check's date first"
        elif ci == "running":
            why = "CI still running on %s" % sha[:10]
            fix = "wait for it; if it never settles, re-run it"
        elif mergeable is None:
            why = "GitHub has not computed mergeability"
            fix = "the next fold tick asks again"
        else:
            why = "CI green and mergeable, and fold.sh has not taken it"
            fix = "read $WORK/fold.log for why fold.sh skipped it"
        stuck.append((n, p["lane"], age, why, fix))
    return release, stuck, unread


def released_files(terr):
    """[(file, released_by, taken_by or None)] -- files freed at PR-ready.

    A released file is AVAILABLE: the next lane may claim it. `taken_by` is
    the row that has since claimed it without releasing it (check_territory.py
    allows exactly one such row).
    """
    rows = terr.get("lane") or {}
    out = []
    for lane, meta in sorted(rows.items()):
        for f in meta.get("released", []):
            taken = [l for l, m in rows.items() if l != lane
                     and f in m.get("files", []) and f not in m.get("released", [])]
            out.append((f, lane, taken[0] if taken else None))
    return out


def main():
    fleet = load_fleet()
    # The board lives on the `board` branch when it exists, and in the tree
    # until then; board_files says which was read, so a stale local copy is
    # never quoted as a live one (docs/ORCHESTRATION-DESIGN.md §5).
    sys.path.insert(0, HERE)
    # After HERE, not before it: jobs/ is a supplement to this directory, not
    # a shadow of it.
    sys.path.insert(1, os.path.join(HERE, "jobs"))
    import board_files
    try:
        from localtime import say_time
    except ImportError:
        # THIS FILE IS ALSO RUN FROM A COPY OF ITSELF. selftest.d/93's board
        # fixture copies exactly check_coverage.py, fleet.py and board_files.py
        # into a scratch directory and runs fleet.py there, so anything this
        # file imports must either be one of those three or be optional. An
        # unguarded `from localtime import ...` took out all ten of that
        # fragment's checks at once.
        #
        # Degrade to UTC and SAY UTC. The failure mode this whole change exists
        # to prevent is a clock that is labelled with a zone it is not in; a
        # line that reads "UTC" while being UTC costs a reader nothing.
        def say_time():
            return datetime.datetime.now(datetime.timezone.utc) \
                           .strftime("%Y-%m-%d %H:%M UTC")
    terr = board_files.load("territory.toml")
    tracker = board_files.load("nv2a_issues.toml")["issue"]
    # Everything else this report prints is a RELATIVE duration ("4.2h"), which
    # needs no zone. That is also why it never said when "4.2h ago" was counted
    # back from -- a report pasted into an issue an hour later reads as current.
    # One absolute line, in the display zone, fixes that.
    print("fleet report generated %s" % say_time())
    print("board read from: territory.toml <- %s, nv2a_issues.toml <- %s"
          % (board_files.source("territory.toml"),
             board_files.source("nv2a_issues.toml")))

    # A TIMEOUT, BECAUSE THE RISK HERE IS A STALL AND NOT THE RATE LIMIT.
    #
    # Measured 2026-09-14: the token's core and graphql limits are both
    # 5,000/hour with 0 used, and `gh issue list` returns in well under a
    # second. Even a call per watchdog poll could not approach the limit --
    # and the watchdog does not poll this anyway, because check_coverage.py
    # only runs once the session has been idle and armed, not every 20s.
    #
    # So caching would solve a problem that does not exist. What DID need
    # fixing is that this call had no timeout at all: a hung `gh` -- an auth
    # prompt, a wedged connection -- blocks forever, and anything that invokes
    # this from a poll loop then stops reporting the fleet at exactly the
    # moment the fleet is stuck. Fail fast and say the report is issue-blind.
    #
    # AND IT IS REST NOW, for the reason spelled out in gh_rest: `gh issue
    # list` is GraphQL, a cloud session's proxy refuses GraphQL, and this
    # branch's issue-blind path was the ONLY path taken there. The timeout
    # argument above is unchanged and still the reason a per-page timeout
    # exists; gh_rest's is 40s.
    rows, dropped_prs, why = gh_rest.open_issues(REPO)
    if rows is None:
        print("cannot reach gh (%s); fleet report is issue-blind -- the "
              "DISPATCHABLE section below is EMPTY BECAUSE IT WAS NOT "
              "COMPUTED, which is not the same as nothing being dispatchable"
              % why, file=sys.stderr)
        live, titles = set(), {}
    else:
        live = {str(x["number"]) for x in rows}
        titles = {str(x["number"]): x["title"] for x in rows}
        # The PR filter, reported rather than trusted. REST's /issues hands
        # back pull requests too, and an unfiltered read would put every open
        # PR into `live` -- where a tracker row keyed on that number does not
        # exist, so fleet would announce each one as an unclassified issue.
        print("issue list over REST: %d open issue(s), %d pull request(s) "
              "dropped from the /issues response" % (len(rows), dropped_prs))

    # ---------------------------------------------------- the derived fleet
    units = lane_units()
    fleet_blind = units is None
    if fleet_blind:
        units = {}
        print("FLEET-BLIND: systemctl --user did not answer, so the RUNNING "
              "set could not be computed. RUNNING below is EMPTY BECAUSE IT "
              "WAS NOT ASKED, which is not the same as an idle fleet -- and "
              "the sections that subtract it (DISPATCHABLE, LANE CLAIMED "
              "WITH NO RUNNING AGENT, RUNNING WITH NO TERRITORY ROW, BLOCKER "
              "NEVER RECORDED AS TESTED) are suppressed rather than computed "
              "against an empty set.",
              file=sys.stderr)
    running = sorted(units)

    # AND IT IS ITS OWN FAIL, unlike the gh blindness below. board.sh keeps
    # only the lines matching '^FAIL' and drops the rest, so anything said any
    # other way is said to nobody -- which is how this whole file came to
    # report calm for five days. The two are not treated alike on purpose:
    #
    #   gh unreachable   transient, retried in twenty minutes, nothing a board
    #                    tick can do about it. Fails open, as it always has.
    #   systemctl --user unreachable FROM A PROCESS WHOSE JOB IS TO MANAGE
    #                    USER UNITS is a configuration defect. It does not
    #                    self-heal and nobody finds out any other way.
    if fleet_blind:
        print("FAIL: FLEET-BLIND -- systemctl --user did not answer, so this "
              "report cannot say what is running. No other FAIL below was "
              "computed. Check the user manager on the host "
              "(`systemctl --user list-units`); the fleet is unobservable "
              "until it answers.", file=sys.stderr)

    remote = remote_lanes(terr)
    prs = lane_prs(remote)
    pr_blind = prs is None
    if pr_blind:
        prs = []
        print("PR-BLIND: gh pr list did not answer, so READY NOT FOLDED and "
              "BLOCKED were not computed. Fails open like the issue list "
              "above: a network blip is not a board item.", file=sys.stderr)

    # An entry for a lane whose unit is not active is garbage by construction:
    # lane.sh writes one at start and unlinks it at exit. Counted, never shown
    # as a lane, never able to suppress a dispatch. See the header.
    stale_reg = sorted(k for k in fleet if k not in units)

    owned = {}
    for lane, meta in (terr.get("lane") or {}).items():
        for i in meta.get("issues", []):
            owned[str(i)] = lane
    # A RUNNING lane's own issues, from the registry lane.sh wrote at start.
    # This is the one place the registry can withhold work, and it can only do
    # so for a lane systemd says is live this second.
    for lane in running:
        for i in (fleet.get(lane, {}).get("issues") or []):
            owned.setdefault(str(i), lane)
    lanes_with_agent = set(running)

    # REPORTED, NOT FOLDED, asked of GitHub instead of a `state` field: an
    # open lane PR that is not a draft is a lane that has said it is done.
    # Carrying one of IN_FLIGHT means a job already holds it, and that is the
    # pipeline working, not an item for the board.
    unfolded = [p for p in prs
                if not p.get("isDraft") and not (p["labelset"] & IN_FLIGHT)]

    # WAITING. The old section read the registry's `waiting_on` and printed it
    # under "WAITING ON THE ORCHESTRATOR"; there is no orchestrator, nothing
    # has written that field since 09-14, and papercuts.toml bit 245 records
    # that the field conflated four different waiters anyway. A lane that is
    # stuck now says so with the `blocked` label and a `[lane.<n>] blocked:`
    # comment (roles/lane.md), and the board's step 5 acts on the label.
    #
    # WHAT THIS CANNOT SEE: a blocked: COMMENT with no label. Reading comments
    # is a call per PR and the budget here is two calls total, so the label is
    # the contract. A lane that only comments is invisible to the board.
    waiting = [p for p in prs if "blocked" in p["labelset"]]

    # A lane row with no running agent is coverage that does not exist. This is
    # the state territory.toml's own [free] comment warns about, and nothing
    # could detect it before.
    #
    # Empty when fleet-blind, or it would name EVERY territory row: it is the
    # one section here that an empty running set makes maximally wrong rather
    # than merely silent. It sets no rc, so this changes no wake-up -- but a
    # reader acting on a full list of "abandoned" claims would retire the live
    # fleet's rows, and the FLEET-BLIND line promises it is not computed.
    #
    # A REMOTE LANE IS NEVER A GHOST. Its liveness is not a `hakux-lane-*`
    # unit and never can be -- it runs in a cloud container this host cannot
    # see -- so subtracting the unit set says nothing about it. Listing it here
    # was not merely noise: this section is the evidence a reader uses to
    # retire a claim, and retiring `lane.remote`'s row would free files a live
    # session pushes to hourly. It is reported under REMOTE LANES instead.
    ghost = [] if fleet_blind else sorted(
        lane for lane in (terr.get("lane") or {})
        if lane not in units and lane not in remote.values())

    # THE OTHER DIRECTION, AND IT IS THE WORSE ONE: an agent that is RUNNING
    # with no row in territory.toml at all.
    #
    # `ghost` above catches a claim with no agent -- coverage asserted that
    # does not exist, which over-reports and is conservative. This catches an
    # agent with no claim, and that one is invisible to EVERY guard, because
    # check_territory.py cannot see a lane that is not in the file. None of
    # the checks that caught real collisions on 2026-09-13 could have fired
    # for it.
    #
    # Three occurrences in one night, each a different variant, which is why
    # it is bit=3 in papercuts.toml and a rule in AGENTS.md rather than three
    # corrections: no row written at all (lane.padwrite, which then edited
    # three files, and nothing collided only because nothing else wanted them
    # that hour); a row written and validated but COMMITTED AFTER DISPATCH, so
    # the lane fast-forwarded to a tip that predated it and spent its whole
    # life against a table where its files sat in [free] (lane.tcginval); and
    # no row because an auditor claims no files (lane.audit-tcg). AGENTS.md:
    # "the brief is not the claim, and an uncommitted claim is not a claim
    # either."
    #
    # A LANE WITH `files = []` STILL COUNTS AS CLAIMED. The row is what
    # matters, not the territory -- an auditor that edits nothing still has to
    # be visible to the board, and requiring files would re-create the third
    # variant exactly.
    #
    # THE RESIDUAL HOLE IS NOW CLOSED, AND THAT IS WHY THIS SECTION FILLED UP.
    # Until 2026-09-19 both sides of this cross-check were orchestrator-written
    # files, so "a lane running with no fleet row EITHER" was invisible here as
    # well -- and after the role was deleted that was EVERY lane. The running
    # side is systemd now. The first run of this version against the live host
    # found nine active units and eleven territory rows with no unit among
    # them: an entirely disjoint pair of sets, six of the nine editing
    # docs/testing/jobs/selftest.sh at the same time. This FAIL is cleared by
    # the board writing the rows, which is AGENTS.md's ordering anyway.
    unclaimed = sorted(lane for lane in running
                       if lane not in (terr.get("lane") or {}))

    # DISPATCHABLE: open, not owned by a lane with a running agent, and with
    # no blocker -- or a blocker that has never been tested. A blocker is a
    # claim (AGENTS.md), and five of this campaign's were false this week.
    #
    # I TRIED TO DETECT AN UNTESTED BLOCKER FROM ITS PROSE AND IT DOES NOT
    # WORK. Measured 2026-09-14 over all 23 blockers in the tracker, scoring
    # each for six candidate signals of having been tested -- the words
    # MEASURED/REFUTED/VERIFIED, an ISO date, a quantity with units, a capture
    # key, a named tool, a source file:
    #
    #     MEASURED/REFUTED/verified     5 of 23
    #     an ISO date                  13 of 23
    #     a number with units/px        8 of 23
    #     names a capture key           7 of 23
    #     names a tool/command          8 of 23
    #     names a source file           15 of 23
    #     NO signal at all              3 of 23
    #
    # Twenty of 23 carry at least one signal, so the rule flags almost
    # nothing. Worse, it flags the WRONG three: #68, #69 and #73 are the only
    # signal-free blockers and all three are sound scope decisions ("belongs
    # to the tier-1 owner; blast radius is every guest instruction"), not
    # guesses. The signals separate TECHNICAL prose from POLICY prose, which
    # is not the question.
    #
    # And there is a reason no text rule can work: THE TRACKER RECORDS A
    # REFUTATION IN THE SAME FIELD AS THE CLAIM. Once a blocker is disproved
    # the field is rewritten to say so, so the refuted ones read as the
    # best-evidenced ones afterwards -- #59's now opens "NOT A TERRITORY
    # PROBLEM AT ALL, MEASURED 2026-09-14". Before the test it read
    # confidently too. A classifier cannot see a tense.
    #
    # So this asks for a STRUCTURED claim instead of sniffing prose, which is
    # what AGENTS.md already asks for in words: "Write the blocker down in the
    # form of the measurement that would refute it". An entry carries
    # `blocker_falsifier` (what would show the blocker is false) and
    # `blocker_tested` (when it was last run) or it does not, and only the
    # absence is reportable. nv2a_issues.toml is the ORCHESTRATOR's file, so
    # this reads those keys and does not invent them: until they are written
    # every blocker reports UNTESTED, which is accurate -- none of them has
    # ever been recorded as tested -- and is listed separately from the
    # genuinely unblocked so it cannot be mistaken for a dispatch queue.
    #
    # DISPATCHABLE IS NOW A STRUCTURED FIELD TOO, AND THE PROSE SNIFF IS GONE.
    # This section used to read `"NOT BLOCKED" in blocked_on.upper()`, which
    # was the right instinct against the wrong schema: check_coverage.py
    # accepted ANY non-empty `blocked_on` as coverage and nothing else, so the
    # board's only way to satisfy preflight for an issue it could not dispatch
    # this tick was to write into the field that means "do not dispatch this" --
    # and six open rows on 2026-09-18 duly opened with the words "NOT BLOCKED".
    # The sniff undid that from this side and cost a false positive to do it:
    # #92's field says "I had written NOT BLOCKED and then left it
    # unallocated", the board recording a wording it had ALREADY corrected,
    # and the substring search reported the row as dispatchable on the
    # strength of that sentence.
    #
    # `dispatch_state = "available"` is now the third state check_coverage.py
    # accepts, so the prose has no job left. "Available" is about the
    # OBSTACLE; whether a lane is on it is territory.toml's, which is why the
    # running-lane skip above still applies on top of it.
    #
    # AN UNCLASSIFIED ROW IS REPORTED SEPARATELY AND STILL SETS rc. No
    # blocker, no `dispatch_state`, no running lane: an empty row is not a
    # dispatch queue, and calling it dispatchable would assert the board is
    # sitting on work it can start -- a stronger claim than an empty row
    # supports, and exactly the "available by default" direction that got
    # finished work re-dispatched before.
    #
    # AND IT MUST NOT STOP COSTING A FAIL, which took a second pass to see. The old
    # code called such a row dispatchable, which was the wrong description AND
    # a non-zero exit; moving it to a note would have been the right
    # description and a SILENT one. #34 and #62 are in exactly this state on
    # the live board today (owned by lane.remote, no blocker, nothing else), so
    # the hole would have opened the moment that lane stopped running. Separate
    # section, accurate words, same exit code.
    dispatchable = []
    untested = []
    unclassified = []
    # fleet_blind: "I could not ask systemd" is not "nothing is running", and
    # the running-lane skip below is what keeps a live lane's rows out of both
    # lists. With no running set there is nothing to skip WITH, so neither
    # section is computed -- see the NOT COMPUTED headings below.
    for n in ([] if fleet_blind else sorted(live, key=int)):

        lane = owned.get(n)
        if lane and lane in lanes_with_agent:
            continue
        ent = tracker.get(n, {})
        b = (ent.get("blocked_on") or "").strip()
        st = (ent.get("dispatch_state") or "").strip()
        if st == "available":
            dispatchable.append((n, lane, "dispatch_state=available",
                                 titles.get(n, "")[:52]))
        elif b and not (ent.get("blocker_tested") or "").strip():
            untested.append((n, lane, (ent.get("blocker_falsifier") or "").strip(),
                             titles.get(n, "")[:52]))
        elif not b and st != "blocked":
            unclassified.append((n, lane, titles.get(n, "")[:52]))

    pr_of = {}
    for p in prs:
        pr_of.setdefault(p["lane"], p)

    print("=== RUNNING (%d)%s" % (len(running),
                                  "  -- NOT COMPUTED, see FLEET-BLIND above"
                                  if fleet_blind else ""))
    for lane in running:
        f = fleet.get(lane, {})
        p = pr_of.get(lane)
        print("  %-12s %-18s #%-10s %-7s %s"
              % (lane,
                 ("attempt %s/%s" % (f.get("attempt", "?"),
                                     (f.get("model") or "?").replace("claude-", "")))[:18],
                 ",".join(str(i) for i in (f.get("issues") or [])) or "-",
                 age_s(units.get(lane)),
                 ("PR #%d%s" % (p["number"], " draft" if p.get("isDraft") else " READY"))
                 if p else "no PR yet"))
        print("      asked: %s" % ((f.get("asked") or
                                    "(no registry entry -- started before "
                                    "lane.sh wrote one, or not by lane.sh)")[:96]))
    if stale_reg:
        print("  (%d registry entr%s for lanes with no active unit, ignored; "
              "`lane.sh fleet-gc` deletes them)"
              % (len(stale_reg), "y" if len(stale_reg) == 1 else "ies"))

    # ELSEWHERE, NOT GONE. A lane whose row carries `remote` runs somewhere
    # this host cannot observe, so neither RUNNING nor LANE CLAIMED WITH NO
    # RUNNING AGENT is the truth about it. It gets a line of its own saying
    # what IS known: its branch, its PR, and that nothing local can wake it.
    # No FAIL FROM THIS SECTION: there is no action a board tick could take
    # from here, and a standing wake-up the board cannot clear spends a window
    # every twenty minutes for nothing. Its PR can still raise one through
    # `unfolded` and `waiting` below, and should -- a remote lane's ready PR
    # enters the audit pipeline exactly like any other. The line this section
    # does not want is the permanent one about the lane itself.
    if remote:
        print("\n=== REMOTE LANES (%d) -- no local unit, and that is not a fault"
              % len(remote))
        for branch, lane in sorted(remote.items(), key=lambda kv: kv[1]):
            p = pr_of.get(lane)
            print("  %-12s %-44s %s"
                  % (lane, branch,
                     ("PR #%d%s" % (p["number"], " draft" if p.get("isDraft") else " READY"))
                     if p else "no open PR"))
        print("  Its routine wakes it; `lane.sh resume` refuses these by name "
              "(two agents, one branch, no lock). fold.sh never prunes their "
              "branches.")

    print("\n=== READY, NOT FOLDED (%d)%s"
          % (len(unfolded), "  -- NOT COMPUTED, see PR-BLIND above" if pr_blind else ""))
    for p in unfolded:
        # `finished` MEANS "the local unit is gone", and a remote lane never
        # had one -- so the unit test answers a question that was never asked
        # about it, and always with the one word that reads as "nobody is
        # working on this". That is what `remote` is for: the row above is the
        # only other place the distinction is visible, and a reader who stops
        # at this section would not have got there.
        if p.get("remote"):
            where = "elsewhere"
        else:
            where = "unit up" if p["lane"] in units else "finished"
        print("  %-12s #%-5d %-9s %s"
              % (p["lane"], p["number"], where, (p.get("title") or "")[:60]))
    # RELEASED AT READY. Available files: the board may start the next lane
    # on one (roles/board.md), with a brief naming the ready PR it overlaps.
    if pr_blind:
        release, stuck, unread = [], [], 0
    else:
        release, stuck, unread = fold_watch(prs, terr,
                                            None if fleet_blind else units)
    freed = released_files(terr)
    print("\n=== RELEASED AT READY -- available to the next lane (%d)"
          % sum(1 for _, _, t in freed if not t))
    for f, by, taken in freed:
        print("  %-44s released by %-12s %s"
              % (f, by, ("taken by " + taken) if taken else "AVAILABLE"))
    if release:
        print("  Ready PRs whose files are not released yet:")
        for lane, n, files in release:
            print("    %-12s #%-5d %s" % (lane, n, ", ".join(files)))
    print("\n=== FOLD-READY, NOT FOLDING (%d)%s"
          % (len(stuck), "  -- NOT COMPUTED, see PR-BLIND above" if pr_blind else ""))
    for n, lane, age, why, fix in stuck:
        print("  #%-5d %-12s %-7s %s" % (n, lane, age_s(age) if age else "?", why))
    if unread:
        print("  (%d PR(s) whose head, CI or label history gh would not give; "
              "not judged)" % unread)
    print("\n=== BLOCKED (labelled `blocked`) (%d)" % len(waiting))
    for p in waiting:
        print("  %-12s #%-5d %s" % (p["lane"], p["number"], (p.get("title") or "")[:70]))
    print("\n=== LANE CLAIMED WITH NO RUNNING AGENT (%d)%s"
          % (len(ghost),
             "  -- NOT COMPUTED, see FLEET-BLIND above" if fleet_blind else ""))
    for lane in ghost:
        print("  %-12s holds %d file(s), issues %s"
              % (lane, len((terr["lane"][lane].get("files") or [])),
                 ",".join(str(i) for i in (terr["lane"][lane].get("issues") or []))))
    print("\n=== RUNNING WITH NO TERRITORY ROW (%d)" % len(unclaimed))
    if unclaimed:
        print("  Invisible to every guard: check_territory.py cannot see a "
              "lane that is not in the file. A row with files = [] still "
              "counts as claimed.")
    for lane in unclaimed:
        f = fleet.get(lane, {})
        print("  %-12s %-7s %s" % (lane, age_s(units.get(lane)),
                                   (f.get("asked") or "(no registry entry)")[:70]))
    print("\n=== DISPATCHABLE NOW, NOT DISPATCHED (%d)%s"
          % (len(dispatchable),
             "  -- NOT COMPUTED, see FLEET-BLIND above" if fleet_blind else ""))
    for n, lane, why, title in dispatchable:
        print("  #%-4s %-12s %-26s %s" % (n, lane or "-", why, title))

    # SEPARATE SECTION, AND DELIBERATELY NOT PART OF THE EXIT CODE. These are
    # not known-dispatchable; they are blockers nobody has recorded testing.
    # Folding them into the FAIL above would say the board is holding work it
    # can start, which is a stronger claim than the evidence supports.
    print("\n=== BLOCKER NEVER RECORDED AS TESTED (%d)%s"
          % (len(untested),
             "  -- NOT COMPUTED, see FLEET-BLIND above" if fleet_blind else ""))
    if untested:
        print("  A blocker is a claim. Five were refuted in two days, two of"
              " them the orchestrator's own.")
    for n, lane, fals, title in untested:
        print("  #%-4s %-12s %-30s %s"
              % (n, lane or "-",
                 ("falsifier: " + fals[:24]) if fals else "NO FALSIFIER WRITTEN",
                 title))

    # NOT A DISPATCH QUEUE, BUT STILL PART OF THE EXIT CODE (see above). These
    # rows say nothing at all: no blocker, no `dispatch_state`, no running
    # lane.
    # The qualifier is master's (ae3712aae1) and applies here for its reason:
    # this list is built by the same running-lane-skipped loop, so under
    # FLEET-BLIND a bare (0) would read as "nothing is unclassified" when what
    # happened is that nothing was looked at.
    print("\n=== NEITHER BLOCKED NOR MARKED AVAILABLE (%d)%s"
          % (len(unclassified),
             "  -- NOT COMPUTED, see FLEET-BLIND above" if fleet_blind else ""))
    if unclassified:
        print("  An empty row is not a dispatch queue -- write "
              "`dispatch_state = \"available\"` if nothing blocks it, or the "
              "blocker if something does. check_coverage.py fails on these.")
    for n, lane, title in unclassified:
        print("  #%-4s %-12s %s" % (n, lane or "-", title))

    # SAME LIVE-PLUS-DISK MIX AS check_coverage.py, SO THE SAME QUALIFIER.
    # This reads open issues live from GitHub and territory.toml/
    # nv2a_issues.toml from whatever checkout it is standing in. Run from a
    # stale worktree, every section above is a statement about that checkout,
    # and "DISPATCHABLE NOW" is the one most likely to be acted on.
    try:
        out = subprocess.run(
            ["git", "-C", HERE, "rev-list", "--count", "HEAD..%s"
             % os.environ.get("HAKUX_TIP",
                              "master")],
            capture_output=True, text=True, timeout=15)
        behind = int(out.stdout.strip()) if out.returncode == 0 else None
    except Exception:
        behind = None
    if behind:
        print("\nSTALE CHECKOUT: %d commit(s) behind the campaign tip. The "
              "issue list above is live and the two toml files are from this "
              "tree, so rebase before acting on any of it." % behind)

    # EVERY LINE BELOW IS A BOARD WAKE-UP. board.sh greps stdout+stderr for
    # '^FAIL' and starts a model session on any hit, so a FAIL that cannot be
    # cleared by the board spends a window every twenty minutes for nothing.
    # Each one names the actor and the action that clears it.
    rc = 1 if fleet_blind else 0   # the FLEET-BLIND FAIL was printed above
    if waiting:
        print("\nFAIL: %d lane PR(s) labelled `blocked`: %s. Grant the file or "
              "answer the question and remove the label -- 'ask and I will "
              "grant it' is a deadlock (roles/board.md)."
              % (len(waiting), ", ".join("#%d" % p["number"] for p in waiting)),
              file=sys.stderr)
        rc = 1
    if dispatchable:
        print("FAIL: %d issue(s) could be dispatched and are not." % len(dispatchable),
              file=sys.stderr)
        rc = 1
    if unclassified:
        print("FAIL: %d open issue(s) are NEITHER BLOCKED NOR MARKED "
              "AVAILABLE and no lane is running on them -- %s. An empty row "
              "is not a dispatch queue and it is not coverage either: write "
              "the blocker, or `dispatch_state = \"available\"`."
              % (len(unclassified),
                 ", ".join("#" + n for n, _, _ in unclassified)),
              file=sys.stderr)
        rc = 1
    if unfolded:
        print("FAIL: %d lane PR(s) are READY and carry no pipeline label: %s. "
              "A ready PR with no needs-audit-*/needs-remediation/fold-ready/"
              "folded label is stalled -- nothing else will pick it up."
              % (len(unfolded), ", ".join("#%d" % p["number"] for p in unfolded)),
              file=sys.stderr)
        rc = 1
    # THE BOARD RELEASES, AND ONLY THE BOARD: territory.toml has one writer.
    # Each line names the row and the files, so the edit is mechanical.
    for lane, n, files in release:
        print("FAIL: lane.%s's PR #%d is ready (out of draft, CI green, unit "
              "gone) and its row still holds %d file(s) it has not released. "
              "Add them to `released` on [lane.%s] (roles/board.md: release at "
              "ready) so the next lane can start: %s"
              % (lane, n, len(files), lane, ", ".join(files)), file=sys.stderr)
        rc = 1
    # A fold-ready PR that cannot fold is never a reason to wait silently.
    for n, lane, age, why, fix in stuck:
        print("FAIL: fold-ready PR #%d (lane.%s) is not folding%s: %s. Fix: %s."
              % (n, lane, (" after " + age_s(age)) if age else "", why, fix),
              file=sys.stderr)
        rc = 1
    # NON-ZERO, LIKE THE OTHERS. `ghost` is printed and deliberately does not
    # set rc, because a stale claim OVER-reports coverage and that errs safe.
    # This one UNDER-reports it: the lane is editing files nothing knows it
    # holds, so a second lane can be handed the same file and both preflights
    # will pass.
    if unclaimed:
        print("FAIL: %d lane(s) are RUNNING with no territory row -- %s. "
              "Nothing can see them: check_territory.py cannot detect a "
              "collision with a lane that is not in the file. Write the row "
              "(files = [] is a valid claim), validate, commit, PUSH."
              % (len(unclaimed), ", ".join(unclaimed)), file=sys.stderr)
        rc = 1
    # A REQUEST EVERY LIVE CLAIMER HAS WALKED PAST (see queue_stall). The FAIL
    # carries each claimer's evidence, because "who skipped it, doing what" is
    # the first thing anyone clearing it needs; the next is the snapshot, since
    # a stale $DISPATCH_DIR/bin is how 2026-09-20 happened. A request waiting
    # on a hold is said on stdout and costs nothing: a hold is somebody's
    # decision, and waking the board for it every tick would be noise.
    stalled, on_hold, qblind = queue_stall()
    if qblind:
        print("FAIL: QUEUE-BLIND -- %s. The dispatch queue was not judged."
              % qblind, file=sys.stderr)
        rc = 1
    if stalled:
        rid, age_secs, why = stalled[0]
        print("FAIL: %d dispatch request(s) passed over by every live claimer "
              "-- oldest %s, queued %s ago: %s. Nothing will claim it. Check "
              "whether the workers run a stale snapshot (`diff -q "
              "docs/testing/affinity.py $DISPATCH_DIR/bin/affinity.py`; that "
              "is how four arms sat unclaimed for eighteen hours on "
              "2026-09-20), then the request's `device` field against "
              "$DISPATCH_DIR/lanes/."
              % (len(stalled), rid, age_s(age_secs), why), file=sys.stderr)
        rc = 1
    if on_hold:
        rid, age_secs, labels = on_hold[0]
        print("\nqueue: %d request(s) can only run on a held device -- oldest "
              "%s, queued %s ago, held: %s. Deliberate, not a stall; `rm "
              "$DISPATCH_DIR/hold/<label>` returns a device to service."
              % (len(on_hold), rid, age_s(age_secs), labels))
    return rc


if __name__ == "__main__":
    sys.exit(main())
