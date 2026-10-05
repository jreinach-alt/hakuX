# accuracy804 (re-open): the owner sees no rival cars on the #804 fix build (#804)

State: draft (waiting on two queued Nova runs; the Nova is under the owner's hold)

Lane: accuracy804          Issue: #804
Base: master @ 6f463a0ae2
Files: docs/lanes/accuracy804/NOTES.md, docs/lanes/accuracy804/OUTBOX.md, docs/lanes/accuracy804/PR.md, docs/lanes/accuracy804/WAITING, docs/lanes/accuracy804/rallisport-804f.route, hw/xbox/nv2a/pgraph/vk/reports.c
Prediction: none: a survey of car presence (screencaps) and visibility-test values (logcat); no pgraph golden is claimed to move
Needs device: yes (Nova: two queued 240 s runs, 1791166524 and 1791166528)    Needs NDK: no
Release note (none): instrumentation only, off unless HAKUX_OCCL_LOG / HAKUX_OCCL_WAIT are set.

**What the owner saw.** Debug 0.4.1-1004-064ca7aa43 on the Nova: no flicker, and no NPC cars or shadows at all.

**What the captures show on that exact code.** `git diff 510ebb25f2 064ca7aa43 -- . ':!docs'` is empty, so the
owner's APK is the code of my two patched bursts and of lane.local's 600 s hold. All three show rival cars:

| capture | frames | rivals |
|---|---|---|
| patched-run1 (`runs/patched-run1/sheet.jpg`) | race clock 5.15-9.57 | a rival far ahead; the Nissan lands beside the camera at 7.03 and fills the frame 7.36-8.32, body in every frame of the worst triple |
| patched-run2 | the same pass | the same |
| lane.local's hold (`~/hakux-work/perf/2026-10-04-ralli804-fps/run/frames/015-gameplay.jpg`, `016-probe-a.jpg`) | grid 00:00.00; 06.67 | Beetle and Corolla on the grid; the Nissan beside the camera |

**No car-present capture of the owner's session exists yet, and no capture reproduces the absence.** Every
capture ran the golden HDD (`titles.qcow2`, pathfind's Single Race / Safari SS1 / Ford Escort profile) with the
player standing at the start. The owner plays on `hdd.img` with their own profile and options; mode, track and
driving are unknown.

**Instrument (this PR).** `hw/xbox/nv2a/pgraph/vk/reports.c`, `pgraph_vk_process_pending_reports_internal()`:
`HAKUX_OCCL_LOG=<s>` logs per guest frame the queries read, how many were nonzero, how many submitted frames
were still on the GPU at the read, and the values handed to the guest (`hakuX-lane`, `[occl804]`).
`HAKUX_OCCL_WAIT=0` turns the #804 fence wait off in the same binary. Both default to the shipped behaviour.

**Queued** (route `rallisport-804f`: six grid/countdown shots, sixteen pass shots): fix arm
`1791166524-lane.accuracy804-3407154`, no-fix arm `1791166528-lane.accuracy804-3408923`. NOTES section 19.2 says
what each outcome means.

This PR is not ready: there is no fix to claim, and the owner's observation is not reproduced.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
