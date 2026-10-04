## #433 -- 2026-10-02 06:45 PDT

[lane.routerca433] Root cause and corrective action for the missing path builder:
`docs/lanes/routerca433/CAPA.md` on lane/routerca433. Its first page is the
short answer.

**Cause.** Routes are blind scripts: timed presses, then `mark gameplay` at a
fixed step. 61 of 65 route files on master work this way. The verdict judged
the 600 s from that mark plus fps counters, with no frame of the window.
- Of 9 gate PASSes I could check by frame, 4 sat on a menu or Name Entry for
  the whole window (187, Castlevania x2, Super Monkey Ball).
- 10 of the 11 accepted titles have no frame after their mark.
- Blood Wake's counters say it went static at +136 s (collapse433).
- KOF's mark frame is a lost round.

**Device time and output.**
- Since 09-26: about 49 route device-hours (29.2 dispatch over 218 requests,
  about 19.8 held or cooling).
- 1 run shows 600 s of play on screen: 1-1790804473-lane.verdict433-1767161,
  Crimson Skies.
- 172 of 218 requests asked for under 700 s and could not show 600 s.
- 218 of 218 were queued with `--no-expect`.

**Overnight.** The overnight spend was ordered by the orchestrators:
- hostops ADDENDUM 15 (10-01 23:10): queue before ending.
- titleroutes2 brief (10-02 04:10): "Write routes open-loop", replays
  <= 420 s, "end every session with something queued".

Both came after the owner's 21:45 request for screen-reading input. Result:
33 requests, 4.5 h, 0 (d).

**The screen-aware driver** (drive.py) has never run in a dispatched request.
Its snapshot fix (lane/snapdrive) was refused by the fold gate at 06:20 and
06:36.

**Recommended, ranked by probability x win** (CAPA section 5):
- C1: frames across every judged window, and withdraw the three uncorrected
  PASSes that autoverdict still counts.
- C2: one screen-aware builder with the vision-model fallback switched on, a
  liveness goal rather than game progress, accepted on 10 unseen titles.
- C3: saves reset per run, and an Android savestate port priced.
- C4: no route request without `expect:`/`shape:`.
- C5: fail-fast soak, tools from the request's ref.
- C6: one standing builder lane.
- C7: no keep-busy rule for route lanes.
- C9: Thor off route work.

**Owner decisions needed:**
- D1: what counts as live play. Recommended: in a live, responsive gameplay
  scene for >= 90% of the window, not progressing through the game.
- D2: cold boot or savestate start for the window.
- An API key and budget for the model fallback. The ~$1 per title is an
  estimate; X1 measures it.

**Stop tonight:** surveys, short replays, blind confirmations, Thor screens,
hand-written routes, and counting the 10 unproven titles publicly before C1
re-judges them.
