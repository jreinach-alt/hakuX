# GTA III: where the 46 ms parked frame goes once every copy is removed

State: ready

Lane: gta3dip1018            Issue: #1049 [#433]
Base: master @ bb1817defc
Files: docs/lanes/gta3dip1018/**
Prediction: none: analysis-only
Needs device: no    Needs NDK: no
Selftest: none -- analysis only, no code

Decomposes the GTA III parked-frame cost across the b3 perflog arms (R1; R1+R2; R1+R3), identifies and quantifies a
cold-shader-compile confound specific to that run, locates the owner capture's two multi-second single-frame stalls
against the shader/pipeline-library warm-up counters, and ranks levers for the sustained 16-22 fps driving dip that
remains after R1/R2/R3. NOTES.md has the Already-tried table; FINDINGS.md has the decomposition and the one lever to
take first. No emulator code touched.
