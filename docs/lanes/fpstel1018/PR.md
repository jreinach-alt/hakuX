# fpstel1018: Forza and Buffy missed the bar -- decompose the frame, name the lever

State: draft

Lane: fpstel1018            Issue: #433
Base: master @ da6e8949dc
Files: docs/lanes/fpstel1018/NOTES.md, docs/lanes/fpstel1018/PR.md, docs/lanes/fpstel1018/FINDINGS.md, docs/lanes/fpstel1018/forza-run/run.log, docs/lanes/fpstel1018/forza-run/logcat.txt, docs/lanes/fpstel1018/forza-decompose.tsv, docs/lanes/fpstel1018/buffy-decompose.tsv
Prediction: none -- analysis only, no code
Selftest: none -- analysis only, no code
Needs device: no    Needs NDK: no

Offline decomposition of two already-finished perflog soaks that missed the
50-Playable fps bar: Forza Motorsport (17.5% of gameplay >=30fps) and Buffy
the Vampire Slayer (73.9%). No device time, no code change, no emulator-code
edits; read-only against the two result dirs.

Forza's route (`forza-soak1010`, the screen-aware `drive` script) logs its
`mark gameplay` to logcat, not to run.log in the format `decompose.py`
expects, so a synthetic minimal result dir
(`docs/lanes/fpstel1018/forza-run/`) was built from a copy of the real
run.log plus the real mark timestamp, and a symlink to the real logcat.txt,
to run the decomposer unmodified. The resulting row count (419 x 2s = 838s)
matches `verdict.json`'s own `scored_s`, independently confirming the mark.

`NOTES.md` has the Step 0 Already-tried table (forza414, belowbar1005,
near30, cloud-286, plus the brief's explicitly named #488 and the gta3fps
surface-as-texture lane, both checked directly and ruled out by this run's
own telemetry). `FINDINGS.md` has the per-title decomposition, ranked
levers, and the one lever a fix lane should take first with a falsifiable
prediction. Will flip to ready once FINDINGS.md lands.
