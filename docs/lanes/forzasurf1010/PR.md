lane.forzasurf1010 -- does the default-on surfgpu route remove Forza's surface-download wait? (#433, 0.5)

State: draft

Lane: forzasurf1010          Issue: none (dispatched directly by lane.local, #433 umbrella)
Base: master @ 510dacff37
Files: docs/lanes/forzasurf1010/NOTES.md, docs/lanes/forzasurf1010/PR.md, docs/lanes/forzasurf1010/WAITING,
  docs/testing/titles/routes/forza-soak1010.route, docs/testing/predictions/forzasurf1010-ab.json
Prediction: docs/testing/predictions/forzasurf1010-ab.json (registered, a_ref=b_ref=ab1acc4154)
Needs device: yes (Nova, used)    Needs NDK: no

Working. Verification run confirmed the drive route reaches moving play (NOTES section 3).
Pilot chunk of the A/B queued (A1 `HAKUX_SURFGPU=0`, B1 `HAKUX_SURFGPU=1`), see WAITING. Two more
runs (A2/B2) and the decision in step 5 of the brief are still to come. See NOTES.md for detail.
