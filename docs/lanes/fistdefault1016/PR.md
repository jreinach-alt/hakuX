# HAKUX_FIST_ROUND on by default for 0.5.1 (#939 (b))

State: draft

Lane: fistdefault1016          Issue: #939 [#433]
Base: master @ fb6ebcff40
Files: tcg/aarch64/tcg-target.c.inc, docs/lanes/fistdefault1016/NOTES.md, docs/lanes/fistdefault1016/PR.md, docs/testing/predictions/fistdefault1016-fistround.json
Prediction: docs/testing/predictions/fistdefault1016-fistround.json @ (pending)
Needs device: yes (Nova)    Needs NDK: yes

Flips `hakux_fist_round` (`tcg/aarch64/tcg-target.c.inc`) from default-false to default-true.
`HAKUX_FIST_ROUND=0` is now the escape hatch; any other value, or unset, is ON. The `hb_log`
line now says which way it was decided: `fist round=ON (default)`, `fist round=ON (env)`, or
`fist round=OFF (env HAKUX_FIST_ROUND=0)`.

lane.x1port1012 root-caused #939 (b) (the ring's lit side toggling in bursts) to aarch64's
bare `FCVTZS` on inline x87 FIST/FISTP truncating instead of rounding per the guest's RC, and
verified the fix on the Nova (run 13, `docs/lanes/x1port1012/PR.md`/NOTES.md). The owner's word
(10-16 ~19:00 PDT) is to ship it ON in 0.5.1. This lane only flips the default; no change to the
FRINTI emission, the x86_64 backend (already rounds), or any other switch.

This is emulator code (`tcg/`): the fold runs the device-run gate (Forza, 120 s, Nova), and the
owner will run a regression sweep on the resulting build separately.

Release note (rendering): Halo's menu ring no longer jumps back in bursts; float-to-integer
stores round as on the Xbox.

Work in progress: NOTES.md (arithmetic cost, FRINTI/FPCR.RMode reading, grep for other
default-off claims), the prediction file, and the NDK/Android compile check are still to come.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
