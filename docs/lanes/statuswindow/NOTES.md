# lane.statuswindow -- #433: the title table must not overstate a title's fps

## The mechanism (found by reading, then confirmed with a fixture)

`titles05()` in `docs/testing/jobs/status_html.py` reads a title's fps two
ways: from a stored `verdict.json` (title_verdict.py's own full-gameplay-window
score, mark-to-`soak end`), or, when none exists yet, from a "soak" fallback
that called `_soak_read()` -- the Ghoulies gate's fixed 90-240 s slice,
anchored at the first `hakuX-perf` line in the capture. That fallback set
`reached: "unconfirmed"` unconditionally, so a slice-only reading could never
by itself satisfy `bench` (which needs `reached == "yes"`) and could never
show a title in the `soak`/`playable` (Playable-candidate) stage. What it
COULD do, and did, is print the slice's fps and share -- "59.9 fps, 100%" --
in the fps cell and the per-device detail line, tagged only "soak" with no
hint that the number came from 150 s of the run, not the whole thing. A title
that ran fine for its first four minutes and then hung or fell to a crawl
still showed those numbers, with a "benchmark at MAX" or "20-min soak" next
step, reading as nearly Playable when the real run was nowhere close.

lane.verdict433's numbers (Kabuki 22-47%, Bruce Lee 81% with a 21 s hang,
BF2 MC / D&D Heroes 0%) are exactly what re-scoring those captures with
`title_verdict.py`'s real mark-to-end window gives instead of the slice.

## The fix

- `title_verdict.py`: `judge()` takes `write_contact_sheet=False` to skip
  `contact_sheet()` (which writes `contact.png` into the result dir). A
  status render is read-only by design (see the `release05`/`titles05`
  docstrings) and must not write into `dispatch/results` on every tick;
  writing `verdict.json` and `contact.png` stays `table.py --judge`'s job
  (run by an operator or the arms job), which is unchanged and still writes
  both. `main()` is unaffected (its call keeps the default `True`).
- `status_html.py`:
  - `_meas_from_verdict()` is the one place that turns a title_verdict.py-shaped
    dict (a loaded `verdict.json`, or a live `judge()` result) into the
    `measured` row's fields -- fps, share, `reached`/`crash`/`hang`, and a new
    `audio` flag (true on any `audio:` entry in `failures`, not just the
    first-named failure). The verdict.json branch and the new soak branch
    both call it, so they can't drift apart.
  - The soak fallback now calls `title_verdict.judge()` (imported lazily via
    `_title_verdict_module()`, `None` and a graceful fallback if it cannot be
    imported) on any finished request whose `request.json` carries a route
    and a `run.log` -- title_verdict.py's own criterion for what it can score
    (`table.py`'s `judge_missing()` uses the same test). That gives the real
    `reached_gameplay`/`hang`/`crash`/share, so a title that hung or fell
    short now reads that way and lands in `blocked`/`below`, not `soak`.
  - A route-less request (no mark to score a window from) still falls back to
    `_soak_read()`'s slice, now explicitly flagged `screen_only` and worded
    "screen: 90-240 s only, N gfps samples" everywhere it is shown (the fps
    cell's sub-line and the detail popup), so it can never be mistaken for a
    verdict. Its `reached` stays `"unconfirmed"`, so (as before the fix) it
    still cannot satisfy `bench` on its own.
  - `soak-gfps.json` (the per-result cache; results don't change once `DONE`)
    is renamed `soak-live.json` since its shape changed -- a stale cache in
    the old shape would otherwise be silently reused.
  - `_title_detail()` now prints `, hang` / `, audio short` explicitly per
    measured device, instead of folding everything into the single `verdict`
    string (which only ever named the FIRST failing criterion).

## `docs/testing/titles/table.py`: not changed, on purpose

`table.py`'s own listing (`rows()`/`main()`) reads only `results/*/verdict.json`
and already shows every field (`fps_ok_share`, `hang`, `audio_short`, ...) as
its own column, straight from title_verdict.py's full-window score -- it never
had a slice-based fallback to begin with (`--judge` calls title_verdict.py
itself, the official full-window judge, unconditionally). The brief lists it
as a file "where it renders the table," but the rendering with the actual bug
is `status_html.py`'s HTML table; I found no overstatement in `table.py`
itself and no change was needed there.

## Proof

- `docs/testing/jobs/selftest.d/99-status-fullwindow.sh`: two synthetic
  results sharing one logcat shape -- 100% at 60 fps in the 90-240 s slice,
  then ~8 fps (under the 28.5 bar) from 255 s to the end. One has a route
  (title_verdict.py can score its full window: share reads ~23%, `below`
  stage, never a candidate); one has none (falls back to the slice, reads
  ~100%, but is labelled `screen_only` / "screen: 90-240 s only" and still
  never a candidate). A monkeypatched mutant (`_title_verdict_module` forced
  to `None`) proves the first case would ALSO read the ~100% slice without
  the fix -- i.e. the checks exercise the fix, not a fixture quirk. Verified
  red against the pre-fix code (`git stash` the two source files, rerun,
  confirm `FAIL`/traceback; restore, confirm green) before committing.
- `SELFTEST_ONLY="60-status.sh 62-status-freshness.sh 63-status-lanes.sh
  64-status-html.sh 65-status-objective.sh 66-status-titles.sh
  67-status-measured.sh 89-title-verdict.sh 99-status-degraded.sh
  99-status-escalation-items.sh 99-status-fullwindow.sh" bash
  docs/testing/jobs/selftest.sh` -- see the PR for the result; run in the
  background because the full fragment set exceeds a 120 s foreground call.
- Local render (real `status.sh --print`, not the selftest fixture above): the
  `docs/lanes/titles05/fixture` harness (`synth.py` + `run_fixture.sh`) plus
  one extra result -- a title named "Kabuki Warriors", the same logcat shape
  as the selftest, but with a 40 s gap (255 s to 295 s) standing in for the
  hang lane.verdict433 reported -- with no `verdict.json`. Before the fix,
  `S._soak_read()` on that result dir reads `(60.0 fps, 150 samples, share
  1.0, ...)`: exactly the false "100% at 28.5+" the brief describes. After the
  fix, the rendered row reads:

      Kabuki Warriors ... nova: 60 fps, 24% at 28.5+, reached gameplay yes,
      hang, audio short; fails: hang: 40.5 s without 60 guest flips after
      the mark (full window; no verdict.json yet) ...
      stage: blocked (red) -- next: fix the hang

  the full 90-240 s slice alone would have read 100%; the full window reads
  24%, the hang and audio flags print explicitly, and the row is `blocked`,
  never a Playable candidate. (Render commands aren't reproduced here --
  they build a scratch copy of `docs/lanes/dash432/fixtures/1624` via
  `docs/lanes/titles05/fixture/synth.py` and `run_fixture.sh`, add the one
  extra result above, and are not part of the repo; ask lane.statuswindow's
  session log, or rebuild from the steps above, to reproduce.)
