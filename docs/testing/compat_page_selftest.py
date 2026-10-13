#!/usr/bin/env python3
"""Selftest for compat_page.py: tier assignment per cause shape (including
the left-off ones), ledger-wins on a disagreement, the NFS override, the
"?" region fallback, and --check failing on a stale page."""
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "docs", "testing"))

import compat_page as cp  # noqa: E402

REGISTRY_HEADER = ["title_id", "aliases", "name", "status", "status_rule", "ledger",
                    "flicker", "holds", "hold_detail", "latest_verdict", "verdict_utc",
                    "fps_ok_share", "fps_window_median", "play_share", "play_s", "hitch",
                    "crash", "hang", "void", "failing_all", "cause", "fix_commit",
                    "last_run", "last_run_utc", "last_run_build", "runs_total",
                    "runs_today", "staged", "input_seq", "notes"]


def registry_row(**kv):
    row = {c: "" for c in REGISTRY_HEADER}
    row.update(kv)
    return row


def notes_row(section, title_id, title, **kv):
    row = {c: "" for c in cp.NOTES_COLS}
    row.update(section=section, title_id=title_id, title=title)
    row.update(kv)
    return row


class BelowBarQualifies(unittest.TestCase):
    def test_pure_fps_qualifies(self):
        self.assertTrue(cp.below_bar_qualifies(registry_row(failing_all="fps")))

    def test_menu_time_is_left_off(self):
        self.assertFalse(cp.below_bar_qualifies(registry_row(failing_all="menu_time")))

    def test_duration_is_left_off(self):
        self.assertFalse(cp.below_bar_qualifies(registry_row(failing_all="duration")))

    def test_reached_gameplay_unconfirmed_is_left_off(self):
        self.assertFalse(cp.below_bar_qualifies(
            registry_row(failing_all="fps+reached_gameplay")))

    def test_blank_cause_is_left_off(self):
        self.assertFalse(cp.below_bar_qualifies(registry_row(failing_all="")))


class CrashHangLeftOffReason(unittest.TestCase):
    def test_clean_crash_has_no_reason(self):
        row = registry_row(failing_all="crash+duration", cause="crash: guest exited after 247s")
        self.assertIsNone(cp.crash_hang_left_off_reason(row))

    def test_reached_gameplay_unconfirmed_flags(self):
        # SSX Tricky / Whacked shape.
        row = registry_row(
            failing_all="hang+reached_gameplay",
            cause="reached_gameplay: unconfirmed (generic route) -- review the contact sheet")
        self.assertIsNotNone(cp.crash_hang_left_off_reason(row))

    def test_thermal_void_flags(self):
        # Project Gotham Racing 2 shape.
        row = registry_row(failing_all="void+hang+duration+audio",
                            void="thermal-pause: thermal-pause-F8 1/1 began after +140 s")
        self.assertIsNotNone(cp.crash_hang_left_off_reason(row))

    def test_fps_only_cause_flags(self):
        # NHL Hitz Pro's stale cause tag shape, absent an override.
        row = registry_row(failing_all="fps", cause="fps: 75.0% of gameplay at >= 30 fps")
        self.assertIsNotNone(cp.crash_hang_left_off_reason(row))


class BuildNotPlayableRows(unittest.TestCase):
    def test_flagged_row_needs_an_override(self):
        registry_rows = [registry_row(title_id="4D57001A", name="NHL Hitz Pro",
                                       status="CRASH_OR_HANG", failing_all="fps",
                                       cause="fps: 75.0% of gameplay at >= 30 fps")]
        notes_rows = [notes_row("not_playable", "4D57001A", "NHL Hitz Pro",
                                 tested="2026-10-06", notes="Hangs after team selection")]
        # The real RED_OVERRIDES table carries this title_id; the generator
        # must accept it rather than raising.
        self.assertIn("4D57001A", cp.RED_OVERRIDES)
        out = cp.build_not_playable_rows(registry_rows, set(), notes_rows)
        self.assertEqual(len(out), 1)

    def test_unflagged_override_free_row_raises(self):
        registry_rows = [registry_row(title_id="AAAA0001", name="Some Game",
                                       status="CRASH_OR_HANG", failing_all="fps",
                                       cause="fps: 10% of gameplay at >= 30 fps")]
        notes_rows = [notes_row("not_playable", "AAAA0001", "Some Game",
                                 tested="2026-10-06", notes="Crashes early")]
        with self.assertRaises(SystemExit):
            cp.build_not_playable_rows(registry_rows, set(), notes_rows)

    def test_ledger_wins_excludes_a_ledger_title(self):
        registry_rows = [registry_row(title_id="BBBB0002", name="Ledger Game",
                                       status="CRASH_OR_HANG", failing_all="crash",
                                       cause="crash: guest exited after 10s")]
        notes_rows = [notes_row("not_playable", "BBBB0002", "Ledger Game",
                                 tested="2026-10-06", notes="Crashes early")]
        with self.assertRaises(SystemExit):
            cp.build_not_playable_rows(registry_rows, {"BBBB0002"}, notes_rows)

    def test_non_crash_or_hang_status_raises(self):
        registry_rows = [registry_row(title_id="CCCC0003", name="Pending Game",
                                       status="PENDING_OWNER")]
        notes_rows = [notes_row("not_playable", "CCCC0003", "Pending Game",
                                 tested="2026-10-06", notes="Crashes early")]
        with self.assertRaises(SystemExit):
            cp.build_not_playable_rows(registry_rows, set(), notes_rows)


class BuildBelowBarRows(unittest.TestCase):
    def test_ledger_wins_excludes_a_below_bar_title(self):
        registry_rows = [registry_row(title_id="DDDD0004", name="Ledger Below Bar",
                                       status="BELOW_BAR", failing_all="fps")]
        notes_rows = []
        out = cp.build_below_bar_rows(registry_rows, {"DDDD0004"}, notes_rows)
        self.assertEqual(out, [])

    def test_stale_notes_row_raises(self):
        registry_rows = [registry_row(title_id="EEEE0005", name="Now Fixed",
                                       status="BELOW_BAR", failing_all="menu_time")]
        notes_rows = [notes_row("below_bar", "EEEE0005", "Now Fixed", tested="2026-10-06")]
        with self.assertRaises(SystemExit):
            cp.build_below_bar_rows(registry_rows, set(), notes_rows)


class NfsOverride(unittest.TestCase):
    def test_nfs_notes_row_renders_with_hardcoded_figures(self):
        row = notes_row("playable", "4541007B", "Need for Speed: Most Wanted",
                         region="?", device="Nova", fps_median="29.9", time_at_bar="0.95",
                         gameplay_s="204", tested="2026-10-12",
                         notes="Hand-played race; 30 fps cap")
        md = cp.render_md([row], [], [])
        self.assertIn("Need for Speed: Most Wanted", md)
        self.assertIn("29.9", md)
        self.assertIn("95%", md)
        self.assertIn("Hand-played race; 30 fps cap", md)


class UnknownRegionFallback(unittest.TestCase):
    def test_blank_region_renders_as_question_mark(self):
        row = notes_row("playable", "", "Mystery Game", region="", device="Nova",
                         fps_median="60", time_at_bar="1.0", tested="2026-10-01")
        md = cp.render_md([row], [], [])
        self.assertIn("| Mystery Game | ? |", md)


class DateLine(unittest.TestCase):
    def test_date_line_follows_h1_and_carries_newest_tested_date(self):
        older = notes_row("playable", "", "Older", region="USA", device="Nova",
                          fps_median="60", time_at_bar="1.0", tested="2026-10-01")
        newer = notes_row("below_bar", "FFFF0006", "Newer", region="USA", device="Nova",
                          fps_median="25", time_at_bar="0.5", tested="2026-10-09")
        lines = cp.render_md([older], [newer], []).splitlines()
        self.assertEqual(lines[0], "# Compatibility")
        self.assertEqual(lines[1], "")
        self.assertRegex(lines[2], r"^_Last updated 2026-10-09, for version \d+\.\d+\.\d+\._$")


class CheckFailsOnStalePage(unittest.TestCase):
    def test_check_exits_nonzero_when_md_is_stale(self):
        with tempfile.TemporaryDirectory() as td:
            ledger = os.path.join(td, "ledger.tsv")
            registry = os.path.join(td, "registry.tsv")
            notes = os.path.join(td, "notes.tsv")
            out_md = os.path.join(td, "COMPATIBILITY.md")
            out_csv = os.path.join(td, "compatibility.csv")

            with open(ledger, "w") as f:
                f.write("date_pdt\ttitle\ttitle_id\tresult\taccepted_by\tevidence\n")
                f.write("2026-10-01\tSample Game\t-\tsome-run\towner\tNova run\n")
            with open(registry, "w") as f:
                f.write("# comment\n# comment\n")
                f.write("\t".join(REGISTRY_HEADER) + "\n")
            with open(notes, "w") as f:
                f.write("\t".join(cp.NOTES_COLS) + "\n")
                f.write("playable\t\tSample Game\tUSA\tfilename\tNova\t60\t1.0\t600\t2026-10-01\t\n")

            script = os.path.join(ROOT, "docs", "testing", "compat_page.py")
            common = ["python3", script, "--ledger", ledger, "--registry", registry,
                      "--notes", notes, "--out-md", out_md, "--out-csv", out_csv]

            # Stale: files don't exist yet.
            r = subprocess.run(common + ["--check"], capture_output=True)
            self.assertNotEqual(r.returncode, 0)

            # Write them, then --check should pass.
            r = subprocess.run(common, capture_output=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            r = subprocess.run(common + ["--check"], capture_output=True)
            self.assertEqual(r.returncode, 0, r.stderr)

            # Mutate the committed file; --check should now fail again.
            with open(out_md, "a") as f:
                f.write("\nstale addition\n")
            r = subprocess.run(common + ["--check"], capture_output=True)
            self.assertNotEqual(r.returncode, 0)


if __name__ == "__main__":
    unittest.main()
