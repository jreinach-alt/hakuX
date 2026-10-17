# halo1016: Halo CE cutscenes on the Nova -- quiet speech under loud music (#938), cinematic below 30 fps

State: draft

Lane: halo1016            Issue: #938, #1018
Base: master @ 61ae61dd91
Files: docs/lanes/halo1016/PR.md, docs/lanes/halo1016/NOTES.md
Prediction: none: analysis in progress
Needs device: yes    Needs NDK: yes

Deep dive into the two defects the owner heard and saw in Halo: Combat Evolved's opening
cinematic on 0.5.1-rc1 (Nova, release build at b12a313033): dialogue quiet under loud music,
and a ~47 s stretch at 8-19 gfps with a per-window floor of 49-97 ms. Work in progress; the
account per symptom and the hypothesis tables live in `docs/lanes/halo1016/NOTES.md`.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
