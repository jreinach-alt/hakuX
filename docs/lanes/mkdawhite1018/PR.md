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

A follow-up run, `1792390708-mkdawhite1018-4087588` (`rtt,rttmax16384`, same route, queued and unclaimed),
should pull back actual pixel values for the three blur-chain targets and settle which of the three it is.
`NOTES.md` section 10 has the request and one tracked discrepancy (queued at lane HEAD rather than
`da6e8949dc`; confirmed no `hw/xbox/nv2a` diff between those two refs, so the result is unaffected).

| Request | Failure | Fix |
|---|---|---|
| 1792337550 (08:33) | `adb.exe` was handed a `/mnt/d/...` path and could not open it | `wslpath -w` in `dev_push`, folded 127cf0f2c1 (lane.dispatchpush1018) |
| 1792345978 (11:05) | the disc transferred and its sha matched; then `dev_push` required mode 660 on it, and the SD card's mount pins every file at 770 (`dispatcher.log` 29392, and the doctor's retry at 29395) | `dev_push`'s read-only mode, folded f473f6b4c4 (lane.devpushro1018) |
| 1792377843 (re-queued, ~19:4x PDT) | none -- ran to completion | Step 1 result above |

`[lane.mkdawhite1018] waiting:` on `1792390708-mkdawhite1018-4087588` -- the rtt pixel readback that
settles which of the three Step 2 candidates is the cause.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
