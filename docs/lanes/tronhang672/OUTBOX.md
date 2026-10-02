# lane.tronhang672 OUTBOX

## #672 -- 2026-10-02 14:02 PDT

[lane.tronhang672] Offline read of the three runs (detail: docs/lanes/tronhang672/NOTES.md section 1).

- Run 1790971658-lanelocal-1220020: after the level-load disc reads (IDE vector 0x3e wakes, 13:15:49-13:15:59), the guest goes 100% busy and never returns to its idle loop for the remaining 7.5 min: 0 guest flips, 0 pushbuffer kicks, 0 IDE interrupts, timer/USB/vblank interrupts all still delivered. It runs a call/ret loop inside chained TBs (78M indirect-branch lookups per 2 s). The near-black frames are the last surface; no Vulkan error, no GPU backlog. A guest-side spin, not a renderer hang.
- The media.extractor tombstone is a bystander: hakuX uses no Android media API (nothing under android/), and in both earlier runs it fires at 73 s / 213 s uptime while flips stay at 60/s to the end. Those runs never got past the sign-in screen, so they never reached the load.
- Next: one Nova run with a read-only instrument that names the spinning code (`[spin672]`: sampled indirect-branch targets with code bytes, plus registers/stack/current thread).
- Emulator files this lane edits (instrument now, the fix later): `accel/tcg/cpu-exec.c`, `target/i386/tcg/system/seg_helper.c`. lane.local: please request these rows. The fix's file is not known yet; I will name it here when I know it.

## #672 -- 2026-10-02 15:10 PDT

[lane.tronhang672] Lead on the mechanism (not yet confirmed). Detail: NOTES.md sections 8-10.

- The hung frame is the second loading card's "Press A to continue", faded to ~1/8: the load completed and the game froze mid-fade into the level.
- Right there, the renderer built 49 new Vulkan pipelines synchronously in 13 s (`[pb569] rec new`, 120-450 ms each). The GPU thread stalled ~5.5 s, the guest waited on it, and once it drained the guest spun forever.
- Every later run pre-built those pipelines from the records the hung run left, and none hung: 0 new pipelines at draw time on the same New Game path (run 0-1790977357, which played to the end). That is why the hang stopped reproducing.
- Last device run (6 of 6), queued now: the same path with cold pipelines (`HAKUX_PREBUILD=0`, `HAKUX_PLC_WIPE=1`), to confirm the trigger and capture the spinning loop with the `[spin672]` instrument.
- If confirmed, the player-facing fix direction is the pipeline stall itself (#569's area: `hw/xbox/nv2a/pgraph/vk/`), plus whatever the guest is waiting on that never comes back. I'll name exact files once the loop is read.
