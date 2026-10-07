# Sourced by ../../testing/jobs/selftest.sh with the harness already built: $T, $HERE, $REPO,
# ok/bad/check. Not executable, no shebang, no exit (see 59-hangwatch.sh).
#
# SCRATCH LOCATION (lane.stuckdetect1007, #433): this leg lives under docs/lanes/stuckdetect1007/
# until a grant moves it (and stuckdetect.py) to docs/testing/jobs/selftest.d/ -- see OUTBOX.md
# for the exact destination paths and the pathfind.py integration this is standing in for.
#
# stuckdetect.py: a stuck/menu detector for pathfind's 600-s hold, built because three Nova runs
# on 2026-10-07 burned 30-40 min each stuck in a wall or a shop menu the existing checks did not
# catch (NOTES.md has the numbers). Its own `selftest` is stdlib-only (synthetic signatures, no
# image decode, so this runs on the CI selftest runner which has neither PIL nor numpy); `validate`
# replays the real stored hold runs and needs both plus the run dirs on this host, so it only
# ever skips or passes here, never fails the leg on a host that lacks either.

echo "== stuckdetect: a stuck/menu detector for pathfind's hold (#433)"

SD="$REPO/docs/lanes/stuckdetect1007/stuckdetect.py"

check "stuckdetect selftest passes (synthetic signatures, no image decode, stdlib only)" \
    python3 "$SD" selftest

# `validate` is diagnostic, not a gate: it prints the must-flag/must-not-flag table against
# lane.pathfind's stored hold runs when they and PIL/numpy are both on this host, and "skip"
# otherwise. Shown directly (not swallowed by `check`) so the table is visible in the log; only
# a real separation failure (every run present, but a must-flag run clears or a must-not-flag
# run flags) turns this leg red.
SD_OUT="$T/stuckdetect-validate.out"
python3 "$SD" validate > "$SD_OUT" 2>&1
SD_RC=$?
cat "$SD_OUT"
if [ "$SD_RC" = 0 ]; then
    ok "stuckdetect validate: skip or all correct (rc 0)"
else
    bad "stuckdetect validate: SEPARATION FAILED (rc $SD_RC) -- see the table above"
fi

# Mutants: each must turn `selftest` red, built as a one-off source patch (python3 str.replace),
# the same technique 84-perf-regimen.sh uses -- never edits the real module.
SD_MUT="$T/stuckdetect-mutant.py"
stuckdetect_mutant() {   # <name> <old> <new>
    local name="$1" old="$2" new="$3"
    if ! grep -qF "$old" "$SD"; then
        bad "stuckdetect mutant '$name': its anchor is gone from stuckdetect.py -- update the mutant"
        return
    fi
    python3 -c 'import sys; s=open(sys.argv[1]).read(); open(sys.argv[2],"w").write(s.replace(sys.argv[3], sys.argv[4], 1))' \
        "$SD" "$SD_MUT" "$old" "$new"
    if python3 "$SD_MUT" selftest >/dev/null 2>&1; then
        bad "stuckdetect mutant '$name' SURVIVED (selftest still passed)"
    else
        ok "stuckdetect mutant '$name' is caught"
    fi
}

# Mutant 1: the fix removed outright -- stuck_run never reports a run beyond 1, so is_stuck
# never trips at all. Everything downstream (menu_stuck, stuck_step) goes with it.
stuckdetect_mutant "fix removed: stuck_run never reports a run" \
"    run = 1
    for i in range(len(history) - 1, 0, -1):
        if near_identical(history[i], history[i - 1], grid_bar, hist_bar):
            run += 1
        else:
            break
    return run" \
"    return 1"

# Mutant 2: the weaker rule a prior check used, reinstated -- first vs last only, exactly what
# hitch_report.position_fail's first_last test does on the offline verdict. This is the Arx
# Fatalis bug: a drifting-but-stuck wall view clears a first-vs-last check and must not clear
# this module's own trailing-run test.
stuckdetect_mutant "weaker rule reinstated: first-vs-last only" \
"    run = 1
    for i in range(len(history) - 1, 0, -1):
        if near_identical(history[i], history[i - 1], grid_bar, hist_bar):
            run += 1
        else:
            break
    return run" \
"    if near_identical(history[0], history[-1], grid_bar, hist_bar):
        return len(history)
    return 1"
