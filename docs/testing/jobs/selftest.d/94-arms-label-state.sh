# Sourced by ../selftest.sh with the harness already built: $T, $HERE, $REPO,
# the shims on PATH, ok/bad/check, and the live prediction's fixtures. Not
# executable, no shebang, no exit -- `fail` is shared and is the run's verdict.
#
# arms.sh: the PR's label is a function of ALL its verdicts, not of the last
# one judged.
#
# Builds its own pairs/ and judged/ fixtures -- PR #102's four verdicts,
# exactly -- and clears $WORK/arms/{pairs,judged} first, so it must run after
# every fragment that reads what arms.sh left (10..60) and after 92, which
# reads 40's refusal marker. It leaves those two directories holding its own
# fixtures, so a later fragment must not assume the earlier ones survive.
#
# It drives the judge loop through a STUB ab_compare.py: the real one needs two
# scored result directories with progress-log proof, and what is under test is
# the labelling, not the comparison. The stub is reached by running arms.sh
# through a symlink tree whose ab_compare.py is the only real file -- the
# script derives $T from its own BASH_SOURCE. The tree is swapped, never the
# path: a falsification run that edits the real file in place leaves it there.

echo "== arms.sh: the PR's label is a function of ALL its verdicts"

# ------------------------------------------------------------ the stub trunk
STUBT="$T/stub-testing"; mkdir -p "$STUBT"
ln -sfn "$TESTING/jobs" "$STUBT/jobs"            # arms.sh, gh-label.sh, status.sh: the real ones
ln -sfn "$TESTING/request.sh" "$STUBT/request.sh"
cat > "$STUBT/ab_compare.py" <<'EOF'
import os, sys
print("VERDICT: %s" % os.environ.get("SELFTEST_VERDICT", "PASS -- all 13 registered checks hold."))
EOF
ARMS="$STUBT/jobs/arms.sh"
# Nothing may queue while this runs: the fixtures below are the whole corpus,
# and a fresh pair would be a fifth verdict nobody registered.
export ARMS_MAX_PAIRS_PER_TICK=0

# ------------------------------------------------------------- the fixtures
# PR #102 as it stood at 2026-09-19T10:03Z. The gh shim answers `pr list --head
# lane/selftest` with 102, so pr_for() resolves these to a PR and the label
# path runs for real.
arm() {   # <nick> <issue> <registered_utc> <verdict|"">  -> sets $sha
    local nick=$1 issue=$2 reg=$3 verdict=$4 exp="$HAKUX_WORK/arms/expect/$1.json"
    python3 - "$exp" "$reg" "$issue" <<'PY'
import json, sys
p, reg, issue = sys.argv[1:]
json.dump({"registered_utc": reg, "who": "lane.selftest", "issue": issue,
           "a_ref": "aaaaaaa", "b_ref": "bbbbbbb"}, open(p, "w"), indent=2)
PY
    sha=$(sha256sum "$exp" | cut -d' ' -f1)
    python3 - "$HAKUX_WORK/arms/pairs/$sha.json" "$sha" "$exp" "$issue" "$nick" "$reg" <<'PY'
import json, sys
p, sha, exp, issue, nick, reg = sys.argv[1:]
json.dump({"sha": sha, "id_a": nick + "-a", "id_b": nick + "-b", "expect": exp,
           "source": "lane/selftest:docs/testing/predictions/%s.json" % nick,
           "who": "lane.selftest", "issue": issue, "a_ref": "aaaaaaa", "b_ref": "bbbbbbb",
           "suites": "Blend surface", "queued_utc": reg}, open(p, "w"), indent=2)
PY
    mkdir -p "$DISPATCH_DIR/results/$nick-a" "$DISPATCH_DIR/results/$nick-b"
    : > "$DISPATCH_DIR/results/$nick-a/DONE"; : > "$DISPATCH_DIR/results/$nick-b/DONE"
    [ -n "$verdict" ] && echo "VERDICT: $verdict" > "$HAKUX_WORK/arms/judged/$sha"
    return 0
}
rm -f "$HAKUX_WORK"/arms/pairs/* "$HAKUX_WORK"/arms/judged/*
mkdir -p "$HAKUX_WORK/arms/expect"
arm issue89-clear-pad-alpha-shape        89 2026-09-19T06:00:00Z "PASS -- all 44 registered checks hold."
arm issue88-vk-same-offset-colour-wins   88 2026-09-19T07:00:00Z "FAIL -- 2 of 13 checks violated:"
arm issue91-swap-solo-classification     91 2026-09-19T08:00:00Z "FAIL -- 1 of 1 checks violated:"
arm issue91-decline-frame-attribution    91 2026-09-19T09:00:00Z ""    # the one judged at 10:03Z
live=$sha

# --------------------------------------------- the defect, end to end
# The label the job actually applies when #91's replacement arm comes back
# PASS. SELFTEST_LABELS says `regressed` IS on the PR: without it label_rm
# declines to DELETE a label that is absent and the "did not clear it" check
# below would pass against the broken code for free.
: > "$SELFTEST_GH_LOG"
( export SELFTEST_VERDICT="PASS -- all 13 registered checks hold." SELFTEST_LABELS="regressed"
  bash "$ARMS" ) >/dev/null 2>&1
check "a PASS on one issue does not clear another issue's outstanding FAIL" \
    bash -c '! grep -q "DELETE repos/example/hakux/issues/102/labels/regressed" "$SELFTEST_GH_LOG"'
check "the PR stays labelled regressed while #88's FAIL stands" \
    grep -q 'POST repos/example/hakux/issues/102/labels.*labels\[\]=regressed' "$SELFTEST_GH_LOG"
check "and is not also labelled verified" \
    bash -c '! grep -q "labels\[\]=verified" "$SELFTEST_GH_LOG"'
check "the verdict comment names the FAIL that is still outstanding" \
    grep -q 'issue88-vk-same-offset-colour-wins.*nothing supersedes it' "$HAKUX_WORK/arms/pairs/$live.comment.md"
check "the comment says which verdict superseded #91's FAIL" \
    grep -q 'issue91-swap-solo-classification.*superseded by .issue91-decline-frame-attribution' \
    "$HAKUX_WORK/arms/pairs/$live.comment.md"
check "the decision is on disk beside the verdict, not only in the comment" \
    grep -q '^STATE=regressed' "$HAKUX_WORK/arms/pairs/$live.label.md"

# ---------------------------------------- and it does clear, when it should
# Same PR, once #88 is genuinely answered: a later registration against issue
# 88 that PASSES. Every issue's newest verdict is now a PASS, so `regressed`
# must come off -- a rule that never clears is not a fix, it is a stuck label.
arm issue88-vk-offset-colour-second-look 88 2026-09-19T11:00:00Z "PASS -- all 13 registered checks hold."
rm -f "$HAKUX_WORK/arms/judged/$live"
: > "$SELFTEST_GH_LOG"
( export SELFTEST_VERDICT="PASS -- all 13 registered checks hold." SELFTEST_LABELS="regressed"
  bash "$ARMS" ) >/dev/null 2>&1
check "a FAIL superseded by a later PASS on the same issue does clear regressed" \
    grep -q "DELETE repos/example/hakux/issues/102/labels/regressed" "$SELFTEST_GH_LOG"
check "and the PR is labelled verified" \
    grep -q 'POST repos/example/hakux/issues/102/labels.*labels\[\]=verified' "$SELFTEST_GH_LOG"
check "clearing it is explained by naming the superseding verdict" \
    grep -q 'issue88-vk-same-offset-colour-wins\.json. FAILED, and does not count' \
    "$HAKUX_WORK/arms/pairs/$live.comment.md"

# --------------------------------------------------- the decision, on demand
# `arms.sh state` is the same computation with no device, no gh and no judging
# -- what the board runs to ask why a label is what it is. Everything below
# reads it directly, because the interesting cases are cheap to state and
# expensive to drive a whole tick for.
#
# Every check here runs in THIS shell: `check ... bash -c '... "$ARMS" ...'` in
# the first draft of this file expanded $ARMS in the child, where it is unset,
# so three checks ran `bash state lane/selftest`, read the script from an empty
# stdin and passed on nothing at all. A negation evaluated in a child shell
# over a variable the child does not have is green against anything.
st() { bash "$ARMS" state "${1:-lane/selftest}" 2>&1; }
sha88b=$(sha256sum "$HAKUX_WORK/arms/expect/issue88-vk-offset-colour-second-look.json" | cut -d' ' -f1)
judge_88_second_look() { echo "$1" > "$HAKUX_WORK/arms/judged/$sha88b"; }
check "state reports verified when every issue's newest verdict passes" \
    grep -q '^STATE=verified' <<< "$(st)"
check "state names the branch it was asked about, not the PR" \
    grep -q 'arms.sh state lane/selftest' <<< "$(st)"
if bash "$ARMS" state >/dev/null 2>&1
then bad "state refuses without a branch (it answered for no branch at all)"
else ok  "state refuses without a branch"; fi

# AN ERROR SUPERSEDES NOTHING. An arm that failed to build is not a verdict:
# it neither sets a label nor answers the FAIL it was registered to answer.
# Without this an errored or unjudged re-registration silently clears a
# regression, which is the original defect wearing a different hat.
judge_88_second_look ERROR
check "an ERRORed later arm does not supersede the FAIL it was meant to answer" \
    grep -q '^STATE=regressed' <<< "$(st)"
judge_88_second_look "VERDICT: UNJUDGED -- nothing got worse, but no registered check bound."
check "an UNJUDGED later arm does not either" \
    grep -q '^STATE=regressed' <<< "$(st)"
judge_88_second_look "VERDICT: PASS -- all 13 registered checks hold."
check "a PASSing later arm does supersede it, so the rule is not vacuous" \
    grep -q '^STATE=verified' <<< "$(st)"

# A VERDICT ON ANOTHER BRANCH IS ANOTHER PR'S. The branch is the PR's identity
# here -- pr_for() resolves an open PR by head branch -- so a FAIL on
# lane/elsewhere must not pin this one.
python3 - "$HAKUX_WORK/arms/pairs/other.json" <<'PY'
import json, sys
json.dump({"sha": "otherbranchsha", "id_a": "x-a", "id_b": "x-b", "expect": "",
           "source": "lane/elsewhere:docs/testing/predictions/z.json",
           "issue": "88", "queued_utc": "2026-09-19T12:00:00Z"}, open(sys.argv[1], "w"))
PY
echo "VERDICT: FAIL -- 3 of 3 checks violated:" > "$HAKUX_WORK/arms/judged/otherbranchsha"
check "a FAIL on another branch is not this PR's, even on the same issue" \
    grep -q '^STATE=verified' <<< "$(st)"
check "and the other branch reads regressed on its own" \
    grep -q '^STATE=regressed' <<< "$(st lane/elsewhere)"

# A pair that has not been judged at all contributes nothing: the label is
# computed from verdicts, and a queued arm has none.
arm issue92-still-running 92 2026-09-19T13:00:00Z ""
check "an unjudged pair does not appear in the decision" \
    bash -c '! grep -q issue92-still-running <<< "$1"' -- "$(st)"
check "verified and regressed are never both live" \
    bash -c '[ "$1" = verified ] || [ "$1" = regressed ]' -- "$(sed -n '1s/^STATE=//p' <<< "$(st)")"
unset ARMS_MAX_PAIRS_PER_TICK
