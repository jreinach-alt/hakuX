# Sourced by ../selftest.sh with the harness already built: $T, $HERE, $REPO,
# $TESTING, the shims on PATH, ok/bad/check. Not executable, no shebang, no
# exit -- `fail` is shared and is the run's verdict.
#
# #507: every lane ran on MODEL_LANE (Opus) whatever its work -- measurement
# bookkeeping and harness plumbing costing the same session as JIT or shader
# engineering -- and a lane started on the cheaper model still drifted back to
# Opus at its first resume, because next_attempt() only ever read HAKUX_MODEL
# (which does not survive a resume) and the escalation counter.
# $WORK/briefs/<name>.model is the fix: one line, read ahead of MODEL_LANE on
# every start AND every resume. Proven here against a throwaway origin --
# lane.sh's systemd-run is the global shim selftest.sh installs on $T/bin,
# which logs the whole command line to $SELFTEST_GH_LOG, so the --model
# argument actually spawned is the oracle, not anything read back out of
# lane.sh's own variables.
#
# 99 because it depends on the harness only (git, the real jobs/ and
# lane.sh), touches no other fragment's state, and reads the real board the
# way 96-fleet-registry.sh and 98-lane-shape.sh already do (no HAKUX_TERRITORY
# set): refuse_if_remote asks about a lane name ("modellane", "auditmodel")
# no territory row anywhere names, so it always falls through.

echo "== lane.sh: \$WORK/briefs/<name>.model persists the model across a resume"
LM="$T/lanemodel"; rm -rf "$LM"; mkdir -p "$LM/work/briefs" "$LM/dispatch"
git init -q -b master "$LM/origin"
git -C "$LM/origin" -c user.email=s@t -c user.name=s commit -q --allow-empty -m base
git clone -q "$LM/origin" "$LM/repo"
printf '# a brief for the model-file selftest\n' > "$LM/brief.md"

# THE ORACLE. `--model 'X'` on the systemd-run line the global shim logged,
# last match: a log that is truncated before every run (below) never has more
# than one, but `resume` appends to a filename all its own too.
lm_model() { sed -n "s/.*--model '\([^']*\)'.*/\1/p" "$1" | tail -1; }

# A REAL start (or, with $4=resume, a real resume), against $lsh's lane.sh --
# the production one for the positive legs, a mutated copy for the negatives.
# Each start is from nothing, as 99-limits-env.sh's le_run is: lane.sh exits
# 3 on an existing worktree and refuses a branch already there, either one
# ending the run BEFORE systemd-run, which every read of an empty log would
# misreport as a pass.
lm_fresh() {
    git -C "$LM/repo" worktree remove --force "$LM/work/wt/modellane" 2>/dev/null
    rm -rf "$LM/work/wt/modellane" "$LM/work/attempts/modellane" "$LM/work/briefs/modellane."*
    git -C "$LM/repo" worktree prune 2>/dev/null
    git -C "$LM/repo" branch -qD lane/modellane 2>/dev/null
}
lm_start() {   # <lane.sh> <log> <model-file-contents-or-""> [extra env=val ...]
    local lsh=$1 log=$2 mf=$3; shift 3
    [ -n "$mf" ] && printf '%s\n' "$mf" > "$LM/work/briefs/modellane.model"
    : > "$log"
    ( env -u HAKUX_MODEL "$@" \
        HAKUX_WORK="$LM/work" HAKUX_REPO_DIR="$LM/repo" DISPATCH_DIR="$LM/dispatch" \
        SELFTEST_GH_LOG="$log" \
        bash "$lsh" start modellane "$LM/brief.md" 9401 ) >/dev/null 2>&1
}
lm_resume() {   # <lane.sh> <log> [extra env=val ...] -- modellane must already have a worktree+brief
    local lsh=$1 log=$2; shift 2
    : > "$log"
    ( env -u HAKUX_MODEL "$@" \
        HAKUX_WORK="$LM/work" HAKUX_REPO_DIR="$LM/repo" DISPATCH_DIR="$LM/dispatch" \
        SELFTEST_GH_LOG="$log" \
        bash "$lsh" resume modellane ) >/dev/null 2>&1
}
lm_default=$( . "$HERE/models.env"; echo "$MODEL_LANE" )

# ------------------------------------------------------------- the four legs
lm_fresh
lm_start "$TESTING/lane.sh" "$LM/start.log" claude-sonnet-5
check "a start with a .model file uses it, not MODEL_LANE" \
    [ "$(lm_model "$LM/start.log")" = claude-sonnet-5 ]
lm_resume "$TESTING/lane.sh" "$LM/resume.log"
check "a resume of that lane ALSO uses the persisted .model file" \
    [ "$(lm_model "$LM/resume.log")" = claude-sonnet-5 ]

lm_fresh
lm_start "$TESTING/lane.sh" "$LM/override.log" claude-sonnet-5 HAKUX_MODEL=claude-fable-5-1
check "HAKUX_MODEL still overrides the .model file, for that one start" \
    [ "$(lm_model "$LM/override.log")" = claude-fable-5-1 ]

lm_fresh
lm_start "$TESTING/lane.sh" "$LM/nofile.log" ""
check "with no .model file, MODEL_LANE (\$lm_default) is what starts" \
    [ "$(lm_model "$LM/nofile.log")" = "$lm_default" ]

# ----------------------------------------------- usage Low, read at every start
# jobs/usage/mode.sh only creates or removes $WORK/usage/low-active; lane.sh
# applies Low itself, so the .model file keeps saying what the brief wants.
mkdir -p "$LM/work/usage"; echo "selftest: low" > "$LM/work/usage/low-active"
lm_fresh
lm_start "$TESTING/lane.sh" "$LM/low.log" claude-opus-5-5
check "usage Low: a lane whose .model is Opus starts on Sonnet" \
    [ "$(lm_model "$LM/low.log")" = claude-sonnet-5 ]
lm_fresh
lm_start "$TESTING/lane.sh" "$LM/lowover.log" claude-opus-5-5 HAKUX_MODEL=claude-fable-5-1
check "usage Low: an explicit HAKUX_MODEL still wins" \
    [ "$(lm_model "$LM/lowover.log")" = claude-fable-5-1 ]
rm -f "$LM/work/usage/low-active"
lm_fresh
lm_start "$TESTING/lane.sh" "$LM/lowoff.log" claude-opus-5-5
check "low-active gone: the same .model starts on Opus again, nothing to restore" \
    [ "$(lm_model "$LM/lowoff.log")" = claude-opus-5-5 ]

# ------------------------------------------------------------------ mutants
# One per leg above, made by editing a COPY OF lane.sh LEFT IN PLACE beside
# the real one, not a copy of the whole jobs/ tree. lane.sh finds its jobs/
# (models.env, window.sh, remote-lane.sh) at "$(dirname lane.sh)/jobs" --
# relative to wherever it is RUN FROM -- and remote-lane.sh in turn finds
# board_files.py at ITS OWN "$(dirname remote-lane.sh)/.." and hands that path
# to `git -C` to read origin/board. A first version of this copied the whole
# jobs/ directory into scratch so the mutated lane.sh would find its siblings:
# that put a COPY of remote-lane.sh two directories away from a real git
# checkout, `git -C <scratch>/jobs show origin/board:...` failed outright
# ("not a git repository"), and remote-lane.sh's own safe-by-construction
# answer to "I could not read the board" is REFUSED -- so every mutant run
# exited before systemd-run, every log stayed EMPTY, and `[ "$(lm_model
# empty-log)" = claude-sonnet-5 ]` was false for a reason that had nothing to
# do with the mutation: three of the four "is red" checks below passed
# against a script that never ran at all. Only the one check that asserted
# EQUALITY to a real value (not an "!= " on a mutant) caught it, by failing.
# So: the mutated file lives directly beside lane.sh in $TESTING, its jobs/
# is the real one, and only the ONE FILE is a copy.
lm_mutant() {   # <name> <sed-expr> -> path to a mutated lane.sh, living in $TESTING itself
    local f="$TESTING/.selftest-mutlane-$1.sh"
    cp "$TESTING/lane.sh" "$f"
    sed -i "$2" "$f"
    echo "$f"
}
lm_differs() { ! cmp -s "$1" "$TESTING/lane.sh"; }

# MUTANT: drop Low's model cap. The Low leg must go red.
m=$(lm_mutant nolowcap 's/MODEL=\$LOW_MODEL ;;/;;/')
check "mutant nolowcap: dropping the cap assignment, the sed applied" lm_differs "$m"
echo "selftest: low" > "$LM/work/usage/low-active"
lm_fresh; lm_start "$m" "$LM/mutlow.log" claude-opus-5-5
rm -f "$LM/work/usage/low-active"
if [ "$(lm_model "$LM/mutlow.log")" = claude-sonnet-5 ]; then
    bad "mutant nolowcap: an Opus lane still starts on Sonnet under Low"
elif [ "$(lm_model "$LM/mutlow.log")" = claude-opus-5-5 ]; then
    ok "mutant nolowcap: the lane starts on Opus, and the Low leg is red"
else
    bad "mutant nolowcap: the mutant start never reached systemd-run (empty log), so it proves nothing"
fi
rm -f "$m"

# MUTANT 1: drop the read of the .model file entirely. Kills the start leg
# (and would kill the resume leg too, which is exactly why mutant 2 below is
# a DIFFERENT edit -- so the resume leg is shown to be testing something the
# start leg does not already cover).
m=$(lm_mutant nofileread '/\[ -f "\$mf" \] && lane_model=\$(head -1 "\$mf")/d')
check "mutant nofileread: dropping the .model read line, the sed applied" lm_differs "$m"
lm_fresh; lm_start "$m" "$LM/mut1.log" claude-sonnet-5
if [ "$(lm_model "$LM/mut1.log")" = claude-sonnet-5 ]; then
    bad "mutant nofileread: a start still honours the .model file"
else
    ok "mutant nofileread: the file is ignored, and the start leg is red"
fi
rm -f "$m"

# MUTANT 2: THE ACTUAL #507 REGRESSION, reintroduced only in `resume)`. Every
# start still reads the file; a resume forces MODEL back to MODEL_LANE right
# after next_attempt, which is precisely "next_attempt() falls back to
# MODEL_LANE on every lane.sh resume" from the issue. The start leg above must
# stay green against this mutant, or it is not isolating resume at all.
m=$(lm_mutant resumedrop '/^  resume)/,/^  rm)/ s/next_attempt "\$name" || exit 75/&; MODEL="${HAKUX_MODEL:-$MODEL_LANE}"/')
check "mutant resumedrop: forcing MODEL_LANE back in on resume, the sed applied" lm_differs "$m"
lm_fresh; lm_start "$m" "$LM/mut2-start.log" claude-sonnet-5
check "  ...and does not touch the start leg, which is still on the .model file" \
    [ "$(lm_model "$LM/mut2-start.log")" = claude-sonnet-5 ]
lm_resume "$m" "$LM/mut2-resume.log"
if [ "$(lm_model "$LM/mut2-resume.log")" = claude-sonnet-5 ]; then
    bad "mutant resumedrop: a resume still honours the .model file"
else
    ok "mutant resumedrop: a resume falls back to MODEL_LANE, and the resume leg is red"
fi
rm -f "$m"

# MUTANT 3: drop the HAKUX_MODEL layer from the non-escalated branch.
m=$(lm_mutant nooverride 's/MODEL="\${HAKUX_MODEL:-\${lane_model:-\$MODEL_LANE}}"/MODEL="\${lane_model:-\$MODEL_LANE}"/')
check "mutant nooverride: dropping the HAKUX_MODEL layer, the sed applied" lm_differs "$m"
lm_fresh; lm_start "$m" "$LM/mut3.log" claude-sonnet-5 HAKUX_MODEL=claude-fable-5-1
if [ "$(lm_model "$LM/mut3.log")" = claude-fable-5-1 ]; then
    bad "mutant nooverride: HAKUX_MODEL still wins"
else
    ok "mutant nooverride: HAKUX_MODEL is ignored, and the override leg is red"
fi
rm -f "$m"

# MUTANT 4: the no-file default silently becomes the escalated model instead
# of MODEL_LANE.
m=$(lm_mutant wrongdefault 's/\${lane_model:-\$MODEL_LANE}/\${lane_model:-\$MODEL_LANE_ESCALATED}/')
check "mutant wrongdefault: swapping the no-file default, the sed applied" lm_differs "$m"
lm_fresh; lm_start "$m" "$LM/mut4.log" ""
if [ "$(lm_model "$LM/mut4.log")" = "$lm_default" ]; then
    bad "mutant wrongdefault: the no-file default is still MODEL_LANE"
else
    ok "mutant wrongdefault: the no-file default drifted, and that leg is red"
fi
rm -f "$m"

lm_fresh
rm -f "$TESTING"/.selftest-mutlane-*.sh   # defensive: nothing left in the real tree even on an early return above
unset -f lm_model lm_fresh lm_start lm_resume lm_mutant lm_differs

# ----------------------------------------------- cloud.sh: audits sized to the diff
echo "== cloud.sh: pass 2 runs on MODEL_BOOKKEEPING when pass 1 found nothing"
# A real claim of a needs-audit-2 PR against a throwaway origin, in the same
# shape as 99-limits-env.sh's LEC fixture: a bare origin, a lane branch, a gh
# shim answering the exact calls cloud.sh makes. The decision this section
# proves lane.sh's oracle cannot reach cloud.sh's for -- cloud.sh reads the
# pass-1 audit file OUT OF THE WORKTREE IT JUST CHECKED OUT, which nothing
# selftest.sh seeds, so this builds its own.
CM="$T/cloudmodel"; rm -rf "$CM"; mkdir -p "$CM/work/briefs" "$CM/bin"
cat > "$CM/bin/gh" <<'EOF'
#!/usr/bin/env bash
echo "$*" >> "${SELFTEST_GH_LOG:?}"
args="$*"
case "$1 $2" in
    "pr list")
        [[ "$args" == *"--label needs-audit-2"* ]] && { printf '%s\n' "${CM_ROW:?}"; exit 0; }
        exit 0 ;;
    "issue list") exit 0 ;;
    "pr view")
        echo '{"body": "Lane: auditmodel          Issue: #9402", "closingIssuesReferences": [], "files": []}'
        exit 0 ;;
    "pr comment"|"issue comment") exit 0 ;;
    "api "*)
        [[ "$args" == *"/pulls/"* ]] && { echo "${CM_HEAD:?}"; exit 0; }
        [[ "$args" == *"/labels"* && "$args" != *"-X"* ]] && exit 0
        exit 0 ;;
esac
exit 0
EOF
cat > "$CM/bin/systemctl" <<'EOF'
#!/usr/bin/env bash
exit 0
EOF
cat > "$CM/bin/systemd-run" <<'EOF'
#!/usr/bin/env bash
echo "systemd-run $*" >> "${CM_LOG:?}"
exit 0
EOF
chmod +x "$CM/bin/"*

git init -q --bare "$CM/origin.git"
git init -q "$CM/repo"
cm() { git -C "$CM/repo" -c user.email=s@t -c user.name=s "$@"; }
cm remote add origin "$CM/origin.git"
cm checkout -q -b master
echo trunk > "$CM/repo/README.md"; cm add -A; cm commit -qm trunk; cm push -q origin master
cm checkout -q -b lane/auditmodel
mkdir -p "$CM/repo/docs/audits"
cm_pass1() {   # <body after the heading line> <commit tag, also written into the file so each push actually changes it>
    { echo "# Audit pass 1 -- PR #601, lane.auditmodel (#9402)"; echo "<!-- $2 -->"; echo; printf '%s\n' "$1"; } \
        > "$CM/repo/docs/audits/2026-09-01-auditmodel-pass1.md"
    cm add -A; cm commit -qm "audit: pass1 ($2)" >/dev/null; cm push -q origin lane/auditmodel
}
cm_pass1 $'**Verdict: no HIGH, no MEDIUM, one LOW.**\n\n## LOW-1: cosmetic\nNo failure scenario.' clean

cm_run() {   # <log> <cloud.sh path> [extra env=val ...] -- a real cloud.sh claim of PR #601
    local log=$1 csh=$2; shift 2
    git -C "$CM/repo" worktree remove --force "$CM/work/wt/cloud-audit2-601" 2>/dev/null
    rm -rf "$CM/work/wt/cloud-audit2-601" "$CM/work/attempts/cloud-audit2-601"
    git -C "$CM/repo" worktree prune 2>/dev/null
    : > "$log"
    ( env -u HAKUX_MODEL "$@" \
        PATH="$CM/bin:$PATH" HAKUX_WORK="$CM/work" HAKUX_REPO_DIR="$CM/repo" GH_REPO="example/hakux" \
        CM_HEAD="lane/auditmodel" CM_ROW=$'601\tlane/auditmodel\taudit model test PR' \
        CM_LOG="$log" SELFTEST_GH_LOG="$CM/gh.log" \
        bash "$csh" ) >/dev/null 2>&1
}
lm_model() { sed -n "s/.*--model '\([^']*\)'.*/\1/p" "$1" | tail -1; }
cm_default=$( . "$HERE/models.env"; echo "$MODEL_AUDIT" )
cm_book=$( . "$HERE/models.env"; echo "$MODEL_BOOKKEEPING" )

cm_run "$CM/clean.log" "$HERE/cloud.sh"
check "pass 1 with no HIGH/MEDIUM: audit2 runs on MODEL_BOOKKEEPING" \
    [ "$(lm_model "$CM/clean.log")" = "$cm_book" ]

cm_pass1 $'**Verdict: 1 MEDIUM, 1 LOW → needs-remediation, then remediated.**\n\n## MEDIUM 1: a real defect\nScenario: it fires when...' dirty
cm_run "$CM/dirty.log" "$HERE/cloud.sh"
check "pass 1 (or the remediation since) found a MEDIUM: audit2 stays on MODEL_AUDIT" \
    [ "$(lm_model "$CM/dirty.log")" = "$cm_default" ]

cm_pass1 $'**Verdict: no HIGH, no MEDIUM, one LOW.**\n\n## LOW-1: cosmetic\nNo failure scenario.' clean-again
cm_run "$CM/hakuxmodel.log" "$HERE/cloud.sh" HAKUX_MODEL=claude-fable-5-1
check "HAKUX_MODEL still overrides the pass-2 sizing too" \
    [ "$(lm_model "$CM/hakuxmodel.log")" = claude-fable-5-1 ]

# ------------------------------------------------------------------- mutant
cm_mutant() {   # <name> <sed-expr> -> path to a mutated cloud.sh, lane.sh and jobs/ alongside
    rm -rf "$CM/mut-$1"; mkdir -p "$CM/mut-$1/jobs"
    cp -r "$HERE/." "$CM/mut-$1/jobs/"
    cp "$TESTING/lane.sh" "$CM/mut-$1/lane.sh"
    sed -i "$2" "$CM/mut-$1/jobs/cloud.sh"
    echo "$CM/mut-$1/jobs/cloud.sh"
}
cm_differs() { ! cmp -s "$1" "$HERE/cloud.sh"; }
m=$(cm_mutant nosizing '/# AUDITS SIZED TO THE DIFF/,/^        fi$/d')
check "mutant nosizing: dropping the whole sizing block, the sed applied" cm_differs "$m"
cm_pass1 $'**Verdict: no HIGH, no MEDIUM, one LOW.**\n\n## LOW-1: cosmetic\nNo failure scenario.' clean-again
cm_run "$CM/mutclean.log" "$m"
if [ "$(lm_model "$CM/mutclean.log")" = "$cm_book" ]; then
    bad "mutant nosizing: a clean pass 1 still downgrades to MODEL_BOOKKEEPING"
else
    ok "mutant nosizing: a clean pass 1 stays on MODEL_AUDIT, and this leg is red"
fi

git -C "$CM/repo" worktree remove --force "$CM/work/wt/cloud-audit2-601" 2>/dev/null
unset -f lm_model cm cm_pass1 cm_run cm_mutant cm_differs
