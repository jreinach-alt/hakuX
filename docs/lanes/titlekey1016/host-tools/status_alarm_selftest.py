#!/usr/bin/env python3
"""Selftest for status_alarm.py (#433 item 4): a fresh, matching STATUS.md is
quiet; a stale timestamp or a mismatched count each raise their own ALARM
line, independently of each other."""
import datetime
import os
import subprocess
import sys
import tempfile
import unittest
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import status_alarm as sa  # noqa: E402

PT = ZoneInfo("America/Los_Angeles")


def make_git_dir(tmp, status_md):
    git_dir = os.path.join(tmp, "repo.git")
    subprocess.run(["git", "init", "--bare", "-q", "-b", "home", git_dir], check=True)
    env = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t", GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@t")
    blob = subprocess.run(["git", "--git-dir", git_dir, "hash-object", "-w", "--stdin"],
                           input=status_md, capture_output=True, text=True, check=True).stdout.strip()
    tree = subprocess.run(["git", "--git-dir", git_dir, "mktree"],
                           input="100644 blob %s\tSTATUS.md\n" % blob, capture_output=True, text=True, check=True).stdout.strip()
    commit = subprocess.run(["git", "--git-dir", git_dir, "commit-tree", tree, "-m", "test"],
                             capture_output=True, text=True, check=True, env=env).stdout.strip()
    subprocess.run(["git", "--git-dir", git_dir, "update-ref", "refs/heads/home", commit], check=True)
    return git_dir


def make_ledger(tmp, n):
    path = os.path.join(tmp, "ledger.tsv")
    with open(path, "w") as f:
        f.write("date_pdt\ttitle\ttitle_id\tresult\taccepted_by\tevidence\n")
        for i in range(n):
            f.write("2026-10-01\tGame %d\tAAAA%04d\tsome-run\towner\tNova run\n" % (i, i))
    return path


STATUS_TMPL = "# hakuX status\n\n_updated %s_\n\nPlayable **%d** / 110.\n"


class StatusAlarm(unittest.TestCase):
    def test_fresh_and_matching_is_quiet(self):
        with tempfile.TemporaryDirectory() as tmp:
            now = datetime.datetime(2026, 10, 16, 8, 0, tzinfo=PT)
            stamp = (now - datetime.timedelta(minutes=30)).strftime("%Y-%m-%d %H:%M") + " PDT"
            git_dir = make_git_dir(tmp, STATUS_TMPL % (stamp, 87))
            ledger = make_ledger(tmp, 87)
            self.assertEqual(sa.check(git_dir, ledger, now=now), [])

    def test_stale_timestamp_alarms(self):
        with tempfile.TemporaryDirectory() as tmp:
            now = datetime.datetime(2026, 10, 16, 8, 0, tzinfo=PT)
            stamp = (now - datetime.timedelta(hours=33)).strftime("%Y-%m-%d %H:%M") + " PDT"
            git_dir = make_git_dir(tmp, STATUS_TMPL % (stamp, 87))
            ledger = make_ledger(tmp, 87)
            out = sa.check(git_dir, ledger, now=now)
            self.assertEqual(len(out), 1)
            self.assertIn("stale", out[0])

    def test_count_mismatch_alarms(self):
        with tempfile.TemporaryDirectory() as tmp:
            now = datetime.datetime(2026, 10, 16, 8, 0, tzinfo=PT)
            stamp = (now - datetime.timedelta(minutes=30)).strftime("%Y-%m-%d %H:%M") + " PDT"
            git_dir = make_git_dir(tmp, STATUS_TMPL % (stamp, 77))
            ledger = make_ledger(tmp, 87)
            out = sa.check(git_dir, ledger, now=now)
            self.assertEqual(len(out), 1)
            self.assertIn("Playable 77", out[0])
            self.assertIn("ledger has 87", out[0])

    def test_both_wrong_raises_both(self):
        with tempfile.TemporaryDirectory() as tmp:
            now = datetime.datetime(2026, 10, 16, 8, 0, tzinfo=PT)
            stamp = (now - datetime.timedelta(hours=33)).strftime("%Y-%m-%d %H:%M") + " PDT"
            git_dir = make_git_dir(tmp, STATUS_TMPL % (stamp, 77))
            ledger = make_ledger(tmp, 87)
            out = sa.check(git_dir, ledger, now=now)
            self.assertEqual(len(out), 2)


if __name__ == "__main__":
    unittest.main()
