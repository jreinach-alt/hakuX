# Sourced by ../selftest.sh with the harness already built: $T, $HERE, $REPO,
# the shims on PATH, ok/bad/check. Not executable, no shebang, no exit --
# `fail` is shared and is the run's verdict.
#
# fold.sh: more than one fold per tick, only of PRs with disjoint files, and
# the attribution of a red trunk after such a tick.
#
# One fold per tick was the backlog's clock: every fold-ready PR queued behind
# the one before it at one per 30-minute tick ("#350 waits: one fold per
# tick"). These drive REAL fold.sh ticks against a scratch origin: two PRs on
# disjoint files fold in one tick, two on the same file fold in two, and when
# master's CI goes red after a multi-fold tick the LAST fold is reverted first
# and then named. Builds everything under $T/foldmulti. Depends on no other
# fragment.

echo "== fold.sh: up to three disjoint folds per tick; a red after one is attributed"
FM="$T/foldmulti"; rm -rf "$FM"; mkdir -p "$FM/bin"

# The gh shim: $FM/labels.<pr> holds a PR's labels, $FM/prs.tsv declares
# "<num>\t<branch>", every PR head's CI is GREEN, and a trunk commit's CI is
# the word in $FM/ci.<sha> (PENDING when there is none; CANCELLED and NONE are
# what TRUNK_CI_JQ says for all-cancelled runs and for no runs).
cat > "$FM/bin/gh" <<'EOF'
#!/usr/bin/env bash
args="$*"; echo "$args" >> "$FM/gh.log"
labels_of() { tr '\n' ',' < "$FM/labels.$1" 2>/dev/null | sed 's/,$//'; }
case "$1 $2" in
    "pr list")
        while IFS=$'\t' read -r n b; do
            [ -n "$n" ] || continue
            h=$(git -C "$FM/origin.git" rev-parse -q --verify "refs/heads/$b") || continue
            if [[ "$args" == *mergeable* ]]; then
                printf '%s\t%s\t%s\tfalse\tMERGEABLE\t%s\n' "$n" "$b" "$h" "$(labels_of "$n")"
            elif [[ "$args" =~ --label\ ([A-Za-z0-9:_-]+) ]] && grep -qxF "${BASH_REMATCH[1]}" "$FM/labels.$n" 2>/dev/null; then
                if [ "${BASH_REMATCH[1]}" = fold-ready ]; then
                    printf '%s\t%s\t%s\tfalse\t%s\t%s\n' "$n" "$b" "$h" "$(labels_of "$n")" "pr $n"
                else
                    printf '%s\t%s\t%s\t%s\n' "$n" "$b" "$h" "$(labels_of "$n")"
                fi
            fi
        done < "$FM/prs.tsv"
        exit 0 ;;
    "pr view") [[ "$args" == *headRefOid* ]] || echo GREEN; exit 0 ;;
    "pr comment") { echo "--- comment on $3"; cat "${args##*--body-file }"; } >> "$FM/comments.log"; exit 0 ;;
    "api "*|"api -X"*)
        if [[ "$args" == *check-runs* ]]; then
            s=$(sed -n 's#.*/commits/\([0-9a-f]*\)/check-runs.*#\1#p' <<< "$args"); cat "$FM/ci.$s" 2>/dev/null || echo PENDING; exit 0
        fi
        n=$(sed -n 's#.*/issues/\([0-9]*\)/labels.*#\1#p' <<< "$args")
        if [[ "$args" == *"-X POST"* ]]; then
            sed -n 's/.*labels\[\]=\([^ ]*\).*/\1/p' <<< "$args" >> "$FM/labels.$n"
        elif [[ "$args" == *"-X DELETE"* ]]; then
            l="${args##*/labels/}"; l="${l%% *}"; grep -vxF "$l" "$FM/labels.$n" > "$FM/labels.tmp"; mv "$FM/labels.tmp" "$FM/labels.$n"
        elif [ -n "$n" ]; then
            cat "$FM/labels.$n" 2>/dev/null
        fi
        exit 0 ;;
esac
exit 0
EOF
printf '#!/usr/bin/env bash\ncase "$*" in *is-active*) exit 3 ;; esac; exit 0\n' > "$FM/bin/systemctl"
chmod +x "$FM/bin/"*

R="$FM/host"
git -c init.defaultBranch=master init -q --bare "$FM/origin.git"
git -c init.defaultBranch=master init -q "$R"
git -C "$R" config user.name s; git -C "$R" config user.email s@t
git -C "$R" remote add origin "$FM/origin.git"
mkdir -p "$R/docs/testing"
printf '#!/usr/bin/env bash\nexit 0\n' > "$R/docs/testing/preflight.sh"
# a.c has ten lines so two lanes can edit it without a textual conflict:
# the same-file rule must hold them apart on its own, not lean on the merge.
seq 1 10 > "$R/a.c"; echo b > "$R/b.c"; git -C "$R" add -A; git -C "$R" commit -q -m base
fm_lane() {   # <branch> <file> <line> <text>
    git -C "$R" checkout -q -b "$1" master; sed -i "$3s/.*/$4/" "$R/$2"; git -C "$R" commit -qam "$1"
}
fm_lane lane/fma a.c 1 "from fma"     # a.c, line 1
fm_lane lane/fmb b.c 1 "from fmb"     # b.c: disjoint from fma
fm_lane lane/fmc a.c 10 "from fmc"    # a.c again, line 10: shares a file with fma, merges cleanly
for x in d e f g; do   # a new file each: disjoint from everything
    git -C "$R" checkout -q -b "lane/fm$x" master; echo $x > "$R/$x.c"; git -C "$R" add $x.c; git -C "$R" commit -qm "lane/fm$x"
done
git -C "$R" checkout -q master
FM_M0=$(git -C "$R" rev-parse master)
declare -A FM_H
for x in a b c d e f g; do FM_H[lane/fm$x]=$(git -C "$R" rev-parse "lane/fm$x"); done

fm_reset() {   # <"num branch" ...> : a fresh origin, host work dir and label set
    rm -rf "$FM/tw" "$FM/labels."* "$FM/ci."*; git -C "$R" worktree prune
    : > "$FM/comments.log"; : > "$FM/gh.log"; : > "$FM/prs.tsv"
    git -C "$R" push -q -f origin "$FM_M0:refs/heads/master"
    local p n b
    for p in "$@"; do
        read -r n b <<< "$p"
        git -C "$R" push -q -f origin "${FM_H[$b]}:refs/heads/$b"
        printf '%s\t%s\n' "$n" "$b" >> "$FM/prs.tsv"; echo fold-ready > "$FM/labels.$n"
    done
}
fm_tick() {
    env FM="$FM" PATH="$FM/bin:$PATH" TESTS="$FM/none" SUPPORT="$FM/none" \
        HAKUX_WORK="$FM/tw" HAKUX_REPO_DIR="$R" bash "${FM_FOLD:-$HERE/fold.sh}" >> "$FM/out.log" 2>&1
}
fm_add() {   # <num> <branch>: one more fold-ready PR on the current origin
    git -C "$R" push -q -f origin "${FM_H[$2]}:refs/heads/$2"; printf '%s\t%s\n' "$1" "$2" >> "$FM/prs.tsv"; echo fold-ready > "$FM/labels.$1"
}
fm_master() { git -C "$FM/origin.git" rev-parse master; }
fm_folds() { git -C "$FM/origin.git" log --first-parent --format=%s master | grep -c '^fold: PR #'; }
fm_tiplog() { tail -n "${2:-3}" "$FM/tw/logs/fold/tick.log" | grep -q "$1"; }

# (1) disjoint: one tick folds both
fm_reset "41 lane/fma" "42 lane/fmb"
fm_tick
check "(1) two PRs on disjoint files fold in ONE tick" [ "$(fm_folds)" = 2 ]
check "  both labelled folded" bash -c 'grep -qx folded "$1" && grep -qx folded "$2"' _ "$FM/labels.41" "$FM/labels.42"
check "  the tick's summary names both" grep -q "tick: repaired none; folded #41 #42; handed back none; waiting none" "$FM/tw/logs/fold/tick.log"
FM_TIP=$(git -C "$FM/origin.git" rev-parse master)
check "  and the tick is recorded for attribution under the trunk head it left" \
    bash -c 'grep -q "^fold 42 lane/fmb " "$1"' _ "$FM/tw/fold/multi/$FM_TIP"

# (1b) FOLD_MAX_PER_TICK caps it
fm_reset "41 lane/fma" "42 lane/fmb"
FOLD_MAX_PER_TICK=1 fm_tick
check "(1b) with FOLD_MAX_PER_TICK=1 the same two fold one at a time" [ "$(fm_folds)" = 1 ]

# (2) same file: two ticks
fm_reset "41 lane/fma" "43 lane/fmc"
fm_tick
check "(2) two PRs on the same file: the first tick folds ONE" [ "$(fm_folds)" = 1 ]
check "  and says the other waits on the shared file" grep -q "#43 waits: it shares a.c with a PR folded this tick" "$FM/tw/logs/fold/tick.log"
check "  no multi-fold record for a one-fold tick" bash -c '[ -z "$(ls -A "$1")" ]' _ "$FM/tw/fold/multi"
fm_tick
check "  the second tick folds the other" [ "$(fm_folds)" = 2 ]
check "  #43 is folded" grep -qx folded "$FM/labels.43"

# (3) attribution: master goes red after the two-fold tick
fm_reset "41 lane/fma" "42 lane/fmb"
fm_tick
FM_TIP=$(git -C "$FM/origin.git" rev-parse master)
echo RED > "$FM/ci.$FM_TIP"; echo GREEN > "$FM/ci.$FM_M0"
fm_tick
FM_REV=$(git -C "$FM/origin.git" rev-parse master)
check "(3) red after a two-fold tick: master moved by one revert" [ "$(git -C "$FM/origin.git" rev-parse "$FM_REV^")" = "$FM_TIP" ]
check "  of the LAST fold (#42): b.c is back to base, a.c keeps #41" \
    bash -c '[ "$(git -C "$1" show "$2:b.c")" = b ] && git -C "$1" show "$2:a.c" | grep -q "from fma"' _ "$FM/origin.git" "$FM_REV"
check "  #42 told it was reverted to attribute" grep -q "^\[job.fold\] Reverted from \`master\`" "$FM/comments.log"
fm_add 44 lane/fmd
fm_tick
check "  while the revert's CI is pending nothing folds, not even a disjoint #44" [ "$(git -C "$FM/origin.git" rev-parse master)" = "$FM_REV" ]
check "  and the log says why #44 waits" grep -q "#44 waits: master's CI after a multi-fold tick is being attributed" "$FM/tw/logs/fold/tick.log"
echo GREEN > "$FM/ci.$FM_REV"
fm_tick
check "  revert GREEN: #42 named, red together with #41" grep -q "this PR is red together with #41" "$FM/comments.log"
check "  with the re-land steps, since the PR is closed as merged" grep -q "git revert ${FM_REV:0:10}" "$FM/comments.log"
check "  and the tick.log names it" grep -q "ATTRIBUTED #42, red together with #41" "$FM/tw/logs/fold/tick.log"
check "  the record is closed" grep -qx "done culprit 42" "$FM/tw/fold/multi/$FM_TIP"
check "  and in that same tick folding resumes: #44 folded" grep -qx folded "$FM/labels.44"

# (3b) master already red before the tick: not attributed to it
fm_reset "41 lane/fma" "42 lane/fmb"
fm_tick
FM_TIP=$(git -C "$FM/origin.git" rev-parse master)
echo RED > "$FM/ci.$FM_TIP"; echo RED > "$FM/ci.$FM_M0"
fm_tick
check "(3b) red before the tick too: nothing reverted" [ "$(git -C "$FM/origin.git" rev-parse master)" = "$FM_TIP" ]
check "  and the log says why" grep -q "it was already red at ${FM_M0:0:10} before that tick" "$FM/tw/logs/fold/tick.log"

# (5) the tip's runs were all CANCELLED by a later push: a descendant answers
fm_reset "41 lane/fma" "42 lane/fmb"
fm_tick
FM_TIP=$(fm_master); echo CANCELLED > "$FM/ci.$FM_TIP"
fm_add 44 lane/fmd
fm_tick
FM_D1=$(fm_master)
check "(5) cancelled, no descendant yet: one fold (#44)" [ "$(fm_folds)" = 3 ]
check "  and the log says the runs were cancelled and nothing answers yet" \
    grep -q "master CI CANCELLED on ${FM_TIP:0:10} after folding #41 #42 in one tick (its own runs: all cancelled; none of its first-parent descendants has reported, 0 read); at most one fold" "$FM/tw/logs/fold/tick.log"
fm_add 45 lane/fme; fm_add 46 lane/fmf
fm_tick
FM_D2=$(fm_master)
check "(5c) its descendant still pending: still at most one fold per tick" [ "$(fm_folds)" = 4 ]
check "  #45 folded, #46 waits" bash -c 'grep -qx folded "$1" && ! grep -qx folded "$2"' _ "$FM/labels.45" "$FM/labels.46"
check "  the log says one descendant was read" grep -q "none of its first-parent descendants has reported, 1 read); at most one fold" "$FM/tw/logs/fold/tick.log"
check "  the record stays open" bash -c '! grep -q "^done" "$1"' _ "$FM/tw/fold/multi/$FM_TIP"
echo CANCELLED > "$FM/ci.$FM_D1"; echo GREEN > "$FM/ci.$FM_D2"
fm_add 47 lane/fmg
fm_tick
check "(5g) a GREEN descendant past a cancelled one: done superseded-green, naming it" grep -qx "done superseded-green $FM_D2" "$FM/tw/fold/multi/$FM_TIP"
check "  the log names the descendant" grep -q "master CI GREEN on ${FM_D2:0:10} after folding #41 #42 in one tick at ${FM_TIP:0:10} (its own runs: all cancelled; ${FM_D2:0:10}, its nearest descendant to report, answers for it)" "$FM/tw/logs/fold/tick.log"
check "  and that same tick folds more than one: #46 and #47" grep -q "tick: repaired none; folded #46 #47;" "$FM/tw/logs/fold/tick.log"

# (6) the same with no runs at all on the tip, and a RED descendant
fm_reset "41 lane/fma" "42 lane/fmb"
fm_tick
FM_TIP=$(fm_master); echo NONE > "$FM/ci.$FM_TIP"; echo GREEN > "$FM/ci.$FM_M0"
fm_add 44 lane/fmd
fm_tick
FM_D1=$(fm_master); echo RED > "$FM/ci.$FM_D1"
fm_tick
FM_REV=$(fm_master)
check "(6) no runs on the tip, a RED descendant: master moved by one revert on top of it" [ "$(git -C "$FM/origin.git" rev-parse "$FM_REV^")" = "$FM_D1" ]
check "  of the batch's LAST fold (#42): b.c is back to base, #44's d.c stays" \
    bash -c '[ "$(git -C "$1" show "$2:b.c")" = b ] && git -C "$1" show "$2:d.c" | grep -qx d' _ "$FM/origin.git" "$FM_REV"
check "  the log names the red descendant and the tip it answers for" \
    grep -q "master CI RED on ${FM_D1:0:10} after folding #41 #42 in one tick at ${FM_TIP:0:10} (its own runs: none; ${FM_D1:0:10}, its nearest descendant to report, answers for it); reverting the last, #42" "$FM/tw/logs/fold/tick.log"
check "  #42's comment names the red descendant" grep -q "went red on .${FM_D1:0:10}., the nearest descendant with a verdict of .${FM_TIP:0:10}., the tip after" "$FM/comments.log"
# (6r) the revert's own runs are cancelled by an unrelated push to master
echo CANCELLED > "$FM/ci.$FM_REV"
git -C "$R" fetch -q origin master; git -C "$R" checkout -q --detach origin/master
echo z > "$R/z.c"; git -C "$R" add z.c; git -C "$R" commit -qm "audit: an unrelated push"; git -C "$R" push -q origin HEAD:master
git -C "$R" checkout -q master
FM_D3=$(fm_master)
fm_tick
check "(6r) revert cancelled, its descendant pending: nothing folds" [ "$(fm_master)" = "$FM_D3" ]
check "  and the log says so" grep -q "on the revert ${FM_REV:0:10} of #42 (its own runs: all cancelled; none of its first-parent descendants has reported, 1 read); nothing folds" "$FM/tw/logs/fold/tick.log"
echo GREEN > "$FM/ci.$FM_D3"
fm_tick
check "  its descendant GREEN: #42 named, red together with #41" grep -qx "done culprit 42" "$FM/tw/fold/multi/$FM_TIP"
check "  the log says the descendant answered for the revert" grep -q "master CI GREEN on the revert ${FM_REV:0:10} (its own runs: all cancelled; ${FM_D3:0:10}, its nearest descendant to report, answers for it): ATTRIBUTED #42" "$FM/tw/logs/fold/tick.log"
check "  and the attribution names the red commit, not the silent tip" grep -q "went red on .${FM_D1:0:10}., and reverting this PR" "$FM/comments.log"

# (4) the classifier, through the real jq
fm_jq() { printf '%s' "$1" | jq -r "$(sed -n "/^TRUNK_CI_JQ='/,/end'\$/p" "$HERE/fold.sh" | sed "1s/^TRUNK_CI_JQ='//; \$s/'\$//")"; }
check "(4) trunk CI: a failure is RED while another run is still going" \
    [ "$(fm_jq '{"check_runs":[{"status":"completed","conclusion":"failure"},{"status":"in_progress","conclusion":null}]}')" = RED ]
check "  a cancelled run is not a verdict" \
    [ "$(fm_jq '{"check_runs":[{"status":"completed","conclusion":"cancelled"},{"status":"completed","conclusion":"success"}]}')" = GREEN ]
check "  every run cancelled is CANCELLED, not NONE" \
    [ "$(fm_jq '{"check_runs":[{"status":"completed","conclusion":"cancelled"},{"status":"completed","conclusion":"cancelled"}]}')" = CANCELLED ]
check "  nothing at all is NONE" [ "$(fm_jq '{"check_runs":[]}')" = NONE ]

# --------------------------------------------------------------- mutant
rm -rf "$FM/mut"; cp -r "$HERE" "$FM/mut"
sed -i 's/it shares \$f with a PR folded this tick"; break/"; :/' "$FM/mut/fold.sh"
check "mutant: without the shared-file test the sed applied" bash -c '! cmp -s "$1" "$2"' _ "$FM/mut/fold.sh" "$HERE/fold.sh"
fm_reset "41 lane/fma" "43 lane/fmc"
FM_FOLD="$FM/mut/fold.sh" fm_tick
check "  mutant: same-file PRs are NOT held apart (so (2) tests the guard)" [ "$(fm_folds)" != 1 ]

# without the descendant walk, (5g)'s record never closes
rm -rf "$FM/mut"; cp -r "$HERE" "$FM/mut"
sed -i 's/^descendant_ci() {   #.*/&\n    return 1/' "$FM/mut/fold.sh"
check "mutant: without descendant_ci the sed applied" bash -c '! cmp -s "$1" "$2"' _ "$FM/mut/fold.sh" "$HERE/fold.sh"
fm_reset "41 lane/fma" "42 lane/fmb"
FM_FOLD="$FM/mut/fold.sh" fm_tick
FM_TIP=$(fm_master); echo CANCELLED > "$FM/ci.$FM_TIP"
fm_add 44 lane/fmd
FM_FOLD="$FM/mut/fold.sh" fm_tick
echo GREEN > "$FM/ci.$(fm_master)"
FM_FOLD="$FM/mut/fold.sh" fm_tick
check "  mutant: a cancelled tip with a GREEN descendant stays open (so (5g) tests the walk)" bash -c '! grep -q "^done" "$1"' _ "$FM/tw/fold/multi/$FM_TIP"
