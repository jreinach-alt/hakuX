# mkdawhite1018: Mortal Kombat: Deadly Alliance arena floors and walls draw flat white (#1058)

State: draft

Lane: mkdawhite1018            Issue: #1058 #433
Base: master @ a1e5a7d504
Files: docs/lanes/mkdawhite1018/NOTES.md, docs/lanes/mkdawhite1018/PR.md, docs/lanes/mkdawhite1018/WAITING, docs/lanes/mkdawhite1018/mkda-arcade.route
Prediction: none: analysis-only (so far)
Needs device: yes    Needs NDK: no

Mortal Kombat: Deadly Alliance draws its arena floors, and the walls and pillars nearest the camera, flat
white. The fighters, the floor decals, the HUD and the far backdrop are drawn correctly. On the Kenshi
cloud platform a textured central disc sits beside a white outer ring, so the fault is per material, not
per frame.

**Step 1 is settled: the defect reproduces on Turnip, not just on the stock driver that the 10-06
sighting used.** Request `1792377843-mkdawhite1018-4522138` (after two harness fixes to get the disc
staged at all, `wslpath` and a read-only disc push -- see the table below) ran on the 10-18 build
(`da6e8949dc`), logcat confirms `Driver: PurpleVK` and `[gpl569] mode=3`, and the arena floor and walls
still come back flat white (`frames/f00005.png`, `f00010.png`; sampled pixels are exactly `(255,255,255)`).
That rules out the stock driver as the sole cause.

**Step 2, in progress:** read the `gd` frame dump with `haloshadow1017`'s `chain.py`/`texids.py`. The
floor renders in three passes -- a vertex-colour-only paint pass into an offscreen surface, a 3-tap
ping-pong blur (`s2t`) across three more offscreen surfaces, then a composite into the backbuffer that
binds the blurred surface directly (`tex_surface_direct`, dump field `bv:"d"`). That rules out two of
NOTES.md's standing hypotheses for this draw (dummy texture, texture never uploaded) and narrows the
cause to one of: the paint pass writing wrong colour, the blur shader/read producing white from correct
input, or a GPU read-after-write hazard reusing one image as render target then texture across passes.
None of those three can be told apart from the `gd` dump alone, since it carries register/combiner state
but no pixel data for these offscreen targets -- `NOTES.md` section 9 has the full draw-chain reading.

**The rtt readback landed** (`1792390708-mkdawhite1018-4087588`) and pulled real pixels for the chain.
Two of the three candidates are now ruled out: it is not a GPU read-after-write hazard (the first draw
in the chain is already ~91% solid white RGB on an address nothing else wrote this frame, so there is
no stale content to hazard against), and the chain's shader is not a blur -- its generated GLSL,
pulled straight from the dump, is a single `v0.rgb * t0.rgb` modulated sample, a copy/resample
(correcting this lane's own earlier "3-tap ping-pong blur" label). That leaves one open candidate: the
256x256 surface the chain's first draw samples (`s2t`, direct Vulkan-image bind) is never written
within this run's capture window at all -- the window was armed 170s into a steady soak, deep past the
~84s arena load the route's own notes record, so if this surface is baked once per arena load (a
legitimate pattern: a static glow/AO map, resampled every frame rather than redrawn) this dump cannot
tell a correct bake read every frame since from a bake that never produced real colour in the first
place. `NOTES.md` section 11 has the full reading, the pixel-count table, and the shader source.

A second follow-up, `1792394397-mkdawhite1018-1306972`, was meant to re-arm the same dump 15-20s
before round-start instead of 170s in, to try to catch the bake itself -- but that request was queued
without `--pull`, a mistake in how this lane built the request rather than a harness defect, so it
ran a real 150s on the Nova and pulled nothing (`result.json`: `"pulled": []`). Re-queued, corrected,
as `1792395921-mkdawhite1018-2024860` with `--pull 'framedump_*'` present.

That run pulled cleanly but answered a different question: its 8-frame window landed on the stage
flythrough (Kuatan Palace), not the arena, because `XEMU_FRAME_DUMP`'s leading number is a frame
**count**, not a duration scaled against `--seconds` -- a wrong assumption in this lane's own plan,
corrected by reading `fdump_parse_spec`/`fdump_begin` in `hw/xbox/nv2a/pgraph/vk/renderer.c` directly
(`NOTES.md` section 13). Two follow-ups widened the window instead of guessing a single new instant:
`1792399140-mkdawhite1018-2541099` (120 frames at `after63`, ~3 real seconds, no frame drops) landed
mid-flythrough, camera zoomed from a distant orbital shot to a close temple courtyard shot by its last
frame -- closer, but still before the cut into the fight (section 15). A pilot verdict
(`dispatch/pilots/mkdawhite1018.ok`) was written to justify one more follow-up past the 30-minute
unpiloted device-time line, since every request in this lane has been read before the next was queued;
`1792399836-mkdawhite1018-2687998` (180 frames at `after66`) is now queued to try to catch the cut
itself and the fight's first frames.

Step 3's lever is still open: the bake's own draw (if the floor is a baked/resampled target), or the
surface creation/pool-reuse path in `hw/xbox/nv2a/pgraph/vk/surface.c` (a freshly-created Vulkan image
gets no explicit clear, and a pool-recycled one carries over a different surface's last content), or
something specific to the in-fight camera/lighting path -- the stage flythrough itself, sampled across
two runs and 127 frames total, shows no white anywhere.

| Request | Failure | Fix |
|---|---|---|
| 1792337550 (08:33) | `adb.exe` was handed a `/mnt/d/...` path and could not open it | `wslpath -w` in `dev_push`, folded 127cf0f2c1 (lane.dispatchpush1018) |
| 1792345978 (11:05) | the disc transferred and its sha matched; then `dev_push` required mode 660 on it, and the SD card's mount pins every file at 770 (`dispatcher.log` 29392, and the doctor's retry at 29395) | `dev_push`'s read-only mode, folded f473f6b4c4 (lane.devpushro1018) |
| 1792377843 (re-queued, ~19:4x PDT) | none -- ran to completion | Step 1 result above |
| 1792390708 (rtt readback) | none -- ran to completion | Step 2 result above (section 11) |
| 1792394397 (rtt readback, after65) | queued without `--pull`; ran 150s, pulled nothing | re-queued as 1792395921 with `--pull` present |
| 1792395921 (rtt readback, after65, corrected) | ran and pulled; 8-frame window landed on the stage flythrough, not the arena | frame-count-is-not-duration correction (NOTES section 13); widened to 120/180 frames in the next two requests |

Device time: 1876 s (31.3 min) queued/run against a 30-minute unpiloted cap, covered by the pilot
verdict above.

`1792399836` (180 frames, after66) landed on yet a third character/stage pair -- and the same screen
`1792399140` saw, not a new one: reading `mkda-arcade.route`'s own fixed `wait N` lines (summed in
NOTES.md section 16) shows the stage card is pressed onto screen at t=68 and the script does not
touch the controller again until t=80, a 12-second gap. The "flythrough" `1792399140` sampled and the
near-static hold this run sampled are the same thing -- the stage card's own animated background,
caught moving at different points in that gap. **None of the six runs to date has covered [t68, t83]
end-to-end**, the only window the script's own timing says contains the cut into the fight.

Also read `hw/xbox/nv2a/pgraph/vk/surface.c`'s `create_surface_image` (NOTES section 17, no edits
yet): neither a freshly allocated nor a pool-recycled surface image is cleared on creation -- a fresh
allocation's content is driver-defined, and a pool-recycled one explicitly carries over a different,
unrelated surface's last content (the pool matches only format/width/height/usage). That is the
concrete lever if the floor-glow surface's bake draw turns out to be skipped or under-covered rather
than simply wrong-coloured.

A sixth run, `1792403678-mkdawhite1018-3048897`, is queued: `after78`, 600 frames (~10 s, covering
t78-88), derived from the route script's timing rather than another guess, dropping `images` from the
env spec to keep the payload light. `[lane.mkdawhite1018] waiting:` on it, itself still blocked
behind a Nova hold another lane (`lane.pathfind`) currently holds (`dispatch/hold/nova.why`). This is
outside this session's control (the dispatcher claims queued requests on its own schedule once the
device is free), not this lane's own background task.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
