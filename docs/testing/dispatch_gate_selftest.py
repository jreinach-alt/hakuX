#!/usr/bin/env python3
"""Selftest for title_registry.py and dispatch_gate.py: the 2026-10-06 incidents
as regression fixtures, each with a MUTANT that disables the rule it rests on
and must turn the leg red.

    dispatch_gate_selftest.py            run every leg; exit 0 all green, 1 otherwise
    dispatch_gate_selftest.py -v         also print each decision's reasons

It needs no device, no network, no forge and no host files: it builds a
fixture work tree in a temp dir (ledger, holds, verdicts, listings, paths,
builds) that mirrors the records the incidents were decided on, and a fake
git (commit times and ancestry) in place of the host's bare repo.

A LEG is (fixture request, expected decision, mutant). It passes when the gate
decides as expected AND the same request under its mutant decides the other
way: a leg whose mutant cannot change the outcome is testing nothing, and is
reported red as `MUTANT SURVIVED`.
"""
import contextlib
import datetime as dt
import hashlib
import http.server
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import title_registry as TR    # noqa: E402
import dispatch_gate as G      # noqa: E402

VERBOSE = "-v" in sys.argv
UTC = dt.timezone.utc
NOW = dt.datetime(2026, 10, 6, 20, 30, tzinfo=UTC)          # 13:30 PDT
T = lambda h, m=0, d=6: dt.datetime(2026, 10, d, h, m, tzinfo=UTC)   # noqa: E731

# fixture commits: sha -> commit time (fake git). History is linear by time, except
# NOT_IN_BUILD (a lane branch that has not folded).
COMMITS = {
    "aaaaaaaaaa": T(1, 0, 4),        # the fixture's libfolders floor (10-04)
    "c0ffee0001": T(19, 0),          # NAME_SEQ / CHARSEL (10-06 12:00 PDT): changes MK's and Strike Force's path files
    "f1x2000001": T(20, 0),          # route fixes for Tron/NGB/Amped 2/Spider-Man 2, after their post-fix verdicts
    "7f1x000001": T(20, 2),          # a harness-wide change (pathfind.py): answers no title by its paths
    "unf01ded01": T(20, 5),          # MK's path file + emulator code on a lane branch, not in the build
    "d0c5f1x001": T(20, 6),          # MK's path file alone on pathfind's branch, not in the build
    "a11ce80401": T(19, 10),         # RalliSport's path file (an accuracy804-like fix): answers its menu time
    "6cef37f426": T(20, 10),         # the real 10-06 waitread1006 fold: lane docs only, newer than every verdict
    "bbbbbbbbbb": T(20, 15),         # master build used by the requests (10-06 13:15 PDT)
    "0ldf1x0001": T(1, 0, 3),        # a fix OLDER than the verdicts it would answer
}
PF_PATHS = "docs/testing/titles/pathknow/paths/%s.json"
COMMIT_PATHS = {
    "c0ffee0001": [PF_PATHS % "4D570034", PF_PATHS % "43560008", "docs/testing/titles/pathfind.py"],
    "f1x2000001": [PF_PATHS % t for t in ("42560001", "5443000D", "4D530041", "4156002B")],
    "7f1x000001": ["docs/testing/titles/pathfind.py", "docs/testing/titles/pathfind_selftest.py"],
    "unf01ded01": [PF_PATHS % "4D570034", "hw/xbox/nv2a/pgraph/vk/draw.c"],
    "d0c5f1x001": [PF_PATHS % "4D570034"],
    "a11ce80401": [PF_PATHS % "4D53000F"],
    "6cef37f426": ["docs/lanes/waitread1006/NOTES.md", "docs/lanes/waitread1006/evidence.tsv",
                   "docs/lanes/waitread1006/tools/run_waits.py"],
}
NOT_IN_BUILD = {"unf01ded01", "d0c5f1x001"}
BUILD = "bbbbbbbbbb"
APK = b"fixture apk bytes for bbbbbbbbbb"
APK_SHA12 = hashlib.sha256(APK).hexdigest()[:12]

# title_id: (name, ISO stem)
TITLES = {
    "54430001": ("Dead or Alive 3", "Dead_or_Alive_3"),
    "43430003": ("Dino Crisis 3", "Dino_Crisis_3"),
    "4D53000F": ("RalliSport Challenge", "RalliSport_Challenge"),
    "43560008": ("Strike Force Bowling", "Strike_Force_Bowling"),
    "4D570034": ("Mortal Kombat: Armageddon", "Mortal_Kombat_Armageddon"),
    "42560001": ("Tron 2.0: Killer App", "Tron_2_0_Killer_App"),
    "5443000D": ("Ninja Gaiden Black", "Ninja_Gaiden_Black"),
    "4D530041": ("Amped 2", "Amped_2"),
    "4156002B": ("Spider-Man 2", "Spider_Man_2"),
    "4D570014": ("NFL Blitz Pro", "NFL_Blitz_Pro"),
    "53450013": ("NBA 2K3", "NBA_2K3"),
    "42530014": ("AMF Xtreme Bowling", "AMF_Xtreme_Bowling"),
    "42530009": ("AMF Bowling 2004", "AMF_Bowling_2004"),
    "4D4A0008": ("Blowout", "Blowout"),
    "5655002F": ("Fight Club", "Fight_Club"),
}


def verdict(fps, play_share=0.99, crash=False, hang=False, worst_hitch=100.0, judged=T(4), failing=None):
    """A verdict.json shaped like title_verdict.py's, with the gate inputs set."""
    big = 1 if worst_hitch > 500 else 0
    fails = []
    if crash:
        fails.append("crash: exiting due to SIG_DFL handler for signal 11")
    if play_share < 0.9:
        fails.append("menu time: %.1f%% of the scored window in `play`" % (100 * play_share))
    if fps is not None and fps < 0.9:
        fails.append("fps: %.1f%% of gameplay at >= 30 fps (bar 90%%)" % (100 * fps))
    if big:
        fails.append("hitches: a %.0f ms stall after the first 60 s (bar 500 ms)" % worst_hitch)
    return {
        "booted": True, "reached_gameplay": True, "crash": crash, "hang": hang, "void": None,
        "gameplay_s": 640.0, "confirmation_need_s": 600.0, "pass_kind": "confirmation",
        "timeline": {"play_s": 610.0, "play_share": play_share},
        "fps_ok_share": fps, "fps_window_median": 29.9 if fps and fps < 0.9 else 45.0,
        "audio_measured": True, "audio_starve_share": 0.0,
        "hitches": {"n": 3, "n_after_warmup": 2, "per_min_after_warmup": 0.2, "worst_ms": worst_hitch,
                    "n_big_after_warmup": big,
                    "worst5": [{"off_s": 120.0, "max_ms": worst_hitch, "cls": "shader"}]},
        "hitch_allowance": None,
        "static_window": {"measured": True, "frozen_frac": 0.0, "n": 20, "source": "route-frames"},
        "position": {"measured": True, "first_last": 0.7, "still_frac": 0.0, "bar": 0.025, "samples": 20},
        "pass": not fails,
        "failing": (failing if failing is not None else (fails[0] if fails else None)),
        "failures": fails,
        "judged_utc": judged.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


# run dir -> (title_id, verdict or None, device)
RUNS = {
    # Incident 4: DOA3 below the bar; `failing` names only menu time
    "retro-doa3": ("54430001", verdict(0.4394, play_share=0.7014, worst_hitch=653.2, judged=T(4, 0, 5)), "nova"),
    "dino-crisis-3-hold": ("43430003", verdict(0.3793, play_share=0.7906, judged=T(4, 44, 4)), "nova"),
    # Incident 2: RalliSport's latest verdict failed on menu time only; a "fix folded" (c0ffee0001) is newer
    "screen-ralli-challenge/hold": ("4D53000F", verdict(1.0, play_share=0.80, judged=T(15, 31, 4)), "nova"),
    # Incident 1: Strike Force failed on name entry (menu time); NAME_SEQ c0ffee0001 is newer
    "strike-force-bowling/hold5": ("43560008", verdict(1.0, play_share=0.70, judged=T(2, 25)), "nova"),
    "rehold2-4D570034": ("4D570034", verdict(1.0, play_share=0.80, judged=T(15, 26)), "nova"),
    "retro-tron": ("42560001", verdict(0.92, worst_hitch=1064.0, judged=T(5, 9, 5)), "nova"),
    "retro-ngb": ("5443000D", verdict(0.2495, judged=T(4, 35, 5)), "nova"),
    "retro-amped2": ("4D530041", verdict(0.4423, judged=T(4, 18, 5)), "nova"),
    "sweep-4156002B": ("4156002B", verdict(0.2895, judged=T(4, 3)), "nova"),
    "nba-2k3/hold3": ("53450013", verdict(0.9632, judged=T(19, 56)), "nova"),
    "amf-xtreme-bowling/hold2": ("42530014", verdict(1.0, play_share=0.747, crash=True, judged=T(23, 55, 5)), "nova"),
    "amf-bowling-2004/hold2": ("42530009", verdict(1.0, play_share=0.892, judged=T(20, 24, 5)), "nova"),
    "blowout-1006": ("4D4A0008", verdict(1.0, play_share=0.831, judged=T(22, 21) - dt.timedelta(hours=3)), "nova"),
    # the four owner-held below-bar titles after a fix: perf now clears, menu time fails. Only the
    # owner's below_bar hold (released by lane.local, never by a verdict) keeps them out.
    "postfix-tron": ("42560001", verdict(0.95, play_share=0.70, judged=T(19, 30)), "nova"),
    "postfix-ngb": ("5443000D", verdict(0.95, play_share=0.70, judged=T(19, 30)), "nova"),
    "postfix-amped2": ("4D530041", verdict(0.95, play_share=0.70, judged=T(19, 30)), "nova"),
    "postfix-sm2": ("4156002B", verdict(0.95, play_share=0.70, judged=T(19, 30)), "nova"),
}

LEDGER = "date_pdt\ttitle\ttitle_id\tresult\taccepted_by\tevidence\n" \
         "2026-10-06 14:05\tNBA 2K3\t\tpathfind held run runs/nba-2k3/hold3\tlane.local (frame review)\tPASS\n" \
         "2026-10-05 14:05\tAMF Bowling 2004\t-\tpathfind held run runs/amf-bowling-2004/hold2\towner\tFAIL on play share only\n"


def holds_text(ralli_order_released=False, with_amf_hold=False):
    src = os.path.join(HERE, "..", "lanes", "dispatchgate1006", "owner-holds.seed.tsv")
    lines = open(src).read().splitlines()
    out = []
    for l in lines:
        c = l.split("\t")
        if not l.startswith("#") and len(c) > 1:
            if c[0] == "owner-1006-1450-ralli":
                c[9] = "2026-10-06 lane.local: ran" if ralli_order_released else ""
            if c[0] == "amf-xtreme-835-837" and not with_amf_hold:
                continue              # the AMF leg rests on the run's crash alone
            if c[0] == "libfolders-floor":
                c[11] = "aaaaaaaaaa"  # the fixture's floor commit
            if c[0] == "forza-583-floor":
                continue
            l = "\t".join(c)
        out.append(l)
    return "\n".join(out) + "\n"


def build_tree(root, ralli_order_released=False):
    def w(rel, text):
        p = os.path.join(root, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w") as f:
            f.write(text)
    w("pm/playable-accepted.tsv", LEDGER)
    w("pm/owner-holds.tsv", holds_text(ralli_order_released))
    w("pm/failure-intake.tsv", "utc\tclass\thandoff\ttitle\ttitle_id\tresult\troute\troute_sha\tgolden\tevidence\n")
    w("pm/pathfind-pool.tsv", "utc\tclass\thandoff\ttitle\ttitle_id\tresult\troute\troute_sha\tgolden\tevidence\n")
    w("host-tools/blocked-titles.txt", "# blocked\n41540004\tGalleon -- owner 2026-09-30\n")
    w("hardware/titlepush/listing-nova.txt", "# nova, listed\n" + "".join(
        "%s-%s.xiso.iso\n" % (t, stem) for t, (_, stem) in sorted(TITLES.items())))
    w("titles/xemu-compat-2026-09-25.csv", "title_id,canonical_title_id,name\n" + "".join(
        "%s,%s,%s\n" % (t, t, n.replace(",", " ")) for t, (n, _) in sorted(TITLES.items())))
    runs = os.path.join("wt", "pathfind", "docs", "lanes", "pathfind", "runs")
    for rd, (tid, v, dev) in RUNS.items():
        name, stem = TITLES[tid]
        # the folder-ISO held runs carry no title_id: resolved from the ISO stem, exactly
        res = {"title_id": None if "bowling" in rd else tid, "name": name, "device": dev,
               "iso": "/storage/X/%s.xiso.iso" % stem, "started": "2026-10-05 12:00:00 PDT"}
        w(os.path.join(runs, rd, "result.json"), json.dumps(res))
        w(os.path.join(runs, rd, "request.json"), json.dumps({"title": name, "title_id": res["title_id"], "device": dev}))
        if v:
            w(os.path.join(runs, rd, "verdict.json"), json.dumps(v))
    paths = os.path.join("wt", "pathfind", "docs", "testing", "titles", "pathknow", "paths")
    for tid in TITLES:
        w(os.path.join(paths, tid + ".json"), json.dumps({"title_id": tid, "complete": True, "result": "gameplay",
                                                          "steps": []}))
    os.makedirs(os.path.join(root, "dispatch", "builds"), exist_ok=True)
    with open(os.path.join(root, "dispatch", "builds", BUILD + ".apk"), "wb") as f:
        f.write(APK)
    os.makedirs(os.path.join(root, "dispatch", "hold"), exist_ok=True)


class FakeCtx(G.Ctx):
    def commit_time(self, sha):
        for k, t in COMMITS.items():
            if sha and (k.startswith(sha) or sha.startswith(k)):
                return t
        return None

    def is_ancestor(self, older, newer):
        if older == newer:
            return True
        to, tn = self.commit_time(older), self.commit_time(newer)
        return bool(to and tn) and to <= tn and not any(_sha_pre(older, k) for k in NOT_IN_BUILD)

    def commit_paths(self, sha):
        return next((v for k, v in COMMIT_PATHS.items() if _sha_pre(sha, k)), [] if self.commit_time(sha) else None)


def _sha_pre(a, b):
    return bool(a and b) and (a.startswith(b) or b.startswith(a))


class _AllAncestors(FakeCtx):
    """Mutant: every commit is in every build."""
    def is_ancestor(self, older, newer):
        return True


def _pre_review_rule():
    """Mutant: the matrix as lane.local's 18:10 review found it. Any commit newer than the
    latest verdict was a fix, and a below-bar title with one got a Playable attempt."""
    def old_fix(ctx, req, row):
        vt = G._latest_verdict_time(row)
        for sha in G._because(req, "fix") + ([row["fix_commit"]] if row.get("fix_commit") else []):
            ct = ctx.commit_time(sha)
            if ct is not None and (vt is None or ct > vt):
                return sha, "newer"
        return None, "none newer"

    def rule_class_status(ctx, req, row, d):
        if row and req.get("class") == "PLAYABLE_ATTEMPT" and row["status"] == "BELOW_BAR":
            if not old_fix(ctx, req, row)[0]:
                d.deny("matrix", "below the bar, no newer commit")
            return
        real = G._answering_fix
        G._answering_fix = old_fix
        try:
            G.rule_class_status(ctx, req, row, d)
        finally:
            G._answering_fix = real
    return rule_class_status


def fresh_ctx(root, now=NOW):
    ctx = FakeCtx(root, now=now)
    rows, unresolved, oi = TR.build(ctx.p, now=now, use_forge=False)
    TR.write(ctx.p, rows, ctx.registry_path, now=now, open_issues=oi)
    return ctx, unresolved


def seq(ctx, tid):
    _, rows = ctx.registry()
    return (rows.get(tid) or {}).get("input_seq", "")


def req(ctx, tid, cls, **kw):
    r = dict(title=tid, **{"class": cls}, device="nova", build=BUILD, seconds=900,
             because=["verdict:wt/pathfind/docs/lanes/pathfind/runs"], input_seq=seq(ctx, tid),
             valid_end="valid-verdict", caller="lane.pathfind", via="request")
    r.update(kw)
    return r


# ---------------------------------------------------------------- the legs

RESULTS = []


def leg(name, ctx, request, expect_allow, mutant, mutant_desc):
    """mutant: dict(disabled=[rule names]) or a callable(ctx, request) -> Decision."""
    d = G.admit(ctx, request, write_log=False, shadow=False)
    ok = d.allow == expect_allow
    if callable(mutant):
        dm = mutant(ctx, request)
    else:
        dm = G.admit(ctx, request, write_log=False, shadow=False, **mutant)
    flipped = dm.allow != d.allow
    status = "GREEN" if ok and flipped else ("RED" if not ok else "RED (MUTANT SURVIVED)")
    RESULTS.append((name, status))
    print("%-5s %-62s %s | mutant[%s] -> %s" % (status.split()[0], name, "ALLOW" if d.allow else "DENY",
                                               mutant_desc, "ALLOW" if dm.allow else "DENY"))
    if VERBOSE or not ok:
        for r in d.reasons:
            print("        - " + r)
    elif d.reasons:
        print("        - " + d.reasons[0][:200])
    return d


def check(name, cond, mutant_cond, detail=""):
    status = "GREEN" if cond and not mutant_cond else ("RED" if not cond else "RED (MUTANT SURVIVED)")
    RESULTS.append((name, status))
    print("%-5s %-62s %s" % (status.split()[0], name, detail))


@contextlib.contextmanager
def holds_without(kinds=(), ids=()):
    real = TR.load_holds

    def fake(p):
        return [h for h in real(p) if h.get("kind") not in kinds and h.get("id") not in ids]
    TR.load_holds = fake
    try:
        yield
    finally:
        TR.load_holds = real


def rebuilt(root, now=NOW):
    ctx, _ = fresh_ctx(root, now)
    return ctx


# ---------------------------------------------------------------- the forge: local HTTP, never gh

GH_CALL = re.compile(r"""(\[\s*|\(\s*|which\(\s*)["']gh["']|["']gh\s+(issue|api|pr|repo)\b""")
# the line lane.local's review found at title_registry.py:484 (10-06 18:10)
REVIEWED_GH_LINE = 'out = subprocess.run(["gh", "issue", "list", "--repo", "jreinach-alt/hakuX", "--state", "open",'


def gh_calls(text):
    return [l.strip() for l in text.splitlines() if GH_CALL.search(l) and not l.lstrip().startswith("#")]


class _FakeForge(http.server.BaseHTTPRequestHandler):
    """Forgejo's issue listing: OPEN pages, then an empty page. Records each request's auth."""
    OPEN = []
    SEEN = []

    def do_GET(self):
        page = int((re.search(r"[?&]page=(\d+)", self.path) or [0, "1"])[1])
        _FakeForge.SEEN.append((self.path, self.headers.get("Authorization")))
        body = json.dumps(_FakeForge.OPEN if page == 1 else []).encode()
        self.send_response(200 if self.headers.get("Authorization") == "token fixture-token" else 403)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


def forge_legs():
    print("== the forge: read over local HTTP, never gh; unreadable keeps holds active")
    srcs = {n: open(os.path.join(HERE, n)).read() for n in ("title_registry.py", "dispatch_gate.py", "dispatch_audit.py")}
    found = {n: gh_calls(t) for n, t in srcs.items() if gh_calls(t)}
    check("no `gh` invocation in title_registry.py, dispatch_gate.py, dispatch_audit.py", not found,
          not gh_calls(srcs["title_registry.py"] + "\n        " + REVIEWED_GH_LINE),
          "found %s | mutant[the reviewed line restored] flagged" % (found or "none"))
    tmp = tempfile.mkdtemp(prefix="dispatchgate-forge-")
    srv = http.server.HTTPServer(("127.0.0.1", 0), _FakeForge)
    th = threading.Thread(target=srv.serve_forever, daemon=True)
    th.start()
    url = "http://127.0.0.1:%d" % srv.server_address[1]
    calls = []
    real_run, real_popen, real_system = subprocess.run, subprocess.Popen, os.system

    def rec(name, real):
        def f(*a, **kw):
            argv = a[0] if a else kw.get("args")
            calls.append(argv if isinstance(argv, (list, tuple)) else str(argv).split())
            return real(*a, **kw)
        return f
    try:
        build_tree(tmp)
        with open(os.path.join(tmp, "pm", "owner-holds.tsv"), "w") as f:
            f.write(holds_text(with_amf_hold=True))
        os.makedirs(os.path.join(tmp, "forge", "tokens"))
        with open(os.path.join(tmp, "forge", "tokens", "jobs.token"), "w") as f:
            f.write("fixture-token\n")
        p = TR.Paths(tmp)
        subprocess.run, subprocess.Popen, os.system = rec("run", real_run), rec("Popen", real_popen), rec("system", real_system)

        def amf(forge_url, use_forge=True):
            rows, _, oi = TR.build(p, now=NOW, use_forge=use_forge, forge_url=forge_url)
            out = os.path.join(tmp, "pm", "reg-forge.tsv")
            TR.write(p, rows, out, now=NOW, open_issues=oi)
            hdr, reg = TR.read_registry(out)
            return hdr.get("forge"), reg["42530014"]["holds"], oi
        _FakeForge.OPEN = [{"number": 835, "title": "AMF Xtreme SIGSEGV"}, {"number": 900, "title": "a PR",
                                                                            "pull_request": {}}]
        f_open, h_open, oi_open = amf(url)
        _FakeForge.OPEN = [{"number": 10, "title": "unrelated"}]
        f_closed, h_closed, _ = amf(url)
        f_down, h_down, _ = amf("http://127.0.0.1:9")
        os.remove(os.path.join(tmp, "forge", "tokens", "jobs.token"))
        f_notok, h_notok, _ = amf(url)
        auths = set(a for _, a in _FakeForge.SEEN)
        gh_seen = [c for c in calls if c and os.path.basename(str(c[0])) == "gh"]

        # mutant: the reviewed reader, shelling out to gh (a stub that is never on PATH here)
        def gh_reader(p, use_forge=True, url=None):
            try:
                out = subprocess.run(["gh", "issue", "list", "--state", "open", "--json", "number,title"],
                                     capture_output=True, text=True, timeout=10, env={"PATH": "/nonexistent"})
                return {int(x["number"]): x["title"] for x in json.loads(out.stdout)}
            except (OSError, ValueError):
                return None
        real_reader = TR.forge_open_issues
        TR.forge_open_issues = gh_reader
        try:
            amf(url)
        finally:
            TR.forge_open_issues = real_reader
        gh_mut = [c for c in calls if c and os.path.basename(str(c[0])) == "gh"]

        # mutant: an unreadable forge read as "nothing open"
        TR.forge_open_issues = lambda p, use_forge=True, url=None: real_reader(p, use_forge, url) or {}
        try:
            _, h_mut, _ = amf("http://127.0.0.1:9")
        finally:
            TR.forge_open_issues = real_reader
    finally:
        subprocess.run, subprocess.Popen, os.system = real_run, real_popen, real_system
        srv.shutdown()
        shutil.rmtree(tmp, ignore_errors=True)
    check("registry build reads the forge over HTTP with the jobs token, never runs gh",
          not gh_seen and auths == {"token fixture-token"} and oi_open == {835: "AMF Xtreme SIGSEGV"},
          not gh_mut, "%d HTTP request(s), %d gh call(s) | mutant[gh reader] -> %d gh call(s)"
          % (len(_FakeForge.SEEN), len(gh_seen), len(gh_mut)))
    check("#835 open on the forge -> AMF's crash hold active; #835/#837 closed -> released",
          f_open == "ok" and "amf-xtreme-835-837" in h_open and f_closed == "ok" and "amf-xtreme-835-837" not in h_closed,
          False, "open: %r / closed: %r" % (h_open, h_closed))
    check("forge unreachable or no token -> header forge=unreadable, the hold stays active",
          f_down == "unreadable" and "amf-xtreme-835-837" in h_down and f_notok == "unreadable"
          and "amf-xtreme-835-837" in h_notok,
          "amf-xtreme-835-837" in h_mut,
          "down: forge=%s holds=%r; no token: forge=%s | mutant[unreadable read as nothing open] -> holds=%r"
          % (f_down, h_down, f_notok, h_mut))


def main():
    tmp = tempfile.mkdtemp(prefix="dispatchgate-selftest-")
    try:
        build_tree(tmp)
        ctx, unresolved = fresh_ctx(tmp)
        _, rows = ctx.registry()

        print("== registry: identity and recomputed gates")
        amf = rows.get("42530014", {})
        check("AMF Xtreme Bowling resolves to 42530014, not the ledger's AMF 2004",
              amf.get("ledger") == "" and amf.get("status") == "CRASH_OR_HANG" and rows["42530009"]["status"] == "PLAYABLE",
              # mutant: a word-substring ledger test like the earlier tool's ("amf" and "bowling" both in a
              # ledger title) puts AMF Xtreme in the ledger
              not any(all(w in lt.lower() for w in ("amf", "bowling"))
                      for lt in [r["title"] for r in TR.read_tsv(os.path.join(tmp, "pm", "playable-accepted.tsv"))]),
              "status %s, ledger %r" % (amf.get("status"), amf.get("ledger")))
        doa = rows.get("54430001", {})
        real_rg = TR.recompute_gates

        def trust_failing(v):            # mutant: the gates are what `failing` names, nothing else
            g, det = real_rg(v)
            first = (v.get("failing") or "").split(":")[0].replace(" ", "_")
            return [x for x in g if x == first], det
        TR.recompute_gates = trust_failing
        try:
            mrow = rebuilt(tmp).registry()[1].get("54430001", {})
        finally:
            TR.recompute_gates = real_rg
        ctx = rebuilt(tmp)
        check("DOA3 failing_all carries fps although `failing` says menu time",
              "fps" in doa.get("failing_all", "").split("+") and doa.get("status") == "BELOW_BAR",
              "fps" in mrow.get("failing_all", "").split("+") and mrow.get("status") == "BELOW_BAR",
              "failing_all=%s status=%s fps_ok_share=%s" % (doa.get("failing_all"), doa.get("status"), doa.get("fps_ok_share")))
        check("every fixture run resolved (no name guessed)", not unresolved, False, "%d unresolved" % len(unresolved))

        print("== incident fixtures")
        # 4. DOA3 / Dino Crisis 3: below the bar, Playable attempt refused
        leg("DOA3 PLAYABLE_ATTEMPT -> deny (BELOW_BAR, fps_ok_share 0.4394)", ctx,
            req(ctx, "54430001", "PLAYABLE_ATTEMPT"), False, dict(disabled=["rule_class_status"]), "no matrix")
        leg("Dino Crisis 3 PLAYABLE_ATTEMPT -> deny (BELOW_BAR 0.3793)", ctx,
            req(ctx, "43430003", "PLAYABLE_ATTEMPT"), False, dict(disabled=["rule_class_status"]), "no matrix")
        leg("DOA3 PLAYABLE_ATTEMPT citing a fix OLDER than its verdict -> deny", ctx,
            req(ctx, "54430001", "PLAYABLE_ATTEMPT", because=["fix:0ldf1x0001"]), False,
            dict(disabled=["rule_class_status"]), "no matrix")
        # 2. RalliSport: the owner hold, with a 'fix folded' that answers its menu time
        ralli = req(ctx, "4D53000F", "PLAYABLE_ATTEMPT", because=["fix:a11ce80401"])

        def no_exclude_holds(c, r):
            with holds_without(kinds=("exclude",)):
                return G.admit(rebuilt(tmp), r, write_log=False, shadow=False)
        leg("RalliSport PLAYABLE_ATTEMPT with 'fix folded' -> deny (owner hold)", ctx, ralli, False,
            no_exclude_holds, "exclude holds dropped")
        rd = req(ctx, "4D53000F", "OWNER_DIAGNOSTIC", order="owner-1006-1450-ralli", valid_end="condition:rival cars visible",
                 because=["order:owner-1006-1450-ralli"])
        leg("RalliSport OWNER_DIAGNOSTIC with the order id -> allow", ctx, rd, True,
            lambda c, r: G.admit(c, dict(r, order="owner-1006-1450-ralli-typo"), write_log=False, shadow=False),
            "order id not on record")
        leg("RalliSport OWNER_DIAGNOSTIC without an order -> deny", ctx, dict(rd, order=""), False,
            dict(disabled=["rule_owner_order"]), "no order rule")
        # 3. installed APK read back and compared with dispatch/builds/<sha>.apk
        val = req(ctx, "4D4A0008", "VALIDATION", via="hold", caller="lane.local", seconds=600,
                  valid_end="condition:the 145 s corner stall at hold.jsonl n=28-35 reverses",
                  because=["run:wt/pathfind/docs/lanes/pathfind/runs/blowout-1006"], installed_apk="0123456789ab")
        leg("installed APK sha != requested build -> deny", ctx, val, False, dict(disabled=["rule_build"]), "no build rule")
        leg("installed APK not read back -> deny", ctx, dict(val, installed_apk=None), False,
            dict(disabled=["rule_build"]), "no build rule")
        good = dict(val, installed_apk=APK_SHA12)
        leg("Blowout VALIDATION naming the stall, APK read back -> allow", ctx, good, True,
            lambda c, r: G.admit(c, dict(r, installed_apk="0123456789ab"), write_log=False, shadow=False),
            "readback mismatched")
        leg("Blowout VALIDATION naming no condition -> deny", ctx,
            dict(good, valid_end="capture:600s", because=["run:wt/pathfind/docs/lanes/pathfind/runs/blowout-1006"]),
            False, dict(disabled=["rule_class_status"]), "no matrix")
        # 1. Strike Force ahead of the plan order
        plan = os.path.join(tmp, "pm", "plan-2026-10-06-replan.md")
        with open(plan, "w") as f:
            f.write("# Plan\n\n| # | Title (issue) | P | Committed change that answers the last failure | Slot |\n"
                    "|---|---|---|---|---|\n"
                    "| 1 | **MK Armageddon** 4D570034 (#852) | 0.5 | CHARSEL A,B,START (c0ffee0001) | 14:05 |\n"
                    "| 2 | **RalliSport Challenge** (#804) | 0.5 | accuracy804 (folded) | 14:30 |\n"
                    "| 10 | **Strike Force Bowling** (#840) | 0.3 | NAME_SEQ (c0ffee0001) | 18:00 |\n")
        os.utime(plan, (NOW.timestamp() - 600, NOW.timestamp() - 600))
        sf = req(ctx, "43560008", "PLAYABLE_ATTEMPT", because=["fix:c0ffee0001"], plan=plan)
        leg("Strike Force ahead of the plan order -> deny", ctx, sf, False, dict(disabled=["rule_plan"]), "no plan rule")
        leg("MK Armageddon, row 1 of the plan -> allow", ctx,
            req(ctx, "4D570034", "PLAYABLE_ATTEMPT", because=["fix:c0ffee0001"], plan=plan), True,
            dict(disabled=[]) if False else (lambda c, r: G.admit(c, dict(r, because=["fix:0ldf1x0001"]),
                                                                  write_log=False, shadow=False)),
            "fix older than verdict")
        prow, prej = G.plan_check(ctx, plan)
        rj = [x for x in prej if x["row"] == "2"]
        check("plan_check rejects RalliSport row 2 ('folded', no commit, owner hold)",
              bool(rj) and any("folded" in x["why"] for x in rj) and any("hold" in x["why"] for x in rj),
              False, " || ".join(x["why"][:90] for x in rj))
        check("plan_check passes rows 1 and 10", not [x for x in prej if x["row"] in ("1", "10")], False,
              "%d rows, %d rejects" % (len(prow), len(prej)))
        # owner-held below-bar titles after a clearing verdict, each WITH a fix that answers its
        # remaining menu-time failure, so only the owner hold stands
        for tid in ("42560001", "5443000D", "4D530041", "4156002B"):
            def no_below_holds(c, r):
                with holds_without(kinds=("below_bar",)):
                    return G.admit(rebuilt(tmp), r, write_log=False, shadow=False)
            leg("%s PLAYABLE_ATTEMPT -> deny (owner below-bar hold)" % TITLES[tid][0], ctx,
                req(ctx, tid, "PLAYABLE_ATTEMPT", because=["fix:f1x2000001"]), False, no_below_holds,
                "below_bar holds dropped")

        print("== what counts as a fix (lane.local review 10-06 18:10)")
        pre = _pre_review_rule()

        def pre_review(c, r):            # mutant: the gate as reviewed (a newer commit is a fix)
            i = G.RULES.index(G.rule_class_status)
            G.RULES[i] = pre
            try:
                return G.admit(c, r, write_log=False, shadow=False)
            finally:
                G.RULES[i] = G.rule_class_status
        leg("DOA3 PLAYABLE_ATTEMPT citing fix:6cef37f426 (an unrelated fold) -> deny", ctx,
            req(ctx, "54430001", "PLAYABLE_ATTEMPT", because=["fix:6cef37f426"]), False, pre_review,
            "newer commit = fix")
        leg("MK Armageddon (menu time) citing fix:6cef37f426 -> deny", ctx,
            req(ctx, "4D570034", "PLAYABLE_ATTEMPT", because=["fix:6cef37f426"]), False, pre_review,
            "newer commit = fix")
        mk_ok = req(ctx, "4D570034", "PLAYABLE_ATTEMPT", because=["fix:c0ffee0001"])

        def no_gate_paths(c, r):
            saved = dict(G.GATE_PATHS)
            G.GATE_PATHS.clear()
            try:
                return G.admit(c, r, write_log=False, shadow=False)
            finally:
                G.GATE_PATHS.update(saved)
        leg("MK citing a commit that changes its own path file -> allow", ctx, mk_ok, True, no_gate_paths,
            "GATE_PATHS empty")
        leg("MK citing a harness-wide commit, no title-fixes row -> deny", ctx,
            dict(mk_ok, because=["fix:7f1x000001"]), False, pre_review, "newer commit = fix")
        leg("MK citing a fix with emulator code not in the requested build -> deny", ctx,
            dict(mk_ok, because=["fix:unf01ded01"]), False,
            lambda c, r: G.admit(_AllAncestors(tmp, now=NOW), r, write_log=False, shadow=False), "every commit in build")

        def apk_only(c, r):              # mutant: a path-file (tooling) fix must also be in the APK build
            saved = G.TOOLING_PREFIXES
            G.TOOLING_PREFIXES = ("no-such-prefix/",)
            try:
                return G.admit(c, r, write_log=False, shadow=False)
            finally:
                G.TOOLING_PREFIXES = saved
        leg("MK citing a path-file-only fix not in the APK build -> allow (tool tree)", ctx,
            dict(mk_ok, because=["fix:d0c5f1x001"]), True, apk_only, "tooling fix needs the APK")
        fixes_tsv = os.path.join(tmp, "pm", "title-fixes.tsv")

        def with_fixes(rows, r, how=lambda c, r: G.admit(c, r, write_log=False, shadow=False)):
            with open(fixes_tsv, "w") as f:
                f.write("\t".join(TR.FIX_COLS) + "\n" + "".join("\t".join(x) + "\n" for x in rows))
            try:
                return how(rebuilt(tmp), r)
            finally:
                os.remove(fixes_tsv)
        row_ll = ["4D570034", "menu_time", "7f1x000001", "lane.local", "2026-10-06 13:20",
                  "the CHARSEL step in pathfind.py is what MK's menu time failed on (hold frames 40-52)"]
        r_hw = dict(mk_ok, because=["fix:7f1x000001"])
        d_ll = with_fixes([row_ll], r_hw)
        d_pf = with_fixes([row_ll[:3] + ["lane.pathfind"] + row_ll[4:]], r_hw)
        d_gate = with_fixes([row_ll[:1] + ["audio"] + row_ll[2:]], r_hw)
        d_nowhy = with_fixes([row_ll[:5] + [""]], r_hw)
        check("harness-wide commit + a lane.local title-fixes row naming menu_time -> allow",
              d_ll.allow, d_pf.allow, "row set_by lane.local -> %s; mutant set_by lane.pathfind -> %s"
              % ("ALLOW" if d_ll.allow else "DENY: " + "; ".join(d_ll.reasons)[:160], "ALLOW" if d_pf.allow else "DENY"))
        check("a title-fixes row naming another gate, or with no why, answers nothing",
              d_ll.allow and not d_gate.allow and not d_nowhy.allow, False,
              "gate audio -> %s, no why -> %s" % ("ALLOW" if d_gate.allow else "DENY", "ALLOW" if d_nowhy.allow else "DENY"))
        fps_row = [["54430001", "fps", "7f1x000001", "lane.local", "2026-10-06 13:20", "a perf fix"]]
        r_fps = req(ctx, "54430001", "PLAYABLE_ATTEMPT", because=["fix:7f1x000001"])
        d_fps = with_fixes(fps_row, r_fps)
        d_fps_mut = with_fixes(fps_row, r_fps, pre_review)
        check("DOA3 with a recorded fps fix and no verdict after it: PLAYABLE_ATTEMPT -> deny",
              not d_fps.allow and any("verdict after" in x for x in d_fps.reasons), not d_fps_mut.allow,
              "%s | mutant[newer commit = fix] -> %s" % ((d_fps.reasons or ["ALLOW"])[0][:110],
                                                         "ALLOW" if d_fps_mut.allow else "DENY"))
        ctx = rebuilt(tmp)             # title-fixes.tsv is gone again: rebuild over the restored sources
        tel = req(ctx, "54430001", "TELEMETRY", because=["fix:7f1x000001"], valid_end="capture:600s")
        leg("DOA3 TELEMETRY on the fix build -> allow", ctx, tel, True,
            lambda c, r: G.admit(c, dict(r, **{"class": "PLAYABLE_ATTEMPT", "valid_end": "valid-verdict"}),
                                 write_log=False, shadow=False), "same request as a Playable attempt")
        # football: refused with no release; the env var changes nothing
        os.environ["PATHFIND_FOOTBALL"] = "1"
        fb = req(ctx, "4D570014", "SCREEN", input_seq="discovery")

        def no_football(c, r):
            with holds_without(ids=("football-last",)):
                return G.admit(rebuilt(tmp), r, write_log=False, shadow=False)
        leg("NFL Blitz Pro SCREEN, PATHFIND_FOOTBALL=1 in env -> deny", ctx, fb, False, no_football, "football hold dropped")
        del os.environ["PATHFIND_FOOTBALL"]
        leg("NBA 2K3 (in the ledger) PLAYABLE_ATTEMPT -> deny", ctx,
            req(ctx, "53450013", "PLAYABLE_ATTEMPT", because=["fix:c0ffee0001"]), False,
            dict(disabled=["rule_class_status"]), "no matrix")
        leg("AMF Xtreme Bowling (crash, no fix) PLAYABLE_ATTEMPT -> deny", ctx,
            req(ctx, "42530014", "PLAYABLE_ATTEMPT", because=["fix:c0ffee0001"]), False,
            dict(disabled=["rule_class_status"]), "no matrix")
        leg("Fight Club (UNSCREENED) first run -> allow SCREEN", ctx,
            req(ctx, "5655002F", "SCREEN", input_seq="discovery"), True,
            lambda c, r: G.admit(c, dict(r, title="4D4A0008"), write_log=False, shadow=False), "same request, a screened title")
        leg("SCREEN of a title that has run -> deny", ctx,
            req(ctx, "4D4A0008", "SCREEN", input_seq="discovery"), False, dict(disabled=["rule_class_status"]), "no matrix")
        # stale registry
        stale = FakeCtx(tmp, now=NOW + dt.timedelta(minutes=20))
        leg("stale registry (20 min old) -> deny", stale, req(stale, "5655002F", "SCREEN", input_seq="discovery"), False,
            dict(disabled=["rule_registry_fresh"]), "no freshness rule")
        ctx2 = rebuilt(tmp)
        with open(os.path.join(tmp, "pm", "playable-accepted.tsv"), "a") as f:
            f.write("2026-10-06 15:00\tFight Club\t5655002F\tx\tlane.local\tPASS\n")
        leg("registry sources changed since the build -> deny", ctx2,
            req(ctx2, "5655002F", "SCREEN", input_seq="discovery"), False,
            dict(disabled=["rule_registry_fresh"]), "no freshness rule")
        with open(os.path.join(tmp, "pm", "playable-accepted.tsv"), "w") as f:
            f.write(LEDGER)
        ctx = rebuilt(tmp)
        # hand-typed override env vars are ignored
        doa = req(ctx, "54430001", "PLAYABLE_ATTEMPT")
        base = G.admit(ctx, doa, write_log=False, shadow=False).allow
        for k in ("DISPATCH_GATE_OVERRIDE", "DISPATCH_GATE", "HAKUX_GATE_OFF", "PATHFIND_FOOTBALL", "FORCE"):
            os.environ[k] = "1"
        withenv = G.admit(ctx, doa, write_log=False, shadow=False).allow
        mutant_rules = G.RULES + []

        def env_reading_rule(c, r, row, d):     # mutant: a gate that honours an override variable
            if os.environ.get("DISPATCH_GATE_OVERRIDE"):
                d.reasons.clear()
        G.RULES.append(env_reading_rule)
        withmutant = G.admit(ctx, doa, write_log=False, shadow=False).allow
        G.RULES[:] = mutant_rules
        for k in ("DISPATCH_GATE_OVERRIDE", "DISPATCH_GATE", "HAKUX_GATE_OFF", "PATHFIND_FOOTBALL", "FORCE"):
            del os.environ[k]
        check("override env vars set -> DOA3 decision unchanged (DENY)", base is False and withenv is False,
              withmutant is False, "mutant[env-reading rule] -> %s" % ("ALLOW" if withmutant else "DENY"))

        print("== run-level preflight")
        leg("Thor PLAYABLE_ATTEMPT (fan dead, 480 s cap) -> deny", ctx,
            req(ctx, "4D570034", "PLAYABLE_ATTEMPT", device="thor", because=["fix:c0ffee0001"], seconds=900), False,
            dict(disabled=["rule_device", "rule_staged"]), "no device rule")
        late = rebuilt(tmp, now=T(4, 20, 7))
        leg("time window: Playable attempt at 21:20 PDT -> deny", late,
            req(late, "4D570034", "PLAYABLE_ATTEMPT", because=["fix:c0ffee0001"]), False,
            dict(disabled=["rule_window"]), "no window rule")
        ctx = rebuilt(tmp)
        leg("no input sequence -> deny", ctx, req(ctx, "4D570034", "PLAYABLE_ATTEMPT", because=["fix:c0ffee0001"],
                                                   input_seq=""), False, dict(disabled=["rule_input_and_end"]), "no input rule")
        leg("no valid end (budget) -> deny", ctx, req(ctx, "4D570034", "PLAYABLE_ATTEMPT", because=["fix:c0ffee0001"],
                                                       valid_end="budget:900s"), False,
            dict(disabled=["rule_input_and_end"]), "no input rule")
        leg("undeclared request env -> deny", ctx, req(ctx, "4D570034", "PLAYABLE_ATTEMPT", because=["fix:c0ffee0001"],
                                                        env={"HAKUX_FRAMETRACE": "1"}), False,
            dict(disabled=["rule_env"]), "no env rule")
        leg("build without the libfolders floor -> deny", ctx,
            req(ctx, "5655002F", "SCREEN", input_seq="discovery", build="0ldf1x0001"), False,
            dict(disabled=["rule_build"]), "no build rule")
        with open(os.path.join(tmp, "dispatch", "hold", "nova"), "w") as f:
            f.write("lane.gpunonrender\n")
        leg("direct hold while another lane holds the Nova -> deny", ctx, dict(good, caller="lane.local"), False,
            dict(disabled=["rule_device"]), "no device rule")
        os.remove(os.path.join(tmp, "dispatch", "hold", "nova"))
        leg("title not staged on the requested device -> deny", ctx,
            req(ctx, "5655002F", "SCREEN", input_seq="discovery", device="thor", seconds=300), False,
            dict(disabled=["rule_staged"]), "no staging rule")

        print("== token and log")
        lctx = rebuilt(tmp)
        d = G.admit(lctx, req(lctx, "5655002F", "SCREEN", input_seq="discovery"), shadow=False)
        ok, why = G.verify_token(lctx, d.token, "5655002F", "nova")
        bad, why2 = G.verify_token(lctx, d.token, "5655002F", "thor")
        forged = d.token[:-4] + ("0000" if not d.token.endswith("0000") else "1111")
        fok, why3 = G.verify_token(lctx, forged, "5655002F", "nova")
        check("token verifies for its title+device, not another device, not forged", ok and not bad and not fok,
              False, "%s / %s / %s" % (why[:40], why2[:40], why3[:40]))
        log = TR.read_tsv(lctx.log)
        G.admit(lctx, req(lctx, "54430001", "PLAYABLE_ATTEMPT"), shadow=True)
        log2 = TR.read_tsv(lctx.log)
        check("every decision is a log row; shadow mode logs SHADOW-DENY", len(log) == 1 and log[0]["decision"] == "ALLOW"
              and len(log2) == 2 and log2[1]["decision"] == "SHADOW-DENY" and "BELOW_BAR" in log2[1]["reasons"], False,
              "%d -> %d rows, last %s" % (len(log), len(log2), log2[-1]["decision"]))
        os.remove(lctx.log)
        mode_default = lctx.mode()
        check("mode is shadow until lane.local writes enforce", mode_default == "shadow", False, mode_default)

        print("== call sites: request.sh (admit-request) and hold.sh take (hold-check)")
        rq = os.path.join(tmp, "req.json")

        def admit_request(mode, title_id, cls, extra=()):
            with open(rq, "w") as f:
                json.dump({"id": "x", "requester": "lane.pathfind", "title": "x.iso", "title_id": title_id,
                           "device": "nova", "ref": BUILD, "seconds": 900, "env": [], "route_name": ""}, f)
            with open(lctx.modefile, "w") as f:
                f.write(mode)
            argv = ["admit-request", rq, "--root", tmp, "--no-refresh", "--class", cls,
                    "--because", "verdict:wt/pathfind/docs/lanes/pathfind/runs", "--valid-end", "valid-verdict"] + list(extra)
            real = G.Ctx
            G.Ctx = lambda root, readback=None: FakeCtx(root, now=NOW)
            try:
                with contextlib.redirect_stderr(open(os.devnull, "w")):
                    rc = G.main(argv)
            finally:
                G.Ctx = real
            return rc, json.load(open(rq)).get("gate_token")
        lctx = rebuilt(tmp)
        rc_sh, _ = admit_request("shadow", "54430001", "PLAYABLE_ATTEMPT", ["--input-seq", seq(lctx, "54430001")])
        rc_en, _ = admit_request("enforce", "54430001", "PLAYABLE_ATTEMPT", ["--input-seq", seq(lctx, "54430001")])
        rc_ok, tok = admit_request("enforce", "5655002F", "SCREEN", ["--input-seq", "discovery"])
        check("admit-request: DOA3 queued in shadow (exit 0), refused in enforce (exit 2)",
              rc_sh == 0 and rc_en == 2, rc_sh == rc_en, "shadow %s, enforce %s" % (rc_sh, rc_en))
        check("admit-request: an allowed SCREEN writes gate_token into the request", rc_ok == 0 and bool(tok), False,
              (tok or "")[:40])

        def admit_iso(title, title_id):
            with open(rq, "w") as f:
                json.dump({"id": "x", "requester": "lane.pathfind", "title": title, "title_id": title_id,
                           "device": "nova", "ref": BUILD, "seconds": 900, "env": [], "route_name": ""}, f)
            real = G.Ctx
            G.Ctx = lambda root, readback=None: FakeCtx(root, now=NOW)
            try:
                with contextlib.redirect_stderr(open(os.devnull, "w")):
                    return G.main(["admit-request", rq, "--root", tmp, "--no-refresh", "--class", "SCREEN",
                                   "--because", "issue:#433", "--valid-end", "valid-verdict", "--input-seq", "discovery"])
            finally:
                G.Ctx = real
        with open(lctx.modefile, "w") as f:
            f.write("enforce")
        rc_match = admit_iso("5655002F-Fight_Club.xiso.iso", "5655002F")
        rc_stale = admit_iso("5655002F-Fight_Club.xiso.iso", "54540082")
        real_shape = G.rule_request_shape

        def shape_without_conflict(c, r, row, d):     # mutant: trust whichever id the request names
            return real_shape(c, dict(r, _id_conflict=""), row, d)
        G.RULES[G.RULES.index(real_shape)] = shape_without_conflict
        rc_mut = admit_iso("5655002F-Fight_Club.xiso.iso", "54540082")
        G.RULES[G.RULES.index(shape_without_conflict)] = real_shape
        check("admit-request: a stale request title_id (GTA's 54540082 on another ISO) -> deny",
              rc_match == 0 and rc_stale == 2, rc_mut == 2, "match %s, stale %s, mutant %s" % (rc_match, rc_stale, rc_mut))
        hc = lambda tag, why: G.hold_check(FakeCtx(tmp, now=NOW), "nova", tag, why)   # noqa: E731
        with open(lctx.modefile, "w") as f:
            f.write("enforce")
        r_untok = hc("lane.pathfind", "pathfind 54430001 one run, 600 s hold")
        r_exempt = hc("hostupd-123", "host update window")
        G.admit(FakeCtx(tmp, now=NOW), dict(req(lctx, "5655002F", "SCREEN", input_seq="discovery"), caller="lane.pathfind"),
                shadow=False)
        r_tok = hc("lane.pathfind", "pathfind 5655002F first run")
        r_other = hc("lane.pathfind", "pathfind 54430001 one run")
        with open(lctx.modefile, "w") as f:
            f.write("shadow")
        r_shadow = hc("lane.pathfind", "pathfind 54430001 one run, 600 s hold")
        log3 = TR.read_tsv(lctx.log)
        check("hold-check (enforce): no token -> 3; token for the title -> 0; token for another title -> 3; "
              "host hold exempt", (r_untok, r_tok, r_other, r_exempt) == (3, 0, 3, 0), r_untok == 0,
              "untok %s tok %s other %s exempt %s" % (r_untok, r_tok, r_other, r_exempt))
        check("hold-check (shadow): refuses nothing, logs SHADOW-HOLD-UNGATED",
              r_shadow == 0 and log3[-1]["decision"] == "SHADOW-HOLD-UNGATED", r_shadow != 0,
              log3[-1]["decision"])
        forge_legs()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    red =[n for n, s in RESULTS if s != "GREEN"]
    print("\n%d legs, %d green, %d red" % (len(RESULTS), len(RESULTS) - len(red), len(red)))
    for n in red:
        print("RED: " + n)
    return 1 if red else 0


if __name__ == "__main__":
    sys.exit(main())
