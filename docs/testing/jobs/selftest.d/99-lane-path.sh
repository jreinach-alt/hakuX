# Sourced by ../selftest.sh with the harness already built: $T, $HERE, $REPO,
# $TESTING, the shims on PATH, ok/bad/check. Not executable, no shebang, no
# exit -- `fail` is shared and is the run's verdict.
#
# lane.sh's start and resume systemd-run blocks now carry --setenv=PATH, so a
# lane unit's PATH no longer depends on whatever the systemd --user manager
# happened to hold when it spawned (#433; see lane.sh's own LANE_SHIM_BIN
# comment for the 2026-10-09 WSL-crash incident this closes). Proven here
# against a throwaway origin, the same way 99-lane-model-file.sh proves the
# .model file: lane.sh's systemd-run is the global shim selftest.sh installs
# on $T/bin, which logs the whole command line to $SELFTEST_GH_LOG, so the
# --setenv=PATH argument actually spawned is the oracle, not anything read
# back out of lane.sh's own variables.
#
# 99 because it depends on the harness only (git, the real jobs/ and
# lane.sh), touches no other fragment's state, and reads the real board the
# way 96-fleet-registry.sh and 98-lane-shape.sh already do (no HAKUX_TERRITORY
# set): refuse_if_remote asks about a lane name ("pathlane") no territory row
# anywhere names, so it always falls through.
#
# WHY THIS FRAGMENT MAKES ITS OWN $WORK/forge/shim/bin. lane.sh now REFUSES
# (exit 78) to start or resume a lane when that directory is missing, and no
# existing selftest fixture creates it -- measured by running
# 96-fleet-registry.sh, 88-window-budget.sh and the 99-handback-*.sh family in
# isolation against this change: 47 checks across those files went red,
# every one of them because the fixture's $WORK never had a shim directory
# and lane.sh refused before systemd-run ever ran. Those files are outside
# this lane's territory (docs/testing/lane.sh and this file only) and are not
# touched here; see docs/lanes/lanepath1009/NOTES.md for the full count and
# the one-line fix each of them needs. This fragment's own fixture creates
# the directory precisely so its positive legs are not testing the refusal by
# accident, and has one leg that removes it on purpose to test the refusal on
# purpose.

echo "== lane.sh: a lane unit's PATH puts the forge shim first, from one definition"
LP="$T/lanepath"; rm -rf "$LP"; mkdir -p "$LP/work/briefs" "$LP/dispatch"
git init -q -b master "$LP/origin"
git -C "$LP/origin" -c user.email=s@t -c user.name=s commit -q --allow-empty -m base
git clone -q "$LP/origin" "$LP/repo"
printf '# a brief for the lane-path selftest\n' > "$LP/brief.md"
LP_SHIM="$LP/work/forge/shim/bin"

# THE ORACLE. The --setenv=PATH=<value> argument systemd-run actually got, as
# ONE unquoted argv word (lane.sh's own "$LANE_PATH" expansion happens in its
# OUTER double-quoted systemd-run argument, not inside the bash -c string, so
# no literal quote characters land in the log around it -- unlike --model
# 'X', which IS inside that string and is quoted there in lane.sh's own text).
lp_path() { grep -oE -- '--setenv=PATH=[^ ]*' "$1" | tail -1 | sed 's/^--setenv=PATH=//'; }
lp_shim_first() { case "$(lp_path "$1")" in "$LP_SHIM:"*) return 0 ;; *) return 1 ;; esac; }
lp_footer() { grep -qF 'ends the moment this turn ends' "$1"; }
lp_reached_run() { [ -s "$1" ] && grep -q -- '--setenv=HAKUX_ROLE=lane' "$1"; }   # not an early-exit empty log

lp_fresh() {
    git -C "$LP/repo" worktree remove --force "$LP/work/wt/pathlane" 2>/dev/null
    rm -rf "$LP/work/wt/pathlane" "$LP/work/attempts/pathlane" "$LP/work/briefs/pathlane."*
    git -C "$LP/repo" worktree prune 2>/dev/null
    git -C "$LP/repo" branch -qD lane/pathlane 2>/dev/null
}
lp_start() {   # <lane.sh> <log> -> exit code of the start, via $LP_RC
    local lsh=$1 log=$2
    : > "$log"
    ( env HAKUX_WORK="$LP/work" HAKUX_REPO_DIR="$LP/repo" DISPATCH_DIR="$LP/dispatch" \
          SELFTEST_GH_LOG="$log" \
          bash "$lsh" start pathlane "$LP/brief.md" 9401 ) >/dev/null 2>"$log.err"
    LP_RC=$?
}
lp_resume() {   # <lane.sh> <log> -- pathlane must already have a worktree+brief
    local lsh=$1 log=$2
    : > "$log"
    ( env HAKUX_WORK="$LP/work" HAKUX_REPO_DIR="$LP/repo" DISPATCH_DIR="$LP/dispatch" \
          SELFTEST_GH_LOG="$log" \
          bash "$lsh" resume pathlane ) >/dev/null 2>"$log.err"
    LP_RC=$?
}

# ------------------------------------------------- the shim present: the happy path
mkdir -p "$LP_SHIM"
lp_fresh
lp_start "$TESTING/lane.sh" "$LP/start.log"
check "a real start's --setenv=PATH puts the forge shim dir first" lp_shim_first "$LP/start.log"
check "...and the start actually reached systemd-run (not an early exit)" lp_reached_run "$LP/start.log"
check "the start's prompt carries the headless-session footer" lp_footer "$LP/start.log"
START_PATH=$(lp_path "$LP/start.log")

lp_resume "$TESTING/lane.sh" "$LP/resume.log"
check "a resume's --setenv=PATH ALSO puts the forge shim dir first" lp_shim_first "$LP/resume.log"
check "the resume's prompt carries the headless-session footer too" lp_footer "$LP/resume.log"
lp_same_path() { [ -n "$1" ] && [ "$1" = "$2" ]; }
check "resume's PATH is byte-identical to start's -- one definition, not two" \
    lp_same_path "$START_PATH" "$(lp_path "$LP/resume.log")"

# STRUCTURAL: a value computed twice can still agree today and drift the next
# time only one copy is edited, which the equality check above cannot see in
# advance. Anchored on the assignment (like 99-limits-env.sh's le_order), not
# on nearby prose, which would also match this comment block's own mentions.
lp_one() { [ "$(grep -c "^$2" "$1")" = 1 ]; }
check "lane.sh has exactly one LANE_SHIM_BIN= assignment" lp_one "$TESTING/lane.sh" 'LANE_SHIM_BIN='
check "lane.sh has exactly one LANE_PATH_TAIL= assignment" lp_one "$TESTING/lane.sh" 'LANE_PATH_TAIL='
check "lane.sh has exactly one lane_path() definition" lp_one "$TESTING/lane.sh" 'lane_path() {'
check "lane.sh has exactly one LANE_SESSION_FOOTER= assignment" lp_one "$TESTING/lane.sh" 'LANE_SESSION_FOOTER='

# ------------------------------------------------- the shim missing: refuse, don't start
rm -rf "$LP_SHIM"
lp_fresh
lp_start "$TESTING/lane.sh" "$LP/norefuse-start.log"
check "no shim: start refuses (exit 78), not any other code" [ "$LP_RC" = 78 ]
check "no shim: start never reached systemd-run (log stays empty)" [ ! -s "$LP/norefuse-start.log" ]
check "no shim: start says so on stderr" grep -q 'REFUSED.*forge shim' "$LP/norefuse-start.log.err"

mkdir -p "$LP_SHIM"; lp_fresh; lp_start "$TESTING/lane.sh" "$LP/setup-for-resume.log"
rm -rf "$LP_SHIM"
lp_resume "$TESTING/lane.sh" "$LP/norefuse-resume.log"
check "no shim: resume ALSO refuses (exit 78)" [ "$LP_RC" = 78 ]
check "no shim: resume never reached systemd-run either" [ ! -s "$LP/norefuse-resume.log" ]
mkdir -p "$LP_SHIM"

# ------------------------------------------------------------------ mutants
# One file, mutated and left beside the real lane.sh (not a copy of the whole
# jobs/ tree): 99-lane-model-file.sh's lm_mutant comment explains why a copy
# of jobs/ breaks remote-lane.sh's own relative paths and makes every mutant
# run exit before systemd-run, which would read as a false red here too.
lp_mutant() {   # <name> <sed-expr> -> path to a mutated lane.sh, living in $TESTING itself
    local f="$TESTING/.selftest-mutlane-path-$1.sh"
    cp "$TESTING/lane.sh" "$f"
    sed -i "$2" "$f"
    echo "$f"
}
lp_differs() { ! cmp -s "$1" "$TESTING/lane.sh"; }

# MUTANT (a): --setenv=PATH dropped from the resume block only.
m=$(lp_mutant noresumepath '/^  resume)/,/^  rm)/ { /--setenv=PATH="\$LANE_PATH"/d }')
check "mutant (a) noresumepath: the sed applied" lp_differs "$m"
lp_fresh; lp_start "$m" "$LP/muta-start.log"
check "  ...and does not touch the start leg" lp_shim_first "$LP/muta-start.log"
lp_resume "$m" "$LP/muta-resume.log"
check "  ...and resume still reached systemd-run (not an early exit)" lp_reached_run "$LP/muta-resume.log"
if grep -q -- '--setenv=PATH=' "$LP/muta-resume.log"; then
    bad "mutant (a) noresumepath: resume still sets PATH explicitly"
else
    ok "mutant (a) noresumepath: resume's --setenv=PATH is gone, and the resume leg is red"
fi
rm -f "$m"

# MUTANT (b): the weaker rule reinstated -- the caller's own $PATH, not LANE_PATH.
m=$(lp_mutant callerpath 's/--setenv=PATH="\$LANE_PATH"/--setenv=PATH="\$PATH"/g')
check "mutant (b) callerpath: the sed applied" lp_differs "$m"
lp_fresh; lp_start "$m" "$LP/mutb-start.log"
check "  ...start still reached systemd-run" lp_reached_run "$LP/mutb-start.log"
if lp_shim_first "$LP/mutb-start.log"; then
    bad "mutant (b) callerpath: the shim dir is still first -- the caller's \$PATH happened to agree"
else
    ok "mutant (b) callerpath: PATH is the caller's own (shim not first), and this leg is red"
fi
rm -f "$m"

# MUTANT (c): the shim dir moved after /usr/bin.
m=$(lp_mutant shimafter 's#LANE_PATH="\$LANE_SHIM_BIN:\$LANE_PATH_TAIL"#LANE_PATH="/home/justin/.local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:\$LANE_SHIM_BIN:/sbin:/bin:/snap/bin"#')
check "mutant (c) shimafter: the sed applied" lp_differs "$m"
lp_fresh; lp_start "$m" "$LP/mutc-start.log"
check "  ...start still reached systemd-run" lp_reached_run "$LP/mutc-start.log"
if lp_shim_first "$LP/mutc-start.log"; then
    bad "mutant (c) shimafter: the shim dir is still read as first"
else
    ok "mutant (c) shimafter: the shim dir sits after /usr/bin, and this leg is red"
fi
rm -f "$m"

# MUTANT (d), Addendum 1: the headless-session footer dropped from resume only.
m=$(lp_mutant noresumefooter '/^  resume)/,/^  rm)/ s/\$LANE_SESSION_FOOTER\\"/\\"/')
check "mutant (d) noresumefooter: the sed applied" lp_differs "$m"
lp_fresh; lp_start "$m" "$LP/mutd-start.log"
check "  ...and does not touch the start leg's footer" lp_footer "$LP/mutd-start.log"
lp_resume "$m" "$LP/mutd-resume.log"
check "  ...and resume still reached systemd-run" lp_reached_run "$LP/mutd-resume.log"
if lp_footer "$LP/mutd-resume.log"; then
    bad "mutant (d) noresumefooter: resume's prompt still carries the footer"
else
    ok "mutant (d) noresumefooter: resume's footer is gone, and this leg is red"
fi
rm -f "$m"

lp_fresh
rm -f "$TESTING"/.selftest-mutlane-path-*.sh   # defensive: nothing left in the real tree even on an early return above
rm -rf "$LP_SHIM"
unset -f lp_path lp_shim_first lp_footer lp_reached_run lp_fresh lp_start lp_resume lp_one lp_mutant lp_differs lp_same_path
unset LP_SHIM LP_RC START_PATH
