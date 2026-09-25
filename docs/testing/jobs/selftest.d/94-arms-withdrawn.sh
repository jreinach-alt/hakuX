# Sourced by ../selftest.sh with the harness already built: $T, $TESTING, the
# shims on PATH, ok/bad/check. Not executable, no shebang, no exit.
#
# arms.sh: a FAIL whose registered code is gone from the branch is
# `withdrawn`, not `regressed` (dispatch-hardening defect 11, decision #257).
#
# PR #252 refuted its candidate, reverted it, and was left a docs-only branch
# labelled `regressed` that no arm could ever supersede. This builds its own git
# repository, its own $HAKUX_WORK and its own dispatch dir, so nothing another
# fragment left behind can decide a check here, and it leaves nothing either.
#
# THE MUTANTS RUN HERE TOO, each against a copy of arms.sh in a scratch dir:
# the real file is never edited, so a failed run cannot leave a mutant in it.

echo "== arms.sh: a FAIL whose code is gone from the branch is withdrawn"

WD="$T/withdrawn"; WR="$WD/repo"
mkdir -p "$WR"
g() { git -C "$WR" -c user.name=t -c user.email=t@t -c commit.gpgsign=false "$@"; }
g init -q -b master
mkdir -p "$WR/src" "$WR/docs/lanes/wd"
for f in a b c; do echo "$f 0" > "$WR/src/$f.c"; done
echo notes > "$WR/docs/lanes/wd/NOTES.md"
g add -A; g commit -qm base
A_REF=$(g rev-parse HEAD)
g update-ref refs/remotes/origin/master "$A_REF"

# The refuted candidate: two code files, and the lane's NOTES alongside them.
g checkout -q -b cand
echo "a 1" > "$WR/src/a.c"; echo "b 1" > "$WR/src/b.c"; echo "notes: tried it" > "$WR/docs/lanes/wd/NOTES.md"
g commit -qam candidate
B_REF=$(g rev-parse HEAD)
# A second, separate candidate on src/c.c, for the three-arm branch.
g checkout -q -b cand2 master
echo "c 1" > "$WR/src/c.c"; g commit -qam candidate2
C_REF=$(g rev-parse HEAD)

branch() {   # <name> <start> [<file-to-revert>...]  -> refs/remotes/origin/lane/<name>
    local name=$1 start=$2; shift 2
    g checkout -q -B "wd-$name" "$start"
    if [ $# -gt 0 ]; then
        g checkout -q "$A_REF" -- "$@"; g commit -qm "revert $*"
    fi
    g update-ref "refs/remotes/origin/lane/$name" "$(g rev-parse HEAD)"
}
branch full    "$B_REF" src/a.c src/b.c   # (a) fully reverted; NOTES still differ from master
branch part    "$B_REF" src/a.c           # (b) src/b.c is still there
branch intact  "$B_REF"                   # (c) nothing reverted
# (d) docs only, never any code: a PASS whose arm was about b_ref
g checkout -q -B wd-pass "$A_REF"; echo "notes: pass" > "$WR/docs/lanes/wd/NOTES.md"; g commit -qam docs
g update-ref refs/remotes/origin/lane/pass "$(g rev-parse HEAD)"
# (e) three arms on one branch, the withdrawn one in the MIDDLE: a first-wins or
# last-wins reading of "which FAIL is gone" names the wrong one. The branch keeps
# cand2's src/c.c and reverts cand's two files.
g checkout -q -B wd-three "$C_REF"; g merge -q --no-edit "$B_REF" >/dev/null
g checkout -q "$A_REF" -- src/a.c src/b.c; g commit -qm "revert the refuted half"
g update-ref refs/remotes/origin/lane/three "$(g rev-parse HEAD)"
g checkout -q master

# ------------------------------------------------------------ the verdicts
WW="$WD/work"; mkdir -p "$WW/arms"/{pairs,judged,log,expect} "$WW/dispatch"/{queue,running,results,expect}
wpair() {   # <branch> <nick> <issue> <registered> <a> <b> <verdict>
    local sha; sha=$(echo "$1 $2" | sha256sum | cut -c1-64)
    python3 - "$WW/arms/pairs/$sha.json" "$sha" "$1" "$2" "$3" "$4" "$5" "$6" <<'PY'
import json, sys
p, sha, br, nick, issue, reg, a, b = sys.argv[1:]
json.dump({"sha": sha, "id_a": nick + "-a", "id_b": nick + "-b", "expect": "",
           "source": "lane/%s:docs/testing/predictions/%s.json" % (br, nick),
           "who": "lane.wd", "issue": issue, "a_ref": a, "b_ref": b,
           "queued_utc": reg}, open(p, "w"), indent=2)
PY
    echo "VERDICT: $7" > "$WW/arms/judged/$sha"
}
FAILV="FAIL -- 3 of 9 checks violated:"; PASSV="PASS -- all 9 registered checks hold."
wpair full   wd-full-arm   224 2026-09-25T01:00:00Z "$A_REF" "$B_REF" "$FAILV"
wpair part   wd-part-arm   224 2026-09-25T01:00:00Z "$A_REF" "$B_REF" "$FAILV"
wpair intact wd-intact-arm 224 2026-09-25T01:00:00Z "$A_REF" "$B_REF" "$FAILV"
wpair pass   wd-pass-arm   225 2026-09-25T01:00:00Z "$A_REF" "$B_REF" "$PASSV"
wpair three  wd-first-pass  301 2026-09-25T01:00:00Z "$A_REF" "$C_REF" "$PASSV"
wpair three  wd-middle-fail 302 2026-09-25T02:00:00Z "$A_REF" "$B_REF" "$FAILV"
wpair three  wd-last-pass   303 2026-09-25T03:00:00Z "$A_REF" "$C_REF" "$PASSV"

wst() {   # <arms.sh> <branch>
    HAKUX_WORK="$WW" DISPATCH_DIR="$WW/dispatch" HAKUX_REPO_DIR="$WR" HAKUX_TIP=master bash "$1" state "lane/$2" 2>&1
}
cases() {   # <arms.sh> -> one "<case> <STATE> <withdrawn names>" line per case
    local s c
    for c in full part intact pass three; do
        s=$(wst "$1" "$c")
        echo "$c $(sed -n '1s/^STATE=//p' <<< "$s") [$(sed -n 's/^withdrawn //p' <<< "$s" | tr '\n' ' ')]"
    done
}
WANT="full none [wd-full-arm.json ]
part regressed []
intact regressed []
pass verified []
three verified [wd-middle-fail.json ]"

got=$(cases "$TESTING/jobs/arms.sh")
line() { grep "^$1 " <<< "$got"; }
check "(a) a fully reverted refuted branch is not regressed" bash -c '[[ "$1" != *regressed* ]]' -- "$(line full)"
check "(a) and state prints 'withdrawn <prediction>' for it" \
    grep -qx 'withdrawn wd-full-arm.json' <<< "$(wst "$TESTING/jobs/arms.sh" full)"
check "(a) its markdown names the code that is gone" \
    grep -q 'no longer changes `src/a.c`, `src/b.c`' <<< "$(wst "$TESTING/jobs/arms.sh" full)"
check "(b) a partly reverted branch stays regressed, nothing withdrawn" [ "$(line part)" = "part regressed []" ]
check "(c) a branch whose FAIL code is intact stays regressed" [ "$(line intact)" = "intact regressed []" ]
check "(d) a PASS on a branch with no code change stays verified" [ "$(line pass)" = "pass verified []" ]
check "(e) of three arms, only the middle FAIL is withdrawn, and the PASSes count" \
    [ "$(line three)" = "three verified [wd-middle-fail.json ]" ]
check "every case exactly as specified" [ "$got" = "$WANT" ]

# ------------------------------------------------ the tick takes the label off
# The judge loop never runs again on a reverted branch, so the tick itself must
# remove `regressed` from an open PR whose FAIL is withdrawn -- once -- and must
# not touch the PR whose FAIL still stands.
printf 'lane/full\t401\nlane/part\t402\n' > "$WW/arms/log/prs.tsv"
wtick() {
    ( export HAKUX_WORK="$WW" DISPATCH_DIR="$WW/dispatch" HAKUX_REPO_DIR="$WR" HAKUX_TIP=master \
             ARMS_MAX_PAIRS_PER_TICK=0 SELFTEST_LABELS=regressed
      bash "$TESTING/jobs/arms.sh" ) >/dev/null 2>&1
}
: > "$SELFTEST_GH_LOG"; wtick
check "the tick removes regressed from the withdrawn PR" \
    grep -q 'DELETE repos/example/hakux/issues/401/labels/regressed' "$SELFTEST_GH_LOG"
check "  and says so on it" grep -q '^pr comment 401' "$SELFTEST_GH_LOG"
check "  and leaves the partly reverted PR's label alone" \
    bash -c '! grep -q "issues/402/labels/regressed" "$1"' -- "$SELFTEST_GH_LOG"
check "  and adds verified to neither" bash -c '! grep -q "labels\[\]=verified" "$1"' -- "$SELFTEST_GH_LOG"
check "  and the verdict judged/ marker is untouched" grep -q FAIL "$WW/arms/judged/$(echo 'full wd-full-arm' | sha256sum | cut -c1-64)"
: > "$SELFTEST_GH_LOG"; wtick
check "a second tick does it once, not every tick" \
    bash -c '! grep -q "issues/401" "$1"' -- "$SELFTEST_GH_LOG"

# ------------------------------------------------------------------ mutants
# Each must turn some case red. Run from a copy beside its sourced helpers.
mutant() {   # <label> <python-literal-to-replace> <replacement> <case that must go wrong>
    local md="$WD/mut-$RANDOM"; mkdir -p "$md"
    cp "$TESTING/jobs/gh-label.sh" "$TESTING/jobs/localtime.sh" "$md/"
    python3 - "$TESTING/jobs/arms.sh" "$md/arms.sh" "$2" "$3" <<'PY'
import sys
src, dst, old, new = sys.argv[1:]
s = open(src).read()
assert s.count(old) == 1, "mutant anchor %r matches %d times" % (old, s.count(old))
open(dst, "w").write(s.replace(old, new))
PY
    [ -f "$md/arms.sh" ] || { bad "mutant '$1': its anchor no longer matches arms.sh"; return; }
    local mg; mg=$(cases "$md/arms.sh")
    if [ "$mg" = "$WANT" ]; then bad "mutant '$1' passes every case (the fragment cannot see it)"
    elif [ "$(grep "^$4 " <<< "$mg")" != "$(grep "^$4 " <<< "$WANT")" ]; then ok "mutant '$1' is red on ($4)"
    else bad "mutant '$1' is red, but not on ($4): $(tr '\n' ';' <<< "$mg")"; fi
}
mutant "no docs/ restriction: NOTES keep a FAIL alive" \
    'code = {f for f in code if not f.startswith("docs/")}' 'code = set(code)' full
mutant "any overlap withdraws: a partial revert reads withdrawn" \
    'if not code or have is None or code & have:' 'if not code or have is None or code <= have:' part
mutant "withdrawal ignores the verdict: a PASS is withdrawn too" \
    'if r["cls"] != "FAIL" or not r["a"] or not r["b"]:' 'if not r["a"] or not r["b"]:' pass
rm -rf "$WD"
