# compatrefresh1013: the compatibility page and README move to 57 Playable; Aeon Flux and Half-Life 2 listed below 30 fps (#433, 0.5)

State: ready

Lane: compatrefresh1013          Issue: #433
Base: master @ d0102bb88d
Files: docs/testing/compat_notes.tsv, docs/COMPATIBILITY.md, docs/compatibility.csv, README.md, docs/lanes/compatrefresh1013/**
Prediction: none (docs only)
Needs device: no    Needs NDK: no

## What this is

The page was last built from 52 Playable ledger rows. The ledger now has 57:
five titles were rated Playable on the Nova on 2026-10-13, each after a frame
review of its run.

| Title | Title ID | Median fps | Time at bar | Gameplay |
|---|---|---|---|---|
| Tony Hawk's Underground 2 | 4156003C | 59.7 | 100% | 606 s |
| Scooby-Doo! Unmasked (Europe) | 545100F7 | 59.94 | 99.4% | 1364 s |
| Shadow of Memories (Europe) | 4B4E000E | 29.97 | 100% | 663 s |
| Tony Hawk's Pro Skater 4 | 41560017 | 56.6 | 97.5% | 604 s |
| 25 to Life | 45530018 | 59.94 | 97.4% | 609 s |

Two titles were measured below the bar the same day, on frame rate alone (no
crash, no hang). The registry now rates both BELOW_BAR, so the generator
requires a below-30 row for each:

| Title | Title ID | Median fps | Time at bar |
|---|---|---|---|
| Aeon Flux | 4D4A0014 | 29.96 | 84.6% |
| Half-Life 2 | 45410091 | 29.78 | 74.2% |

- `docs/testing/compat_notes.tsv`: seven rows. The Playable rows take the
  median, time at bar and gameplay from each title's scored verdict, as the 52
  existing rows do; the below-30 rows take them from the registry, with the
  gameplay column blank, as the 13 existing rows do. Region is read from the
  disc image filename: "USA, Europe" for Tony Hawk's Underground 2, "Europe" for
  Scooby-Doo! Unmasked and Shadow of Memories, and "?" for the four whose
  filename names none.
- `docs/COMPATIBILITY.md`, `docs/compatibility.csv`: regenerated. The summary
  line reads "57 Playable · 15 run below 30 fps · 11 not playable"; the other
  changes are the seven table rows and the Last updated date.
- `README.md`: the two "52 Playable" counts become 57.

## Inputs

- Ledger: `pm/playable-accepted.tsv`, 57 data rows.
- Registry: `docs/lanes/compatrefresh1013/registry.tsv`, built 2026-10-13
  11:26 PDT with `title_registry.py build --no-forge`: PLAYABLE 57, BELOW_BAR 64,
  CRASH_OR_HANG 15.
- `compat_page.py --check` against those inputs: up to date.
- `docs/testing/compat_page_selftest.py`: 19 tests, OK.

Release note (docs): The compatibility page and the README now list 57 Playable games, adding Tony Hawk's Underground 2, Scooby-Doo! Unmasked, Shadow of Memories, Tony Hawk's Pro Skater 4 and 25 to Life; Aeon Flux and Half-Life 2 are listed as running below 30 fps.
