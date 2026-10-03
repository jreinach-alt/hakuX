## #433 -- 2026-10-02 00:25 PDT

lane.routedriver: the two route-conversion proofs (brief item 6) are done.
Both reached live play under the screen-aware driver. Sonic also turned up a
false `play`, which is now fixed.

- **Forza Motorsport, Thor (supervised `--find`, ADDENDUM 4):** title 15.5 s,
  play 74.7 s. Only A went into the menus, then RT was held. In the
  confirmed stretch the car accelerates 10 -> 73 MPH, LAP 0/2 -> 1/2, and
  the scenery passes; at 0 MPH on the line it read `unknown`, not play.
  Started at xo-therm 39 C and ended at 59 C. Limit: RT does not steer, so
  the car ran wide at the first bend. That is fine for finding play, but a
  scored window needs steering. Frames:
  `/home/justin/hakux-work/wt/routedriver/scratch/run-fz1/route-frames/`
  234106-040-play.png ... 234129-050-play.png; sheets
  `docs/lanes/routedriver/forza/run1-play-a.jpg`, `run1-play-b.jpg`.
- **Sonic Heroes, Nova:** title 8.1 s, play 34.7 s. One A skipped the story
  cutscene the old route waited 100 s for. Frames:
  `/home/justin/hakux-work/wt/routedriver/scratch/run-sh2/route-frames/`
  235256-021-play.png ... 235317-030-play.png; sheet
  `docs/lanes/routedriver/sonic/run2-play.jpg`. They show running and
  rings, then the team falls into the sea and respawns. That is live play,
  not progress.
- **Found and fixed:** Sonic's first replay counted 6 s of the team wedged
  against a block as `play` (the clock and water kept the frame changing).
  Sonic's HUD frames now use their own motion bars, so that wedge reads
  `stalled`.
- **Not solved:** the Seaside Hill block. A jump-and-fly escape clears it,
  but every variant tried (five) falls short of the next island and costs a
  life. The profile allows one try per run and records all five.
- No confirmations queued; nothing here makes a title Playable. 0 model
  calls in every run.

## #433 -- 2026-10-01 23:30 PDT

lane.routedriver: Castlevania: Curse of Darkness (4B4E002D) first run now
reaches live play under the screen-aware driver (owner ADDENDUM 3).

- Held Nova replay 5 (23:00 PDT), `drive castlevania-cod 360 find`: title at
  6.6 s, play at 53.6 s, ended itself at 74 s after 20 s of confirmed play
  (`reached-play`), app force-stopped, hold released 23:02. The old fixed-wait
  first-run route pressed at 24.3 s and marked gameplay at 192.5 s of waits,
  and never reached it unattended.
- Inputs, each sent only when the screen it is meant for is recognised:
  intro A -> title LY:min onto New Game, A -> Name Entry A, START, A ->
  "Is this correct?" A -> SAVE slot 1 A -> "Overwrite?" LX:min, A ->
  Saving -> three cutscene skips with A -> play.
- Skips recorded and tried first next run: intro_video via A (+0.0 s);
  cutscene via A (+0.0 s, 3 of 4 visits). Nothing unskippable.
- 0 model calls: every capture was named by the cheap classifier.
- The disk on the Nova carries a Castlevania save (the authoring session's,
  0:00:00), so "Create new save data?" did not appear; the driver answered
  "Overwrite?" instead. The no-save path's crops have not run on a device.

**Frames for your review** (the 20 s play stretch, full size):
`/home/justin/hakux-work/wt/routedriver/scratch/run-cv5/route-frames/`
230106-032-play.png, 230108-033, 230109-034, 230113-035, 230115-036,
230117-037, 230119-038, 230121-039, 230123-040, 230125-041, 230127-042
(and the path before them, 001 ... 031, in the same directory). Contact
sheet: `docs/lanes/routedriver/castlevania/run5-contact.jpg`. I looked at all
of them: HUD up in every frame, the character moving around the courtyard,
sword swings, camera panning. No confirmation was queued. Castlevania is not
Playable from this.

Not done: Sonic Heroes and the driving proof (one title per Nova session);
`drive` needs this branch folded before the dispatcher can play it.
