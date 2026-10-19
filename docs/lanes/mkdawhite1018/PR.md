# mkdawhite1018: Mortal Kombat: Deadly Alliance arena floors and walls draw flat white (#1058)

State: ready

Lane: mkdawhite1018            Issue: #1058 #433
Base: master @ a1e5a7d504
Files: docs/lanes/mkdawhite1018/NOTES.md, docs/lanes/mkdawhite1018/PR.md, docs/lanes/mkdawhite1018/FINDINGS.md, docs/lanes/mkdawhite1018/WAITING, docs/lanes/mkdawhite1018/mkda-arcade.route
Prediction: none: analysis-only, no code change made
Needs device: no (this lane's own device work is done; a fix lane needs one)    Needs NDK: no

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

A sixth run, `1792403678-mkdawhite1018-3048897`, ran: `after78`, 600 frames (~10 s, covering
t78-88), derived from the route script's timing rather than another guess, dropping `images` from the
env spec to keep the payload light. It finally landed inside real gameplay, not another stage-card or
flythrough frame. Its `gd`+`rtt` dump shows the §11 floor-glow composite chain (a large backbuffer
draw live-sampling a small offscreen surface via `tex_surface_direct`/`bv:"d"`) as an exact, byte-
identical no-op in all 24 instances across the full 600-frame window, and finds no dummy-texture
evidence anywhere in frame 0 (`th`==`gh` on every checked binding). **Neither result tells us
anything about the defect**, because of the next finding.

**The defect is scoped to specific arenas, not the renderer in general -- found at zero additional
device cost.** `mkda-arcade.route` fires `shot round`/`shot gameplay` at a fixed point regardless of
the frame-dump env spec, so every one of this lane's six prior dispatch runs already held a full-
colour screenshot of the fight it reached, unread until now. Opening and measuring all seven
(`0-1792377843` through `1792403678`) gives:

| Run | Opponent | Arena | White px | Floor |
|---|---|---|---|---|
| 0-1792377843 | Johnny Cage | Stone courtyard, red banners | 30.36% | white |
| 1792390708 | Mavado | Snowy mountain pass | 23.16% | ambiguous (blur/fog) |
| 1792394397 | Li Mei | Hall with carved heads | 31.90% | white |
| 1792395921 | Bo Rai Cho | Kuatan Palace | 56.40% | white (wall too) |
| 1792399140 | Sonya | Stone courtyard, red banners | 32.34% | white |
| 1792399836 | Kenshi | Stone temple interior | 0.02% | correct |
| 1792403678 | Sub-Zero | Ice temple | 0.07% | correct |

Five of seven land white; the two clean ones are the two arenas that landed register-level dumps in
this lane (Kenshi's run never got a `gd`/`rtt` dump; Sub-Zero's -- `1792403678` -- is the one analysed
above). The run this lane finally got register data from was, by the blind route's luck, one of the
*correctly-rendering* arenas -- which is why the no-op/texture-integrity findings above are
inconclusive rather than a disproof of any standing hypothesis. "Stone courtyard" and "Hall with
carved heads" are the exact same arenas the original 10-06 stock-driver sighting named (`NOTES.md`
section 1's table, rows 1 and 2), now reproduced on Turnip with different opponents -- strong
confirmation this is a real, per-arena-asset defect and not routing noise. Full table and reasoning:
`NOTES.md` section 19; summary and recommendation: `FINDINGS.md`.

**Step 3, the lever for a fix lane:** `mkda-arcade.route`'s character-select input is blind -- seven
runs, six different opponent/arena pairings, no way to choose which arena a run lands on. A fix lane
needs a `gd`+`rtt`+`images` dump taken *while deterministically on one of the three confirmed-broken
arenas* (Stone courtyard, Hall with carved heads, or Kuatan Palace) to catch the floor-paint draw's
register state and a visual frame together -- either a save state that starts past character select
already in one of those arenas, or a route that controls the select screen deterministically rather
than relying on landing there by chance. Without that targeting, another register dump through this
route is a coin flip (2 of 7 so far landed on a correct arena) and risks re-learning exactly what this
lane already found for the wrong arena. The standing `create_surface_image` no-clear candidate
(`hw/xbox/nv2a/pgraph/vk/surface.c`, NOTES.md section 17 -- neither a fresh nor a pool-recycled
surface image is cleared) remains a plausible mechanism but unconfirmed either way; it was never
tested against a broken-arena instance.

**Proposed tracker update for #1058's `status_note`** (board request, not a direct edit): "Confirmed
on Turnip (0.5.0-1018-da6e8949dc), not stock-driver-only. Scoped to specific arena floor/wall
materials, not the renderer generally: Stone courtyard and Hall with carved heads reproduce white
(5 of 7 sampled fights, 23-56% white pixels); Kenshi's fortress interior and the ice temple render
correctly (0.02-0.07%). A fix lane needs deterministic arena selection (save state or scripted
select-screen input) to get a register-level dump of a confirmed-broken arena's floor-paint draw;
see docs/lanes/mkdawhite1018/FINDINGS.md."

Device time: 2256 s (37.6 min) total queued/run against a 30-minute unpiloted cap, covered by the
pilot verdict and its addendum (`dispatch/pilots/mkdawhite1018.ok`). This attempt's analysis (the
no-op/texture-integrity checks and the full seven-run screenshot comparison) spent zero additional
device time -- all of it read data already on disk.

Selftest: none -- analysis-only lane, no code or test changed; the pgraph suite the tracker row asks
for belongs to whichever fix lane picks up the named lever above, once it has a register-level dump
of an actually-broken arena to write a fixture against.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
