# compat1019b (#433, Playable 94 -> 97: Pro Evolution Soccer 5 (Europe), The Wild Rings, Knights of the Temple II)

## Step 0: Already-tried table

Read `docs/lanes/compat1018c/NOTES.md` (RalliSport Challenge + Mortal Kombat:
Shaolin Monks add: the `title_id`-only join in `build_playable_rows()`, the
precedent of using the brief's own figures rather than a stale registry
pointer, the CRLF-preserving splice method, and the `title_registry.py check
--pages` scope split -- fix `COMPATIBILITY.md`/README, leave `status/index.html`
and the Wall to other actors) and `docs/lanes/compat1018b/NOTES.md` (GTA
III/VC demotion: the `BELOW_BAR_OVERRIDES` pattern, the "blank the fps
columns rather than publish a number that describes a different scene"
rule -- not needed here, since all three new figures describe exactly the
scene the row is about -- and the precedent for what counts as a stale
`targets.toml` claim).

Unlike both predecessors, the ledger (`pm/playable-accepted.tsv`) and
registry (`pm/title-registry.tsv`) are **not stale** against this session:
both already carry the 2026-10-19 entries for all three titles with current
numeric columns (confirmed by grepping both files for all three title_ids
before writing anything), so there is no registry/ledger numeric
disagreement to resolve this round -- a first for this lane sequence.

| Column | Source used this session | Confirmed |
|---|---|---|
| `title_id` join | `compat_page.py`'s `build_playable_rows()` joins the ledger to `compat_notes.tsv` by `title_id` only | grepped `pm/playable-accepted.tsv` for all three IDs first: all present, dated 2026-10-19 08:50/08:51/08:52 |
| `fps_median`/`time_at_bar` | the brief's own figures (median/fps_ok share), which match the registry's own numeric columns exactly for all three (registry is current, not stale this round) | cross-checked `pm/title-registry.tsv` lines 491/586/771 against the brief before writing: `fps_ok`=1/1/1, `fps_window_median`=59.94/53.29/29.97 -- identical to the brief |
| `gameplay_s` | the **in-play** figure (659.9 / 454.1 / 438.3 s), not the **scored** window length (710.3 / 610.3 / 598.7 s) | established by cross-checking existing rows against the registry's own column order: Micro Machines' `gameplay_s` (672.9) and Burnout 3: Takedown's (634.9, a `below_bar` row with a non-1.0 play share) both match the registry's `play_s` column exactly, not a `scored`/`play_s` ambiguity -- confirmed before writing, not guessed |
| `region`/`region_source` | Pro Evolution Soccer 5 (Europe): `Europe`/`filename`, matching every other title whose name itself carries a `(Europe)`/`(USA)` suffix (Micro Machines (Europe), Lemony Snicket's ... (USA), X-Men: The Official Game (Europe), etc.). The Wild Rings and Knights of the Temple II: `?`/`none` -- no parenthetical region in either title and no local copy to check (`ls /mnt/d/hakux-staging/xiso \| grep -i wild` / `\| grep -i knights`: no hits) | same "no evidence, stays `?`/`none`" precedent `compat1017c`/`compat1018c` used |
| `notes` | left blank for all three | none of the three is a technical fix note like RalliSport's "Car flicker (#804) fixed."; the brief's "notes say what is true and nothing more; no process commentary, no owner quotes" rules out narrating the owner's play-share/length rulings in this column -- that story already lives in the ledger row and PR body, and the page's own `DEFINITIONS` text already covers the general shape ("A few titles were rated by a person playing them rather than by the timed run alone") |

Stop rule honored: no generator failure repeated twice for the same cause
(zero `SystemExit`s hit; the `gameplay_s` ambiguity above was resolved by
reading existing rows against the registry before writing, not by running
`--check` twice for the same reason).

## `compat_notes.tsv` edit

All three are brand-new rows (none of the three title_ids had any existing
`compat_notes.tsv` row in any section -- confirmed by grep before editing),
spliced in with a small Python script that splits the file on `\n` only
(preserving each line's own `\r`), after confirming the splice region
(lines 91-98, now 91-101) is CRLF-only end to end (no LF-only lines in that
range, unlike the known LF-only lines elsewhere in the file noted by
`compat1018c`). Inserted after the last `playable` row (RalliSport
Challenge, was line 95) and before the `below_bar` section start (was line
96), same method `compat1018c` and `compat1017c` used.

## Step 2: generator output

```
python3 docs/testing/compat_page.py --ledger /home/justin/hakux-work/pm/playable-accepted.tsv \
  --registry /home/justin/hakux-work/pm/title-registry.tsv --notes docs/testing/compat_notes.tsv
```

wrote `docs/COMPATIBILITY.md` / `docs/compatibility.csv` with **97
Playable** (up from 94), 20 below_bar, 11 not_playable -- matches the
brief's expectation exactly, all three new rows picked up from the ledger
with no `SystemExit`. Ledger, registry and generator all agree at 97 (the
registry's own `status=PLAYABLE` rows for all three already cite the same
2026-10-19 ledger entries used here).

- `--check`: up to date.
- `python3 docs/testing/compat_page_selftest.py`: 21 tests, OK -- no change
  needed to `compat_page.py` or its selftest; this promotion needed no new
  generator rule (no `BELOW_BAR_OVERRIDES`-style gap, unlike `compat1018b`).

## Step 3: `title_registry.py check --pages`

```
python3 docs/testing/title_registry.py check --root /home/justin/hakux-work --pages
```

exit 3:

- `README.md`: numberless Playable line -- **nothing to fix**. Checked for
  any other "94" anywhere in README.md first (`grep -n 94`: zero hits): the
  numberless form has carried no number since the 10-16 switch
  (`compat1018b`'s precedent), so step 3's "94 -> 97" instruction has no
  live target in this file this round.
- `COMPATIBILITY.md` (header) and (table rows): both **match** the table
  (97) -- this lane's fix.
- `Wall`: **matches** (97) -- already current (the brief says lane.local
  "republished the Wall (v94)"; whatever that version label means, the
  Wall's own Playable count the checker reads is 97, not stale). Not
  touched (not in this lane's `Files:`, and already correct).
- `status page`: **94**, stale against the table (97). `status/index.html`
  lives outside this repo (`DEFAULT_ROOT`) and outside this lane's
  `Files:`; same gap every compat* lane before this one has hit and left to
  the next rebuild of that external artifact.
- registry itself: `STALE (sources changed since it was built)` --
  pre-existing, a shared/generated file this lane does not rebuild.

## Step 4: `targets.toml` -- nothing to change

None of the three titles has a block in `targets.toml` at all (confirmed by
grep on all three title_ids and all three title names: zero hits, not even
a differently-titled near-match the way `compat1018c` found "RalliSport
Challenge 2" for RalliSport Challenge). Nothing to fix.

## Step 5: other stale references

`grep -rln "Pro Evolution Soccer 5\|4B4E0030\|Wild Rings\|4D530048\|Knights
of the Temple\|544D0013" docs/ README.md`, plus a separate `grep -rn "94
Playable\|94 games"`:

- No stale "94 Playable"/"94 games" count anywhere outside
  `docs/lanes/compat1018c/PR.md`'s own frozen "92 -> 94 Playable" line, a
  dated record of that lane's own PR body, not a live status claim, not
  touched.
- `docs/testing/titles/pathknow/hints/learned-pub-544D.md` and
  `docs/testing/titles/pathknow/paths/544D0013.json`: pathfinding mechanics
  only (checked `grep -i "playable\|excluded\|held\|unscreened\|below the
  bar"`: zero hits), same outcome `compat1018b`/`compat1018c` found for
  other pathknow files. Left untouched.
- `docs/lanes/pathfind/below-bar.tsv` line 70: lists Knights of the Temple
  II with `fps_ok_share=1.0000` -- despite the filename, this is the
  pathfind lane's own per-title route-verdict tracking table (every routed
  title appears here regardless of whether it passed), not a
  Playable/held status claim; its own header confirms the columns are
  `title / title_id / fps_ok_share / verdict / judged_utc / cause /
  fix_commit`, no status field. Not in this lane's `Files:`, left
  untouched.
- `docs/lanes/compatpage1012/registry.tsv` and
  `docs/lanes/compatrefresh1013/registry.tsv`: frozen registry snapshots
  from those lanes' own sessions (10-12/10-13), correctly showing The Wild
  Rings and Knights of the Temple II as `UNSCREENED` **as of those dates**
  -- a dated historical record, same category as `docs/releases/`, not
  touched. Pro Evolution Soccer 5 does not appear in either snapshot at
  all (not yet in the registry on those dates).
- `docs/HISTORY.md` and `docs/releases/*.md`: zero mentions of any of the
  three titles.

## Verification

- `python3 docs/testing/compat_page.py --ledger /home/justin/hakux-work/pm/playable-accepted.tsv --registry /home/justin/hakux-work/pm/title-registry.tsv --notes docs/testing/compat_notes.tsv`: 97 playable / 20 below_bar / 11 not_playable.
- `... --check`: up to date.
- `python3 docs/testing/compat_page_selftest.py`: 21 tests, OK.
- `python3 docs/testing/title_registry.py check --root /home/justin/hakux-work --pages`: exit 3 -- README.md, COMPATIBILITY.md (header, table rows) and Wall all match (97); status page (94) and registry staleness are pre-existing gaps outside this lane's `Files:` (see Step 3 above).
- `bash docs/testing/preflight.sh`: passed -- territory ok, coverage ok, board files ok.
- `python3 -c "import tomllib; tomllib.load(open('docs/testing/titles/targets.toml','rb'))"`: parses, 106 titles (unchanged).

## Selftest

No `selftest.d` fragment reads `compat_notes.tsv`, `targets.toml`,
`COMPATIBILITY.md` or `compatibility.csv`; `compat_page_selftest.py` is the
compat page's own unittest file, not a `selftest.d` fragment, and the fold
only runs named fragments. `Selftest: none -- compat_page_selftest.py is
not a selftest.d fragment`.
