## #433 -- 2026-10-02 07:40 PDT

[lane.snapdrive] Dispatched runs can now play `drive` routes, once this
folds. Branch `lane/snapdrive`, PR.md on it.

- **The snapshot now ships the driver.** `dispatcher.sh` snapshots
  `titles/drive.py`, `classify.py`, `waitfor_match.py` and every
  `titles/drive-profiles/*.toml` plus `*/*.png`, by glob, without the
  `selftest/` fixtures. The profiles are in `src_hash`, so a profile added
  later is a re-exec and needs no dispatcher.sh edit. Scratch snapshot: 18
  files before, 67 after. `bin/titles/route.sh --check
  routes/sonic-heroes.drive.route` fails before ("no profile") and passes
  after.
- **A worker now snapshots at startup.** Without that, this fold would not
  have shipped the new files at the first re-exec, because the re-exec is
  carried out by the old code and copies the old list (the same gap that
  left vsh_score.py out of bin/ on 09-25). No restart is needed. The first
  re-exec after the fold ships everything.
- **`request.sh --route` now checks the route as the run sees it**
  (`<rdir>/route.txt`, the serving snapshot's route.sh). It refuses a
  `drive` route whose profile the serving snapshot or tree lacks. It also
  refuses every `waitfor`/`press-until` route: their reference crops never
  reach the result dir, so such a run dies at line 1 and the soak runs on
  with no input. Today that is only `castlevania-cod.first-run`, which
  could not run dispatched anyway.
- **Next item, not done here:** make waitfor crops travel with the request.
  request.sh would embed `routes/refs/<route>/*.png` in the request, and the
  dispatcher would write them beside `route.txt` where `ref_path` looks
  (`<rdir>/refs/route.txt/`, or rename the played file to
  `<route>.route`). That changes the request format and the dispatcher's
  route writer, so it is a separate lane. Until then, port a waitfor route
  to a `drive` profile, as castlevania-cod.drive does.
- **Selftest:** see PR.md for the full run result.
