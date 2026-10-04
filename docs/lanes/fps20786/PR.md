# fps20786: the bound behind the ~20-fps class on the Nova (#786, #747)
State: draft

Lane: fps20786            Issue: #786 #747
Base: master @ 4a3308a21e
Files: docs/lanes/fps20786/PR.md, docs/lanes/fps20786/NOTES.md, docs/lanes/fps20786/decompose.py, docs/lanes/fps20786/steps2route.py, docs/lanes/fps20786/make-routes.sh, docs/lanes/fps20786/nba-live-2005-hold.steps.jsonl, docs/lanes/fps20786/routes/fps786-nba2005.route, docs/lanes/fps20786/routes/fps786-topspin.route, docs/lanes/fps20786/routes/fps786-cs.route
Prediction: none: analysis-only (telemetry runs; bound signatures registered in NOTES.md at e95ca394c1 before any run)
Needs device: yes (Nova, up to 5 --perflog soaks via request.sh)    Needs NDK: no

Work in progress. The always-on lines of pathfind's 609-s NBA Live 2005 hold already rule out
the vCPU (guest busy 22 of 50 ms) and lock (0.9 ms) bounds. The render thread costs ~42 ms per
frame (26 on-CPU, 15.5 blocked). 42 falls in (33.3, 50], so every frame takes three VBLANKs and
reads 20.0 fps. The perflog runs split the blocked part (GPU or not) and cover Top Spin and
Counter-Strike.

Release note (none): analysis only, no emulator change.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
