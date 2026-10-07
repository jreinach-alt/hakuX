#!/usr/bin/env python3
"""Dispatch admission control: one admit() between "someone decides to run it"
and a device. Every path that puts a title on a handheld calls it.

    dispatch_gate.py admit  --title T --class C --device D --build REF --because ID [--because ID ...]
                            --input-seq S --valid-end E [--order ID] [--seconds N]
                            [--env K=V ...] [--declare K ...] [--caller WHO] [--via request|hold]
                            [--installed-apk SHA12 | --readback] [--plan FILE] [--json REQ.json]
                            [--root W] [--no-refresh]
        exit 0 allow (prints the token), 2 deny. In SHADOW mode it always exits 0
        and prints SHADOW-DENY with the reasons; the log row records what it would
        have refused.
    dispatch_gate.py verify TOKEN --title T --device D [--root W]     exit 0 valid, 2 not
    dispatch_gate.py plan-check PLAN.md [--root W]                    exit 0 clean, 2 rows rejected
    dispatch_gate.py skip --plan PLAN.md --row N --why TEXT --caller WHO    record a skipped plan row
    dispatch_gate.py mode                                             print shadow|enforce

THE CLASSES (exactly one per dispatch, with evidence ids in --because):
  PLAYABLE_ATTEMPT  a title not in the ledger whose latest scored verdict clears the perf gates,
                    with no open hold, whose every failed gate is ANSWERED by a commit newer
                    than that verdict and in the build: a pm/title-fixes.tsv row (lane.local's)
                    or a change to the title's own files (GATE_PATHS). A newer commit is not
                    a fix. A BELOW_BAR title never: its fix buys TELEMETRY/VALIDATION, and a
                    verdict after it that clears the bar. No blind re-run.
  SCREEN            the first run of a title with no run on record (`--input-seq discovery` allowed).
  TELEMETRY         a BELOW_BAR or CRASH_OR_HANG title, to name the cost; never a confirmation
                    (its valid end is `capture:<N>s` or `condition:<text>`, not `valid-verdict`).
  VALIDATION        a harness fix or A/B; must name the condition it exercises (`condition:<text>`).
  OWNER_DIAGNOSTIC  an owner order recorded in pm/owner-holds.tsv (`--order <id>`): the ONLY override.

EVIDENCE IDS: verdict:<path under W>  fix:<commit>  issue:#N  order:<id>  plan:<file>#<row>
              condition:<text>  run:<run dir under W>

DEFAULT IS DENY. Each rule appends a reason that names the registry row (status, rule)
and the rule; any reason denies. There is no override flag and no override
environment variable: the process environment is never read for a decision
(PATHFIND_FOOTBALL, DISPATCH_GATE_OVERRIDE and the like change nothing).

MODE: W/pm/dispatch-gate.mode holds `enforce` (lane.local writes it) or anything
else / absent = shadow. --shadow forces shadow; nothing forces enforce.

THE TOKEN: `DG1 <tid> <class> <build> <device> <expiry> <decision_id> <mac>`, an
HMAC-SHA256 over the fields with the host key W/pm/.dispatch-gate.key. Every
decision (allow and deny, shadow or not) is a row in W/pm/dispatch-log.tsv, so a
dispatch with no row is detectable (dispatch_audit.py).
"""
import argparse
import datetime as dt
import glob
import hashlib
import hmac
import json
import os
import re
import secrets
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import title_registry as TR  # noqa: E402

CLASSES = ("PLAYABLE_ATTEMPT", "SCREEN", "TELEMETRY", "VALIDATION", "OWNER_DIAGNOSTIC")
DEVICES = {"nova": "ee317437", "thor": "bdc158a5"}
PKG = "com.jreinach.hakux.debug"
TOKEN_TTL_S = 3 * 3600
LOG_COLS = ["utc", "decision", "mode", "caller", "via", "title_id", "name", "class", "device", "build",
            "seconds", "because", "input_seq", "valid_end", "order", "status", "status_rule",
            "registry", "reasons", "token"]
VALID_END = re.compile(r"^(valid-verdict|capture:\d+s|condition:.+)$")
EVIDENCE = re.compile(r"^(verdict|fix|issue|order|plan|condition|run):(.+)$")


# ---------------------------------------------------------------- environment of a decision

class Ctx:
    """Everything admit() reads besides the request. The selftest builds one
    over a fixture tree; the CLI builds one over the host."""

    def __init__(self, root=TR.DEFAULT_ROOT, now=None, git_dir=None, readback=None, registry=None):
        self.p = TR.Paths(root)
        self.now = now or dt.datetime.now(dt.timezone.utc)
        self.git_dir = git_dir or os.path.join(root, "offline-git", "hakuX.git")
        self.readback = readback            # callable(device) -> sha12 | None
        self.registry_path = registry or self.p.registry
        self.log = os.path.join(self.p.pm, "dispatch-log.tsv")
        self.keyfile = os.path.join(self.p.pm, ".dispatch-gate.key")
        self.modefile = os.path.join(self.p.pm, "dispatch-gate.mode")
        self.hold_dir = os.path.join(self.p.dispatch, "hold")
        self.builds = os.path.join(self.p.dispatch, "builds")
        self._hdr, self._rows = None, None

    def registry(self):
        if self._rows is None:
            self._hdr, self._rows = TR.read_registry(self.registry_path)
        return self._hdr, self._rows

    def holds(self):
        return TR.load_holds(self.p)

    def mode(self):
        try:
            return "enforce" if open(self.modefile).read().strip() == "enforce" else "shadow"
        except OSError:
            return "shadow"

    # git, against the host's bare repo (every pushed branch, so a lane's fix is found
    # before it folds)
    def commit_time(self, sha):
        """aware datetime of the commit, or None if it does not exist."""
        if not re.match(r"^[0-9a-f]{7,40}$", sha or ""):
            return None
        try:
            out = subprocess.run(["git", "--git-dir", self.git_dir, "log", "-1", "--format=%ct", sha + "^{commit}"],
                                 capture_output=True, text=True, timeout=30)
        except (OSError, subprocess.SubprocessError):
            return None
        if out.returncode != 0 or not out.stdout.strip():
            return None
        return dt.datetime.fromtimestamp(int(out.stdout.strip()), dt.timezone.utc)

    def commit_paths(self, sha):
        """Paths the commit changed against its first parent (a fold's whole lane), or
        None if it cannot be read."""
        if not re.match(r"^[0-9a-f]{7,40}$", sha or ""):
            return None
        try:
            out = subprocess.run(["git", "--git-dir", self.git_dir, "diff-tree", "-r", "--root", "--no-commit-id",
                                  "--name-only", "-m", "--first-parent", sha + "^{commit}"],
                                 capture_output=True, text=True, timeout=60)
        except (OSError, subprocess.SubprocessError):
            return None
        if out.returncode != 0:
            return None
        return [x for x in out.stdout.splitlines() if x.strip()]

    def is_ancestor(self, older, newer):
        try:
            return subprocess.run(["git", "--git-dir", self.git_dir, "merge-base", "--is-ancestor", older, newer],
                                  capture_output=True, timeout=30).returncode == 0
        except (OSError, subprocess.SubprocessError):
            return False

    def build_apk_sha(self, build):
        """sha256[:12] of dispatch/builds/<build>.apk, the dispatcher's apk_sha convention."""
        f = os.path.join(self.builds, "%s.apk" % build)
        if not re.match(r"^[0-9a-f]{7,40}(-[a-z0-9]+)?$", build or "") or not os.path.isfile(f):
            return None
        h = hashlib.sha256()
        with open(f, "rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                h.update(chunk)
        return h.hexdigest()[:12]

    def key(self):
        if not os.path.isfile(self.keyfile):
            fd = os.open(self.keyfile, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "w") as f:
                f.write(secrets.token_hex(32) + "\n")
        return open(self.keyfile).read().strip().encode()


def readback_installed_apk(device):
    """Read back the APK installed on the handheld: `pm path` then sha256sum of it,
    first 12 hex (the dispatcher's apk_sha). For the CALL SITE to run (hold.sh
    take / a lane script, which own the device at that point); this lane never
    runs it. None on any failure, which denies."""
    serial = DEVICES.get(device)
    if not serial:
        return None
    try:
        out = subprocess.run(["adb", "-s", serial, "shell", "pm", "path", PKG],
                             capture_output=True, text=True, timeout=20).stdout
        m = re.search(r"package:(\S+base\.apk)", out)
        if not m:
            return None
        out = subprocess.run(["adb", "-s", serial, "shell", "sha256sum", m.group(1)],
                             capture_output=True, text=True, timeout=60).stdout
        m2 = re.match(r"([0-9a-f]{64})", out.strip())
        return m2.group(1)[:12] if m2 else None
    except (OSError, subprocess.SubprocessError):
        return None


# ---------------------------------------------------------------- the decision

class Decision:
    def __init__(self, req, row):
        self.req = req
        self.row = row
        self.reasons = []
        self.notes = []
        self.allow = False
        self.token = ""
        self.mode = "shadow"

    def deny(self, rule, text):
        self.reasons.append("%s: %s" % (rule, text))


def _row_ref(row):
    if not row:
        return "no registry row"
    return "registry %s %s [%s: %s]" % (row["title_id"], row["name"], row["status"], row["status_rule"])


def _because(req, kind):
    return [EVIDENCE.match(b).group(2) for b in req.get("because") or [] if EVIDENCE.match(b)
            and EVIDENCE.match(b).group(1) == kind]


def _holds_for(ctx, tid, name, kinds):
    cat = None
    out = []
    for h in ctx.holds():
        if h.get("kind") not in kinds:
            continue
        if not TR.hold_matches(h, tid, name, cat) and not _alias_match(ctx, h, tid):
            continue
        out.append(h)
    return out


def _alias_match(ctx, h, tid):
    """A hold names a regional id; the registry row is keyed by the canonical one."""
    _, rows = ctx.registry()
    row = rows.get(tid) or {}
    al = set(filter(None, (row.get("aliases") or "").split(",")))
    return any(x.strip().upper() in al for x in (h.get("match") or "").split(","))


def _classes(h):
    c = (h.get("classes") or "").replace(" ", "")
    if c == "ALL":
        return set(CLASSES) - {"OWNER_DIAGNOSTIC"}
    return set(filter(None, c.split(",")))


# Each rule: (ctx, req, row, d) -> appends reasons. Named so a selftest mutant can
# disable exactly one and show its fixture leg turn red.

def rule_registry_fresh(ctx, req, row, d):
    hdr, _ = ctx.registry()
    if hdr is None:
        return d.deny("registry", "no registry at %s" % ctx.registry_path)
    ok, why = TR.freshness(ctx.p, ctx.registry_path, ctx.now)
    if not ok:
        d.deny("registry", "stale: " + why)


def rule_request_shape(ctx, req, row, d):
    if req.get("class") not in CLASSES:
        d.deny("class", "class %r is not one of %s" % (req.get("class"), ", ".join(CLASSES)))
    if not row:
        d.deny("title", "title %r is not a registry row (resolve: %s)" % (req.get("title"), req.get("_resolve")))
    if req.get("_id_conflict"):
        d.deny("title", req["_id_conflict"])
    if req.get("device") not in DEVICES:
        d.deny("device", "device %r is not one of %s" % (req.get("device"), ", ".join(DEVICES)))
    if not req.get("because"):
        d.deny("evidence", "no --because evidence id: every dispatch cites its evidence")
    for b in req.get("because") or []:
        m = EVIDENCE.match(b)
        if not m:
            d.deny("evidence", "evidence id %r is not one of verdict:|fix:|issue:|order:|plan:|condition:|run:" % b)
            continue
        kind, val = m.groups()
        if kind in ("verdict", "run") and not os.path.exists(os.path.join(ctx.p.root, val)):
            d.deny("evidence", "%s %s does not exist under %s" % (kind, val, ctx.p.root))
        if kind == "fix" and ctx.commit_time(val) is None:
            d.deny("evidence", "fix:%s is not a commit in %s" % (val, ctx.git_dir))


def _latest_verdict_time(row):
    return TR.parse_utc(row.get("verdict_utc")) if row else None


# A commit ANSWERS a failed gate of a title by one of two records, never by being newer
# than the verdict (lane.local's review 10-06 18:10: fix:6cef37f426, an unrelated fold,
# admitted DOA3, Hulk Ultimate Destruction and LOTR ROTK):
#  (a) a row of pm/title-fixes.tsv (lane.local's; title_id, gate, fix_commit, set_by,
#      date, why) set by one of FIX_SETTERS, naming the gate, with a why;
#  (b) the commit's changed paths (first parent: a fold counts its whole lane) match a
#      GATE_PATHS pattern for that gate, {TID} being the title's id or an alias.
# The map is deliberately narrow: only files that belong to one title answer a
# route gate; a harness-wide or emulator-wide change answers nothing by its paths
# (it may answer every title or none) and needs a title-fixes row.
FIX_SETTERS = ("lane.local", "owner")
ROUTE_GATES = ("menu_time", "reached_gameplay", "duration", "static", "position")
GATE_ALIASES = {"route": ROUTE_GATES}
GATE_PATHS = {g: (r"^docs/testing/titles/pathknow/paths/{TID}\.json$",) for g in ROUTE_GATES}
# A fix that changes only these is harness input (routes, paths, pathfind): it acts from the tool
# tree that runs the title, not from the APK, so it is not required to be in the requested build.
# Whether that tree has it is not checked (NOTES section 3).
TOOLING_PREFIXES = ("docs/",)


def _gate_set(cell):
    out = set()
    for g in re.split(r"[+,\s]+", (cell or "").strip()):
        out.update(GATE_ALIASES.get(g, (g,)) if g else ())
    return out


def _sha_eq(a, b):
    a, b = (a or "").strip().lower(), (b or "").strip().lower()
    return len(min(a, b, key=len)) >= 7 and (a.startswith(b) or b.startswith(a))


def _fix_answers(ctx, sha, row):
    """{gate: how} this commit answers for this title, by (a) or (b)."""
    ids = {row["title_id"]} | set(filter(None, (row.get("aliases") or "").split(",")))
    out = {}
    for f in TR.load_title_fixes(ctx.p):
        if f["title_id"].strip().upper() not in ids or not _sha_eq(f.get("fix_commit"), sha):
            continue
        if (f.get("set_by") or "").strip() not in FIX_SETTERS or not (f.get("why") or "").strip():
            continue
        for g in _gate_set(f.get("gate")):
            out[g] = "pm/title-fixes.tsv row (%s %s: %s)" % (f.get("set_by"), f.get("date"), f["why"][:80])
    paths = ctx.commit_paths(sha) or []
    for g, pats in GATE_PATHS.items():
        if g in out:
            continue
        for pat in pats:
            rx = [re.compile(pat.replace("{TID}", re.escape(t)), re.I) for t in ids]
            hit = next((p for p in paths if any(r.search(p) for r in rx)), None)
            if hit:
                out[g] = "touches %s" % hit
                break
    return out


def _answering_fix(ctx, req, row):
    """(sha, why) when committed fixes newer than the latest verdict, and in the requested
    build, answer EVERY failed gate of it (by pm/title-fixes.tsv or GATE_PATHS); (None,
    why) otherwise. A perf gate (fps/hitch/audio) is never answered here: a fix for it
    admits a Playable attempt only once a verdict AFTER it clears the bar, so the fix
    alone buys a TELEMETRY or VALIDATION run."""
    failing = _gate_set((row.get("failing_all") or "").replace("+", " "))
    perf = sorted(failing & set(TR.PERF_GATES))
    if perf:
        return None, ("the latest verdict fails %s: a fix for a perf gate needs a verdict after it that clears the bar "
                      "before a Playable attempt (run TELEMETRY or VALIDATION on the fix build)" % "+".join(perf))
    vt = _latest_verdict_time(row) or TR.parse_utc(row.get("last_run_utc"))
    ids = {row["title_id"]} | set(filter(None, (row.get("aliases") or "").split(",")))
    recorded = [f["fix_commit"].strip() for f in TR.load_title_fixes(ctx.p)
                if f["title_id"].strip().upper() in ids and (f.get("fix_commit") or "").strip()]
    cands = list(dict.fromkeys(_because(req, "fix") + recorded))
    if not cands:
        return None, "no committed fix is cited (fix:<sha>) or recorded in pm/title-fixes.tsv"
    build = re.sub(r"-[a-z0-9]+$", "", req.get("build") or "")
    answered, used, why = {}, [], []
    for sha in cands:
        ct = ctx.commit_time(sha)
        if ct is None:
            why.append("%s is not a commit" % sha)
            continue
        if vt is not None and ct <= vt:
            why.append("%s (%s) is not newer than the latest verdict/run (%s): the same inputs again"
                       % (sha, TR.iso_z(ct), TR.iso_z(vt)))
            continue
        paths = ctx.commit_paths(sha) or []
        tooling = bool(paths) and all(p.startswith(TOOLING_PREFIXES) for p in paths)
        if build and not tooling and not ctx.is_ancestor(sha, build):
            why.append("%s changes code outside %s and is not in build %s" % (sha, "/".join(TOOLING_PREFIXES), build))
            continue
        got = _fix_answers(ctx, sha, row)
        if not got:
            why.append("%s answers no gate of %s: no pm/title-fixes.tsv row (set_by lane.local/owner) names it and it "
                       "touches none of the title's paths; a newer commit is not a fix" % (sha, row["title_id"]))
            continue
        used.append(sha)
        for g, how in got.items():
            answered.setdefault(g, "%s %s" % (sha, how))
    need = failing or {"*"}
    missing = sorted(g for g in need if g not in answered and not (g == "*" and answered))
    if missing or not used:
        return None, "failed gate(s) %s not answered by a recorded fix (%s)" % (
            "+".join(missing) or "?", "; ".join(why) or "answered: " + ", ".join(sorted(answered)))
    return "+".join(used), "fix %s answers %s" % ("+".join(used), "; ".join(
        "%s by %s" % (g, answered[g]) for g in sorted(answered) if g in need or need == {"*"}))


def rule_class_status(ctx, req, row, d):
    """The class x status matrix. Default deny: a pair not allowed here is refused."""
    if not row or req.get("class") not in CLASSES:
        return
    c, st = req["class"], row["status"]
    ref = _row_ref(row)
    if c == "OWNER_DIAGNOSTIC":
        return                      # the order rule decides
    if c == "PLAYABLE_ATTEMPT":
        if st == "PLAYABLE":
            return d.deny("matrix", "already in the Playable ledger (%s): %s" % (row["ledger"], ref))
        if st in ("EXCLUDED", "PENDING_OWNER", "CRASH_OR_HANG"):
            return d.deny("matrix", "%s titles get no Playable attempt: %s" % (st, ref))
        if st == "UNSCREENED":
            return d.deny("matrix", "never screened: the first run is a SCREEN, not a Playable attempt: %s" % ref)
        if st == "BELOW_BAR":
            # Never, fix or no fix: a fix lets TELEMETRY/VALIDATION produce a verdict after it,
            # and a verdict that clears the bar moves the title out of BELOW_BAR.
            _, why = _answering_fix(ctx, req, row)
            return d.deny("matrix", "below the bar (fps_ok_share %s, failing %s): no Playable attempt until a verdict "
                          "after a fix clears it; TELEMETRY or VALIDATION only; %s; %s"
                          % (row["fps_ok_share"], row["failing_all"] or "-", why, ref))
        if st == "FAILED_HARNESS":
            if not row.get("failing_all") and row.get("latest_verdict"):
                return d.deny("matrix", "the latest verdict is a harness PASS not in the ledger: it needs a frame "
                              "review, not a run: %s" % ref)
            sha, why = _answering_fix(ctx, req, row)
            if not sha:
                return d.deny("matrix", "last failure (%s) has no committed fix since it: %s; %s"
                              % (row["failing_all"] or row["status_rule"], why, ref))
            return
        if st == "VOID":
            sha, why = _answering_fix(ctx, req, row)
            if not sha:
                return d.deny("matrix", "the last runs voided and no fix for the void cause is cited: %s; %s" % (why, ref))
            return
        return d.deny("matrix", "status %s is not eligible for a Playable attempt: %s" % (st, ref))
    if c == "SCREEN":
        if st != "UNSCREENED" or (row.get("runs_total") or "0") != "0":
            return d.deny("matrix", "SCREEN is a first-ever run of an UNSCREENED title; this one is %s with %s run(s) "
                          "on record: %s" % (st, row.get("runs_total"), ref))
        return
    if c == "TELEMETRY":
        if st not in ("BELOW_BAR", "CRASH_OR_HANG"):
            return d.deny("matrix", "TELEMETRY is for a below-bar or crash/hang title (to name the cost); "
                          "this one is %s: %s" % (st, ref))
        if req.get("valid_end") == "valid-verdict":
            d.deny("matrix", "TELEMETRY is never a confirmation run (owner 10-03): its valid end is "
                   "capture:<N>s or condition:<text>, not valid-verdict")
        return
    if c == "VALIDATION":
        conds = _because(req, "condition") + ([req["valid_end"][len("condition:"):]]
                                               if (req.get("valid_end") or "").startswith("condition:") else [])
        if not any(x.strip() for x in conds):
            d.deny("matrix", "VALIDATION must name the stall/condition it exercises (condition:<text>); a run that "
                   "cannot show the defect proves nothing")
        return


def rule_holds(ctx, req, row, d):
    """Title-level owner holds: an active hold blocking this class denies, whatever
    the status; only an owner order (OWNER_DIAGNOSTIC) passes one."""
    if not row:
        return
    # The row's `holds` column is the active set, computed at build time with the
    # forge's issue states; a hold edited since then moved the sources digest, so
    # rule_registry_fresh has already refused.
    active = set(filter(None, (row.get("holds") or "").split(",")))
    for h in ctx.holds():
        if h.get("id") not in active or h.get("kind") not in TR.TITLE_HOLD_KINDS:
            continue
        if req.get("class") in _classes(h):
            d.deny("hold", "owner hold %s (%s, since %s by %s: %r) blocks %s; release: %s; %s"
                   % (h["id"], h["kind"], h.get("since"), h.get("by"), (h.get("quote") or "")[:120],
                      req.get("class"), h.get("release"), _row_ref(row)))


def rule_owner_order(ctx, req, row, d):
    if req.get("class") != "OWNER_DIAGNOSTIC":
        return
    oid = req.get("order") or ""
    if not oid:
        return d.deny("order", "OWNER_DIAGNOSTIC needs --order <id> recorded in pm/owner-holds.tsv")
    orders = [h for h in ctx.holds() if h.get("kind") == "order" and h.get("id") == oid]
    if not orders:
        return d.deny("order", "order %r is not a row of pm/owner-holds.tsv (an env var or a brief line is not an order)"
                      % oid)
    h = orders[0]
    if (h.get("released") or "").strip():
        return d.deny("order", "order %s is spent/released: %s" % (oid, h["released"]))
    if row and not (TR.hold_matches(h, row["title_id"], row["name"]) or _alias_match(ctx, h, row["title_id"])):
        return d.deny("order", "order %s is for %s, not %s" % (oid, h.get("match"), row["title_id"]))
    if "OWNER_DIAGNOSTIC" not in _classes(h) and (h.get("classes") or "") != "OWNER_DIAGNOSTIC":
        return d.deny("order", "order %s does not permit OWNER_DIAGNOSTIC" % oid)


def rule_input_and_end(ctx, req, row, d):
    seq = req.get("input_seq") or ""
    if not seq:
        d.deny("input", "no --input-seq: no device run without a recorded, verified input sequence (owner 10-06 07:50)")
    elif seq == "discovery":
        if req.get("class") != "SCREEN":
            d.deny("input", "input sequence `discovery` is allowed only for a SCREEN (first run)")
    elif seq.startswith("path:"):
        if not row or seq != row.get("input_seq"):
            d.deny("input", "%s is not the title's recorded complete path (registry has %r)" % (
                seq, (row or {}).get("input_seq")))
    elif seq.startswith("route:"):
        if not os.path.isfile(os.path.join(ctx.p.routes, seq[len("route:"):] + ".route")):
            d.deny("input", "%s: no docs/testing/titles/routes/%s.route" % (seq, seq[len("route:"):]))
    else:
        d.deny("input", "input sequence %r is not path:<TID>@<sha12>, route:<name> or discovery" % seq)
    ve = req.get("valid_end") or ""
    if not VALID_END.match(ve):
        d.deny("valid_end", "valid end %r is not valid-verdict | capture:<N>s | condition:<text>: a run ends only on a "
               "valid result (owner 10-06)" % ve)
    elif req.get("class") == "PLAYABLE_ATTEMPT" and ve != "valid-verdict":
        d.deny("valid_end", "a Playable attempt ends only on a valid verdict (valid-verdict), not %r" % ve)


def rule_build(ctx, req, row, d):
    b = req.get("build") or ""
    base = re.sub(r"-[a-z0-9]+$", "", b)
    if ctx.commit_time(base) is None:
        return d.deny("build", "build %r is not a commit in %s" % (b, ctx.git_dir))
    for h in ctx.holds():
        if h.get("kind") != "build_floor" or (h.get("released") or "").strip():
            continue
        if row and not (TR.hold_matches(h, row["title_id"], row["name"]) or _alias_match(ctx, h, row["title_id"])):
            continue
        floor = (h.get("value") or "").strip()
        if floor and not ctx.is_ancestor(floor, base):
            d.deny("build", "build %s does not contain %s (%s: %s)" % (base, floor, h["id"], (h.get("quote") or "")[:100]))
    if req.get("via") == "hold":
        want = ctx.build_apk_sha(b)
        got = req.get("installed_apk")
        if got is None and ctx.readback:
            got = ctx.readback(req.get("device"))
            req["installed_apk"] = got
        if want is None:
            d.deny("apk", "no dispatch/builds/%s.apk to compare the installed APK with" % b)
        elif not got:
            d.deny("apk", "the installed APK on %s was not read back (pm path + sha256sum); a run on an unknown "
                   "build proves nothing" % req.get("device"))
        elif got[:12] != want:
            d.deny("apk", "installed APK on %s is %s but dispatch/builds/%s.apk is %s" % (req.get("device"), got[:12], b, want))


def rule_device(ctx, req, row, d):
    dev = req.get("device")
    secs = int(req.get("seconds") or 0)
    for h in ctx.holds():
        if h.get("kind") != "device" or h.get("match") != "device:%s" % dev or (h.get("released") or "").strip():
            continue
        m = re.search(r"max_s=(\d+)", h.get("value") or "")
        if m:
            cap = int(m.group(1))
            if req.get("class") == "PLAYABLE_ATTEMPT":
                d.deny("device", "%s: a Playable attempt holds 600 s; %s is capped at %d s (%s)" % (h["id"], dev, cap, h.get("quote", "")[:80]))
            elif not secs or secs > cap:
                d.deny("device", "%s: %s takes only queued requests <= %d s; this one is %s s" % (h["id"], dev, cap, secs or "unstated"))
            if req.get("via") == "hold" and req.get("class") != "OWNER_DIAGNOSTIC":
                d.deny("device", "%s: %s runs only queued requests in a cold slot, not a direct hold" % (h["id"], dev))
    if req.get("via") == "hold":
        hf = os.path.join(ctx.hold_dir, dev or "")
        if os.path.isfile(hf):
            tag = open(hf).read().strip()
            if tag and tag != (req.get("caller") or ""):
                d.deny("device", "%s is held by %s, not %s" % (dev, tag, req.get("caller")))


def rule_window(ctx, req, row, d):
    now_pt = ctx.now.astimezone(TR.PT)
    for h in ctx.holds():
        if h.get("kind") != "window" or req.get("class") not in _classes(h) or (h.get("released") or "").strip():
            continue
        kv = dict(x.split("=", 1) for x in (h.get("value") or "").split() if "=" in x)
        if kv.get("date") and kv["date"] != now_pt.strftime("%Y-%m-%d"):
            continue
        if kv.get("last_start") and now_pt.strftime("%H:%M") > kv["last_start"]:
            d.deny("window", "%s: the last %s starts by %s PT (now %s): %s" % (
                h["id"], req.get("class"), kv["last_start"], now_pt.strftime("%H:%M"), (h.get("quote") or "")[:80]))


def rule_env(ctx, req, row, d):
    env = req.get("env") or {}
    declared = set(req.get("declared_env") or [])
    undeclared = sorted(k for k in env if k not in declared)
    if undeclared:
        d.deny("env", "request env %s is not declared (--declare K): an env that outlives a run changes the next one"
               % ",".join(undeclared))


def rule_staged(ctx, req, row, d):
    if not row or req.get("device") not in DEVICES:
        return
    st = row.get("staged") or ""
    if not any(s.split(":")[0] == req["device"] for s in st.split(",") if s):
        d.deny("staged", "%s is not staged on %s per its listing/push records/runs (staged: %s)" % (
            row["title_id"], req["device"], st or "nowhere"))


def rule_identical(ctx, req, row, d):
    """No run of identical inputs: an earlier ALLOW for the same title, class, build and
    input sequence whose run has since produced a verdict."""
    if not row or req.get("class") in ("OWNER_DIAGNOSTIC", "VALIDATION"):
        return
    vt = _latest_verdict_time(row)
    for r in TR.read_tsv(ctx.log):
        if r.get("decision") != "ALLOW" or r.get("title_id") != row["title_id"]:
            continue
        if (r.get("class"), r.get("build"), r.get("input_seq")) == (req.get("class"), req.get("build"), req.get("input_seq")):
            t = TR.parse_utc(r.get("utc"))
            if t and vt and vt > t:
                d.deny("identical", "the same class/build/input sequence was admitted %s and has a verdict since (%s): "
                       "the same inputs are not repeated" % (r.get("utc"), row.get("latest_verdict")))


def rule_plan(ctx, req, row, d):
    plan = req.get("plan")
    if not plan:
        return
    if not os.path.isfile(plan):
        return d.deny("plan", "plan %s does not exist" % plan)
    rows, rejects = plan_check(ctx, plan)
    mine = [r for r in rows if row and r["tid"] == row["title_id"]]
    if not mine:
        return d.deny("plan", "%s is not a row of %s" % ((row or {}).get("title_id"), os.path.basename(plan)))
    pr = mine[0]
    for rj in rejects:
        if rj["row"] == pr["row"]:
            d.deny("plan", "plan row %s is rejected by plan_check: %s" % (pr["row"], rj["why"]))
    done = _plan_done(ctx, plan)
    for r in rows:
        if r["order"] >= pr["order"]:
            break
        if any(rj["row"] == r["row"] for rj in rejects):
            continue                 # an ineligible earlier row is not owed a run
        if r["tid"] not in done:
            d.deny("plan", "plan order: row %s (%s) comes first and has neither run nor a recorded skip since the plan "
                   "was written (dispatch_gate.py skip)" % (r["row"], r["title"]))
            return


# ---------------------------------------------------------------- plans

PLAN_FIX_WORDS = re.compile(r"\b(fix(ed)? folded|folded|resolved|fixed)\b", re.I)
SHA = re.compile(r"\b[0-9a-f]{10,40}\b")


def parse_plan(path):
    """Rows of the first markdown table whose header has a Title column:
    [{row, order, title, cells{header: text}, raw}]."""
    out = []
    hdr = None
    for line in open(path, encoding="utf-8", errors="replace"):
        line = line.rstrip("\n")
        if not line.startswith("|"):
            if hdr and out:
                break
            hdr = None if not line.strip() else hdr
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if hdr is None:
            if any(re.match(r"(?i)title", c) for c in cells):
                hdr = cells
            continue
        if all(re.match(r"^:?-+:?$", c) for c in cells if c):
            continue
        rec = dict(zip(hdr, cells))
        tcol = next(h for h in hdr if re.match(r"(?i)title", h))
        num = rec.get("#") or str(len(out))
        out.append(dict(row=num, order=len(out), title=rec[tcol], cells=rec, raw=line))
    return out


def _plan_title(ctx, text, cat):
    """(tid, name, why) for a plan cell: an 8-hex title id in the cell wins; else the
    bolded name, exactly."""
    m = re.search(r"\b([0-9A-F]{8})\b", text)
    if m:
        return cat.canonical(m.group(1)), m.group(1), "title id in the row"
    name = re.sub(r"\*\*|\(#[^)]*\)|\([^)]*\)", "", text)
    name = re.split(r",| then ", name)[0].strip()
    tid, why = cat.resolve(name)
    return tid, name, why


def _plan_class(rec):
    for k, v in rec["cells"].items():
        if k.lower() == "class" and v.strip().upper() in CLASSES:
            return v.strip().upper()
    if re.search(r"(?i)first run|unscreened", rec["raw"]):
        return "SCREEN"
    return "PLAYABLE_ATTEMPT"


def plan_check(ctx, plan):
    """(rows, rejects). rows: [{row, order, title, tid, class, fixes}]. A rejected row
    names its reason. A row is rejected when its title does not resolve, when the
    gate's title-level rules refuse its class, or when it claims a fix ("folded",
    "resolved") that does not resolve to an existing commit with a verdict after it."""
    cat = TR.build_catalog(ctx.p)
    _, reg = ctx.registry()
    rows, rejects = [], []
    for rec in parse_plan(plan):
        tid, name, why = _plan_title(ctx, rec["title"], cat)
        cls = _plan_class(rec)
        fixcell = " ".join(v for k, v in rec["cells"].items() if re.search(r"(?i)fix|change|committed", k))
        fixes = SHA.findall(fixcell)
        r = dict(row=rec["row"], order=rec["order"], title=name, tid=tid, cls=cls, fixes=fixes)
        rows.append(r)
        if not tid:
            rejects.append(dict(row=rec["row"], title=name, why="title %r does not resolve to one title id (%s); put "
                                "the title id in the row" % (name, why)))
            continue
        row = reg.get(tid)
        fake = dict(title=tid, **{"class": cls}, because=["fix:%s" % s for s in fixes])
        d = Decision(fake, row)
        for fn in (rule_class_status, rule_holds):
            fn(ctx, fake, row, d)
        if PLAN_FIX_WORDS.search(fixcell):
            if not fixes:
                d.deny("plan-fix", "the row says %r but names no commit" % PLAN_FIX_WORDS.search(fixcell).group(0))
            for s in fixes:
                ct = ctx.commit_time(s)
                vt = _latest_verdict_time(row)
                if ct is None:
                    d.deny("plan-fix", "fix %s is not a commit" % s)
                elif not vt or vt < ct:
                    d.deny("plan-fix", "the row says %r but no verdict exists after fix %s (%s): folded is not resolved"
                           % (PLAN_FIX_WORDS.search(fixcell).group(0), s, TR.iso_z(ct)))
        for reason in d.reasons:
            rejects.append(dict(row=rec["row"], title=name, why=reason))
    return rows, rejects


def _plan_done(ctx, plan):
    """Title ids the plan's earlier rows count as done: an ALLOW logged after the plan
    file's mtime, a SKIP row naming this plan, or a run (registry last_run_utc) after it."""
    t0 = dt.datetime.fromtimestamp(os.path.getmtime(plan), dt.timezone.utc)
    done = set()
    for r in TR.read_tsv(ctx.log):
        t = TR.parse_utc(r.get("utc"))
        if not t or t < t0:
            continue
        if r.get("decision") == "ALLOW":
            done.add(r.get("title_id"))
        if r.get("decision") == "SKIP" and os.path.basename(plan) in (r.get("because") or ""):
            done.add(r.get("title_id"))
    _, reg = ctx.registry()
    for tid, row in reg.items():
        lt = TR.parse_utc(row.get("last_run_utc"))
        if lt and lt >= t0:
            done.add(tid)
    return done


# ---------------------------------------------------------------- admit

RULES = [rule_registry_fresh, rule_request_shape, rule_class_status, rule_holds, rule_owner_order,
         rule_input_and_end, rule_build, rule_device, rule_window, rule_env, rule_staged, rule_identical, rule_plan]


def admit(ctx, req, disabled=(), shadow=None, write_log=True):
    """-> Decision. `disabled` names rules to skip: the selftest's mutants only. The
    process environment is not read."""
    req = dict(req)
    _, rows = ctx.registry()
    cat = TR.build_catalog(ctx.p)
    tid, why = cat.resolve(req.get("title") or "")
    req["_resolve"] = why
    row = rows.get(tid) if tid else None
    d = Decision(req, row)
    for fn in RULES:
        if fn.__name__ in disabled:
            continue
        fn(ctx, req, row, d)
    d.allow = not d.reasons
    d.mode = "shadow" if shadow or (shadow is None and ctx.mode() != "enforce") else "enforce"
    did = hashlib.sha256(("%s|%s|%s" % (TR.iso_z(ctx.now), tid, secrets.token_hex(4))).encode()).hexdigest()[:10]
    if d.allow:
        d.token = make_token(ctx, row["title_id"], req["class"], req.get("build", ""), req["device"], did)
    if write_log:
        log_decision(ctx, d, did)
    return d


def make_token(ctx, tid, cls, build, device, did):
    exp = TR.iso_z(ctx.now + dt.timedelta(seconds=TOKEN_TTL_S))
    body = "DG1 %s %s %s %s %s %s" % (tid, cls, build or "-", device, exp, did)
    mac = hmac.new(ctx.key(), body.encode(), hashlib.sha256).hexdigest()[:24]
    return body + " " + mac


def verify_token(ctx, token, title, device):
    """(ok, why): the MAC checks, it is unexpired, it names this title and device,
    and pm/dispatch-log.tsv has the ALLOW row that issued it."""
    parts = (token or "").split()
    if len(parts) != 8 or parts[0] != "DG1":
        return False, "not a DG1 token"
    body, mac = " ".join(parts[:7]), parts[7]
    if not hmac.compare_digest(hmac.new(ctx.key(), body.encode(), hashlib.sha256).hexdigest()[:24], mac):
        return False, "MAC does not verify"
    _, tid, cls, build, dev, exp, did = parts[:7]
    cat = TR.build_catalog(ctx.p)
    want, _ = cat.resolve(title or "")
    if want != tid:
        return False, "token is for %s, not %s" % (tid, title)
    if dev != device:
        return False, "token is for %s, not %s" % (dev, device)
    e = TR.parse_utc(exp)
    if not e or e < ctx.now:
        return False, "token expired %s" % exp
    if not any(r.get("token") == token and r.get("decision") == "ALLOW" for r in TR.read_tsv(ctx.log)):
        return False, "no ALLOW row in dispatch-log.tsv carries this token"
    return True, "valid: %s %s on %s, build %s, until %s" % (tid, cls, dev, build, exp)


def log_decision(ctx, d, did):
    r = d.req
    row = d.row or {}
    dec = "ALLOW" if d.allow else ("SHADOW-DENY" if d.mode == "shadow" else "DENY")
    rec = dict(utc=TR.iso_z(ctx.now), decision=dec, mode=d.mode, caller=r.get("caller", ""), via=r.get("via", ""),
               title_id=row.get("title_id", r.get("title", "")), name=row.get("name", ""), **{"class": r.get("class", "")},
               device=r.get("device", ""), build=r.get("build", ""), seconds=str(r.get("seconds") or ""),
               because=" ".join(r.get("because") or []), input_seq=r.get("input_seq", ""),
               valid_end=r.get("valid_end", ""), order=r.get("order", ""), status=row.get("status", ""),
               status_rule=row.get("status_rule", ""), registry=(ctx._hdr or {}).get("generated_utc", ""),
               reasons=" || ".join(d.reasons), token=d.token or did)
    _append_log(ctx, rec)


def _append_log(ctx, rec):
    new = not os.path.isfile(ctx.log)
    with open(ctx.log, "a") as f:
        if new:
            f.write("\t".join(LOG_COLS) + "\n")
        f.write("\t".join(str(rec.get(c, "")).replace("\t", " ").replace("\n", " ") for c in LOG_COLS) + "\n")


# ---------------------------------------------------------------- CLI

def _req_from_args(a):
    req = {}
    if a.json:
        req.update(json.load(open(a.json)))
    for k in ("title", "device", "build", "input_seq", "valid_end", "order", "seconds", "caller", "via", "plan"):
        v = getattr(a, k)
        if v is not None:
            req[k] = v
    if a.cls:
        req["class"] = a.cls
    if a.because:
        req["because"] = a.because
    if a.env:
        req["env"] = dict(e.split("=", 1) for e in a.env)
    if a.declare:
        req["declared_env"] = a.declare
    if a.installed_apk:
        req["installed_apk"] = a.installed_apk
    req.setdefault("via", "request")
    return req


# Holds that are not dispatches: the host's update window, charging, the Thor's
# fan-wait park, the owner's playtest. Enforcement exempts them; lane.local
# confirms the list before writing `enforce` (NOTES, "hold.sh").
NON_DISPATCH_TAGS = re.compile(r"^(hostupd-|lanelocal-fanwait$|lanelocal-topup|charge-|playtest)")
TID_IN_TEXT = re.compile(r"\b([0-9A-F]{8})\b")


def hold_check(ctx, device, tag, why):
    """hold.sh take's call site. A direct hold on a handheld is a dispatch when it
    runs a title, so it must carry an unexpired ALLOW token for this device whose
    caller is the taker (or whose token text is in the why), and -- when the why
    names a title id -- for that title. Shadow: log what would be refused, exit 0.
    Enforce: exit 3 (hold.sh's "refused") unless the tag is a non-dispatch hold."""
    rows = TR.read_tsv(ctx.log)
    named = set(TID_IN_TEXT.findall(why or ""))
    cat = TR.build_catalog(ctx.p)
    named = {cat.canonical(t) for t in named}
    found = None
    for r in reversed(rows):
        if r.get("decision") != "ALLOW" or r.get("device") != device:
            continue
        tok = r.get("token") or ""
        if r.get("caller") != tag and tok not in (why or ""):
            continue
        parts = tok.split()
        exp = TR.parse_utc(parts[5]) if len(parts) == 8 else None
        if not exp or exp < ctx.now:
            continue
        if named and r.get("title_id") not in named:
            continue
        found = r
        break
    mode = ctx.mode()
    if found:
        _append_log(ctx, dict(utc=TR.iso_z(ctx.now), decision="HOLD-GATED", mode=mode, caller=tag, via="hold",
                              title_id=found.get("title_id"), device=device, reasons="token " + found.get("token", "")[:60]))
        return 0
    exempt = bool(NON_DISPATCH_TAGS.match(tag or ""))
    why_no = ("no unexpired ALLOW token in dispatch-log.tsv for device %s and caller %s%s"
              % (device, tag, (" naming " + ",".join(sorted(named))) if named else ""))
    dec = "HOLD-EXEMPT" if exempt else ("SHADOW-HOLD-UNGATED" if mode != "enforce" else "HOLD-DENY")
    _append_log(ctx, dict(utc=TR.iso_z(ctx.now), decision=dec, mode=mode, caller=tag, via="hold",
                          title_id=",".join(sorted(named)), device=device, reasons=why_no + "; why: " + (why or "")[:200]))
    if exempt or mode != "enforce":
        if not exempt:
            print("dispatch gate (shadow): hold %s by %s has no gate token: %s" % (device, tag, why_no), file=sys.stderr)
        return 0
    print("dispatch gate: refusing the hold: %s (run dispatch_gate.py admit --via hold first)" % why_no, file=sys.stderr)
    return 3


def admit_request(ctx, a):
    """request.sh's call site: the queued request JSON (a.arg) supplies title, device,
    ref, seconds and env; the gate flags supply class, evidence, input sequence, valid
    end and order. ALLOW writes `gate_token` into the request. In shadow mode it
    always exits 0; in enforce mode a DENY exits 2 and request.sh does not queue."""
    rq = json.load(open(a.arg))
    if not rq.get("title"):
        return 0                        # a disc request: no title, nothing to admit
    env = {}
    for e in rq.get("env") or []:
        if "=" in e:
            k, v = e.split("=", 1)
            env[k] = v
    # IDENTITY: the ISO the dispatcher will boot is the title. The request's own
    # `title_id` comes from request.sh's TITLE_ID and has been stale: the 10-05
    # Tron and Star Wars III requests carry GTA SA's 54540082. A conflict denies.
    cat = TR.build_catalog(ctx.p)
    by_iso, _ = cat.resolve(rq.get("title") or "")
    by_id = cat.canonical(rq["title_id"]) if TR.TID_RE.match((rq.get("title_id") or "").upper()) else None
    conflict = "request title_id %s is not the title of its ISO %r (%s)" % (rq.get("title_id"), rq.get("title"), by_iso) \
        if by_iso and by_id and by_iso != by_id else ""
    req = {"title": by_iso or rq.get("title_id") or rq.get("title"), "_id_conflict": conflict, "device": rq.get("device") or a.device or "", "build": rq.get("ref") or "",
           "seconds": rq.get("seconds") or 0, "env": env, "declared_env": a.declare or [],
           "caller": a.caller or rq.get("requester") or "", "via": "request"}
    if a.cls:
        req["class"] = a.cls
    for k in ("because", "input_seq", "valid_end", "order", "plan"):
        v = getattr(a, k)
        if v:
            req[k] = v
    if not req.get("input_seq") and rq.get("route_name"):
        req["input_seq"] = "route:" + rq["route_name"]
    d = admit(ctx, req, shadow=True if a.shadow else None)
    if d.allow:
        rq["gate_token"] = d.token
        tmp = a.arg + ".gate"
        with open(tmp, "w") as f:
            json.dump(rq, f, indent=1)
        os.replace(tmp, a.arg)
        print("dispatch gate: ALLOW %s" % d.token, file=sys.stderr)
        return 0
    print("dispatch gate: %s %s %s on %s" % ("SHADOW-DENY (logged, not refused)" if d.mode == "shadow" else "DENY",
                                             (d.row or {}).get("title_id", req["title"]), req.get("class"),
                                             req["device"] or "any"), file=sys.stderr)
    for r in d.reasons:
        print("  - " + r, file=sys.stderr)
    return 0 if d.mode == "shadow" else 2


def main(argv=None):
    ap = argparse.ArgumentParser(description="dispatch admission control")
    ap.add_argument("cmd", choices=["admit", "admit-request", "hold-check", "verify", "plan-check", "skip", "mode"])
    ap.add_argument("--tag")
    ap.add_argument("arg", nargs="?")
    ap.add_argument("--root", default=TR.DEFAULT_ROOT)
    ap.add_argument("--json")
    ap.add_argument("--title")
    ap.add_argument("--class", dest="cls")
    ap.add_argument("--device")
    ap.add_argument("--build")
    ap.add_argument("--because", action="append")
    ap.add_argument("--input-seq", dest="input_seq")
    ap.add_argument("--valid-end", dest="valid_end")
    ap.add_argument("--order")
    ap.add_argument("--seconds", type=int)
    ap.add_argument("--env", action="append")
    ap.add_argument("--declare", action="append")
    ap.add_argument("--caller")
    ap.add_argument("--via", choices=["request", "hold"])
    ap.add_argument("--installed-apk", dest="installed_apk")
    ap.add_argument("--readback", action="store_true")
    ap.add_argument("--plan")
    ap.add_argument("--row")
    ap.add_argument("--why")
    ap.add_argument("--shadow", action="store_true")
    ap.add_argument("--no-refresh", action="store_true")
    a = ap.parse_args(argv)
    ctx = Ctx(a.root, readback=readback_installed_apk if a.readback else None)
    if a.cmd == "mode":
        print(ctx.mode())
        return 0
    if a.cmd in ("admit", "admit-request", "plan-check") and not a.no_refresh:
        ok, _ = TR.freshness(ctx.p, ctx.registry_path)
        if not ok:
            rows, _, oi = TR.build(ctx.p)
            TR.write(ctx.p, rows, ctx.registry_path, open_issues=oi)
    if a.cmd == "admit":
        d = admit(ctx, _req_from_args(a), shadow=True if a.shadow else None)
        if d.allow:
            print("ALLOW %s" % d.token)
            for n in d.notes:
                print("  note: " + n)
            return 0
        print(("SHADOW-DENY" if d.mode == "shadow" else "DENY") + " %s %s on %s" % (
            (d.row or {}).get("title_id", d.req.get("title")), d.req.get("class"), d.req.get("device")))
        for r in d.reasons:
            print("  - " + r)
        return 0 if d.mode == "shadow" else 2
    if a.cmd == "admit-request":
        return admit_request(ctx, a)
    if a.cmd == "hold-check":
        return hold_check(ctx, a.device or "", a.tag or "", a.why or "")
    if a.cmd == "verify":
        ok, why = verify_token(ctx, a.arg, a.title, a.device)
        print(("VALID " if ok else "INVALID ") + why)
        return 0 if ok else 2
    if a.cmd == "plan-check":
        rows, rejects = plan_check(ctx, a.arg)
        for r in rows:
            bad = [x["why"] for x in rejects if x["row"] == r["row"]]
            print("%-4s %-9s %-17s %-30s %s" % (r["row"], r["tid"] or "-", r["cls"], r["title"][:30],
                                                "REJECT: " + " || ".join(bad) if bad else "ok"))
        return 2 if rejects else 0
    if a.cmd == "skip":
        if not (a.plan and a.row and a.why and a.caller):
            print("skip needs --plan --row --why --caller")
            return 2
        rows = parse_plan(a.plan)
        cat = TR.build_catalog(ctx.p)
        r = next((x for x in rows if x["row"] == a.row), None)
        if not r:
            print("no row %s in %s" % (a.row, a.plan))
            return 2
        tid, _, _ = _plan_title(ctx, r["title"], cat)
        _append_log(ctx, dict(utc=TR.iso_z(ctx.now), decision="SKIP", mode=ctx.mode(), caller=a.caller,
                              title_id=tid or r["title"], because="plan:%s#%s" % (os.path.basename(a.plan), a.row),
                              reasons=a.why))
        print("SKIP recorded: %s row %s (%s)" % (os.path.basename(a.plan), a.row, tid))
        return 0


if __name__ == "__main__":
    sys.exit(main())
