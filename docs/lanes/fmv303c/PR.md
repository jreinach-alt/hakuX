# #303: surface write-back probe for Spikeout's FMV green blocks (lane.fmv303c)
State: ready

Lane: fmv303c            Issue: #303
Base: master @ 7e6a4ac88a (origin/master 10f14d301d merged at e2b045168a)
Files: hw/xbox/nv2a/pgraph/vk/surface.c, docs/lanes/fmv303c/NOTES.md, docs/lanes/fmv303c/wb_judge.py, docs/lanes/fmv303c/PR.md, docs/lanes/fmv303c/OUTBOX.md, docs/testing/predictions/fmv303c-wb-probe.json
Prediction: docs/testing/predictions/fmv303c-wb-probe.json @ 3ca87cf99e64fd394861d7873a1ab198985f3caefade06c74c604d052a8e67d3
Needs device: yes (Thor)    Needs NDK: yes

This is step 2a of docs/lanes/fmv303b/NOTES.md s5. A probe that is off by
default (`HAKUX_FMV303_PROBE=1` turns it on) logs every nv2a surface
write-back that lands in guest RAM, with the guest flip count. It covers the
sync copy in `download_surface_to_buffer()` and each staged or deferred copy
in `pgraph_vk_complete_staged_downloads()`. It also logs one cumulative `wbc`
counter line per flip stall, so a zero count is an observed zero.
`docs/lanes/fmv303c/wb_judge.py` joins these lines to the fmv303b tint lines
read from the guest buffer.

## Result: surface write-back is not the cause of #303

Two valid Thor runs on e2b045168a (apk afb8d4ccd1e3), Spikeout USA disc,
probe on, hands-off:

| run | lit tinted (clean) | write-backs | in region | NEAR t / c | SINCE t / c |
|---|---|---|---|---|---|
| 1791150498-lane.fmv303c-2353118 | 389 (36) | 2496 | 5 | 0.000 / 0.000 | 0.000 / 0.000 |
| 1791154079-lane.fmv303c-3735646 | 543 (52) | 2823 | 67 | 0.004 / 0.000 | 0.000 / 0.000 |

The registered verdict is **UNORDERED**. The prediction was EXONERATED, and
it misses on the letter of the rule. The 72 landings in 0x3000000..0x3400000
all fall past the FMV buffers' end (0x3249000), on a colour surface at
0x32a4000 and a zeta surface at 0x33d0000. No write-back lands on either FMV
buffer in 932 lit tinted frames. HIT needed a tinted-minus-clean separation
of at least 0.5, and the measured separation is 0.002. P2 holds: the tint is
0.826 of lit frames, inside the registered [0.3, 0.9], so the probe did not
suppress it. Every write-back in both runs was logged, under the cap. The
frequent writers are the game's own 640x480 targets at 0x3958000, 0x3a84000
and 0x3bb0000. The heat stop on the dead-fan Thor voided two other runs
(19 and 96 lit tinted, under 100).

Next, ranked by P x win in NOTES.md. The win is the same for all: two
titles' pre-game screens. First: find the guest colour-conversion routine
and read the Cr plane per flip (P about 0.7 that it decides). Then MMX/x87
state across an interrupt in TCG (P about 0.3), IDE and APU DMA (about 0.1),
and the per-op SIMD helpers (about 0.1).

Territory: `hw/xbox/nv2a/pgraph/vk/surface.c` is held by lane.async794. This
lane's hunk was committed before that grant, under fmv303c's original grant,
and the fold needs a shared grant for it (see OUTBOX.md). The hunk only
adds lines.

Local checks (no CI while offline):
- wb_judge.py fixtures on this tree give none=EXONERATED, onbuf=HIT,
  otherbuf=UNORDERED, all=UNORDERED, outside=NONE (both runs M0 VOID),
  re-run 2026-10-04 15:5x PDT.
- origin/master (18 commits ahead, none under hw/) merges clean
  (`git merge-tree`).
- The surface.c diff against origin/master only adds lines.
- Head run: a Spikeout USA soak on the Thor, built from this commit, with
  `HAKUX_FMV303_PROBE` unset. It is queued after the push as requester
  lane.fmv303c, purpose "head run". With the probe unset it must boot and
  log no `[fmv303] wb` lines.

Release note (none): diagnostic probe, off unless HAKUX_FMV303_PROBE=1.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
