#!/usr/bin/env bash
#
# SessionStart hook. Prints the forty lines this session actually needs,
# instead of relying on every session reading 2,200 lines of AGENTS.md.
# Whatever this prints is added to the session's context.
#
# It fails OPEN on everything: no adb, no dispatch directory, no board branch,
# no network. A hook that can stop a session from starting is worse than one
# that says less. Every branch below tolerates its input being absent.
#
# Environment, all optional, set by lane.sh / run-claude-job.sh:
#   HAKUX_ROLE     lane | board | fold | audit | ...   (default: interactive)
#   HAKUX_BRIEF    path to the brief file for this session
#   HAKUX_BRANCH   the only branch this session may push to
#   HAKUX_TIP      the trunk ref to measure staleness against (default master)
set -u
ROOT="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"
D="${DISPATCH_DIR:-/home/justin/hakux-work/dispatch}"
TIP="${HAKUX_TIP:-master}"
cd "$ROOT" 2>/dev/null || exit 0

echo "== hakuX session start: role=${HAKUX_ROLE:-interactive} branch=${HAKUX_BRANCH:-$(git rev-parse --abbrev-ref HEAD 2>/dev/null)}"

# THE BASE CHECK, first, because a stale checkout invalidates everything a
# session concludes from its own tree (AGENTS.md: "An agent worktree is
# created on a STALE base"). origin/<tip> is used when it resolves; a
# worktree shares the object store so this costs nothing.
ref="origin/$TIP"; git rev-parse --verify --quiet "$ref" >/dev/null 2>&1 || ref="$TIP"
behind=$(git rev-list --count "HEAD..$ref" 2>/dev/null || echo "?")
if [ "$behind" = "?" ]; then
    echo "-- base: could not measure against $ref"
elif [ "$behind" -gt 0 ]; then
    echo "-- base: THIS CHECKOUT IS $behind COMMIT(S) BEHIND $ref."
    echo "   In a lane: merge $ref before concluding anything from this tree, and"
    echo "   never register a prediction on a ref older than that merge."
else
    echo "-- base: at $ref ($(git rev-parse --short HEAD 2>/dev/null))"
fi

if [ -n "${HAKUX_BRIEF:-}" ] && [ -f "$HAKUX_BRIEF" ]; then
    echo "-- brief ($HAKUX_BRIEF):"
    sed 's/^/   /' "$HAKUX_BRIEF"
fi

if [ -d "$D/hold" ]; then
    holds=$(ls "$D/hold" 2>/dev/null | grep -v '\.why$' | tr '\n' ' ')
    if [ -n "$holds" ]; then
        echo "-- device holds in force: $holds (a hold is never a reason to go idle; every issue has offline surface)"
        for w in "$D"/hold/*.why; do [ -f "$w" ] && echo "   $(basename "$w" .why): $(head -1 "$w")"; done
    else
        echo "-- device holds: none"
    fi
fi

if [ -f docs/testing/fleet.py ] && [ "${HAKUX_ROLE:-}" != "lane" ]; then
    echo "-- fleet (FAIL lines only; run fleet.py for the inventory):"
    timeout 30 python3 docs/testing/fleet.py 2>&1 | grep '^FAIL' | head -8 | sed 's/^/   /' || true
fi

case "${HAKUX_ROLE:-}" in
  lane)
    cat <<'RULES'
-- lane contract (docs/ORCHESTRATION-DESIGN.md §6.4):
   push only to your own branch; open a draft PR whose body lists your files;
   never edit territory.toml or nv2a_issues.toml (write a board request);
   register the prediction AFTER your last rebase and never rebase after;
   commit NOTES.md before any long step; report on the issue with [lane.<name>] first;
   a hold is not a reason to idle -- implement, prove by reading, register, then stop.
RULES
    ;;
  board)
    echo "-- board contract: act on the FAIL lines by rule; never author code; anything you cannot decide by rule becomes a decision-needed issue."
    ;;
esac
exit 0
