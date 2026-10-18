# gta3car1018: GTA III in the car -- what the extra render passes are (#1049)

State: draft

Lane: gta3car1018            Issue: #1049 #433
Base: master @ 343221f6fc (merges lane/gta3instr1018 9eabf6a463 for the `[dipwin]` line)
Files: docs/lanes/gta3car1018/**, docs/lanes/gta3instr1018/** (via merge), docs/testing/jobs/selftest.d/99-dipwin-counters.sh (via merge), hw/xbox/nv2a/pgraph/vk/dipwin.h (via merge), hw/xbox/nv2a/pgraph/vk/draw.c (via merge), hw/xbox/nv2a/pgraph/vk/surface.c (via merge)
Prediction: none: measurement in progress (in-car `[dipwin]` runs)
Needs device: yes    Needs NDK: yes
Selftest: none -- no code change of this lane's own yet

Release note (none): instrumentation only so far (perflog builds).

In-car `[dipwin]` measurement of GTA III on the owner's state (parked, then RT held), to name what asks for the
~52 render passes a frame the car scene takes against 7.7 on foot, and then remove the dominant cause.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
