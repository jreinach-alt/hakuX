#!/usr/bin/env bash
#
# The one place the harness's display timezone is written down.
#
#   . "$JOBS/localtime.sh"
#   say() { echo "$(say_time) $*" | tee -a "$LOG"; }      # 2026-09-19 06:32 PDT
#   echo "| $(local_ts "$registered_utc") | ..."          # a stored UTC field, shown local
#
# WHY THIS EXISTS AND WHAT IT DELIBERATELY DOES NOT COVER. The harness has two
# kinds of timestamp and only one of them may move:
#
#   display  a person reads it -- a tick log, the status page, a PR comment.
#            The owner reads the status page from a phone; "13:32 UTC" is a
#            subtraction they should not have to do. These come from here.
#
#   data     a script COMPARES it -- arms.sh's watermark, status.sh's 24h
#            window over logs/*/index.tsv, the GitHub API's `since=`. Every
#            one of those is a LEXICAL string comparison that is correct only
#            because UTC "%FT%TZ" sorts chronologically. Local time breaks
#            that twice a year: on the November fall-back 01:00-02:00 happens
#            twice, so two distinct instants produce strings that compare in
#            the wrong order and the comparison silently skips or repeats
#            work. Those sites stay `date -u` and say so in a comment.
#
# WHY NOT `Pacific/Los_Angeles`. That is not a zone name. The tz database has
# no `Pacific/Los_Angeles` -- `Pacific/*` is the Pacific ocean (Auckland,
# Honolulu, Fiji); the United States west coast is `America/Los_Angeles`. The
# two halves of the harness fail differently on the bad name, and the shell's
# failure is the dangerous one:
#
#   sh      TZ=Pacific/Los_Angeles date '+%F %H:%M %Z'  ->  2026-09-19 13:37 Pacific
#           glibc cannot find the file, falls back to UTC, and takes the
#           string before the "/" as the abbreviation. That is UTC wearing a
#           label that reads as Pacific -- a seven-hour error that looks
#           converted. Strictly worse than having left it as UTC.
#   python  ZoneInfo("Pacific/Los_Angeles") raises ZoneInfoNotFoundError.
#
# So the name is written once, here, and selftest.d/55-localtime.sh asserts
# that it resolves in BOTH halves and that they agree on the offset.
#
# HAKUX_TZ is read by localtime.py too, which parses the assignment below out
# of this file rather than repeating the name. Keep it a plain unquoted
# KEY=value on its own line at the start of the line.

HAKUX_TZ=America/Los_Angeles

# Does this host actually have that zone? glibc resolves a TZ of the form
# Area/Location against $TZDIR (/usr/share/zoneinfo by default) and, when it
# is missing, falls back to UTC WITHOUT any error -- see above. So probe the
# file, and if it is not there say UTC honestly rather than mislabel it.
if [ -e "${TZDIR:-/usr/share/zoneinfo}/$HAKUX_TZ" ]; then
    HAKUX_TZ_OK=1
else
    HAKUX_TZ_OK=0
fi

# The wall clock now, for a human. Always carries the zone: the host ran UTC
# for the harness's first weeks and a bare "06:32" would be read as UTC by
# anyone who remembers the old format.
say_time() {
    if [ "$HAKUX_TZ_OK" = 1 ]; then TZ="$HAKUX_TZ" date '+%F %H:%M %Z'
    else                            date -u '+%F %H:%M UTC'
    fi
}

# Same, with seconds, for a log line that may get several entries a minute.
say_time_s() {
    if [ "$HAKUX_TZ_OK" = 1 ]; then TZ="$HAKUX_TZ" date '+%F %H:%M:%S %Z'
    else                            date -u '+%F %H:%M:%S UTC'
    fi
}

# Render a STORED UTC timestamp ("2026-09-19T13:32:07Z", or anything `date -d`
# accepts) in the display zone. This is the conversion that belongs at the
# point of printing: the field itself stays UTC on disk so the scripts that
# compare it keep sorting correctly, and only the reader sees local time.
#
# An unparseable or empty value is echoed back unchanged rather than dropped
# -- a status page that silently blanks a column is harder to debug than one
# showing a timestamp it did not understand.
local_ts() {
    local t=${1:-} out=
    [ -n "$t" ] || { echo ""; return; }
    if [ "$HAKUX_TZ_OK" = 1 ]; then
        out=$(TZ="$HAKUX_TZ" date -d "$t" '+%F %H:%M %Z' 2>/dev/null)
    else
        out=$(date -u -d "$t" '+%F %H:%M UTC' 2>/dev/null)
    fi
    echo "${out:-$t}"
}

# As local_ts, but only the day and the clock -- for a table that has already
# named its zone in the header and would otherwise repeat "PDT" on every row.
local_hm() {
    local t=${1:-} out=
    [ -n "$t" ] || { echo ""; return; }
    if [ "$HAKUX_TZ_OK" = 1 ]; then
        out=$(TZ="$HAKUX_TZ" date -d "$t" '+%m-%d %H:%M' 2>/dev/null)
    else
        out=$(date -u -d "$t" '+%m-%d %H:%M' 2>/dev/null)
    fi
    echo "${out:-$t}"
}

# Today's date in the display zone, for something a person dates by their own
# day -- an audit filename, a nightly's log name. The host runs America/
# Los_Angeles, so `date -u +%F` past 17:00 local already names TOMORROW; an
# audit written on Tuesday evening filed under Wednesday is a small lie that
# costs someone a search. Unlike a clock time this is DST-safe to sort on: the
# fall-back repeats an hour, never a day, so %F stays monotonic.
local_day() {
    if [ "$HAKUX_TZ_OK" = 1 ]; then TZ="$HAKUX_TZ" date '+%F'
    else                            date -u '+%F'
    fi
}

# The zone abbreviation alone ("PDT"), for a table header or a section title
# that names the zone once instead of on every row.
tz_abbr() {
    if [ "$HAKUX_TZ_OK" = 1 ]; then TZ="$HAKUX_TZ" date '+%Z'
    else                            echo UTC
    fi
}
