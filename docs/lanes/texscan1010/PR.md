lane.texscan1010 -- create_texture()'s surface-range scan: a GPU-side copy instead of the synchronous download, behind HAKUX_TEXSCAN=1 (#433, 0.5)

State: draft

Lane: texscan1010          Issue: none (dispatched directly by lane.local, #433 umbrella)
Base: master @ 07937793af
Files: hw/xbox/nv2a/pgraph/vk/texture.c, hw/xbox/nv2a/pgraph/vk/surface.c, docs/lanes/texscan1010/**,
  docs/testing/predictions/texscan1010-*.json
Prediction: none yet (to be registered before any arm: NFS MW race start, HAKUX_TEXSCAN on vs off, same build)
Needs device: yes (Nova)    Needs NDK: yes

Working. Step 1 (name the downloads at the NFS race start) first.
