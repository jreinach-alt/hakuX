Lane: blinx372b            Issue: #372
Base: master @ 7a2036020d
Files: docs/testing/dispatcher.sh, docs/lanes/blinx372b/NOTES.md, docs/lanes/blinx372b/run_selftest.sh, docs/lanes/blinx372b/pr-body.md, docs/lanes/blinx372b/sites.py, docs/lanes/blinx372b/workread.py
Prediction: none: the soak is a single-arm perf read that needs this PR folded first (the dispatcher runs from master's tree)
Needs device: yes    Needs NDK: no

The dispatcher's logcat allow-list ends in `*:S` and dropped every perflog line that splits the renderer's frame: `hakuX-stall` (which surface-download site fires), `hakuX-rpbrk`, `hakuX-cpu`, `xemu-gpu`, `xemu-sfp`. This adds them. `hakuX-pace` was already added by lane.titlerun.

Next, after this folds: one perflog soak of Blinx on the Thor, read the per-site `hakuX-stall` counters, name the site behind `Sd2`.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
