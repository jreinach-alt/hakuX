# #412 Agent Under Fire at ~15 fps on the Nova: find what paces the frame (vCPU side)

Lane: aufire412b           Issue: 412 (0.5: listed on #433 under per-title investigations)
Base: origin/master
Files: docs/lanes/aufire412b/NOTES.md, docs/testing/predictions/aufire412b-*.json
       (profile first. A code site you find is a board request for its file, not an edit: say the file and why.)
Needs device: yes, the Nova (AUF is on the Nova only). Pilot rule: first request under 30 min, review it, then more.

## Why (evidence)

lane.aufire412 (PR #416, folded 034d46a06c 2026-09-26) removed the renderer's UBO-ring finishes: ring finishes per
60 flips 39 -> 0, Sub wait 21.9 -> 0.2 ms, GPU 40.0 -> 28.3 ms. fps did not move: 15.1 -> 15.5 in mission play,
inside the 0.9 fps A-to-A spread (its comment on #412, and docs/lanes/aufire412/NOTES.md sections 5-6). The frame
interval stays ~63-67 ms, the removed wait reappears as renderer CPU time in Surf/Tx (+10 ms) and Idle, and the vCPU
is saturated in both arms. So the frame is paced outside the renderer. #412 was reopened for that reason.

## Build

1. Read docs/lanes/aufire412/NOTES.md whole, and docs/investigations/perf-architecture.md for the vCPU levers
   (#424 code-write invalidation, #425 jump cache / block chaining, #427 build flags, #428 vCPU priority). Those
   lanes are running or folded; check each one's PR before pricing its lever for AUF.
2. The counter NOTES section 6 names: a vCPU-thread simpleperf profile over the matched pause-menu-over-scene
   window (count report-sample records, not rounded percentages), plus a wait-excluded timer on Surf/Tx to test
   for a hidden wait. Queue on the Nova via request.sh with the survey route AUF reached gameplay on (pass 1:
   0-0-y-1790433159-titleplay-p1-aufire). If PR #444 (MAX perf regimen) has folded, the soak runs at MAX; say which.
3. Price the top vCPU consumers against the frame budget and name, per consumer, which 0.5 lever lane owns it.
   Hand each finding to that lane's issue (deliver.sh send), so AUF becomes a measured case for #424/#425/#428.
4. If a fix site is AUF-specific and no lever lane owns it, write the prediction first, then ask for the file.

## Proof

- The profile's result ids, the sample counts per top symbol, and the Surf/Tx wait-excluded split, in NOTES and on #412.
- Every claim of "X ms of the frame" says what it is bounded by and which capture it was read from.

## Do not

- Do not edit board files. Do not hold the Nova over 30 min. Do not trigger CI as a self-check.
- Do not re-do the UBO-ring work; it is folded and inert on fps.
