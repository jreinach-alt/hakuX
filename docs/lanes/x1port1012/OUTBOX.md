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
- 2026-10-13: Phase A smoke runs 1-2 (Halo, GTA VC) queued; PR #965 opened (draft) for `lane/x1port1012`.
- 2026-10-13: Phase B (#939) leads committed on `lane/x1port1012-halo`: f3acdd0912 (`HAKUX_XVSS`), 18fb351588 (`HAKUX_S2TSHELF`), 223f216d7c (staging-buffer memory-properties log). Attempt 1 ended without pushing the branch or updating these docs; see NOTES.md "Attempt 2 resume".
- 2026-10-13 (attempt 2): Phase A smoke runs 1-2 judged PASS (Halo gfps 59.93 vs 59.98; GTA VC fps_ok 0.9859 vs ledger 0.9872). Run 3 (Crimson Skies) queued, 1791897193-x1port1012-336185.
- 2026-10-13 (attempt 2): `lane/x1port1012-halo` pushed; PR opened (draft) for Phase B-D, stacked on #965. #939 triage-video arm 1/3 (`HAKUX_SURFGPU=0`) queued, 1791897357-x1port1012-341157; arms 2/3 and 3/3 (fastpaths off, shipped defaults) written up in NOTES.md to queue next as the queue has room. WAITING: owner judgment of the triage video once all three arms have results.
- 2026-10-13 (attempt 3): merged 11 commits of origin/master (none touch this lane's territory). Phase A smoke run 3 (Crimson Skies) judged PASS (fps_ok=1.0 vs ledger 0.95); all three Phase A smoke titles now PASS; `lane/x1port1012` PR.md set `State: ready`, pushed.
- 2026-10-13 (attempt 3): #939 triage video, all three arms landed and dispatched this session (no crash/hang, logcat clean, none judged for ring/overlay content -- owner-reserved per the brief):
  - shipped defaults OFF (`HAKUX_SURFGPU=0`): `/home/justin/hakux-work/dispatch/results/1791897357-x1port1012-341157/video/v00001.mp4`
  - fastpaths off (all 8): `/home/justin/hakux-work/dispatch/results/1791900988-x1port1012-549369/video/v00001.mp4`
  - shipped defaults: `/home/justin/hakux-work/dispatch/results/1791900994-x1port1012-549623/video/v00001.mp4`
  6 of 24 device runs used, 0 queued/running. WAITING: owner (Opus resume) judges the three videos; see NOTES.md WAITING line.
- 2026-10-16 (lane.xbox): the three #939 clips are VOID. Every clip is the intro movies (Microsoft logo, MGS intro, Bungie logo), not the ring menu, which runs +33..+96 s after soak start (smoke run 1's frames f00004-f00008). Re-record plan, with a v0.5.0 control arm first: NOTES.md "Triage video void". WAITING: when the Nova is free, resume on Opus to re-record.
