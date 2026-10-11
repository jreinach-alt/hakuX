# lane.nfsroute1011 -- NFS Most Wanted: routes that check the screen, and a saved profile

Issue: none (#433 umbrella, dispatched directly by lane.local).
Base: master @ 6d8947bb47.

## Step 0: base

Read in full: `docs/testing/titles/route.sh`, `titlestate.py`'s module docstring,
`dispatcher.sh`'s `titles_first_run_golden()` (~line 884-900), `castlevania-cod.first-run.route`,
`pgr.first-run.route`, `burnout3.first-run.route`.

### press RIGHT vs axis HATX: NOT the same input

`docs/testing/perf/pad.sh` sends two unrelated evdev paths:

- `press UP/DOWN/LEFT/RIGHT` looks up `BTN[UP]` etc (544-547, `BTN_DPAD_*`) and calls `key()`,
  an `EV_KEY` event.
- `axis HATX/HATY` resolves to `ABS_HAT0X`/`ABS_HAT0Y` (codes 16/17) and calls `axis()`, an
  `EV_ABS` event via `sendevent $DEV 3 $code $val`.

These are different device axes/keys as far as evdev is concerned, and whether a game reads one,
the other, or neither is a per-title fact, not a route.sh fact.

`docs/lanes/titleroutes/NOTES.md` (pre-existing, cross-title) records that in GoldenEye: Rogue
Agent, Midnight Club 3, and 187: Ride or Die, **the D-pad buttons do nothing in any menu or
keyboard tested** -- those titles read the hat axis or the left stick instead.
`burnout3.first-run.route`'s header independently reaches the same conclusion ("UP is the left
stick pushed and released, not the D-pad... whether the Thor's pad reports its D-pad as keys or
as a hat has not been checked").

nfs-mw-quickrace.route already uses `axis HATX`/`axis HATY` exclusively (no `press RIGHT` et al
anywhere in the file), and its own good runs (`3581025`, `3581205`) show it working: `mm-quickrace`
in `3581025` shows Quick Race correctly highlighted after exactly two `axis HATX max`/`mid` taps.
**Conclusion: NFS MW reads the hat axis, not BTN_DPAD_*.** Step 2 keeps `axis HATX/HATY`, adding a
hold, rather than switching to `press RIGHT`-style input.

### Good vs bad runs, frame by frame

Compared `s04`-`s12`/`mm-quickrace` across the two good runs (`1-1791735965-nfsdefault1011-3581025`,
`1-1791735970-nfsdefault1011-3581205`) and the two voided runs
(`1-1791741306-nfsdefault1011-87778`, `1-1791741301-nfsdefault1011-87617`).

**Good run (`3581025`) sequence, confirmed from frames:**
- s04 alias prompt (No/Yes, No default) -> s05/s06 autosave notices (OK only) -> s07 name
  keyboard, cursor starts on **A**, NAME empty -> ... -> s08 "save alias NAME?" (No/Yes, No
  default) -> s09/s10/s11 are the **same** "The autosave feature has been disabled" OK screen,
  three times in a row. This matches the route's own step comments: step 9's `press B` and step
  10's `press START` are documented as doing nothing on this notice ("B did nothing on this
  unchanged screen", "START and B already did noth[ing]") -- only step 11's `press A` dismisses
  it. So three near-identical frames in the good run are expected, not a sign of drift; a single
  reference crop for "autosave disabled OK" is reused for s09, s10 and s11 (same convention the
  route already plans to reuse for the 11x restart-OK prompt in the race loop).
- s12 main menu: Career highlighted. `mm-quickrace`: Quick Race highlighted (two right taps
  landed).

**Bad run `87778`:** s04-s06 match the good run pixel-for-pixel. **s07 diverges**: cursor is on
**D**, not A, with NAME still empty, even though no route-sent input happens between s06's press
and the s07 screenshot other than a passive `wait` -- run.log timing is within ~100ms of the good
run at every step through s07, and neither log has a `pad.sh ... failed` line. s12 main menu still
shows Career highlighted (both right taps at s12 were lost, confirming the brief). `mm-quickrace`
still shows Career. The subsequent A press (meant for Quick Race) started Career instead, which is
why `go4`/`s1-g11` show the keyboard being typed into at 59 fps: the run fell back into character
creation.

**Bad run `87617`:** s07 also diverges the same way (cursor off A, several cells in). The frame
labelled `s11-save_load_prompt` in this run's capture set shows the **"Do you want to save the
alias NAME?" No/Yes prompt** -- the good run's s08 content, not s11's. The frame labelled
`s12-main_menu` shows the **"autosave feature has been disabled" OK dialog** -- the good run's
s09/s10/s11 content, not the main menu. So this run's screen sequence is running roughly
2-3 steps behind its own shot labels: the fixed-wait route fired a shot step before the
corresponding screen had actually arrived, and every later shot through `cr-auto`/`s1-g11`
diverges further, ending on attract-mode footage (confirmed earlier: `cr-auto` and `s1-g11` are a
street scene with traffic, 23-29 fps -- no car-select or race HUD at all).

**Reading:** both void runs diverge first at s07 (the name keyboard), in the same direction (cursor
further from A than expected, name field still empty) -- consistent with the d-pad-tap-drop cause:
the keyboard navigation before step 7's `press A` is four `axis HATY` taps and two `axis HATX`
taps, all zero-hold, and the keyboard is the single screen in the route with the most taps packed
together. Once the keyboard's own state is off from what the fixed waits assume, every later
press in the route is blind and compounds the drift -- exactly cause #3 (no step reads the screen).
This is why Step 2 gates every screen-dependent press with `waitfor`, not just the d-pad holds:
holding longer fixes dropped taps, but only a screen check catches a run that drifts anyway.

### Reference-crop sizing/orientation check (for Step 1)

Full device screencaps used by route.sh's `shot`/`mark`/`waitfor_step` are 1280x960 PNG (confirmed
via PIL `Image.open().size` on both good- and bad-run frames above). `castlevania-cod.first-run`'s
existing refs (`name-entry-header.png` 490x85, `name-field-empty.png` 120x70) are pre-cropped to
exactly their region's `w x h`, matching `waitfor_match.py`'s `region_score()`, which crops the
*frame* to the region but uses the ref image at its native size (both are then resized to the
fixed `CMP_SIZE = (64, 48)` for scoring). Crops cut from the dispatcher `route-frames/*.png` files
used in this analysis are the same 1280x960 orientation route.sh captures, so no resize/orientation
fix is needed before cutting Step 1's reference crops.
