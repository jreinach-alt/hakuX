lane.texscan1010 -- create_texture()'s surface-range scan: a GPU-side copy instead of the synchronous download, behind HAKUX_TEXSCAN=1 (#433, 0.5)

State: draft

Lane: texscan1010          Issue: none (dispatched directly by lane.local, #433 umbrella)
Base: master @ 07937793af
Files: hw/xbox/nv2a/pgraph/vk/texture.c, hw/xbox/nv2a/pgraph/vk/surface.c, docs/lanes/texscan1010/**,
  docs/testing/predictions/texscan1010-*.json
Prediction: docs/testing/predictions/texscan1010-pixels.json @ 0e780d95d9d0, docs/testing/predictions/texscan1010-nfs.json @ e7d9f79c0787
Needs device: yes (Nova)    Needs NDK: yes

Working.

- Step 1 is done: NOTES.md section 3. Every download at the NFS race start is a whole face of the car's 128x128 cube environment map, 270 per 60 frames, and together they cost 7.3 ms/frame.
- Step 2 is built: NOTES.md section 4. HAKUX_TEXSCAN=1 copies those faces on the GPU.
- Both predictions are registered, and 6 Nova runs are queued (NOTES.md section 5): the pixel leg (29 suites) and the NFS leg (off, on, on, off).
