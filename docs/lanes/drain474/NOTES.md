# lane.drain474 (#474)

Branch `lane/drain474`, base master 09fdca3ba1 merged with PR #512
(`lane/slowdown462-bindtex`, the perflog-only `txw[]` probe) at 3b5c577e9c.

## The change (73a4126325)

`create_texture()` in `hw/xbox/nv2a/pgraph/vk/texture.c`, the surface-to-texture
rebind (`surface->draw_time != snode->draw_time`): the drain

    if (snode->submit_time + r->num_active_frames > r->submit_count)
        pgraph_vk_flush_all_frames(pg);

ran before `can_direct_bind` was computed, so it ran ahead of direct binds too.
It now runs only in the `!can_direct_bind` branch, ahead of
`copy_surface_to_texture`. The `txw[]` FAF/BS/CP counters are unchanged, so
`faf` in B counts only drains ahead of a copy.

Premise (lane.slowdown462, run `1-1790543757-slowdown462-3565156`, AUF, Nova,
299-420 s): `faf` 0.27 calls/flip, 4.47 ms/flip of `bt`'s 4.57; `bs` 1.00, `cp` 0,
`up` 0; 16.6 fps. The bound on the gain is about 18.0 fps: a bound, not a value.

## Why nothing in flight needs the drain on the direct path (read, not assumed)

- **What the drain guards.** Its condition is on the texture node
  (`snode->submit_time`, which `update_timestamps()` stamps on every bound node
  at submit). It waits until no in-flight frame can still sample the node's
  image. Only `copy_surface_to_texture` / `copy_zeta_surface_to_texture` write
  that image (transition to TRANSFER_DST, `vkCmdCopyImage`, back to
  SHADER_READ_ONLY, updating `texture->current_layout`).
- **The direct bind writes nothing into the node.** `bind_surface_as_texture`
  flushes the reorder window and draw queue, opens a non-draw command buffer and
  puts a COLOR_ATTACHMENT_WRITE -> SHADER_READ barrier on `surface->image`
  (GENERAL -> GENERAL). `bind_zeta_surface_as_texture` does the same for depth and
  moves `surface->image_layout` to DEPTH_STENCIL_READ_ONLY. Both set
  `texture->draw_time` and nothing else on the node. The node's `image`,
  `image_view` and `current_layout` are not touched. The barriers are on the
  surface's image and are ordered by queue submission, so an earlier frame's use
  of the surface comes first without a host wait.
- **Descriptors of in-flight frames.** With push descriptors (the fast paths in
  draw.c and `pgraph_vk_update_descriptor_sets` in shaders.c), the image infos
  are recorded into the command buffer at push time. Changing
  `tex_surface_direct_views[i]` changes what later pushes record, not what
  earlier ones did. On the standard path, a new texture descriptor set is taken
  from the ring at `descriptor_set_index`. When the ring is full, the code runs
  `pgraph_vk_finish` + `pgraph_vk_flush_all_frames` before it resets the index,
  so a set in use by a frame in flight is never rewritten. The descriptor-set
  cache (`tex_desc_cache`) is keyed on views, samplers and layouts, so a direct
  bind looks up a different key and cannot alter a cached set.
- **`tex_surface_direct_views` rotation.** Retiring a surface view is handled by
  `pgraph_vk_texture_surface_view_retired()` (#34/#274): it points a slot at the
  dummy until the slot is rebuilt. That path is separate from this drain, and its
  condition is on the node, not the surface.
- **The node's layout.** Unchanged by a direct bind. A later copy into the same
  node still goes through the copy branch, and so through the drain.
- **Natural experiment.** Two paths in `create_texture` already bind directly
  with no drain: the cache-miss bind at the end (a fresh node), and the
  same-draw_time rebind (`else if` after the draw_time test). This change makes
  the changed-draw_time direct rebind behave like them.

## Predictions (registered before any device run)

- `docs/testing/predictions/drain474-s2t-pixels.json`: pixel A/B across Texture
  render target, render update in place, Framebuffer Blit, Antialiasing, shadow
  comparator, Surface format, and Color zeta overlap. `must_not_move` on all of
  them. The arms job queues it.
- `drain474-auf-soak.json` (Nova) and `drain474-blinx-soak.json` (Thor): 420 s
  perflog survey soaks. Read with `docs/lanes/slowdown462/txwwin.py <dir> 255 411`.
  These are hand-queued (arms.sh skips soaks).

## State (2026-09-27, attempt 1)

- Preflight passed on f759e898db. CI is the build check. The code was not
  compiled locally.
- Pixel arm: the arms job queues `drain474-s2t-pixels.json` from the pushed
  registration.
- Blinx pair on the Thor, the pilot (two requests, 17 min):
  A `1790549563-drain474-2135431`, B `1790549563-drain474-2135559`. When they
  were queued, about 2.5 h of flip474 and titleroutes work was ahead of them.
- AUF pair on the Nova: **not queued yet.** Four soaks come to 34 min, over the
  30-min pilot gate. After the Blinx pair is read, write
  `pilots/drain474.ok` (with python3) and queue AUF A/B on the Nova with
  `--expect docs/testing/predictions/drain474-auf-soak.json`. The Nova is held
  for battery at the moment, so the pair will wait for it either way.
- Next lane: do not re-queue the Blinx pair. Read it with
  `python3 docs/lanes/slowdown462/txwwin.py <dir> 255 411`, and read the
  cooling devices before trusting a low fps (#507).

## Why attempt 1 did not finish

It ended correctly, as a wait: the Blinx pair was queued behind about 2.5 h of
other device work, and a lane session cannot outlive its own tool calls. It
posted `[lane.drain474] waiting:` on #517. handback resumed it at 01:30Z
(2026-09-28), with both requests DONE and CI green on 73eed83cd4.

## Results (attempt 2, 2026-09-28)

**Pixel arm** (arms job; base `1-1790549936-arms-drain474-base-2297206` on
3b5c577e9c, fix `1-1790549937-arms-drain474-fix-2297407` on 73a4126325, both
on the Nova). Neither arm has an `unreadable` row or any UtilAcceptVsock in
run1.log. The 363 score rows are identical between A and B, and so are the 363
captures, byte for byte. The only file that differs is
`pgraph_progress_log.txt`. That meets must_not_move on all seven suites. The
limit of this arm: it cannot show that a suite reached the direct-bind rebind,
because the txw probe is perflog-only. The Blinx soak below is where the direct
path is known to run.

**Blinx pair**: 420 s survey, perflog, window 255-411 s. The requests were
pinned to the **Nova**, not the Thor that `drain474-blinx-soak.json` names. Both
arms ran on the same device (`ee317437`), so the A/B stands, but the device
differs from the registration.

| | A 3b5c577e9c | B 73a4126325 |
|---|---|---|
| txw lines / flips | 42 / 2520 | 40 / 2400 |
| flips/s (time-weighted) | 15.68 | 15.51 |
| ms/flip | 63.8 | 64.5 |
| `bt` bind_textures wall | 8.25 ms/flip | 0.34 ms/flip |
| `faf` flush_all_frames | 2.08 calls, 7.91 ms/flip | 0.00, 0.00 |
| `bs` direct binds | 2.57 /flip | 2.79 /flip |
| `cp` / `up` | 0 / 0 | 0 / 0 |
| gfps line median (n) | 19 (42) | 15 (40) |
| thermal-pause / hotplug in the window | none | none |
| validation / crash / device-lost lines | 0 | 0 |

- M0 holds. Both arms were in level play: shots 180530 (A) and 181305 (B)
  show Blinx in the clock-tower level. B shows no stale, torn or black quads
  that A does not. The streaked window slats appear in both arms, so they
  predate this change.
- M1 holds: no cooling-device pause or hotplug state in either arm.
- P0 holds. Blinx rebinds far more than AUF does: 2.57 direct binds and 2.08
  drains per flip, against AUF's 1.00 and 0.27. The drain cost 7.91 ms/flip.
- F1 holds. B's `faf` is 0.00. A's `cp` is 0, so every drain in A came before
  a direct bind. B's `bs` is 9% above A's.
- F2 holds.
- P2 holds, trivially: the bound is 1000/(63.8-7.91) + 0.5 = 18.4, and B is
  at 15.5.
- **P1 fails as registered, and fps did not move.** P1 reads the median of the
  gfps *lines*: 15 against A's 19, which is below 19 - 0.5. Those lines are
  written every ~60 flips (2520 flips / 42 lines), not every second, so a line
  median counts the fast spans more often than the slow ones. The time-weighted
  rate, flips over elapsed time from the same probe, is 15.68 vs 15.51, a
  change of -1%. Both arms swing through the same 7-30 gfps band. The blind
  survey route puts those swings at different times in each arm, so a
  single-run median sits wherever the swings happen to fall. Read this way,
  the arm shows no fps change, not a regression. The P1 leg is still failed as
  registered, and the next lane should not quietly re-read it.
- **What this means.** Taking the drain out of the direct path removed
  7.9 ms/flip of CPU wall in `bind_textures`, and the frame rate did not
  change. The drain was not on the critical path. Its wait overlapped a GPU
  wait (or another stall) that still bounds the frame. The next wait along
  the frame is in `flip474`'s territory, PFIFO's GPU waits inside pg->lock.
  The 16.6 ms per drain in slowdown462's AUF read fits that: each drain was
  waiting out one GPU frame, and the frame still costs that time without the
  drain.

**AUF pair** (the title the premise was measured on): pilot verdict written
to `pilots/drain474.ok`. Queued on the Nova with
`--expect docs/testing/predictions/drain474-auf-soak.json`:
A `1790559191-drain474-1881273` (3b5c577e9c), B `1790559196-drain474-1882754`
(73a4126325). Read them the same way. The Blinx result predicts `faf` 0.27 -> 0
with fps flat. A rise toward 18.0 would mean AUF's drain *was* on its critical
path. Read the time-weighted rate, not a line median.

Next lane: do not re-queue either Blinx arm or the pixel arm. Do not read P1
off gfps line medians.

## Why attempt 2 did not finish

It also ended as a wait, correctly. The AUF pair was queued on the Nova
behind other device work. Attempt 2 posted `[lane.drain474] waiting:` on #517
naming both requests. The pair finished at about 20:15 PDT on 09-27, and
handback resumed the lane.

## Results (attempt 3, 2026-09-28): AUF pair, and energy per frame

**AUF pair** (Nova `ee317437`, both arms, MAX regimen, 420 s survey, window
255-411 s). A is `1-1790559191-drain474-1881273` on 3b5c577e9c, and B is
`1-1790559196-drain474-1882754` on 73a4126325. Power is from `title_verdict.py`
(master), run on copies in /tmp. Its scored window is mark to soak end, not
255-411 s.

| | A 3b5c577e9c | B 73a4126325 |
|---|---|---|
| txw lines / flips (255-411 s) | 43 / 2580 | 44 / 2640 |
| flips/s (time-weighted) | 16.68 | 16.97 (+1.7%) |
| ms/flip | 60.0 | 58.9 |
| `bt` bind_textures wall | 4.55 ms/flip | 0.10 ms/flip |
| `faf` flush_all_frames | 0.30 calls, 4.45 ms/flip | 0.00, 0.00 |
| `bs` direct binds | 1.00 /flip | 1.00 /flip |
| `cp` / `up` | 0 / 0 | 0 / 0 |
| gfps line median (n) | 16 (43) | 17 (44) |
| title_verdict fps window median | 16.63 | 16.93 |
| thermal pauses (whole run) | none | none |
| validation / crash / device-lost lines | 0 | 0 |
| battery_w (discharging) | 4.96 W | 4.42 W |
| usb_w (measured) | 2.11 W | 2.11 W |
| net_w | 7.07 W | 6.53 W |
| **j_per_frame** | **0.4245 J** | **0.3842 J (-9.5%)** |
| power samples in the window | 5 | 6 |

Legs of `drain474-auf-soak.json`:
- M0 holds. Both arms have 43-44 txw lines, and the play shots (A 200622,
  B 201407) show the same spot in the first level.
- M1 holds.
- F2 holds. The two shots match, with no stale, torn or black quads. Neither
  logcat has a validation, device-lost or crash line.
- P0 holds: `faf` 0.30 is in 0.15-0.40, and `cp` is 0.
- F1 holds: `faf` is 0.00, and `bs` is 1.00 in both arms.
- P1 holds: 17 >= 16 - 0.5.
- P2 holds: the bound is 1000/(60.0 - 4.45) + 0.5 = 18.5, and B is at 16.97.

So AUF shows the same thing as Blinx. The drain is gone, and fps moves by
+0.3 (+1.7%), about a fifth of the 4.45 ms the drain took. That is within what
one survey run per arm can resolve.

**Blocking wait or CPU work.** The drain was a blocking wait.
`pgraph_vk_flush_all_frames` (draw.c) is `pgraph_vk_render_thread_wait_idle`,
which calls `qemu_event_wait` on the render thread's idle event, followed by
`vkWaitForFences(..., UINT64_MAX)` on each submitted frame. The only work
after that is per-slot bookkeeping. So the 4.45 ms/flip (AUF) and
7.91 ms/flip (Blinx) removed were time the PGRAPH thread spent asleep. Each
drain waited out the GPU work already in flight, and that GPU work still
bounds the frame once the drain is gone. Removing a sleep should save little
CPU energy.

**Energy.** AUF's net power fell 0.53 W and J/frame fell 9.5%, from one pair
with 5-6 power samples each. The USB input was identical (2.11 W), so the
difference is on the battery side. A blocking wait does not explain a 0.5 W
drop. What could: fewer wake/sleep cycles on the PGRAPH thread, a GPU that
stays busy instead of idling and re-clocking at every drain, or the battery's
state of charge moving between the two runs. This measurement cannot tell
those apart. Read it as "not worse, possibly better", not as a 9.5% saving.
A replicate pair would be needed to claim a number.

**Blinx has no power record.** Both Blinx arms (`1-1790549563-drain474-2135431`
and `-2135559`) ran before #523 went live. `title_verdict.py` reports
`power.measured: false` with 0 samples for both, so Blinx has no J/frame, and
none is estimated here. The same reasoning covers it: its 7.9 ms/flip was the
same blocking drain.

Next lane: do not re-queue the AUF pair, the Blinx pair or the pixel arm. If
an energy claim is wanted, queue one replicate AUF pair on the Nova and read
`power` with `title_verdict.py`. Do not change code for it.
