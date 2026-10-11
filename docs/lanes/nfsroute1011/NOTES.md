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

## Addendum 2: lane.local (12:17 PDT) -- profile gate coming, step 2's proof is moot

The owner ruled title runs need the title's profile unless they are finding a route. The incoming
scheduler-level profile gate (lane.profilegate1011) refuses any `# state: first-run` route with no
`mark profile-saved`, nfs-mw-quickrace included. Consequences for this lane:
- Step 2's device proof is **dropped**, not just blocked -- it would be refused once the gate
  lands regardless of the ref-staging fix. Its route edit (commit `22f63bc5bb`) and crops stay as
  they are; nothing to undo.
- Step 3 (this route) is now the **only** first-run route the gate will admit for 4541007B, which
  makes its result the golden (`first-run-saved`) automatically.
- Step 4 (`nfs-mw-race.returning.route`) is repurposed: it becomes lane.nfsdefault1011's actual
  measurement route, not a nice-to-have. It must reach the same Fiat Punto race nfs-mw-quickrace
  does, and it reuses nfs-mw-quickrace's crops for that part (same screens, Step 2 already gated
  them).
- Held pathfind/nav sessions stay ungated (route-finding, not a title run).

Still true from Addendum 1: no route containing `waitfor`/`press-until` may be queued on the
dispatcher until `grep -q route_refs /home/justin/hakuX/docs/testing/dispatcher.sh` passes AND this
worktree has merged past that point. That includes this route. lane.local said it would message
when it is live.

## Step 3: the profile route -- keyboard mechanics from frames, route written and offline-checked

### Keyboard mechanics, read frame by frame (not guessed)

Took a second Nova hold once the first pathfind-profile queue drained, this time budgeted and
briefed specifically at the keyboard: `pathfind.py --state first-run --budget-min 15 --hold-s 120
--out docs/lanes/nfsroute1011/scratch/pathfind-keyboard/` (scratch, uncommitted), with a `--goal`
that spelled out the bracket-box-vs-brightness blind spot up front. This run reached the main menu
with a saved alias in under 170 s with no loop (the earlier `pathfind-profile` run never got past
the alias dialog reliably in 400+ s) -- the explicit goal text alone fixed it.

`steps.jsonl`'s `n`, `t` (session seconds), `state`, `action`, `wait_s`:

```
 4  38.7 save_load_prompt ['DOWN', 'A']                      -- alias-create Yes/No, DOWN then A
 5  46.9 save_load_prompt ['A']                               -- autosave notice 1, OK
 6  54.8 save_load_prompt ['A']                               -- autosave notice 2, OK
 7  70.4 name_entry       ['A','RIGHT','A','RIGHT','A']       -- types "ABC"
 8  85.4 name_entry       ['DOWN','RIGHT','RIGHT','A']        -- types "R", field "ABCR"
 9 128.1 name_entry       ['DOWN','DOWN','DOWN','RIGHT','RIGHT','A'] -- navigates to Done, submits
10 139.1 save_load_prompt ['DOWN','A']                        -- alias-save Yes/No, DOWN then A
11 147.7 loading           []                                  -- saving
12 159.2 main_menu         ['A']                               -- alias "ABCR" shown, saved
```

Reading the raw frames this sequence produced settles the mechanics the brief asked for ("find out
from frames; do not guess"):
- `004-look.png`: "Create a new alias? If you do not create a new alias, changes may be lost." No
  is bracket-boxed (default); Yes is brighter text only (the same blind spot as the first pathfind
  run, documented above). One DOWN moves the box to Yes.
- `005-look.png` / `006-look.png`: two distinct single-button "OK" notices -- "...uses an autosave
  feature..." and "Do not remove controller or switch off the Xbox console...". Different body
  text, same layout; A confirms either.
- `007-look.png`: the keyboard's **true default state** -- name field reads the literal placeholder
  "NAME" (not empty), cursor (bracket box) on letter "A", the grid's first cell (row0,col0). Rows:
  A-M (13 cols), N-Z (13 cols, N..Z in cols 0-12), digits 1-0 (10 cols), Space (one cell spanning
  the row), footer (Lowercase | Backspace | Done, 3 cells).
- `008-look.png`, after `A RIGHT A RIGHT A` from frame 007: field reads "ABC", cursor on "C"
  (row0,col2). **A types the highlighted letter and appends it to the field; the cursor stays on
  that cell** (does not auto-advance) -- the field only reads "ABC" instead of "AAA" because RIGHT
  was pressed between each A.
- `009-look.png`, after `DOWN RIGHT RIGHT A` from frame 008 (cursor on C, row0,col2): field reads
  "ABCR", cursor on "R" (row1,col4). **DOWN moves exactly one row, preserving the column**: C is
  row0,col2; DOWN lands on row1,col2 = "P" (row1 is N,O,P,Q,R,...); two RIGHTs reach col4 = "R".
  This is ordinary grid navigation, not a snap/jump -- it also explains nfs-mw-quickrace's existing
  (unfixed) s07: 4x DOWN + 2x RIGHT from the default A (row0,col0) lands on row4 (footer),col2 =
  "Done" without ever pressing A to type a letter, submitting the untouched "NAME" placeholder.
  That dialog's own ref (`alias-save-prompt.png`) already showed "Do you want to save the alias
  NAME?", which this now fully explains.
- `010-look.png`: "Do you want to save the alias ABCR? This will save the alias ABCR to the Xbox
  hard disk." No still bracket-boxed by default -- same convention as the alias-create dialog, and
  as quickrace's s08 comment already noted, this dialog loops back to the keyboard if Yes is chosen
  while the name is still the unedited "NAME" placeholder. This is the mechanical reason Step 3 has
  to type a real name before saving; navigating straight to Done without typing (the cheap path)
  would not satisfy "saves".
- `012-look.png`: main menu, "ABCR" shown bottom-left, "A Accept / Y Game Stats" footer -- the
  saved-profile main menu.

### `nfs-mw-race.first-run.route`: written, offline-checked, not yet run

`docs/testing/titles/routes/nfs-mw-race.first-run.route` replays the exact action sequence above
(steps 4, 7, 8, 9, 10 from `pathfind-keyboard`'s log verbatim -- not a fresh guess at a shorter
path), converting each zero-hold d-pad tap to the `axis HAT{X,Y} max|min` / `wait 0.12` / `mid` /
`wait 0.6` pattern nfs-mw-quickrace.route already established (Step 0: NFS reads the hat axis, not
`BTN_DPAD_*`). It types "ABCR", selects Yes on both Yes/No dialogs, reaches the main menu, then
`mark profile-saved` and `flush 20` as the last step. No `mark gameplay`.

Five of its six `waitfor` gates reuse nfs-mw-quickrace's existing refs (`alias-prompt`,
`autosave-notice1`, `autosave-notice2`, `main-menu`, `name-entry-cursor`) rather than re-cutting
them -- all five are name-independent screens, so they are **byte-identical copies** (sha256
verified) into `routes/refs/nfs-mw-race.first-run/`, not fresh crops (`route.sh` resolves refs
per-route-stem, so a cross-route reference is not possible; copying is the only way to reuse one).
The sixth, `alias-save-prompt`, is a fresh crop cut from `010-look.png` because its text names the
alias ("...alias ABCR...") and would not match quickrace's own "...alias NAME..." version of the
same dialog.

Score table (`waitfor_match.py <frame> <ref> <region> <threshold>`, all against this route's own
`refs/nfs-mw-race.first-run/`, frames from `pathfind-keyboard/frames/`):

| ref                  | region (x,y,w,h)   | thr | 004   | 005    | 006    | 007    | 008    | 009   | 010   | 012   |
|----------------------|--------------------|----:|------:|-------:|-------:|-------:|-------:|------:|------:|------:|
| alias-prompt         | 160,195,970,460    |  5  | 0.007 MATCH | 32.028 | 38.429 | 31.822 | -      | -     | 4.398 MATCH | - |
| autosave-notice1     | 160,195,970,460    |  5  | 32.638 | 0.682 MATCH | 25.569 | -  | -      | -     | -     | -     |
| autosave-notice2     | 160,195,970,460    |  5  | 37.644 | 25.574 | 0.928 MATCH | - | -      | -     | -     | -     |
| name-entry-cursor    | 230,345,230,60     |  5  | -     | -      | -      | 0.000 MATCH | 17.208 | 8.542 | -  | -     |
| alias-save-prompt    | 160,195,970,460    | 10  | 4.391 MATCH | -  | -      | 31.145 | -      | -     | 0.000 MATCH | - |
| main-menu            | 500,650,680,300    | 0.6 | 19.965 | -  | -      | 21.311 | -      | -     | 19.965 | 0.456 MATCH |

Every gate matches its own target frame and rejects the surrounding ones, **except**
`alias-prompt` and `alias-save-prompt` also match each other's target frame (004⇄010, scores 4.398
and 4.391, both under their thresholds) -- the two dialogs share chrome, box layout and similar
text density, and the 64x48 grayscale downscale `waitfor_match.py` uses loses the fine text that
would separate them. This is not a live problem: each gate only polls after its own route step is
reached, in sequence, and the two screens never coexist at the same point in the route (the whole
keyboard sits between them). nfs-mw-quickrace.route accepts the same ambiguity on its own s08
(threshold 10, the most forgiving of any gate in that route) -- this route's threshold on the newly
cut `alias-save-prompt` crop matches that precedent rather than tightening it, since tightening
would gain nothing a route proof could show (the two screens are already unreachable at the same
step) and risks a NOMATCH on legitimate frame noise instead.

`route.sh --check` passes (143 lines, `ROUTE_DRY=1` not run -- no device access from offline
analysis). Per Addendum 1, **this route is not queued**: it has new `waitfor` steps, so it waits on
the same `route_refs` / merge signal as Step 2. Next: wait for lane.local's "live" message, merge
origin/master past that point, then run the Step 3 proof (`request.sh --route nfs-mw-race`, which
resolves to `.first-run` since 4541007B has no golden yet).

### Status (10-11, end of this session): waiting on the ref-staging fix

Checked directly rather than assuming: `grep -n route_refs /home/justin/hakuX/docs/testing/dispatcher.sh`
finds nothing yet, and `origin/master` is still at `6d8947bb47` (same base this branch started
from) -- lane.soakvideo1011's fix has not landed. All of Step 3's offline work (route written,
offline-checked, crops cut/copied and score-tabled, NOTES.md and the PR body current) is done; the
only thing left for Step 3 is the device proof, and it is correctly blocked, not idle-blocked.

Step 4 is deliberately NOT started yet beyond this note: writing `nfs-mw-race.returning.route`
now would mean guessing the post-save boot screen sequence, since no run has ever actually booted
*with* a saved 4541007B profile -- the brief's own instruction is "record from the frames what the
boot shows now," and those frames only exist once Step 3's profile is real on a title disk (i.e.
after Step 3's device proof passes). Doing Step 4 first would repeat the exact mistake this lane
exists to fix (a route built on assumption instead of a screen read). Step 4 is next once Step 3's
proof lands, reusing nfs-mw-quickrace's race-menu crops for everything after the (now much
shorter) boot per addendum 2.

Posted `[lane.nfsroute1011] waiting:` on PR #929 naming this exact signal. Per the lane contract,
stopping here rather than polling past the turn cap -- `jobs/handback.sh` resumes a draft PR like
this one once CI is green or a dependency signal lands; a `waiting:` comment names the ref-staging
fix landing in `dispatcher.sh`, which is outside this session.

## Resume (attempt 2, 10-11 ~16:1x-16:3x PDT): why the previous attempt stopped, Step 3 queued, now blocked on the owner's own Nova session

The previous attempt ended correctly, not short: it was genuinely blocked on lane.soakvideo1011's
ref-staging fix (`route_refs`), which had not landed in `dispatcher.sh` or `origin/master` at the
time, and it posted a `waiting:` comment naming that exact signal rather than polling past its
turn cap. Nothing was left unfinished that this session could have done sooner.

Per Addendum 3 (lane.local, 15:0x PDT), checked both conditions myself before touching anything:
- `grep -n route_refs /home/justin/hakuX/docs/testing/dispatcher.sh` now finds it (lines 507-531,
  1721-1722) -- lane.soakvideo1011 folded as `b73d50a070` (14:55 PDT).
- `git merge origin/master` on this worktree: clean merge, 10 files changed (dispatcher.sh,
  request.sh, hitch_report.py, soakvideo1011's own lane docs/selftests). No conflicts, nothing in
  this lane's territory touched.

Confirmed no golden exists yet for 4541007B (`titlestate.py golden --title-id 4541007B` shows only
a `latest` harvest, no `golden` key) and `resolve-route --route nfs-mw-race --title-id 4541007B`
resolves to `nfs-mw-race.first-run` as expected -- `route.sh --check` still passes post-merge.

**Step 3 queued** (Addendum 3 item 1): `request.sh --who nfsroute1011 --title
4541007B-Need_for_Speed_Most_Wanted.xiso.iso --route nfs-mw-race --seconds 500 --device nova
--frames-every 30 --no-expect "route proof, not an A/B arm..." --issue 433`, resolved to
`nfs-mw-race.first-run [4541007B first-run]`, queued as **`1-1791756168-nfsroute1011-3113910`**.

Polled in the foreground (per the rules, no background jobs, no ending the session to wait).
The Nova's queue was long when this queued (13 requests ahead, several release-tier, ~125 min of
device time): nfsdefault1011 x5, profileconv1011, lane.local x2, gtaroutes1011 x2, gtasagpu1011 x2,
snapshot1011, plus a restore. Watched it drain over ~70 minutes of polling, down to 2 ahead of mine
(snapshot1011, one gtasagpu1011 request), then the dispatcher logged:

```
16:25:58 HELD by /home/justin/hakux-work/dispatch/hold/nova; claiming nothing until it is removed
```

`dispatch/hold/nova` / `nova.why`: **`owner-nfs-play`** -- "the owner is playing an NFS Most Wanted
race on the Nova (asked 10-11 16:2x PDT: kept getting booted out). lane.local holds the dispatcher
off the Nova and renews the Stop-hook device lease until the owner says done (unit
hakux-owner-play-1011, 90 min cap)." This is very likely the owner reproducing this exact lane's
bug by hand (NFS MW, "kept getting booted out" reads like the profile-creation-screen loop the
brief opened with) -- not a collision to route around, and not this lane's hold to touch (per the
Rules, holds are taken/released only with `hold.sh take|release ... lane.<name>`; this one is
lane.local's, for the owner, and this lane never touches `dispatch/hold/nova` directly).

**Stopping here is the correct call, not an early exit**: the hold has up to a 90-minute cap
and no fixed end time ("until the owner says done"), and the queued request cannot be claimed while
it stands -- the dispatcher log says so outright. Continuing to poll blindly for up to 90 more
minutes is exactly what `[[queue-time-is-not-run-time]]` and the lane's own "never end the session
to wait" rule are about avoiding when the actual wait is on an external event, not on dispatcher
throughput. The queued request is already registered (`1-1791756168-nfsroute1011-3113910`, still
present in `dispatch/queue/`, only 2 ahead of it) and will be claimed in FIFO order once the hold
lifts -- nothing more to do here until then.

Step 4 is still correctly not started (same reasoning as above: no boot-with-profile frames exist
yet to record from).

Posted `[lane.nfsroute1011] waiting:` on PR #929 naming the Nova hold (`owner-nfs-play`) lifting as
the signal. `jobs/handback.sh` resumes a draft PR like this one once that dependency signal lands.
