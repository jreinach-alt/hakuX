# lane.x1port1012 outbox (one line per milestone, newest last)

- 2026-10-13: lane opened at dd5e3cb3c6; Phase A ports under way.
- 2026-10-13: A1 committed, 81b542ca3e: bad guest voice data skips the voice instead of aborting (X1 BOX c59b1a7ba7, 51e16997ff).
- 2026-10-13: A2 committed, de06bd39e3: a texture outside VRAM binds the dummy texture (X1 BOX 39435acbc7, 71604431d6).
- 2026-10-13: A3 committed, 79981e045c: ADPCM step index clamped, not a refused block (X1 BOX d8d73ed85b).
- 2026-10-13: A4 committed, cbda0e85fd: our tree had the NULL dereference; EDS1 core names alias the EXT ones, a device without cull/front-face commands is refused cleanly (X1 BOX d5d64b9dc3, e3c1927bdf).
- 2026-10-13: A5 committed, d0eb2410b2: setup wizard accepts only 256 KB / 512 KB / 1 MB flash images (X1 BOX a7765290d1).
- 2026-10-13: A6 committed, 10c83bfa06: HRTF history cleared on voice start; no audio device is no longer fatal (X1 BOX 55262dde6d, two hunks).
- 2026-10-13: A7 committed, d4d292c9ca: staging flushed before its copy (X1 BOX 3d3515faad); fragment stage added to the UBO barrier (ours).
- 2026-10-13: A8 committed, d88374737c: HRTF normalisation skips one channel, not both (ours; X1 BOX has the same bug).
- 2026-10-13: A9 committed, 172d94de1f (pipeline-cache retry, X1 BOX 1d10f6cb2a/67fe8d7b2e) and 4f0111232c (DMA_VERTEX gen bump, X1 BOX b4999f2e97).
- 2026-10-13: Phase A smoke runs 1-3 (Halo, GTA VC, Crimson Skies) all PASS (no crash/hang, fps within noise of each ledger reading). PR.md set `State: ready`.
