# vcpuwait433: Tron 2.0's slow-frame vCPU sleep is pfifo.lock in user_read; a lock-free read is the fix
State: draft

Lane: vcpuwait433       Issue: #433
Base: master @ 9550493846
Files: docs/lanes/vcpuwait433/PR.md, docs/lanes/vcpuwait433/NOTES.md, docs/lanes/vcpuwait433/OUTBOX.md, docs/lanes/vcpuwait433/capture_offcpu.sh, docs/lanes/vcpuwait433/waitsite.py, docs/lanes/vcpuwait433/decompose.py, docs/lanes/vcpuwait433/tron-newgame.route, docs/lanes/vcpuwait433/levelcheck.py, docs/lanes/vcpuwait433/userread-lockless.diff
Prediction: none yet: drafted in NOTES.md section 4. It is registered on concrete refs once the fix is on this branch, which needs the grant below.
Needs device: yes (Nova; 2 of 3 runs used: tron1 void (menu), tron2 = the brief's slow window)    Needs NDK: yes, for the fix's arm

[lane.vcpuwait433] waiting: on a grant for `hw/xbox/nv2a/user.c` and `hw/xbox/nv2a/pfifo.c` (requested from lane.local in OUTBOX.md, 2026-10-02 21:10 PDT). With it, the next session applies `userread-lockless.diff`, builds, registers the Tron + BF2 prediction and queues the arm.

**The site.** In Tron 2.0's slow window (tron2, 60 s at 27.9 fps), the vCPU is off-CPU 18.1% of the time, 6.5 ms/frame. **65.2%** of the attributed off-CPU time is `pfifo.lock` in USER MMIO, and 95.5% of that is `user_read`, a guest load of DMA_GET/PUT/REF. In tron1's 60-fps menu the same site was under 3%.

**Why the vCPU waits there.** `pfifo_thread` calls `pgraph_process_pending_reports` with pfifo.lock held. When DMA_GET == DMA_PUT and a command buffer is open, that function does `pgraph_vk_finish(STALLED)`, which waits for the render thread to submit (`wait_frame_submitted`). That is the largest named holder, 40% of the wait time. The guest's read takes the same lock to return one word, and the word is already final: GET == PUT, and only the guest writes REF. **No golden can need the wait.** An acquire load against a release store gives the read the same ordering the lock did.

**The fix** (`userread-lockless.diff`, 25+/14-, applies to master; not compiled here, because there is no build tree): `user_read` takes no lock and uses acquire loads; the stores to DMA_PUT/GET/REF and the pusher's DMA_GET advance become release stores. This is #474's pattern: stop MMIO waiting behind a GPU-paced hold.

**Premise corrections** (NOTES.md "Result"):
- The capture gate of runs 1-2 read fps as the f difference of two `hakuX-pace` lines. Lines come every 60 frames, so it always read 60.
- Near30's slow window on the New Game route is the in-engine intro, which is what tron2 recorded. The in-level (Auto Load) sleep is about 6.5 of 33 ms.
- The capture now prepares Tron's golden profile and fails closed on a frame-confirmed level (`levelcheck.py`, validated: in-level 87/89 frames, menu and credits 0/66).

| Next | P | win | cost |
|---|---|---|---|
| **A. lock-free `user_read` arm** | 0.45 (fps +5% in the slow window): the per-tid pass puts the PFIFO thread asleep for >= 86% of the vCPU's waits, so the value read never changes during a wait; the renderer is idle 18 of 45 ms, so it waits on the guest. Against: the guest may then wait on GPU results in RAM, turning freed sleep into spin | up to 4.0 ms of a 36 ms frame (27.9 -> at most 31.4 fps); BF2 unknown | grant, 1 build, 2 Nova runs |
| B. release pfifo.lock across the stalled finish | 0.3: wider, but exposes renderer state to the display thread | <= A + the 4.5% DMA_PUT share | grant, build, goldens, arm |
| C. in-level capture (run 3) | 0.85 it names the owner | knowledge only; A's arm answers it too | 1 run |
| D. per-tid holder pass (offline) | done | PFIFO thread 92% of the hold (40% named finish, 47% unsampled sleep, 6% on-CPU) | done |

Local checks: `docs/testing/preflight.sh --allow-tracker` passed at this head (territory ok, board files ok; the coverage gate did not run: gh suspended). `bash -n capture_offcpu.sh` OK. The gate's fps parse reads 33 fps on 2186958's pace lines and is empty-safe. `.scratch/replay_gate.py` replays the gate: OPEN on 2186958 at mark+28 s, ABORT on tron1 and tron2. `git apply --check userread-lockless.diff` OK on master 9550493846. `waitsite.py`'s `--detail` code runs only under its flag. Its site table on tron2 is byte-identical before and after the edit. The doa3 validation was not re-run.

Release note (none): no emulator code changes on this branch yet; the fix is a patch file pending a grant.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
