# lane.xbox -- the project console as an instrument

Standing lane (board wave 148). It owns the console (192.168.50.1, GPU rev
163 / MCP rev 212, V1.1) and the issues that need silicon: #31, #109, #110,
#112. Operating knowledge is in `docs/testing/handoff-on-hardware.md`
(PR #216); read its four config traps before writing a config.

## Where things live, outside this repository

| what | where |
|---|---|
| per-test PGRAPH register instrument | `~/nxdk_pgraph_tests`, branch `hakux/per-test-instrument` (`8158852`); `main` stays pristine at `6743b6a`, which the NV2A index pins |
| #31 `clip_top = 35` build | `~/nxdk_pgraph_tests-wbuf31`, branch `hakux/wbuf31-clipf35`, submodules linked to the main checkout's |
| XBE toolchain | `PATH=$HOME/.local/nv2a-venv/bin:$HOME/.local/nxdk-tools/bin:$PATH` (the venv has cmake 4.4.3 and `nv2avsh`; without it the build stops at step 1 with `nv2avsh: not found`) |
| console runs | `~/hakux-work/hardware/runs/<date>-<name>/`, captures and logs, never committed |

## Until the owner's networked power switch is in (expected 2026-09-25)

A wedged or powered-off console stays that way. So: no register writes,
`enable_shutdown_on_completion` false, every new XBE through the desktop
channel first, a timeout on every FTP poll, and one plain-text line to the
owner if the console stops answering.

## Log

- 2026-09-24. #31: the V0 check needed no run. The console's calibration
  captures give anchor recovery byte-identical to the goldens' (66 anchors),
  so the console stands in for the 1.0 goldens on `W buffering`. Registered
  `wbuf31-clipf35-prediction.md`, then built the `clip_top = 35` XBE.
- 2026-09-25. #31 RESULT: on silicon `ClipF-150-035` t1 anchors at **34** -- the
  absolute 4-grid at phase 2, `TriH`'s rule. `ct+2` refuted. C1, C2 and C3 all
  held, and every existing-test capture was bit-identical to its golden.
  `docs/testing/xbox-wbuf31-clipf35-2026-09-25.md`. 47 coarse-grid rules
  (grids 8/16/32, no mechanism) still fit, and a variant at `clip_top` 36-39
  would exclude them.
- Runner lesson (fixed in `lane/xbox-runner`): with networking off, an XBE
  never answers ping, so a run in progress LOOKS unreachable. It went dark
  at SITE EXEC and answered ping again 49 s later, back at the dashboard.
- 2026-09-25. #31 RESULT, fourth run (routed on #112 item C): at
  `clip_left` 300, `clip_top` 8, the first triangle anchors at **10**, the
  4-grid. `span_starts_at_clip` holds and master's `flatTop` clause (8) is
  refuted there. Master's rule gets all 24,952 of that triangle's pixels wrong
  in the float32 simulation. 57 four-literal fits survive, exactly the ones
  registered as voting grid. Every leg held (C1 22/22 identical).
  `docs/testing/xbox-wbuf31-clipf300-2026-09-25.md`.
- Wrapper lesson: `wbuf_anchor_recover.py` builds `_QUADS` from PRIMS at
  import, so a scoring wrapper that adds a quad capture must add it to
  `_QUADS` too, or its second triangle reads `second_of_quad` False. That
  made the t0 run's published count 75 instead of 93 (corrected in place).
