#!/usr/bin/env bash
# Run the gates CI runs, here, before pushing.
#
# The workflows that fire on a pull request are Android, Desktop build and
# NV2A index -- about thirteen minutes of hosted runner time per push, and
# Actions minutes are a limited monthly budget. Two of those three gates are
# reproducible locally in seconds, so a push that has passed this script
# should not need CI to tell it anything.
#
#   docs/testing/preflight.sh [--tests DIR] [--support DIR]
#
# Exits non-zero and says which gate failed. Run it before every push; put
# [skip ci] in the commit message when it passes and the change cannot affect
# a platform this script does not build (Android, macOS, Windows).

set -u
cd "$(dirname "$0")/../.." || exit 2

# The test sources live wherever the lane put them; $HOME differs between the
# desktop container and a workstation, so look rather than assume.
find_repo() {
    for d in "$HOME/$1" /home/user/"$1" /home/justin/"$1" "$PWD/../$1"; do
        [ -d "$d/.git" ] && { echo "$d"; return; }
    done
}
TESTS=${TESTS:-$(find_repo nxdk_pgraph_tests)}
SUPPORT=${SUPPORT:-$(find_repo pbkitplusplus)}
while [ $# -gt 0 ]; do
    case "$1" in
        --allow-ci) ALLOW_CI=1; shift ;;
        --allow-tracker) ALLOW_TRACKER=1; shift ;;
        --tests) TESTS="$2"; shift 2 ;;
        --support) SUPPORT="$2"; shift 2 ;;
        *) echo "unknown argument: $1" >&2; exit 2 ;;
    esac
done

fail=0
step() { printf '%-28s' "$1"; }
ok()   { echo "ok"; }
bad()  { echo "FAILED"; fail=1; }

# 1. psh_differ, as .github/workflows/desktop.yml runs it. carve.py refuses to
#    carve a function it was not told about, so a new PGRAPHState reader in
#    psh.c stops the build here rather than on a runner.
step "psh_differ build"
if make -C docs/testing/psh_differ >/tmp/preflight-make.log 2>&1; then ok; else
    bad; tail -5 /tmp/preflight-make.log
fi

if [ $fail -eq 0 ]; then
    step "psh_differ report"
    ./docs/testing/psh_differ/build/psh-differ >/tmp/preflight-differ.log 2>/tmp/preflight-differ.err
    if grep -q 'does not generate' /tmp/preflight-differ.err; then
        bad; echo "  a baseline no longer generates a shader:"; head -5 /tmp/preflight-differ.err
    elif ! grep -q '^TOTAL' /tmp/preflight-differ.log; then
        bad; echo "  produced no report"; tail -5 /tmp/preflight-differ.log
    else
        ok; grep -E '^TOTAL' /tmp/preflight-differ.log | sed 's/^/  /'
    fi
fi

# 1b. aci_vmstate, the save/load round trip for the MCPX ACI (issue #75). No
#     configured QEMU build, no device, three seconds -- and it carves its
#     field list out of hw/xbox/mcpx/aci.c and its member list out of
#     hw/audio/ac97_int.h, so a field added to AC97LinkState without a
#     decision about whether it is guest state stops here.
step "aci_vmstate"
if make -C docs/testing/aci_vmstate run >/tmp/preflight-aci.log 2>&1; then
    ok
    grep -E 'guest state reproduced' /tmp/preflight-aci.log | sed 's/^/  /'
else
    bad
    grep -E 'FAIL|error:' /tmp/preflight-aci.log | head -8 | sed 's/^/  /'
    echo "  full output: /tmp/preflight-aci.log"
fi

# 2. The nv2a index, as .github/workflows/nv2a-index.yml runs it. It records
#    site line numbers, so ANY commit touching hw/xbox has to carry a
#    regenerated index or this goes red on the next push.
#
#    AND IT IS SCORED AGAINST THE FOLD BASE, NOT THE TIP, because otherwise it
#    punishes a lane for the previous fold. `lane.lows` arrived to a failure of
#    396 entries, ALL in vk/draw.c and NONE of them its own -- it had touched
#    no hw/xbox file at all. The index is derived from the whole tree, so a
#    lane that regenerates it necessarily commits other lanes' churn, and three
#    concurrent lanes produce three conflicting 829 KB JSONs at the next fold.
#    Decision recorded in docs/audits/2026-09-14-decisions.md: fold-time
#    regeneration is the rule and the orchestrator owns it.
#
#    THE ATTRIBUTION IS STRUCTURAL, not a guess. nv2a_index.py's SCAN_ROOTS is
#    the only place the symbol/site half comes from, so a change that touches
#    no file under those roots CANNOT have moved a site -- the way the empty
#    `_ZB` class settled a scorer question in a second. The suite half comes
#    from the tests tree, which is a different repository this branch never
#    commits to, so no commit here can move it either. SCAN_ROOTS is READ from
#    nv2a_index.py rather than hardcoded: that file is not in this lane's
#    claim, and a gate that hardcodes the thing it guards goes wrong silently
#    the day the guarded thing changes.
#
#    WHO IS THE FOLD POINT is a question about SHAS, which is the one thing
#    `merge-base --is-ancestor` answers honestly (AGENTS.md is warning about
#    using it for PATCHES, which this is not). HEAD an ancestor of the campaign
#    tip means this checkout IS the shared position -- the orchestrator at fold
#    time, or a lane that has committed nothing -- and there is nobody else to
#    attribute the drift to, so it fails exactly as it did before. A lane with
#    commits the tip does not have gets the attribution.
#
#    WHAT THIS CANNOT SEE: whether the pre-existing drift is real. It does not
#    rebuild the index at the base -- that needs a checkout of the base and a
#    second index build, and a checker with a side effect on the tree it checks
#    has already stalled this project's build path once. So it establishes
#    "this lane did not cause it", never "the index is fine". The stale index
#    is still reported in full and still has to reach the orchestrator.
step "nv2a index"
if [ -z "$TESTS" ] || [ ! -d "$TESTS" ]; then
    bad
    echo "  cannot find nxdk_pgraph_tests, so this gate did not run."
    echo "  Pass --tests DIR. Do not push on an unchecked index: it is the"
    echo "  gate that fails most often, because it records source line numbers."
elif python3 docs/testing/nv2a_index.py check --tests "$TESTS" \
        ${SUPPORT:+--support "$SUPPORT"} >/tmp/preflight-index.log 2>&1; then
    ok
else
    INDEX_TIP="${HAKUX_TIP:-claude/es-de-launcher-disc-error-ojnl14}"
    INDEX_ROOTS=$(python3 - <<'PYROOTS'
import re, sys
src = open("docs/testing/nv2a_index.py").read()
m = re.search(r"^SCAN_ROOTS\s*=\s*\[(.*?)\]", src, re.S | re.M)
print(" ".join(re.findall(r"['\"]([^'\"]+)['\"]", m.group(1))) if m else "")
PYROOTS
)
    INDEX_BASE=$(git merge-base HEAD "$INDEX_TIP" 2>/dev/null || true)
    INDEX_MINE=""
    if [ -n "$INDEX_BASE" ] && [ -n "$INDEX_ROOTS" ] \
       && ! git merge-base --is-ancestor HEAD "$INDEX_TIP" 2>/dev/null; then
        # base..WORKING TREE, not base..HEAD: an uncommitted edit under a scan
        # root moves sites just as a committed one does, and untracked files
        # add them, so both are asked for.
        INDEX_MINE=$(
            { git diff --name-only "$INDEX_BASE" -- $INDEX_ROOTS 2>/dev/null
              git ls-files --others --exclude-standard -- $INDEX_ROOTS 2>/dev/null
            } | sort -u)
    else
        # No base, no roots, or HEAD is at/behind the tip: no one else to
        # attribute to. Fail as before.
        INDEX_MINE="(unattributable)"
    fi
    if [ -z "$INDEX_MINE" ]; then
        echo "ok (stale, but NOT THIS LANE'S)"
        echo "  The committed index does not match the tree, and none of this"
        echo "  lane's changes touch $INDEX_ROOTS -- so none of them can have"
        echo "  moved a site. The drift predates $(git rev-parse --short "$INDEX_BASE" 2>/dev/null)."
        echo "  Fold-time regeneration is the orchestrator's, per"
        echo "  docs/audits/2026-09-14-decisions.md. Do NOT regenerate here:"
        echo "  the index is whole-tree, so you would commit other lanes'"
        echo "  churn and collide with every concurrent lane at the fold."
        echo "  PUT THIS IN YOUR REPORT so the orchestrator sees it:"
        sed 's/^/    /' /tmp/preflight-index.log
    else
        bad
        sed 's/^/  /' /tmp/preflight-index.log
        if [ "$INDEX_MINE" != "(unattributable)" ]; then
            echo "  YOUR changes under $INDEX_ROOTS, which is why this is yours:"
            printf '    %s\n' $INDEX_MINE
        fi
        echo "  regenerate: python3 docs/testing/nv2a_index.py build --tests $TESTS --support $SUPPORT"
    fi
fi

# 3. The territory allocation. Not a CI gate -- CI does not care who holds a
#    file -- but it belongs here because it catches a SILENT revert, and the
#    revert happens at exactly the moment this script runs: after folding lane
#    branches, before pushing. A lane carries whatever territory.toml said when
#    it branched, so cherry-picking it restores the older allocation with no
#    conflict. That went unnoticed on 2026-09-13 and the next brief was written
#    from a reverted table.
step "territory"
if python3 docs/testing/check_territory.py >/tmp/preflight-territory.log 2>&1; then
    ok
else
    bad
    sed 's/^/  /' /tmp/preflight-territory.log
fi

# 4. Issue coverage. Like the territory check this is not a CI gate -- CI does
#    not know what a lane is -- but it belongs here for the same reason: the
#    state it guards changes at exactly the moment someone folds work and
#    pushes. It FAILS OPEN without `gh`, so an offline preflight still passes.
step "coverage"
if python3 docs/testing/check_coverage.py >/tmp/preflight-coverage.log 2>&1; then
    ok
    sed -n 1p /tmp/preflight-coverage.log | sed 's/^/  /'
else
    bad
    sed 's/^/  /' /tmp/preflight-coverage.log
fi

# 5. THE BOARD FILES, which a lane is contractually barred from editing and
#    which nothing enforced.
#
#    AGENTS.md:228 bars a lane from touching `nv2a_issues.toml` or
#    `territory.toml`; AGENTS.md:237 puts tracker arbitration with the
#    orchestrator, because the tracker is the one hand-maintained table in the
#    index and an agent editing the claim registry while claiming territory in
#    it is circular. A lane that needs the board changed writes
#    $DISPATCH_DIR/board-requests/<lane>.md instead.
#
#    A LANE DID IT ANYWAY THIS SESSION -- 45c8adb4f6, +42/-11 in
#    nv2a_issues.toml. The content was correct, so nothing was reverted, and
#    that is exactly the shape this audit loop exists to catch: the only thing
#    enforcing the rule was somebody reading the diff, and concurrent edits to
#    the board conflict badly at the next fold.
#
#    WHAT IT MUST NOT REFUSE, stated before the check rather than after it,
#    because a gate that fires on correct work is worse than no gate and this
#    one guards a file the ORCHESTRATOR edits constantly -- 178 commits touch
#    nv2a_issues.toml on this branch and 61 touch territory.toml, essentially
#    all of them orchestrator `board:` commits. Three exemptions, and none of
#    them is "trust the subject line":
#
#      * THE SHARED TREE. A checkout at $DISPATCH_TREE is the orchestrator's
#        own position, and it is where every one of those 239 commits was made.
#      * THE FOLD WORKTREE, /home/justin/hakux-work/fold, which is where a fold
#        now happens (AGENTS.md, "The orchestrator folds in a separate
#        worktree"). At fold time HEAD there is ahead of the tip and carries
#        the lane's commits AND the orchestrator's board edits, so the
#        ancestor test the nv2a-index gate uses cannot tell the two apart --
#        which is why this keys on WHERE rather than on WHAT.
#      * --allow-tracker, said out loud, the same escape --allow-ci provides.
#
#    The fold path is READ from AGENTS.md rather than hardcoded here, for the
#    reason gate 2 reads SCAN_ROOTS from nv2a_index.py: a gate that hardcodes
#    the thing it guards goes wrong silently the day the guarded thing moves.
#    HAKUX_FOLD_DIR overrides it.
#
#    WHAT IT CANNOT SEE: a lane that edits the board and does not run
#    preflight, and a lane whose worktree happens to sit at one of the exempt
#    paths. It is a check on a checkout's position, not on an agent's
#    identity, and there is no agent identity available here to check.
step "board files"
TRACKER_FILES="docs/testing/nv2a_issues.toml docs/testing/territory.toml"
TRACKER_TIP="${HAKUX_TIP:-claude/es-de-launcher-disc-error-ojnl14}"
TRACKER_ROOT=$(git rev-parse --show-toplevel 2>/dev/null || echo "")
TRACKER_SHARED="${DISPATCH_TREE:-/home/justin/hakuX}"
TRACKER_FOLD="${HAKUX_FOLD_DIR:-$(grep -o '/home/[a-z0-9_-]*/hakux-work/fold' AGENTS.md 2>/dev/null | head -1)}"
# base..HEAD plus the working tree and the index: an uncommitted board edit is
# the same violation one moment earlier, and preflight is meant to be run
# before the commit as well as before the push.
TRACKER_BASE=$(git merge-base HEAD "$TRACKER_TIP" 2>/dev/null || true)
TRACKER_MINE=""
if [ -n "$TRACKER_BASE" ] \
   && ! git merge-base --is-ancestor HEAD "$TRACKER_TIP" 2>/dev/null; then
    TRACKER_MINE=$(git log --format='%h %s' "$TRACKER_BASE..HEAD" -- $TRACKER_FILES 2>/dev/null)
fi
TRACKER_DIRTY=$(git status --porcelain -- $TRACKER_FILES 2>/dev/null)
if [ -z "$TRACKER_MINE" ] && [ -z "$TRACKER_DIRTY" ]; then
    ok
elif [ "${ALLOW_TRACKER:-0}" = 1 ]; then
    ok
    echo "  --allow-tracker given: editing the board here is deliberate."
elif [ -n "$TRACKER_ROOT" ] && [ "$TRACKER_ROOT" = "$TRACKER_SHARED" ]; then
    ok
    echo "  the shared tree ($TRACKER_SHARED), so this is the orchestrator's"
    echo "  own position and the board is its to arbitrate."
elif [ -n "$TRACKER_FOLD" ] && [ "$TRACKER_ROOT" = "$TRACKER_FOLD" ]; then
    ok
    echo "  the fold worktree ($TRACKER_FOLD), where a fold legitimately edits"
    echo "  the board alongside the lane commits it is folding."
else
    bad
    echo "  This checkout edits the BOARD, which a lane may not do."
    echo "  AGENTS.md:228 bars it and AGENTS.md:237 puts tracker arbitration"
    echo "  with the orchestrator: the tracker is the one hand-maintained table"
    echo "  in the index, and concurrent board edits conflict badly at a fold."
    if [ -n "$TRACKER_MINE" ]; then
        echo "  commits of yours that the tip does not have:"
        printf '%s\n' "$TRACKER_MINE" | sed 's/^/    /'
    fi
    if [ -n "$TRACKER_DIRTY" ]; then
        echo "  uncommitted:"
        printf '%s\n' "$TRACKER_DIRTY" | sed 's/^/    /'
    fi
    echo "  WHAT TO DO INSTEAD: write what the board needs to say, and why, to"
    echo "    \$DISPATCH_DIR/board-requests/<lane>.md"
    echo "  and put the same thing in your final report. The orchestrator"
    echo "  applies it. A lane must never be blamed for a gate it cannot reach,"
    echo "  and it must not reach past this one either."
    echo "  nv2a_index.json in the same directory is FINE: nv2a_index.py build"
    echo "  generates it, and gate 2 above is what governs it."
    echo "  If you ARE the orchestrator, fold in $TRACKER_FOLD or pass"
    echo "  --allow-tracker."
fi

# 6. THE COMMIT SUBJECT'S [skip ci], because nothing enforced it and the
#    convention was doing less work than it looked like.
#
#    The rule here is that every commit subject ends with [skip ci], and CI is
#    an on-demand resource. GitHub evaluates that marker on the HEAD commit,
#    so the protection is only as good as the last subject -- and an audit on
#    2026-09-13 found all FIVE merge commits of the day carried no marker at
#    all, several of them HEAD at push time. Nothing was spent, because this
#    branch has no pull request and a push to it fires nothing. THAT is the
#    real protection, and it is not the one anyone believed they had: open a
#    PR on this branch and each of those pushes becomes three hosted jobs. For
#    scale, the single open PR in this repo consumed 21 runs in one day.
#
#    Found by a typo -- [skip ki] for [skip ci] -- caught while amending. A
#    convention a typo can silently disable wants a check.
#
#    Refuses rather than warns, because the cost is the resource this script
#    exists to protect. A deliberate CI run is still available and now has to
#    be said out loud: --allow-ci.
#    AND IT MUST NAME A NEAR-MISS, which is now at bit=4 in papercuts.toml.
#    `[skip ki]` has happened FOUR times, the fourth minutes after the third
#    was logged, in a commit whose body was about false-positive rates. It
#    happens in a plain heredoc subject as well as when chaining -m, so it is
#    a typing slip and not a git behaviour, and four occurrences is enough
#    evidence that knowing about it does not fix it.
#
#    The presence grep is not useless against it -- a bare `[skip ki]` already
#    FAILS, because the subject does not contain `[skip ci]`. Two things were
#    still wrong, and the second is the one that let it recur:
#
#      * THE MESSAGE SAID "has no [skip ci]" and told the author to add one.
#        That is true and unhelpful: the marker is right there, one character
#        out, and the author re-types it -- possibly wrong again. A gate that
#        names the typo turns a recurring slip into a one-character amend.
#        Same argument as the nv2a index gate printing WHICH line moved.
#      * A NEAR-MISS ALONGSIDE A CORRECT MARKER PASSED SILENTLY. `... [skip
#        ci] [skip ki]` contains `[skip ci]`, so the grep was satisfied and
#        the typo shipped. That is the "guard satisfied by the presence of
#        the thing it guards" shape.
#
#    So: every bracketed token in the subject is normalised (lowercased,
#    whitespace collapsed) and measured against `skip ci`. Distance 0 is the
#    marker; distance 1 or 2 is a near-miss and FAILS whether or not a correct
#    marker is also present. 2 rather than 1 because a TRANSPOSITION -- the
#    commonest typing slip of all -- is distance 2 in Levenshtein, so `[skpi
#    ci]` needs it. Measured over the last 400 subjects on this branch: 390
#    bracketed tokens, every one of them exactly `[skip ci]`, so the widened
#    radius flags nothing that is actually in use.
#
#    WHAT THIS CANNOT SEE: a near-miss in any commit that is not HEAD. GitHub
#    evaluates the marker on HEAD, so that is the commit that can spend
#    minutes -- but a typo further down the branch stays invisible here and
#    becomes live the moment anything is pushed on top of it.
step "commit subject"
subject=$(git log -1 --format=%s 2>/dev/null || echo "")
# THE SUBJECT ARRIVES AS ARGV, NOT ON STDIN, and the first version got this
# wrong in a way worth keeping the note for. `python3 - <<'EOF'` already uses
# stdin for the PROGRAM text, so `printf ... | python3 - <<EOF` has its pipe
# silently discarded and sys.stdin.read() returns "". Every near-miss case
# then fell through to the old "has no [skip ci]" message and this branch
# never ran once.
#
# It was invisible because the gate still FAILED on the cases that matter --
# the right exit code for the wrong reason, which is this file's "a guard
# satisfied by the absence of the thing it guards". The case that exposed it
# is the one the gate was added for: a typo BESIDE a correct marker still
# printed `ok`.
nearmiss=$(python3 - "$subject" <<'PYSKIP'
import re, sys
WANT = "skip ci"


def dist(a, b):
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1,
                           prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


subject = sys.argv[1] if len(sys.argv) > 1 else ""
for tok in re.findall(r"\[([^\]]*)\]", subject):
    norm = " ".join(tok.lower().split())
    if norm == WANT:
        continue
    d = dist(norm, WANT)
    if d <= 2:
        print("[%s]\t%d" % (tok, d))
PYSKIP
)
if [ "${ALLOW_CI:-0}" = 1 ]; then
    ok
    echo "  --allow-ci given: HEAD may trigger CI, which is deliberate."
elif [ -n "$nearmiss" ]; then
    bad
    echo "  HEAD's subject carries a NEAR-MISS of the [skip ci] marker:"
    echo "    $subject"
    printf '%s\n' "$nearmiss" | while IFS="$(printf '\t')" read -r tok d; do
        echo "    $tok is $d character(s) from [skip ci] -- did you mean [skip ci]?"
    done
    if printf '%s' "$subject" | grep -q '\[skip ci\]'; then
        echo "  A correct [skip ci] IS also present, so CI would be skipped and"
        echo "  the old check passed this silently. The typo still ships, and"
        echo "  this marker is at bit=4 in papercuts.toml precisely because"
        echo "  knowing about it has not stopped it."
    else
        echo "  There is no correct [skip ci], so pushing this can spend CI"
        echo "  minutes. This is a one-character amend, not a missing marker."
    fi
    echo "  Amend the subject, or pass --allow-ci if a CI run is the point."
elif printf '%s' "$subject" | grep -q '\[skip ci\]'; then
    ok
else
    bad
    echo "  HEAD's subject has no [skip ci]:"
    echo "    $subject"
    echo "  GitHub reads that marker on the HEAD commit, so pushing this can"
    echo "  spend CI minutes. Merge commits are the usual culprit: git does not"
    echo "  put the marker in a generated merge subject, so pass -m."
    echo "  Amend the subject, or pass --allow-ci if a CI run is the point."
fi

echo
if [ $fail -eq 0 ]; then
    echo "preflight passed - safe to push"
else
    echo "preflight FAILED - fix before pushing, do not spend a CI run finding out"
fi
exit $fail
