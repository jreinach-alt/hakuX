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

## Step 1: gates that tell good from bad

Crops cut from `1-1791735965-nfsdefault1011-3581025` (good run 1) into
`docs/testing/titles/routes/refs/nfs-mw-quickrace/`, each sized exactly to its box's `w x h`
(route.sh's `validate()` requires the ref file to exist; `waitfor_match.py` resizes both crop and
ref to a fixed 64x48 internally, so box/ref dimensions only need to match each other for the repo
convention, which these do). Scored with `waitfor_match.py`'s `region_score()` against: good run 1
(the source, always 0.00), good run 2 (`3581205`), and the two void runs (`87778`, `87617`) at the
matching shot filename -- which carries the route's step label regardless of what is actually on
screen, so e.g. bad run `mm-quickrace.png` is scored against the `mm-quickrace` ref even though it
shows a different screen.

| gate | box (x,y,w,h) | good1 | good2 | bad1 (87778) | bad2 (87617) | threshold | margin (good max / bad min) |
|---|---|---|---|---|---|---|---|
| alias-prompt | 160,195,970,460 | 0.00 | 0.01 | 0.01 | 0.00 | 5 | n/a -- see note below |
| autosave-notice1 | 160,195,970,460 | 0.00 | 0.14 | 0.48 | 0.17 | 5 | n/a -- see note below |
| autosave-notice2 | 160,195,970,460 | 0.00 | 0.55 | 0.25 | 0.57 | 5 | n/a -- see note below |
| name-entry-cursor | 230,345,230,60 | 0.00 | 0.00 | 17.02 | 17.39 | 5 | 0.00 / 17.02 |
| alias-save-prompt | 160,195,970,460 | 0.00 | 0.02 | 30.00 | 31.47 | 10 | 0.02 / 30.00 |
| autosave-disabled (s09/s10/s11, one ref reused 3x) | 160,195,970,460 | 0.00-0.06 | 0.00-0.09 | 13.62-32.90 | 15.22-15.23 | 5 | 0.09 / 13.62 |
| main-menu | 500,650,680,300 | 0.00 | 0.20 | 1.12 | 19.88 | 0.6 | 0.20 / 1.12 (tight -- see note) |
| mm-quickrace | 500,650,680,300 | 0.00 | 0.62 | 9.83 | 22.78 | 3 | 0.62 / 9.83 |
| qr-custom | 500,650,680,300 | 0.00 | 0.67 | 15.30 | 21.89 | 3 | 0.67 / 15.30 |
| cr-sprint | 500,650,680,300 | 0.00 | 0.37 | 19.99 | 16.87 | 3 | 0.37 / 16.87 |
| cr-track | 0,60,1180,140 | 0.00 | 0.07 | 48.13 | 33.70 | 5 | 0.07 / 33.70 |
| cr-opp2 | 130,300,1020,200 | 0.00 | 0.24 | 29.77 | 51.24 | 5 | 0.24 / 29.77 |
| cr-punto | 0,60,1180,160 | 0.00 | 0.06 | 33.39 | 61.93 | 5 | 0.06 / 33.39 |
| cr-auto | 150,290,980,380 | 0.00 | 0.00 | 27.64 | 45.59 | 5 | 0.00 / 27.64 |
| restart-ok (reused 11x) | 190,265,900,420 | 0.00 | see note | n/a | n/a | 5 | see note |

**alias-prompt / autosave-notice1 / autosave-notice2 do not discriminate bad from good**: both void
runs match pixel-for-pixel with the good runs through s04-s06 (confirmed in Step 0 -- divergence
starts at s07). Scores stay low (<0.6) for both good and bad frames at these three steps. These
three gates are kept anyway because a `waitfor` still does its primary job here -- it absorbs a
slow load before the press instead of firing on a fixed timer -- even though at this point in the
route it cannot yet catch a run that has not diverged yet. Threshold 5 is generous (not meant to
reject, since there is nothing to reject yet); it still rejects a genuinely wrong screen (e.g. a
black loading frame) if one occurred.

**main-menu's margin is tight** (good2 0.20 vs bad1 1.12, factor ~5.6x, versus 15-100x+ margins on
every other gate): the icon-carousel crop box is shared across main-menu/mm-quickrace/qr-custom/
cr-sprint for convenience, and main-menu's "Career" icon sits in a less text-dense part of that box
than the others' highlighted labels. threshold 0.6 sits roughly in the middle of the two bounds
measured here (2 good runs, 2 bad runs) and correctly separates all four, but a third bad run that
landed closer to Career than `87778` did could slip through. Flagging rather than reworking the
box, since the box already separates every sample available.

**restart-ok's bad-run columns are n/a**: neither void run reached the race loop in a form where
"the frame at this shot label" is a meaningful comparison (both diverged long before `r2-ok`).
Instead, scoring restart-ok against every `r<N>-ok` frame in both good runs (22 samples) turned up
one real divergence inside a run already called "good": good run 2's `r7-ok` scores **46.18**,
because that frame is not the restart-confirmation dialog at all -- it is mid-race gameplay HUD (7%
complete, 18.40s elapsed). The other 21 samples score 0.00-0.72. This means the existing route's
restart loop has already produced at least one silently-wrong `r*-ok`/`go<N>` pair in a run that
`title_verdict.py` presumably scored as a normal frame-rate measurement -- direct evidence for why
step 2 gates the restart loop too, not just the first-run prompts and the pre-race menus.

### Reference-crop sizing/orientation check (for Step 1)

Full device screencaps used by route.sh's `shot`/`mark`/`waitfor_step` are 1280x960 PNG (confirmed
via PIL `Image.open().size` on both good- and bad-run frames above). `castlevania-cod.first-run`'s
existing refs (`name-entry-header.png` 490x85, `name-field-empty.png` 120x70) are pre-cropped to
exactly their region's `w x h`, matching `waitfor_match.py`'s `region_score()`, which crops the
*frame* to the region but uses the ref image at its native size (both are then resized to the
fixed `CMP_SIZE = (64, 48)` for scoring). Crops cut from the dispatcher `route-frames/*.png` files
used in this analysis are the same 1280x960 orientation route.sh captures, so no resize/orientation
fix is needed before cutting Step 1's reference crops.

## Step 2: gated nfs-mw-quickrace.route

Edited `docs/testing/titles/routes/nfs-mw-quickrace.route` additive-only: 36 `wait 0.12` lines
(one after every zero-hold `axis HATX/HATY max|min` tap, so each hold is >=0.1s before the
following `mid`), 9 `waitfor` gates for the first-run prompts/menus (s04-s12), 7 `waitfor` gates
for the pre-race menu screens, and 11 `waitfor restart-ok` gates before each restart loop's `press
A`. No existing `wait` duration, and no `mark gameplay`/`go2`..`go12` offset, was touched; every
new gate sits before the committing `press A`, never between it and the mark it feeds, per the
brief. `route.sh --check docs/testing/titles/routes/nfs-mw-quickrace.route` -> "route ok". Header
note added citing 87778/87617. Committed at `22f63bc5bb`, pushed (matches `origin/lane/nfsroute1011`).

### Proof blocked: ref crops cannot reach a pre-merge dispatched run

Ran the required proof:

```
bash docs/testing/request.sh --who nfsroute1011 \
  --purpose "route proof: gated nfs-mw-quickrace reaches 12 race starts (#433)" \
  --title "4541007B-Need_for_Speed_Most_Wanted.xiso.iso" --route nfs-mw-quickrace \
  --seconds 500 --frames-every 30 --device nova \
  --no-expect "route proof: gated nfs-mw-quickrace reaches 12 race starts"
```

Refused at queue time, before touching the device:

```
refusing to queue: route 'nfs-mw-quickrace' parses here but would not run in the dispatched soak:
  /home/justin/hakux-work/dispatch/bin/titles/route.sh: route.sh: /tmp/tmp.16Ybj5HzIq/route.txt:44: waitfor 'alias-prompt': no reference crop /tmp/tmp.16Ybj5HzIq/refs/route.txt/alias-prompt.png
  /home/justin/hakuX/docs/testing/titles/route.sh: route.sh: /tmp/tmp.16Ybj5HzIq/route.txt:44: waitfor 'alias-prompt': no reference crop /tmp/tmp.16Ybj5HzIq/refs/route.txt/alias-prompt.png
```

This is not my route being wrong; it is `request.sh`'s own documented design (its comment above the
check, ~line 1154-1190): the route's *text* travels with the request and is written to `<result
dir>/route.txt`, but the worker plays that bare file with the **serving snapshot's**
(`$SNAPBIN/titles/route.sh`) or **serving tree's** (`/home/justin/hakuX`, tracking master)
`route.sh`. `ref_path()` resolves a `waitfor`/`press-until` crop at
`$(dirname ROUTE)/refs/$(basename ROUTE .route)/<name>.png` -- i.e. `<result
dir>/refs/route.txt/<name>.png` for a file literally named `route.txt` -- and nothing copies a
`refs/` directory alongside it. `request.sh` checks this exact failure mode itself, against both
the snapshot and the serving tree, before ever queuing: "A 'waitfor' or 'press-until' crop does not
travel with the request... must be in the serving snapshot
(`$SNAPBIN/titles/drive-profiles/`) or on the serving tree's master." Both of those are outside
this lane's territory (`/home/justin/hakux-work/dispatch/bin`, `/home/justin/hakuX`) and are not
something a lane may write to directly (the lane role's device rules: `request.sh`/`hold.sh` only,
no new kind of write). The "private DISPATCH_DIR" the comment mentions as the third fallback is a
host with no snapshot and no serving tree at all -- not a staging area a lane can point at itself;
on this host both the snapshot and the serving tree exist, so that branch does not apply here
either.

**Consequence:** any route whose `waitfor`/`press-until` gates are new (not yet on
`/home/justin/hakuX`'s master or in the dispatcher's snapshot bin) cannot be proven by a real
dispatched device run before merge, regardless of whether the route's own logic is correct --
`route.sh`'s `validate()` checks every `waitfor` ref's existence at parse time, for the whole file,
before the first step plays, so this is the actual run-time behavior, not an artifact of
`request.sh`'s own pre-check. Steps 2, 3 and 4 in this brief all introduce new refs directories, so
all three hit this same wall; it is a harness-level gap in the dispatch/testing path (ref-staging
for a route under test), not something in this lane's territory (`route.sh`, `request.sh`,
`dispatcher.sh` are all out of territory) to fix.

This counts as the one failure the brief allows before moving on ("A route that fails its proof
gets one fix and one rerun. If it fails again, write up what blocks it in NOTES.md and go on to
step 3.") -- except there is no fix available on this lane's side to attempt a rerun against: the
failure is in the proof mechanism, not in the route text, which already passes local `route.sh
--check`. Per that same brief line, proceeding to Step 3. **lane.local / whoever owns
`request.sh`/`dispatcher.sh`: a route-under-test needs its `refs/<route-stem>/` copied alongside
`<result dir>/route.txt` (or `ref_path()` needs to resolve against the *request's own* route name,
not the literal `route.txt` filename the dispatcher writes) before any lane's new `waitfor` gates
can be proven pre-merge. Until that lands, `nfs-mw-quickrace.route`'s Step 2 gates are reviewed and
locally validated but not device-proven, and the same will be true of Steps 3 and 4's new routes.**

No `QUICKRACE-GATED:` line follows, because the required proof did not run.

## Addendum: lane.local (11:58 PDT) -- crop fix owned by soakvideo1011; hold the proof runs

lane.local confirmed the ref-staging gap above is real and is being fixed in
`request.sh`/`dispatcher.sh` by lane.soakvideo1011 (its brief's Addendum 3): `request.sh` will
carry the crops a route names as `route_refs` and stage them; `dispatcher.sh` will write them to
`<result dir>/refs/route.txt/`. This lane does not touch either file. Until it is live (both
`grep -q route_refs /home/justin/hakuX/docs/testing/dispatcher.sh` passes and this worktree has
merged origin/master past that point), **no run of a route with `waitfor`/`press-until` may be
queued.** Steps 2 and 3's device proofs stay blocked on that signal; lane.local said it would
message when it is live. Meanwhile: settle the alias dialog from frames (below), write Step 3's
route and validate its crops offline, and let the Nova queue drain before taking another hold.

## Step 3: the profile route -- alias dialog settled, pathfind exploration

### Alias-creation Yes/No dialog: default and highlight, settled from raw frames

Took the Nova hold and ran `pathfind.py` with `--state first-run --budget-min 15 --hold-s 120`
into `docs/lanes/nfsroute1011/scratch/pathfind-profile/` (scratch, uncommitted). The model's own
per-step narration misread this exact dialog repeatedly -- at least 6 of its ~14 encounters
(steps 6, 8, 14, 21, 23 in `calls.jsonl`) it called "Yes" the highlighted/selected option because
the word renders in bold white text, and pressed `A` directly, which **declines** alias creation
and loops back to the Career Main Menu. Reading the raw `NNN-look.png` frames directly (not the
model's "see"/"why" fields) settles it:

- `006-look.png`, `025-look.png`, `026-look.png` (same dialog, 3 separate encounters): the "Xbox
  hard disk" alias-creation prompt has two stacked rows, "No" above "Yes". **"No" carries a
  bracket-cornered highlight box; "Yes" does not.** "Yes" only renders in brighter/bolder text,
  which is a style choice, not a selection indicator, and is what fooled the model's narration
  repeatedly.
- `007-look.png` (captured right after step 6's bare `A` on frame 006): back at the Career Main
  Menu with Start Career highlighted -- confirms `A` on the as-shown ("No" boxed) state declined,
  it did not create an alias.
- Step 26's action (`DOWN`, `A` -- i.e. `press DOWN` then `press A`, not `axis HATY`) on the same
  dialog (frame 026) produced `027-look.png`: the "Need for Speed Most Wanted uses an autosave
  feature..." info dialog with a single "OK" button, layered over the Career Main Menu. This is
  the autosave notice mentioned in cause #1 of the brief, and its appearance means `DOWN A`
  **did** move the selection off "No" and onto "Yes" and confirmed it -- alias creation succeeded.

**This matches the already-established Step 0 finding and `nfs-mw-quickrace.route`'s own existing
`s04` input** (`axis HATY max` / `wait 0.12` / `axis HATY mid` / `wait 0.6` / `press A 120`): one
down-tap selects "Yes" from the "No" default, then confirm. Step 26 used a `press DOWN` (BTN code)
rather than an axis tap and it still worked, which is further (independent) evidence for Step 0's
finding that NFS reads the D-pad `press` the same as an `axis HAT` tap on this dialog family (both
move the dialog's cursor).

**Caution for whoever later touches `pathfind.py`'s vision prompting**: this dialog is a
reproducible blind spot -- the model fixates on text brightness over the bracket-box selection
indicator, with no self-correction across many repeats of the identical screen, and the resulting
loop (~400 s, 20+ steps) closely resembles the owner's original report ("stuck in a profile
creation screen that's scrolling through keys and buttons"). Not this lane's territory to fix, but
worth a line in whatever picks up pathfind.py's prompt next.

### Still missing: keyboard and save-confirmation frames

The pathfind run ended (exited on its own, apparently its `--hold-s 120` session timeout, right
after emitting frame 027/step 26 with no further step) before reaching the name keyboard or the
save-confirmation dialog. `027-look.png` is the last frame captured. Pressing `A` on the
autosave-notice "OK" (frame 027) should be the next input, expected to lead into the name keyboard
-- not yet confirmed from a frame.

Per the brief's Rules ("Use request.sh, pathfind.py and hold.sh only"), the Nova hold was released
immediately once this pathfind session ended (three runs were queued behind it: two nfsdefault1011,
one gtasagpu1011 -- `ls /home/justin/hakux-work/dispatch/queue`). Next hold waits for that queue to
drain, per lane.local's addendum, and is capped at 20 minutes, aimed specifically at the keyboard
and save-confirmation screens (e.g. `--goal` text telling the model explicitly that a dialog's
selected option is marked by a bracket-cornered highlight box, not by text brightness, since that
is the exact blind spot that produced this run's loop).
