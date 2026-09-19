#!/usr/bin/env bash
#
# The arms job. Runs from hakux-arms.timer every 30 minutes, and never starts
# a model session: it is a script, start to finish.
#
#   arms.sh            queue what is runnable, judge what has finished
#   arms.sh list       what it would queue, and why the rest is skipped
#
# WHAT IT DOES. Every registered prediction names two refs (a_ref, b_ref) and
# the captures it expects to move or hold. That is a complete device request:
# the arms job finds every such prediction on master, on any lane branch, or
# registered on this host, queues its two arms through request.sh, and when
# both have run, judges the pair with ab_compare.py and posts the verdict on
# the lane's PR (or its issue). Nothing has to label anything for the
# handhelds to get work: a lane that commits a prediction and pushes has
# queued an arm.
#
# WHY IT IS A SCRIPT. On the first evening of the job harness two handhelds
# sat idle for two hours while three lanes pushed predictions, because the
# only actor that used to queue arms was the orchestrator session, and that
# session had been wound down. A queue driven by a model's attention is a
# queue that empties whenever the model is not looking. This one is driven
# by files.
#
# WHAT KEEPS IT FROM RE-RUNNING HISTORY. 131 predictions are on disk and most
# have run. A prediction is skipped when its sha256 already appears in a
# result's request.json (the dispatcher records expect_sha at queue time), in
# the queue, or in $WORK/arms/judged; and when it was registered before the
# watermark in $WORK/arms/since (install-host.sh seeds it with "now"). Set the
# watermark back to re-run older ones; delete a judged marker to re-judge.
#
# WHAT IT REFUSES, per AGENTS.md's inert-prediction rules: a ref that does not
# resolve, a b_ref that is not an ancestor of master or of any live lane
# branch (a reachable-but-stale ref is the one that measures the wrong
# binary and looks like success), and a prediction naming no suite that has
# goldens. request.sh's own gate (every key must name a golden capture) runs
# too, and a refusal there is recorded once and not retried.
set -u
WORK="${HAKUX_WORK:-/home/justin/hakux-work}"
REPO="${HAKUX_REPO_DIR:-/home/justin/hakuX}"          # the object store the dispatcher builds from
D="${DISPATCH_DIR:-$WORK/dispatch}"
GOLDENS="${GOLDENS:-/home/justin/goldens/results}"
GH_REPO="${GH_REPO:-jreinach-alt/hakuX}"
TIP="${HAKUX_TIP:-master}"
A="$WORK/arms"
# The scripts a queue and a judge run through are the trunk's, taken from
# beside this file (board.sh re-execs this from a fetched master worktree).
T="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
. "$(dirname "${BASH_SOURCE[0]}")/gh-label.sh"   # label_add/label_rm: `gh pr edit --add-label` exits 1 here
mkdir -p "$A"/{expect,pairs,judged,skipped,log} "$WORK/logs/arms"
LOG="$WORK/logs/arms/tick.log"
say() { echo "$(date -u '+%FT%TZ') $*" | tee -a "$LOG"; }
[ -f "$WORK/limits.env" ] && . "$WORK/limits.env"
MAX_PAIRS="${ARMS_MAX_PAIRS_PER_TICK:-2}"   # pairs queued per tick; both handhelds busy is the goal, a 40-deep queue is not
QUEUE_MAX="${ARMS_QUEUE_MAX:-4}"            # do not queue when this many requests already wait
# Default watermark: two days back, not "now". Seeded at "now" on the first
# install, it made every prediction the lanes had pushed THAT DAY read as
# history, and the first tick queued nothing while PR #102's live arm sat
# there. The expect_sha check is what stops a re-run; the watermark only
# keeps the job from walking a week of old registrations.
[ -f "$A/since" ] || date -u -d '2 days ago' '+%FT%TZ' > "$A/since"
SINCE=$(cat "$A/since")
history=0
mode="${1:-run}"

# ----------------------------------------------------------------- collect
# Every prediction file reachable from the trunk, from any lane branch, or
# registered in the dispatch directory. Exported by content hash so the same
# registration on two branches is one candidate and an amended copy is a new
# one (an amendment changes the sha, and the sha is what binds an arm).
git -C "$REPO" fetch -q origin "$TIP" '+refs/heads/lane/*:refs/remotes/origin/lane/*' 2>/dev/null \
    || say "WARNING: fetch failed; working from what the object store has"
# The trunk first: a prediction that is on master AND on the lane branch
# that folded it is master's, and its verdict goes to the issue, not to a
# PR that may have closed.
tips="refs/remotes/origin/$TIP $(git -C "$REPO" for-each-ref --format='%(refname)' 'refs/remotes/origin/lane/*')"

collect() {   # prints: <sha256> <exported-path> <source>, first sighting wins (trunk before lanes)
    local ref blob f sha out; declare -A seen; declare -A blobsha
    for ref in $tips; do
        # ONE cat-file per unique BLOB, not one per (ref, path). 23 lane refs
        # times 110 predictions is 2,530 pairs of git spawns, and almost all of
        # them are the same hundred blobs -- the identical prediction file is
        # reachable from every branch cut after it landed. The tick's cost grew
        # with the NUMBER OF LANE BRANCHES, which nothing prunes, and
        # selftest.sh runs this eight times: the gate every harness lane must
        # pass went to eight minutes against a fifteen-minute CI timeout.
        while read -r blob f; do
            [ -n "$blob" ] || continue
            sha="${blobsha[$blob]:-}"
            if [ -z "$sha" ]; then
                sha=$(git -C "$REPO" cat-file -p "$blob" | sha256sum | cut -d' ' -f1)
                blobsha[$blob]=$sha
            fi
            [ -n "${seen[$sha]:-}" ] && continue; seen[$sha]=1
            out="$A/expect/$sha.json"
            [ -f "$out" ] || git -C "$REPO" cat-file -p "$blob" > "$out"
            echo "$sha $out ${ref#refs/remotes/origin/}:$f"
        done < <(git -C "$REPO" ls-tree -r "$ref" -- docs/testing/predictions/ 2>/dev/null \
                     | awk -F'\t' '$2 ~ /\.json$/ {split($1,a," "); print a[3], $2}')
    done
    for f in "$D"/expect/*.json; do
        [ -f "$f" ] || continue
        sha=$(sha256sum "$f" | cut -d' ' -f1)
        [ -n "${seen[$sha]:-}" ] && continue; seen[$sha]=1
        echo "$sha $f host:$(basename "$f")"
    done
}

ARMS_VERSION=$(md5sum "${BASH_SOURCE[0]}" | cut -c1-12)
already_ran() {   # the sha is in a result, in the queue, in flight, or judged
    local sha=$1
    [ -f "$A/judged/$sha" ] && return 0
    [ -f "$A/pairs/$sha.json" ] && return 0
    if [ -f "$A/skipped/$sha" ]; then
        # A request.sh refusal recorded by an OLDER arms.sh is reconsidered
        # once this script changes: the first real refusal (#89, 02:56Z) was
        # this script's own bug, and the fix should not need a human to rm a
        # file on the host.
        #
        # WHAT IDENTIFIES ONE IS THE REFUSAL TEXT, NOT THE "arms=" STAMP. The
        # first version of this retry tested `grep -q '^arms='` first, and the
        # stamp was introduced by the same commit as the retry -- so the one
        # marker the retry was written for, #89's, already sitting on the host
        # with no stamp, took the `else` and was skipped forever. A guard keyed
        # on a field only the new writer emits exempts exactly the backlog it
        # was meant to clear. The stamp still does its job: it makes the retry
        # once per version, not every tick.
        #
        # Structural skips (no a_ref, a_ref == b_ref, a ref that does not
        # resolve, a stale b_ref, a soak, no suite with goldens) never carry
        # that text and stand until the prediction itself changes, because no
        # edit to this script can turn one of them into a run.
        if grep -q 'request\.sh refused' "$A/skipped/$sha" && ! grep -q "^arms=$ARMS_VERSION" "$A/skipped/$sha"; then
            say "  reconsidering $sha: request.sh refusal recorded by an older arms.sh"; rm -f "$A/skipped/$sha"
        else
            return 0
        fi
    fi
    grep -lq "\"expect_sha\": *\"$sha\"" "$D"/queue/*.req "$D"/running/*.req 2>/dev/null && return 0
    [ -n "${RAN[$sha]:-}" ] && return 0
    return 1
}

# EVERY expect_sha THAT ACTUALLY RAN, READ ONCE.
#
# A result that ERRORED is not a run: the ARM ERROR comment tells the lane to
# delete judged/<sha> and pairs/<sha>.json to have the arm queued again, and
# that could not work while an errored result's request.json still matched it.
# #89's arm hit exactly that when it failed to build on both sides for a reason
# that was the host's and not the branch's.
#
# The first version of that fix tested it PER CANDIDATE -- a grep per result
# directory, inside the loop over predictions. On this host that is 916 result
# directories times 117 candidates. The tick went from 17 seconds to over ten
# minutes and had to be killed. A per-item test inside a per-item loop is a
# quadratic that nobody notices until the corpus is real, and this corpus grew
# to 916 results without anyone watching it.
#
# So the results are read ONCE, here, into a set.
declare -A RAN
while IFS= read -r s; do [ -n "$s" ] && RAN[$s]=1; done < <(python3 - "$D" <<'PYRAN'
import glob, json, os, sys
for rj in glob.glob(os.path.join(sys.argv[1], "results", "*", "request.json")):
    if os.path.exists(os.path.join(os.path.dirname(rj), "ERROR")):
        continue                       # an ERRORed result is not a run
    try:
        sha = json.load(open(rj)).get("expect_sha")
    except Exception:
        continue
    if sha:
        print(sha)
PYRAN
)

live_ancestor() {   # is $1 an ancestor of the trunk or of any lane tip?
    local ref
    for ref in $tips; do
        git -C "$REPO" merge-base --is-ancestor "$1" "$ref" 2>/dev/null && return 0
    done
    return 1
}

# The suites a prediction runs on. The registration's own disc composition
# wins when it has one (its order is part of the disc identity); otherwise the
# suite half of every capture key, results-directory spelling turned back
# into the constructor spelling request.sh takes. Wildcard suites and suites
# with no goldens are dropped, and dropping everything is a refusal.
suites_for() {
    python3 - "$1" "$GOLDENS" <<'PY'
import json, os, sys
exp = json.load(open(sys.argv[1])); goldens = sys.argv[2]
disc = exp.get("disc") or {}
suites = disc.get("suites") if isinstance(disc, dict) else None
if isinstance(suites, str):
    suites = [s.strip() for s in suites.split(",") if s.strip()]
if not suites:
    seen = []
    keys = list((exp.get("expect") or {}).keys()) + list(exp.get("must_not_move") or []) + list(exp.get("must_not_regress") or [])
    for k in keys:
        s = k.split("/", 1)[0]
        if any(c in s for c in "*?[") or not s:
            continue
        s = s.replace("_", " ")
        if s not in seen:
            seen.append(s)
    suites = sorted(seen)
ok = [s for s in suites if os.path.isdir(os.path.join(goldens, s.replace(" ", "_"))) or os.path.isdir(os.path.join(goldens, s))]
print(",".join(ok))
PY
}

field() { python3 -c "import json,sys;v=json.load(open(sys.argv[1])).get(sys.argv[2],'');print(v if not isinstance(v,(list,dict)) else json.dumps(v))" "$1" "$2"; }

# The PR a verdict belongs on: the open PR whose head is the branch the
# prediction came from. A host-registered or master prediction goes to its
# issue instead.
pr_for() {   # <source>  -> PR number or empty
    case "$1" in
        lane/*) gh pr list --repo "$GH_REPO" --head "${1%%:*}" --state open --json number --jq '.[0].number' 2>/dev/null ;;
    esac
}
post() {   # <pr> <issue> <body-file>
    if [ -n "$1" ]; then gh pr comment "$1" --repo "$GH_REPO" --body-file "$3" >/dev/null 2>&1 && return 0; fi
    if [ -n "$2" ]; then gh issue comment "$2" --repo "$GH_REPO" --body-file "$3" >/dev/null 2>&1 && return 0; fi
    return 1
}
# A REFUSAL FROM request.sh IS TOLD TO THE LANE, ONCE. request.sh's gates
# (every key must name a golden, the composition rules, the ref must resolve)
# are the project's own; when they refuse a lane's prediction the lane has to
# hear it on its PR, not in a file on the host it cannot read. The skipped
# marker keeps it to one comment; a fixed prediction is a new sha.
refused() {   # <sha> <source> <issue> <which arm> <stderr file>
    local sha=$1 src=$2 issue=$3 arm=$4 err=$5 body="$A/log/$sha.refused.md"
    skip "$sha" "arms=$ARMS_VERSION $src: request.sh refused the $arm arm: $(tail -3 "$err" | tr '\n' ' ')"
    {
        echo "[job.arms] REFUSED: request.sh would not queue the $arm arm of \`${src#*:}\` (sha256 \`${sha:0:12}\`). The prediction is not on the device until this is fixed."
        echo; echo '```'; tail -40 "$err"; echo '```'; echo
        echo "Fix the prediction (a changed file is a new registration and is picked up on the next arms tick, every 30 min), or say on this PR why the refusal is wrong."
    } > "$body"
    post "$(pr_for "$src")" "$issue" "$body" || say "  could not post the refusal for $sha anywhere"
}
skip() { if [ "$mode" = list ]; then echo "  would skip $1: $2"; else echo "$2" > "$A/skipped/$1"; say "  skip $1: $2"; fi; }

# ------------------------------------------------------------------- queue
queued=0
waiting=$(ls "$D"/queue/*.req 2>/dev/null | wc -l)
while read -r sha path src; do
    [ -n "$sha" ] || continue
    already_ran "$sha" && continue
    reg=$(field "$path" registered_utc)
    for k in amended_utc amended_utc_2; do v=$(field "$path" $k); [ -n "$v" ] && [ "$v" \> "$reg" ] && reg=$v; done
    [ -n "$reg" ] && [ "$reg" \< "$SINCE" ] && { history=$((history+1)); continue; }   # history; not a refusal, so not recorded
    a=$(field "$path" a_ref); b=$(field "$path" b_ref); who=$(field "$path" who); issue=$(field "$path" issue)
    [ -n "$a" ] && [ -n "$b" ] || { skip "$sha" "$src: no a_ref/b_ref (a soak or a hand-read prediction)"; continue; }
    [ "$a" != "$b" ] || { skip "$sha" "$src: a_ref == b_ref, nothing to compare"; continue; }
    git -C "$REPO" rev-parse -q --verify "$a^{commit}" >/dev/null || { skip "$sha" "$src: a_ref $a does not resolve"; continue; }
    git -C "$REPO" rev-parse -q --verify "$b^{commit}" >/dev/null || { skip "$sha" "$src: b_ref $b does not resolve"; continue; }
    live_ancestor "$b" || { skip "$sha" "$src: b_ref $b is not an ancestor of $TIP or any lane branch (stale registration; re-register on live refs)"; continue; }
    title=$(field "$path" title)
    if [ -n "$title" ]; then
        skip "$sha" "$src: soak predictions (title=$title) are hand-read; queue with request.sh --title yourself"; continue
    fi
    suites=$(suites_for "$path")
    [ -n "$suites" ] || { skip "$sha" "$src: no suite with goldens in its keys or disc"; continue; }
    if [ "$mode" = list ]; then
        echo "WOULD QUEUE $sha $src who=$who issue=#$issue a=$a b=$b suites=[$suites]"; continue
    fi
    [ "$queued" -lt "$MAX_PAIRS" ] || { say "pair cap $MAX_PAIRS reached this tick; $src waits"; continue; }
    [ "$waiting" -lt "$QUEUE_MAX" ] || { say "queue has $waiting waiting (ARMS_QUEUE_MAX=$QUEUE_MAX); $src waits"; continue; }
    name=$(echo "${who:-arm}" | sed 's/^lane\.//; s/[^A-Za-z0-9_-]/_/g' | cut -c1-24)
    # runs_per_arm is optional. The first version tested "${runs:-1}" and never
    # assigned it, so a prediction without the field handed request.sh
    # --runs "" and its JSON writer died on int(""): the very first arm the
    # job ever queued (#89, 02:56Z) was refused for that and nothing else.
    runs=$(field "$path" runs_per_arm); [[ "$runs" =~ ^[0-9]+$ ]] && [ "$runs" -ge 1 ] || runs=1
    say "queue $src: $name #$issue a=$a b=$b suites=[$suites] runs=$runs"
    qa=$(cd "$REPO" && DISPATCH_DIR="$D" bash "$T/request.sh" --who "arms-$name-base" --ref "$a" --suites "$suites" --runs "$runs" \
            --expect "$path" --purpose "BASE arm ${issue:+#$issue }$who at $a, queued by the arms job from $src" 2>"$A/log/$sha.base.err") \
        || { refused "$sha" "$src" "$issue" base "$A/log/$sha.base.err"; continue; }
    qb=$(cd "$REPO" && DISPATCH_DIR="$D" bash "$T/request.sh" --who "arms-$name-fix" --ref "$b" --suites "$suites" --runs "$runs" \
            --expect "$path" --purpose "FIX arm ${issue:+#$issue }$who at $b, queued by the arms job from $src" 2>"$A/log/$sha.fix.err") \
        || { refused "$sha" "$src" "$issue" "fix (the base arm ${qa##* } is queued and will run unpaired)" "$A/log/$sha.fix.err"; continue; }
    ida="${qa##* }"; idb="${qb##* }"
    python3 - "$A/pairs/$sha.json" "$sha" "$ida" "$idb" "$path" "$src" "$who" "$issue" "$a" "$b" "$suites" <<'PY'
import json, sys, datetime
p, sha, ida, idb, path, src, who, issue, a, b, suites = sys.argv[1:]
json.dump({"sha": sha, "id_a": ida, "id_b": idb, "expect": path, "source": src, "who": who, "issue": issue,
           "a_ref": a, "b_ref": b, "suites": suites,
           "queued_utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")},
          open(p, "w"), indent=2)
PY
    say "  queued base $ida fix $idb"
    queued=$((queued + 1)); waiting=$((waiting + 2))
done < <(collect)
[ "$mode" = list ] && { echo "--- $history prediction(s) older than the watermark $SINCE were not considered (edit $A/since to move it)"; echo "--- skipped (delete $A/skipped/<sha> to reconsider):"; for f in "$A"/skipped/*; do [ -e "$f" ] && echo "  $(basename "$f") $(cat "$f")"; done; exit 0; }

# ------------------------------------------------------------------- judge
for pair in "$A"/pairs/*.json; do
    [ -f "$pair" ] || continue
    sha=$(field "$pair" sha); [ -f "$A/judged/$sha" ] && continue
    ida=$(field "$pair" id_a); idb=$(field "$pair" id_b); exp=$(field "$pair" expect)
    src=$(field "$pair" source); who=$(field "$pair" who); issue=$(field "$pair" issue)
    RA="$D/results/$ida"; RB="$D/results/$idb"
    body="$A/pairs/$sha.comment.md"
    if [ -f "$RA/ERROR" ] || [ -f "$RB/ERROR" ]; then
        {
            echo "[job.arms] ARM ERROR for $who ${issue:+(#$issue)} -- no verdict."
            echo
            echo "a_ref $(field "$pair" a_ref) ($ida): $( [ -f "$RA/ERROR" ] && head -3 "$RA/ERROR" || echo ok )"
            echo "b_ref $(field "$pair" b_ref) ($idb): $( [ -f "$RB/ERROR" ] && head -3 "$RB/ERROR" || echo ok )"
            echo
            echo "A half-run pair is not compared (a missing arm is absent, not zero). Fix the cause and register a fresh prediction, or delete \`\$WORK/arms/judged/$sha\` and \`\$WORK/arms/pairs/$sha.json\` to have the job queue it again."
        } > "$body"
        post "$(pr_for "$src")" "$issue" "$body" || say "  could not post the ARM ERROR for $sha anywhere"
        echo "ERROR" > "$A/judged/$sha"; say "judged $sha: ARM ERROR ($src)"
        continue
    fi
    [ -f "$RA/DONE" ] && [ -f "$RB/DONE" ] || continue
    out="$A/pairs/$sha.verdict.txt"
    (cd "$REPO" && DISPATCH_DIR="$D" python3 "$T/ab_compare.py" --a "$RA" --b "$RB" --expect "$exp" --json "$A/pairs/$sha.verdict.json") > "$out" 2>&1
    verdict=$(grep -m1 '^VERDICT:' "$out" || echo "VERDICT: (none printed; see the full output)")
    pr=$(pr_for "$src")
    {
        echo "[job.arms] $verdict"
        echo
        echo "| | |"; echo "|---|---|"
        echo "| prediction | \`$src\` (sha256 \`${sha:0:12}\`) |"
        echo "| who / issue | $who ${issue:+/ #$issue} |"
        echo "| a_ref (base) | \`$(field "$pair" a_ref)\` result \`$ida\` |"
        echo "| b_ref (fix) | \`$(field "$pair" b_ref)\` result \`$idb\` |"
        echo "| suites | $(field "$pair" suites) |"
        echo "| judged | $(date -u '+%FT%TZ') by ab_compare.py on the host; full text in \`\$WORK/arms/pairs/$sha.verdict.txt\` |"
        echo
        echo "<details><summary>ab_compare output (first 80 lines)</summary>"
        echo; echo '```'; head -80 "$out"; echo '```'; echo "</details>"
    } > "$body"
    post "$pr" "$issue" "$body" || say "  could not post the verdict for $sha anywhere"
    if [ -n "$pr" ]; then
        case "$verdict" in
            *PASS*) label_add "$pr" verified && label_rm "$pr" regressed || say "  WARNING: #$pr judged PASS but could not be labelled verified" ;;
            *FAIL*) label_add "$pr" regressed && label_rm "$pr" verified || say "  WARNING: #$pr judged FAIL but could not be labelled regressed" ;;
        esac
    fi
    echo "$verdict" > "$A/judged/$sha"; say "judged $sha: $verdict ($src${pr:+, PR #$pr})"
done

[ -x "$T/jobs/status.sh" ] && bash "$T/jobs/status.sh" >/dev/null 2>&1
exit 0
