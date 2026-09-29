# Sourced by ../selftest.sh with the harness already built: $T, $TESTING,
# $REPO, $GOLDENS, the shims on PATH, ok/bad/check. Not executable, no
# shebang, no exit.
#
# A FAIL whose two arms ran on two devices is CONFOUNDED, not `regressed`, and
# a pin to a HELD device waits instead of falling through (lane.armsconfound).
#
# #583 (the #414 Forza fix) was labelled `regressed` on 2026-09-28 from a FAIL
# whose base arm ran on the thor and fix arm on the nova: the thor was under a
# hold when the fix arm came up, affinity.py read "held" as "gone" and let
# both pins fall through, and arms.sh counted a verdict ab_compare itself
# called unattributable. Nothing queued the same-device pair it asked for.
#
# Builds its own work dir, dispatch dir and pairs under $T/confound, and runs
# the real request.sh against the harness's $REPO and $GOLDENS, so nothing
# another fragment left behind decides a check, and it leaves nothing either.
#
# CF_ARMS and CF_AFF name the arms.sh and affinity.py under test (default: this
# tree's). Pointing them at origin/master's copies is the falsification run;
# docs/lanes/armsconfound/NOTES.md has its output.

echo "== arms.sh: a FAIL across two devices is confounded; affinity waits for a held device"

CF="$T/confound"; CW="$CF/work"; CD="$CF/dispatch"
CF_ARMS="${CF_ARMS:-$TESTING/jobs/arms.sh}"; CF_AFF="${CF_AFF:-$TESTING/affinity.py}"
rm -rf "$CF"; mkdir -p "$CW/arms"/{pairs,judged,log,expect} "$CW/logs/arms" "$CD"/{queue,running,results,expect,lanes,hold}
sleep 600 & CFPID=$!                       # a pid that is certainly alive: the nova's worker
printf '%s\n' "$CFPID" > "$CD/lanes/nova"  # the thor has no registration: a held worker drops it
: > "$CD/hold/thor"                        # ...because it is held, freshly
date -u '+%FT%TZ' > "$CW/arms/since"       # fences every committed prediction: only the pairs below exist
CFB=$(git -C "$REPO" rev-parse --short HEAD); CFA=$(git -C "$REPO" rev-parse --short "HEAD~1")

cfpair() {   # <branch> <nick> <issue> <device A> <device B> [<registered>]  -> sets $sha
    local br=$1 nick=$2 issue=$3 exp="$CW/arms/expect/$2.json"
    python3 - "$exp" "$issue" "$CFA" "$CFB" "$nick" "${6:-2026-09-28T20:00:00Z}" <<'PY'
import json, sys
p, issue, a, b, nick, reg = sys.argv[1:]
json.dump({"registered_utc": reg, "who": "lane.forzadecay414", "issue": issue,
           "a_ref": a, "b_ref": b, "nick": nick,
           "expect": {"Blend_surface/TestA": 0}}, open(p, "w"), indent=2)
PY
    sha=$(sha256sum "$exp" | cut -d' ' -f1)
    python3 - "$CW/arms/pairs/$sha.json" "$sha" "$exp" "$br" "$nick" "$issue" "$CFA" "$CFB" <<'PY'
import json, sys
p, sha, exp, br, nick, issue, a, b = sys.argv[1:]
json.dump({"sha": sha, "id_a": nick + "-a", "id_b": nick + "-b", "expect": exp,
           "source": "%s:docs/testing/predictions/%s.json" % (br, nick),
           "who": "lane.forzadecay414", "issue": issue, "a_ref": a, "b_ref": b,
           "suites": "Blend surface", "queued_utc": "2026-09-28T20:00:00Z"}, open(p, "w"), indent=2)
PY
    local arm dev
    for arm in a b; do
        [ "$arm" = a ] && dev=$4 || dev=$5
        mkdir -p "$CD/results/$nick-$arm"; : > "$CD/results/$nick-$arm/DONE"
        printf '{"expect": "%s"}\n' "$exp" > "$CD/results/$nick-$arm/request.json"
        printf '{"device_label": "%s"}\n' "$dev" > "$CD/results/$nick-$arm/result.json"
    done
    echo "VERDICT: FAIL -- 2 of 3379 checks violated:" > "$CW/arms/judged/$sha"
    echo "VERDICT: FAIL -- 2 of 3379 checks violated:" > "$CW/arms/pairs/$sha.verdict.txt"
}
cfpair lane/cfsplit forzadecay414-fix-pixels 583 thor nova; SPLIT=$sha
cfpair lane/cfsame  forzadecay414-same-pixels 584 thor thor; SAME=$sha
# #583 as it really stands: a later registration on the same issue is queued,
# so the confounded verdict is superseded whatever a re-run would say.
cfpair lane/cfnewer forzadecay414-old-pixels 585 thor nova; OLDER=$sha
cfpair lane/cfnewer forzadecay414-new-pixels 585 thor thor 2026-09-29T01:00:00Z
rm -f "$CW/arms/judged/$sha" "$CW/arms/pairs/$sha.verdict.txt" \
      "$CD/results/forzadecay414-new-pixels-a/DONE" "$CD/results/forzadecay414-new-pixels-b/DONE"
printf 'lane/cfsplit\t583\nlane/cfsame\t584\nlane/cfnewer\t585\n' > "$CW/arms/log/prs.tsv"

cfst() { HAKUX_WORK="$CW" DISPATCH_DIR="$CD" bash "$CF_ARMS" state "$1" 2>&1; }
cftick() {
    ( export HAKUX_WORK="$CW" DISPATCH_DIR="$CD" ARMS_MAX_PAIRS_PER_TICK=0 SELFTEST_LABELS=regressed
      bash "$CF_ARMS" ) >/dev/null 2>&1
}
cfreqs() { grep -l "\"expect_sha\": *\"$1\"" "$CD"/queue/*.req 2>/dev/null | wc -l; }

# ------------------------------------------------------------ the label
s=$(cfst lane/cfsplit)
check "(A1) a FAIL with its arms on thor and nova does not label the PR regressed" \
    grep -qx 'STATE=none' <<< "$s"
check "(A1) state names it confounded, with both devices" \
    grep -qx 'confounded forzadecay414-fix-pixels.json (A thor, B nova)' <<< "$s"
check "(A2) CONTROL: the same FAIL with both arms on the thor is still regressed (narrowed, not disabled)" \
    grep -qx 'STATE=regressed' <<< "$(cfst lane/cfsame)"

# ------------------------------------------ the tick: one same-device pair
: > "$SELFTEST_GH_LOG"; cftick
check "(A3) the tick queues exactly one same-device pair (two requests) for the confounded FAIL" \
    [ "$(cfreqs "$SPLIT")" = 2 ]
check "(A3) both are HARD-pinned to the thor, where the base arm ran" \
    python3 -c 'import json,sys
rs=[json.load(open(f)) for f in sys.argv[1:]]
sys.exit(0 if len(rs)==2 and all(r.get("device")=="thor" and r.get("pin")=="hard" for r in rs) else 1)' \
    $(grep -l "\"expect_sha\": *\"$SPLIT\"" "$CD"/queue/*.req 2>/dev/null)
check "(A3) the base and the fix ref are the pair's own" \
    bash -c 'grep -q "\"ref\": \"$1\"" $3 && grep -q "\"ref\": \"$2\"" $3' -- "$CFA" "$CFB" \
    "$(grep -l "\"expect_sha\": *\"$SPLIT\"" "$CD"/queue/*.req 2>/dev/null | tr '\n' ' ')"
check "(A3) the pair record names the re-run, and the judged marker is gone so it is judged again" \
    bash -c 'grep -q "\"rerun\"" "$1" && [ ! -f "$2" ]' -- "$CW/arms/pairs/$SPLIT.json" "$CW/arms/judged/$SPLIT"
check "(A3) the PR comment says CONFOUNDED FAIL (A thor, B nova) and names the queued ids" \
    grep -q 'CONFOUNDED FAIL (A thor, B nova): not attributable; same-device pair queued as' "$CW/arms/pairs/$SPLIT.comment.md"
check "(A3) and regressed comes off #583" \
    grep -q 'DELETE repos/example/hakux/issues/583/labels/regressed' "$SELFTEST_GH_LOG"
check "(A3) the same-device FAIL's PR (#584) is not touched" \
    bash -c '! grep -q "issues/584\|comment 584" "$1"' -- "$SELFTEST_GH_LOG"
check "(A3) the same-device FAIL queued nothing" [ "$(cfreqs "$SAME")" = 0 ]
check "(A6) a confounded FAIL already superseded by a later registration queues no re-run" \
    [ "$(cfreqs "$OLDER")" = 0 ]
check "(A6) and its comment says why" \
    grep -q 'no same-device pair queued: not needed: forzadecay414-new-pixels.json' "$CW/arms/pairs/$OLDER.comment.md"
: > "$SELFTEST_GH_LOG"; cftick
check "(A4) a second tick queues nothing more" [ "$(cfreqs "$SPLIT")" = 2 ]
check "(A4) and says nothing more on #583" bash -c '! grep -q "583" "$1"' -- "$SELFTEST_GH_LOG"

# The hard pin holds where a load pin falls through: thor held past any
# bound, nova serving and idle. The fix arm of the re-run stays on the thor.
fixreq=$(grep -l '"requester": "arms-forzadecay414-fix"' $(grep -l "\"expect_sha\": *\"$SPLIT\"" "$CD"/queue/*.req 2>/dev/null) 2>/dev/null | head -1)
rm -f "$CD/hold/thor"
check "(A5) the re-run's hard pin does not fall through when the thor is neither serving nor held" \
    [ "$(python3 "$CF_AFF" "$CD" "${fixreq:-/nonexistent}" 2>/dev/null)" = thor ]

# ------------------------------------------------------ B: affinity.py
AD2="$CF/aff"; mkdir -p "$AD2"/{lanes,queue,running,results,hold,splits}
printf '%s\n' "$CFPID" > "$AD2/lanes/nova"          # nova serving; thor's worker dropped its lane on the hold
mkdir -p "$AD2/results/base-1"
printf '{"expect":"/p/forzadecay414-fix-pixels.json"}\n' > "$AD2/results/base-1/request.json"
printf '{"device_label":"thor"}\n'                  > "$AD2/results/base-1/result.json"
printf '{"requester":"arms-forzadecay414-fix","device":"thor","expect":"/p/forzadecay414-fix-pixels.json"}\n' > "$AD2/fix.req"
aff() { python3 "$CF_AFF" "$AD2" "$AD2/fix.req" 2>/dev/null; }
: > "$AD2/hold/thor"
check "(B1) sibling ran on the thor, thor freshly HELD: the fix arm waits for the thor" [ "$(aff)" = thor ]
check "(B1) --available says a held device is coming back" python3 "$CF_AFF" "$AD2" --available thor
touch -d '4 hours ago' "$AD2/hold/thor"
check "(B2) the hold is older than the bound (3 h): the pin falls through as before" [ -z "$(aff)" ]
rm -f "$AD2/hold/thor"
check "(B3) thor neither serving nor held (gone): falls through at once" [ -z "$(aff)" ]
check "(B3) --available says a gone device is gone" bash -c '! python3 "$1" "$2" --available thor' -- "$CF_AFF" "$AD2"
: > "$AD2/hold/thor"; rm -rf "$AD2/results/base-1"
check "(B4) CONTROL: a load pin to a held device with NO sibling landed still falls through (#503)" [ -z "$(aff)" ]
printf '{"requester":"arms-forzadecay414-base","device":"thor","expect":"/p/forzadecay414-fix-pixels.json"}\n' > "$AD2/running/base-2.req"
printf 'thor\n' > "$AD2/running/base-2.owner"
check "(B5) a sibling still RUNNING on the held thor pins the fix arm there too" [ "$(aff)" = thor ]
rm -f "$AD2/running/base-2.req" "$AD2/running/base-2.owner"
mkdir -p "$AD2/results/base-3"
printf '{"expect":"/p/forzadecay414-fix-pixels.json"}\n' > "$AD2/results/base-3/request.json"
printf '{"device_label":"nova"}\n'                  > "$AD2/results/base-3/result.json"
rm -f "$AD2/lanes/nova"; : > "$AD2/lanes/thor.lastbrief"
check "(B6) CONTROL, 09-13: sibling on a nova that is neither serving nor held falls through, not stalls" \
    [ "$(python3 "$CF_AFF" "$AD2" "$AD2/fix.req" 2>/dev/null)" != nova ]

kill "$CFPID" 2>/dev/null; wait "$CFPID" 2>/dev/null
rm -rf "$CF"
