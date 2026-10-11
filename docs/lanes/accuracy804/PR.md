# accuracy804 (re-open): the #804 fix keeps the rival cars; the owner's "no cars" is Career on any build (#804)

State: ready (the folding code is reports.c instrumentation, off unless HAKUX_OCCL_LOG / HAKUX_OCCL_WAIT are set; the rest is lane docs and analysis scripts)

Lane: accuracy804          Issue: #804
Base: master @ 6f463a0ae2
Files: docs/lanes/accuracy804/NOTES.md, docs/lanes/accuracy804/OUTBOX.md, docs/lanes/accuracy804/PR.md, docs/lanes/accuracy804/carpix.py, docs/lanes/accuracy804/carshare.py, docs/lanes/accuracy804/occl_read.py, docs/lanes/accuracy804/rallisport-804f.route, docs/lanes/accuracy804/rallisport-804g.route, docs/lanes/accuracy804/runs/cap1-career-sheet.jpg, docs/lanes/accuracy804/runs/career-fix/occl804.tsv, docs/lanes/accuracy804/runs/career-fix/sheet.jpg, docs/lanes/accuracy804/runs/career-nofix/occl804.tsv, docs/lanes/accuracy804/runs/career-nofix/sheet.jpg, docs/lanes/accuracy804/runs/occl-fix/occl804.tsv, docs/lanes/accuracy804/runs/occl-fix/sheet.jpg, docs/lanes/accuracy804/runs/occl-nofix/occl804.tsv, docs/lanes/accuracy804/runs/occl-nofix/sheet.jpg, docs/lanes/accuracy804/runs/presence/patched1-pass.jpg, docs/lanes/accuracy804/runs/presence/patched1.tsv, docs/lanes/accuracy804/runs/presence/patched2-pass.jpg, docs/lanes/accuracy804/runs/presence/patched2.tsv, docs/lanes/accuracy804/runs/presence/perflog1-pass.jpg, docs/lanes/accuracy804/runs/presence/perflog1.tsv, hw/xbox/nv2a/pgraph/vk/reports.c
Prediction: none: a survey of car presence (video frames, screencaps) and visibility-test values (logcat); no pgraph golden is claimed to move
Needs device: no (this attempt used none)    Needs NDK: no
Release note (none): instrumentation only, off unless HAKUX_OCCL_LOG / HAKUX_OCCL_WAIT are set.

**What the owner saw.** Debug 0.4.1-1004-064ca7aa43 on the Nova: no flicker, and no NPC cars or shadows at all.
`git diff 510ebb25f2 064ca7aa43 -- . ':!docs'` is empty, so every capture below at `510ebb25f2` or `5e16698c99`
(plus env-gated logging) runs the owner's code.

**Car-present capture (fix build).** The rival pass in Single Race, Safari SS1, filmed with screenrecord
(10 s held bursts, section 17). `carpix.py` counts the Nissan's red livery pixels in each unique video frame,
and the sheets show the race clock on every frame:

| burst | build | unique frames in the pass (race clock ~7.2-8.8) | Nissan body drawn |
|---|---|---|---|
| perflog1 | unpatched `10f14d301d` | 50 | 43 (86%); 7 shadow-only frames (9 by eye) |
| patched-run1 | the fix `510ebb25f2` | 48 | **48 (100%)** |
| patched-run2 | the fix | 51 | **51 (100%)** |

Sheets: `runs/presence/{perflog1,patched1,patched2}-pass.jpg`.

**The fix does not remove the cars or zero the visibility reads.** One binary, with the fence wait switched by
env:

| mode | fence wait off (pre-fix) | fence wait on (the fix) |
|---|---|---|
| Single Race, Safari SS1 (`runs/occl-*`) | grid cars and the pass drawn; 30.9% of reads nonzero | the same; 30.0% |
| Career, Safari SS-1, throttle held for 60 s (`runs/career-*`) | **no rival or shadow in any shot**; 2.4% nonzero | **no rival or shadow**; 2.9% nonzero |

Capture 1 (`5e4196fefd`, before reports.c changed) shows Career the same way. So the owner's "no NPC cars,
ever" is what Career's Safari SS-1 shows on this emulator with or without the fix. The owner's mode is not
confirmed, and Career is the menu default. Whether a real Xbox shows a rival there in the first minute is not
checked.

**fps on the fix build.** lane.local's 600 s hold: 534 windows, 100% at or above the 30 fps bar, median 56.5,
min 29.63. In that hold the rivals were mostly out of view.

**Not covered.** A filmed 30 s window that includes the countdown on the fix build. The grid cars are drawn in
single shots on the fix build (occl-fix c4-c6, lane.local frame 015). Those runs did not have the GPU behind the
read (`pend` = 0), so they could not have blinked either way. **For the owner's eye check, use Single Race.**

🤖 Generated with [Claude Code](https://claude.com/claude-code)
