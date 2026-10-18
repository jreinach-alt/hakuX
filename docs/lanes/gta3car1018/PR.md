# gta3car1018: GTA III in the car -- the render passes are a feedback-loop copy per draw (#1049)

State: ready

Lane: gta3car1018            Issue: #1049 #433
Base: master @ 343221f6fc (merges lane/gta3instr1018 9eabf6a463 for the `[dipwin]` line; master merged again at 3357b0e196 and 635141c4cc)
Files: docs/lanes/gta3car1018/**, hw/xbox/nv2a/pgraph/vk/texture.c, docs/testing/nv2a_index.json (regenerated for texture.c's new REF site, preflight gate), docs/lanes/gta3instr1018/** (via merge), docs/testing/jobs/selftest.d/99-dipwin-counters.sh (via merge), hw/xbox/nv2a/pgraph/vk/dipwin.h (via merge), hw/xbox/nv2a/pgraph/vk/draw.c (via merge), hw/xbox/nv2a/pgraph/vk/surface.c (via merge)
Prediction: none: the switch is off by default and the in-car arms are soaks; RenderTextureLoop checked against its golden with the switch on and off (requests 1792347481-gta3car1018-2028877, 1792347484-gta3car1018-2030801)
Needs device: yes    Needs NDK: yes
Selftest: none -- the change is behind an env switch that is off by default; its check is the golden run above

Release note (none): opt-in switch HAKUX_S2T_FB, off by default; no change unless set.

In the car, GTA III draws into a 128x128 colour target while that target is also bound as a texture, about 140
times a flip. Each of those draws copied the target into the texture first, and each copy ended the render pass:
151.65 passes a flip parked in the car against 7.64 on foot, 141.43 of them from that one copy site
(`copy_surface_to_texture`). Frame time follows the pass count (ms/flip = 30.89 + 0.131 x passes/flip over 46
windows); windows without the copies run at the 30 fps cap.

| in-car arm (Nova, owner's state) | parked fps | moving fps |
|---|---|---|
| A1 | 20.6 | 23.0 |
| A2 | 20.2 | 24.5 |
| A3 | 19.2 | 19.4 |

`HAKUX_S2T_FB=1` keeps a slot's copy for the run of draws into the target (until the flip, a target change, or the
slot binding anything else) instead of copying per draw; `=2` does so only for stages whose shader program does
not read the texture. In-car A/B (same state, RT held 60 s, mean fps and render passes/flip over the hold):

| arm | off (baseline) | `=1` run 1 | `=1` run 2 | `=2` run 1 |
|---|---|---|---|---|
| fps | 24.8 | 26.8 | 22.6 | 27.9 |
| passes/flip | 57.11 | 20.15 | 33.67 | 38.20 |

Both values cut passes and raise fps on their first reading; `=2`'s lightest-traffic third of the hold reaches
the 33.3 ms/flip cap outright. `=1`'s second run (an unscripted, different stretch of road) falls below the
baseline with no infra or cold-pipeline cause found, so one run per value does not settle `=1` against `=2` as
the better default, and the fence wait and stalled finishes that also scale with the pass count are still
10-15 ms/flip after the switch in heavy traffic. **This run does not reach 30 fps while driving with either
value.** The switch stays off by default; a third in-car reading (to pair with `=2`'s single run, and to repeat
`=1`) was planned but the Nova went unreachable over adb mid-session (`docs/lanes/gta3car1018/NOTES.md` 6.2) and
the Thor is mid an owner thermal test, so this PR reports what two in-car batches measured and names what is
still missing rather than claiming more.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
