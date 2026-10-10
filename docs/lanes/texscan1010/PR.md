lane.texscan1010 -- create_texture()'s surface-range scan: a GPU-side copy instead of the synchronous download, behind HAKUX_TEXSCAN=1 (#433, 0.5)

State: ready

Lane: texscan1010          Issue: none (dispatched directly by lane.local, #433 umbrella)
Base: master @ 07937793af (merged forward to 9fd2608f8f)
Files: hw/xbox/nv2a/pgraph/vk/texture.c, hw/xbox/nv2a/pgraph/vk/surface.c, docs/lanes/texscan1010/**,
  docs/testing/predictions/texscan1010-*.json
Prediction: docs/testing/predictions/texscan1010-pixels.json @ 0e780d95d9d0 (FAIL on 1 capture, explained: device noise in a test the switch cannot reach), docs/testing/predictions/texscan1010-nfs.json @ e7d9f79c0787 (R PASS; P, H, F FAIL, wrong sign)
Needs device: yes (Nova, used)    Needs NDK: yes

Release note (none): HAKUX_TEXSCAN=1 (opt-in, default off) copies a cube map's drawn faces on the GPU instead of downloading them to the CPU. On its own it makes the NFS Most Wanted race start slower (20.3 fps vs 21.5); this lane does not recommend default-on until it is paired with lane.reportasync1010's async occlusion report.

**What the downloads are** (NOTES.md section 3, run `1-1791648919-texscan1010-2004607`). Every create_texture() download at the NFS MW race start is a whole face of the car's 128x128 A8R8G8B8 cube environment map at 0x352a080. Face 0 is downloaded by the SDL block (30 per 60 frames), faces 1-5 by the range scan (240 per 60 frames). Each is a synchronous GPU finish plus a readback, 7.3 ms/frame together (sdl 3.9 + scan 4.0).

**What the switch does** (NOTES.md section 4). For a cube of that shape whose drawn faces are all whole faces, it skips both downloads and records `vkCmdCopyImage` from each changed face's surface into array layer `face` of the texture, in order in the frame's command buffer. Unchanged faces are not copied again. VRAM stays coherent: the faces stay draw-dirty, so any CPU, guest, blit or eviction read still downloads them first. Anything outside that shape takes the existing downloads unchanged.

**Pixel leg** (B on `1-1791650753-texscan1010-2542806`, A off `1-1791650757-texscan1010-2543971`, 29 texture/surface suites). 718 of 719 captures are the same. `Texture_border/2D_BorderTex_SZ` moved 17103 -> 16268 px off golden. The switch cannot reach that test (2D, border: refused at the shape check), and 16268 is the value most recent APKs read for it, so the off arm is the outlier. B logged no `[texscan] first copy`: as predicted, no suite exercises the copy. In game, the car's reflection is present and the same kind on vs off (route frames `s5-g11`).

**NFS leg** (12 race starts per run, apk 15d83b0da02e):

| run | state | period ms | v2 / v3 / v4+ | range ms/frame | gfps |
|---|---|---|---|---|---|
| `1-1791650940-texscan1010-2621346` | off | 46.6 | 31.8 / 57.8 / 10.3 % | 4.03 | 22.7 |
| `1-1791650940-texscan1010-2621780` | on | 49.4 | 27.3 / 52.3 / 18.8 % | 0.00 | 21.7 |
| `1-1791650941-texscan1010-2622254` | on | 48.9 | 26.7 / 53.2 / 17.8 % | 0.00 | 22.1 |
| `1-1791650942-texscan1010-2622720` | off | void: the route went one menu too deep and raced an alias dialog | | | |

| leg | predicted (on - off) | measured, 3 valid runs | |
|---|---|---|---|
| R | range on <= 0.5, off >= 2.5 ms/frame | 0.00 / 4.03 | PASS |
| P | period in [-12, -2] ms | +2.6 | FAIL |
| H | v3+v4 down >= 10 points, v2 up >= 10 | +2.9, -4.8 | FAIL |
| F | matched-work gfps in [+1, +8] | -1.40 | FAIL |

The registered judge over all 4 runs also reads P, H, F FAIL, but by much more (+25.6 ms, -26 gfps), because the void run raced at 59 fps. The sign holds without it: the on period is above every off reading of this start on record (46.6, 46.4, 43.5, 41.9 ms). There is no MC2 pair, because the brief runs one only if NFS wins.

**Why it lost** (NOTES.md section 9). The download wait did not go away. It moved. NFS issues two occlusion queries per frame, and every finish with queries in flight waits on every submitted frame fence (#804, reports.c:243-263). With the switch off, the mid-frame cube-face finishes submitted part of the frame early, so the report fence found the GPU nearly done. With it on, the whole frame submits at the end, and the fence waits for all of it. `Fin` is 12.0 ms either way: Sub drops 6.4 -> 0.2, and the report part rises ~4.6 -> ~10.5. create_texture's own cost does fall from 8.96 to 1.04 ms/frame, and the cube is no longer re-uploaded. The GPU also does ~1.6 ms more per frame with it on, in one inter-pass gap that is not yet attributed (`HAKUX_GPUXFR=1` would say).

**Recommendation.** Keep default-off and fold as-is: it is opt-in, inert when off and pixel-checked. lane.reportasync1010 (`HAKUX_REPORT_ASYNC=1`) removes the report wait this switch exposes, and its brief step 5 runs both switches on vs both off once this one is on its base. That pair decides default-on.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
