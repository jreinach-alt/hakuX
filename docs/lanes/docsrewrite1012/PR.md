# docsrewrite1012: the public docs rewritten for players, each with a Last updated line (#433, 0.5)

State: ready

Lane: docsrewrite1012          Issue: #433
Base: master @ dd5e3cb3c6
Files: README.md, KNOWN_ISSUES.md, ROADMAP.md, CONTRIBUTING.md, PRIVACY.md, docs/reporting-bugs.md, docs/es-de/README.md, docs/releases/README.md, android/README.md, android/MIGRATING.md, docs/lanes/docsrewrite1012/**
Prediction: none (docs only)
Needs device: no    Needs NDK: no

## What this is

The owner (10-12): the README is verbose, leaks process notes, and does not
speak to someone deciding whether to try this build on a handheld. The pages it
links to have the same problems. They also date from the early pgraph work and
carry no timestamp, so the only way to judge their age is from the prose.

Every public doc except docs/COMPATIBILITY.md (compatpage1012) is rewritten for
that reader:

| Page | Now |
|---|---|
| README.md | Highlights first (52 Playable, save states, less shader stutter, several games folders, ES-DE), then device support, what you need, getting started, good to know, links, credits |
| KNOWN_ISSUES.md | Games, audio, setup and storage, and where to report. Only problems a player can hit. |
| ROADMAP.md | The goal for 1.0, what is coming along the way, and what is not planned |
| CONTRIBUTING.md | Lineage, the toolchain, Android and desktop builds, testing games, pull requests |
| PRIVACY.md | What stays on the device, the two times the app goes online (box art, which is opt-in, and Insignia), other builds |
| docs/reporting-bugs.md | Which form to use, what to include, the two builds and their package names, and how to take a log and a graphics capture |
| docs/es-de/README.md | Install, merging with existing custom files, removal, and why the find rule names the full activity |
| docs/releases/README.md | A version table and a note on Debug Capture in release builds |
| android/README.md | The toolchain (including meson and ninja, which fail late when missing), build commands, signing, SDL2 |
| android/MIGRATING.md | Moving saves from the official app, with or without a computer, and why to copy the EEPROM too |

The development history is gone, along with the agent and harness notes and
the long explanations. Facts were checked against the tree where a page states
one: the toolchain versions, package and launcher names, settings paths, the
ES-DE activity, and the HDD skip-copy behaviour in xemu_android.cpp.

## Date lines

Each page carries `_Last updated <date>, for version 0.5.0._` as the first
line after its title. docsfresh1012's `docs_freshness.py`, taken from its
branch and run against this worktree on 2026-10-13 00:1x PDT:

```
OK           README.md                        2026-10-12   0.5.0      (1 d)
OK           KNOWN_ISSUES.md                  2026-10-12   0.5.0      (1 d)
OK           ROADMAP.md                       2026-10-12   0.5.0      (1 d)
OK           CONTRIBUTING.md                  2026-10-13   0.5.0      (0 d)
OK           PRIVACY.md                       2026-10-13   0.5.0      (0 d)
MISSING-LINE docs/COMPATIBILITY.md            -            -          (None d)
OK           docs/reporting-bugs.md           2026-10-13   0.5.0      (0 d)
OK           docs/es-de/README.md             2026-10-13   0.5.0      (0 d)
OK           docs/releases/README.md          2026-10-13   0.5.0      (0 d)
OK           android/README.md                2026-10-13   0.5.0      (0 d)
OK           android/MIGRATING.md             2026-10-13   0.5.0      (0 d)
```

docs/COMPATIBILITY.md gets its line when compatpage1012 folds. Until then the
hourly alarm from docsfresh1012 would report it, so that alarm is installed
only after both have folded.

## Left as they are

- Two code comments cite sections of the old pages:
  - `docs/testing/driver_ab.sh:7` and `_driver_ab_verdict.py:2` cite "ROADMAP.md section 3";
  - `HakuXApplication.kt:30` cites "KNOWN_ISSUES.md".
  
  They are comments only, so nothing reads them as data.
- Three open questions for the owner, which would change these pages:
  - a screenshot row in the README;
  - stray upstream files at the repository root;
  - naming the Turnip driver on the compatibility page.

Release note (docs): The README and every linked guide are rewritten, and each now shows when it was last updated.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

https://claude.ai/code/session_01QjK9KDoS6St9aU1269xDrG
