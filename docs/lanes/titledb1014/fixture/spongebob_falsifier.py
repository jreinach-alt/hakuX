#!/usr/bin/env python3
"""The SpongeBob falsifier (#433 Part 1).

The owner's report: SpongeBob is listed as "copied" on the status page
while it is on the Playable wall. Mechanism: a device's own listing spells
the title "Nickelodeon SpongeBob SquarePants Battle for Bikini Bottom USA"
(the ISO's own name); the Playable ledger spells it "SpongeBob SquarePants:
Battle for Bikini Bottom". Before title_id became the join key,
status_html.py's titles05() bridged spellings only by in-session substring
matching, which an added prefix word and a trailing region tag both defeat
-- so the two spellings landed on two rows, and the one the ledger marked
Playable was never the one carrying any device.

This builds one minimal, self-contained work tree (no fixture shared with
any other selftest) with exactly that disagreement -- a titlepush listing
that teaches the catalog the ISO's spelling, an already-on-handhelds.json
entry using that same spelling with no title_id anywhere in it, and a
ledger row in the canonical spelling -- and renders titles05() twice: once
against the current status_html.py (must fold to one row, Playable), once
against the pre-#433 version at ref OLD_REF below (must split into two).
A green run on the "old" half and a red run on the "new" half is the
falsifier: if the old code ever stopped reproducing the bug, or the new
code ever stopped fixing it, this prints FAIL and exits 1.

Usage: python3 spongebob_falsifier.py [<repo>]
"""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile

REPO = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else
                        os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
# The commit this lane's title_id-join fix (f1e1ee18f9) landed on top of --
# the last state of status_html.py with no catalog at all.
OLD_REF = "f1e1ee18f9~1"

TID = "5451001A"
ISO_SPELLING = "Nickelodeon SpongeBob SquarePants Battle for Bikini Bottom USA"
LEDGER_SPELLING = "SpongeBob SquarePants: Battle for Bikini Bottom"


def build_tree(root):
    os.makedirs(os.path.join(root, "titles"), exist_ok=True)
    os.makedirs(os.path.join(root, "pm"), exist_ok=True)
    os.makedirs(os.path.join(root, "hardware", "titlepush"), exist_ok=True)
    # titles/already-on-handhelds.json: a bare display name, no title_id and
    # no ISO-filename structure -- exactly what a device listing's own name
    # field carries, and exactly what has no local way to find a title_id.
    json.dump([ISO_SPELLING], open(os.path.join(root, "titles", "already-on-handhelds.json"), "w"))
    # hardware/titlepush/listing-<dev>.txt: title_registry.py's own catalog
    # source for a device's staged-ISO listing, in the <TID>-stem.xiso.iso
    # convention -- this is how the catalog learns that this exact spelling
    # belongs to TID, the same way a real listing would.
    with open(os.path.join(root, "hardware", "titlepush", "listing-thor.txt"), "w") as fh:
        fh.write("%s-%s.xiso.iso\n" % (TID, ISO_SPELLING.replace(" ", "_")))
    # pm/playable-accepted.tsv: the ledger, canonical spelling, carrying its
    # own title_id (as a real row does once #433's column is added).
    with open(os.path.join(root, "pm", "playable-accepted.tsv"), "w") as fh:
        fh.write("date_pdt\ttitle\ttitle_id\tresult\taccepted_by\tevidence\n")
        fh.write("2026-09-01 12:00\t%s\t%s\tfalsifier\tfalsifier\tframes reviewed\n" % (LEDGER_SPELLING, TID))
    # An empty, valid targets.toml: this title has no registry entry, on
    # purpose -- the catalog must bridge the two spellings from the listing
    # and the ledger alone, with no help from targets.toml's own name field.
    open(os.path.join(root, "targets.toml"), "w").write("[defaults]\nplayable_fps = 30\n")


def render(status_html_path, root):
    """Import status_html.py from `status_html_path` under a fresh module
    name (so old and new don't collide in sys.modules) and run titles05()
    against the tree at `root`. Returns the rows whose title mentions
    "sponge" (case-insensitive) -- there should be exactly one title in this
    tree, but matching by name rather than assuming a row count keeps this
    from silently passing if titles05 renamed or dropped the row outright."""
    name = "status_html_falsifier_%d" % id(status_html_path)
    spec = importlib.util.spec_from_file_location(name, status_html_path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    try:
        spec.loader.exec_module(mod)
    finally:
        del sys.modules[name]
    os.environ["TITLE_TARGETS"] = os.path.join(root, "targets.toml")
    os.environ["TITLESTATE_DIR"] = os.path.join(root, "dispatch", "titlestate")
    os.environ.pop("STATUS_PATHFIND_RUNS", None)
    os.environ.pop("STATUS_XISO_DIR", None)
    os.environ.pop("HAKUX_XISO_DIR", None)
    F = mod.Facts({"WORK": root, "D": os.path.join(root, "dispatch")})
    out = mod.titles05(F, {}, os.path.join(root, "release.toml"), 2000000000)
    return [r for r in out["rows"] if "sponge" in r["title"].lower()]


def old_status_html(tmp):
    dest = os.path.join(tmp, "status_html_old.py")
    txt = subprocess.run(["git", "-C", REPO, "show", "%s:docs/testing/jobs/status_html.py" % OLD_REF],
                          capture_output=True, text=True, check=True).stdout
    open(dest, "w").write(txt)
    return dest


def main():
    fails = []
    with tempfile.TemporaryDirectory(prefix="spongebob-old-") as old_root, \
         tempfile.TemporaryDirectory(prefix="spongebob-new-") as new_root, \
         tempfile.TemporaryDirectory(prefix="spongebob-ref-") as refdir:
        build_tree(old_root)
        build_tree(new_root)
        old_path = old_status_html(refdir)
        new_path = os.path.join(REPO, "docs", "testing", "jobs", "status_html.py")

        old_rows = render(old_path, old_root)
        stages = sorted(r["stage"] for r in old_rows)
        print("old (pre-#433) status_html.py: %d row(s), stages %s" % (len(old_rows), stages))
        if not (len(old_rows) == 2 and stages == ["copied", "playable"]):
            fails.append("old code was expected to SPLIT into a copied row and a playable row "
                         "(reproducing the owner's report) and did not: %r" % old_rows)

        new_rows = render(new_path, new_root)
        stages = sorted(r["stage"] for r in new_rows)
        print("new (#433) status_html.py: %d row(s), stages %s" % (len(new_rows), stages))
        if not (len(new_rows) == 1 and stages == ["playable"]):
            fails.append("new code was expected to FOLD to one Playable row and did not: %r" % new_rows)

    if fails:
        print("FAIL")
        for f in fails:
            print(" - %s" % f)
        return 1
    print("PASS: the two-spelling defect reproduces on the pre-#433 code and is fixed on the current code")
    return 0


if __name__ == "__main__":
    sys.exit(main())
