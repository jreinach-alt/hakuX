lane.forzasurf1010 -- does the default-on surfgpu route remove Forza's surface-download wait? (#433, 0.5)

State: draft

Lane: forzasurf1010          Issue: none (dispatched directly by lane.local, #433 umbrella)
Base: master @ 510dacff37
Files: docs/lanes/forzasurf1010/NOTES.md, docs/lanes/forzasurf1010/PR.md, docs/lanes/forzasurf1010/WAITING,
  docs/testing/titles/routes/forza-soak1010.route, docs/testing/predictions/forzasurf1010-ab.json
Prediction: docs/testing/predictions/forzasurf1010-ab.json (registered, a_ref=b_ref=ab1acc4154)
Needs device: yes (Nova, used)    Needs NDK: no

Working. Verification run confirmed the drive route reaches moving play (NOTES section 3). Pilot
pair (A1 `HAKUX_SURFGPU=0`, B1 `HAKUX_SURFGPU=1`) read: both valid (switch state confirmed, moving
car confirmed). `sg_judge.py`'s V4/P3/P4 came back void/no-data from a judge-tool gap, not a real
event -- `near30/decompose.py` needs a `ROUTE H:M:S mark gameplay` line in `run.log`, which
drive.py's screen-aware `mark` routes never write there (only to device logcat and
`route-state.tsv`); traced and worked around with a scratch decompose.py run (NOTES section 6).
Real reading: no thermal pause either arm; `surfupd`'s wait is removed (6.64 -> 0.14 ms/flip) but
the total `[sdcall]` wait only falls 23% (17.59 -> 13.48 ms/flip, P2 fails its ratio ceiling)
because `range` (5.71 -> 9.42) and a new caller `tobuf` (3.41) absorb it -- outcome (b), the wait
moved, not outcome (a) or (c) cleanly. gfps still rose +1.56. Pilot verdict written to
`dispatch/pilots/forzasurf1010.ok`; A2/B2 queued to complete the registered 2 runs/arm, see
WAITING. Decision (step 5 of the brief) still to come once A2/B2 land. See NOTES.md for detail.
