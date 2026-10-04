# failgate (#433): a failed or unproven run goes for identification

## What was wrong (lane.local's measurements, stored results in `dispatch/results/*`)

1. The verdict could not see a menu. `hitch_report.static_window` scored only
   post-mark `route-frames/` and needed 3; with fewer it returned
   `measured: False`, and `static_window_fail` never fails an unmeasured window.
   A window with no frames at all therefore passed.
2. Nothing turned a failure into a pathing hand-off on the repo side. The host
   side (`host-tools/failure_intake.py`) does that; `request.sh` did not ask it.
3. `title_verdict.contact_sheet` concatenated `route-frames/` then `frames/`
   into one grid, so a boot title screen sat mid-sheet and read as a restart.

## What changed

| Item | Where | What it does |
|---|---|---|
| 1 static_window fallback | `hitch_report.window_frames`, `static_window` | Liveness reads post-mark `route-frames/` when there are 3 or more, else post-mark `frames/`. Fewer than 3 in both: `measured: False`. |
| 1 unmeasured fails | `hitch_report.static_window_unmeasured`, `title_verdict.judge` | An unmeasured scored window fails the verdict as `window unmeasured: <reason>`. `static_window_fail` is unchanged (still never fails on its own). |
| 2 position test | `hitch_report.position_change`, `position_fail`, `judge` | Zero-model: `titles/classify.py` `motion()` between consecutive post-mark samples, against its `STATIC_BAR` (0.025). Fails when the first and last samples are the same picture, or when more than 50% of consecutive pairs are still. Recorded as `verdict.position`. |
| 3 request.sh gate | `request.sh` | Before queueing, runs `failure_intake.py gate <tid> <route>` when the tool exists. Exit 1 with `HELD` refuses with exit 3. `--identified <id>` admits it and is written into the request as `identified`. A failing gate (any other non-zero) also refuses. No tool: no gate. |
| 4 contact sheet | `title_verdict.contact_sheet` | Two groups under their own headers: `--- route frames ---` and `--- boot samples (30 s from boot) ---`. Each tile is labelled HH:MM:SS from its file name. Capped at 36 across both. |
| 5 Playable wall | **not in this PR** | Saved as `docs/lanes/failgate/item5-wall.diff`. See "Item 5" below. |

## Replay of stored verdicts (138 result dirs with a verdict)

`judge()` re-run on every stored result dir: master code vs this branch, with
no contact sheet written. Passing verdicts before: **12**. After: **4**.

Passes that now fail, all for the same reason, `window unmeasured: 0 post-mark
route-frame(s) and 0 post-mark frames/ sample(s)`. These runs have no frames
after the mark, so there is nothing to read:

| Result | Title | Before | After |
|---|---|---|---|
| 1790897326-autoverdict-3745925 | Castlevania (4B4E002D) | PASS | FAIL unmeasured |
| 1790902028-titleroutes-1005086 | Castlevania (4B4E002D) | PASS | FAIL unmeasured |
| 1790860858-autoverdict-1510236 | 187 Ride or Die (55530036) | PASS | FAIL unmeasured |
| 1-1790775886-lane.verdict433-3086875 | 187 Ride or Die (55530036) | PASS | FAIL unmeasured |
| 1-1790515369-lanelocal-1183547 | Alien Hominid (5A440004) | PASS | FAIL unmeasured |
| 1-1790737858-lane.verdict433-1456493r2 | WWE Raw 2 (5451000D) | PASS | FAIL unmeasured |
| 1-1790737859-lane.verdict433-1456544r2 | 50 Cent: Bulletproof (56550042) | PASS | FAIL unmeasured |
| 1-1790745235-lane.verdict433-366130 | Baldur's Gate: DA (5655001A) | PASS | FAIL unmeasured |

Passes that still pass (all three with frames read, and the position test
passes them):

| Result | Title | Still-pairs | First vs last changed |
|---|---|---|---|
| 0-1791050563-lanelocal-403485 | Gunvalkyrie (5345000B) | 2 of 39 (5%) | 0.315 |
| 1790970734-lanelocal-1022425 | ToeJam & Earl III | 0 of 172 (0%) | 0.849 |
| 1-1790804473-lane.verdict433-1767161 | Crimson Skies | (replay pass) | (replay pass) |
| 1-1791001364-uberdefault569-1888217 | ToeJam & Earl III | (replay pass) | (replay pass) |

The two `(replay pass)` rows are the four-pass replay table only; I did not
re-measure their pairs separately.

The position test failed four verdicts that already failed for other reasons.
It changed no verdict on its own:

| Result | Earlier failure | Position |
|---|---|---|
| 0-0-s-1790830432-titleroutes-310926 | duration 189 s | 10 of 19 pairs still (53%) |
| 1-1790826491-lane.verdict433-3477700 | reached_gameplay unconfirmed (generic route) | 30 of 48 pairs still (62%) |
| 1790830432-titleroutes-310926 | duration 189 s | 10 of 19 pairs still (53%), same numbers as the first row |
| 1790971658-lanelocal-1220020 | hang 466 s | 104 of 157 pairs still (66%) |

### What the brief's premises do not match

- The brief names Castlevania 1790895867-autoverdict-3359625 as a PASS. Its
  stored verdict is `verdict.json.withdrawn-20261003`, a FAIL for duration
  (560 s of 600). It fails before and after this change. The two Castlevania
  PASSes are 1790897326 and 1790902028, and both now fail as unmeasured.
- The brief names Black Stone as a PASS. No stored Black Stone result passes.
  The Black Stone results fail before and after (reached_gameplay, duration).
  Nothing in `dispatch/results/` backs "Black Stone got PASS".
- Gunvalkyrie, Tron and the other walls: Gunvalkyrie 1791050563 still passes.
  No stored Tron result passes, so there is no Tron pass to keep.

### The open question this table cannot answer

No stored result is a menu that **has frames** and passes. The 50% still bar
and the first-to-last rule are set from the stored walls above and from
`classify.STATIC_BAR`; they are not tested against a Name Entry that the
verdict got wrong. The owner's Name Entry case is the one to watch: its frames
should now be read and fail `position:`. If it still passes, the bar is too
loose.

## Decisions I made

- **Still vs moving, not menu vs gameplay.** `classify.py` names a menu only
  through a title's drive profile, and profiles exist for three titles
  (Buffy, Castlevania CoD, Forza). The position test therefore names the
  picture as still or moving. The failure message says "a menu, a pause, a
  load or a freeze", because a still picture is all three in the verdict's
  terms.
- **Unmeasured fails the run.** This is a rule change for every verdict. Eight
  of the twelve stored passes were judged on no frames after the mark.
- **PIL missing is unmeasured too.** The selftest runner has no PIL, so
  `judge()`-based fixtures carry route-frames only when PIL is present, and the
  pass-family expectations in `89-title-verdict.sh` say `window unmeasured`
  without PIL.
- **The gate fails closed on a broken gate.** A tool exit other than 0 or
  a `HELD` 1 refuses the request. An identification is not skipped because
  the tool that holds it crashed.
- **`--identified` is not verified by the lane.** The brief says the lane only
  refuses or allows. The host's `gate` already reads `pm/failure-resolved.txt`,
  and the request records the id so a reviewer can see what was claimed.

## Item 5 (Playable wall): deferred, not in this PR

`docs/testing/jobs/status_html.py` and `docs/testing/jobs/selftest.d/64-status-html.sh`
are not in this lane's territory. I did not edit them. The change is saved as
`docs/lanes/failgate/item5-wall.diff` (76 lines) and is ready to apply once the
territory is granted. What it does:

- `unproven(v, rdir)`: a PASS with no `static_window`, or with `measured: false`,
  is `window unmeasured`. A PASS whose result dir holds `IDENTIFIED.json` of
  class `pass-unproven` is `pass-unproven`.
- The panel count (`by_title`), the soak list that feeds `playable`, and the
  per-title verdict text all use it.
- `64-status-html.sh`'s fixture gets a measured `static_window`, so its
  "Playable needs a pass on every handheld" check still means what it says.

This matters now: the eight unmeasured passes above are still counted Playable
on the wall until the patch lands.

## Tests

- `docs/testing/jobs/selftest.d/96-failgate.sh` (new): window fallback (1),
  unmeasured fails (1b), position bar (2), gate held / `--identified` /
  released / broken / tool absent (3A to 3E), contact sheet bands (4, PIL only).
  Ran with a minimal harness: all pass on this host, PIL present.
- `89-title-verdict.sh`: fixtures write route-frames when PIL is present; the
  pass family accepts `window unmeasured` without PIL. Ran: all fixtures and
  mutants OK.
- `99-hitch-report.sh`: the static_window_fail contract is unchanged. Ran: OK.
- `64-status-html.sh`: not run here. It needs the full selftest harness (its
  `$HERE`, `gh` and git shims). It fails the same way on the master copy under
  this minimal harness, so the failures are the harness, not the change.

## Territory and file notes

- `request.sh`: the lend was asked for as one hunk. The change is three
  places: the `--identified` flag line, the `IDENTIFIED=""` default beside
  `ISSUE`, and the gate block with its env prefix and JSON field just before
  the queue write. The gate block and the env line are contiguous.
- `89-title-verdict.sh` is not in the requested territory. I changed it
  because the verdict now needs a readable window and its fixtures had none.
  Without this change CI would be red. It is in the PR's Files line.

## Open for an owner decision

- **Eight passes now unproven.** Alien Hominid, WWE Raw 2, 50 Cent, Baldur's
  Gate, 187 Ride or Die (two results) and Castlevania (two results) have no
  frames after the mark. Their Playable status stands on no readable window.
  Re-judging needs a run that captures frames (`--frames-every`), which is a
  device run. I did not queue one. Decide which of these to re-run.
- **Item 5 territory.** `status_html.py` needs a grant before the patch lands.

## What the next lane should not repeat

- Do not read a PASS as evidence that a window was seen. The verdict now says
  when it could not see the window.
- Do not judge a menu from one frame pair. The position test needs at least
  three samples to say anything.
- Do not assume the stored verdict is the verdict. `verdict.json` can be
  withdrawn; replay with `judge()` on the stored dir before quoting a result.

## Attempt 2: why attempt 1 did not finish

Attempt 1 finished items 1 to 4 on this branch (commits `fa0ce5ab44`,
`de4b991a6c`) but stopped before writing `docs/lanes/failgate/PR.md`. With no
PR.md, `foldqueue` never tried the branch, so the lane looked idle. Item 5 was
deferred for territory: `status_html.py` and `64-status-html.sh` were not
granted, so its diff is parked in `item5-wall.diff`.

Attempt 2 wrote PR.md (`State: ready`, Prediction none) and checked the two
fragments it touched. Results on this branch, `SELFTEST_ONLY` set to
`89-title-verdict.sh 96-failgate.sh`:

| Fragment | Result |
|---|---|
| 89-title-verdict.sh | all fixture and mutant checks ok (117 s) |
| 96-failgate.sh | 12 of 12 checks ok (2 s) |
| total | 126 passed, 0 failed |

Item 5 is still not in this PR. The 8 unmeasured passes in the table above
stay counted Playable on the wall until a follow-up applies the diff.
