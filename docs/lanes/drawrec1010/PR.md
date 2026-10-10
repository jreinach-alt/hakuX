drawrec1010: HAKUX_DRAWREC=1 (default off): owe the vertex sync's TLB walk, and consume a stale shader_bindings_changed (#433, 0.5)
State: draft

Lane: drawrec1010       Issue: #433 (umbrella), none filed
Base: master @ 67187f9574
Files: hw/xbox/nv2a/pgraph/vk/draw.c, docs/lanes/drawrec1010/**, docs/testing/predictions/drawrec1010-*.json
Prediction: docs/testing/predictions/drawrec1010-pixels.json @ 958f10d9dd48e384c5e9b16eebffbaede5b2e8253fee21bf5b80c4b984cbd681, docs/testing/predictions/drawrec1010-nfs.json @ 7f465817484721653e51b27e84ae8ac4e77744b7a2d358265193b30cdb649d82
Needs device: yes (Nova, used)
Needs NDK: no
Release note (none): opt-in switch HAKUX_DRAWREC=1, default off

Step 3 of `docs/lanes/nfs30plan1010/PLAN.md`: cut the PFIFO thread's per-draw
recording cost at the NFS Most Wanted race start.

1. **Census** (`HAKUX_DRAWCENSUS=1`, default off, no behaviour change), run
   `1-1791656193-drawrec1010-4097387` (perflog, F1-F3 on, 12 starts):
   same 24.4%, uniforms-only 38.6%, cumulative 63.0% of consecutive draws, so
   the brief's step 2 (reuse) applies. 31% of draws take the full path and write
   a fresh UBO set only because `shader_bindings_changed` stays set after the
   change it reports. And the largest phase left after F1-F3 is `Syn`: the vertex
   sync's TLB walk (~240 walks per flip at ~16 us, 3.4-3.9 ms of the 4.0 ms at
   the cold start). Tables: `docs/lanes/drawrec1010/NOTES.md` section 5.
2. **`HAKUX_DRAWREC=1`** (draw.c only):
   - VTX: test-and-clear and copy as before, but owe the TLB re-arm to a
     bitmap walked once per flip, re-copying owed pages on every touch until
     then.
   - SHC: clear `shader_bindings_changed` after a full-path draw that has used
     it.

   `HAKUX_DRAWREC_VTX=0` / `HAKUX_DRAWREC_SHC=0` turn one part off.
   NOTES section 8.
3. Pixel check and NFS A/B: queued (NOTES section 4); results and verdict to
   follow.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
