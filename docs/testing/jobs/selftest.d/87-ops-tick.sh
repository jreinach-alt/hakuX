# Sourced by ../selftest.sh with the harness already built: $T, $HERE, $REPO,
# the shims on PATH, ok/bad/check. Not executable, no shebang, no exit.
#
# docs/testing/jobs/ops/ops_tick.py: the model-free replacement for hostops's
# $110/day model tick (#433). Everything here runs against its OWN fixture
# tree under $T/ops -- never the shared $DISPATCH_DIR/$HAKUX_WORK the other
# fragments use, and never the shared $T/bin/systemctl shim (it only knows
# `is-active` -> active; this job also needs list-timers/list-units shapes,
# so every systemctl call is routed through $OT_SYSTEMCTL instead).
#
# The world each leg checks:
#   (a) a device held past its stated bound by a dead lane's tag is released;
#       an owner-tagged hold (OWNER_HOLD_TAGS) past the same bound is not a jam.
#   (b) a stranded lane (PR.md still draft, no running unit) is resumed ONCE:
#       its brief gets an addendum and lane.sh resume is called exactly once
#       across two ticks, not once per tick; a lane with a STOPPED marker is
#       never resumed.
#   (c) fold-failures.log: a territory-gap FAILED line writes an inbox note; a
#       conflict FAILED line resumes the lane; a later FOLDED line for the
#       same branch clears the jam so a third tick does not act again.
#   (d) a failed hakux unit has no remedy and escalates on its very first
#       tick (not after 30 minutes) -- ops_escalate.sh is a fixture shim here,
#       never a real `claude -p` call.
#   (e) jams.tsv accumulates one row per (class, subject) and clears a row
#       once its detector stops reporting it.

echo "== ops_tick.py: model-free jam detection and scripted remedies (#433)"

OT_PY="$HERE/ops/ops_tick.py"
check "ops_tick.py parses (py_compile)" python3 -m py_compile "$OT_PY"

OT="$T/ops"; rm -rf "$OT"
mkdir -p "$OT/work/dispatch/hold" "$OT/work/dispatch/queue" "$OT/work/dispatch/running" \
         "$OT/work/briefs" "$OT/work/offline-git" "$OT/work/host-tools" "$OT/state" "$OT/bin" "$OT/repo"

# ------------------------------------------------------------- systemctl shim
# Controlled by three files ops_tick.py's shim-under-test never sees directly:
# $OT/bin/active-lanes (one lane name per line: is-active says "active"),
# $OT/bin/timers.txt (raw `list-timers` output), $OT/bin/failed-units.txt (raw
# `list-units --state=failed` output). Every call is logged to systemctl.log.
: > "$OT/bin/active-lanes"; : > "$OT/bin/timers.txt"; : > "$OT/bin/failed-units.txt"
cat > "$OT/bin/systemctl" <<'EOF'
#!/usr/bin/env bash
echo "$*" >> "$OT_SYSTEMCTL_LOG"
case "$*" in
    *is-active\ hakux-lane-*)
        lane="${*##*is-active hakux-lane-}"; lane="${lane%.service}"
        grep -qxF "$lane" "$OT_ACTIVE_LANES" 2>/dev/null && { echo active; exit 0; }
        echo inactive; exit 3 ;;
    *is-active*) echo inactive; exit 3 ;;
    *list-timers*) cat "$OT_TIMERS_FILE"; exit 0 ;;
    *list-units*--state=failed*) cat "$OT_FAILED_UNITS_FILE"; exit 0 ;;
    *start*--no-block*) exit 0 ;;
    *) exit 0 ;;
esac
EOF
chmod +x "$OT/bin/systemctl"
export OT_SYSTEMCTL_LOG="$OT/systemctl.log" OT_ACTIVE_LANES="$OT/bin/active-lanes" \
       OT_TIMERS_FILE="$OT/bin/timers.txt" OT_FAILED_UNITS_FILE="$OT/bin/failed-units.txt"
: > "$OT_SYSTEMCTL_LOG"

# -------------------------------------------------------- lane.sh / hold.sh shims
# Real hold.sh (take/release/wait-idle/who) against our own dispatch dir --
# that part of ops_tick.py is exercised for real, not faked.
OT_HOLD_SH="$HERE/hold.sh"
# lane.sh is faked: it only needs to prove it was called once per stranding,
# with the right name, and that a brief addendum landed first.
cat > "$OT/bin/lane.sh" <<'EOF'
#!/usr/bin/env bash
echo "$*" >> "$OT_LANE_LOG"
[ "$1" = resume ] && [ -f "$OT_WORK/briefs/$2.md" ] && exit 0
exit 3
EOF
chmod +x "$OT/bin/lane.sh"
export OT_LANE_LOG="$OT/lane.log"; : > "$OT_LANE_LOG"

# ops_escalate.sh is faked too: no real `claude -p` call from a selftest.
cat > "$OT/bin/ops_escalate.sh" <<'EOF'
#!/usr/bin/env bash
echo "$*" >> "$OT_ESCALATE_LOG"
echo "COST_USD=0.42"
EOF
chmod +x "$OT/bin/ops_escalate.sh"
export OT_ESCALATE_LOG="$OT/escalate.log"; : > "$OT_ESCALATE_LOG"

ot_env() {
    env OPS_SYSTEMCTL="$OT/bin/systemctl" HAKUX_WORK="$OT/work" HAKUX_REPO_DIR="$OT/repo" \
        DISPATCH_DIR="$OT/work/dispatch" OPS_STATE_DIR="$OT/state" \
        OPS_INBOX="$OT/work/host-tools/hostops-inbox.md" OPS_BRIEFS="$OT/work/briefs" \
        OPS_FOLD_FAILURES="$OT/work/offline-git/fold-failures.log" \
        OPS_DEVICE_REALITY="$OT/work/host-tools/.device-reality.json" \
        OPS_LANE_SH="$OT/bin/lane.sh" OPS_HOLD_SH="$OT_HOLD_SH" \
        OPS_JAMCHECK_SH="$OT/bin/true" OPS_ESCALATE_SH="$OT/bin/ops_escalate.sh" \
        OPS_DEVICES="thor,nova" OPS_ESCALATE_AFTER_MIN=30 OPS_HOLD_BOUND_MIN=30 \
        OPS_ROOT="$OT" OPS_CDRIVE="/nonexistent-ops-selftest" \
        python3 "$OT_PY" "$@"
}
printf '#!/usr/bin/env bash\nexit 0\n' > "$OT/bin/true"; chmod +x "$OT/bin/true"
OT_WORK="$OT/work"; export OT_WORK

ot_tick() { ot_env > "$OT/tick.out" 2>&1; }
ot_jams() { cat "$OT/state/jams.tsv" 2>/dev/null; }
ot_row()  { # (class) (subject) -> that row's remedy_tried field, or empty
    awk -F'\t' -v c="$1" -v s="$2" '$2==c && $3==s {print $4}' "$OT/state/jams.tsv" 2>/dev/null | tail -1
}
ot_cleared() {
    awk -F'\t' -v c="$1" -v s="$2" '$2==c && $3==s {print ($5=="")?"open":"cleared"}' "$OT/state/jams.tsv" 2>/dev/null | tail -1
}

# ---------------------------------------------------------------- (a) holds
touch -d '45 minutes ago' "$OT/work/dispatch/hold/thor" 2>/dev/null || touch "$OT/work/dispatch/hold/thor"
echo "lane.deadlane" > "$OT/work/dispatch/hold/thor"
echo "taken for a 30-min cold slot" > "$OT/work/dispatch/hold/thor.why"
touch -d '45 minutes ago' "$OT/work/dispatch/hold/thor.why" "$OT/work/dispatch/hold/thor" 2>/dev/null

touch -d '45 minutes ago' "$OT/work/dispatch/hold/nova" 2>/dev/null || touch "$OT/work/dispatch/hold/nova"
echo "lanelocal-fanwait" > "$OT/work/dispatch/hold/nova"

ot_tick
check "(a) thor held by a dead lane past its bound is released" \
    bash -c '! grep -qxF lane.deadlane '"$OT/work/dispatch/hold/thor"' 2>/dev/null'
check "(a) nova (owner tag, past the same bound) keeps its hold -- not a jam" \
    grep -qxF lanelocal-fanwait "$OT/work/dispatch/hold/nova"
check "(a) hold-overbound thor row exists with a release remedy" \
    bash -c 'ot_row() { awk -F"\t" -v c=hold-overbound -v s=thor "\$2==c && \$3==s {print \$4}" "'"$OT"'/state/jams.tsv"; }; ot_row | grep -q "hold.sh release"'

# -------------------------------------------------------- (b) stranded lane
mkdir -p "$OT/work/briefs"
printf '# brief for stranded1\ndo the thing\n' > "$OT/work/briefs/stranded1.md"
printf '# brief for stopped1\ndo the other thing\n' > "$OT/work/briefs/stopped1.md"
: > "$OT/work/briefs/stopped1.md.STOPPED-by-owner-20261002-0900-selftest"
git -C "$OT/repo" init -q -b master 2>/dev/null
git -C "$OT/repo" -c user.email=t@t -c user.name=t commit -q --allow-empty -m init
for name in stranded1 stopped1 terrgap; do
    git -C "$OT/repo" branch -q "lane/$name" master
    git -C "$OT/repo" checkout -q "lane/$name"
    mkdir -p "$OT/repo/docs/lanes/$name"
    printf '# lane.%s\nState: draft\n\nwaiting on something that already finished\n' "$name" > "$OT/repo/docs/lanes/$name/PR.md"
    git -C "$OT/repo" -c user.email=t@t -c user.name=t add -A >/dev/null
    git -C "$OT/repo" -c user.email=t@t -c user.name=t commit -q -m "lane.$name PR.md draft"
done
git -C "$OT/repo" checkout -q master
mkdir -p "$OT/repo/origin.git"
git -C "$OT/repo/origin.git" init -q --bare -b master
git -C "$OT/repo" remote add origin "$OT/repo/origin.git" 2>/dev/null || git -C "$OT/repo" remote set-url origin "$OT/repo/origin.git"
git -C "$OT/repo" push -q origin master lane/stranded1 lane/stopped1 lane/terrgap
git -C "$OT/repo" fetch -q origin
# det_fold_failures prunes a fold-failure line whose recorded head no longer matches the
# branch's CURRENT head (a stale failure the lane has since moved past) -- so a fold-failures.log
# fixture must name a branch's REAL current short sha, not a made-up one.
OT_SHA_STRANDED1=$(git -C "$OT/repo" rev-parse --short=10 lane/stranded1)
OT_SHA_TERRGAP=$(git -C "$OT/repo" rev-parse --short=10 lane/terrgap)

ot_tick
check "(b) stranded1's brief got an addendum" grep -q "Resumed by ops_tick" "$OT/work/briefs/stranded1.md"
check "(b) lane.sh resume stranded1 was called exactly once" \
    bash -c '[ "$(grep -c "^resume stranded1$" "'"$OT_LANE_LOG"'")" = 1 ]'
check "(b) stopped1 (STOPPED marker) was never resumed" \
    bash -c '! grep -q "resume stopped1" "'"$OT_LANE_LOG"'"'
check "(b) stranded1's brief carries no addendum for stopped1" \
    bash -c '! grep -q "Resumed by ops_tick" "'"$OT_WORK"'/briefs/stopped1.md"'

ot_tick   # a second tick: lane.sh's fake still reports inactive (no real unit started), but
          # the row already exists and is not yet past ESCALATE_AFTER_MIN, so no SECOND resume
check "(b) a second tick does not resume stranded1 again" \
    bash -c '[ "$(grep -c "^resume stranded1$" "'"$OT_LANE_LOG"'")" = 1 ]'

# ------------------------------------------------------- (c) fold failures
FF="$OT/work/offline-git/fold-failures.log"
cat > "$FF" <<EOF
2026-10-02 09:01:00 PDT FAILED lane/terrgap @ $OT_SHA_TERRGAP: outside [lane.terrgap]'s files ['docs/lanes/terrgap/**']: ['hw/xbox/x.c']
EOF
ot_tick
check "(c) territory-gap fold failure wrote an inbox note" \
    grep -q "fold-failure:territory" "$OT_WORK/host-tools/hostops-inbox.md"
check "(c) territory-gap jam is open" bash -c '[ "$(awk -F"\t" -v c=fold-failure:territory -v s=lane/terrgap "\$2==c && \$3==s {print (\$5==\"\")?\"open\":\"cleared\"}" "'"$OT"'/state/jams.tsv" | tail -1)" = open ]'

cat >> "$FF" <<EOF
2026-10-02 09:05:00 PDT FAILED lane/stranded1 @ $OT_SHA_STRANDED1: merge conflict with master:
diff --git a/x b/x
EOF
ot_tick
check "(c) a conflict fold failure resumed lane.stranded1 a second time (new reason, same lane)" \
    bash -c '[ "$(grep -c "^resume stranded1$" "'"$OT_LANE_LOG"'")" = 2 ]'
check "(c) fold-failure:conflict jam for lane/stranded1 is open" \
    bash -c '[ "$(awk -F"\t" -v c=fold-failure:conflict -v s=lane/stranded1 "\$2==c && \$3==s {print (\$5==\"\")?\"open\":\"cleared\"}" "'"$OT"'/state/jams.tsv" | tail -1)" = open ]'

cat >> "$FF" <<'EOF'
2026-10-02 09:10:00 PDT FOLDED lane/stranded1: 09:10:00 FOLDED lane/stranded1 as fedcba9876 on master
EOF
ot_tick
check "(c) a later FOLDED line clears the conflict jam" \
    bash -c '[ "$(awk -F"\t" -v c=fold-failure:conflict -v s=lane/stranded1 "\$2==c && \$3==s {print (\$5==\"\")?\"open\":\"cleared\"}" "'"$OT"'/state/jams.tsv" | tail -1)" = cleared ]'
check "(c) the territory-gap jam is untouched by that FOLDED line (different branch)" \
    bash -c '[ "$(awk -F"\t" -v c=fold-failure:territory -v s=lane/terrgap "\$2==c && \$3==s {print (\$5==\"\")?\"open\":\"cleared\"}" "'"$OT"'/state/jams.tsv" | tail -1)" = open ]'
ot_conflict_resumes_before=$(grep -c "^resume stranded1$" "$OT_LANE_LOG")
ot_tick
check "(c) a cleared fold-failure jam is not re-escalated or re-resumed on the next tick" \
    bash -c '[ "$(grep -c "^resume stranded1$" "'"$OT_LANE_LOG"'")" = '"$ot_conflict_resumes_before"' ]'

# lane/terrgap pushes a new commit without a new FAILED or FOLDED line naming it -- the open
# territory jam's recorded head is now stale (the lane may have already fixed it and be
# waiting on a retry), so it must be dropped, not kept open on old evidence.
git -C "$OT/repo" checkout -q lane/terrgap
git -C "$OT/repo" -c user.email=t@t -c user.name=t commit -q --allow-empty -m "lane.terrgap: pushed again"
git -C "$OT/repo" push -q origin lane/terrgap
git -C "$OT/repo" checkout -q master
ot_tick
check "(c) a fold-failure jam whose branch has since moved on is dropped, not kept open" \
    bash -c '[ "$(awk -F"\t" -v c=fold-failure:territory -v s=lane/terrgap "\$2==c && \$3==s {print (\$5==\"\")?\"open\":\"cleared\"}" "'"$OT"'/state/jams.tsv" | tail -1)" = cleared ]'

# --------------------------------------------------------- (d) failed unit
echo "hakux-fold.service loaded failed failed hakuX fold job" > "$OT/bin/failed-units.txt"
: > "$OT_ESCALATE_LOG"
ot_tick
check "(d) a failed unit with no remedy escalates on its first tick (no 30-min wait)" \
    grep -q "failed-unit hakux-fold.service" "$OT_ESCALATE_LOG"
check "(d) the escalation ran on claude-sonnet-5 the first time" \
    grep -q "claude-sonnet-5" "$OT_ESCALATE_LOG"
esc_calls_before=$(wc -l < "$OT_ESCALATE_LOG")
ot_tick
check "(d) the same still-open failed-unit does not escalate again inside ESCALATE_AFTER_MIN" \
    bash -c '[ "$(wc -l < "'"$OT_ESCALATE_LOG"'")" = '"$esc_calls_before"' ]'
: > "$OT/bin/failed-units.txt"
ot_tick
check "(d) once the unit is no longer failed, its jam row clears" \
    bash -c '[ "$(awk -F"\t" -v c=failed-unit -v s=hakux-fold.service "\$2==c && \$3==s {print (\$5==\"\")?\"open\":\"cleared\"}" "'"$OT"'/state/jams.tsv" | tail -1)" = cleared ]'

# --------------------------------------------------------------- (e) shadow
rm -rf "$OT/state"; mkdir -p "$OT/state"
echo "lane.deadlane" > "$OT/work/dispatch/hold/thor"
touch -d '45 minutes ago' "$OT/work/dispatch/hold/thor"
ot_env --shadow > "$OT/shadow.out" 2>&1
check "(e) --shadow logs what it would do" grep -q "would run remedy" "$OT/state/shadow.log"
check "(e) --shadow writes no jams.tsv" bash -c '[ ! -s "'"$OT"'/state/jams.tsv" ]'
check "(e) --shadow does not actually release the hold" grep -qxF lane.deadlane "$OT/work/dispatch/hold/thor"
