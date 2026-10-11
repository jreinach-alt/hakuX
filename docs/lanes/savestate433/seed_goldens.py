#!/usr/bin/env python3
"""Seed the live golden profiles (lane.savestate433, 2026-10-02). Run once;
idempotent: it never replaces a golden that is already set, and never
removes a save.

  1. Blinx 2 (4D530065): the owner's own save, "Jaguars" (Team01, save dir
     13C91777168C) and "Tigers" (Team02), from the 19:23 PDT hdd-reset backup
     of the Nova's hdd.img, imported into the store and made the golden.
  2. TitleID aliases where targets.toml's canonical id is not the disk's.
  3. Every other title in the store: its most recent verified harvest,
     PROPOSED (loads like a golden; lane.local / the owner confirm it with
     `titlestate.py promote --title-id T --save S`, or replace it).
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "testing", "titles"))
import titlestate as ts  # noqa: E402

BLINX2_BACKUP = os.path.join(ts.dispatch_dir(), "hdd-reset", "nova-20261003T022340Z", "saves", "4D530065")
ALIASES = {
    "4D53002D": "54430001",     # Dead or Alive 3: TitleMeta "Dead or Alive 3"
    "49470018": "5345000A",     # JSRF: TitleMeta "Jet Set Radio Future"
    "49470017": "5345000B",     # Gunvalkyrie: TitleMeta "Gunvalkrye" (sic)
}

tid, sid = ts.import_save(BLINX2_BACKUP)
print(f"imported {tid}/{sid} from {BLINX2_BACKUP}")
g = ts.golden(tid)
if not g or g["save"] != sid or g["status"] != "golden":
    ts.promote(tid, by="owner (hand play on the Nova's hdd.img; profile Jaguars, Team01)", save=sid,
               note="from the 2026-10-03T02:23:40Z hdd-reset backup; Team01 'Jaguars' (13C91777168C) "
                    "and Team02 'Tigers' (13C91777168D). Never overwrite without promote.")
print("Blinx 2 golden:", ts.golden(tid))
for t, d in ALIASES.items():
    if ts.load_goldens().get("aliases", {}).get(t) != d:
        ts.set_alias(t, d)
print("aliases:", ts.load_goldens().get("aliases"))
for t, s, why in ts.propose_all("lane.savestate433 (most recent verified harvest)"):
    print(f"proposed {t} {s or '-'} {why}")
