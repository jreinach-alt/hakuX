#!/usr/bin/env bash
#
# Daily DX pass: harvest new paper cuts, then mark one as DUE for the
# orchestrator to dispatch. 09:23 America/Los_Angeles.
#
# WHY A TIMER AND NOT A SESSION CRON. The first version of this was a session
# cron -- held in memory, dead when the session exits, auto-expiring after
# seven days regardless. That is the third piece of this project's automation
# with exactly that shape: the Stop hook is read from settings.json at session
# start, and idle-watchdog.sh is read lazily by byte offset so editing it
# mid-run changes nothing. Each one LOOKS installed and is not. A user timer
# with Persistent=true does not, which is why the nightly is one.
#
# WHAT IT DOES AND DELIBERATELY DOES NOT DO. It harvests -- scanning a day of
# commit messages for friction is mechanical and should not wait for an agent.
# It does NOT dispatch: choosing a lane, writing its territory row and briefing
# it is orchestrator work, and a timer that spawned agents would be dispatching
# without a board in view. So it writes a DUE marker and the orchestrator picks
# it up through the channel that already wakes it.
#
# It reports either way, for the nightly's reason: a silent failure here is
# worse than none, because an unharvested day looks exactly like a day with no
# friction.
set -u

TREE="${DX_TREE:-/home/justin/hakuX}"
OUT="${DX_OUT:-/home/justin/hakux-work/dx}"
D="${DISPATCH_DIR:-/home/justin/hakux-work/dispatch}"

mkdir -p "$OUT"
DAY=$(date +%Y-%m-%d)
LOG="$OUT/$DAY.log"
say() { echo "$(date '+%H:%M:%S') $*" | tee -a "$LOG"; }

cd "$TREE" || { echo "no tree at $TREE"; exit 1; }
say "dx pass $DAY  head=$(git rev-parse --short HEAD)"

CUTS="$TREE/docs/testing/papercuts.toml"
[ -f "$CUTS" ] || { say "FATAL: $CUTS missing -- the backlog this pass exists to drain is gone"; exit 1; }

TRACKED=$(python3 - "$CUTS" <<'PY' 2>/dev/null || echo 0
import sys, tomllib
print(len(tomllib.load(open(sys.argv[1], "rb")).get("cut") or []))
PY
)
say "tracked paper cuts: $TRACKED"

# HARVEST. Commit messages in this repo record what a mistake COST, because
# that is the house style -- so they are the corpus.
#
# THE FIRST PATTERN WAS TOO LOOSE AND ITS FAILURE IS INSTRUCTIVE. It matched
# bare "cost (a|an|the)" and returned 26 candidates, nearly all noise: this
# project discusses the COST OF A MEASUREMENT in almost every commit, so the
# word is ambient. A harvester whose hits are mostly noise gets ignored, and
# an ignored harvester is worse than none because it looks like coverage.
#
# So "cost" is only a marker when what was spent is a unit of WORK -- a pass,
# a run, a day, an arm, a build, a queue claim. Plus the phrases that are only
# ever written about a mistake: "had to amend", "commits over", "recurred",
# "bit twice", "silently missed", "this is the second time".
say "--- candidate friction from the last 24h of commits"
git log --since='24 hours ago' --format='%h %s%n%b' 2>/dev/null \
    | grep -nEi 'had to (amend|correct|redo)|committed over an edit|commits over|recurred|bit (me |twice)|silently (missed|failed|never)|cost (a|an|the) (pass|run|day|arm|build|queue claim)|this is the [a-z]+ time' \
    | sed 's/^/  /' | tee -a "$LOG" | head -40

NEW=$(git log --since='24 hours ago' --format='%h %s%n%b' 2>/dev/null \
    | grep -cEi 'had to (amend|correct|redo)|committed over an edit|commits over|recurred|bit (me |twice)|silently (missed|failed|never)|cost (a|an|the) (pass|run|day|arm|build|queue claim)|this is the [a-z]+ time')
say "harvest: $NEW candidate line(s) -- these are CANDIDATES, not entries; the pass triages them"

# The marker. Written last so a failure above leaves no DUE claim behind.
mkdir -p "$D"
{
    echo "due_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo "tracked=$TRACKED"
    echo "harvest_candidates=$NEW"
    echo "log=$LOG"
} > "$D/dx-pass.due"
say "wrote $D/dx-pass.due -- orchestrator dispatches; this script does not"
