# failgate (#433)

Goal: a failed or unproven run goes for identification, not a re-run.

Causes measured by lane.local (stored results in `dispatch/results/*`):

1. The verdict cannot see a menu. `hitch_report.static_window` scores only
   post-mark `route-frames` and needs >= 3; with fewer it returns
   `measured: False`, and `static_window_fail` never fails an unmeasured window.
   Castlevania (1790895867-autoverdict-3359625) and Black Stone passed with no travel.
2. Nothing converted a failure into a pathing hand-off (host side now in
   `host-tools/failure_intake.py`; `request.sh` does not call its gate).
3. `title_verdict.contact_sheet` concatenates `route-frames/` then `frames/`, so
   boot samples appear mid-sheet and read as a restart.

Build order: (1) static_window fallback, (2) position-change test, (3) request.sh
admission gate, (4) contact sheet seam, (5) wall sync flags unproven passes.

Status: started. Nothing measured yet.
