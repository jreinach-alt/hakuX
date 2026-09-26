# Sourced by ../selftest.sh with the harness already built: $T, $HERE, $REPO,
# the shims on PATH, ok/bad/check, and the live prediction's fixtures. Not
# executable, no shebang, no exit -- `fail` is shared and is the run's verdict.
#
# status.sh: every section renders, and the eight-column lane row with a "?"
# in it does not kill the render.
#
# Reads the arms state the 10..50 fragments left behind (the refusal it shows
# is 40-arms-refusal's), so it runs after them.

echo "== status.sh"
# RELATIVE TO NOW, NOT A DATE. `### Lane sessions finished` filters on
# since_iso() -- `date -u -d '24 hours ago'` -- so a hardcoded stamp is a fixture
# with a fuse in it: these two rows read 2026-09-19T01:00Z and T01:10Z, and at
# 2026-09-20T01:26Z they fell out of the window twenty-six and sixteen minutes
# apart, turning green into red on every branch at once for a fault in none of
# them. The row's CONTENT is what these checks are about; its age is not, so
# the age is pinned inside the window instead of being pinned to a day.
sixty_ago=$(date -u -d '60 minutes ago' +%FT%TZ)
fifty_ago=$(date -u -d '50 minutes ago' +%FT%TZ)
printf '%s\tlane-x\t?\t?\t?\tERR\tx.json\t\n%s\tlane-y\tclaude-opus-5\t41\t1300\t0\tERR\ty.json\tsaid a thing\n' \
    "$sixty_ago" "$fifty_ago" > "$HAKUX_WORK/logs/lane/index.tsv"
sout=$(bash "$HERE/status.sh" --print 2>&1); src=$?
check "status.sh exits 0" [ "$src" -eq 0 ]
for h in "### Lanes running" "### Lane sessions finished" "### Cloud-class sessions" "### Board job" "### Handhelds and arms" "### Fold job" "### Open lane PRs" "### Host"; do
    check "status has '$h'" grep -q "^$h" <<< "$sout"
done
check "status renders the eight-column row without dying" grep -q '| y | opus-5 | 41 | 21 | ERR' <<< "$sout"
check "status shows the arms refusal in full" grep -q 'last refusals' <<< "$sout"
