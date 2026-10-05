# accuracy804 (re-open): the owner sees no rival cars on the #804 fix build (#804)

State: draft (waiting on two queued Nova runs, Career with the throttle held, fence wait off/on)

Lane: accuracy804          Issue: #804
Base: master @ 6f463a0ae2
Files: docs/lanes/accuracy804/NOTES.md, docs/lanes/accuracy804/OUTBOX.md, docs/lanes/accuracy804/PR.md, docs/lanes/accuracy804/WAITING, docs/lanes/accuracy804/occl_read.py, docs/lanes/accuracy804/rallisport-804f.route, docs/lanes/accuracy804/rallisport-804g.route, docs/lanes/accuracy804/runs/cap1-career-sheet.jpg, docs/lanes/accuracy804/runs/occl-fix/occl804.tsv, docs/lanes/accuracy804/runs/occl-fix/sheet.jpg, docs/lanes/accuracy804/runs/occl-nofix/occl804.tsv, docs/lanes/accuracy804/runs/occl-nofix/sheet.jpg, hw/xbox/nv2a/pgraph/vk/reports.c
Prediction: none: a survey of car presence (screencaps) and visibility-test values (logcat); no pgraph golden is claimed to move
Needs device: yes (Nova: two queued 240 s runs, 1791167617 and 1791167624)    Needs NDK: no
Release note (none): instrumentation only, off unless HAKUX_OCCL_LOG / HAKUX_OCCL_WAIT are set.

**What the owner saw.** Debug 0.4.1-1004-064ca7aa43 on the Nova: no flicker, and no NPC cars or shadows at all.

**Car-present captures on the owner's code.** `git diff 510ebb25f2 064ca7aa43 -- . ':!docs'` is empty. Two runs
of one binary (`5e16698c99`, the fix plus an env-gated log), Single Race / Safari SS1, fence wait on and off:

| | fix arm `1791166524` | no-fix arm `1791166528` |
|---|---|---|
| grid, race clock 00:00.00 (`runs/occl-*/sheet.jpg`, c4-c6) | Beetle in front of the camera, Corolla to its left, both drawn | the same |
| the pass | Nissan's rear fills the frame at 07.39 and 08.14 | the same at 07.76 and 08.32 |
| visibility queries nonzero, race window | 30.0% (6,545 of 21,848) | 30.9% (6,907 of 22,363) |
| query batches with every report 0 | 37 of 745 | 48 of 747 |
| submitted frames still on the GPU at the read (`pend`) | 0 in every frame | 0 in every frame |

On this path the fix neither zeroes the visibility reads nor removes the cars. With `pend` = 0 in both arms, the
fence wait had nothing to wait for in these runs, so they cannot show the blink either way.

**The owner's symptom on code from before the fix.** Capture 1 (13:48, ref `5e4196fefd`, before reports.c
changed) took CAREER, the item lit on the game menu, to Safari SS-1. It shows POS 4 OF 4 and no rival or shadow
from race clock 4 to 46 (`runs/cap1-career-sheet.jpg`), and 0 rival body draws in its 600 dumped race frames.
Capture 3 at the same code, Single Race, has them in 414. Career's start places the player alone at the banner;
Single Race starts four cars on a grid.

**Queued** (`rallisport-804g.route`: Career, throttle held ~50 s, a shot every ~2 s): no-fix arm
`1791167617-lane.accuracy804-3666473`, then the fix arm `1791167624-lane.accuracy804-3669384`. NOTES section 20.3
says what each outcome means.

This PR is not ready: the owner's mode is unconfirmed and the Career drive is unread. No fix is claimed here.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
