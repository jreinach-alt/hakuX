# Sourced by ../selftest.sh with the harness already built: $T, $HERE, $REPO,
# the shims on PATH, ok/bad/check, and the live prediction's fixtures. Not
# executable, no shebang, no exit -- `fail` is shared and is the run's verdict.
#
# The display timezone: jobs/localtime.sh and jobs/localtime.py.
#
# Two halves of one rule. What a PERSON reads is shown in the display zone
# (tick logs, the status page, a verdict comment). What a SCRIPT COMPARES
# stays UTC, because every one of those comparisons is lexical and is correct
# only because UTC "%FT%TZ" sorts chronologically. Both halves are checked
# here, and the second half is checked precisely so that a later lane
# "finishing the job" turns this file red instead of introducing a bug that
# appears once a year on the November fall-back and leaves no trace.
#
# NOT TIME-OF-DAY DEPENDENT, ON PURPOSE. Every absolute assertion below fixes
# its INPUT instant rather than its environment: "2026-09-19T13:32:07Z must
# render as 06:32 PDT" is true whenever and wherever this runs. The one row
# fed through status.sh is dated relative to now so that it stays inside the
# page's own 24h window, and its expectation is derived from the same instant.
#
# Depends on the 10..50 fragments only for $HAKUX_WORK/logs/arms/tick.log,
# which arms.sh has written by the time this runs.

echo "== localtime: the display zone"

. "$HERE/localtime.sh"

# `check` runs its argv in THIS shell so that pass/fail accumulate; a negation
# needs a real function, not `!` in argv and not `bash -c` (an unexported var
# inside a child shell makes a negative check green against anything).
lt_absent()   { ! grep -qE "$1" "$2"; }
lt_hour_is()  { [ "${1:0:13}" = "$2" ] || [ "${1:0:13}" = "$3" ]; }

# ---------------------------------------------------------------- the zone
check "localtime.sh's zone resolves on this host (HAKUX_TZ_OK)" [ "$HAKUX_TZ_OK" = 1 ]

# One file owns the name. localtime.py parses it out of localtime.sh rather
# than repeating it, so this goes red if that parse ever stops matching --
# which would show up in production as two timestamps on one status page
# disagreeing by seven hours.
lt_pyzone=$(cd "$HERE" && python3 -c 'import localtime; print(localtime.ZONE or "")' 2>/dev/null)
check "localtime.py reads the same zone as localtime.sh (sh=$HAKUX_TZ py=$lt_pyzone)" \
      [ "$lt_pyzone" = "$HAKUX_TZ" ]

# THE CHECK THIS FRAGMENT EXISTS FOR. The brief that asked for this work
# specified TZ='Pacific/Los_Angeles'. There is no such zone: `Pacific/*` is
# the Pacific ocean (Auckland, Honolulu, Fiji) and the US west coast is
# `America/Los_Angeles`. glibc does not complain about the bad name -- it
# falls back to UTC and takes the string before the "/" as the abbreviation,
# so `TZ=Pacific/Los_Angeles date '+%F %H:%M %Z'` prints "2026-09-19 13:40
# Pacific" when the true Pacific time is 06:40 PDT. That is UTC wearing a
# label that reads as converted: a seven-hour error strictly worse than
# having left the timestamps in UTC, and invisible to any check that only
# asks "does the output mention Pacific".
#
# So ask the two things a silent UTC fallback cannot fake: a non-zero offset,
# and an abbreviation that CHANGES with the season. A bad name answers
# "Pacific" for both dates below; a host with no tzdata answers "UTC" for
# both; only a real US-Pacific zone answers PDT and then PST.
lt_off=$(TZ="$HAKUX_TZ" date -d 2026-09-19T13:32:07Z '+%z')
lt_sum=$(TZ="$HAKUX_TZ" date -d 2026-07-01T12:00:00Z '+%Z')
lt_win=$(TZ="$HAKUX_TZ" date -d 2026-01-01T12:00:00Z '+%Z')
check "the display zone is really offset from UTC, not a silent fallback (got $lt_off)" \
      [ "$lt_off" != "+0000" ]
check "the display zone observes summer time (2026-07-01 -> PDT, got $lt_sum)" [ "$lt_sum" = PDT ]
check "the display zone observes winter time (2026-01-01 -> PST, got $lt_win)" [ "$lt_win" = PST ]

# The two halves must agree to the minute on one fixed instant. Against the
# bad zone name they disagree loudly and in opposite directions: the shell
# says "13:32 Pacific", ZoneInfo raises and the Python half falls back to
# "13:32 UTC".
lt_sh=$(local_ts 2026-09-19T13:32:07Z)
lt_py=$(cd "$HERE" && python3 -c 'import localtime; print(localtime.local_ts("2026-09-19T13:32:07Z"))' 2>/dev/null)
check "localtime.sh renders 2026-09-19T13:32:07Z as 06:32 PDT (got '$lt_sh')" \
      [ "$lt_sh" = "2026-09-19 06:32 PDT" ]
check "localtime.py renders the same instant identically (got '$lt_py')" [ "$lt_py" = "$lt_sh" ]

# An unreadable value must come back unchanged, not blank: a status page that
# silently drops a column is harder to debug than one showing a timestamp it
# did not parse.
check "local_ts passes an unparseable value through" [ "$(local_ts 'not-a-time')" = "not-a-time" ]
check "local_ts renders an empty value as empty" [ -z "$(local_ts '')" ]

# fleet.py IS ALSO RUN FROM A COPY OF ITSELF: selftest.d/93's board fixture
# copies exactly check_coverage.py, fleet.py and board_files.py into a scratch
# directory and runs fleet.py there, with no jobs/ beside it. So fleet.py's
# import of the display helper has to be optional, and an unguarded one is not
# a theoretical risk -- it took out all ten of that fragment's checks at once
# on this branch's first CI run. Reproduce that layout here, so the next lane
# to add an import to fleet.py finds out from its own fragment rather than
# from somebody else's.
lt_copy="$T/fleet-copy"; mkdir -p "$lt_copy"
cp "$(dirname "$HERE")/fleet.py" "$(dirname "$HERE")/board_files.py" "$lt_copy/" 2>/dev/null
# The two board files 93's fixture also writes; HAKUX_BOARD_REF= makes
# board_files read them from this directory rather than from origin/board.
printf 'wave = 1\nupdated_utc = "2026-09-19T00:00:00Z"\n' > "$lt_copy/territory.toml"
printf '[issue.1]\ntitle = "t"\nstatus = "open"\nblocked_on = "b"\n' > "$lt_copy/nv2a_issues.toml"
lt_out=$(cd "$lt_copy" && HAKUX_BOARD_REF= HAKUX_REPO=example/none python3 "$lt_copy/fleet.py" 2>&1)
printf '%s\n' "$lt_out" > "$T/fleet-copy.out"
check "fleet.py still runs when copied away from jobs/ (no ImportError)" \
      lt_absent 'ImportError|ModuleNotFoundError' "$T/fleet-copy.out"
# And it degrades HONESTLY: the line says UTC when it is UTC. A copy that
# printed "PDT" while running on the fallback would be the exact defect this
# whole change exists to remove.
check "fleet.py's generated-at line survives the bare copy, labelled UTC" \
      grep -qE '^fleet report generated [0-9-]{10} [0-9]{2}:[0-9]{2} UTC$' "$T/fleet-copy.out"
# ...and in the real tree it reaches the helper, so the line carries the zone.
check "fleet.py in its own tree renders the generated-at line in the display zone" \
      grep -qE "^fleet report generated [0-9-]{10} [0-9]{2}:[0-9]{2} $(tz_abbr)$" \
      <<< "$(python3 -c "
import os, sys
HERE = os.path.abspath('$(dirname "$HERE")')
sys.path.insert(0, HERE); sys.path.insert(1, os.path.join(HERE, 'jobs'))
from localtime import say_time
print('fleet report generated %s' % say_time())" 2>&1)"

# ------------------------------------------------- display: the tick logs
# The real thing, not a grep: arms.sh has already run and written its log.
lt_log="$HAKUX_WORK/logs/arms/tick.log"
if [ -s "$lt_log" ]; then
    check "arms.sh stamps its tick log in the display zone" \
          grep -qE "^[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2} [A-Z]{3,5} " "$lt_log"
    check "arms.sh's tick log carries no UTC '...Z' stamp any more" \
          lt_absent '^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z ' "$lt_log"
else
    bad "arms.sh wrote no tick log, so its stamp could not be checked"
fi

# The other four say() sites are not all reachable from this fixture, so they
# are pinned on the call itself -- `$(say_time_s)` inside the say() body --
# rather than on any word in the surrounding prose.
for lt_j in board cloud fold handback; do
    check "$lt_j.sh's say() stamps through say_time_s" \
          grep -q 'say() { echo "$(say_time_s) \$\*" | tee -a "\$LOG"; }' "$HERE/$lt_j.sh"
done
check "nightly_build.sh's say() stamps through say_time_s" \
      grep -q 'say() { echo "$(say_time_s) \$\*" | tee -a "\$LOG"; }' "$(dirname "$HERE")/nightly_build.sh"

# ------------------------------------------------ display: the status page
# One row, dated relative to now so it stays inside the page's own 24h
# window, with its expectation derived from the same instant. This is not
# circular with respect to what is under test: the code being checked is
# status.sh's RENDERING of a stored UTC field, and the form it replaced --
# `${ts:5:11}`, a raw slice -- produces "09-19T01:10" where this wants
# "09-18 18:10". The helper itself is pinned absolutely, above.
lt_iso=$(date -u -d '1 hour ago' '+%FT%TZ')
lt_want=$(local_hm "$lt_iso")
printf '%s\tlane-ltz\tclaude-opus-5\t41\t1300\t0\tERR\tltz.json\tsaid a thing\n' "$lt_iso" \
    > "$HAKUX_WORK/logs/lane/index.tsv"
bash "$HERE/status.sh" --print > "$T/localtime-status.out" 2>&1
lt_abbr=$(tz_abbr)
check "status.sh's 'Rewritten' line names the display zone" \
      grep -qE "^_Rewritten [0-9-]{10} [0-9]{2}:[0-9]{2} $lt_abbr by " "$T/localtime-status.out"
check "status.sh's lane table header names the display zone, not UTC" \
      grep -qF "| when ($lt_abbr) |" "$T/localtime-status.out"
check "status.sh converts the stored UTC row to the display zone ($lt_iso -> $lt_want)" \
      grep -qF "| $lt_want | ltz |" "$T/localtime-status.out"
check "status.sh's lane table no longer heads its time column 'UTC'" \
      lt_absent '\| when \(UTC\) \|' "$T/localtime-status.out"

# ------------------------------------------------------------- data sites
# These must NOT move. Each is a lexical string comparison that is correct
# only in UTC; a local-time value would shift one side of the comparison
# against an unchanged other side, and across the November fall-back would
# make two distinct instants compare in the wrong order.

# Behavioural, not a grep: run summarise_run.py and check the hour it wrote
# is the UTC hour. Local time here would be seven hours out and would silently
# drop every row from status.sh's 24h window.
lt_h1=$(date -u '+%Y-%m-%dT%H')
lt_ts=$(python3 "$HERE/summarise_run.py" /dev/null probe 2>/dev/null | cut -f1)
lt_h2=$(date -u '+%Y-%m-%dT%H')
check "summarise_run.py's index column is UTC-shaped (got '$lt_ts')" \
      grep -qE '^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$' <<< "$lt_ts"
check "summarise_run.py's index column is UTC, not local ('$lt_ts' vs ${lt_h1}xx)" \
      lt_hour_is "$lt_ts" "$lt_h1" "$lt_h2"

check "status.sh's since_iso is still UTC (the GitHub API's zone, and the TSV cutoff)" \
      grep -q 'since_iso() { date -u -d' "$HERE/status.sh"
check "arms.sh's watermark seed is still UTC" \
      grep -qF "date -u -d '2 days ago' '+%FT%TZ' > \"\$A/since\"" "$HERE/arms.sh"
check "arms.sh's watermark comparison is untouched" \
      grep -qF '[ -n "$reg" ] && [ "$reg" \< "$SINCE" ]' "$HERE/arms.sh"
check "arms.sh still records queued_utc in UTC" \
      grep -qF '"queued_utc": datetime.datetime.now(datetime.timezone.utc)' "$HERE/arms.sh"

# The committed predictions' registered_utc is provenance bound into a
# measurement and is never rewritten -- AGENTS.md's whole discipline. Nothing
# in this change touches docs/testing/predictions/, and this asserts it stays
# that way by checking the field arms.sh reads is still the UTC one.
check "arms.sh still reads registered_utc as-is" grep -qF 'reg=$(field "$path" registered_utc)' "$HERE/arms.sh"

unset lt_j lt_iso lt_want lt_abbr lt_off lt_sum lt_win lt_sh lt_py lt_log lt_ts lt_h1 lt_h2 lt_pyzone lt_copy lt_out
