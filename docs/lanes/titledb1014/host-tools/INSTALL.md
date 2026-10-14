# host-tools -- lane.titledb1014 (#433)

Neither file below is in the repo; these are edited copies of the live
scripts at `/home/justin/hakux-work/host-tools/` and `/home/justin/hakux-work/pm/`
for lane.local to diff, review and install.

## hourly_report.sh

Live at `host-tools/hourly_report.sh`. Only the "PLAYABLE" block (one
`echo`/`python3 -c` pair) changed: it now counts `status == PLAYABLE` rows
in `pm/title-registry.tsv` instead of counting `pm/playable-accepted.tsv`
lines itself, and compares the Wall's row count to that same table count.
It still reads the ledger for today's newly-added titles (the table has no
per-row acceptance date) and now prints a `LEDGER/TABLE MISMATCH` line if
the ledger's row count and the table's PLAYABLE count ever disagree. Also
dropped the stale hardcoded "of 50" (the 0.5 release's Playable target;
0.6 raised it and nothing here needs a target denominator to report a
count).

Install: diff against the live file; if accepted, replace it, no restart
needed (it's invoked by `hakux-hourly.timer`, next run picks it up).

## prequeue.py

Live at `pm/prequeue.py`. One line changed: the "ledger (Playable already
banked)" section no longer adds its own `"already in the Playable ledger"`
block reason -- the registry loop right above it already blocks on
`status == PLAYABLE` for the same title, read from the same table, so the
ledger section now only prints the acceptance evidence text (still useful
to a human) and leaves the blocking decision to the table. Verdict-file
scanning (the per-run fps_ok_share/crash/hang history) is unchanged: the
registry's single `latest_verdict`/`fps_ok_share` columns carry only the
most recent verdict, and prequeue.py's "last 4 distinct verdicts" history
view needs more than that one row to replace -- a larger change, not
attempted here (see NOTES.md).

Install: diff against the live file; drop-in replacement, no restart.
