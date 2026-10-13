#!/usr/bin/env python3
"""Freshness check for the public docs (#433).

The public docs (docs/testing/public_docs.txt) are written for someone
outside the project, and nobody was re-reading them: some of what they
describe was already stale before this script existed, with no way to tell
short of inferring an age from the prose. The fix is a date line every public
doc must carry as the first non-blank line after its H1:

    _Last updated 2026-10-12, for version 0.5.0._

and this script, which reads that line back and says which docs are overdue
for a pass -- by age (`--max-age-days`, default 14) or because the doc still
names an older release than the one actually being built.

    docs_freshness.py [--repo DIR] [--max-age-days N] [--release X.Y.Z] [--today YYYY-MM-DD]

Exit 0 when every doc is OK, 1 when at least one is not, 2 on a usage error.
Read-only: it never edits a doc, only reports on what it finds.
"""
import argparse
import datetime as dt
import os
import re
import sys

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover
    ZoneInfo = None

HERE = os.path.dirname(os.path.abspath(__file__))

H1_RE = re.compile(r"^#\s+\S")
DATE_LINE_RE = re.compile(
    r"^_Last updated ([^,]+), for version (\S+?)\._\s*$"
)
# the fallback literal in android/app/build.gradle.kts ("0.5.0-unknown"),
# the one X.Y.Z string that is actually written under android/ -- the real
# versionName is computed at build time by docs/testing/version_stamp.sh,
# which this script cannot run without a git checkout of the exact commit
# being released, so the gradle file's fallback is the base version both
# agree on (kept in sync by hand; see version_stamp.sh's BASE_VERSION).
GRADLE_VERSION_RE = re.compile(r'"(\d+\.\d+\.\d+)(?:-[A-Za-z0-9.]+)?"')


def parse_version(s):
    """'0.10.0-rc1' -> (0, 10, 0). None if no X.Y.Z is found anywhere in s."""
    m = re.search(r"(\d+)\.(\d+)\.(\d+)", s)
    if not m:
        return None
    return tuple(int(g) for g in m.groups())


def read_app_version(repo):
    android_dir = os.path.join(repo, "android")
    candidates = []
    for root, dirs, files in os.walk(android_dir):
        # skip generated/output dirs so a stale compiled artifact can't win
        dirs[:] = [d for d in dirs if d not in ("build", ".gradle")]
        for f in files:
            if f in ("build.gradle.kts", "build.gradle"):
                candidates.append(os.path.join(root, f))
    candidates.sort(key=lambda p: (0 if "app" in p.split(os.sep) else 1, p))
    for path in candidates:
        try:
            text = open(path, encoding="utf-8", errors="replace").read()
        except OSError:
            continue
        m = GRADLE_VERSION_RE.search(text)
        if m:
            return m.group(1)
    return None


def read_date_line(path):
    """(date_str, version_str) right after the doc's H1, or (None, None)."""
    try:
        text = open(path, encoding="utf-8", errors="replace").read()
    except OSError:
        return None, None
    lines = text.splitlines()
    h1 = next((i for i, l in enumerate(lines) if H1_RE.match(l)), None)
    if h1 is None:
        return None, None
    i = h1 + 1
    while i < len(lines) and lines[i].strip() == "":
        i += 1
    if i >= len(lines):
        return None, None
    m = DATE_LINE_RE.match(lines[i])
    if not m:
        return None, None
    return m.group(1), m.group(2)


def today_la(today_override):
    if today_override:
        return dt.date.fromisoformat(today_override)
    if ZoneInfo is not None:
        return dt.datetime.now(ZoneInfo("America/Los_Angeles")).date()
    return dt.date.today()


def load_public_docs(repo):
    list_path = os.path.join(repo, "docs", "testing", "public_docs.txt")
    paths = []
    with open(list_path, encoding="utf-8") as fh:
        for line in fh:
            line = line.split("#", 1)[0].strip()
            if line:
                paths.append(line)
    return paths


def check_one(repo, relpath, today, max_age_days, current_version):
    """-> (state, date_str, version_str, age_days_or_None)."""
    full = os.path.join(repo, relpath)
    if not os.path.isfile(full):
        return "MISSING-FILE", "-", "-", None

    date_str, version_str = read_date_line(full)
    if date_str is None:
        return "MISSING-LINE", "-", "-", None

    try:
        date = dt.date.fromisoformat(date_str)
    except ValueError:
        return "BAD-DATE", date_str, version_str, None
    if date > today:
        return "BAD-DATE", date_str, version_str, None

    version = parse_version(version_str)
    if version is None:
        return "BAD-DATE", date_str, version_str, None

    age = (today - date).days
    if age > max_age_days:
        return "STALE", date_str, version_str, age
    if current_version is not None and version < current_version:
        return "STALE", date_str, version_str, age
    return "OK", date_str, version_str, age


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0],
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--repo", default=os.path.normpath(os.path.join(HERE, "..", "..")))
    ap.add_argument("--max-age-days", type=int, default=14)
    ap.add_argument("--release", default=None, help="X.Y.Z; overrides the Gradle versionName")
    ap.add_argument("--today", default=None, help="YYYY-MM-DD; overrides today (for the selftest)")
    try:
        args = ap.parse_args(argv)
    except SystemExit as e:
        return 2 if e.code else 0

    repo = os.path.abspath(args.repo)

    try:
        today = today_la(args.today)
    except ValueError:
        print("docs_freshness.py: --today is not a valid YYYY-MM-DD date: %r" % args.today,
              file=sys.stderr)
        return 2

    if args.release is not None:
        current_version_str = args.release
    else:
        current_version_str = read_app_version(repo)
        if current_version_str is None:
            print("docs_freshness.py: could not find an app version under %s/android "
                  "(pass --release to override)" % repo, file=sys.stderr)
            return 2
    current_version = parse_version(current_version_str)
    if current_version is None:
        print("docs_freshness.py: %r is not an X.Y.Z version" % current_version_str,
              file=sys.stderr)
        return 2

    try:
        public_docs = load_public_docs(repo)
    except OSError as e:
        print("docs_freshness.py: %s" % e, file=sys.stderr)
        return 2

    ok_count = 0
    not_ok = []
    for relpath in public_docs:
        state, date_str, version_str, age = check_one(
            repo, relpath, today, args.max_age_days, current_version)
        age_str = str(age) if age is not None else "-"
        print("%-12s %-32s %-12s %-10s (%s d)" % (state, relpath, date_str, version_str, age_str))
        if state == "OK":
            ok_count += 1
        else:
            not_ok.append(relpath)

    print("public docs: %d OK, %d not%s" % (
        ok_count, len(not_ok), (": " + ", ".join(not_ok)) if not_ok else ""))

    return 0 if not not_ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
