# x1port1012-halo: #939 ring-world leads (triage video dispatched, all 3 arms); #938, Fable not yet started

State: draft

Lane: x1port1012          Issue: #939 [#938]
Base: master @ dd5e3cb3c6 (stacked on PR #965, `lane/x1port1012`, still open)
Files: docs/lanes/x1port1012/PR.md, docs/lanes/x1port1012/NOTES.md, docs/lanes/x1port1012/OUTBOX.md, hw/xbox/nv2a/pgraph/pgraph.c, hw/xbox/nv2a/pgraph/vk/texture.c, hw/xbox/nv2a/pgraph/vk/buffer.c
Prediction: none: the leads are default-off diagnostic switches, judged by an owner-reviewed triage video, not an automated A/B against a golden
Needs device: yes (Nova)    Needs NDK: yes

Release note (none): default-off diagnostic switches for #939 (`HAKUX_XVSS`, `HAKUX_S2TSHELF`) and a
staging-buffer memory-properties log line; nothing changes at shipped defaults.

This is the second PR for lane.x1port1012 (the suffixed-branch convention: a second "own PR" branches
`lane/<name>-<suffix>` from the first PR's head rather than restarting CI/audit on #965, which is waiting
to fold its own Phase A smoke batch). It stacks on #965's head; `Base` and `Files` get updated once #965
folds and this branch rebases its accounting onto master.

## What is here

Three Phase B (#939, the Halo ring-world glitch) leads, each a default-off `HAKUX_*` switch:

| switch | commit | what it changes |
|---|---|---|
| `HAKUX_XVSS` | f3acdd0912 | `noskip` runs every `LAUNCH_TRANSFORM_PROGRAM` launch instead of skipping on a v0-hash match (X1 BOX cf92edbbba removed the skip); `audit` logs how often the skip's output would have differed |
| `HAKUX_S2TSHELF` | 18fb351588 | `0` turns off the shelved-surface lookup in `create_texture` (X1 BOX 0c014f8fe8 removed it); `audit` logs each hit's state |
| (logging only) | 223f216d7c | one line per per-frame staging buffer at init, saying whether the device gave HOST_COHERENT memory |

All three are gated leads from `batchC.md`/`batchD.md`, not fixes: none is claimed to resolve #939 yet.

## What is not here

- The triage video (brief Phase B step 1, three arms: shipped defaults, `HAKUX_SURFGPU=0`, fast paths
  off) is fully dispatched (arm 1 landed, arms 2-3 queued) but not yet judged -- see NOTES.md, `WAITING`.
  Judging frame content for #939 is reserved for the owner, not this lane.
- Phase C (#938, speech level) and Phase D (Fable, fp_jit) have not started.
- Phase E (`HAKUX_PATTFENCE`) is explicitly not before Thursday's reset per the brief.

This PR stays draft until the owner judges the triage video and at least one lead is confirmed or ruled
out; see `docs/lanes/x1port1012/NOTES.md` for the queued runs and the `WAITING` line.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
