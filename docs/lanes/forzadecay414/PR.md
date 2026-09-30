# lane.forzadecay414: vk/surface.c clears a slot's invalidation stamps when its fence is waited (#414)
State: draft

Lane: forzadecay414-fix   Issue: #414
Base: master @ 146b8887db (merged into this branch as eec025dd37; the branch began on 85347ffbd1)
Files: docs/lanes/forzadecay414/NOTES.md, docs/lanes/forzadecay414/OUTBOX.md, docs/lanes/forzadecay414/PR.md, docs/lanes/forzadecay414/judge.py, docs/lanes/forzadecay414/queue_fix.sh, docs/lanes/forzadecay414/register_fix2.py, docs/lanes/forzadecay414/register_fix3.py, docs/testing/predictions/forzadecay414-fix-auf.json, docs/testing/predictions/forzadecay414-fix-forza.json, docs/testing/predictions/forzadecay414-fix-forza2.json, docs/testing/predictions/forzadecay414-fix-forza3.json, docs/testing/predictions/forzadecay414-fix-pixels.json, docs/testing/predictions/forzadecay414-fix-pixels2.json, docs/testing/predictions/forzadecay414-fix-pixels3.json, hw/xbox/nv2a/pgraph/vk/surface.c
Prediction: docs/testing/predictions/forzadecay414-fix-pixels3.json @ 82cd41a840fc, docs/testing/predictions/forzadecay414-fix-forza3.json @ 3d3587def921 (current; earlier files kept as registered)
Needs device: yes    Needs NDK: yes

Release note (performance): Forza Motorsport no longer slows down over a race (a surface list grew without bound)

## The defect

Since #517 (fold 09050ddbe5), `r->invalid_surfaces` grows without bound in Forza Motorsport's race.
`invalidate_surface()` stamps a surface invalidated inside the open command buffer with
`invalidation_frame = r->current_frame`, a ring-slot index that nothing resets. `surface_in_flight()`
reads a slot that is current or submitted as busy, and in steady state every slot is one or the other,
so a stamped surface can never be pruned. The one reset was `pgraph_vk_flush_all_frames()` on each
surface-to-texture bind, and #517 moved that flush to the copy branch. The list is walked on every
texture bind (~800 a flip), so on the Thor the race fell from 12 to 2 fps as the list reached ~4000.
On the Nova, the list reached ~2000 by t = 230 s, and every run was cut at 208-276 s (lmkd, xemu 4.4 GB PSS).

## The change

One hunk in `vk/surface.c`: `pgraph_vk_drain_deferred_surface_releases(r, frame)`, which runs exactly
when that slot's fence is known complete (the frame rotation, `pgraph_vk_flush_all_frames` for slots
other than the current one, and the finalizers), also sets `invalidation_frame = -1` on every invalid
surface stamped with that slot. #517's move of the flush stays. A submission count was the other option
and was not taken, because `submit_count` also counts the render thread's inline submits, which do
not rotate the slot.

## Evidence (NOTES sections 5, 8)

| run | ref | fps rows t = 150..330 | invalid max / last | list walk ms/flip first -> last |
|---|---|---|---|---|
| `1-1790624588-forzadecay414-3394734` | f82e7e87fe, before #517 | 16 20 20 28 26 26 28 | 199 / 17 | 0.08 -> 0.12 |
| `1-1790625108-forzadecay414-3486226` | 10fe2f59a7, the fix | 20 20 28 28 26 28 26 | 10 / 9 | 0.06 -> 0.06 |
| `1-1790639501-forzadecay414-151099` | 10fe2f59a7, the fix | 20 22 26 28 26 28 26 | 10 / 9 | 0.04 -> 0.05 |
| `-3394828`, `-r2`, `-r3` | 09050ddbe5, #517 | 12 10 6 / 12 10 4 / 14 10 2, then cut | 1915-1996 | 1.68 -> 8.96 |
| `1-1790624589-forzadecay414-3394871` | 85347ffbd1, master | 12 10 2, then cut | 1969 | 2.47 -> 8.78 |

- **fix-forza2** (B `-151099`): B1, B2, B3, D1 hold; A1/A3/D2 not read (no master run survives the race).
- **fix-auf** (`-151975` / `-152037`): every leg holds. The #517 saving on AUF is kept: faf 0.00, bt 0.07 ms/flip in both arms.
- **fix-pixels** and **fix-pixels2**: both pairs split Thor/Nova, and both FAILs are confounded. pixels2's 37 are 36 ZPass_pixel_count captures shifted +672 to +1114 and one Antialiasing capture 0 -> 1.
- **fix-pixels3** (the pair on one device: `1-1790778383-arms-forzadecay414-base-3163761` / `-fix-3163802`) and **fix-forza3** (a 420-s Forza run on eec025dd37: `1-1790778383-forzadecay414-3163702`): queued on the Nova, results pending. Draft until both hold.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
