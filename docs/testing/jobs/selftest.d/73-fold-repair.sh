# Sourced by ../selftest.sh with the harness already built: $T, $HERE, $REPO,
# the shims on PATH, ok/bad/check. Not executable, no shebang, no exit --
# `fail` is shared and is the run's verdict.
#
# fold.sh: a conflicting PR is a conflict, not a CI wait.
#
# GitHub runs no CI on a PR that does not merge, so fold.sh read every
# conflicting PR as `CI NONE` and waited forever. On 2026-09-26 four PRs
# holding the hot pgraph files conflicted in the generated index alone and
# froze every issue that needed those files until the host repaired them by
# hand. These drive REAL fold.sh ticks against a scratch origin with shims of
# their own, and check the two answers: an index-only conflict is repaired ON
# THE LANE BRANCH and pushed; any other conflict is handed back THE SAME tick,
# which means handback.sh -- the tail of that tick -- resumes the lane.
#
# Builds everything under $T/foldrepair and gives every tick its own
# HAKUX_WORK. Depends on no other fragment.

echo "== fold.sh: a conflicting PR is repaired (index only) or handed back (anything else), in the tick"
FR="$T/foldrepair"; rm -rf "$FR"; mkdir -p "$FR/bin"
IX=docs/testing/nv2a_index.json

fr_three() {   # <dir> -> three commits; prints their shas oldest first
    git -c init.defaultBranch=master init -q "$1"
    git -C "$1" config user.email s@t; git -C "$1" config user.name s
    local i; for i in 1 2 3; do echo "$i" > "$1/tree.txt"; git -C "$1" add -A; git -C "$1" commit -q -m "c$i"; git -C "$1" rev-parse HEAD; done
}
read -r FR_TC1 FR_TC2 FR_TC3 <<< "$(fr_three "$FR/tests" | tr '\n' ' ')"
read -r FR_PB1 FR_PB2 FR_PB3 <<< "$(fr_three "$FR/support" | tr '\n' ' ')"

# nv2a_index.py stand-in: `check` passes only a rebuilt index; `build` marks it.
cat > "$FR/stub.py" <<'EOF'
import json, os, sys
P = os.path.join(os.path.dirname(os.path.abspath(__file__)), "nv2a_index.json")
d = json.load(open(P))
if sys.argv[1] == "check":
    sys.exit(0 if d["provenance"].get("rebuilt") else 1)
d["provenance"]["rebuilt"] = True
json.dump(d, open(P, "w"), indent=1)
EOF
fr_index() {   # <who> <tests_commit>
    printf '{"provenance": {"who": "%s", "tests_commit": "%s"},\n "suites": {"s0": 1, "s1": 1, "s2": 1}}\n' "$1" "$2"
}

# The gh shim. State lives in files so a label set by one call is seen by the
# next: $FR/labels.<pr> holds a PR's labels, one per line, and the pipeline
# listing is built from them. PRs are declared in $FR/prs.tsv as
# "<num>\t<branch>\t<mergeable>".
cat > "$FR/bin/gh" <<'EOF'
#!/usr/bin/env bash
args="$*"; echo "$args" >> "${FR_GH_LOG:?}"
labels_of() { tr '\n' ',' < "$FR/labels.$1" 2>/dev/null | sed 's/,$//'; }
head_of() { git -C "$FR/origin.git" rev-parse "refs/heads/$1" 2>/dev/null; }
case "$1 $2" in
    "pr list")
        while IFS=$'\t' read -r n b mg; do
            [ -n "$n" ] || continue
            h=$(head_of "$b"); [ -n "$h" ] || continue; l=$(labels_of "$n")
            if [[ "$args" == *mergeable* ]]; then
                printf '%s\t%s\t%s\tfalse\t%s\t%s\n' "$n" "$b" "$h" "$mg" "$l"
            elif [[ "$args" =~ --label\ ([A-Za-z0-9:_-]+) ]]; then
                grep -qxF "${BASH_REMATCH[1]}" "$FR/labels.$n" 2>/dev/null || continue
                if [ "${BASH_REMATCH[1]}" = fold-ready ]; then
                    printf '%s\t%s\t%s\tfalse\t%s\t%s\n' "$n" "$b" "$h" "$l" "a title"
                else
                    printf '%s\t%s\t%s\t%s\n' "$n" "$b" "$h" "$l"
                fi
            fi
        done < "$FR/prs.tsv"
        exit 0 ;;
    "pr view")
        [[ "$args" == *"--json mergeable "* ]] && { awk -F'\t' -v n="$3" '$1==n{print $3}' "$FR/prs.tsv"; exit 0; }
        [[ "$args" == *headRefOid* ]] && exit 0
        echo "${FR_CI:-NONE}"; exit 0 ;;
    "pr comment")
        { echo "--- comment on $3"; cat "${args##*--body-file }"; } >> "$FR/comments.log"; exit 0 ;;
    "api "*|"api -X"*)
        n=$(sed -n 's#.*/issues/\([0-9]*\)/labels.*#\1#p' <<< "$args")
        if [[ "$args" == *"-X POST"* ]]; then
            l=$(sed -n 's/.*labels\[\]=\([^ ]*\).*/\1/p' <<< "$args"); echo "$l" >> "$FR/labels.$n"
        elif [[ "$args" == *"-X DELETE"* ]]; then
            l="${args##*/labels/}"; l="${l%% *}"; grep -vxF "$l" "$FR/labels.$n" > "$FR/labels.tmp"; mv "$FR/labels.tmp" "$FR/labels.$n"
        elif [ -n "$n" ]; then
            cat "$FR/labels.$n" 2>/dev/null
        fi
        exit 0 ;;
esac
exit 0
EOF
cat > "$FR/bin/systemctl" <<'EOF'
#!/usr/bin/env bash
case "$*" in
    *is-active*) grep -qxF -- "${!#}" "$FR/active" 2>/dev/null ;;
    *) exit 0 ;;
esac
EOF
cat > "$FR/lane.sh" <<'EOF'
#!/usr/bin/env bash
echo "lane.sh $*" >> "$FR/lanesh.log"; echo "resumed $2"; exit 0
EOF
chmod +x "$FR/bin/"* "$FR/lane.sh"

# The scratch origin and the host checkout it is cloned into.
R="$FR/host"
git -c init.defaultBranch=master init -q --bare "$FR/origin.git"
git -c init.defaultBranch=master init -q "$R"
git -C "$R" config user.name s; git -C "$R" config user.email s@t
git -C "$R" remote add origin "$FR/origin.git"
mkdir -p "$R/docs/testing" "$R/.github/workflows"
cp "$FR/stub.py" "$R/docs/testing/nv2a_index.py"
printf '#!/usr/bin/env bash\nexit 0\n' > "$R/docs/testing/preflight.sh"
printf 'jobs:\n  check:\n    steps:\n      - env:\n          PBKIT_SHA: %s\n' "$FR_PB2" > "$R/.github/workflows/nv2a-index.yml"
fr_index base "$FR_TC2" > "$R/$IX"; echo base > "$R/src.c"
git -C "$R" add -A; git -C "$R" commit -q -m base
# lane/fxidx: the index and its own code. lane/fxcode: the index AND src.c.
git -C "$R" checkout -q -b lane/fxidx; fr_index idx "$FR_TC2" > "$R/$IX"; echo idx > "$R/idx.c"; git -C "$R" add -A; git -C "$R" commit -q -m idx
git -C "$R" checkout -q -b lane/fxcode master; fr_index code "$FR_TC2" > "$R/$IX"; echo code > "$R/src.c"; git -C "$R" commit -qam code
git -C "$R" checkout -q master; fr_index master "$FR_TC2" > "$R/$IX"; echo master > "$R/src.c"; git -C "$R" commit -qam master
git -C "$R" push -q origin master lane/fxidx lane/fxcode
FR_M0=$(git -C "$R" rev-parse master); FR_IDX=$(git -C "$R" rev-parse lane/fxidx); FR_CODE=$(git -C "$R" rev-parse lane/fxcode)

fr_tick() {   # [env assignments...] : one tick of the REAL fold.sh, on a fresh HAKUX_WORK
    rm -rf "$FR/tw" "$FR/labels."*; git -C "$R" worktree prune
    : > "$FR/comments.log"; : > "$FR/gh.log"; : > "$FR/active"; : > "$FR/lanesh.log"
    git -C "$R" push -q -f origin "$FR_M0:refs/heads/master" "$FR_IDX:refs/heads/lane/fxidx" "$FR_CODE:refs/heads/lane/fxcode"
    mkdir -p "$FR/tw/wt/fxcode" "$FR/tw/wt/fxidx" "$FR/tw/attempts"
    echo brief > "$FR/tw/briefs.md"; mkdir -p "$FR/tw/briefs"; echo brief > "$FR/tw/briefs/fxcode.md"; echo brief > "$FR/tw/briefs/fxidx.md"
    printf '31\tlane/fxidx\tCONFLICTING\n32\tlane/fxcode\tUNKNOWN\n' > "$FR/prs.tsv"
    echo fold-ready > "$FR/labels.31"; echo needs-audit-2 > "$FR/labels.32"
    local a; for a in "$@"; do case "$a" in PRE:*) eval "${a#PRE:}" ;; esac; done
    env $(printf '%s\n' "$@" | grep -v '^PRE:') FR="$FR" FR_GH_LOG="$FR/gh.log" \
        TESTS="$FR/tests" SUPPORT="$FR/support" PATH="$FR/bin:$PATH" HAKUX_LANE_SH="$FR/lane.sh" \
        HAKUX_WORK="$FR/tw" HAKUX_REPO_DIR="$R" bash "${FR_FOLD:-$HERE/fold.sh}" > "$FR/out.log" 2>&1
}
fr_head() { git -C "$FR/origin.git" rev-parse "refs/heads/$1"; }

fr_tick
FR_NEW=$(fr_head lane/fxidx)
check "(1) index-only conflict: lane/fxidx moved on origin" [ "$FR_NEW" != "$FR_IDX" ]
check "  as a fast-forward: the lane's head is an ancestor (merge, not rebase)" \
    git -C "$FR/origin.git" merge-base --is-ancestor "$FR_IDX" "$FR_NEW"
check "  and master is in it" git -C "$FR/origin.git" merge-base --is-ancestor "$FR_M0" "$FR_NEW"
check "  the top commit regenerated the index" \
    bash -c '[ "$(git -C "$1" log -1 --format=%s "$2")" = "nv2a index: regenerate after merging master into lane/fxidx (#31)" ]' _ "$FR/origin.git" "$FR_NEW"
check "  over the pinned trees (the rebuilt marker is in the pushed index)" \
    bash -c 'git -C "$1" show "$2:docs/testing/nv2a_index.json" | grep -q "\"rebuilt\": true"' _ "$FR/origin.git" "$FR_NEW"
check "  the merge under it took master's index (not hand-merged)" \
    bash -c 'git -C "$1" show "$2~1:docs/testing/nv2a_index.json" | grep -q "\"who\": \"master\""' _ "$FR/origin.git" "$FR_NEW"
check "  and kept the lane's own code" \
    bash -c '[ "$(git -C "$1" show "$2:idx.c")" = idx ]' _ "$FR/origin.git" "$FR_NEW"
check "  master itself was not touched" [ "$(fr_head master)" = "$FR_M0" ]
check "  one line on the PR saying so" grep -q "^\[job.fold\] Repaired: \`lane/fxidx\` conflicted with \`master\` only in" "$FR/comments.log"
check "  its labels were kept (still fold-ready, no needs-rebase)" bash -c '[ "$(cat "$1")" = fold-ready ]' _ "$FR/labels.31"

check "(2) code conflict: #32 labelled needs-rebase" grep -qx needs-rebase "$FR/labels.32"
check "  its audit label kept" grep -qx needs-audit-2 "$FR/labels.32"
check "  the cause names both files" grep -qx "files=$IX src.c " "$FR/tw/handback/cause/32-$FR_CODE"
check "  lane/fxcode was not touched" [ "$(fr_head lane/fxcode)" = "$FR_CODE" ]
check "  THE SAME tick: handback.sh resumed lane fxcode" grep -qx "lane.sh resume fxcode" "$FR/lanesh.log"
check "  and nothing else" [ "$(wc -l < "$FR/lanesh.log")" = 1 ]
check "  the hand-back comment names the files" grep -q "conflicts in: \`$IX src.c \`" "$FR/comments.log"
check "(3) tick.log names both outcomes in one summary line" \
    grep -q "tick: repaired #31; folded none; handed back #32; waiting" "$FR/tw/logs/fold/tick.log"
check "  and no CI NONE wait was logged for either" bash -c '! grep -q "CI is NONE" "$1"' _ "$FR/tw/logs/fold/tick.log"

# (4) the refusals: a running lane, and a lane at its last attempt
fr_tick 'PRE:echo hakux-lane-fxidx > "$FR/active"; echo 4 > "$FR/tw/attempts/fxcode"'
check "(4) lane unit running: lane/fxidx is not pushed" [ "$(fr_head lane/fxidx)" = "$FR_IDX" ]
check "  and the log says it waits for the lane" grep -q "not repaired this tick: lane.fxidx's unit is running" "$FR/tw/logs/fold/tick.log"
check "  attempt 4 of 4: no needs-rebase, no resume" \
    bash -c '! grep -qx needs-rebase "$1" && [ ! -s "$2" ]' _ "$FR/labels.32" "$FR/lanesh.log"
check "  a decision-needed comment instead" grep -q "^\[job.fold\] decision-needed: merging \`lane/fxcode\`" "$FR/comments.log"

# (5) the sides name different tests_commits: refused and handed back, not pushed
git -C "$R" checkout -q lane/fxidx; fr_index idx "$FR_TC1" > "$R/$IX"; git -C "$R" commit -qam "idx at another tests commit"
FR_IDX_SAVED=$FR_IDX; FR_IDX=$(git -C "$R" rev-parse HEAD); git -C "$R" checkout -q master
fr_tick
check "(5) different tests_commits: lane/fxidx not pushed" [ "$(fr_head lane/fxidx)" = "$FR_IDX" ]
check "  handed back instead, with the reason" grep -q "which one is a decision" "$FR/comments.log"
check "  and labelled needs-rebase" grep -qx needs-rebase "$FR/labels.31"
FR_IDX=$FR_IDX_SAVED

# --------------------------------------------------------------- mutants
fr_mutant() {   # <name> <sed expr> -> a mutated copy of the jobs dir; prints its fold.sh
    rm -rf "$FR/mut-$1"; cp -r "$HERE" "$FR/mut-$1"; sed -i "$2" "$FR/mut-$1/fold.sh"; echo "$FR/mut-$1/fold.sh"
}
m=$(fr_mutant nopass 's/^conflict_pass$/: conflict_pass/')
check "mutant: without the conflict pass the sed applied" bash -c '! cmp -s "$1" "$2"' _ "$m" "$HERE/fold.sh"
FR_FOLD="$m" fr_tick
check "  mutant nopass: lane/fxidx is NOT repaired (the check above is not vacuous)" [ "$(fr_head lane/fxidx)" = "$FR_IDX" ]
m=$(fr_mutant nounit 's/unit_active "\$name" &&/false \&\&/g')
check "mutant: without the unit check the sed applied" bash -c '! cmp -s "$1" "$2"' _ "$m" "$HERE/fold.sh"
FR_FOLD="$m" fr_tick 'PRE:echo hakux-lane-fxidx > "$FR/active"'
check "  mutant nounit: a running lane's branch IS pushed (so (4) tests the guard)" [ "$(fr_head lane/fxidx)" != "$FR_IDX" ]
