# compat1018b (#433 Part 4, #1049)

## Step 0: Already-tried table

Read `docs/lanes/compat1017b/NOTES.md` (Mortal Kombat: Deadly Alliance removed
after an owner reversal: the splice-by-explicit-index method, the row-ordering
CRLF pitfall, and "file a board request instead of hand-editing
territory.toml/nv2a_issues.toml") and `docs/lanes/compat1017/NOTES.md` (31-title
bulk add: the column-filling convention below, the BELOW_BAR expansion the
generator can demand on its own, and the README numberless-line history).

| Column | Source used this session | Confirmed |
|---|---|---|
| `section` | changed `playable` -> `below_bar` for both GTA rows | brief's own instruction |
| `region`/`region_source`/`device`/`tested` | left as already filled (the on-foot confirmation run's own values) | unchanged from the existing row, still correct: `tested` is the date of the real reviewed run |
| `fps_median`/`time_at_bar`/`gameplay_s` | **blanked**, not copied from the registry or kept from the old playable row | see "Why the fps columns are blank" below -- a deliberate departure from the pure "copy the registry/ledger numbers" convention `compat1017`/`compat1017b` used, because here the measured numbers are honest but describe a different scene than the one the row is about |
| `notes` | free text per the brief's exact instruction ("it plays, but drops into the teens...#1049"), nothing else | — |

Stop rule honored: no generator failure repeated twice for the same cause (the
`below_bar_qualifies()` gap below was identified by reading the generator before
editing `compat_notes.tsv` a second time, not by a second raised SystemExit for
the same reason).

## The core finding: a generator gap between an owner hold and the automatic fps gate

`docs/testing/compat_page.py`'s `below_bar_qualifies()` only admits a BELOW_BAR
registry row to the public page when `failing_all == "fps"` -- a tag the
generator's own comment says exists because "any other tag... means gameplay
was not cleanly confirmed." That tag is set only by the *automatic* path in
`title_registry.py` (`latest scored verdict ... fails ...`), not by the
*manual* `hold <id>` path (`elif any(h["kind"] == "below_bar" for h in
active)`).

GTA III (`5454000E`) and GTA: Vice City (`5454000F`) are BELOW_BAR in
`pm/title-registry.tsv` **only** via the manual hold path (`status_rule = "hold
gta3-driving-below-bar"` / `"hold gtavc-driving-below-bar"`), with
`failing_all` empty for both. This is because their last *scored* run is the
10-12 on-foot confirmation PASS (fps_ok 0.9798/0.9814 per the registry's
`latest_verdict`, matching the 0.9967/0.9872 already in `compat_notes.tsv`
from the original ledger citation) -- it never failed any gate. The owner's
"drops into the teens while driving" finding (memory
`gta3-blinx-fps-results-1018`: a 10-18 A/B held-RT-state investigation showing
18.7-26.0 fps while driving) is real but comes from a diagnostic run, not a
scored harness verdict, so it never set `failing_all`.

Tried the straightforward fix first (just moving the rows to `section =
below_bar` in `compat_notes.tsv`) and confirmed by reading the generator
(not by running it to find out) that `build_below_bar_rows()`'s stale check
would reject it: `qualifying` only contains rows where `below_bar_qualifies()`
is true, and a `below_bar` notes row whose `title_id` isn't in `qualifying_ids`
raises `SystemExit` ("...lists below_bar titles that no longer qualify").

**Considered and rejected**: broadening `below_bar_qualifies()` to accept
*any* hold-based BELOW_BAR row. Checked `pm/owner-holds.tsv`'s other
`kind=below_bar` holds against the registry first (`doa1u-window-scoring`,
`crashwoc-route`, `celdamage-never-drove`, `arx-never-drove`,
`gun-load-hang`, `guiyi-hold-opens-shop`, `puyopop-route`,
`pop-menu-sitting`, `avatar-stuck-at-wall`, `ngb-below-bar`, and others):
several of these are route/stuck/menu problems with `failing_all` empty too,
and are correctly absent from today's public page. A blanket "any hold
qualifies" change would have surfaced those as if they were clean
below-the-fps-bar titles, which they are not -- a real regression, caught by
reading the registry before writing the fix, not after.

**Fix applied**: `compat_page.py` gets a `BELOW_BAR_OVERRIDES` dict, the same
shape and purpose as the file's existing `RED_OVERRIDES` (used for
`not_playable`/CRASH_OR_HANG rows whose own evidence trips a left-off shape
but a human review settles otherwise) -- keyed by title_id, one entry each for
`5454000E`/`5454000F`, with the reason recorded in the source so a registry
rebuild can't silently re-flag it. `below_bar_qualifies()` now accepts
`failing_all == "fps"` **or** a `BELOW_BAR_OVERRIDES` title_id. Added two
tests to `compat_page_selftest.py`'s `BuildBelowBarRows` class mirroring the
existing `RED_OVERRIDES` test in `BuildNotPlayableRows`: one proving the two
real title_ids are in the table and qualify, one proving an *unlisted*
hold-only BELOW_BAR title still raises (so the override stays narrow).

## Why the fps columns are blank, not copied

The rendered below_bar table would otherwise show `30.0 / 100%` (GTA III) and
`30.0 / 99%` (VC) next to a note that says the title drops into the teens --
numbers that are real (the on-foot confirmation run) but describe a scene the
whole row isn't about, flatly contradicting the "below 30 fps" classification
sitting next to them. Checked a representative true below_bar row (NHL 2K3,
`53450017`: 35.0 median / 69% at bar) to confirm the shape readers expect is
"a real, low number," not "a real number that happens not to apply here."
Per the "never invent a number" rule from `compat1017`'s notes, the honest
move is neither inventing a driving-specific median (the only driving numbers
on record are unscored A/B telemetry, not a harness verdict) nor publishing a
number that actively misleads -- so `fps_median`/`time_at_bar`/`gameplay_s`
are left blank (an established pattern elsewhere in this file, e.g. ATV Quad
Power Racing 2's blank `fps_median`) and the notes field carries the whole
story, exactly as the brief specified it.

## The Playable count: 92, not the brief's anticipated 93 -- a third, unrelated drop

The brief expected "Playable comes out 93" (95 - the 2 GTA titles). The live
figures disagree with that, and agree with each other:

- `pm/playable-accepted.tsv`: 92 data rows (header excluded), already missing
  GTA III and VC (moved to `pm/ledger-held-1018.tsv` before this lane
  started, per the brief).
- `pm/title-registry.tsv`'s own PLAYABLE count (what
  `title_registry.py check --pages` compares every page against): 92.
- This lane's regenerated `docs/COMPATIBILITY.md`/`compatibility.csv`: 92.

All three agree at 92, not the predicted 93, because a **third** title,
**Mortal Kombat: Shaolin Monks** (`4D570029`), dropped out of the ledger
between when the brief was written and this session -- unrelated to #1049,
caused by the just-folded `pathfind` lane's run landing a new scored verdict
that fails `fps+hitch` (registry: `status=BELOW_BAR`,
`status_rule="latest scored verdict .../shaolin-1006 fails fps+hitch"`).
Because it fails more than just `fps`, `below_bar_qualifies()` correctly
leaves it off every section (not playable, not below_bar, not not_playable) --
it is simply absent from the page now, same as any other "gameplay not
cleanly confirmed" title.

**This lane did not touch `compat_notes.tsv`'s stale `playable` row for Mortal
Kombat: Shaolin Monks** (line ~91): it is now an inert orphan (no ledger row
points to it, so the generator silently ignores it; confirmed harmless by
running `--check`, the selftest, and `title_registry.py check --pages`, all
of which pass with it present). Fixing it is a separate compatibility
regression, not named in this lane's brief (#1049 names only the two GTA
titles) and not something this lane should decide unilaterally -- **flagging
to lane.local**: Mortal Kombat: Shaolin Monks has silently fallen off the
Playable list (3rd title, not 2nd) and may need its own hold row / board
item, the same way GTA did.

## `title_registry.py check --pages`: 2 of 4 pages fixed, 2 are other actors' files

Ran `python3 docs/testing/title_registry.py check --root /home/justin/hakux-work --pages`
(this worktree has no `pm/`, `status/`, or Wall sync files -- they live only in
the main checkout, hence `--root`):

- `COMPATIBILITY.md (header)` and `(table rows)`: **now match** the registry's
  table count (92) -- this lane's fix.
- `status page` (94) and `Wall` (93): still stale against the table (92).
  Neither `status/index.html` nor the Wall sync file is in this lane's `Files:`
  list (and neither exists in this worktree at all -- confirmed, not just
  assumed). Not this lane's defect to fix, same pattern as `compat1017`'s
  filed territory/coverage preflight failures.
- The registry itself reports STALE (`sources changed since it was built`):
  pre-existing, a shared/generated file this lane does not rebuild.

## Step 4: `targets.toml` -- nothing to change

Checked both title blocks (`[titles."5454000E"]` line 369,
`[titles."5454000F"]` line 375): both `notes` fields are route-proving
technical writeups ("Route pathfound and proved on the Nova (golden
...): gameplay=...s, fps_ok=...") from `lane.gtaroutes1011`, not a
Playable/confirmed status claim -- no "Playable" or "confirmed" wording
anywhere in either. Left untouched, same outcome as `compat1017b`'s check of
Dead or Alive 3 and Mortal Kombat: Deadly Alliance's `targets.toml` entries.

## Step 5: other stale references

`grep -rln` across `docs/` and `README.md` for "95 Playable"/"95 games" and
for the two titles by name:

- No "95" count anywhere remains (README.md already carries the numberless
  Playable line from the 10-16 switch; nothing else in scope had a number).
- `docs/HISTORY.md` line 154 (`10-12 | 0.5.0: GTA III, GTA Vice City, and
  Grabbed by the Ghoulies after an 1,800-second soak | 52`) names both
  titles, but it is a dated changelog entry reporting what was true that day,
  the same kind of dated record `docs/releases/` is -- not in this lane's
  `Files:` list, left untouched.
- `docs/testing/titles/pathknow/**` (hints, families.md, paths/5454000E.json)
  and `docs/testing/titles/routes/gta-3.route` / `gta-vc.route`: pathfinding
  mechanics only, no Playable-status language (checked by grep -i playable,
  zero hits).
- `docs/testing/selftest_title_locations.py`: a different, fabricated
  title_id pair (`41430002`/`45560029`) used as fixture data for an unrelated
  file-location test -- not the real titles, not touched.
- `docs/lanes/*` (gtaroutes1011, gta3fps1017, gta3fps1017b, gtawedge1012,
  compatpage1012, compatrefresh1013, bootstatic1017, x1port1012): dated lane
  records of past work, same category as `docs/releases/`, not edited.
- No Reddit/announcement draft naming either title was found anywhere under
  `docs/` (`find -iname "*reddit*" -o -iname "*announce*" -o -iname
  "*draft*"` outside `docs/lanes/`: two unrelated hits, a selftest script and
  a route file, neither mentions GTA).
- `docs/releases/*.md`: checked, zero mentions of either title.

## Verification

- `python3 docs/testing/compat_page.py --ledger /home/justin/hakux-work/pm/playable-accepted.tsv --registry /home/justin/hakux-work/pm/title-registry.tsv --notes docs/testing/compat_notes.tsv`: 92 playable / 20 below_bar / 11 not_playable.
- `... --check`: up to date.
- `python3 docs/testing/compat_page_selftest.py`: 21 tests (19 existing + 2 new), OK.
- `python3 docs/testing/title_registry.py check --root /home/justin/hakux-work --pages`: COMPATIBILITY.md header and table rows both match the table (92); status page and Wall remain stale on files outside this lane (see above); registry staleness is pre-existing/shared.

## Selftest

No `selftest.d` fragment reads `compat_notes.tsv`, `compat_page.py`,
`targets.toml`, `COMPATIBILITY.md` or README's Playable line;
`compat_page_selftest.py` is the compat page's own unittest file, not a
`selftest.d` fragment, and the fold only runs named fragments.
`Selftest: none -- compat_page_selftest.py is not a selftest.d fragment`.
