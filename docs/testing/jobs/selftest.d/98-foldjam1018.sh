# Sourced by ../selftest.sh with the harness already built: $T, $HERE, $REPO,
# the shims on PATH, ok/bad/check. Not executable, no shebang, no exit --
# `fail` is shared and is the run's verdict.
#
# foldqueue.sh's blacklist (#433, foldjam1018 item B): a selftest failure used
# to blacklist a head by its bare sha forever, so fixing master never retried
# an already-failed lane -- lane.local had to hand-edit the blacklist file
# during the 2026-10-18 jam. The fix keys a selftest failure to the master sha
# it failed against (`head@master:sha`) and retries once that sha has moved.
#
# foldqueue.sh and offline_fold.py live outside this repo
# (/home/justin/hakux-work/offline-git/, not git-tracked) and cannot be
# imported here, so this mirrors the ~6-line skip-check foldqueue.sh runs
# against $TRIED before folding a head, verbatim as of 2026-10-18. If that
# script's key format changes, this fragment goes stale silently -- it tests
# the shape this file documents, not the live script itself. Depends on no
# other fragment.

echo "== foldqueue.sh: a selftest-failed head retries once master moves past the sha it failed at"
FJ="$T/foldjamqueue"; rm -rf "$FJ"; mkdir -p "$FJ"
TRIED="$FJ/foldqueue.tried"

skip_check() {   # <head> <master> -> prints "skip" or "retry", mirrors foldqueue.sh's blacklist skip-check
    local head=$1 master=$2
    grep -qx "$head" "$TRIED" 2>/dev/null && { echo skip; return; }
    local msline
    msline=$(grep -x "$head@master:[0-9a-f]\{1,\}" "$TRIED" 2>/dev/null | tail -1)
    if [ -n "$msline" ]; then
        local mssha=${msline#*@master:}
        [ "$mssha" = "$master" ] && { echo skip; return; }
    fi
    echo retry
}
export -f skip_check; export TRIED

# master shas must be hex (foldqueue.sh's own pattern is [0-9a-f]{1,}) -- m1/m2/m3 would silently
# never match and every "skipped" case below would pass for the wrong reason (always falling through
# to "retry"), which is exactly how a fixture can look green while testing nothing.
: > "$TRIED"
check "  a head never tried is retried" bash -c '[ "$(skip_check aaaa0001 1111111111)" = retry ]'

echo "aaaa0002@master:1111111111" >> "$TRIED"
check "  blacklisted at sha 11..., master still 11...: skipped" bash -c '[ "$(skip_check aaaa0002 1111111111)" = skip ]'
check "  blacklisted at sha 11..., master now 22...: retried (master advanced)" bash -c '[ "$(skip_check aaaa0002 2222222222)" = retry ]'

echo "aaaa0002@master:2222222222" >> "$TRIED"
check "  blacklisted again at 22..., master still 22...: skipped" bash -c '[ "$(skip_check aaaa0002 2222222222)" = skip ]'
check "  blacklisted again at 22..., master now 33...: retried" bash -c '[ "$(skip_check aaaa0002 3333333333)" = retry ]'

echo "aaaa0003" >> "$TRIED"
check "  a plain (non-selftest) blacklist entry never retries on its own" bash -c '[ "$(skip_check aaaa0003 9999999999)" = skip ]'

echo "== offline_fold.py: a Selftest: claim is checked against what the suite's fragments cover, not trusted"
# mentioning_fragments(fdir, changed, exclude=()) itself lives in offline_fold.py, outside this repo; this
# mirrors its match rule (a fragment's text contains a changed file's full path OR basename) to pin the
# exact defect found building this fix: 66-status-titles.sh mentions the file compat1017b actually changed
# (docs/testing/title_registry.py) only by BASENAME in a comment, so a full-path-only grep would miss it.
FRAG="$T/foldjamfrag"; rm -rf "$FRAG"; mkdir -p "$FRAG"
cat > "$FRAG/66-status-titles.sh" <<'EOF'
# `title_registry.py check --pages` (#433 Part 4): every public/rendered
EOF
cat > "$FRAG/01-other.sh" <<'EOF'
echo unrelated
EOF

mentions() {   # <fragdir> <changed-file...> -> matching fragment names, one per line, sorted
    local dir=$1; shift
    python3 - "$dir" "$@" <<'PYEOF'
import os, sys
fdir, changed = sys.argv[1], sys.argv[2:]
needles = set(changed) | {os.path.basename(f) for f in changed}
out = []
for fn in sorted(os.listdir(fdir)):
    if not fn.endswith(".sh"):
        continue
    text = open(os.path.join(fdir, fn)).read()
    if any(n in text for n in needles):
        out.append(fn[:-3])
print("\n".join(out))
PYEOF
}

out=$(mentions "$FRAG" "docs/testing/title_registry.py" "README.md" "docs/lanes/compat1017b/PR.md")
check "  the real compat1017b changed-file set matches 66-status-titles by basename" \
    bash -c "[ '$out' = '66-status-titles' ]"
out2=$(mentions "$FRAG" "docs/lanes/unrelated1018/NOTES.md")
check "  an unrelated changed-file set matches nothing" bash -c "[ -z '$out2' ]"

echo "== offline_fold.py: a widened fragment set is closed over selftest.sh's own SHARD_CHAINS"
# This lane's OWN fold failed on exactly this gap (hostops addendum, 2026-10-19 00:11 PDT): the "none"/named
# widens above pick 51-dispatch-hardening.sh because it mentions a changed file (check_territory.py), but
# 51 calls clear_markers/finish_queue, both only DEFINED in 50-arms-requeue.sh -- a full run only works
# because bash sources every fragment, in file order, in one shell before 51 runs. A SELFTEST_ONLY run that
# selects 51 alone never sources 50, so both calls fail open (`set -u`, not `set -e`: a bare "command not
# found", not a fatal error) and the fixture state they were supposed to reset stays dirty, cascading into
# unrelated-looking FAILs further down -- silently, not loudly. `shard_chains()`/`close_chains()` in
# offline_fold.py (outside this repo) fix this by reading the REAL SHARD_CHAINS array out of the REAL
# ../selftest.sh this fragment is itself running under (not a copy), so if that array is ever edited this
# check tracks it, unlike the synthetic fixtures above.
python3 - "$HERE/selftest.sh" <<'PYEOF'
import re, sys
text = open(sys.argv[1]).read()
m = re.search(r"^SHARD_CHAINS=\((.*?)^\)\s*$", text, re.M | re.S)
assert m, "SHARD_CHAINS not found in selftest.sh -- did its shape change?"
chains = [set(re.sub(r"\.sh\b", "", g).split()) for g in re.findall(r'"([^"]*)"', m.group(1))]
assert any({"50-arms-requeue", "51-dispatch-hardening"} <= c for c in chains), \
    "50-arms-requeue/51-dispatch-hardening are no longer in the same SHARD_CHAINS group -- " \
    "update the fixed scenario below (or this fragment) to match whatever pair still shares undefined-function state"
PYEOF
check "  selftest.sh still chains 50-arms-requeue with 51-dispatch-hardening (the real incident pair)" true

close_chains() {   # <space-separated selected names> -> closed set, one per line, sorted
    python3 - "$HERE/selftest.sh" "$1" <<'PYEOF'
import re, sys
text = open(sys.argv[1]).read()
m = re.search(r"^SHARD_CHAINS=\((.*?)^\)\s*$", text, re.M | re.S)
chains = [set(re.sub(r"\.sh\b", "", g).split()) for g in re.findall(r'"([^"]*)"', m.group(1))]
closed = set(sys.argv[2].split())
changed = True
while changed:
    changed = False
    for c in chains:
        if closed & c and not (c <= closed):
            closed |= c; changed = True
print("\n".join(sorted(closed)))
PYEOF
}
closed=$(close_chains "51-dispatch-hardening")
check "  closing over 51-dispatch-hardening alone pulls in 50-arms-requeue" \
    bash -c "grep -qx 50-arms-requeue <<< '$closed'"
closed2=$(close_chains "75-fold-exact")
check "  closing over an unchained fragment adds nothing" \
    bash -c "[ '$closed2' = '75-fold-exact' ]"

echo "== offline_fold.py: a partial run's log is scanned for the quiet 'command not found' this gap produces"
mkdir -p "$T/foldjamlog"; FJLOG="$T/foldjamlog/selftest.log"
cat > "$FJLOG" <<'EOF'
selftest: running 51-dispatch-hardening.sh
bash: line 270: clear_markers: command not found
FAIL E: dispatch half-written after the crash
selftest: 4 passed, 1 failed, PARTIAL: 1 of 157 fragments
EOF
missing=$(grep -oP '[^\s:]+(?=: command not found$)' "$FJLOG" | sort -u)
check "  the undefined-function line names clear_markers" bash -c "[ '$missing' = clear_markers ]"
clean_log="$T/foldjamlog/clean.log"; printf 'ok 1\nFAIL something unrelated\n' > "$clean_log"
missing2=$(grep -oP '[^\s:]+(?=: command not found$)' "$clean_log" | sort -u)
check "  a real failure with no such line names nothing" bash -c "[ -z '$missing2' ]"
