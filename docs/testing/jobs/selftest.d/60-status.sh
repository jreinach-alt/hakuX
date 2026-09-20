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
# RELATIVE TIMESTAMPS, AND THEY HAVE TO BE. status.sh:177 filters this file
# with `awk '$1 >= c'` where c is since_iso() -- "24 hours ago". These rows
# were written with the absolute date 2026-09-19T01:00/01:10Z, so at
# 2026-09-20T01:10:00Z they fell out of the window, the eight-column row
# stopped rendering, and the check below began failing on every branch and on
# master alike. A fixture dated by hand against a rolling window is a test
# that passes for one day; the run time is the only thing it can be pinned to.
sx=$(date -u -d '70 minutes ago' +%FT%TZ)
sy=$(date -u -d '60 minutes ago' +%FT%TZ)
printf '%s\tlane-x\t?\t?\t?\tERR\tx.json\t\n%s\tlane-y\tclaude-opus-5\t41\t1300\t0\tERR\ty.json\tsaid a thing\n' \
    "$sx" "$sy" > "$HAKUX_WORK/logs/lane/index.tsv"
sout=$(bash "$HERE/status.sh" --print 2>&1); src=$?
check "status.sh exits 0" [ "$src" -eq 0 ]
for h in "### Lanes running" "### Lane sessions finished" "### Cloud-class sessions" "### Board job" "### Handhelds and arms" "### Fold job" "### Open lane PRs" "### Host"; do
    check "status has '$h'" grep -q "^$h" <<< "$sout"
done
check "status renders the eight-column row without dying" grep -q '| y | opus-5 | 41 | 21 | ERR' <<< "$sout"
check "status shows the arms refusal in full" grep -q 'last refusals' <<< "$sout"
