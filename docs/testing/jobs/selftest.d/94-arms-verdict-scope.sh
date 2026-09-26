# Sourced by ../selftest.sh with the harness already built: $T, $TESTING, the
# shims on PATH, ok/bad/check. Not executable, no shebang, no exit.
#
# arms.sh: a PR's label counts the verdicts of its OWN predictions, not every
# verdict ever collected from a branch of the same name.
#
# lane.remote reuses one branch for every PR it opens. On 2026-09-26 PR #389 on
# that branch was labelled by #60's 09-20 PASS and listed four 09-20 FAILs as
# `withdrawn`, all five folded to master with earlier PRs. This builds that
# history in its own repository: an earlier PR on `claude/reuse` whose PASS and
# FAIL predictions (and the FAIL's code) were folded, then a new PR on the same
# branch name with a prediction of its own.
#
# The mutants run against a copy of arms.sh; the real file is never edited.

echo "== arms.sh: a PR's label counts only its own predictions"

VD="$T/vscope"; VR="$VD/repo"
mkdir -p "$VR/src" "$VR/docs/testing/predictions"
vg() { git -C "$VR" -c user.name=t -c user.email=t@t -c commit.gpgsign=false "$@"; }
vg init -q -b master
for f in a b c; do seq -f "$f %g" 0 19 > "$VR/src/$f.c"; done
echo '{"n": "folded-by-hand"}' > "$VR/docs/testing/predictions/edited.json"
vg add -A; vg commit -qm base
V_BASE=$(vg rev-parse HEAD)

# The earlier PR: two predictions and the FAIL's code, folded to master.
vg checkout -q -b claude/reuse
echo "a 1" >> "$VR/src/a.c"; vg commit -qam "old candidate"
V_OLD_B=$(vg rev-parse HEAD)
echo '{"n": "old-pass"}' > "$VR/docs/testing/predictions/old-pass.json"
echo '{"n": "old-fail"}' > "$VR/docs/testing/predictions/old-fail.json"
vg add -A; vg commit -qm "old predictions"
vg checkout -q master; vg merge -q --no-ff --no-edit claude/reuse >/dev/null
vg update-ref refs/remotes/origin/master "$(vg rev-parse HEAD)"

# The new PR on the same branch name, cut from the folded master.
vg checkout -q -B claude/reuse master
echo "b 1" >> "$VR/src/b.c"; vg commit -qam "new candidate"
V_NEW_B=$(vg rev-parse HEAD)
echo '{"n": "new"}' > "$VR/docs/testing/predictions/new.json"
echo '{"n": "edited-again"}' > "$VR/docs/testing/predictions/edited.json"
vg add -A; vg commit -qm "new prediction, and an edit to a folded one"
vg update-ref refs/remotes/origin/claude/reuse "$(vg rev-parse HEAD)"

# A single-use lane: its prediction is in its diff, one PASS and one FAIL.
vg checkout -q -B lane/single master
echo "c 1" >> "$VR/src/c.c"; vg commit -qam "single candidate"
V_SINGLE_B=$(vg rev-parse HEAD)
echo '{"n": "single-pass"}' > "$VR/docs/testing/predictions/single-pass.json"
echo '{"n": "single-fail"}' > "$VR/docs/testing/predictions/single-fail.json"
vg add -A; vg commit -qm "single predictions"
vg update-ref refs/remotes/origin/lane/single "$(vg rev-parse HEAD)"

# A lane that deletes its own FAILed prediction: never on master, so its
# verdict still counts. Deleting a registration must not clear a FAIL.
vg checkout -q -B lane/deleter master
echo "c 2" >> "$VR/src/c.c"; echo '{"n": "gone"}' > "$VR/docs/testing/predictions/gone.json"
vg add -A; vg commit -qm "candidate and prediction"
V_DEL_B=$(vg rev-parse HEAD)
vg rm -q docs/testing/predictions/gone.json; vg commit -qm "drop the prediction"
vg update-ref refs/remotes/origin/lane/deleter "$(vg rev-parse HEAD)"
vg checkout -q master
V_MASTER=$(vg rev-parse HEAD)

# ------------------------------------------------------------ the verdicts
VW="$VD/work"; mkdir -p "$VW/arms"/{pairs,judged,log,expect} "$VW/dispatch"/{queue,running,results,expect}
vsha() { echo "$1 $2" | sha256sum | cut -c1-64; }
vpair() {   # <branch> <nick> <issue> <queued> <a> <b> [<verdict>]
    local sha; sha=$(vsha "$1" "$2")
    python3 - "$VW/arms/pairs/$sha.json" "$sha" "$1" "$2" "$3" "$4" "$5" "$6" <<'PY'
import json, sys
p, sha, br, nick, issue, q, a, b = sys.argv[1:]
json.dump({"sha": sha, "id_a": nick + "-a", "id_b": nick + "-b", "expect": "",
           "source": "%s:docs/testing/predictions/%s.json" % (br, nick),
           "who": "lane.vs", "issue": issue, "a_ref": a, "b_ref": b,
           "queued_utc": q}, open(p, "w"), indent=2)
PY
    [ -z "${7:-}" ] || echo "VERDICT: $7" > "$VW/arms/judged/$sha"
}
VFAIL="FAIL -- 3 of 9 checks violated:"; VPASS="PASS -- all 9 registered checks hold."
vpair claude/reuse old-pass    60 2026-09-20T01:00:00Z "$V_BASE" "$V_OLD_B" "$VPASS"
vpair claude/reuse old-fail    61 2026-09-20T02:00:00Z "$V_BASE" "$V_OLD_B" "$VFAIL"
vpair claude/reuse new         70 2026-09-26T01:00:00Z "$V_MASTER" "$V_NEW_B"          # not judged yet
vpair claude/reuse edited      71 2026-09-26T02:00:00Z "$V_MASTER" "$V_NEW_B" "$VFAIL"
vpair lane/single  single-pass 80 2026-09-26T01:00:00Z "$V_MASTER" "$V_SINGLE_B" "$VPASS"
vpair lane/single  single-fail 81 2026-09-26T02:00:00Z "$V_MASTER" "$V_SINGLE_B" "$VFAIL"
vpair lane/deleter gone        90 2026-09-26T01:00:00Z "$V_MASTER" "$V_DEL_B" "$VFAIL"
V_NEW=$(vsha claude/reuse new); V_EDITED=$(vsha claude/reuse edited)

vst() {   # <arms.sh> <branch> [<sha> <verdict>]
    HAKUX_WORK="$VW" DISPATCH_DIR="$VW/dispatch" HAKUX_REPO_DIR="$VR" HAKUX_TIP=master bash "$1" state "$2" "${3:-}" "${4:-}" 2>&1
}
# One line per case: the state, what the table counts, and what is withdrawn.
vcases() {   # <arms.sh>
    local s c
    for c in "reuse claude/reuse" "reuse-unjudged claude/reuse $V_EDITED UNJUDGED" "reuse-judged claude/reuse $V_EDITED PASS" \
             "reuse-new-pass claude/reuse $V_EDITED PASS" "single lane/single" "deleter lane/deleter"; do
        set -- $c
        case "$1" in reuse-new-pass) echo "VERDICT: $VPASS" > "$VW/arms/judged/$V_NEW" ;; esac
        s=$(vst "$VSCRIPT" "$2" "${3:-}" "${4:+VERDICT: $4}")
        rm -f "$VW/arms/judged/$V_NEW"
        echo "$1 $(sed -n '1s/^STATE=//p' <<< "$s")" \
             "counts[$(grep -o '^| [A-Z]* | `[^`]*`' <<< "$s" | sed 's/^| //; s/ | `/:/; s/`$//' | sort | tr '\n' ' ')]" \
             "withdrawn[$(sed -n 's/^withdrawn //p' <<< "$s" | tr '\n' ' ')]"
    done
}
VWANT="reuse regressed counts[FAIL:edited.json ] withdrawn[]
reuse-unjudged none counts[] withdrawn[]
reuse-judged verified counts[PASS:edited.json ] withdrawn[]
reuse-new-pass verified counts[PASS:edited.json PASS:new.json ] withdrawn[]
single regressed counts[FAIL:single-fail.json PASS:single-pass.json ] withdrawn[]
deleter regressed counts[FAIL:gone.json ] withdrawn[]"

VSCRIPT="$TESTING/jobs/arms.sh"; vgot=$(vcases)
vline() { grep "^$1 " <<< "$vgot"; }
vout=$(vst "$VSCRIPT" claude/reuse "$V_EDITED" "VERDICT: $VPASS")
check "the folded PR's PASS does not label the new PR" \
    bash -c '! grep -q "old-pass" <<< "$1"' -- "$vout"
check "the folded PR's FAIL is neither counted nor listed withdrawn" \
    bash -c '! grep -q "old-fail" <<< "$1"' -- "$vout"
check "  and with no verdict of its own yet, the new PR has no label at all" \
    [ "$(vline reuse-unjudged)" = "reuse-unjudged none counts[] withdrawn[]" ]
check "the new PR's own verdict labels it" [ "$(vline reuse-judged)" = "reuse-judged verified counts[PASS:edited.json ] withdrawn[]" ]
check "  and a folded prediction the new PR edits is the new PR's" bash -c '[[ "$1" == *edited.json* ]]' -- "$(vline reuse)"
check "  and a second own verdict counts beside it" [ "$(vline reuse-new-pass)" = "reuse-new-pass verified counts[PASS:edited.json PASS:new.json ] withdrawn[]" ]
check "a single-use lane labels exactly as before" \
    [ "$(vline single)" = "single regressed counts[FAIL:single-fail.json PASS:single-pass.json ] withdrawn[]" ]
check "deleting a lane's own FAILed prediction does not clear the FAIL" \
    [ "$(vline deleter)" = "deleter regressed counts[FAIL:gone.json ] withdrawn[]" ]
check "every case exactly as specified" [ "$vgot" = "$VWANT" ]

# ------------------------------------------------- the tick posts nothing on it
# The withdrawal pass walks every branch in the index. Before the fix it read the
# folded FAIL as withdrawn on the reused branch's open PR, read the folded PASS
# as verified, and took `regressed` off it with a comment. The new PR has no
# verdict of its own here (its FAIL's marker is set aside for the tick).
printf 'claude/reuse\t389\nlane/single\t402\n' > "$VW/arms/log/prs.tsv"
mv "$VW/arms/judged/$V_EDITED" "$VD/edited.judged"
: > "$SELFTEST_GH_LOG"
( export HAKUX_WORK="$VW" DISPATCH_DIR="$VW/dispatch" HAKUX_REPO_DIR="$VR" HAKUX_TIP=master \
         ARMS_MAX_PAIRS_PER_TICK=0 SELFTEST_LABELS=regressed
  bash "$TESTING/jobs/arms.sh" ) >/dev/null 2>&1
mv "$VD/edited.judged" "$VW/arms/judged/$V_EDITED"
check "the tick posts no withdrawal on the reused branch's PR" \
    bash -c '! grep -q -e "issues/389/" -e "comment 389" "$1"' -- "$SELFTEST_GH_LOG"

# ------------------------------------------------------------------ mutants
vmutant() {   # <label> <literal to replace> <replacement> <case that must go wrong>
    local md="$VD/mut-$RANDOM"; mkdir -p "$md"
    cp "$TESTING/jobs/gh-label.sh" "$TESTING/jobs/localtime.sh" "$md/"
    python3 - "$TESTING/jobs/arms.sh" "$md/arms.sh" "$2" "$3" <<'PY'
import sys
src, dst, old, new = sys.argv[1:]
s = open(src).read()
assert s.count(old) == 1, "mutant anchor %r matches %d times" % (old, s.count(old))
open(dst, "w").write(s.replace(old, new))
PY
    [ -f "$md/arms.sh" ] || { bad "mutant '$1': its anchor no longer matches arms.sh"; return; }
    local mg; VSCRIPT="$md/arms.sh"; mg=$(vcases); VSCRIPT="$TESTING/jobs/arms.sh"
    if [ "$mg" = "$VWANT" ]; then bad "mutant '$1' passes every case (the fragment cannot see it)"
    elif [ "$(grep "^$4 " <<< "$mg")" != "$(grep "^$4 " <<< "$VWANT")" ]; then ok "mutant '$1' is red on ($4)"
    else bad "mutant '$1' is red, but not on ($4): $(tr '\n' ';' <<< "$mg")"; fi
}
VANCHOR='rows = [r for r in rows if not (r["pred"] in folded and r["pred"] not in have)]'
vmutant "no scoping: the branch name decides" "$VANCHOR" 'pass' reuse-unjudged
vmutant "scoped by the diff alone: deleting a prediction clears its FAIL" \
    "$VANCHOR" 'rows = [r for r in rows if r["pred"] in have]' deleter
vmutant "scoped by the trunk alone: a PR's edit to a folded prediction is dropped" \
    "$VANCHOR" 'rows = [r for r in rows if r["pred"] not in folded]' reuse
rm -rf "$VD"
