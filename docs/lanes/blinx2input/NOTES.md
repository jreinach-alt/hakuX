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

Verdict on the hypotheses after run 2: H2 refuted (right stick reaches the
guest); H3 has nothing left to explain; H1 holds. Not an emulator defect, no
emulator fix and so no prediction. The prober's fix is a right-stick token in
pathfind (lane.pathfind's file, not mine).

Do not repeat: probing a Blinx 2 "no movement" with the left stick. Read the
tutorial card first.
