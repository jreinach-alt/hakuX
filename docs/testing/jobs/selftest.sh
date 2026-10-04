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

# ------------------------------------------------------------ the fragments
# Collected first, before any fixture, so the shard check below can run on its
# own. Why fragments, and how to add one: see "the checks" further down.
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

# --------------------------------------------------------------- the shards
# SELFTEST_SHARD=k/n runs shard k (0-based) of n. WHY: run whole, this took
# 18-25 min on the CI runner against a 25-min cap, and a capped run concludes
# CANCELLED, which fold.sh reads as RED -- 4 of 20 runs on 2026-09-27. The
# workflow runs one job per shard (.github/workflows/jobs-selftest.yml).
#
# A SHARD IS NOT i % n. Fragments share state on purpose: 10..64 drive arms.sh
# and status.sh over one dispatcher queue in sequence, 92/94 read what 40 and
# 50 left, 87 calls a predicate 86 defines, 99-handback-{runs,strand} copy
# 99-handback-draft's shims. A CHAIN
# below is a set that must land in one shard; everything else is a unit of
# one. Units go to shards by longest-first onto the lightest shard, weighted by
# SHARD_SECS (seconds, measured; a fragment not listed weighs SHARD_SECS_NEW).
# A stale weight costs balance, never coverage. Inside a shard, fragments run
# in the global sorted order.
#
# A NEW FRAGMENT THAT READS ANOTHER'S LEFTOVERS goes into that fragment's
# chain here. If it is not, it may land in another shard and fail there --
# loud, and the fix is one line. Verify with SELFTEST_ONLY="<it>" (a
# fragment that passes alone needs no chain).
SHARD_CHAINS=(
    "10-arms-list 20-arms-queue 30-arms-error 40-arms-refusal 50-arms-requeue 51-dispatch-hardening 55-localtime 60-status 62-status-freshness 63-status-lanes 64-status-html 92-arms-skip-told 94-arms-label-state"
    "86-nightly-notes 87-nightly-trunk"
    "99-handback-draft 99-handback-runs 99-handback-strand"
)
# Measured 2026-09-27, each fragment alone on the host (SELFTEST_ONLY); the
# CI runner is about 2x faster. 84 and 92 have no alone time (84 printed a
# clobbered one, 92 needs its chain) and weigh SHARD_SECS_NEW.
SHARD_SECS_NEW=15
SHARD_SECS="
    10-arms-list:65 20-arms-queue:140 30-arms-error:71 40-arms-refusal:333
    50-arms-requeue:204 51-dispatch-hardening:24 55-affinity-offpool:7
    55-localtime:5 56-desktop-worker:31 57-vsh-disc:10 58-pull-verify:59
    60-status:3 62-status-freshness:17 63-status-lanes:12 64-status-html:37
    65-fold-cloud-list:3 65-status-objective:17 66-deliveries:11
    66-status-titles:14 67-status-measured:14 70-cloud-audit:0
    71-cloud-territory:12 72-cloud-tail:29 73-cloud-claim:17 73-fold-repair:21
    74-fold-multi:101 75-fold-exact:2 75-nv2a-index:1 75-nv2a-index-drift:2
    76-pr-sweep:19 76-x1a7-model:1 77-issue-sweep:43 78-sweep-remote:9
    79-stop-hook-hold:1 80-labels:0 83-blank-rule:9 85-fold-ci:41
    86-fold-regressed:68 86-nightly-notes:7 87-fold-stale-ci:52
    87-nightly-trunk:4 88-sweep-cover:5 88-window-budget:20
    89-title-verdict:49 90-fold-index:22 90-fold-notes:0 91-fold-transient:37
    93-backlog-state:4 94-arms-disc-narrow:186 94-arms-idle-tier:250
    94-arms-label-state:164 94-arms-verdict-scope:18 94-arms-withdrawn:21
    95-affinity:6 96-fleet-registry:3 97-board-gate:5 97-board-priority:3
    97-board-push-gate:4 97-board-release:1 97-dispatch-deploy:1
    97-dispatch-snapshot-rename:4 97-fold-branch-prune:3 97-preflight-tmp:3
    97-release-prio:239 98-audit-outlet:3 98-coverage-rest:1
    98-dispatch-late-device:14 98-fleet-queue-stall:3 98-lane-shape:24
    99-affinity-backlog:87 99-default-regimen:3 99-display-covered:41
    99-handback:29 99-handback-branch:18 99-handback-draft:28
    99-handback-idle:175 99-handback-lane-line:17 99-handback-merged:29
    99-handback-parked:46 99-handback-resolved:13 99-handback-runs:12
    99-handback-strand:6 99-hold-take:5 99-iso-roots:1 99-limits-env:12
    99-pilot-gate:3 99-power-per-frame:4 99-score-sweep-flat-split:3
    99-status-escalation-items:1 99-thermal-pause:34 99-title-state:5
"
shard_frags() {   # <k> <n> -> the basenames of shard k, sorted, one per line
    printf '%s\n' "${frags[@]##*/}" | python3 -c '
import sys
k, n, new, secs = int(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]
chains = [c.split() for c in sys.argv[5:]]
names = [l.strip() for l in sys.stdin if l.strip()]
have = set(names)
w = {}
for tok in secs.split():
    f, s = tok.rsplit(":", 1); w[f] = int(s)
def wt(f): return w.get(f[:-3], new)
units, seen = [], set()
for c in chains:
    bad = [m for m in c if m + ".sh" not in have]
    if bad:
        sys.exit("selftest: SHARD_CHAINS names %s, not under selftest.d" % " ".join(bad))
    units.append([m + ".sh" for m in c]); seen.update(units[-1])
units += [[f] for f in names if f not in seen]
units.sort(key=lambda u: (-sum(map(wt, u)), u[0]))
load, owner = [0] * n, {}
for u in units:
    s = min(range(n), key=lambda i: (load[i], i))
    load[s] += sum(map(wt, u))
    for f in u: owner[f] = s
print("\n".join(f for f in names if owner[f] == k))
' "$1" "$2" "$SHARD_SECS_NEW" "$SHARD_SECS" "${SHARD_CHAINS[@]}"
}
# THE GUARD. A fragment in no shard is a check silently gone, which is worse
# than a slow run. So before a shard runs anything: the n shards, each asked
# for exactly as a run asks for it, must together be the full fragment list,
# each fragment exactly once, every chain inside one shard; and the workflow's
# matrix must name shards 0..n-1 with this n. `selftest.sh --check-shards n`
# runs only this.
shard_check() {   # <n>
    local n=$1 k all="" f wf="$REPO/.github/workflows/jobs-selftest.yml" m err=0 c
    for ((k = 0; k < n; k++)); do
        f=$(shard_frags "$k" "$n") || return 1
        all+="$f"$'\n'
        for c in "${SHARD_CHAINS[@]}"; do
            m=$(comm -12 <(tr ' ' '\n' <<< "$c" | sed 's/$/.sh/' | LC_ALL=C sort) <(LC_ALL=C sort <<< "$f") | wc -l)
            [ "$m" -eq 0 ] || [ "$m" -eq "$(wc -w <<< "$c")" ] || { echo "selftest: shard $k/$n splits the chain: $c" >&2; err=1; }
        done
    done
    m=$(diff <(printf '%s\n' "${frags[@]##*/}") <(grep . <<< "$all" | LC_ALL=C sort)) \
        || { echo "selftest: shards 0..$((n-1)) of $n are not the fragment list, each once (< missing, > extra):" >&2; echo "$m" >&2; err=1; }
    if [ -f "$wf" ]; then
        m=$(sed -n 's/^ *shard: *\[\(.*\)\] *$/\1/p' "$wf" | tr -d ' ')
        c=$(sed -n 's|^ *SELFTEST_SHARD: *\${{ *matrix\.shard *}}/\([0-9]*\) *$|\1|p' "$wf")
        [ "$m" = "$(seq -s, 0 $((n-1)))" ] && [ "$c" = "$n" ] \
            || { echo "selftest: $wf runs shards [$m] of '$c', not 0..$((n-1)) of $n" >&2; err=1; }
    fi
    [ "$err" -eq 0 ] && echo "selftest: shards 0..$((n-1)) of $n cover all ${#frags[@]} fragments, each once"
    return "$err"
}
case "${1:-}" in
    --check-shards) shard_check "${2:?--check-shards <n>}"; exit ;;
    --list-shards)  for ((k = 0; k < ${2:?--list-shards <n>}; k++)); do
                        echo "shard $k/$2: $(shard_frags "$k" "$2" | tr '\n' ' ')"
                    done; exit ;;
esac
if [ -n "${SELFTEST_SHARD:-}" ]; then
    [[ "$SELFTEST_SHARD" =~ ^([0-9]+)/([0-9]+)$ ]] && [ "${BASH_REMATCH[1]}" -lt "${BASH_REMATCH[2]}" ] \
        || { echo "selftest: SELFTEST_SHARD=$SELFTEST_SHARD is not k/n with k < n" >&2; exit 2; }
    SHARD_K=${BASH_REMATCH[1]} SHARD_N=${BASH_REMATCH[2]}
    shard_check "$SHARD_N" || exit 2
fi
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
#
# SHARDS. CI runs this as a matrix (SELFTEST_SHARD=k/n, see the header of
# shard_plan below); with no selector every fragment runs, in order, as the
# host runs it. The fragment list was collected above, before any fixture.
run=("${frags[@]}")
if [ -n "${SELFTEST_ONLY:-}" ]; then
    run=()
    for f in "${frags[@]}"; do
        case " $SELFTEST_ONLY " in *" ${f##*/} "*|*" $(basename "$f" .sh) "*) run+=("$f") ;; esac
    done
    [ "${#run[@]}" -gt 0 ] || { echo "selftest: SELFTEST_ONLY names no fragment under selftest.d" >&2; exit 2; }
elif [ -n "${SELFTEST_SHARD:-}" ]; then
    mapfile -t run < <(shard_frags "$SHARD_K" "$SHARD_N" | sed "s|^|$HERE/selftest.d/|")
fi
# The loop's names are private: fragments run in this shell, and some set `f`
# and `t0` for themselves, which printed the wrong name and time.
for _st_frag in "${run[@]}"; do
    _st_t0=$SECONDS
    . "$_st_frag"
    echo "selftest: ${_st_frag##*/} took $((SECONDS - _st_t0))s"
done

echo
scope="all ${#frags[@]} fragments"
[ "${#run[@]}" -eq "${#frags[@]}" ] || scope="PARTIAL: ${#run[@]} of ${#frags[@]} fragments${SELFTEST_SHARD:+, shard $SELFTEST_SHARD}"
echo "selftest: $pass passed, $fail failed, $scope (fake host in $T)"
[ "$fail" -eq 0 ]
