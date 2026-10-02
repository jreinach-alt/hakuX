## #433 -- 2026-10-02 04:10 PDT

lane.routedriver2, session 1. All runs were held `drive` replays on the Nova
(02:21-04:02 PDT). No confirmations were queued, and nothing here makes a
title Playable.

- **Sonic Heroes: past the Seaside Hill block (brief item 1, done).** The
  escape that works is Fly's own move. The formation gate before the block
  puts the team in Fly. Climbing in place (stick released, 12 A taps), then
  1.2 s of forward, lands them on top of the block (0:12 → 0:17), with 30 s
  of play after it. The driver now reads the formation from the HUD's leader
  circle and picks that formation's escape. In 4 trials it also cleared the
  POWER block (2:03). Trial 4 played 450 s with no ROUTE FAIL, through three
  obstacles, a fall into the sea, and a Game Over that it menued back from.
  Not solved: Seaside Hill end to end. A scored Sonic window would still be
  about half `stalled`/recovering. Frames: `docs/lanes/routedriver2/sonic/`.
- **False `play`, found and fixed.** A team struggling in a corner, or a
  camera swaying at the sky, changes the screen enough to read `play` (40-45%
  of 100 s stretches in Sonic trials 1-2). The fixes:
  - a 10 s scene-layout progress check (opt-in per title);
  - a rule that play must hold 10 s after a stall.

  Also found: a selftest fixture had been passing on that false play (the
  team wedged at the POWER block). It now expects a stall.
- **Forza steering (item 2): tried, not solved, switched off.** The Arcade
  suggested line (green chevrons) is easy to find in the frame. But a
  steering loop driven by screencaps runs at ~1 Hz on the Nova. In both runs
  it put the car into a wall within 12 s, where RT alone reaches play. The
  precondition for any steering is a faster screen signal. `--find` with
  steering off still reaches play. The frames are weak, though: the car
  scrapes the pit wall at 0-22 MPH on the Nova, against 73 MPH on the Thor.
- **Buffy (item 3): the driver reaches real play ~35 s after boot**,
  through title, menus, difficulty and the load, each recognised. This
  needed per-title dark-scene settings: the canyon's motion and luma sit
  under the defaults. It stops at a ledge gap ~12 s into play. So `--find`
  gets 10-12 s of play, not its 20, and I did not lower the bar.
- **Emulator abort, for a tracker row.** Buffy, Nova, 03:40:27 PDT, about
  10 s into the intro FMV: `pgraph.c:2163 pgraph_method: assertion
  "channel_valid" failed` (pfifo_thread, SIGABRT). It is intermittent: five
  other Buffy boots passed the same intro. Excerpt:
  `docs/lanes/routedriver2/buffy/b4-emulator-abort.txt`.
- **Driver safety fix.** After that abort, the driver's next A went into the
  launcher and opened Calendar. drive.py now sends no press unless hakuX is
  the focused app.
- **Blocker for the play_share spot check (item 4), and for every
  dispatched `drive` route.** The dispatcher's script snapshot does not carry
  drive.py, classify.py, waitfor_match.py or drive-profiles/:
  `route.sh --check` on the snapshot fails with "no profile". The fix is in
  dispatcher.sh (outside this lane); the exact list is in NOTES.md item 4.
  The gate's reader does check out on a held Forza run's full logcat
  (play_share 0.51, which matches the frames).
