# README Highlights: drop GTA III/VC from the Playable list, name TimeSplitters 2, Mortal Kombat: Shaolin Monks and Burnout Revenge, and add two fix bullets

State: ready

Lane: readme1018            Issue: #433
Base: master @ 3357b0e196
Files: README.md, docs/lanes/readme1018/**
Prediction: none: analysis-only (docs prose only, no device/perf claim)
Needs device: no    Needs NDK: no

## What changed

The home page's Highlights (README.md, generated onto the `home` branch by
`host-tools/home_page.py`) still named Grand Theft Auto III and Vice City as
Playable, after both were taken off every Playable surface (`compat1018b`,
#1058). The owner (2026-10-18) asked for the home page to catch up: drop
those two from the "Rated by play." bullet's named list and add three
titles that reached Playable since the page was last written --
TimeSplitters 2 and Burnout Revenge (both 2026-10-13), and Mortal Kombat:
Shaolin Monks (2026-10-18, confirmed by `compat1018c`'s promotion that
folded onto master just before this lane started). All three are on
`pm/playable-accepted.tsv` and the Playable wall.

Also added two fix bullets in the existing bold-lead style, after "Faster."
and before "Graphics checked against a real Xbox.":

- **Crimson Skies no longer crashes when skipping the intro video.** We
  know, you've already seen it. (fix: `docs/releases/v0.4.0-j1.md`)
- **RalliSport Challenge no longer flickers.** Rival cars stay on screen
  through the countdown and close passes. (fix: `docs/releases/v0.5.2.md`;
  owner play on the Nova 2026-10-18 confirmed it, per `compat1018c`'s
  NOTES.md)

Neither bullet names a date, version or issue number, per the brief.

The Playable count line (`**N games rated Playable so far.**`, numberless
on master since the 10-16 switch) and anything `compat1018c` changed
(`COMPATIBILITY.md`, `compat_notes.tsv`, `targets.toml`) are untouched.

## Verification

- `python3 docs/testing/title_registry.py check --root /home/justin/hakux-work --pages`:
  exit 3, but the only line about README.md reads `numberless Playable
  line, as home_page.py expects (home sets the count)` -- matched once, as
  before this lane. The exit code's other causes (registry staleness,
  external status-page lag) are pre-existing and outside this lane's
  `Files:`, same gaps `compat1018c` already documented.
- `home_page.py`'s `readme(text, 94)` run directly against the edited
  README.md (one-off Python snippet, not written to disk): both of its
  regex substitutions -- the Playable-count sentence and the
  `| [Compatibility](` table row -- matched exactly once each, no
  `RuntimeError`. Confirms the Highlights/fix-bullet edits do not collide
  with either pattern the home-branch generator rewrites.
- `bash docs/testing/preflight.sh`: passed.
- `git diff --stat` against base: `README.md` only, 7 insertions / 3
  deletions.

See `docs/lanes/readme1018/NOTES.md` for the Already-tried table and full
detail.

`Selftest: none -- README.md prose only; no selftest.d fragment reads the
Highlights bullets, and the generator checks above were run by hand (not
via selftest.d).`

🤖 Generated with [Claude Code](https://claude.com/claude-code)
