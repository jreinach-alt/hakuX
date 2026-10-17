# gta3drive1017: Grand Theft Auto III drops into the teens while driving (#433)

State: draft

Lane: gta3drive1017            Issue: #433
Base: master @ 9abd80e90c
Files: docs/lanes/gta3drive1017/PR.md, docs/lanes/gta3drive1017/NOTES.md, docs/lanes/gta3drive1017/owner_play.tsv, docs/lanes/gta3drive1017/tools/owner_play.py, docs/lanes/gta3drive1017/tools/drive_split.py, docs/lanes/gta3drive1017/routes/gta-3-drive.route, docs/lanes/gta3drive1017/routes/refs/gta-3-drive/fist-hud.png
Prediction: none: analysis-only so far (the pilot is a route proof and a wait split, not an arm)
Needs device: yes    Needs NDK: yes

GTA III (5454000E) is rated Playable on the Nova from an on-foot route. The owner's 10-17 play on 0.5.2-rc1 (Turnip,
mode 3) dips into the teens while driving. This lane locates the wait and fixes it.

Step 0 is done (`docs/lanes/gta3drive1017/NOTES.md` sections 1-2). The owner's capture reads (section 3): in the
dips the PFIFO thread is blocked ~28 ms per flip, neither parked nor on a CPU, while texture dirty walks cost
microseconds. Pipeline creation is at most ~2 ms per flip. The guest stays about a frame of pushbuffer ahead all
through gameplay, so the PFIFO thread sets the pace and the dips are that thread getting slower.

Next: a driving route (`routes/gta-3-drive.route`, not yet proven) and two Nova pilots. One is a perflog build with
FRAMETRACE and GPUXFR, which splits the PFIFO thread's blocked time into finishes by cause, fences, lock and GPU
time. The other is the plain build. `tools/drive_split.py` reads both. Section 4 of NOTES.md says what each outcome
means.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
