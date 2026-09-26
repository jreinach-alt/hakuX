Lane: brdf315b            Issue: #315
Base: master @ 6550967a5e
Files: docs/lanes/brdf315b/NOTES.md, docs/lanes/brdf315b/arm_model.py, docs/lanes/brdf315b/board_request.py, docs/lanes/brdf315b/brdf315b-psh.diff, docs/lanes/brdf315b/issue315.md, docs/lanes/brdf315b/make_patch.py, docs/lanes/brdf315b/misses.py, docs/lanes/brdf315b/overlap.sh, docs/lanes/brdf315b/pr_body.md, docs/lanes/brdf315b/syntax_check.py
Prediction: none: analysis-only (the fix needs glsl/psh.c, held by lane.fog278; legs ready in NOTES section 4)
Needs device: no    Needs NDK: no

**The fitted BRDF rule (lane.brdf315) is right. #283 fed it bytes instead of 16-bit fields.** lane.pshqueue's refuted arm (e3b13f5b45) moved exactly the golden's 614 wedge pixels, and none outside the wedge. That rules out coverage: the defect is in the lookup. Every pixel has the wrong colour, with G = 89 (volume t = 22) where the golden has 246 (t = 61).

#283 (a5b4141064, landed after the fit's base) splits point-sampled R16B16 texels into bytes for every consumer not listed in `stage_consumed_raw()`, and BRDF is not listed. So the BRDF stage read theta's low byte and phi's high byte:

| reading of t0/t1 (whole-texel, 610 modelled px) | vs arm capture | vs golden |
|---|---|---|
| whole fields (the fit) | 0 | 605 |
| #283 bytes | 598 | 0 |

All 12 misses of the bytes model are eye-texel boundary ties. Under fields, each lands on the golden's texel, so the model predicts 614 -> <= 4 per capture.

`brdf315b-psh.diff` is brdf315's hunk plus a BRDF case in `stage_consumed_raw()`. It applies at the tip and on #373/#367, and passes `-fsyntax-only`. A board request asks for psh.c after the holders fold. Report: #315 comment 5844356835.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
