[lane.defaulton1017] ready: S2T_CVT, REPORT_EARLY and FLDCW_CHAIN are on by default, and IBC stays off (HNI's configuration). Release note: "about 29 fps (was 17 fps)", from HNI 35.0 ms/f against HOFF 58.9 over the same span.

The screen was stopped by the owner at 07:00 on 10-17. Every row that ran is judged in NOTES.md, which has a verdict per switch. Top Spin is out of scope: it is not a Playable and has open defects (#992, #796). Its route dropped A presses at controller select with the switches on, with the chain off, with FIST_ROUND off, and with all three switches off, so this is not judged as a regression of the flip.

Not checked: REPORT_EARLY's one-frame visibility flips in frames, and Texture_shadow_comparator beyond what #1033's run-to-run movement allows. Both are listed in PR.md.

Selftest fragments this diff needs: `10-arms-list.sh` and `20-arms-queue.sh` (it adds two committed predictions). No other fragment reads anything the diff changes; PR.md gives the reasoning.

Preflight passes every gate except territory, which fails on origin/board's own dispatchdoctor1017 rows (dispatcher.sh, request.sh, devices.sh, models.toml). None of those files is in this diff, and `[lane.defaulton1017]` holds every file it touches.
