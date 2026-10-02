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

## #672 -- 2026-10-02 15:40 PDT

[lane.tronhang672] blocked: mechanism found, fix not built. Device runs: 6 of 6 used. Detail: NOTES.md sections 11-12.

- **Reproduced on demand.** With cold Vulkan pipelines (`HAKUX_PREBUILD=0 HAKUX_PLC_WIPE=1`) on the New Game path, Tron hangs exactly as in 1790971658: run 0-1790978946-tronhang672-3184149, card at 480 s, then 0 flips for the remaining 3.5 min. Cold: 2 hangs of 2. Warm (pipelines pre-built from earlier runs' records): 0 of 3, including the same New Game path played into live gameplay (0-1790977357).
- **Trigger:** at the post-load "Press A to continue", the renderer builds ~50 new pipelines synchronously in ~13 s. The GPU thread stalls, the guest waits on it, and afterwards one game thread spins forever.
- **The spin is game code**: thread d0008018, IRQL 0, a list walk at 0x3eb16b-0x3eb3be with budget arithmetic on `this->[0x2b4]`. It reads like a catch-up loop that never catches up after a 13-s frame. It is not a device wait and not a hakuX CPU bug.
- **Why the harness stopped seeing it:** every device that has run Tron once pre-builds its pipelines at boot. A 600-s confirmation run now would likely pass, but a player's first New Game would still hang. I have not queued that confirmation, because it would hide the defect.
- **To unblock (decision for the owner):** one device run on the deterministic repro with `HAKUX_GPL=3` (#569's uber ladder, env only, no code), plus a one-time dump of the loop function from the `[spin672]` instrument. That shows whether #569's path removes the hang and what the loop's exit waits on. The likely fix files are under `hw/xbox/nv2a/pgraph/vk/` (#569's area, not this lane's territory). If the loop waits on guest time, a narrower time-side fix may be possible.
- Emulator files on this branch: `accel/tcg/cpu-exec.c`, `target/i386/tcg/system/seg_helper.c` (the read-only `[spin672]` instrument; release note none).
