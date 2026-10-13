#!/usr/bin/env python3
"""
Selftest for the forge-ahead jam added in docs/lanes/forgealloc1013/idlewatch.py.new (#433).

idlewatch.py is a host-tools script, not a docs/testing/jobs/*.sh one: it has no __main__ guard
and runs every jam check as top-level code against hardcoded /home/justin/hakux-work paths, so it
can't be imported for a unit test (import would immediately make live systemctl/forge/network
calls) and doesn't fit selftest.sh's $T-fixture harness (built for jobs/*.sh's relocatable paths).

Instead this pulls just the three pure, self-contained nodes the new jam adds -- the
FORGE_AHEAD_RE assignment and the _latest_run_lines/_forge_ahead_in defs, none of which touch W,
the forge API, or any other part of the file -- out of the staged idlewatch.py.new via ast, execs
them into a throwaway namespace, and feeds them fixture files. This exercises the actual detection
logic fires/doesn't-fire, not a reimplementation of it. The per-number forge lookup (urllib calls
for user/branch) is deliberately not covered here -- it needs a live forge, exercised instead by a
manual curl against http://127.0.0.1:3330 (see NOTES.md), and its failure modes are already
caught (any exception/404 just falls back to "?", never raises).
"""
import ast, os, sys, tempfile, textwrap

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "idlewatch.py.new")

WANTED = {"FORGE_AHEAD_RE", "_latest_run_lines", "_forge_ahead_in"}

def load_detector():
    tree = ast.parse(open(SRC).read(), filename=SRC)
    keep = []
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id in WANTED for t in node.targets
        ):
            keep.append(node)
        elif isinstance(node, ast.FunctionDef) and node.name in WANTED:
            keep.append(node)
    found = set()
    for node in keep:
        if isinstance(node, ast.FunctionDef):
            found.add(node.name)
        else:
            found.update(t.id for t in node.targets if isinstance(t, ast.Name))
    missing = WANTED - found
    if missing:
        raise AssertionError("idlewatch.py.new is missing expected node(s): %s" % missing)
    mod = ast.Module(body=keep, type_ignores=[])
    ns = {"re": __import__("re"), "os": __import__("os")}
    exec(compile(mod, SRC, "exec"), ns)
    return ns

passed = failed = 0

def check(label, cond):
    global passed, failed
    if cond:
        passed += 1
    else:
        failed += 1
        print("FAIL:", label)

ns = load_detector()
_forge_ahead_in = ns["_forge_ahead_in"]
_latest_run_lines = ns["_latest_run_lines"]

# --- _forge_ahead_in: direct line-list tests, no filesystem ---

check(
    "fires on a bare REFUSED-shaped line",
    _forge_ahead_in(["lane/x: FAILED: allocator refused: REFUSED: forge is ahead of GitHub "
                      "(forge max #972, GitHub max #968) -- backfill is pending, or something was "
                      "made directly on the forge. Nothing spent."])
    == (972, 968),
)
check(
    "picks the LAST match when several lines are given (most recent wins)",
    _forge_ahead_in([
        "lane/a: REFUSED: forge is ahead of GitHub (forge max #970, GitHub max #968) -- ...",
        "lane/b: REFUSED: forge is ahead of GitHub (forge max #972, GitHub max #968) -- ...",
    ])
    == (972, 968),
)
check("no match on lines with no such text", _forge_ahead_in(["EXECUTED: 3 lane branches ... 0 error(s)"]) is None)
check("no match on an empty list", _forge_ahead_in([]) is None)

# --- _latest_run_lines: run-boundary bounded window, with real fixture files ---

with tempfile.TemporaryDirectory() as t:
    prsync = os.path.join(t, "prsync.log")

    # A resolved-then-broken-again history. Real prsync.log prints a run's FAILED lines BEFORE
    # that run's own EXECUTED: summary. Run A (two runs back) hit an old forge-ahead; run B
    # resolved it; run C (the latest, most recent EXECUTED:) hit a fresh one. The window is
    # "everything since the run before last" (from just after the second-to-last marker to EOF),
    # which always includes the newest run's own lines -- an older, already-resolved run's lines
    # must not leak in.
    open(prsync, "w").write(textwrap.dedent("""\
        lane/old: FAILED: allocator refused: REFUSED: forge is ahead of GitHub (forge max #900, GitHub max #899)
        EXECUTED: 1 lane branches with PR.md; 1 open forge PRs before this run; 1 error(s)
        lane/mid: opening a forge PR through the allocator -> #901
        EXECUTED: 1 lane branches with PR.md; 2 open forge PRs before this run; 0 error(s)
        lane/new: FAILED: allocator refused: REFUSED: forge is ahead of GitHub (forge max #972, GitHub max #968)
        EXECUTED: 1 lane branches with PR.md; 2 open forge PRs before this run; 1 error(s)
        """))
    latest = _latest_run_lines(prsync, "EXECUTED:")
    check(
        "latest-run window excludes the older, already-resolved run's lines",
        "lane/old: FAILED: allocator refused: REFUSED: forge is ahead of GitHub (forge max #900, GitHub max #899)"
        not in latest,
    )
    check(
        "latest-run window includes the newest run's own failure line",
        "lane/new: FAILED: allocator refused: REFUSED: forge is ahead of GitHub (forge max #972, GitHub max #968)"
        in latest,
    )
    check("fires: fresh forge-ahead in the latest run", _forge_ahead_in(latest) == (972, 968))

    # Resolved case: the LATEST run has no forge-ahead line at all (even though an older run did)
    # -- must not fire, proving a stale/superseded REFUSED doesn't cause a permanent false jam.
    resolved = os.path.join(t, "prsync_resolved.log")
    open(resolved, "w").write(textwrap.dedent("""\
        lane/old: FAILED: allocator refused: REFUSED: forge is ahead of GitHub (forge max #900, GitHub max #899)
        EXECUTED: 1 lane branches with PR.md; 1 open forge PRs before this run; 1 error(s)
        lane/fixed: opening a forge PR through the allocator -> #901
        EXECUTED: 1 lane branches with PR.md; 2 open forge PRs before this run; 0 error(s)
        """))
    latest2 = _latest_run_lines(resolved, "EXECUTED:")
    check("doesn't fire: latest run has no forge-ahead line", _forge_ahead_in(latest2) is None)

    # Fewer than 2 markers: falls back to a flat tail window instead of an empty/wrong slice.
    one_marker = os.path.join(t, "prsync_one.log")
    open(one_marker, "w").write(
        "lane/new: REFUSED: forge is ahead of GitHub (forge max #972, GitHub max #968)\n"
        "EXECUTED: 1 lane branches with PR.md; 1 open forge PRs before this run; 1 error(s)\n"
    )
    check(
        "fewer than 2 markers: falls back to a tail window that still contains the line",
        _forge_ahead_in(_latest_run_lines(one_marker, "EXECUTED:")) == (972, 968),
    )

    check("missing file: empty list, no exception", _latest_run_lines(os.path.join(t, "nope.log"), "EXECUTED:") == [])

# --- lanelocal-log.md shape (issue_sync's REFUSED embedding, no EXECUTED: markers at all) ---

lanelocal_lines = textwrap.dedent("""\
    ## Mon Oct 13 09:00:00 PDT 2026 [issue_sync]
    - issue_sync: lane.foo NEW ISSUE 'something' not filed: REFUSED: forge is ahead of GitHub (forge max #976, GitHub max #972) -- backfill is pending, or something was made directly on the forge. Nothing spent.
    """).splitlines()
check("fires on the issue_sync-shaped embedding (plain tail window, no markers needed)",
      _forge_ahead_in(lanelocal_lines) == (976, 972))

print("forge_alloc_selftest: %d passed, %d failed" % (passed, failed))
sys.exit(1 if failed else 0)
