# lane.blinx2input -- Blinx 2 (4D530065): the character never responds in Challenge 1

Issue #670 (local forge), umbrella #433. Base master @ 0426a98181.

## What the two pathfind runs actually show (read offline, 2026-10-02)

Runs: `~/hakux-work/wt/pathfind/scratch/runs/blinx-2.{guided,unguided}/`.

- Input reaches the guest. Menus, the Locker Room dialogues, the save
  screens and the in-game pause menu all answered START, A, B and the hat.
- The "gameplay" both runs probed is **Challenge, Test 1 of 7** ("This drill
  will test you on: Controlling the camera; Moving and jumping"). The card
  before the HUD says, verbatim: *"First you need to get your bearings. Move
  the **Right thumbstick** to look at the 3 balloons around you."* The HUD
  objective is "Locate the 3 balloons".
  Frames: guided `frames/026-cutscene.jpg`, `027-cutscene.jpg`; unguided
  `frames/008-submenu.jpg`, `009-gameplay.jpg`.
- pathfind's vocabulary has no right stick: `STICK:<dir>` drives LX/LY only
  (`STICK` table in pathfind.py), and no other token sends RX/RY. Every one
  of the 30+ probes per run was left stick, hat, face buttons or LT/START.
  `perf/pad.sh` itself does support RX/RY (on the Nova they resolve to
  ABS_Z/ABS_RZ).
- Blinx 1 (4D530013) has no such gate: its first gameplay is free movement,
  so the natural experiment does not separate "Blinx 2's input is broken"
  from "Blinx 2's first test wants an input the prober never sends".

## Ranked hypotheses (probability x what it explains)

| # | Hypothesis | p | Explains | Device: if right | Device: if wrong |
|---|---|---|---|---|---|
| H1 | Test 1 locks movement and jump until the camera has been turned to the 3 balloons with the RIGHT stick; the prober never sent RX/RY. Not an emulator defect. | 0.75 | all of it: menus work, idle only under LX/LY/hat/A, START pauses | RX hold turns the camera; balloons get ticked; the next instruction card appears; then LX walks and A jumps | RX hold changes nothing on screen |
| H2 | The right stick does not reach the guest on the Nova (pad reports it on ABS_Z/ABS_RZ; Android/SDL may map those to triggers or nothing), so the test can never be passed | 0.15 | same symptom, plus nothing passes Test 1 | RX/RY hold: no camera motion; logcat of the XID report shows sThumbRX stuck at 0 | camera turns (H1) |
| H3 | A guest-visible XID difference (port, capabilities, analog values) that Blinx 2's gameplay reader rejects and Blinx 1 does not | 0.10 | idle under every input in gameplay only | camera does not turn even with sThumbRX non-zero in the report | camera turns |

H1 is cheap to decide and decides the whole lane: one model-free device run
(replay START/A to the card, then RX/RY holds, then LX and A, a frame
after each).

## Device runs (Nova, model-free driver `rstick_probe.py`)

| run | what | result |
|---|---|---|
| 1 | fixed-time START/A beats, then RX/RY/LX holds | void: boot was ~60 s slower than the unguided run; every beat landed before the title and the game sat in its attract loop |
| 2 | screen-reactive (title signature -> START, then A until the card), then RX/RY full-deflection holds, LX/LY, A | reached Test 1 (team "Arch"). **RX orbits the camera, RY tilts it** (060, 062, 064 shows sky and a balloon, 066 floor); the camera springs back behind the player within 0.6 s of release. LX/LY and A: no movement, as the test intends. Objective still "Locate the 3 balloons" |
| 3 | slow sweeps at RX 11000 with RY tilt | RX 11000 does **not** yaw at all (game dead zone); RY tilts in proportion and springs back on release |
| 4 | RX 22000 / max with RY tilt, RX pulses | RX 22000 orbits at ~36 deg/s; yaw persists after a pulse. Frame 072: a **red lock-on arc** round a centred balloon |
| 5 | closed loop: find the olive-green balloon blob, pulse yaw toward it, pitch held up | the loop overshot (gain x2 too high) but swept the balloons through centre; **all 3 popped** in ~25 s (041 arc, 042 popped, 050 confetti). Next card: "Now let's try first-person view. Click the Right thumbstick." -- Test 1 advances; the game is fully responsive |

Verdict on the hypotheses after run 2: H2 refuted (right stick reaches the
guest); H3 has nothing left to explain; H1 holds. Not an emulator defect, no
emulator fix and so no prediction. The prober's fix is a right-stick token in
pathfind (lane.pathfind's file, not mine).

Do not repeat: probing a Blinx 2 "no movement" with the left stick. Read the
tutorial card first.

## Attempt 1 did not finish: paused by the owner (12:55 PDT)

lane.local paused this lane at 12:55 so that lane.crashattr could use the Nova.
At that point the game was running in Test 1's second step. After the
third-person balloons popped, nav.py sent A, R3 and A, and the card read "Now
locate the 3 balloons in first-person view"
(`scratch/nav/blinx2-play.first-run-*/003-r3.png`). The Nova has run other
titles since then, so that state is gone. Attempt 2 starts again from launch.

After run 6, all of this ran on the live game (none of it was a fresh launch):
- `center1` (240 s, third person): RX held continuously near the dead zone.
  No balloon ever centred, because RX 12500 does not yaw and 13500 yaws half
  a screen per second (`scratch/cal`), so there is no proportional range.
  Use pulses.
- `center3` (first person, `center.py`): it never popped a balloon. Two
  bugs, both visible in the frames:
  1. The detector found the crosshair, a ring at (0.5, ~0.48) that is
     sometimes olive-green. It "dwelled" on the ring at dx ~0, y 0.44 five
     times.
  2. The lower-half mask, which exists to hide the player in third person,
     hid every balloon. With RY held, the first-person view kept looking up
     at the dome, which put the balloons at y 0.6-0.85. In first person,
     pitch acts as a rate, as yaw does, so pulse RY rather than hold it.
- Third person, what worked (run 5): RY held at -32000 (run 6, at -22000,
  never drew the lock-on arc), with RX pulses at 22000 lasting |dx|*2.0 s.

## Attempt 2: Test 1 end to end (run 7, `test1.py`), 13:30-13:37 PDT

| phase | result |
|---|---|
| boot | the title came up at 104 s, then A through Story Mode, Load Game and the cards to Test 1's HUD |
| tp, gain 2.0 | **failed for 300 s.** The yaw swung between +0.4 and -0.4 widths and never settled. adb adds ~0.15 s to every pulse, so run 5's pass at this gain was luck |
| tp, gain 0.6 (resumed on the live game) | one dwell, card at 20 s: balloons done |
| fp: A, R3, A, then RX and RY both pulsed, crosshair ring masked | **all 3 popped in 22 s** (lock-on arc, confetti); card "Good. Click the Right thumbstick to return to normal view." |
| nav.sh: R3, A, LY up | "Now for movement. Move the Left thumbstick..."; **the player ran through the flag gate** and the next card ("Press A to jump") came up (`frames/walk-sheet.jpg`) |

## 600-s confirmation (`confirm.py`, 13:37-13:48 PDT): PASS, pending frame review

The run lasted 641 s and made 31 cycles of 20 s each:
- a frame before moving;
- walk forward on LY for 1.2 s, with a frame in the middle;
- walk back for 1.2 s, with a frame in the middle;
- a double jump on every third cycle.

Every cycle moved the picture, with a mean grey difference of 9.5 to 29.3.
The longest gap between frames was 23.6 s. The strip is
`frames/confirm-600s-strip.jpg`. The battery was not charging (USB 791 mA in,
battery current 0 to -168 mA, level flat at 80%), but the run was not
unplugged either. I wrote no charge nodes.

Next lane, do not repeat:
- Pulse the sticks over adb at gain 2.0. The overshoot is mostly adb's
  latency.
- Mask the lower half in first person.
- Use a colour-only balloon test near the crosshair, which is olive-green
  on its edge.

Test 1's remaining steps (the jump onto the container, then Tests 2-7) have
not been driven. The confirmation ran in Test 1's open area. Reach it with
`test1.py`, then send `nav.sh "press R3" "press A"`.

Detector checks before the run (`scratch/dettest.py` on center3's frames):
the ring and the centre dot no longer read as a balloon, and the real
balloons at y 0.5-0.75 are found.
