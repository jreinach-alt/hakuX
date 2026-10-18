# gta3fps1017: GTA III fps -- the census on foot (neither R2 nor R3), and R1: no #474 drain ahead of a plain colour copy (#1049)

State: ready

Lane: gta3fps1017            Issue: #1049 #433
Base: master @ 6295705f20 (master 8ea6676bd0 merged in)
Files: docs/lanes/gta3fps1017/NOTES.md, docs/lanes/gta3fps1017/PR.md, docs/lanes/gta3fps1017/tools/arm_diff.py, docs/lanes/gta3fps1017/tools/desk_census.py, docs/lanes/gta3fps1017/tools/desk_suites.py, hw/xbox/nv2a/pgraph/vk/texture.c
Prediction: none: no arm. R1 claims no pixel change, and no pgraph suite reaches its branch (three desktop arms here, the Nova arms in gta3drive1017 8.1); its proof is the on-foot before/after below
Needs device: no    Needs NDK: yes
Selftest: none. No selftest.d fragment runs or reads texture.c or this lane's docs (grep of selftest.d: no texture.c, pgraph/vk or gta3fps1017 path; 75-nv2a-index-drift reads fixtures). The pgraph suites are not selftest fragments; they ran on the desktop with R1 on and off (NOTES 2.3)

Release note (performance): fewer stalls when a game reuses its rendered picture as a texture, as GTA III does in its driving dips: the renderer no longer waits for every frame in flight before each such copy (HAKUX_S2T_DRAIN=1 restores the wait).

Three commits from lane/gta3drive1017, cherry-picked: R1 (b7d7243392: skip `pgraph_vk_flush_all_frames` ahead of a
plain colour surface-to-texture copy into an in-flight node; c6ca5296fd: `[s2tdrain] first skip` once, kill switch
`HAKUX_S2T_DRAIN=1` logging `[s2tdrain] on`) and the perflog copy census (bd2bf354bb's texture.c hunk:
`[s2c] new` pairs and `[s2c] f60` refusal reasons and dups per 60 flips, `NV2A_PERF_LOG` builds only).

**The census on foot does not transfer to driving, so neither R2 nor R3.** GTA III held on foot on the desktop
(lavapipe, a perflog build of this branch):

| run | R1 | 60-flip windows | copies/flip | reason | dup | drains/flip | drain ms/flip | log line |
|---|---|---|---|---|---|---|---|---|
| c2 | off | 27 | 2.00 | `map` 100% | 0 | 1.86 | 217.17 | `[s2tdrain] on` |
| c1 | on | 65 | 2.00 | `map` 100% | 0 | 0 | 0 | `[s2tdrain] first skip` |

The Nova agrees on the count: the perflog pilot's 26 windows at 2 copies per flip (cutscene, standing, on foot)
run 29.63 fps with 1.90 drains and 3.41 ms of drain per flip. The dips run ~73 copies per flip: 36x more, outside the
brief's factor of two, so the lane stops at step 2. On foot R2 would save ~0.04 ms per flip of copy recording (the
bind still ends the render pass) and R3 has nothing to share (dup 0). The burst census needs driving; NOTES section 5
ranks the route to it: one owner session on a perflog APK after this folds.

**R1 folds alone.** Every burst copy in the pilot is at `s2t@1264` (all 477 GPUXFR windows), which only a plain colour
copy reaches, and in the bursts drains track copies (161.23 vs 161.62 per flip). The copy's
SHADER_READ_ONLY->TRANSFER_DST barrier already orders it after earlier submissions' fragment reads on the one queue.

| pgraph suites (desktop, 7 suites, 363 tests) | R1 | exit | `[s2tdrain]` | golden-exact |
|---|---|---|---|---|
| sA | off | 0 | none | 16 |
| sB | on | 0 | none | 16 |
| sB2 | on (rerun) | 0 | none | 16 |

R1 off vs on: 299 and 290 of 363 bit-identical; R1 on vs its own rerun: 298. Every difference is in
Texture_shadow_comparator, as large within R1 on as between the arms. The 75 other tests are bit-identical in all
three. On Turnip, gta3drive1017's six R1-on GTA III arms (PurpleVK, ~60 min, driving included) ran to the end with no
fatal signal. R1 is default-on for every title. No driving fps claim: that comes from owner play.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
