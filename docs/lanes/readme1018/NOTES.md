# readme1018 (#433, README Highlights: drop GTA III/VC, name TimeSplitters 2, Shaolin Monks, Burnout Revenge; add two fix bullets)

## Step 0: Already-tried table

Read `docs/lanes/compat1018c/NOTES.md` (the RalliSport Challenge + Shaolin
Monks Playable promotion that just folded on master; it touched
`COMPATIBILITY.md`/`compat_notes.tsv`/`targets.toml`, explicitly left
README.md alone because the "92 Playable" line there has carried no number
since the 10-16 switch to the numberless form, and found no stale "92"
anywhere else), `docs/lanes/docsrewrite1012/PR.md` (how README.md's current
shape was written: Highlights first, a fixed sentence structure per bullet,
a `_Last updated <date>, for version <ver>._` line, and `home_page.py`'s
`readme()` function treats the Playable count line and the Compatibility
table row as the only two patterns it rewrites when generating the `home`
branch) and `home_page.py` `readme()` (lines 96-118): it does two regex
substitutions on master's README.md text --
(1) the `**Games rated Playable so far:** [the list, with progress
charts](.../blob/home/STATUS.md).` sentence, replaced with the numbered
`**N games rated Playable so far.** [The list, with progress charts.]
(STATUS.md)` form; (2) a `\| \[Compatibility\](` row, which gets a `| [Status]
(STATUS.md) | ... |` row inserted before it. Each pattern must match
exactly once or the function raises `RuntimeError`. Neither pattern touches
the Highlights section or any other bullet, so adding/removing bullet text
there cannot break the home-branch rewrite.

| Column | Source used this session | Confirmed |
|---|---|---|
| Three titles are Playable | `pm/playable-accepted.tsv` | `grep -iE "TimeSplitters 2\|Shaolin Monks\|Burnout Revenge"` against the ledger: TimeSplitters 2 (2026-10-13), Burnout Revenge (2026-10-13), Mortal Kombat: Shaolin Monks (2026-10-18) all present with accepted verdicts |
| Crimson Skies intro-skip crash fix | `docs/releases/v0.4.0-j1.md` lines 97-100 | "Skipping the intro video closed the emulator... the renderer now binds a blank texture for it instead of aborting." Used as the factual basis for the bullet; the bullet itself names no date/version per the brief |
| RalliSport Challenge flicker fix | `docs/releases/v0.5.2.md` line 72 | "rival cars no longer vanish on alternate frames during the countdown and close passes." `compat1018c`'s NOTES.md also independently confirms the owner-play verdict (10-18) citing "Car flicker (#804) fixed." |
| README.md's "92 Playable" line is numberless | re-read README.md line 15 directly in this worktree | `**Games rated Playable so far:**` with no digit -- confirms `compat1018c`'s finding still holds here; this lane does not touch it either (brief step 3) |
| `home_page.py` only matches two patterns, not the Highlights bullets | read `readme()` source, lines 96-118 | regexes target only the count sentence and the `| [Compatibility](` table row; no risk to Highlights/fix-bullet edits |

Stop rule: no generator run yet this session (none needed before this
table); `title_registry.py check --pages` and the `home_page.py` rewrite
dry run happen once, after the edit, per step 3.

`Selftest: none -- this lane edits README.md prose only; no selftest.d
fragment reads README.md's Highlights bullets (home_page.py's own checks
are run by hand below, not via selftest.d), and compat_page_selftest.py
(compat1018c's generator test) is unaffected since this lane does not touch
COMPATIBILITY.md, compat_notes.tsv or targets.toml.`
