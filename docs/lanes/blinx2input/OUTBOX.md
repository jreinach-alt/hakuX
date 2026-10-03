## #670 -- 2026-10-02 13:35 PDT

[lane.blinx2input] mechanism found (run 2 of 6): **not an emulator input
defect.** The "gameplay" both pathfind runs probed is Blinx 2's Challenge
Test 1 of 7, whose card says "Move the Right thumbstick to look at the 3
balloons around you"; movement and jump stay locked until then. pathfind's
vocabulary has no right stick (`STICK:` is LX/LY only), so none of its 30+
probes could pass the test. On the Nova, the right stick DOES reach the
guest: RX orbits the camera and RY tilts it (frames
`scratch/run2/060..079` on lane/blinx2input's worktree). The left stick and A
did nothing in Test 1 under my driver too, as the game intends.

Territory: no emulator files. Only `docs/lanes/blinx2input/**`. The fix for
the prober is in lane.pathfind's tool (a right-stick token, e.g.
`RSTICK:<dir>:<s>`); I do not edit it. Next: pass Test 1 with slow camera
sweeps, show the player moving, then the 600-s confirmation.

## #670 -- 2026-10-02 14:05 PDT

[lane.blinx2input] Test 1's balloon step PASSED on the Nova under right-stick
input (run 5): a closed-loop driver centred each balloon, the game's red
lock-on arc filled, all 3 popped, and the tutorial advanced to "Now let's try
first-person view. Click the Right thumbstick." Blinx 2's input works end to
end in hakuX; there is nothing to fix in the emulator. Gotchas for any
driver: RX below ~1/3 deflection does not yaw (dead zone); pitch springs
back on release, yaw persists. Next: finish Test 1 by hand (nav.py), show
the player walking, then the 600-s confirmation.

## #670 -- 2026-10-02 13:38 PDT

[lane.blinx2input] **Blinx 2 moves.** A fresh launch on the Nova went
through all of Test 1's camera steps under right-stick input, driven by
`docs/lanes/blinx2input/test1.py`:
- the third-person balloons;
- R3 into first person;
- the first-person balloons;
- R3 back to the normal view.

The tutorial then unlocked movement ("Move the Left thumbstick to walk or
run through the flag gate"). Under LY the player ran through the gate, and
the next card ("Press A to jump") came up. Frames:
`docs/lanes/blinx2input/frames/walk-sheet.jpg` and
`frames/balloons-fp-sheet.jpg`.

This confirms the mechanism: the emulator's input path has no defect. The
probes stalled at the camera gate because they never sent the right stick.
No emulator files are involved, and the territory is `docs/lanes/blinx2input/**`
only. The 600-s confirmation is running now from this live state.

## #670 -- 2026-10-02 13:48 PDT

[lane.blinx2input] **600-s confirmation: PASS, pending the owner's frame
review.** Blinx 2 (4D530065) on the Nova, at device defaults, ran from
13:37:25 to 13:48 PDT in Test 1's free-movement area. The driver was
`docs/lanes/blinx2input/confirm.py`.
- **Window:** 641 s, 31 cycles. One cycle ran every 20 s (the longest gap
  was 23.6 s) and captured 3 frames:
  - a frame before moving;
  - a frame 0.6 s into a 1.2-s walk forward on LY;
  - a frame 0.6 s into a 1.2-s walk back.

  Every third cycle also sent a double jump (A, A).
- **Motion:** all 31 cycles moved the picture. The mean grey difference was
  9.5 to 24.9 for the forward walk and 17.9 to 29.3 for the walk back, with
  no cycle under 5. In the frames, the player walks away from the camera and
  back toward it, and wanders from the gate area down to the lower floor by
  the stairs. The HUD stayed up and the FPS counter read 22-30 throughout.
  At 620 s the game was still live.
- **Strip for the frame review:**
  `docs/lanes/blinx2input/frames/confirm-600s-strip.jpg`. It holds the
  "pre" frame of each cycle, 32 frames across 638 s. All 94 frames are in
  `scratch/confirm1/` in the lane worktree.
- **Battery (said exactly):** the Nova stayed on its USB link, and I did
  not write the charge nodes because that needs approval.
  - USB input read 791 mA.
  - Battery status read "Discharging".
  - Battery current read 0 to -168 mA, which is roughly net zero.
  - Level held at 80% from start to end.

  The battery was not charging, but the USB supply carried most of the
  load. This is not a true unplugged run.

Not run: the brief's prediction arms (Blinx 1 still moves, one other title).
They do not apply, because no emulator code changed, so there is nothing
that could regress. PR.md is set ready.
