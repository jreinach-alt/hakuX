#!/usr/bin/env bash
#
# The jobs' self-test: run the real job scripts against a fake host.
#
#   docs/testing/jobs/selftest.sh          # exits non-zero on any failure
#
# WHY. The jobs run only on the owner's host -- systemd, gh, adb, the
# dispatch directory, the goldens tree -- and the session that writes them
# cannot execute any of it. On 2026-09-19 that put the owner in a loop:
# merge, run, paste the error, wait for the fix, merge again. Three of the
# four defects that day (a watermark seeded at install time, an arithmetic
# error on a "?" field, an empty --runs handed to request.sh) fall out of
# one run of this file. So: nothing under jobs/ is pushed until this passes,
# and the check is in CI (.github/workflows/jobs-selftest.yml) as well.
#
# WHAT IS REAL AND WHAT IS FAKED. Real: git, python3, request.sh's whole
# queue path (its gates, its JSON writer), arms.sh, fold.sh, cloud.sh,
# status.sh. Faked, as shims on PATH under $T/bin: gh (canned answers, every
# call logged), systemctl, systemd-run, adb. The goldens tree is generated
# from the prediction under test, so request.sh's every-key-must-bind gate
# runs for real.
set -u
export HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"; TESTING="$(dirname "$HERE")"; REPO="$(cd "$TESTING/../.." && pwd)"
T="${SELFTEST_DIR:-$(mktemp -d "${TMPDIR:-/tmp}/hakux-selftest.XXXXXX")}"
export HAKUX_WORK="$T/work" HAKUX_REPO_DIR="$REPO" DISPATCH_DIR="$T/work/dispatch" GOLDENS="$T/goldens" GH_REPO="example/hakux"
export HOME="${HOME:-$T}"
mkdir -p "$T/bin" "$HAKUX_WORK"/{arms,logs/arms,logs/lane,logs/board,logs/fold,logs/cloud,status,briefs,attempts} "$DISPATCH_DIR"/{queue,running,results,expect} "$GOLDENS"
pass=0; fail=0
ok()   { echo "  ok   $*"; pass=$((pass+1)); }
bad()  { echo "  FAIL $*"; fail=$((fail+1)); }
check() { local msg=$1; shift; if "$@" >/dev/null 2>&1; then ok "$msg"; else bad "$msg"; fi; }

# ------------------------------------------------------------------ shims
cat > "$T/bin/gh" <<'EOF'
#!/usr/bin/env bash
# gh shim: log every call, answer the shapes the jobs ask for.
echo "$*" >> "${SELFTEST_GH_LOG:?}"
args="$*"
case "$1 $2" in
    "auth status") exit 0 ;;
    "pr list")
        if [[ "$args" == *"--head lane/selftest"* ]]; then
            [[ "$args" == *".[0].number"* ]] && { echo 102; exit 0; }
            echo "#102 draft"; exit 0
        fi
        [[ "$args" == *"--jq"* ]] && exit 0
        echo "[]"; exit 0 ;;
    "pr view") echo GREEN; exit 0 ;;
    "issue list") [[ "$args" == *"harness-status"* ]] && echo 107; exit 0 ;;
    "issue create") echo "https://github.com/example/hakux/issues/107"; exit 0 ;;
    "api "*|"api -X"*)
        [[ "$args" == *"--jq .id"* ]] && { echo 5; exit 0; }
        # the labels currently on an issue/PR, for label_rm's "is it there" probe
        [[ "$args" == *"/labels"* && "$args" != *"-X"* ]] && { printf '%s\n' ${SELFTEST_LABELS:-}; exit 0; }
        exit 0 ;;
    *) exit 0 ;;
esac
EOF
cat > "$T/bin/systemctl" <<'EOF'
#!/usr/bin/env bash
case "$*" in
    *is-active*) echo active ;;
    *show*ActiveEnterTimestamp*) date ;;
    *) exit 0 ;;
esac
EOF
cat > "$T/bin/systemd-run" <<'EOF'
#!/usr/bin/env bash
echo "systemd-run $*" >> "${SELFTEST_GH_LOG:?}"; exit 0
EOF
cat > "$T/bin/adb" <<'EOF'
#!/usr/bin/env bash
printf 'List of devices attached\nbdc158a5\tdevice\nee317437\tdevice\n'
EOF
chmod +x "$T/bin/"*
export PATH="$T/bin:$PATH" SELFTEST_GH_LOG="$T/gh.log"; : > "$SELFTEST_GH_LOG"

# ------------------------------------------------------- the prediction
# A registration naming two real, live refs of this repository: the trunk's
# tip and its parent. It has NO runs_per_arm and NO disc, which is the shape
# that broke the first real tick.
git -C "$REPO" fetch -q origin master 2>/dev/null || true
B=$(git -C "$REPO" rev-parse --short origin/master 2>/dev/null || git -C "$REPO" rev-parse --short HEAD)
A=$(git -C "$REPO" rev-parse --short "$B~1")
EXP="$DISPATCH_DIR/expect/selftest-live.json"
python3 - "$EXP" "$A" "$B" <<'PY'
import json, sys, datetime
p, a, b = sys.argv[1:]
json.dump({"registered_utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "who": "lane.selftest", "issue": "1", "prediction": "selftest: the fix arm moves TestA to 0",
           "a_ref": a, "b_ref": b,
           "expect": {"Blend_surface/TestA": 0}, "must_not_move": ["Color_mask_blend/*"],
           "must_not_regress": [], "expect_counts": {}}, open(p, "w"), indent=2)
PY
mkdir -p "$GOLDENS/Blend_surface" "$GOLDENS/Color_mask_blend"
: > "$GOLDENS/Blend_surface/TestA.png"; : > "$GOLDENS/Color_mask_blend/Sample.png"
date -u -d '1 minute ago' '+%FT%TZ' > "$HAKUX_WORK/arms/since"   # fences every committed prediction; only ours is live
# Make our registration look like it came from a lane branch, so the verdict/refusal path targets a PR.
mkdir -p "$HAKUX_WORK/arms"

# --------------------------------------------------------------- the checks
# Every check lives in its own file under selftest.d/, sourced here in sorted
# order with everything above already built: $T, $HERE, $REPO, the shims on
# PATH, ok/bad/check, the live prediction and its goldens.
#
# WHY IT IS NOT ONE FILE. This is the gate every change under jobs/ must pass,
# so a lane that fixes something here also adds the check that proves it: on
# 2026-09-19 nine harness lanes ran and all nine appended to this file. The
# fold job folds one PR per tick and each fold moves master, so the conflict
# rate on this one path was not high, it was ~100% -- two of the first three
# folds attempted were handed back on selftest.sh alone, each costing a full
# lane.sh resume to re-land work that was already finished and green. A
# fragment is separately ownable; two lanes adding checks now touch two paths.
#
# ADDING A CHECK: write, or edit, selftest.d/NN-<concern>.sh.
#   - NN is exactly two digits. A three-digit prefix would sort before every
#     two-digit one, so the loop below refuses a name that is not NN-*.sh
#     rather than silently never sourcing it.
#   - The number fixes the order, and order matters: fragments 10..50 drive
#     arms.sh over one shared dispatcher queue in sequence, and 60 reads what
#     they left. Each fragment's header says what it depends on.
#   - Fragments are sourced, not executed: no shebang, no exit. `pass`, `fail`
#     and the fixtures are shared state, so a failing check in a fragment
#     fails the whole run, which is the point.
frags=()
while IFS= read -r f; do                         # LC_ALL=C: the runner's
    [ -e "$f" ] || continue                      # collation is not this box's
    case "${f##*/}" in
        [0-9][0-9]-*.sh) frags+=("$f") ;;
        *.md|*~)         ;;                      # a README, an editor backup
        *) echo "selftest: $f is not selftest.d/NN-<concern>.sh and would never be sourced" >&2
           exit 2 ;;
    esac
done < <(printf '%s\n' "$HERE/selftest.d/"* | LC_ALL=C sort)
[ "${#frags[@]}" -gt 0 ] || {
    echo "selftest: no fragments under $HERE/selftest.d -- nothing would be checked" >&2
    exit 2
}
for f in "${frags[@]}"; do
    . "$f"
done

echo "== affinity: the lane registration, and saying so when there is none"
# WHY. On 2026-09-19 #89's A/B pair ran base on the `thor` and fix on the
# `nova`. affinity.py exists to stop exactly that, and it was INERT: $D/lanes/
# was empty, so serving() returned [], so rule 2's _live() was false for a
# device that was in fact serving and rule 3 had no devices to hash over. The
# lane pid file was written once per worker process, so a single `rm` by
# anyone disabled pinning until the dispatcher was restarted -- and no log
# line, no status field and no note reachable by a reader said a word.
#
# These checks pin the three things that were missing, not the remover, which
# is still unidentified (NOTES.md on lane/armpin has the refuted hypotheses).
export AD="$T/aff"; mkdir -p "$AD"/{lanes,running,results,splits,queue,logs}
export TESTING AFF="$TESTING/affinity.py"
sleep 600 & export LIVEPID=$!               # a pid that is certainly alive
sleep 0   & DEADPID=$!; wait $DEADPID 2>/dev/null   # and one that certainly is not
disp() {   # run shell inside a sourced dispatcher.sh, as the nova, against $AD
    ( export DISPATCH_DIR="$AD" SERIAL=ee317437 DISPATCH_TREE="$REPO" DISPATCH_REPO="$REPO"
      . "$TESTING/dispatcher.sh" selftest-not-a-subcommand >/dev/null 2>&1
      eval "$1" )
}

# --- serving(): the single input every rule above is decided over.
printf '%s\n' "$LIVEPID" > "$AD/lanes/nova"
printf '%s\n' "$DEADPID" > "$AD/lanes/thor"
printf '%s\n' "2026-09-14" > "$AD/lanes/remote.lastbrief"   # check_coverage.py's stamp
check "serving lists the lane whose pid is alive and not the one whose pid is dead" \
    [ "$(python3 "$AFF" "$AD" --serving 2>/dev/null)" = "nova" ]
# Counted, not grepped for absence: "no lastbrief in the output" is also true
# of no output at all, and a check that a missing feature satisfies has
# measured nothing. Three files in lanes/, exactly one device.
check "a <lane>.lastbrief stamp sharing the directory is not mistaken for a device" \
    [ "$(python3 "$AFF" "$AD" --serving 2>/dev/null | wc -w)" = 1 ]

# --- the two behaviours the brief says must stay true. CONTROLS: these pass
# against the old file too, and are here to show the fix did not buy its
# visibility by making a pin block a claim.
mkdir -p "$AD/results/r-old"
printf '{"expect":"/p/e7d2.json"}\n' > "$AD/results/r-old/request.json"
printf '{"device_label":"thor"}\n'   > "$AD/results/r-old/result.json"
printf '{"requester":"arms-x-fix","expect":"/p/e7d2.json"}\n' > "$AD/q.req"
check "CONTROL: a pin to a device that is NOT serving falls through rather than stalling" \
    [ -z "$(python3 "$AFF" "$AD" "$AD/q.req" 2>/dev/null)" ]
printf '{"device_label":"nova"}\n' > "$AD/results/r-old/result.json"
check "CONTROL: a pin to a device that IS serving is still honoured" \
    [ "$(python3 "$AFF" "$AD" "$AD/q.req" 2>/dev/null)" = "nova" ]

# --- the fallthrough must stop being silent. This is the defect: every rule
# ran over an empty device set and printed the same "" a request with no
# sibling prints.
rm -rf "$AD/lanes" "$AD/splits"; mkdir -p "$AD/lanes" "$AD/splits"
python3 "$AFF" "$AD" "$AD/q.req" >/dev/null 2>&1
check "a request that could not be pinned AT ALL leaves a note" \
    bash -c '[ -n "$(ls "$AD"/splits/*.blind.txt 2>/dev/null)" ]'
check "the note names the prediction whose pair may now split" \
    bash -c 'grep -q "e7d2.json" "$AD"/splits/*.blind.txt'
printf '%s\n' "$LIVEPID" > "$AD/lanes/nova"; printf '%s\n' "$LIVEPID" > "$AD/lanes/thor"
rm -f "$AD"/splits/*.blind.txt
python3 "$AFF" "$AD" "$AD/q.req" >/dev/null 2>&1
check "CONTROL: a request pinned normally leaves no blind note" \
    bash -c '[ -z "$(ls "$AD"/splits/*.blind.txt 2>/dev/null)" ]'

# --- the lane file itself. It was written once per process; that permanence,
# not the removal, is what cost five hours.
# Chained with && throughout, never `;`. Sequenced with `;` these all pass
# against a file that has no lane_claim in it at all -- the missing function
# fails, nothing is ever created, and "the file is absent" comes out true.
check "lane_claim restores a registration removed from outside, so a removal costs a tick not a restart" \
    disp 'lane_claim && rm -f "$D/lanes/nova" && lane_claim && [ "$(cat "$D/lanes/nova")" = "$$" ]'
check "lane_release drops my own registration" \
    disp 'lane_claim && [ -e "$D/lanes/nova" ] && lane_release && [ ! -e "$D/lanes/nova" ]'
printf '%s\n' "$LIVEPID" > "$AD/lanes/nova"
check "lane_release SUCCEEDS and leaves a registration holding ANOTHER pid (a dead predecessor cannot evict its live successor)" \
    disp 'lane_release && [ "$(cat "$D/lanes/nova")" = "'"$LIVEPID"'" ]'
check "no lane file is removed by name anywhere; every removal goes through lane_release" \
    bash -c '! grep -q "rm -f \"\$D/lanes/" "$TESTING/dispatcher.sh"'
check "the registration is re-asserted after the hold check, not only at worker startup" \
    python3 -c 'import sys; s=open(sys.argv[1]).read(); i=s.index("$D/hold/$DEVICE_LABEL"); sys.exit(0 if "lane_claim" in s[i:] else 1)' "$TESTING/dispatcher.sh"
check "a held device does not re-register itself thirty seconds later" \
    python3 -c 'import sys; s=open(sys.argv[1]).read(); h=s.index("$D/hold/$DEVICE_LABEL"); sys.exit(0 if s.index("lane_claim", h) > s.index("lane_release", h) else 1)' "$TESTING/dispatcher.sh"

# --- the dispatcher must say it out loud, once, not per claim.
rm -rf "$AD/lanes"; mkdir -p "$AD/lanes"; : > "$AD/logs/dispatcher.log"
disp 'lane_blind_check one; lane_blind_check two' >/dev/null 2>&1
check "claiming with no lane registered logs AFFINITY BLIND" \
    grep -q "AFFINITY BLIND" "$AD/logs/dispatcher.log"
check "it is logged once per outage, not once per claim (the sweep queues one request per suite)" \
    [ "$(grep -c 'AFFINITY BLIND' "$AD/logs/dispatcher.log")" = 1 ]
: > "$AD/logs/dispatcher.log"
check "the outage has an END as well as a start: coming back is logged too" \
    disp 'lane_blind_check one && printf "%s\n" "'"$LIVEPID"'" > "$D/lanes/nova" && lane_blind_check two &&
          grep -q "AFFINITY BLIND" "$D/logs/dispatcher.log" && grep -q "lanes registered again" "$D/logs/dispatcher.log"'
: > "$AD/logs/dispatcher.log"
printf '%s\n' "$LIVEPID" > "$AD/lanes/nova"
check "a claim made with a lane registered logs nothing at all" \
    disp 'lane_blind_check one && lane_blind_check two && [ ! -s "$D/logs/dispatcher.log" ]'

# --- $D/splits/ gets a reader. The note was always written correctly; it was
# discoverable only by someone who already suspected it and knew the path.
mkdir -p "$DISPATCH_DIR/splits" "$DISPATCH_DIR/lanes"
printf 'prediction e7d2d739.json was pinned to thor, which is not serving; freed this request\n' \
    > "$DISPATCH_DIR/splits/1789793572-arms-blitsafe-fix-3718905.req.txt"
sout=$(bash "$HERE/status.sh" --print 2>&1)
check "status.sh reports what affinity is doing at all" grep -q '^- affinity:' <<< "$sout"
check "status.sh warns when no lane is registered and pinning is inert" \
    grep -q 'no device lane is registered' <<< "$sout"
check "status.sh surfaces a recent split note, with the prediction in it" \
    grep -q 'e7d2d739.json was pinned to thor' <<< "$sout"
kill "$LIVEPID" 2>/dev/null; wait "$LIVEPID" 2>/dev/null

echo
echo "selftest: $pass passed, $fail failed (fake host in $T)"
[ "$fail" -eq 0 ]
