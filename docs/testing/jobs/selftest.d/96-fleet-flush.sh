# Sourced by ../selftest.sh with the harness already built: $T, $HERE, $REPO,
# the shims on PATH, ok/bad/check, and the live prediction's fixtures. Not
# executable, no shebang, no exit -- `fail` is shared and is the run's verdict.
#
# fleet.py's stdout/stderr interleaving when both land in one file (#433,
# lane/fleetflush1010). Sorts before 96-fleet-registry.sh (`-flush` <
# `-registry`), so it owns no name that fragment has set yet.
#
# THE BUG. fleet.py prints its inventory to stdout and its FAIL lines to
# stderr, and never touches either stream's buffering. A pipe or a file is
# block-buffered (8 KB) for stdout while stderr stays line-buffered, so a
# caller that merges both (`2>&1` into one file or one pipe -- every
# selftest fixture's `fleet_run`, and session-start.sh's FAIL grep) gets
# stdout's 8 KB chunks and stderr's lines ordered by FLUSH time, not PRINT
# time. Once the inventory passes 8 KB, a buffered stdout line can still be
# sitting unflushed when a later stderr FAIL writes straight to the file,
# and the FAIL lands mid-line. Seen for real on 2026-10-10 in a fold log:
# "  #9401 -            selftest: an open issue no lane ownsFAIL: 1 open
# issue(s) are NEITHER BLOCKED..." -- and a `^FAIL` grep (board.sh,
# session-start.sh, 96-fleet-registry.sh:85-86) misses it outright.
#
# This fragment runs fleet.py from a SCRATCH COPY -- not against the live
# board, the way 96-fleet-registry.sh's fleet_run does -- because the bug
# depends only on total stdout size before the FAIL prints, and the live
# board's size drifts with every edit to territory.toml/nv2a_issues.toml.
# Depending on it is exactly how 96-fleet-registry.sh's own check started
# failing on 2026-10-10 with no lane diff. The padding here is 400 dummy
# `[lane.ghostN]` rows, chosen because it reliably pushes fleet.py's stdout
# past the 8 KB block-buffer boundary before the one real issue's FAIL
# prints (300 landed at 8001 bytes -- one byte under the boundary on the
# nose); it does not depend on anything else in the tree and will not drift.

echo "== fleet.py: stdout and stderr stay line-ordered when merged into one file"

export FFX="$T/fleet-flush"; mkdir -p "$FFX/bin"
# THE SAME "RUN FROM A COPY OF ITSELF" LAYOUT as 55-localtime.sh's fixture:
# fleet.py's import of jobs/localtime.py is optional for exactly this reason,
# and this fragment needs no jobs/ dir beside it either.
cp "$HERE/../fleet.py" "$HERE/../board_files.py" "$HERE/../gh_rest.py" "$FFX/"

cat > "$FFX/bin/systemctl" <<'EOF'
#!/usr/bin/env bash
exit 0
EOF
# A gh that answers fleet.py's two REST questions: one open issue (fleet.py's
# /issues? call), no PRs (/pulls?). See gh_rest.py for why REST and not
# `gh issue list`/`gh pr list` (GraphQL, refused in a Claude Code cloud
# session's proxy).
cat > "$FFX/bin/gh" <<'EOF'
#!/usr/bin/env bash
case "$*" in
    *"/issues?"*) echo '[{"number":9401,"title":"selftest: an open issue no lane owns"}]' ;;
    *"/pulls?"*)  echo '[]' ;;
    *) exit 0 ;;
esac
exit 0
EOF
chmod +x "$FFX/bin/"*

# PADDING, NOT THE LIVE BOARD. 400 lanes with no running unit are all
# "LANE CLAIMED WITH NO RUNNING AGENT" (ghost), a section fleet.py prints to
# stdout and raises no FAIL for -- so it pads the inventory without touching
# the one FAIL this fragment is checking.
{ echo 'wave = 1'
  for ffx_i in $(seq 1 400); do printf '[lane.ghost%d]\nfiles = []\n' "$ffx_i"; done
} > "$FFX/territory.toml"
printf '[issue]\n' > "$FFX/nv2a_issues.toml"
ffx_terr_size=$(wc -c < "$FFX/territory.toml")
check "the fixture's own padding passes 8 KB (got $ffx_terr_size bytes), so this does not depend on the live board's size" \
    [ "$ffx_terr_size" -gt 8192 ]

# stdout AND stderr into the SAME file, exactly as session-start.sh's
# `fleet.py 2>&1 | grep '^FAIL'` and every other merging caller do it.
( export PATH="$FFX/bin:$PATH" HAKUX_BOARD_REF= HAKUX_REPO=example/hakux \
         DISPATCH_DIR="$FFX/dispatch"
  cd "$FFX" && python3 fleet.py ) > "$FFX/out.txt" 2>&1

ffx_out_size=$(wc -c < "$FFX/out.txt")
check "fleet.py's merged output exceeds 8 KB (got $ffx_out_size bytes), so a block-buffered stdout would have flushed at least once already" \
    [ "$ffx_out_size" -gt 8192 ]
# THE CHECK THIS FRAGMENT EXISTS FOR. Every FAIL: this run produced starts
# its own line -- not just the one this fragment names. Comparing the two
# counts catches a FAIL spliced into ANY inventory line, not only #9401's.
check "every FAIL: in the merged output starts at column 0 (no mid-line splice)" \
    bash -c '[ "$(grep -c "^FAIL:" "$1")" = "$(grep -o "FAIL:" "$1" | wc -l)" ]' _ "$FFX/out.txt"
check "the one real issue's FAIL is still found by a ^FAIL grep" \
    grep -qE '^FAIL: .*NEITHER BLOCKED NOR MARKED AVAILABLE.*#9401' "$FFX/out.txt"
