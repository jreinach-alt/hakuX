# Sourced by ../selftest.sh with the harness already built: $T, $HERE, $REPO,
# $TESTING, $DISPATCH_DIR, the shims on PATH, ok/bad/check. Not executable, no
# shebang, no exit -- `fail` is shared and is the run's verdict.
#
# THE COVERAGE GATE OVER REST, AND THE PRINT THAT USED TO HIDE THE ANSWER.
#
# `gh issue list` and `gh pr list` are GraphQL. A Claude Code cloud session's
# proxy refuses GraphQL wholesale:
#
#     HTTP 403: GitHub GraphQL is not available from Claude Code sessions;
#     use the REST API (gh api repos/{owner}/{repo}/...)
#
# So check_coverage.py took its fail-open branch on EVERY invocation there --
# printed `coverage NOT CHECKED`, exited 0 -- and preflight.sh printed `ok`
# over it, because `sed -n 1p` of the log shows the provenance line and never
# the verdict. A gate that reported success without doing the work, with the
# sentence admitting it swallowed. Found by lane.remote on PR #162,
# 2026-09-19, from the container where it bites hardest.
#
# 98 AND NOT 101, WHICH IS WHERE THIS STARTED. selftest.sh's fragment loader
# matches `[0-9][0-9]-*.sh` -- exactly two digits -- and anything else hits its
# `*)` arm and `exit 2`s the entire run rather than being skipped. A
# three-digit fragment does not fail quietly; it takes the whole self-test with
# it. Duplicate numbers are fine and already in use (55, 86, 97 each appear
# twice), so the concern name is what distinguishes this from
# 98-audit-outlet.sh. This fragment builds a board and a gh of its own under
# $CR and depends on no other fragment, so its position is free.
#
# EVERY CHECK HERE IS ON THE OUTPUT WORDS, NEVER ON THE EXIT CODE.
# check_coverage.py exits 0 both when it checked and when it failed open --
# that is the whole defect -- so an exit-code assertion passes against the
# broken version for free.
#
# AND EVERY INVARIANT HAS A MUTANT THAT TRIPS IT, built here rather than
# reasoned about. Three of the four mutants are one-line edits to a copy of
# gh_rest.py; the fourth restores preflight.sh's `sed -n 1p`. A check that
# cannot go red tests nothing.

echo "== the coverage gate over REST, and a fail-open that says so"
CR="$T/covrest"; CRB="$CR/board"; CRP="$CR/pages"; CRD="$CR/dispatch"
mkdir -p "$CRB" "$CR/bin" "$CRP" "$CRD" "$CR/mut-nofilter" "$CR/mut-page1" \
         "$CR/mut-graphql" "$CR/mut-pf/docs/testing"
cp "$TESTING/check_coverage.py" "$TESTING/board_files.py" "$TESTING/gh_rest.py" "$CRB/"
check "the coverage modules were copied, gh_rest.py among them" \
    bash -c '[ -s "$1/check_coverage.py" ] && [ -s "$1/board_files.py" ] && [ -s "$1/gh_rest.py" ]' _ "$CRB"

# ------------------------------------------------------------------ the pages
# $CR_WORLD picks which canned response set the shim serves, and the page
# number comes out of the query string the way the real endpoint reads it.
#
# THE `small` WORLD CARRIES A PULL REQUEST, which is the entire trap: REST's
# /issues returns pull requests alongside issues and a PR is marked only by
# carrying a `pull_request` key. Measured against this repository 2026-09-19:
# 32 rows back, 9 of them PRs, 23 genuine issues -- the same 23 `gh issue
# list` reported. A shim that omitted PRs would let an unfiltered reader pass
# here and fail on GitHub, so this one includes one.
python3 - "$CRP" <<'PY'
import json, os, sys
d = sys.argv[1]
small = [
    {"number": 1, "title": "a blocked issue"},
    {"number": 2, "title": "another blocked issue"},
    # A PULL REQUEST, in the shape GitHub sends it: same envelope as an issue,
    # plus the key. Its number is nowhere in the tracker, so anything that
    # counts it as an issue fails the coverage gate by name.
    {"number": 900, "title": "lane/somelane: a pull request, not an issue",
     "pull_request": {"url": "https://api.github.com/repos/x/y/pulls/900",
                      "html_url": "https://github.com/x/y/pull/900"}},
]
json.dump(small, open(os.path.join(d, "small-1.json"), "w"))
json.dump([], open(os.path.join(d, "small-2.json"), "w"))

# EXACTLY per_page ROWS ON PAGE 1, which is what makes a short read invisible:
# a reader that stops after one page gets a complete-looking 100 and never
# learns that #101 exists. Every row on page 1 is covered; the only uncovered
# issue in the whole fixture is the one on page 2.
json.dump([{"number": n, "title": "page one issue %d" % n}
           for n in range(1, 101)], open(os.path.join(d, "paged-1.json"), "w"))
json.dump([{"number": 101, "title": "THE SECOND PAGE, covered by nothing"}],
          open(os.path.join(d, "paged-2.json"), "w"))
json.dump([], open(os.path.join(d, "paged-3.json"), "w"))
PY

cat > "$CR/bin/gh" <<'EOF'
#!/usr/bin/env bash
# A gh that behaves like the Claude Code cloud proxy: REST answers, GraphQL
# is refused with the proxy's own words. $CR_WORLD picks the canned pages;
# CR_OFFLINE=1 makes even REST fail, which is the ordinary network blip.
case "$1 $2" in
    "issue list"|"pr list")
        echo "HTTP 403: GitHub GraphQL is not available from Claude Code sessions; use the REST API (gh api repos/{owner}/{repo}/...)" >&2
        exit 1 ;;
esac
[ -n "${CR_OFFLINE:-}" ] && {
    echo "dial tcp: lookup api.github.com: no such host" >&2; exit 1; }
page=1
case "$*" in *"page=2"*) page=2 ;; *"page=3"*) page=3 ;; esac
case "$*" in
    *"/issues?"*) cat "$CR_PAGES/$CR_WORLD-$page.json" ;;
    *"/pulls?"*)  echo '[]' ;;
    *) exit 0 ;;
esac
EOF
chmod +x "$CR/bin/gh"
export CR_PAGES="$CRP"

crboard() {   # <first issue number> <last>: a tracker row per issue, all blocked
    python3 - "$CRB" "$1" "$2" <<'PY'
import os, sys
bd, lo, hi = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
open(os.path.join(bd, "territory.toml"), "w").write('[free]\nnote = "x"\n')
open(os.path.join(bd, "nv2a_issues.toml"), "w").write("\n".join(
    '[issue.%d]\ntitle = "issue %d"\nstatus = "open"\nstatus_note = "n"\n'
    'blocked_on = "Blocked on real Xbox hardware, which nobody has."\n' % (n, n)
    for n in range(lo, hi + 1)))
PY
}
cov() {   # <module dir> -- the rest comes from the environment
    # THE MUTANT DIRS GET THE CURRENT BOARD, NOT THE ONE THAT EXISTED WHEN
    # THEY WERE BUILT. board_files.py reads the two toml files from beside the
    # script it was imported by, so a mutant run against a stale (or absent)
    # board would be a different experiment from the one it is compared with.
    [ "$1" = "$CRB" ] || cp "$CRB/territory.toml" "$CRB/nv2a_issues.toml" "$1/"
    # HAKUX_TIP is blanked so commits_behind() cannot resolve a ref and stays
    # quiet: the stale-checkout banner is orthogonal to everything here, and
    # it would ride along on every line these checks read.
    env PATH="$CR/bin:$PATH" HAKUX_BOARD_REF= HAKUX_REPO=example/hakux \
        DISPATCH_DIR="$CRD" HAKUX_TIP= python3 "$1/check_coverage.py" 2>&1
}
# The mutants: a copy of the board dir with one line of gh_rest.py changed.
mutant() {   # <dir> <python-expression-old> <new>
    cp "$CRB"/*.py "$1/"
    python3 - "$1/gh_rest.py" "$2" "$3" <<'PY'
import sys
p, old, new = sys.argv[1], sys.argv[2], sys.argv[3]
s = open(p).read()
assert s.count(old) == 1, "mutation site %r appears %d times" % (old, s.count(old))
open(p, "w").write(s.replace(old, new))
PY
}
# DROP THE PULL-REQUEST FILTER.
mutant "$CR/mut-nofilter" 'if r.get("pull_request") is None' 'if True'
# READ ONLY THE FIRST PAGE -- and the mutation site matters. Capping the loop
# at one iteration (`range(1, 2)`) does NOT reproduce the bug: page 1 is
# exactly per_page rows, so the short-page return never fires and the loop
# falls out into the "more than N rows, refusing to report a truncated list"
# error. That is the real code refusing to truncate through a second door,
# which is worth knowing and is not what this mutant is for. The bug being
# pinned is RETURNING what one page held as though it were the whole list, so
# mutate the exit condition.
mutant "$CR/mut-page1" 'if len(batch) < per_page:' 'if True:'
# ASK OVER GRAPHQL AGAIN, which is what the file did before this change.
mutant "$CR/mut-graphql" '["gh", "api", path]' \
    '["gh", "issue", "list", "--repo", "example/hakux", "--json", "number,title"]'
check "the three gh_rest mutants were built" \
    bash -c '[ -s "$1/gh_rest.py" ] && [ -s "$2/gh_rest.py" ] && [ -s "$3/gh_rest.py" ]' \
    _ "$CR/mut-nofilter" "$CR/mut-page1" "$CR/mut-graphql"

# -------------------------------------------- 1. the gate RUNS where it used to fail open
export CR_WORLD=small
crboard 1 2
out=$(cov "$CRB")
check "the gate RUNS against a GraphQL-refusing gh, because it asks over REST" \
    grep -q "^coverage ok (2 open:" <<< "$out"
# THE FIXTURE'S OWN SANITY CHECK. "It ran" is satisfied for free by a shim
# that answers everything; assert the shim really does refuse GraphQL, by
# running a copy that asks that way and watching it fail open.
out_g=$(cov "$CR/mut-graphql")
check "...and the shim really does refuse GraphQL, so the line above is not vacuous" \
    grep -q "^coverage NOT CHECKED" <<< "$out_g"
check "...naming the proxy's own reason, not a generic failure" \
    grep -q "GraphQL is not available from Claude Code sessions" <<< "$out_g"

# ------------------------------------------------------- 2. an open PR is not an issue
check "an open PULL REQUEST in the /issues response is not counted as an issue" \
    grep -q "^coverage ok (2 open:" <<< "$out"
check "...and the filter is reported, not assumed: 1 pull request dropped" \
    grep -q "1 pull request(s) dropped from the /issues response" <<< "$out"
out_f=$(cov "$CR/mut-nofilter")
check "MUTANT without the filter counts the PR and goes red" \
    grep -q "FAIL: 1 open issue(s) with neither a lane nor a blocker" <<< "$out_f"
check "...naming #900, the pull request, by number" \
    grep -q "^  #900 " <<< "$out_f"

# ----------------------------------------------------- 3. the second page is not dropped
export CR_WORLD=paged
crboard 1 100
out_p=$(cov "$CRB")
check "the issue on PAGE TWO is read -- the gate fails on it" \
    grep -q "FAIL: 1 open issue(s) with neither a lane nor a blocker" <<< "$out_p"
check "...and it is #101, the row that only exists on the second page" \
    grep -q "^  #101 " <<< "$out_p"
out_1=$(cov "$CR/mut-page1")
# THE MUTANT GOES GREEN HERE AND THE REAL CODE GOES RED, which is the strongest
# form this check could take: a silently truncating reader cannot fake it.
check "MUTANT reading one page reports a clean board over the row it never saw" \
    grep -q "^coverage ok (100 open:" <<< "$out_1"
check "...and never mentions #101 at all" \
    bash -c '! grep -q "#101" <<< "$1"' _ "$out_1"

# ------------------------------------------ 4. a gate that cannot reach GitHub says so
export CR_WORLD=small CR_OFFLINE=1
crboard 1 2
out_o=$(cov "$CRB")
check "an unreachable GitHub prints THE GATE DID NOT RUN, not a bare NOT CHECKED" \
    grep -q "^coverage NOT CHECKED -- THE GATE DID NOT RUN:" <<< "$out_o"
check "...with the reason on the same line, where preflight prints it" \
    grep -q "no such host" <<< "$out_o"
check "...and it says in words that its exit 0 is not a pass" \
    grep -q "an exit code of 0 from here therefore means .not checked" <<< "$out_o"
# THE FAIL-OPEN ITSELF, PINNED IN BOTH DIRECTIONS. Everything above is about
# making the fail-open visible; this is the check that it is still a fail-open.
# A network blip must not make the repository unpushable.
env PATH="$CR/bin:$PATH" HAKUX_BOARD_REF= HAKUX_REPO=example/hakux \
    DISPATCH_DIR="$CRD" HAKUX_TIP= CR_OFFLINE=1 CR_WORLD=small \
    python3 "$CRB/check_coverage.py" >/dev/null 2>&1
cr_rc=$?
check "...and it STILL EXITS 0: the fail-open is preserved, only made audible" \
    [ "$cr_rc" -eq 0 ]
unset CR_OFFLINE

# --------------------------------- 5. preflight prints the verdict, not line 1
# THE REAL preflight.sh, through its --render-coverage mode, against logs in
# the exact shape check_coverage.py writes: a provenance line FIRST, the
# verdict SECOND. That ordering is the whole defect -- `sed -n 1p` showed the
# operator where the board was read from and nothing about what was checked.
printf 'board read from: territory.toml <- origin/board, nv2a_issues.toml <- origin/board\ncoverage ok (23 open: 0 AVAILABLE, 23 blocked, 13 owned by a lane)\n' \
    > "$CR/log-ok"
printf 'board read from: territory.toml <- working tree, nv2a_issues.toml <- working tree\ncoverage NOT CHECKED -- THE GATE DID NOT RUN: HTTP 403: GitHub GraphQL is not available from Claude Code sessions\n' \
    > "$CR/log-unchecked"
# The mutant restores the single expression this change replaced. It
# reproduces BOTH halves of the defect from one edit, which is the evidence
# that the two halves were one bug.
python3 - "$TESTING/preflight.sh" "$CR/mut-pf/docs/testing/preflight.sh" <<'PY'
import sys
src, dst = sys.argv[1], sys.argv[2]
s = open(src).read()
old = '''v=$(grep -m1 '^coverage ' "$1" 2>/dev/null || true)'''
new = '''v=$(sed -n 1p "$1" 2>/dev/null)'''
# EXACTLY ONE SITE, asserted rather than hoped: a mutation that silently
# matched nothing would leave a "mutant" identical to the real file, and both
# of the checks below would then pass by testing the same code twice.
assert s.count(old) == 1, "mutation site appears %d times" % s.count(old)
open(dst, "w").write(s.replace(old, new))
PY
check "the preflight mutant really differs from the file it was cut from" \
    bash -c '! cmp -s "$1" "$2"' _ "$TESTING/preflight.sh" "$CR/mut-pf/docs/testing/preflight.sh"

pf_ok=$(bash "$TESTING/preflight.sh" --render-coverage "$CR/log-ok" 2>&1)
check "a real verdict renders as ok" grep -qE '^coverage +ok$' <<< "$pf_ok"
check "...and the line shown is the VERDICT, not the provenance line" \
    grep -q "^  coverage ok (23 open:" <<< "$pf_ok"
check "...so 'board read from' is not what the operator is handed" \
    bash -c '! grep -q "board read from" <<< "$1"' _ "$pf_ok"

pf_un=$(bash "$TESTING/preflight.sh" --render-coverage "$CR/log-unchecked" 2>&1)
check "a fail-open renders as DID NOT RUN" grep -qE '^coverage +DID NOT RUN$' <<< "$pf_un"
check "...the word ok appears nowhere on that verdict line" \
    bash -c '! grep -qE "^coverage +ok$" <<< "$1"' _ "$pf_un"
check "...and the operator is shown the 403 that caused it" \
    grep -q "GraphQL is not available from Claude Code sessions" <<< "$pf_un"

mut_un=$(bash "$CR/mut-pf/docs/testing/preflight.sh" --render-coverage "$CR/log-unchecked" 2>&1)
check "MUTANT reading line 1 calls that same fail-open a pass" \
    grep -qE '^coverage +ok$' <<< "$mut_un"
mut_ok=$(bash "$CR/mut-pf/docs/testing/preflight.sh" --render-coverage "$CR/log-ok" 2>&1)
check "...and on a real verdict it hands over the provenance line instead" \
    grep -q "^  board read from:" <<< "$mut_ok"
