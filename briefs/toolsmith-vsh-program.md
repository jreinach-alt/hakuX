# Run nxdk_vsh_tests on a handheld, so hakuX's printed values can be diffed against silicon's

Lane: toolsmith (standing). No tracker issue: this is harness work. Its consumers are #112 item 4 and #223.
Specified by: lane.xbox, after running the program on the project console
(PR #225; results on #112 and #223).
Base: origin/master **after PR #206 folds**. #206 makes the dispatcher hash every
file its snapshot ships, which is what lets edits to `make_test_iso.py` and
`extract_results.py` reach the workers at all.
Files: docs/testing/request.sh, docs/testing/dispatcher.sh, docs/testing/run_disc.sh,
docs/testing/make_test_iso.py, docs/testing/extract_results.py,
docs/testing/vsh_score.py (new), a `selftest.d/NN-<concern>.sh` fragment,
docs/lanes/vsh-program/NOTES.md.
Needs device: yes (one handheld run proves the path). Needs NDK: no. Prediction:
none; this is a harness change. Its proof is the refusal test and one end-to-end run.

## What silicon already has, so there is something to diff against

These are lane.xbox's 2026-09-25 console runs:
`/home/justin/hakux-work/hardware/runs/2026-09-25-vsh/{stage1b,stage2}/console`.

- It ran three times, about 53 s each, and every run handed back to the dashboard.
- A repeat run is byte-identical.
- The six suites with published 2022 goldens differ from them only by font.
- Every test writes `<name>.txt` beside its PNG with the exact printed values.
- Exceptional Float and SpyVsSpy have their first silicon captures.

The program is at `~/nxdk_vsh_tests`, branch `hakux/completion-marker` (`c3dde45`),
built with nxdk `bafba08` (pbkit_extensions). The build needs `NXDK_DIR` and
`BISON_PKGDATADIR=~/.local/nxdk-tools/root/usr/share/bison`, or the prewarm dies
in fp20compiler.

## The job

1. **request.sh** accepts a vsh disc: `--base-iso` plus a program marker, for
   example a `"program": "vsh"` field. `--only-tests` names vsh suites.
2. **make_test_iso.py** builds the vsh disc. The disc must CONTAIN
   `vsh_tests.cnf`, a line-per-suite list built from the requested suite names.
   It must NOT inject the pgraph JSON config into a vsh disc.
3. **THE TRAP, which is also the falsifier.** This build ASSERTs and waits forever
   when `d:\vsh_tests.cnf` is missing (`debug_output.cpp` PrintAssertAndWaitForever).
   Refuse such a disc AT QUEUE TIME. Otherwise every run burns the 900 s timeout
   with the emulator hung and the device awake. The selftest fragment proves the
   refusal. Show it refusing a cnf-less disc, and show the old code accepting it,
   in a scratch worktree, red for that reason and not an import error.
4. **run_disc.sh.** From DVD the program writes to `e:\nxdk_vsh_tests`. Completion
   is `e:\nxdk_vsh_tests\log.txt` containing "Testing completed normally". Never
   use the run's duration. `extract_results.py -d nxdk_vsh_tests` pulls the PNGs
   and TXTs.
5. **dispatcher.sh.** A vsh result is not a pgraph result. Skip `score_sweep.py`'s
   golden scoring for it and run `vsh_score.py` instead. Record which program ran
   in the result's metadata so no pgraph comparison ever pools with it.
6. **vsh_score.py.** An EXACT diff of `<suite>/<test>.txt` against the console's.
   PNGs are secondary; it's the same program and font, so a pixel diff is valid
   there too. Report per test: identical, differs (show the lines), or missing.

## Where to run the proof

Desktop (lavapipe) is a cheap first check of the plumbing. But NaN, Inf and
denormal handling is exactly where lavapipe and Adreno may differ, so the
handheld result is the one that gets scored. Run one small suite end to end on
a handheld through `request.sh`. The Nova may be held for battery (see
`dispatch/hold/nova.why`), and the Thor serves meanwhile.

## Done when

- A vsh disc is refused without its cnf and accepted with it (the selftest
  fragment is green, and red against the old code).
- One handheld run completes on the log marker.
- `vsh_score.py` prints a per-test verdict against the console's text.
- The PR carries the lane template with its `Files:` line, preflight passes,
  NOTES are written, and the PR is marked ready.

The hakuX-vs-silicon verdicts on Exceptional Float and RCP are the first
product. Post them on #112 and #223.
