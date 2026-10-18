#!/usr/bin/env python3
"""Selftest for the #433 display-name fix in title_registry.py: one display
name per title_id, the ledger spelling wins over targets.toml, and
name_drift() catches it when they disagree. Uses the two examples from the
brief -- Crimson Skies and Conker -- in a throwaway fixture tree, so this
proves the MECHANISM, not whatever today's live data happens to agree on
(which this lane has already hand-fixed; see NOTES.md).

Each assertion that rests on the priority fix is paired with a MUTANT that
reinstates the pre-#433 behaviour (first-source-wins, no priority at all --
the same shape of bug as `where[t["name"]]`: whichever source is read last,
or happens to match, decides the name). A check whose mutant can't flip the
outcome is testing nothing."""
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import title_registry as TR  # noqa: E402

CRIMSON_TID = "4D530021"
CONKER_TID = "4D530051"


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def make_fixture(tmp, targets_name_crimson, targets_name_conker):
    """A root with just a ledger (curated, top priority) and a targets.toml
    (curated, second priority) naming the same two titles -- deliberately
    mismatched, per the brief's Crimson Skies / Conker examples."""
    root = os.path.join(tmp, "root")
    write(os.path.join(root, "pm", "playable-accepted.tsv"),
          "date_pdt\ttitle\ttitle_id\tresult\taccepted_by\tevidence\n"
          "2026-10-01\tCrimson Skies: High Road to Revenge\t%s\tsome-run\towner\tNova run\n"
          "2026-10-01\tConker: Live & Reloaded\t%s\tsome-run\towner\tNova run\n" % (CRIMSON_TID, CONKER_TID))
    targets = os.path.join(tmp, "targets.toml")
    write(targets,
          '[titles."%s"]\nname = "%s"\n\n'
          '[titles."%s"]\nname = "%s"\n' % (CRIMSON_TID, targets_name_crimson, CONKER_TID, targets_name_conker))
    p = TR.Paths(root=root)
    p.targets = targets
    return p


class PriorityPicksTheCuratedLedgerName(unittest.TestCase):
    """The brief's exact example: the registry (ledger) spelling wins over a
    filename-style targets.toml spelling."""

    def test_real_code_resolves_to_the_ledger_spelling(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = make_fixture(tmp, "Crimson Skies", "Conker: Live and Reloaded")
            cat = TR.build_catalog(p)
            self.assertEqual(cat.names[CRIMSON_TID], "Crimson Skies: High Road to Revenge")
            self.assertEqual(cat.names[CONKER_TID], "Conker: Live & Reloaded")

    def test_mutant_first_source_wins_resolves_to_the_wrong_name(self):
        """Mutant: Catalog.add() with no priority at all -- the first source to
        name a title_id keeps it, exactly the bug #433 fixed (and the same
        shape as a raw `where[name]` lookup: whichever write lands, wins).
        build_catalog() adds xemu/listings/inventory before targets.toml
        before the ledger, so under this mutant targets.toml's spelling
        would survive instead of the ledger's -- the opposite of the fix."""
        def mutant_add(self, tid, name, where, row=True):
            if not tid or not TR.TID_RE.match(tid.upper()):
                return
            tid = tid.upper()
            c = self.canonical(tid)
            self.aliases.setdefault(c, set()).add(tid)
            if row and name and c not in self.names:
                self.names[c] = name
            n = TR.norm_name(name)
            if n:
                self.by_norm.setdefault(n, {}).setdefault(c, []).append(where)

        with tempfile.TemporaryDirectory() as tmp:
            p = make_fixture(tmp, "Crimson Skies", "Conker: Live and Reloaded")
            real_add = TR.Catalog.add
            TR.Catalog.add = mutant_add
            try:
                cat = TR.build_catalog(p)
            finally:
                TR.Catalog.add = real_add
            # MUTANT SURVIVED if this still matches the ledger spelling.
            self.assertNotEqual(cat.names[CRIMSON_TID], "Crimson Skies: High Road to Revenge",
                                 "mutant survived: first-source-wins still produced the curated name")
            self.assertEqual(cat.names[CRIMSON_TID], "Crimson Skies")


class DriftCheckCatchesTheDisagreement(unittest.TestCase):
    def test_mismatched_targets_toml_is_red(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = make_fixture(tmp, "Crimson Skies", "Conker: Live and Reloaded")
            cat = TR.build_catalog(p)
            drift = dict(TR.name_drift(p, cat))
            self.assertIn(CRIMSON_TID, drift)
            self.assertIn(CONKER_TID, drift)

    def test_matching_targets_toml_is_green(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = make_fixture(tmp, "Crimson Skies: High Road to Revenge", "Conker: Live & Reloaded")
            cat = TR.build_catalog(p)
            drift = dict(TR.name_drift(p, cat))
            self.assertNotIn(CRIMSON_TID, drift)
            self.assertNotIn(CONKER_TID, drift)

    def test_mutant_drift_check_disabled_cannot_tell_them_apart(self):
        """Mutant: name_drift() always reports clean. Proves the two fixtures
        above actually differ in what a real check would say -- a drift
        check that can't be turned red is not protecting anything."""
        with tempfile.TemporaryDirectory() as tmp:
            bad = make_fixture(tmp, "Crimson Skies", "Conker: Live and Reloaded")
            cat_bad = TR.build_catalog(bad)
            real_drift = TR.name_drift
            TR.name_drift = lambda p, cat: []
            try:
                mutant_result = TR.name_drift(bad, cat_bad)
            finally:
                TR.name_drift = real_drift
            self.assertEqual(mutant_result, [], "sanity: mutant really is a no-op")
            real_result = real_drift(bad, cat_bad)
            self.assertNotEqual(real_result, mutant_result,
                                 "mutant survived: a disabled drift check still agrees with the real one")


    def test_readme_playable_line_must_be_the_numberless_form(self):
        """home_page.py rewrites master's exact numberless line; a numbered one
        (what compat1017 wrote, 10-17) froze every home update."""
        good = ("**Games rated Playable so far:** [the list, with progress charts]"
                "(https://github.com/jreinach-alt/hakuX/blob/home/STATUS.md).\n")
        bad = ("**[88 Playable games](https://github.com/jreinach-alt/hakuX/blob/home/STATUS.md)** "
               "so far, with progress charts \u2014 88 games rated Playable.\n")
        with tempfile.TemporaryDirectory() as tmp:
            p = make_fixture(tmp, "Crimson Skies: High Road to Revenge", "Conker: Live & Reloaded")
            for text, want in ((good, True), (bad, False), ("", False)):
                p.repo_readme = os.path.join(tmp, "README.md")
                write(p.repo_readme, text)
                self.assertEqual(TR.readme_has_numberless_line(p), want, text[:40])
            p.repo_readme = os.path.join(tmp, "missing.md")
            self.assertFalse(TR.readme_has_numberless_line(p))


if __name__ == "__main__":
    unittest.main()
