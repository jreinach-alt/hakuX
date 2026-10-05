# frametrace: per-frame critical-path telemetry (HAKUX_FRAMETRACE=1): who set the pace, frame by frame
State: draft

Lane: frametrace            Issue: #433
Base: master @ d32c35d3ce
Files: docs/lanes/frametrace/PR.md, docs/lanes/frametrace/NOTES.md, docs/lanes/frametrace/OUTBOX.md, hw/xbox/nv2a/pgraph/profile.c, hw/xbox/nv2a/pgraph/profile.h, system/cpus.c
Prediction: none: instrument, off by default; its proof is the overhead A/B and the selftests
Needs device: yes (Thor queued runs, Nova gaps)    Needs NDK: yes

Work in progress: building the instrument. Details follow as they land.

Release note (none): opt-in telemetry, off unless HAKUX_FRAMETRACE=1.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
