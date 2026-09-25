# Sourced by ../selftest.sh with the harness already built: $T, $HERE, $REPO,
# the shims on PATH, ok/bad/check, and the live prediction's fixtures. Not
# executable, no shebang, no exit -- `fail` is shared and is the run's verdict.
#
# fold.sh: the generated nv2a index is the second conflict it may resolve.
#
# Builds its own git fixtures under $T/foldindex, and gives every fold.sh call
# its own HAKUX_WORK there. No shared state.

echo "== fold.sh: an index-only conflict is regenerated over the pinned trees"
# Every hw PR regenerates docs/testing/nv2a_index.json, so every fold of one
# left the other open hw PRs conflicting in that file alone, and each went
# back to a lane session for a mechanical resolution (#234, #235, #237 on
# 2026-09-25). fold.sh now stages master's copy and rebuilds it -- but only
# when the index is the WHOLE conflict, only when both sides name the same
# tests_commit, and only over the trees CI checks against: nxdk_pgraph_tests
# at the index's tests_commit and pbkitplusplus at the workflow's PBKIT_SHA,
# never whatever the host's checkouts happen to hold.
FI="$T/foldindex"; rm -rf "$FI"; mkdir -p "$FI"
IX=docs/testing/nv2a_index.json

# The host's "live" checkouts. Three commits each, and the pinned one is the
# MIDDLE: a first-wins mutant lands on the oldest, a last-wins or live-tree
# one on HEAD, and only the pin passes.
three() {   # <dir> -> three commits; prints their shas oldest first
    git -c init.defaultBranch=master init -q "$1"
    git -C "$1" config user.email s@t; git -C "$1" config user.name s
    local i; for i in 1 2 3; do echo "$i" > "$1/tree.txt"; git -C "$1" add -A; git -C "$1" commit -q -m "c$i"; git -C "$1" rev-parse HEAD; done
}
read -r TC1 TC2 TC3 <<< "$(three "$FI/tests" | tr '\n' ' ')"
read -r PB1 PB2 PB3 <<< "$(three "$FI/support" | tr '\n' ' ')"
ABSENT=0123456789abcdef0123456789abcdef01234567

# nv2a_index.py stand-in: records the exact tree each call ran over, `check`
# passes only a rebuilt index, `build` writes $FI_SUITES suites.
cat > "$FI/stub.py" <<'EOF'
import json, os, subprocess, sys
cmd, a = sys.argv[1], dict(zip(sys.argv[2::2], sys.argv[3::2]))
head = lambda p: subprocess.run(["git", "-C", p, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
with open(os.environ["FI_CALLS"], "a") as f:
    f.write("%s tests=%s@%s support=%s@%s\n" % (cmd, a["--tests"], head(a["--tests"]), a["--support"], head(a["--support"])))
P = os.path.join(os.path.dirname(os.path.abspath(__file__)), "nv2a_index.json")
d = json.load(open(P))
if cmd == "check":
    sys.exit(0 if d["provenance"].get("rebuilt") else 1)
d["provenance"]["rebuilt"] = True
d["suites"] = {"s%d" % i: 1 for i in range(int(os.environ.get("FI_SUITES", "3")))}
json.dump(d, open(P, "w"), indent=1)
EOF
index() {   # <who> <tests_commit> -> an index whose one-line provenance both sides rewrite
    printf '{"provenance": {"who": "%s", "tests_commit": "%s"},\n "suites": {"s0": 1, "s1": 1, "s2": 1}}\n' "$1" "$2"
}
fixture() {   # <dir> <master tests_commit> <lane tests_commit> [pbkit sha] [source file both sides change]
    local d="$1" also="${5:-}"; rm -rf "$d"; mkdir -p "$d/docs/testing" "$d/.github/workflows"
    git -c init.defaultBranch=master init -q "$d"
    git -C "$d" config user.email s@t; git -C "$d" config user.name s
    cp "$FI/stub.py" "$d/docs/testing/nv2a_index.py"
    printf 'jobs:\n  check:\n    steps:\n      - env:\n          PBKIT_SHA: %s\n' "${4:-$PB2}" > "$d/.github/workflows/nv2a-index.yml"
    index base "$TC2" > "$d/$IX"; echo base > "$d/src.c"
    git -C "$d" add -A; git -C "$d" commit -q -m base
    git -C "$d" checkout -q -b lane/fixture
    index lane "$3" > "$d/$IX"; [ -n "$also" ] && echo "lane code" > "$d/$also"
    git -C "$d" add -A; git -C "$d" commit -q -m lane
    git -C "$d" checkout -q master
    index master "$2" > "$d/$IX"; [ -n "$also" ] && echo "master code" > "$d/$also"
    git -C "$d" add -A; git -C "$d" commit -q -m master
    git -C "$d" merge --no-ff --no-edit -m "fold: PR #1 lane/fixture -- t" lane/fixture >/dev/null 2>&1
}
unmerged() { git -C "$1" diff --name-only --diff-filter=U | tr '\n' ' '; }
state() { git -C "$1" ls-files -s; git -C "$1" status --porcelain; cat "$1/$IX"; }   # everything a refusal must not change
fi_fold() {   # <fold.sh> <mode> <args...> : the fold, on this fragment's own host
    local f=$1; shift
    TESTS="${FI_TESTS-$FI/tests}" SUPPORT="$FI/support" HAKUX_WORK="$FI/work" HAKUX_REPO_DIR="$FI/nohost" \
        FI_CALLS="$FI/calls" bash "$f" "$@"
}

# One function per claim, each taking the fold.sh under test, so the mutants
# below are judged by exactly the code the real script is.
case_a() {   # an index-only conflict resolves, and what is staged is master's copy
    local d="$FI/a" rc
    fixture "$d" "$TC2" "$TC2"
    [ "$(unmerged "$d")" = "$IX " ] || { echo "fixture did not conflict in the index alone"; return 1; }
    fi_fold "$1" resolve-index "$d" >"$FI/a.log" 2>&1; rc=$?
    [ "$rc" = 0 ] && [ -z "$(unmerged "$d")" ] \
        && [ "$(git -C "$d" show ":$IX")" = "$(git -C "$d" show "HEAD:$IX")" ] \
        && [ -z "$(git -C "$d" diff --name-only)" ]
}
refused() {   # <fold.sh> <dir> <log> <expected unmerged> : refused, and nothing touched
    local before rc; before=$(state "$2")
    fi_fold "$1" resolve-index "$2" >"$3" 2>&1; rc=$?
    [ "$rc" != 0 ] && [ "$(unmerged "$2")" = "$4" ] && [ "$(state "$2")" = "$before" ]
}
case_b() { fixture "$FI/b" "$TC2" "$TC2" "$PB2" src.c; refused "$1" "$FI/b" "$FI/b.log" "$IX src.c "; }
case_c() {   # the pinned tests commit is not on this host; nor is the pinned pbkit one; nor any tests checkout
    fixture "$FI/c1" "$ABSENT" "$ABSENT";        refused "$1" "$FI/c1" "$FI/c1.log" "$IX " || return 1
    fixture "$FI/c2" "$TC2" "$TC2" "$ABSENT";    refused "$1" "$FI/c2" "$FI/c2.log" "$IX " || return 1
    fixture "$FI/c3" "$TC2" "$TC2"; FI_TESTS="$FI/nowhere" refused "$1" "$FI/c3" "$FI/c3.log" "$IX "
}
case_d() { fixture "$FI/d" "$TC2" "$TC1"; refused "$1" "$FI/d" "$FI/d.log" "$IX "; }
case_regen() {   # the rebuild ran over the PINNED trees, at the pinned commits, and was committed
    local d="$FI/r" want
    fixture "$d" "$TC2" "$TC2"; : > "$FI/calls"
    fi_fold "$1" resolve-index "$d" >"$FI/r.log" 2>&1 || return 1
    git -C "$d" commit -q --no-edit || return 1
    fi_fold "$1" regen-index "$d" 7 >>"$FI/r.log" 2>&1 || return 1
    want="build tests=$FI/work/fold-pins/nxdk_pgraph_tests@$TC2 support=$FI/work/fold-pins/pbkitplusplus@$PB2"
    [ "$(grep '^build ' "$FI/calls")" = "$want" ] \
        && [ "$(git -C "$d" log -1 --format=%s)" = "nv2a index: regenerate after folding #7" ] \
        && git -C "$d" show "HEAD:$IX" | grep -q '"rebuilt": true' \
        && [ "$(git -C "$FI/tests" rev-parse HEAD)" = "$TC3" ] && [ "$(git -C "$FI/support" rev-parse HEAD)" = "$PB3" ]
}

check "(a) an index-only conflict resolves, staging master's copy" case_a "$HERE/fold.sh"
check "(b) index + a source file is refused, nothing staged or changed" case_b "$HERE/fold.sh"
check "  and the resolver stayed silent: that is an ordinary conflict, not an index one" [ ! -s "$FI/b.log" ]
check "(c) with the pins unavailable it is refused, nothing staged or changed" case_c "$HERE/fold.sh"
check "  the log says the tests commit is not here" grep -q "nxdk_pgraph_tests @ ${ABSENT:0:12} is not in" "$FI/c1.log"
check "  the log says the pbkit commit is not here" grep -q "pbkitplusplus @ ${ABSENT:0:12} is not in" "$FI/c2.log"
check "(d) sides naming different tests_commits are refused" case_d "$HERE/fold.sh"
check "  and the log names both" grep -q "${TC2:0:12}, the branch's from ${TC1:0:12}" "$FI/d.log"
check "the rebuild runs over the pinned middle commits, not the live checkouts" case_regen "$HERE/fold.sh"

# The pin MOVES: a second rebuild at another tests_commit refreshes the same worktree.
fixture "$FI/m" "$TC1" "$TC1"; : > "$FI/calls"
fi_fold "$HERE/fold.sh" resolve-index "$FI/m" >"$FI/m.log" 2>&1 && git -C "$FI/m" commit -q --no-edit
fi_fold "$HERE/fold.sh" regen-index "$FI/m" 8 >>"$FI/m.log" 2>&1
check "a moved pin is refreshed in place" \
    [ "$(grep '^build ' "$FI/calls")" = "build tests=$FI/work/fold-pins/nxdk_pgraph_tests@$TC1 support=$FI/work/fold-pins/pbkitplusplus@$PB2" ]

# A rebuild with fewer suites than a parent is refused, and nothing is committed.
fixture "$FI/f" "$TC2" "$TC2"
fi_fold "$HERE/fold.sh" resolve-index "$FI/f" >"$FI/f.log" 2>&1 && git -C "$FI/f" commit -q --no-edit
fi_top=$(git -C "$FI/f" rev-parse HEAD)
FI_SUITES=2 fi_fold "$HERE/fold.sh" regen-index "$FI/f" 9 >>"$FI/f.log" 2>&1; rc=$?
check "a rebuild that loses a suite is refused" [ "$rc" = 1 ]
check "  and says so" grep -q "the rebuilt index has 2 suites, HEAD^1's has 3" "$FI/f.log"
check "  and commits nothing" [ "$(git -C "$FI/f" rev-parse HEAD)" = "$fi_top" ]

# ------------------------------------------------------ the tick, end to end
# The modes above pin the resolver; this pins the wiring: a real fold.sh tick
# over a repository it really merges and pushes, with its own gh shim.
mkdir -p "$FI/bin"
cat > "$FI/bin/gh" <<'EOF'
#!/usr/bin/env bash
args="$*"; echo "$args" >> "${FI_GH_LOG:?}"
case "$1 $2" in
    "pr list")    [[ "$args" == *"--label fold-ready"* ]] \
                      && printf '170\tlane/fixidx\t%s\tfalse\tfold-ready\tfixidx: a lane\n' "${FI_HEAD:?}" ;;
    "pr view")    echo GREEN ;;
    "pr comment") { echo "--- comment on $3"; cat "${args##*--body-file }"; } >> "${FI_LOG:?}" ;;
    "api "*)      [[ "$args" == *"/labels"* && "$args" != *"-X"* ]] && echo fold-ready ;;
esac
exit 0
EOF
chmod +x "$FI/bin/gh"
R="$FI/host"; rm -rf "$R" "$FI/origin.git"
git -c init.defaultBranch=master init -q --bare "$FI/origin.git"
git -c init.defaultBranch=master init -q "$R"
git -C "$R" config user.name s; git -C "$R" config user.email s@t
git -C "$R" remote add origin "$FI/origin.git"
mkdir -p "$R/docs/testing" "$R/.github/workflows"
cp "$FI/stub.py" "$R/docs/testing/nv2a_index.py"
printf '#!/usr/bin/env bash\nexit 0\n' > "$R/docs/testing/preflight.sh"
printf 'jobs:\n  check:\n    steps:\n      - env:\n          PBKIT_SHA: %s\n' "$PB2" > "$R/.github/workflows/nv2a-index.yml"
index base "$TC2" > "$R/$IX"
git -C "$R" add -A; git -C "$R" commit -q -m base
git -C "$R" checkout -q -b lane/fixidx; index lane "$TC2" > "$R/$IX"; git -C "$R" commit -qam lane
git -C "$R" checkout -q master; index master "$TC2" > "$R/$IX"; git -C "$R" commit -qam master
git -C "$R" push -q origin master lane/fixidx
FI_MASTER0=$(git -C "$R" rev-parse master); FI_LANE=$(git -C "$R" rev-parse lane/fixidx)
fi_tick() {   # [env assignments...] : one tick of the REAL fold.sh, on a fresh host dir
    rm -rf "$FI/tw"; git -C "$R" worktree prune; : > "$FI/comments.log"; : > "$FI/ghcalls.log"
    git -C "$R" update-ref refs/heads/lane/fixidx "$FI_LANE"
    git -C "$R" push -q -f origin "$FI_MASTER0:refs/heads/master" lane/fixidx
    env "$@" FI_HEAD="$FI_LANE" FI_LOG="$FI/comments.log" FI_GH_LOG="$FI/ghcalls.log" FI_CALLS="$FI/calls" \
        TESTS="${FI_TESTS-$FI/tests}" SUPPORT="$FI/support" PATH="$FI/bin:$PATH" \
        HAKUX_WORK="$FI/tw" HAKUX_REPO_DIR="$R" bash "$HERE/fold.sh" > "$FI/tick.log" 2>&1
}
fi_handed_back() {   # labelled needs-rebase, cause names the index, nothing pushed
    grep -q -- '-X POST .*labels\[\]=needs-rebase' "$FI/ghcalls.log" \
        && grep -qx "files=$IX " "$FI/tw/handback/cause/170-$FI_LANE" \
        && [ "$(git -C "$FI/origin.git" rev-parse master)" = "$FI_MASTER0" ]
}

FI_TESTS="$FI/nowhere" fi_tick FI_UNUSED=1
check "tick, pins unavailable: handed back exactly as any conflict" fi_handed_back
check "  with the existing comment text" grep -q "conflicts in: \`$IX \`. The fold job resolves nothing" "$FI/comments.log"
check "  and the log says why it was not resolved" grep -q "is the only conflict, but not resolved here: no host checkout of nxdk_pgraph_tests" "$FI/tick.log"

fi_tick FI_SUITES=2
check "tick, rebuild loses a suite: handed back" fi_handed_back
check "  with the index-failure comment and the reason" grep -q "did not regenerate cleanly after the merge.*HEAD^1's has 3" "$FI/comments.log"
check "  and the head written off in failed/" grep -q "index regeneration failed: the rebuilt index has 2 suites" "$FI/tw/fold/failed/170-$FI_LANE"

fi_tick FI_UNUSED=1
check "tick, index-only conflict: folded and pushed" \
    [ "$(git -C "$FI/origin.git" log -1 --format=%s master)" = "nv2a index: regenerate after folding #170" ]
check "  the fold commit under it is a merge of the lane" \
    [ "$(git -C "$FI/origin.git" rev-parse master~1^2)" = "$FI_LANE" ]
check "  whose message says the index conflicted and master's copy was taken" \
    bash -c 'git -C "$1" log -1 --format=%b master~1 | grep -q "nv2a_index.json conflicted with master.s and nothing else did. master.s copy was taken"' _ "$FI/origin.git"
check "  and master's copy is what that merge holds" \
    bash -c 'git -C "$1" show master~1:docs/testing/nv2a_index.json | grep -q "\"who\": \"master\""' _ "$FI/origin.git"
check "  the rebuild ran over the pins" \
    grep -qx "build tests=$FI/tw/fold-pins/nxdk_pgraph_tests@$TC2 support=$FI/tw/fold-pins/pbkitplusplus@$PB2" "$FI/calls"
fi_no_label() { ! grep -q -- '-X POST .*labels\[\]=needs-rebase' "$FI/ghcalls.log"; }   # the call, not handback.sh's query
check "  and no needs-rebase was set" fi_no_label

# --------------------------------------------------------------- mutants
# One per new invariant, each made by editing a copy of the real script and
# judged by the same case function. A sed that no longer applies makes the
# mutant identical to the real script, and that is a failure of its own.
mutant() {   # <name> <sed expr> -> a mutated copy of the jobs dir; prints its fold.sh
    rm -rf "$FI/mut-$1"; cp -r "$HERE" "$FI/mut-$1"
    sed -i "$2" "$FI/mut-$1/fold.sh"; echo "$FI/mut-$1/fold.sh"
}
differs() { ! cmp -s "$1" "$HERE/fold.sh"; }
m=$(mutant onepath '/diff-filter=U)" = "\$INDEX" \] || return 1/d')
check "mutant: without the exactly-one-path test the sed applied" differs "$m"
case_b "$m" >/dev/null 2>&1 && bad "  mutant onepath: (b) still passes" || ok "  mutant onepath: (b) is red"
m=$(mutant samepin 's/\[ "\$ours" = "\$theirs" \]/true/')
check "mutant: without the tests_commit comparison the sed applied" differs "$m"
case_d "$m" >/dev/null 2>&1 && bad "  mutant samepin: (d) still passes" || ok "  mutant samepin: (d) is red"
m=$(mutant livetree 's/--tests "\$PIN_TESTS"/--tests "$TESTS"/g')
check "mutant: passing \$TESTS instead of the pin the sed applied" differs "$m"
case_regen "$m" >/dev/null 2>&1 && bad "  mutant livetree: the pinned-path check still passes" || ok "  mutant livetree: the pinned-path check is red"
