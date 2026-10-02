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
