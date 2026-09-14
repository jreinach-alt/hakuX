#!/usr/bin/env bash
#
# Wake the orchestrator when it goes idle with the backlog still open.
#
#   idle-watchdog.sh <session-id>      # run under the Monitor tool
#
# Why this exists, and why it is not the Stop hook
# ------------------------------------------------
#
# `backlog-gate.sh` is a Stop hook and is correct: claimed by session id, fails
# open, tested on all four paths. It has never once run in the orchestrator
# session. Proof: its first action is an unconditional append to
# invocations.log, and that file does not exist after three turn ends.
#
# The reason is that `.claude/settings.json` is read when a session STARTS. The
# hook was registered mid-session, so it is live for every session opened
# afterwards -- it gated an unrelated session through six blocks -- and dead for
# the session that registered it. Editing the script cannot fix that; only a
# restart can.
#
# So this is the in-session equivalent. It watches the orchestrator's own
# transcript: when nothing has been appended for IDLE_AFTER seconds and issues
# are still open, it prints one line. Under the Monitor tool a printed line
# becomes a notification, which re-invokes the session -- the same effect the
# hook's `block` would have had, by a route that does not depend on settings
# having been loaded.
#
# Design constraints that matter
# ------------------------------
#
# THIS LOOP PARSES ITS SCRIPT ONCE, so editing this file does not reach a
# RUNNING watchdog -- it must be stopped and restarted. That is not a quirk of
# this script, it is how bash executes a `while` loop, and it has now cost this
# campaign three times in one day: soak_title.sh and run_disc.sh changes that
# never reached the serving dispatcher, a dispatcher snapshot that re-execed
# its own copy, and this file's message continuing to print the old text after
# it was rewritten. The dispatcher solved it by re-execing on a source hash;
# this script is short-lived enough that restarting it is the honest fix, and
# saying so here is cheaper than adding the machinery.
#
# ONE EVENT PER IDLE PERIOD. It latches after firing and only re-arms once the
# transcript is touched again. A monitor that emits repeatedly gets throttled
# and then stopped by the harness, which would leave the session unwatched
# precisely when it had gone quiet.
#
# FAIL QUIET, NOT LOUD. If `gh` is unreachable it does not fire. A network blip
# should not produce a nag, and an un-actionable nag trains the reader to
# ignore the actionable ones.
#
# IT EXITS WHEN THE BACKLOG IS CLEAR. That is the terminating condition for the
# whole exercise, so the watchdog should not outlive it.
set -u

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SID="${1:?usage: idle-watchdog.sh <session-id>}"
# Overridable so the latching behaviour can be tested without relocating HOME,
# which hides gh's credentials and makes the fail-quiet path swallow the test.
TRANSCRIPT="${WATCHDOG_TRANSCRIPT:-$HOME/.claude/projects/-home-justin-hakuX/$SID.jsonl}"
REPO="jreinach-alt/hakuX"
DISPATCH="${DISPATCH_DIR:-/home/justin/hakux-work/dispatch}"

IDLE_AFTER=${IDLE_AFTER:-75}     # seconds of transcript silence before firing
POLL=${POLL:-20}
ISSUE_TTL=${ISSUE_TTL:-300}      # how long an issue count is reused

last_count=""
last_count_at=0
armed=1                          # 1 = will fire when idle; 0 = already fired
last_mtime=0

issue_count() {
    local now; now=$(date +%s)
    if [ -n "$last_count" ] && [ $(( now - last_count_at )) -lt "$ISSUE_TTL" ]; then
        printf '%s' "$last_count"; return 0
    fi
    local c
    c=$(timeout 20 gh issue list --repo "$REPO" --state open --limit 100 \
          --json number --jq 'length' 2>/dev/null) || c=""
    case "$c" in ''|*[!0-9]*) printf ''; return 1 ;; esac
    last_count="$c"; last_count_at="$now"
    printf '%s' "$c"
}

while :; do
    sleep "$POLL"

    # A MISSING TRANSCRIPT MUST BE LOUD, because it looks exactly like a busy
    # session. The path is built from the session id passed on the command
    # line, and a single wrong character makes this loop poll a file that will
    # never exist -- so it never fires, and "no events" reads as "the
    # orchestrator is working", which is the one thing this watchdog exists to
    # contradict.
    #
    # That happened: restarting this watchdog after an edit, the session id was
    # typed with one digit wrong (b4db418e for b4db438e) and the replacement
    # was silently dead on arrival. Caught by re-reading the command, not by
    # anything here.
    #
    # So say it once, after enough polls that a genuinely new session has had
    # time to write its first line, and then keep quiet rather than nagging.
    if [ ! -f "$TRANSCRIPT" ]; then
        missing=$(( ${missing:-0} + 1 ))
        if [ "$missing" = 4 ]; then
            echo "WATCHDOG IS WATCHING NOTHING: no transcript at $TRANSCRIPT after $((missing * POLL))s. The session id argument is probably wrong, and this loop will never fire -- its silence is not an idle-free session. Restart it with the right id."
        fi
        continue
    fi
    missing=0

    mtime=$(stat -c %Y "$TRANSCRIPT" 2>/dev/null || echo 0)
    now=$(date +%s)
    idle=$(( now - mtime ))

    # Re-arm as soon as the session speaks again.
    if [ "$mtime" != "$last_mtime" ]; then
        last_mtime="$mtime"
        armed=1
        continue
    fi

    [ "$armed" = 1 ] || continue
    [ "$idle" -ge "$IDLE_AFTER" ] || continue

    count=$(issue_count) || continue      # fail quiet
    [ -n "$count" ] || continue
    if [ "$count" -eq 0 ]; then
        echo "BACKLOG CLEAR: 0 issues open. The watchdog is exiting; nothing left to nag about."
        exit 0
    fi

    queued=$(ls "$DISPATCH"/queue/*.req 2>/dev/null | wc -l | tr -d ' ')
    running=$(ls "$DISPATCH"/running/*.req 2>/dev/null | wc -l | tr -d ' ')
    sweep=$(ls "$DISPATCH"/queue/z-*.req 2>/dev/null | wc -l | tr -d ' ')
    agentwork=$(( queued - sweep )); [ "$agentwork" -lt 0 ] && agentwork=0

    # NAME THE SPECIFIC GAP, not the generic list. The old message printed the
    # same five suggestions every time, which is a nag: it tells the reader
    # nothing they did not know and trains them to skim it. Worse, on
    # 2026-09-13 the orchestrator twice asserted a state of the board that the
    # board did not support -- once saying every issue had a lane or a blocker
    # when #53 had neither, once saying the remaining work was all blocked when
    # two items were neither blocked nor claimed. Both were caught by reading
    # the machine-readable state instead of the summary.
    #
    # check_coverage.py already reads exactly that state and already fails open
    # without gh, so ask it rather than re-deriving. Its output replaces the
    # suggestion list when it has something specific to say.
    # A DIRTY SHARED TREE OUTRANKS EVERYTHING ELSE THIS CAN SAY, because it
    # stops the dispatcher building any ref that is not already cached -- and
    # it fails by requeueing every 30s, silently. Twice today: a checker of
    # mine that wrote a tracked stamp file (129 requeues) and a lane working in
    # the shared tree instead of a worktree (122 more). Both were found by
    # someone noticing their own arms bouncing, not by anything here, and the
    # second was masked for an hour because the corpus sweep kept running from
    # a cached binary.
    #
    # So check it first and say WHICH files, since that is the whole fix.
    tree=$(cd "$HERE/../.." 2>/dev/null && git status --porcelain 2>/dev/null \
             | grep -v '^??' | awk '{print $2}' | head -4 | tr '\n' ' ')
    if [ -n "$tree" ]; then
        recent=$(tail -400 "$DISPATCH/logs/dispatcher.log" 2>/dev/null \
                   | grep -c "tree is dirty")
        armed=0
        echo "DIRTY SHARED TREE -- the dispatcher cannot build any uncached ref: ${tree}(${recent} dirty-tree requeues in the recent log). Commit or revert them. A lane working in /home/justin/hakuX instead of a worktree does this, and it fails by requeueing silently rather than erroring."
        continue
    fi

    cov=$(cd "$HERE/../.." 2>/dev/null && timeout 45 python3 \
              docs/testing/check_coverage.py 2>&1 | head -6)
    case "$cov" in
        FAIL*)  hint="COVERAGE GAP -- $(printf '%s' "$cov" | sed -n 2p | sed 's/^ *//'). Give it a lane in territory.toml or write blocked_on on its tracker entry." ;;
        *"NOT CHECKED"*) hint="coverage unchecked (no gh). Pick up: fold a finished lane's diff and dispatch its A/B; claim an issue whose files territory.toml lists free; or refresh the scoreboard with collect_sweep.sh." ;;
        *)
            # DEVICE-BOUND IS A STATE, NOT AN ABSENCE OF SUGGESTIONS. When
            # nothing is uncovered and arms are queued, all three of the
            # suggestions below are unavailable -- and printing them anyway is
            # the nag this file's own comment warns about, now aimed at a
            # reader who can only wait. Say so, with the number that makes
            # waiting a decision rather than a guess.
            # DIVIDE BY THE DEVICES THAT ARE ACTUALLY SERVING, not by two.
            # This said "across two handhelds" and halved the total, which was
            # true while both were up and wrong the moment one was not -- and
            # a device can now be taken out of service with
            # $DISPATCH_DIR/hold/<label>, so "not up" is a normal state rather
            # than a fault. Halving a queue that only one device can drain
            # tells the reader to keep holding for half as long as it will
            # actually take, which is the one number this message exists to
            # supply.
            #
            # Live lanes are the same pid files affinity.py uses, and a held
            # worker removes its own, so the count is right without this
            # script knowing anything about holds.
            mins=$(cd "$HERE/../.." 2>/dev/null && python3 - <<'PYEOF' 2>/dev/null
import json, glob, os
D = '/home/justin/hakux-work/dispatch'
live = 0
for name in (os.listdir(os.path.join(D, 'lanes')) if os.path.isdir(os.path.join(D, 'lanes')) else []):
    try:
        os.kill(int(open(os.path.join(D, 'lanes', name)).read().strip()), 0)
        live += 1
    except Exception:
        pass
tot = 0
for f in glob.glob(os.path.join(D, 'queue', '*.req')):
    if os.path.basename(f).startswith('z-'):
        continue
    try:
        r = json.load(open(f))
    except Exception:
        continue
    if r.get('title'):
        tot += int(r.get('seconds', 60)) + 120
    else:
        # PER-SUITE COST DEPENDS ON THE DISC, and only one non-stock disc
        # here has been timed. The interactive Blend image carries 1,673
        # captures against a normal suite's tens and measured 1,033 s of
        # device time plus ~120 s of scoring, so estimating it as one ordinary
        # suite understated a twenty-minute run as six.
        #
        # Every OTHER base_iso is a different disc with a different capture
        # count -- the 2025 depth image is ~338 s/run -- so keying on "base_iso
        # is set" would apply the Blend disc's cost to discs it was never
        # measured on. That is the same mistake as sizing a change off the test
        # disc's ratios, one level down, so it is keyed on the image that was
        # actually timed and everything else keeps the ordinary estimate.
        # AN ALLOW-LIST PRICES BY TEST, NOT BY SUITE. `--only-tests` narrows a
        # run to named tests, so its cost scales with how many were named and
        # not with the one suite they sit in.
        #
        # 1 s/test, MEASURED, and the previous value here was 6 s/test taken
        # from a figure that has since been retracted. That 5.5 s/test came
        # from dividing a 1,800 s run's whole wall clock by the tests it had
        # completed -- on a run that spent 1,525 of those seconds STALLED. It
        # measured the stall and called it pace, which is this file's own
        # "a rate over a busy window measures the busyness". The lane that
        # gave me the number retracted it after its retry ran 189 tests in
        # 161 s wall: 852 ms/test, against 876 ms/test on the stalled run --
        # indistinguishable, so pace was never the variable.
        #
        # Consequence worth recording: my "fix" using the bad constant made
        # this estimate WORSE than the per-suite one it replaced. 196 tests
        # priced at 22 minutes actually took 161 s. A refuted number
        # propagated into tooling outlives the report that refuted it, so the
        # comment carries the measurement and not just the value.
        only = r.get('only_tests') or []
        if only:
            tot += 180 + len(only)
            continue
        iso = os.path.basename(r.get('base_iso') or '')
        per = 1150 if iso == 'nxdk_pgraph_tests_xiso_interactive.iso' else 160
        tot += 180 + len(r.get('suites') or []) * per
print('%d %d' % (tot // 60 // max(live, 1), live))
PYEOF
)
            devs=${mins##* }; mins=${mins%% *}
            if [ "${agentwork:-0}" -gt 0 ] && [ -n "$mins" ]; then
                case "${devs:-0}" in
                    1) fleet="on the ONE handheld still serving (the other is held or down)" ;;
                    0) fleet="but NO device lane is alive -- nothing will drain this queue" ;;
                    *) fleet="across ${devs} handhelds" ;;
                esac
                hint="$(printf '%s' "$cov" | sed -n 1p). DEVICE-BOUND: ~${mins} min of arms queued ${fleet}, and nothing uncovered, so there is nothing to fold or claim -- holding is correct. Fold results as they land."
            else
                # DO NOT ADVISE WORK THAT IS ALREADY RUNNING.
                #
                # This branch told the orchestrator to "fold a FINISHED lane,
                # claim a free file, or collect_sweep.sh" eight times in a row
                # on 2026-09-14 while three lanes were mid-flight, a 100-suite
                # sweep was draining, and every one of those three actions had
                # either just been done or would have collided with a live
                # lane. The advice was generic because it was computed from
                # coverage alone, and coverage cannot see a lane that is
                # WORKING -- only one that is CLAIMED.
                #
                # The queue being empty of agent requests does not mean the
                # fleet is idle: a lane spends most of its life reading code
                # and building, and queues an arm once.
                #
                # So count what is actually claimed, and say that instead.
                # A lane that has reported is retired by the orchestrator and
                # its files released, so a standing claim IS work in progress.
                lanes=$(grep -c '^\[lane\.' "$HERE/territory.toml" 2>/dev/null || echo 0)
                heldn=$(python3 - "$HERE/territory.toml" <<'PYLANE' 2>/dev/null || echo 0
import sys, tomllib
d = tomllib.load(open(sys.argv[1], "rb"))
print(sum(len(m.get("files") or []) for m in (d.get("lane") or {}).values()))
PYLANE
)
                if [ "${lanes:-0}" -gt 0 ]; then
                    hint="$(printf '%s' "$cov" | sed -n 1p). ${lanes} lane(s) hold ${heldn} file(s) and have not reported, and ${sweep} sweep suite(s) are still draining -- so there is nothing FINISHED to fold, and claiming a file now would collide with a live lane. Holding is correct; fold each lane as it reports and release what its result did not need."
                else
                    hint="$(printf '%s' "$cov" | sed -n 1p). Nothing is uncovered, no arms are queued and NO lane is claimed, so the next move is a free file in territory.toml to claim, or collect_sweep.sh."
                fi
            fi ;;
    esac

    armed=0
    echo "IDLE ${idle}s with ${count} issues open -- ${running} device run(s) in flight, ${agentwork} agent request(s) queued, ${sweep} sweep request(s) left. ${hint}"
done
