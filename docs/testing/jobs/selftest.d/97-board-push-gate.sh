# Sourced by ../selftest.sh with the harness already built: $T, $HERE, $REPO,
# $TESTING, the shims on PATH, ok/bad/check. Not executable, no shebang, no
# exit -- `fail` is shared and is the run's verdict.
#
# THE BOARD PUSH GATE. The board job's session pushes `board` itself, and on
# 2026-09-26 it pushed a board that failed check_coverage twice; a red
# origin/board is red preflight for every lane. jobs/board-push-gate.sh runs
# both board checkers against a candidate board, and board.sh installs it as
# a pre-push hook in the board tree. Checked here:
#   - an OPEN issue marked dispatch_state="done" is refused, BY NAME;
#   - a clean board passes; an unparsable one fails closed; no network is the
#     checker's own fail-open, and is SAID;
#   - the installed hook refuses a red push to `board` on a real `git push`,
#     lets other refs through, gates the pushed COMMIT and not the working
#     tree, and is not installed in any other worktree of the repository.
#
# EVERY CHECK READS THE OUTPUT WORDS as well as the exit code: a gate that
# cannot run at all also exits non-zero, and would pass "is refused" for free.
#
# Builds its own repository, board, bare remotes and gh under $BP; depends on
# no other fragment.

echo "== board push gate: a red board cannot be pushed to \`board\`"
BP="$T/boardpush"; mkdir -p "$BP/bin" "$BP/dispatch"
cat > "$BP/bin/gh" <<'EOF'
#!/usr/bin/env bash
# Two open issues over REST; BP_OFFLINE=1 is the ordinary network blip.
[ -n "${BP_OFFLINE:-}" ] && { echo "dial tcp: lookup api.github.com: no such host" >&2; exit 1; }
case "$*" in
    # A short first page, so the reader stops there.
    *"/issues?"*) echo '[{"number": 1, "title": "one"}, {"number": 2, "title": "two"}]' ;;
    *"/pulls?"*) echo '[]' ;;
    *) exit 0 ;;
esac
EOF
chmod +x "$BP/bin/gh"

# A repository whose master carries the checkers, and an orphan `board`.
R="$BP/repo"
git init -q -b master "$R"
git -C "$R" config user.email t@t; git -C "$R" config user.name t
mkdir -p "$R/docs/testing"
cp "$TESTING/check_territory.py" "$TESTING/check_coverage.py" "$TESTING/board_files.py" \
   "$TESTING/gh_rest.py" "$R/docs/testing/"
git -C "$R" add -A && git -C "$R" commit -q -m checkers
bpboard() {   # <dir> <issue 2's extra line>: a board with two open, blocked issues
    printf 'wave = 1\n[free]\nfiles = []\n' > "$1/territory.toml"
    printf '[issue.1]\ntitle = "one"\nstatus = "open"\nstatus_note = "n"\nblocked_on = "Blocked on real Xbox hardware, which nobody has."\n\n[issue.2]\ntitle = "two"\nstatus = "open"\nstatus_note = "n"\nblocked_on = "Blocked on real Xbox hardware, which nobody has."\n%s\n' "$2" > "$1/nv2a_issues.toml"
}
git -C "$R" worktree add -q --detach "$BP/bt" master
git -C "$BP/bt" checkout -q --orphan board && git -C "$BP/bt" rm -rq --cached . && rm -rf "$BP/bt/docs"
bpboard "$BP/bt" ''
git -C "$BP/bt" add territory.toml nv2a_issues.toml && git -C "$BP/bt" commit -q -m "clean board"
CLEAN=$(git -C "$BP/bt" rev-parse HEAD)

gate() {   # [--rev <c>] <tree>
    env PATH="$BP/bin:$PATH" DISPATCH_DIR="$BP/dispatch" HAKUX_REPO=example/hakux \
        HAKUX_GATE_BASE="${BP_BASE:-master}" bash "$HERE/board-push-gate.sh" "$@" 2>&1
}

# ------------------------------------------------------------ 1. the gate alone
out=$(gate "$BP/bt"); rc=$?
check "a clean board PASSES the gate (exit 0)" test "$rc" = 0
check "...and says PASS, having run both checkers" \
    bash -c 'grep -q "^board-push-gate: PASS:" <<< "$1" && grep -q "ok: check_territory.py" <<< "$1" && grep -q "ok: check_coverage.py" <<< "$1"' _ "$out"

bpboard "$BP/bt" 'dispatch_state = "done"'
out=$(gate "$BP/bt"); rc=$?
check "an OPEN issue marked dispatch_state=\"done\" is REFUSED (exit 1)" test "$rc" = 1
check "...by check_coverage's own FAIL line" \
    grep -q "^FAIL: 1 entry whose \`dispatch_state\` does not hold:" <<< "$out"
check "...naming the row, #2, and why" \
    grep -qE '^  #2 +`done` on a row whose status is still `open`' <<< "$out"
check "...and the refusal tells the session what to do next" \
    grep -q "^board-push-gate: REFUSED: .*Repair the named rows, re-run this gate, then push" <<< "$out"
check "...without the checker's explanatory paragraph (FAIL rows only)" \
    bash -c '! grep -q "is one of available" <<< "$1"' _ "$out"

out=$(BP_OFFLINE=1 gate "$BP/bt"); rc=$?
check "no network: the gate fails open exactly where check_coverage does (exit 0)" test "$rc" = 0
check "...and SAYS it did not check, rather than printing ok" \
    bash -c 'grep -q "check_coverage.py could not reach GitHub and FAILED OPEN" <<< "$1" && ! grep -q "ok: check_coverage.py" <<< "$1"' _ "$out"

printf 'this is [not toml\n' > "$BP/bt/territory.toml"
out=$(gate "$BP/bt"); rc=$?
check "an unparsable board FAILS CLOSED (exit 1)" test "$rc" = 1
check "...saying the checker crashed, not that the board is fine" \
    grep -q "exited 1 WITHOUT a FAIL line (a crash, or a timeout); failing closed" <<< "$out"
out=$(BP_BASE=no-such-ref gate "$BP/bt"); rc=$?
check "an unresolvable base FAILS CLOSED, and says so" \
    bash -c '[ "$2" = 1 ] && grep -q "cannot resolve no-such-ref" <<< "$1"' _ "$out" "$rc"
check "...and no scratch worktree is left registered behind the gate" \
    bash -c '[ "$(git -C "$1" worktree list | wc -l)" = 2 ]' _ "$R"

# --------------------------------------------------------- 2. the hook, on git push
out=$(bash "$HERE/board.sh" install-hook "$BP/bt" "$HERE/board-push-gate.sh" 2>&1)
check "board.sh install-hook arms the board tree" grep -q "board pre-push hook installed in" <<< "$out"
check "...as a hooksPath in THAT worktree's own config, not the shared one" \
    bash -c 'git -C "$1" config --worktree core.hooksPath | grep -q board-hooks && [ -z "$(git -C "$2" config core.hooksPath)" ]' _ "$BP/bt" "$R"
git init -q --bare "$BP/remote.git"; git init -q --bare "$BP/other.git"
bpush() {   # <tree> <remote> <refspec>
    env PATH="$BP/bin:$PATH" DISPATCH_DIR="$BP/dispatch" HAKUX_REPO=example/hakux \
        HAKUX_GATE_BASE=master git -C "$1" push "$2" "$3" 2>&1
}
bpboard "$BP/bt" 'dispatch_state = "done"'
git -C "$BP/bt" commit -qam "red board: done on an open issue"
RED=$(git -C "$BP/bt" rev-parse HEAD)
# The working tree is put back to clean WITHOUT committing: the hook must
# judge the commit being pushed, not the files beside it.
bpboard "$BP/bt" ''

out=$(bpush "$BP/bt" "$BP/remote.git" HEAD:refs/heads/scratch); rc=$?
check "the hook lets a push to ANOTHER ref through (exit 0)" test "$rc" = 0
check "...and did not run the gate for it" bash -c '! grep -q "board-push-gate" <<< "$1"' _ "$out"

out=$(bpush "$BP/bt" "$BP/remote.git" HEAD:refs/heads/board); rc=$?
check "git push of a red commit to \`board\` is REFUSED by the hook" \
    bash -c '[ "$2" != 0 ] && grep -q "^board-push-gate: REFUSED:" <<< "$1"' _ "$out" "$rc"
check "...naming #2 and the FAIL, from the pushed commit (the working tree is clean)" \
    bash -c 'grep -q "^FAIL: 1 entry whose \`dispatch_state\`" <<< "$1" && grep -qE "^  #2 " <<< "$1"' _ "$out"
check "...and the remote has no \`board\` ref" \
    bash -c '! git -C "$1" rev-parse -q --verify refs/heads/board' _ "$BP/remote.git"

out=$(bpush "$BP/bt" "$BP/remote.git" ":refs/heads/board"); rc=$?
check "a push that DELETES \`board\` is refused too" \
    bash -c '[ "$2" != 0 ] && grep -q "this push deletes refs/heads/board" <<< "$1"' _ "$out" "$rc"

# The hook is per worktree: the main checkout of the same repository pushes
# the same red commit to `board` unhindered. That is scope, not a hole --
# board.sh arms both trees the board job owns -- and it is what keeps the
# owner's other checkouts from inheriting a gate on every push.
out=$(bpush "$R" "$BP/other.git" "$RED:refs/heads/board"); rc=$?
check "another worktree of the repository is NOT gated (the hook is per worktree)" \
    bash -c '[ "$2" = 0 ] && ! grep -q "board-push-gate" <<< "$1"' _ "$out" "$rc"

git -C "$BP/bt" commit -qam "repair: #2 is not done"
out=$(bpush "$BP/bt" "$BP/remote.git" HEAD:refs/heads/board); rc=$?
check "after the repair the same push goes through (exit 0, gate PASS)" \
    bash -c '[ "$2" = 0 ] && grep -q "^board-push-gate: PASS:" <<< "$1"' _ "$out" "$rc"
check "...and the remote's \`board\` is the repaired commit" \
    bash -c '[ "$(git -C "$1" rev-parse refs/heads/board)" = "$(git -C "$2" rev-parse HEAD)" ]' _ "$BP/remote.git" "$BP/bt"

# A hook whose gate has gone missing refuses, rather than waving pushes by.
out=$(bash "$HERE/board.sh" install-hook "$BP/bt" "$BP/no-such-gate.sh" 2>&1)
out=$(bpush "$BP/bt" "$BP/remote.git" "$CLEAN:refs/heads/board-old"); rc0=$?
out=$(bpush "$BP/bt" "$BP/remote.git" "+$CLEAN:refs/heads/board"); rc=$?
check "a hook whose gate script is missing FAILS CLOSED on \`board\` only" \
    bash -c '[ "$2" = 0 ] && [ "$3" != 0 ] && grep -q "is missing (failing closed)" <<< "$1"' _ "$out" "$rc0" "$rc"
