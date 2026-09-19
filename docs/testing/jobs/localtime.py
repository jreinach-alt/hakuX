"""The Python half of the harness's display timezone. See localtime.sh.

    sys.path.insert(0, JOBS); from localtime import say_time, local_ts
    print("report generated %s" % say_time())

The zone name is NOT written here. It is parsed out of localtime.sh's
`HAKUX_TZ=` line so that one file owns it: the shell and the Python halves
cannot drift onto different zones, which is a failure that would show up as
two timestamps in one status page disagreeing by seven hours.

The display/data split is localtime.sh's, unchanged: anything a script
COMPARES lexically -- summarise_run.py's `ts` column, which status.sh filters
its 24h window on, arms.sh's watermark, the GitHub API's `since=` -- stays
UTC. Only what a person reads comes from here.

`Pacific/Los_Angeles` is not a zone name and ZoneInfo raises on it; the US
west coast is `America/Los_Angeles`. localtime.sh's header has the detail.
"""
import datetime
import os
import re

_HERE = os.path.dirname(os.path.abspath(__file__))


def _read_zone(path=None):
    """The HAKUX_TZ assignment from localtime.sh, or None if unreadable."""
    try:
        with open(path or os.path.join(_HERE, "localtime.sh"), encoding="utf-8") as fh:
            for line in fh:
                m = re.match(r"^HAKUX_TZ=([A-Za-z0-9_+/-]+)\s*$", line)
                if m:
                    return m.group(1)
    except OSError:
        pass
    return None


ZONE = _read_zone()


def tz():
    """The display timezone, or UTC if this host cannot resolve it.

    Falling back to UTC rather than raising keeps a reporting script running
    on a host with a thin tzdata; falling back LOUDLY (the caller's output
    then says "UTC", because the abbreviation comes from the object itself)
    keeps it from mislabelling the fallback as Pacific.
    """
    if ZONE:
        try:
            from zoneinfo import ZoneInfo
            return ZoneInfo(ZONE)
        except Exception:
            pass
    return datetime.timezone.utc


def say_time(when=None):
    """The wall clock now, for a human: "2026-09-19 06:32 PDT".

    Always carries the zone. The host ran UTC for the harness's first weeks,
    so a bare "06:32" is read as UTC by anyone who remembers the old format.
    """
    t = when or datetime.datetime.now(datetime.timezone.utc)
    if t.tzinfo is None:
        t = t.replace(tzinfo=datetime.timezone.utc)
    return t.astimezone(tz()).strftime("%Y-%m-%d %H:%M %Z")


def local_ts(iso):
    """Render a STORED UTC timestamp ("2026-09-19T13:32:07Z") in the display
    zone. The conversion belongs here, at the point of printing: the field
    stays UTC on disk so the scripts that compare it keep sorting correctly.

    An unparseable value comes back unchanged -- a report that silently blanks
    a column is harder to debug than one showing a timestamp it did not read.
    """
    if not iso:
        return ""
    try:
        t = datetime.datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ") \
            .replace(tzinfo=datetime.timezone.utc)
    except (ValueError, TypeError):
        return str(iso)
    return t.astimezone(tz()).strftime("%Y-%m-%d %H:%M %Z")
