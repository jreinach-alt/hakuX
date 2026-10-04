# accuracy804: RalliSport's cars blink on alternate frames (#804): identified and fixed

State: ready

Lane: accuracy804          Issue: #804
Base: master @ 63f4827758
Files: docs/lanes/accuracy804/NOTES.md, docs/lanes/accuracy804/OUTBOX.md, docs/lanes/accuracy804/PR.md, docs/lanes/accuracy804/alt_draws.py, docs/lanes/accuracy804/rallisport-804.route, docs/lanes/accuracy804/rallisport-804b.route, docs/lanes/accuracy804/rallisport-804c.route, docs/lanes/accuracy804/rallisport-804d.route, docs/lanes/accuracy804/rallisport-804e.route, docs/lanes/accuracy804/reports-804.diff, docs/lanes/accuracy804/runs/patched-run1/capture.json, docs/lanes/accuracy804/runs/patched-run1/flicker.tsv, docs/lanes/accuracy804/runs/patched-run1/sheet.jpg, docs/lanes/accuracy804/runs/patched-run1/worst.jpg, docs/lanes/accuracy804/runs/patched-run2/capture.json, docs/lanes/accuracy804/runs/patched-run2/flicker.tsv, docs/lanes/accuracy804/runs/patched-run2/sheet.jpg, docs/lanes/accuracy804/runs/patched-run2/worst.jpg, docs/lanes/accuracy804/runs/perflog1/capture.json, docs/lanes/accuracy804/runs/perflog1/flicker.tsv, docs/lanes/accuracy804/runs/perflog1/sheet.jpg, docs/lanes/accuracy804/runs/perflog1/worst.jpg, docs/lanes/accuracy804/runs/plain1/capture.json, docs/lanes/accuracy804/runs/plain1/flicker.tsv, docs/lanes/accuracy804/runs/plain1/sheet.jpg, docs/lanes/accuracy804/runs/plain1/worst.jpg, docs/lanes/accuracy804/session804e.sh, hw/xbox/nv2a/pgraph/vk/reports.c
Prediction: none: the measurement is held screenrecord bursts on RalliSport, read by eye (the owner's flicker check); no pgraph golden is claimed to move
Needs device: yes (Nova: three held sessions, ~12 min, and three 60 s dispatched install boots, all run)    Needs NDK: no
Release note (rendering): RalliSport's rival cars no longer vanish on alternate frames (the countdown and close passes); titles that gate draws on occlusion queries read this frame's result.

**Cause.** RalliSport draws each car's body only when its last occlusion-query report says the car was visible.
After a deferred finish (FLIP_STALL, PRESENTING, STALLED, SURFACE_DOWN_FLUSH), hakuX returns to the guest once
`vkQueueSubmit` is done, and `pgraph_vk_process_pending_reports_internal()` reads the query pool at once. On Turnip
the query reset is a GPU command, so a slot the GPU has not reset yet reads as available, holding the previous
command buffer's count. The report for frame k then carries frame k-1's visibility, and the body alternates while
its (ungated) shadow is drawn every frame.

**Fix.** `hw/xbox/nv2a/pgraph/vk/reports.c` (granted to this lane): when queries are in flight, wait the fence of
every submitted frame before reading the results, as upstream xemu does. Only a finish that recorded a query pays.

| held screenrecord burst, Nova, `rallisport-804e.route` | build | flicker_score | by eye |
|---|---|---|---|
| plain1 | master `63f4827758`, non-perflog | FLICKER p90 29.4 | countdown: the cars in front vanish on alternate frames, shadows kept |
| perflog1 | master `10f14d301d`, perflog | FLICKER p90 22.1 | race clock 7.92-7.97: the Nissan beside the camera in N only |
| patched-run1 | master + fix `510ebb25f2`, non-perflog | clear p90 0.83 | race clock 7.36-7.44: body in every frame |
| patched-run2 | the same | clear p90 1.02 | race clock 7.39-7.42: body in every frame |

The earlier frame-dump captures (NOTES sections 9-15) never blinked. The `images` dump waits on a fence every
frame, which is the same remedy as the fix. **Not measured:** the fps cost of the wait in titles that run many
queries per flip (RalliSport ~30). RalliSport's Playable confirmation (600 s fps verdict plus the owner's flicker
check) measures it.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
