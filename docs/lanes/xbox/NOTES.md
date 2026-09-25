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
