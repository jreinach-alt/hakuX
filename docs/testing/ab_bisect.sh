#!/usr/bin/env bash
#
# Find the first commit at which one capture regressed, by binary search over
# an explicit commit list, one dispatcher arm per step.
#
#   ab_bisect.sh --who z16bisect --capture Depth_buffer/z16_Fixed \
#                --good 3d08de796f --bad HEAD \
#                --suites "Depth buffer" --paths hw/xbox/nv2a/pgraph/vk \
#                [--runs 3] [--dry-run]
#
# ## Is this practical? Measured, and yes -- but the device time was never the
# ## expensive part.
#
# From the dispatcher log of 2026-09-12, consecutive request start times give
# the real per-arm cost: a one-suite arm including its build is 2m15s to 2m20s
# (blend48tex-base 17:09:29 -> blend48tex-fix 17:11:47 -> f24-base 17:14:05),
# and a 137-capture two-suite arm is about 5 minutes. The Android build is
# cheap because the ninja tree in android/app/.cxx survives the dispatcher's
# detach-and-checkout, so a step recompiles the translation units the jump
# touched and not the world: the slowest gradle run in the whole day's logs is
# "BUILD SUCCESSFUL in 12s".
#
# 215 first-parent commits touch hw/xbox/nv2a/pgraph/{vk,glsl} since the
# Android port began (2026-01-29; issue #17 counted 139 on 2026-09-08, so the
# range grows by about 19 commits a day). ceil(log2(215)) = 8 steps, so a
# one-suite bisect is 8 arms, about 19 minutes of device time, plus two
# endpoint arms. That is one blend A/B. It is affordable.
#
# What actually makes a bisect expensive here, in order:
#
#   1. **It may converge on nothing.** Issue #17's own first application is
#      the cautionary case: a bisect over the DXT decoder would have run 7-8
#      builds and found no commit, because no commit in that history broke DXT
#      decoding -- the defect was never a regression. So the endpoints are
#      validated before any search, and a range whose ends do not straddle the
#      defect is refused rather than searched.
#
#   2. **The oracle has to be deterministic, and for some captures it is
#      not.** Ten runs of one unchanged binary over Texture border give band 0
#      on 17 of 18 captures but 0,0,0,0,0,146,181,1847,2352,2430,5640 on
#      2D_BorderTex_SZ. A binary search reading that capture once per step
#      takes a wrong turn with probability ~0.5 at every step and converges
#      confidently on a commit chosen by coin flips. So the endpoint check
#      measures the band with --runs, and refuses to search a capture whose
#      band is not zero. Raising --runs does not rescue it: 3 runs of a
#      50/50 capture still mislead often enough to ruin an 8-step search, and
#      the honest move is to fix the nondeterminism first or pick another
#      capture in the same suite.
#
#   3. **It monopolises the shared build tree, not just the device.** The
#      dispatcher builds by detaching /home/justin/hakuX onto each sha and
#      restoring the branch afterwards, and it refuses to build at all if that
#      tree is dirty. Eight steps means eight detach windows over twenty
#      minutes, and anyone committing into one of them commits onto the wrong
#      base -- which is what the dispatcher's DETACHED marker is there to make
#      visible. A bisect is therefore exclusive work, and the brief that
#      launches one has to say so.
#
#   4. **History is not monotone.** Binary search assumes one transition from
#      good to bad. A capture that broke, got fixed and broke again returns
#      *a* boundary, not *the* boundary. The result is reported as "the first
#      commit in this range at which the capture is bad", which is what was
#      actually measured, and the two neighbouring steps are printed so the
#      claim can be read rather than trusted.
#
# Deliberately NOT `git bisect run`. That would put the shared checkout into
# bisect state for the duration, and a killed session would leave it there --
# the same tree three other agents build in. `git rev-list` plus an index is
# the same search with no state to leave behind, and it lets a build failure
# be skipped by moving the index rather than by teaching a bisect script the
# difference between "broken commit" and "bad commit".
set -u

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TREE="${DISPATCH_TREE:-/home/justin/hakuX}"
D="${DISPATCH_DIR:-/home/justin/hakux-work/dispatch}"

WHO=""; CAPTURE=""; GOOD=""; BAD=""; SUITES=""; PATHSPEC=""; RUNS=1
DRY=0; TIMEOUT=3600; ENDPOINT_RUNS=3

while [ $# -gt 0 ]; do
    case "$1" in
        --who) WHO="$2"; shift 2;;
        --capture) CAPTURE="$2"; shift 2;;
        --good) GOOD="$2"; shift 2;;
        --bad) BAD="$2"; shift 2;;
        --suites) SUITES="$2"; shift 2;;
        --paths) PATHSPEC="$2"; shift 2;;
        --runs) RUNS="$2"; shift 2;;
        --endpoint-runs) ENDPOINT_RUNS="$2"; shift 2;;
        --timeout) TIMEOUT="$2"; shift 2;;
        --dry-run) DRY=1; shift;;
        *) echo "unknown option $1" >&2; exit 2;;
    esac
done

fail() { echo "ab_bisect: $*" >&2; exit 2; }
[ -n "$WHO" ] || fail "need --who"
[ -n "$CAPTURE" ] || fail "need --capture SUITE/TEST -- a bisect needs ONE capture as its oracle, because per-capture is the only valid unit"
[ -n "$GOOD" ] || fail "need --good REF (a commit where the capture is known good)"
[ -n "$BAD" ] || fail "need --bad REF"
[ -n "$SUITES" ] || fail "need --suites (the disc; identical at every step by construction)"
case "$CAPTURE" in */*) ;; *) fail "--capture wants SUITE/TEST, e.g. Depth_buffer/z16_Fixed";; esac

gsha=$(git -C "$TREE" rev-parse --short --verify "$GOOD^{commit}" 2>/dev/null) \
    || fail "cannot resolve --good $GOOD in $TREE (the tree the dispatcher builds in)"
bsha=$(git -C "$TREE" rev-parse --short --verify "$BAD^{commit}" 2>/dev/null) \
    || fail "cannot resolve --bad $BAD in $TREE"
git -C "$TREE" merge-base --is-ancestor "$gsha" "$bsha" \
    || fail "$gsha is not an ancestor of $bsha, so there is no range between them"
# Both ends are resolved in the DISPATCH tree, because that is the tree every
# step will be built from. "HEAD" here therefore means its HEAD and not the
# caller's, which for an agent in a worktree is a different commit; say so
# rather than let the two be confused.
case "$GOOD$BAD" in
    *HEAD*) echo "ab_bisect: HEAD resolved in $TREE (good $gsha, bad $bsha);" \
                 "an agent worktree's HEAD is a different commit" >&2;;
esac

# First-parent, so the search walks the integration branch rather than diving
# into side branches whose commits were never built or tested here. The
# pathspec is what makes the range small enough to be worth searching.
mapfile -t RANGE < <(git -C "$TREE" rev-list --first-parent --reverse \
                     "$gsha..$bsha" ${PATHSPEC:+-- $PATHSPEC})
N=${#RANGE[@]}
[ "$N" -gt 0 ] || fail "no commits between $gsha and $bsha${PATHSPEC:+ touching $PATHSPEC}"
STEPS=0; n=$N; while [ "$n" -gt 0 ]; do STEPS=$((STEPS+1)); n=$((n/2)); done

echo "=== bisect ${WHO} ==="
echo "  capture   $CAPTURE"
echo "  good      $gsha  $(git -C "$TREE" log -1 --format='%ad %s' --date=short "$gsha" | cut -c1-60)"
echo "  bad       $bsha  $(git -C "$TREE" log -1 --format='%ad %s' --date=short "$bsha" | cut -c1-60)"
echo "  paths     ${PATHSPEC:-(all)}"
echo "  range     $N commits, so at most $STEPS steps"
echo "  cost      $STEPS steps + 2 endpoint arms, ~2m20s each for a one-suite"
echo "            disc = about $(( (STEPS + 2) * 140 / 60 )) minutes of device time"
echo "  EXCLUSIVE: each step detaches $TREE to build. Nobody else may commit"
echo "            there while this runs."

# ------------------------------------------------------------------ one arm
# Returns the capture's median in MED and its band in BND, or sets SKIP=1 if
# the commit could not be built -- a broken commit is not a bad commit, and
# conflating them is how a bisect blames the wrong change.
MED=0; BND=0; SKIP=0; LASTDIR=""
probe_sha() {
    local sha="$1" runs="$2" tag="$3"
    MED=0; BND=0; SKIP=0
    local q id rd
    q=$(bash "$HERE/request.sh" --who "$WHO-$tag" --ref "$sha" \
            --suites "$SUITES" --runs "$runs" \
            --purpose "bisect $WHO step $tag: does $CAPTURE regress at $sha?") \
        || { SKIP=1; return 0; }
    id="${q##* }"; rd="$D/results/$id"
    local deadline=$(( $(date +%s) + TIMEOUT ))
    while :; do
        [ -f "$rd/DONE" ] && break
        if [ -f "$rd/ERROR" ]; then
            echo "      $sha did not produce a result: $(head -1 "$rd/ERROR")"
            echo "      treating it as unbuildable and skipping it"
            SKIP=1; return 0
        fi
        [ "$(date +%s)" -lt "$deadline" ] || fail "step $tag ($sha) timed out; results in $rd"
        sleep 15
    done
    LASTDIR="$rd"
    local out
    out=$(python3 "$HERE/ab_compare.py" --probe "$rd" --capture "$CAPTURE") || { SKIP=1; return 0; }
    MED=$(echo "$out" | awk '/^median/{print $2}')
    BND=$(echo "$out" | awk '/^band/{print $2}')
    echo "      $sha  median $MED  band $BND  ($rd)"
}

if [ "$DRY" = 1 ]; then
    echo
    echo "--- dry run: the steps it would take, and nothing queued ---"
    lo=0; hi=$((N-1)); step=0
    while [ "$lo" -le "$hi" ]; do
        mid=$(( (lo + hi) / 2 )); step=$((step+1))
        printf '  step %d  index %3d/%d  %s  %s\n' "$step" "$mid" "$N" \
            "${RANGE[$mid]:0:10}" \
            "$(git -C "$TREE" log -1 --format=%s "${RANGE[$mid]}" | cut -c1-52)"
        # Show the left-hand walk; the real walk depends on the measurements.
        hi=$((mid-1))
    done
    echo "  (that is the all-good branch of the search; a bad answer at a step"
    echo "   moves lo instead, same count either way.)"
    echo
    echo "endpoint arms first: $gsha and $bsha at --runs $ENDPOINT_RUNS, to"
    echo "establish that the capture straddles the range AND that its band is 0."
    exit 0
fi

# --------------------------------------------------------- endpoint validation
echo
echo "--- endpoints (this is the check that stops a bisect converging on nothing) ---"
probe_sha "$gsha" "$ENDPOINT_RUNS" "good"
[ "$SKIP" = 0 ] || fail "the good endpoint would not build or score; nothing to search"
gmed=$MED; gband=$BND
probe_sha "$bsha" "$ENDPOINT_RUNS" "bad"
[ "$SKIP" = 0 ] || fail "the bad endpoint would not build or score; nothing to search"
bmed=$MED; bband=$BND

if [ "$gband" != 0 ] || [ "$bband" != 0 ]; then
    fail "$CAPTURE has a nonzero run-to-run band (good $gband, bad $bband) on
       an unchanged binary. A binary search reading it once per step takes a
       wrong turn at every step with that probability and then names a commit
       with confidence. Fix the nondeterminism, or bisect a band-0 capture in
       the same suite."
fi
if [ "$gmed" -ge "$bmed" ]; then
    fail "the endpoints do not straddle a regression: $CAPTURE is $gmed at the
       good end and $bmed at the bad end. This is issue #17's own lesson --
       a bisect over a defect that was never a regression runs eight builds
       and converges on nothing. Establish the regression first."
fi
echo "  straddles: $gmed at $gsha, $bmed at $bsha, band 0 at both. Searching."
THRESH=$(( (gmed + bmed) / 2 ))
echo "  a step counts as BAD when the capture is >= $THRESH"

# ------------------------------------------------------------------- the search
lo=0; hi=$((N-1)); first_bad=""; step=0
declare -A SEEN
while [ "$lo" -le "$hi" ]; do
    mid=$(( (lo + hi) / 2 )); step=$((step+1))
    sha="${RANGE[$mid]}"
    echo
    echo "--- step $step: index $mid of $N, $sha"
    git -C "$TREE" log -1 --format='      %ad %s' --date=short "$sha"
    probe_sha "$sha" "$RUNS" "s$step"
    if [ "$SKIP" = 1 ]; then
        # Unbuildable: step one commit later and retry rather than guessing.
        echo "      skipped; advancing one commit"
        lo=$((mid+1)); continue
    fi
    SEEN["$sha"]="$MED"
    if [ "$MED" -ge "$THRESH" ]; then
        echo "      BAD"
        first_bad="$sha"; hi=$((mid-1))
    else
        echo "      good"
        lo=$((mid+1))
    fi
done

echo
echo "=============================================================="
if [ -z "$first_bad" ]; then
    echo "no commit in the range reads as bad, yet the bad endpoint does."
    echo "That means the transition is outside the pathspec ${PATHSPEC:-(none)}"
    echo "-- widen --paths, or the cause is not in the code at all."
    exit 1
fi
echo "first commit in this range at which $CAPTURE is bad:"
echo
git -C "$TREE" log -1 --stat "$first_bad" | sed 's/^/  /'
echo
echo "measurements taken, in commit order:"
for sha in "${RANGE[@]}"; do
    [ -n "${SEEN[$sha]:-}" ] && printf '  %s  %s\n' "${sha:0:10}" "${SEEN[$sha]}"
done
echo
echo "This is the first BAD commit in this range, not necessarily the only"
echo "transition in it: a capture that broke, was fixed and broke again has"
echo "more than one boundary and a binary search returns one of them. The"
echo "measurements above are the evidence; read them before quoting the sha."
echo "=============================================================="
