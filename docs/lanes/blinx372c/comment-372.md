[lane.blinx372c] waiting: the soak half is stopped because the live dispatcher still drops `hakuX-stall`.

- master's dispatcher.sh names the tag (PR #381).
- `/home/justin/hakuX` (the dispatcher's tree) is at c4d541bd72, 52 commits behind origin/master. It was last fast-forwarded at 03:17 PDT, before #381 folded.
- The worker snapshot `$DISPATCH_DIR/bin/dispatcher.sh` lacks the tag.
- The newest result's `logcat.spec` lacks the tag.
- No logcat on disk carries a `hakuX-stall` line.

No run was queued. **What unblocks it:** `host-tools/dispatcher_update_window.sh`. After that, one Thor perflog soak (the command is in docs/lanes/blinx372c/NOTES.md), judged by `stallread.py` against `docs/testing/predictions/blinx372c-demo-soak.json` (sha256 475ff4d9...). The prediction was registered before any stall line existed.

Corrections from the code (6c25a829ef) to the notes this lane inherited:
1. **`pDl` is not display-only.** `surface_access_callback` (the CPU-access watch in vk/surface.c) waits on `pgraph_vk_process_pending_downloads` whenever the guest CPU touches a draw-dirty surface. So pDl can be non-zero on the AHB-presenting Thor, and if it is, it means guest CPU access. That is the "own readback" world if the access is a read, or a conservative pre-write download if it is a write. The line has no read/write split.
2. **vk never increments `NV2A_PROF_SURF_TO_TEX_FALLBACK`** (only gl does). The `/0` in `S2T:6-7/0` excludes nothing, including texture.c's incompatible-shape synchronous download.
3. **The range path's coalesced wait (`cDefC`) is a direct `vkWaitForFences`.** It is not a pgraph_vk_finish, so `Sd` and `Fen` do not count it.

Four candidate hunks are named in NOTES, one per site. Only the pDl-write case overlaps vk/surface.c's watch code (surfwatch382's file).

PR #388.
