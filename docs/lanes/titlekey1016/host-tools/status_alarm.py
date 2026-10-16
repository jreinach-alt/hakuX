#!/usr/bin/env python3
"""hourly_report.sh section (#433 item 4): the public status page can go stale or
drift from the ledger with nobody paged -- that's exactly how the 10-14/10-16
incident ran 32 hours (STATUS.md stuck at "Playable 77" while the ledger, and
the README, had already reached 87). This reads the SAME two numbers a human
would compare by hand: the `home` branch's published STATUS.md, and the live
ledger, and prints one ALARM line per thing that disagrees. Never edits
anything; exits 0 always (an hourly section reports, it doesn't fail the run)."""
import csv
import datetime
import re
import subprocess
import sys
from zoneinfo import ZoneInfo

PT = ZoneInfo("America/Los_Angeles")
STALE_HOURS = 2


def git_show(git_dir, ref):
    return subprocess.run(["git", "--git-dir", git_dir, "show", ref],
                           capture_output=True, text=True, check=True).stdout


def ledger_count(ledger_path):
    with open(ledger_path, newline="") as f:
        return sum(1 for _ in csv.DictReader(f, delimiter="\t"))


def parse_status(md):
    """(updated_dt or None, playable_count or None) from a home-branch STATUS.md."""
    m = re.search(r"_updated (\d{4}-\d{2}-\d{2} \d{2}:\d{2}) \w+_", md)
    updated = None
    if m:
        updated = datetime.datetime.strptime(m.group(1), "%Y-%m-%d %H:%M").replace(tzinfo=PT)
    m = re.search(r"Playable \*\*(\d+)\*\*", md)
    playable = int(m.group(1)) if m else None
    return updated, playable


def check(git_dir, ledger_path, now=None):
    """[alarm lines], or [] if both checks pass. `now` is injectable for tests."""
    now = now or datetime.datetime.now(PT)
    out = []
    try:
        md = git_show(git_dir, "home:STATUS.md")
    except subprocess.CalledProcessError:
        return ["ALARM: home:STATUS.md unreadable (%s)" % git_dir]
    updated, published = parse_status(md)
    if updated is None:
        out.append("ALARM: home:STATUS.md has no \"_updated ...\" stamp to check")
    else:
        age_h = (now - updated).total_seconds() / 3600
        if age_h > STALE_HOURS:
            out.append("ALARM: home:STATUS.md is %.1f h stale (cap %dh, updated %s)"
                        % (age_h, STALE_HOURS, updated.strftime("%Y-%m-%d %H:%M %Z")))
    actual = ledger_count(ledger_path)
    if published is None:
        out.append("ALARM: home:STATUS.md has no \"Playable **N**\" count to check")
    elif published != actual:
        out.append("ALARM: home:STATUS.md says Playable %d, ledger has %d" % (published, actual))
    return out


def main():
    import argparse
    a = argparse.ArgumentParser()
    a.add_argument("--git-dir", default="/home/justin/hakux-work/offline-git/hakuX.git")
    a.add_argument("--ledger", default="/home/justin/hakux-work/pm/playable-accepted.tsv")
    args = a.parse_args()
    lines = check(args.git_dir, args.ledger)
    if lines:
        for ln in lines:
            print("  " + ln)
    else:
        print("  home:STATUS.md: fresh and matches the ledger")
    return 0


if __name__ == "__main__":
    sys.exit(main())
