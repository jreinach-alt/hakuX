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
#       never a real `claude -p` call. Each (a)-(d) leg also shows jams.tsv
#       opening a row once and clearing it once the detector stops reporting it.
#   (e) a device below its battery floor is held (ops_tick's own tag, via
#       hold.sh take -- real hold.sh, like leg (a)); above the lift threshold,
#       held by that same tag, it is released. Caught a real bug here: the
#       first cut's `take` reason string used a bare "<" and "(ops_tick)",
#       both shell metacharacters under shell=True (a redirection, and a
#       syntax error) -- this leg exists so that class of mistake fails loud.
#   (f) --shadow logs intent and writes nothing (no jams.tsv, no actual hold
#       release).
#   (g) jams.tsv is tab-separated, but `remedy_tried` carries a command's raw stdout
#       (truncated, not scrubbed) -- a leg directly on save_jams/load_jams proves an
#       embedded tab or newline does not misalign the row's later columns.
#   (h) a fold-failure whose recorded head is already an ancestor of origin/master
#       (the branch was folded) raises no jam and writes no inbox note.
#   (i) systemctl's failed list prefixes a bullet glyph; the unit name is the
#       hakux-* token, never the glyph.
#   (j) --shadow keeps its own jam identity across ticks: a jam the first shadow
#       tick announced is not announced as NEW again by the second.
#   (k) a lane whose session's cwd is its worktree is live, not stranded.
#   (l) not stranded: a draft lane with a WAITING file (lanewaker's), a draft lane whose
#       head is in origin/master (folded), and a lane idle under the 90-min grace.
#   (m) one jam instance gets at most two model sessions (Sonnet, then Opus), then is
#       marked for lane.local in summary.txt; the 10-03 shadow escalated one jam 4 times.
#   (n) disk-low routes to lane.xbox and never escalates (brief addendum 1); a territory
#       fold gap never escalates either (its fix is a board edit no session may make).
#   (o) a detector that raises keeps its open jams open; the same detector returning
#       nothing clears them (the control).

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
        OPS_DEVICES="thor,nova" OPS_ESCALATE_AFTER_MIN="${OT_ESC_AFTER:-30}" OPS_HOLD_BOUND_MIN=30 \
        OPS_STRANDED_GRACE_MIN="${OT_GRACE:-0}" OPS_DISK_FLOOR_GB="${OT_DISK_FLOOR:-20}" \
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

# ------------------------------------------- (k) a live session is not stranded
# A lane session run outside its unit has no hakux-lane-<name> active. Its worktree is
# the only local sign of it, so a process whose cwd sits in wt/<name> keeps the lane out of
# the stranded set. Falsified: the same stranded set WITHOUT the fake /proc entry must name it.
LIVE_PY=$(cat <<'PY'
import importlib.util, sys
spec = importlib.util.spec_from_file_location("ops_tick", sys.argv[1])
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
print("\n".join(sorted(j.subject for j in m.det_stranded_lanes())))
PY
)
ot_stranded() { # (proc root) -> the stranded lane names ops_tick would act on, one per line
    env OPS_PROC="$1" OPS_SYSTEMCTL="$OT/bin/systemctl" HAKUX_WORK="$OT/work" OPS_STRANDED_GRACE_MIN="${OT_GRACE:-0}" \
        HAKUX_REPO_DIR="$OT/repo" OPS_BRIEFS="$OT/work/briefs" python3 -c "$LIVE_PY" "$OT_PY"
}
mkdir -p "$OT/proc-empty" "$OT/proc-live/4242"
ln -sfn "$OT/work/wt/stranded1" "$OT/proc-live/4242/cwd"
ot_stranded "$OT/proc-empty" > "$OT/k-empty.txt"
ot_stranded "$OT/proc-live" > "$OT/k-live.txt"
check "(k) a stranded lane with no live session is named" grep -qx stranded1 "$OT/k-empty.txt"
check "(k) a lane whose session cwd is its worktree is not stranded" \
    bash -c '! grep -qx stranded1 "'"$OT/k-live.txt"'"'
check "(k) the other lane (no session) is still named" grep -qx terrgap "$OT/k-live.txt"

# ------------------------------------------- (l) waiting, folded, or recent: not stranded
for name in waiting1 draftfolded; do
    git -C "$OT/repo" checkout -q -b "lane/$name" master
    mkdir -p "$OT/repo/docs/lanes/$name"
    printf '# lane.%s\nState: draft\n' "$name" > "$OT/repo/docs/lanes/$name/PR.md"
    [ "$name" = waiting1 ] && echo "run 1700000000-selftest" > "$OT/repo/docs/lanes/$name/WAITING"
    git -C "$OT/repo" add "docs/lanes/$name" >/dev/null  # by path: origin.git sits in this tree
    git -C "$OT/repo" -c user.email=t@t -c user.name=t commit -q -m "lane.$name draft"
    git -C "$OT/repo" push -q origin "lane/$name"
done
git -C "$OT/repo" checkout -q master
git -C "$OT/repo" merge -q --ff-only lane/draftfolded
git -C "$OT/repo" push -q origin master
git -C "$OT/repo" fetch -q origin
ot_stranded "$OT/proc-empty" > "$OT/l-zero.txt"
OT_GRACE=90 ot_stranded "$OT/proc-empty" > "$OT/l-grace.txt"
check "(l) a draft lane with a WAITING file is not stranded" bash -c '! grep -qx waiting1 "'"$OT/l-zero.txt"'"'
check "(l) a draft lane whose head is in origin/master is not stranded" bash -c '! grep -qx draftfolded "'"$OT/l-zero.txt"'"'
check "(l) with no grace, the plain draft lane is still named" grep -qx terrgap "$OT/l-zero.txt"
check "(l) a lane that committed minutes ago is inside the 90-min grace" bash -c '! grep -qx terrgap "'"$OT/l-grace.txt"'"'

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

# (h) A branch already folded into master is not a fold-failure jam. The FOLDED line may sit
# outside the cursor window or never have been written; the recorded head being an ancestor of
# origin/master is the evidence that matters. Live example: snapdrive, usagemode, ibcache.
git -C "$OT/repo" checkout -q -b lane/folded1 master
git -C "$OT/repo" -c user.email=t@t -c user.name=t commit -q --allow-empty -m "lane.folded1 work"
git -C "$OT/repo" push -q origin lane/folded1
OT_SHA_FOLDED1=$(git -C "$OT/repo" rev-parse --short=10 lane/folded1)
git -C "$OT/repo" checkout -q master
git -C "$OT/repo" merge -q --ff-only lane/folded1
git -C "$OT/repo" push -q origin master
echo "2026-10-02 09:20:00 PDT FAILED lane/folded1 @ $OT_SHA_FOLDED1: outside [lane.folded1]'s files ['docs/lanes/folded1/**']: ['hw/x.c']" >> "$FF"
ot_tick
check "(h) a fold-failure whose head is already in origin/master raises no jam" \
    bash -c '[ -z "$(awk -F"\t" "\$3==\"lane/folded1\"" "'"$OT"'/state/jams.tsv" 2>/dev/null)" ]'
check "(h) ...and writes no inbox note for it" \
    bash -c '! grep -q "lane/folded1" "'"$OT_WORK"'/host-tools/hostops-inbox.md" 2>/dev/null'

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

# (i) systemctl prints a bullet glyph (●) as the first column of a failed unit's row. The old
# parse took the first token as the unit name, so the jam was "failed-unit ●" for every failure.
echo "● hakux-bullet.service loaded failed failed hakuX bullet job" > "$OT/bin/failed-units.txt"
: > "$OT_ESCALATE_LOG"
ot_tick
check "(i) a bulleted failed unit is named by its hakux-* token" \
    grep -q "failed-unit hakux-bullet.service" "$OT_ESCALATE_LOG"
check "(i) the bullet glyph is never a jam subject" \
    bash -c '! grep -q "failed-unit ●" "'"$OT_ESCALATE_LOG"'" && ! grep -q "failed-unit ●" "'"$OT/state/jams.tsv"'" 2>/dev/null'
: > "$OT/bin/failed-units.txt"
ot_tick

# ----------------------------------------------- (m) two model sessions per jam, then stop
echo "hakux-capped.service loaded failed failed hakuX capped job" > "$OT/bin/failed-units.txt"
: > "$OT_ESCALATE_LOG"
for i in 1 2 3 4; do OT_ESC_AFTER=0 ot_tick; done
check "(m) four ticks of one open jam spawn exactly two sessions" \
    bash -c '[ "$(grep -c "failed-unit hakux-capped.service" "'"$OT_ESCALATE_LOG"'")" = 2 ]'
check "(m) the second session is Opus" \
    bash -c 'grep "failed-unit hakux-capped.service" "'"$OT_ESCALATE_LOG"'" | tail -1 | grep -q claude-opus-5-5'
check "(m) summary.txt marks the capped jam for lane.local" \
    grep -q "failed-unit hakux-capped.service.*NEEDS lane.local" "$OT/state/summary.txt"
: > "$OT/bin/failed-units.txt"
ot_tick

# ------------------------------------- (n) disk and territory gaps never reach a model
: > "$OT_ESCALATE_LOG"
OT_SHA_STOPPED1=$(git -C "$OT/repo" rev-parse --short=10 lane/stopped1)
echo "2026-10-02 09:30:00 PDT FAILED lane/stopped1 @ $OT_SHA_STOPPED1: outside [lane.stopped1]'s files ['docs/lanes/stopped1/**']: ['hw/y.c']" >> "$FF"
for i in 1 2; do OT_ESC_AFTER=0 OT_DISK_FLOOR=100000000 ot_tick; done
check "(n) disk-low is routed to lane.xbox in the inbox" \
    grep -q "disk-low, for lane.xbox" "$OT_WORK/host-tools/hostops-inbox.md"
check "(n) disk-low is routed once per jam instance, not once per tick" \
    bash -c '[ "$(grep -c "disk-low, for lane.xbox" "'"$OT_WORK"'/host-tools/hostops-inbox.md")" = 1 ]'
check "(n) disk-low never spawns a model session" bash -c '! grep -q "^disk-low" "'"$OT_ESCALATE_LOG"'"'
check "(n) a territory fold gap never spawns a model session" \
    bash -c '! grep -q "^fold-failure:territory" "'"$OT_ESCALATE_LOG"'"'
echo "2026-10-02 09:31:00 PDT FOLDED lane/stopped1: selftest cleanup" >> "$FF"
ot_tick

# --------------------------------------------------------- (e) battery floor
mkdir -p "$OT/work/host-tools"
rm -f "$OT/work/dispatch/hold/thor" "$OT/work/dispatch/hold/thor.why"
cat > "$OT/work/host-tools/.device-reality.json" <<'EOF'
{"thor": {"level": "10"}, "nova": {"level": "80"}}
EOF
ot_tick
check "(e) thor below its battery floor (10% < 15%) gets ops_tick's own hold" \
    grep -qxF ops.battery "$OT/work/dispatch/hold/thor"
check "(e) nova (80%, held by leg (a)'s unrelated owner tag) is untouched" \
    grep -qxF lanelocal-fanwait "$OT/work/dispatch/hold/nova"
cat > "$OT/work/host-tools/.device-reality.json" <<'EOF'
{"thor": {"level": "25"}, "nova": {"level": "80"}}
EOF
ot_tick
check "(e) thor back above the lift threshold (25% >= 20%) is released" \
    bash -c '[ ! -e "'"$OT_WORK"'/dispatch/hold/thor" ]'

# --------------------------------------------------------------- (f) shadow
rm -rf "$OT/state"; mkdir -p "$OT/state"
echo "lane.deadlane" > "$OT/work/dispatch/hold/thor"
touch -d '45 minutes ago' "$OT/work/dispatch/hold/thor"
ot_env --shadow > "$OT/shadow.out" 2>&1
check "(f) --shadow logs what it would do" grep -q "would run remedy" "$OT/state/shadow.log"
check "(f) --shadow writes no jams.tsv" bash -c '[ ! -s "'"$OT"'/state/jams.tsv" ]'
check "(f) --shadow does not actually release the hold" grep -qxF lane.deadlane "$OT/work/dispatch/hold/thor"
# (j) Shadow must remember what it announced, or the overnight log re-announces every jam on
# every tick. Its state lives beside the real jams.tsv, never in it.
ot_env --shadow > "$OT/shadow2.out" 2>&1
check "(j) the first --shadow tick announces the hold-overbound jam as NEW" grep -q "NEW JAM hold-overbound thor" "$OT/shadow.out"
check "(j) a second --shadow tick does not re-announce it" \
    bash -c '! grep -q "NEW JAM hold-overbound thor" "'"$OT/shadow2.out"'"'
check "(j) the shadow tick's identity lives in jams.shadow.tsv, not jams.tsv" \
    bash -c '[ -s "'"$OT"'/state/jams.shadow.tsv" ] && [ ! -e "'"$OT"'/state/jams.tsv" ]'

# ----------------------------------------------------- (g) jams.tsv is tab-safe
cat > "$OT/tsv_safe.py" <<'EOF'
import sys
sys.path.insert(0, sys.argv[1])
import ops_tick as ot
path = sys.argv[2]
rows = {("hold-overbound", "thor"): {
    "opened": "2026-10-02T10:00:00", "class": "hold-overbound", "subject": "thor",
    "remedy_tried": "hold.sh release thor lane.x -> rc=0\nmulti\tline\toutput", "cleared_at": "", "time_to_clear_s": ""}}
ot.save_jams(path, rows)
lines = open(path).readlines()
loaded = ot.load_jams(path)
row = loaded.get(("hold-overbound", "thor"))
# Exactly 2 lines (header + the one row): a raw newline in remedy_tried, left unflattened,
# would split the row into two lines and load_jams would silently drop both (wrong column count).
ok = row is not None and row["subject"] == "thor" and row["cleared_at"] == "" and len(lines) == 2
print("ok" if ok else "FAIL: row=%r lines=%r" % (row, lines))
EOF
check "(g) a remedy_tried with embedded tabs/newlines round-trips without misaligning columns" \
    bash -c 'python3 "'"$OT"'/tsv_safe.py" "'"$HERE/ops"'" "'"$OT"'/tsv_safe.tsv" | grep -qx ok'

# ------------------------------------- (o) a detector that raises does not clear its jams
# 10-03 08:58 a NameError in det_stranded_lanes "cleared" two open stranded jams; the next good
# tick would have reopened them as NEW and resumed both lanes a second time.
cat > "$OT/blind.py" <<'EOF'
import os, sys
os.environ["OPS_STATE_DIR"] = sys.argv[2]
os.makedirs(sys.argv[2], exist_ok=True)
sys.path.insert(0, sys.argv[1])
import ops_tick as ot
path = os.path.join(sys.argv[2], "jams.tsv")
ot.save_jams(path, {("stranded-lane", "lanex"): {"opened": "2026-10-03T08:00:00", "class": "stranded-lane",
    "subject": "lanex", "remedy_tried": "resumed", "cleared_at": "", "time_to_clear_s": ""}})
def det_stranded_lanes():
    if sys.argv[3] == "raise":
        raise NameError("selftest")
    return []
ot.DETECTORS = (det_stranded_lanes,)
ot.run(False)
print("cleared" if ot.load_jams(path)[("stranded-lane", "lanex")]["cleared_at"] else "open")
EOF
check "(o) a detector that raises leaves its open jam open" \
    bash -c 'python3 "'"$OT"'/blind.py" "'"$HERE/ops"'" "'"$OT"'/blind-raise" raise 2>/dev/null | tail -1 | grep -qx open'
check "(o) control: the same detector returning nothing clears it" \
    bash -c 'python3 "'"$OT"'/blind.py" "'"$HERE/ops"'" "'"$OT"'/blind-empty" empty 2>/dev/null | tail -1 | grep -qx cleared'
