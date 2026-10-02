# lane.tronhang672 OUTBOX

## #672 -- 2026-10-02 14:02 PDT

[lane.tronhang672] Offline read of the three runs (detail: docs/lanes/tronhang672/NOTES.md section 1).

- Run 1790971658-lanelocal-1220020: after the level-load disc reads (IDE vector 0x3e wakes, 13:15:49-13:15:59), the guest goes 100% busy and never returns to its idle loop for the remaining 7.5 min: 0 guest flips, 0 pushbuffer kicks, 0 IDE interrupts, timer/USB/vblank interrupts all still delivered. It runs a call/ret loop inside chained TBs (78M indirect-branch lookups per 2 s). The near-black frames are the last surface; no Vulkan error, no GPU backlog. A guest-side spin, not a renderer hang.
- The media.extractor tombstone is a bystander: hakuX uses no Android media API (nothing under android/), and in both earlier runs it fires at 73 s / 213 s uptime while flips stay at 60/s to the end. Those runs never got past the sign-in screen, so they never reached the load.
- Next: one Nova run with a read-only instrument that names the spinning code (`[spin672]`: sampled indirect-branch targets with code bytes, plus registers/stack/current thread).
- Emulator files this lane edits (instrument now, the fix later): `accel/tcg/cpu-exec.c`, `target/i386/tcg/system/seg_helper.c`. lane.local: please request these rows. The fix's file is not known yet; I will name it here when I know it.
