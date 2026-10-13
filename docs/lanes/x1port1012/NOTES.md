# lane.x1port1012 -- X1 BOX ports for 0.5.1, Halo #939 (ring flicker), #938 (speech level)

Brief: `/home/justin/hakux-work/briefs/x1port1012.md`. Base `dd5e3cb3c6`. X1 BOX tip `dadced00ce`
(`refs/remotes/x1box/master`), common base `fce5a8d19f`.

## Device-run count (cap 24, all attempts, video arms included)

| # | request id | arm | result |
|---|---|---|---|
| - | - | none yet | - |

## Phase A -- ports

One commit per port. Status per item:

| item | X1 BOX source | status | commit |
|---|---|---|---|
| A1 VP asserts skip the voice | c59b1a7ba7 (vp.c), 51e16997ff | in progress | |
| A2 texture outside VRAM binds dummy | 39435acbc7, 71604431d6 | todo | |
| A3 ADPCM step-index clamp | d8d73ed85b | todo | |
| A4 NULL guard of e3c1927bdf | e3c1927bdf | todo (check first) | |
| A5 setup-wizard BIOS size check | a7765290d1 (validation hunk) | todo | |
| A6 HRTF history clear; audio-init failure non-fatal | 55262dde6d (two hunks) | todo | |
| A7 staging flush; UBO barrier fragment stage | 3d3515faad | todo | |
| A8 hrtf.h normalisation break -> continue | ours | todo | |
| A9 pipeline-cache retry; DMA_VERTEX gen bump | 67fe8d7b2e/1d10f6cb2a, b4999f2e97 | optional | |
