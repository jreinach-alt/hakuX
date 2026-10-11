# lane.profileconv1011 -- gta-sa and amped2 measure on their golden profiles (#433)

## 1. Base

Branched from `origin/master` @ `6d8947bb47` (fastpaths1010 fold); already at
tip, no merge needed.

## 2. Why compose() strips both routes' goldens today

`titlestate.py compose(device, title_id, state)` (docs/testing/titles/titlestate.py:841):
every title's golden is composed onto the run's disk, EXCEPT the run's own
title's when `state == "first-run"` (`want.pop(dt, None)`, line 862). Both
routes' headers declare `# state: first-run`, so each run's own golden is the
one thing stripped from its own disk -- the one case that matters.

`resolve_route()` only refuses a `first-run` route when none exists for the
title (the family-resolution branch, `any` being a request-level override of
that choice). It never refuses a `first-run` route for CARRYING a golden --
first-run always matches by construction (the disk is composed without that
title's save). So nothing was wrong that needed a gate; the routes were just
declaring the wrong state for what they have now.

`SETTINGS_ONLY_FIX` (titlestate.py:882): a golden with no save directory,
confirmed on it as-is, should be headed `# state: any` -- that loads the
golden unchanged (`compose()` only pops on `first-run`; `any` does not
reach either the pop or the `NoGolden` checks `returning` makes).

## 3. Both goldens, read from the store (read-only)

`titlestate.py golden --title-id <T> --json`:

| Title | TID | golden save | status | how | promoted |
|---|---|---|---|---|---|
| GTA San Andreas | 54540082 | `7da19befd45b` | golden | promote | 2026-10-03T03:46:18Z |
| Amped 2 | 4D530041 | `f90786b6e0f5` | golden | promote | 2026-10-03T03:46:16Z |

Both went `proposed` (lane.savestate433, the newest verified harvest) ->
`promote` (lane.local, "owner order 10-02: deterministic profiles") on
2026-10-03, same minute. Amped 2 also has a newer `latest` (`6c4ae083cae8`,
2026-10-10, run `1-...-pfifowait1009-333840`) that was never promoted -- the
golden is still `f90786b6e0f5`; untouched by this lane.

`saves/<TID>/<save>/save.json` entries, both titles, in full:

- GTA SA `54540082/7da19befd45b`: `UDATA/54540082` (dir), `TitleMeta.xbx` (56
  B), `TitleImage.xbx` (10240 B), `SaveImage.xbx` (18432 B) -- all three
  files directly under `UDATA/54540082`, no subdirectory -- plus an empty
  `TDATA/54540082` dir. No `UDATA/54540082/<slot>/` anywhere.
- Amped 2 `4D530041/f90786b6e0f5`: `UDATA/4D530041` (dir), `TitleMeta.xbx`
  (40 B), `TitleImage.xbx` (8224 B) -- no `SaveImage.xbx` -- plus an empty
  `TDATA/4D530041` dir. Same shape: no `UDATA/4D530041/<slot>/`.

`save_dirs()` (titlestate.py:776) looks for a path component AFTER
`UDATA/<TID>/`; neither golden has one, so both verify as "title data only,
no save directory" exactly as the brief states. `TitleMeta.xbx`/
`TitleImage.xbx` are the dashboard's tile metadata/icon; `SaveImage.xbx` is
normally a save SLOT's icon, but this one sits at the title root, not inside
a slot folder, so it carries no slot either -- just an extra icon asset next
to the title's own.

## 4. Prediction, before any run

**Both routes' "no menu" opening holds.** Both games' own save/continue logic
reads the slot subdirectory under `UDATA/<TID>/`, which neither golden has.
`TitleMeta.xbx`/`TitleImage.xbx` (and GTA SA's loose `SaveImage.xbx`) are
dashboard-tile assets the Xbox kernel's content-enumeration APIs read for the
*dashboard*, not files either game's own in-title save code scans -- a
title's save code looks for its own slot folder (and, inside it, its own
marker/save file), and finds nothing in either case: TDATA is empty, and
UDATA's only children under the title are the three/two loose files, not a
subdirectory.

- **GTA SA**: predict identical to today's first-run frames -- Rockstar
  logos -> intro FMV -> "Press START" -> ~55 s loading -> airport cutscene ->
  police-stop cutscene -> Jefferson alley, CJ on foot, HUD up (`boot`, `skA`,
  `menu`, `load`, `cut1`, `cut2`, `cut3`, `moved` shots unchanged). If this is
  wrong, the frame that would show it is `load`: a Load/Continue prompt in
  place of the ~30 s loading-screen capture, or a different cutscene order if
  the game treats the loose `SaveImage.xbx` as a corrupt/orphan save and
  detours through a "corrupted save" dialog instead.
- **Amped 2**: predict identical to today's first-run frames -- publisher
  logo -> two intro FMVs -> title "PRESS START" -> character select
  (`s05-submenu`) -> name-entry keyboard (`s06-name_entry`) -> main menu ->
  career flow -> gameplay. Amped 2's name-entry/profile-creation screen is
  part of its own new-profile flow regardless of dashboard tile data, so
  title data with no save should not skip or alter it. If wrong, the frame
  that would show it is `s06-name_entry`: that step missing (skipped straight
  to main menu) or showing a non-default existing name, would mean the game
  found something it is treating as an existing profile.

Settings differences (graphics options, audio) are not expected either: there
is no settings data in TDATA (empty dir) for either title, and `TitleMeta.xbx`
is dashboard metadata, not an in-game settings blob.

## 5. Re-headed routes (step 3)

Both routes' `# state:` changed `first-run` -> `any`; no step lines changed
(prediction above expects no divergence). Added one header line to each
naming the golden measured on and the date.
