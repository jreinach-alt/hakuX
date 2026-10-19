# GTA III in the car: what the extra render passes are (#1049)

## The cause

In the car, GTA III draws into a 128x128 X8R8G8B8 colour target (@0x038aa080 on the owner's in-car state, zeta
@0x0389a000) while the same memory is bound as a texture on one of the draw's stages. That happens about 140 times
a flip. For each of those draws the Vulkan renderer copied the target into the texture
(`copy_surface_to_texture`, texture.c), and the copy is recorded outside a render pass, so each one ended the pass
the draws were in.

Parked in the car, perflog build, Nova (Adreno 740, PurpleVK), per flip:

| | in the car | on foot |
|---|---|---|
| render passes | 151.65 | 7.64 |
| of them ended by the surface-to-texture copy | 141.43 | |
| ended by a binding change (`bsnb`) | 5.57 | |
| ended by a clear (`bclre`) | 2.00 | |
| ms/flip | 49.25 | 33.3 (the 30 fps cap) |
| fence wait (`fen`) | 15.57 ms | |
| vertex-RAM refresh (`stale`) | 4.00 ms | |

Over 46 one-second windows from three in-car runs, frame time follows the pass count:
ms/flip = 30.89 + 0.131 x passes/flip (r^2 0.66). Windows where the car scene has no copies run at the 30 fps cap
with the GPU at 21-23 ms.

Why the copy is taken at every draw: each draw into the target while a stage is bound over its memory moves the
texture state generation (`pgraph_vk_surface_written_while_sampled`), the game re-writes the stage's registers per
draw, so the next draw re-binds the stage, finds the surface's draw time has moved, and copies.

## In-car frame rate before the change

Owner's in-car state, 28 s parked, then throttle held 60 s; moving spans read off each run's screen recording.

| run | parked fps | moving fps |
|---|---|---|
| A1 | 20.6 | 23.0 |
| A2 | 20.2 | 24.5 |
| A3 | 19.2 | 19.4 |

The vertex-RAM refresh (`stale`, ~4 ms a flip) does not grow with the pass count; the fence wait does. Bringing
vertex RAM current by page (lane vtxstale1018) is worth at most 2-4 ms of the frame in the car: a second step, not
the cause.

## The change

`HAKUX_S2T_FB` (texture.c, off by default):

- `1`: while the surface stays the colour target, a slot that has held a copy of it since the run's first sample
  keeps sampling that copy. The run's draws read the target as it stood at the run's first sample instead of
  after the draw before.
- `2`: the same, only on stages whose shader program does not read the texture (NONE, PASS_THROUGH, CLIP_PLANE,
  DOT_PRODUCT), where no pixel depends on the copy.

A run ends at the flip, when the colour target changes, when the slot binds anything else, and when the copy's
node is written or released. A sample of the surface while it is not the colour target copies as before.

## Result with the change

Same owner state and protocol, one perflog APK, `HAKUX_S2T_FB` set per arm through the debug prefs:

| arm | env | mean fps (RT held 60 s) | render passes/flip |
|---|---|---|---|
| off | (baseline) | 24.8 | 57.11 |
| `HAKUX_S2T_FB=1` | first run | 26.8 | 20.15 |
| `HAKUX_S2T_FB=1` | second run | 22.6 | 33.67 |
| `HAKUX_S2T_FB=2` | first run | 27.9 | 38.20 |

The switch cuts render passes and raises fps in its clean readings; the lightest-traffic third of the best run
(`HAKUX_S2T_FB=2`) reaches the 33.3 ms/flip, 30 fps cap outright. `HAKUX_S2T_FB=1`'s second run falls below the
baseline on a different, unscripted stretch of road with no infra or cold-pipeline cause found, so one run per
value does not settle whether `=1` or `=2` is the better default; the fence wait and stalled finishes that also
scale with the pass count are still 10-15 ms/flip after the switch in heavy traffic. **30 fps while driving is
not reached by either value in this run.** The switch is off by default and does not change behaviour unless set.
