# Silicon references for the three suites nothing has captured, registered before the run

**Status: PRE-REGISTERED.** This was committed and pushed before the XBE ran
anywhere.

The owner asked for useful console work, because the console turns itself off
after 10 idle hours.

## Why these three

The NV2A index pins nxdk_pgraph_tests `6743b6a`. Three of its suites have no
silicon capture anywhere: no published golden (`6e159f15`, 2026-08-11) and
nothing in the 2026-09-19 calibration, which ran the older stock disc. So hakuX
cannot score them. Each was added upstream after the goldens:

| suite | added upstream |
|---|---|
| `Clipping precision` | `33e7c6b`, 2026-09-01 |
| `Surface as vertex array` | `0a441e0`, 2026-09-17 |
| `Fog planar vsh` | `6743b6a`, 2026-09-20 |

`PVIDEO` is the fourth gap, and it is excluded. `pvideo_tests.cpp` writes
`NV_PMC_ENABLE` directly (0, then 0xFFFFFFFF, then 0x1000). Under the standing
safeguards it waits for the owner's power switch. No other test source writes
PMC, PFIFO or PBUS directly (grep over `src/`).

_Corrected after the run (#296): `PVIDEO` is also interactive-only, and every
test ends in `FinishDrawNoSave`. It saves nothing and never runs in an
automated pass, so the PMC write is a reason not to run it by hand. It is not
why it has no reference._

## What runs

- **The XBE:** pristine `6743b6a`, with no instrument and no patch. XBE sha256
  `8612681afa58…`.
- **The suites:** the three above, plus `Alpha func` as a control.
- **The order:**
  1. An emulator dry run on the Thor, through the dispatcher.
  2. Then the console, via `tools/xbox/pgraph_run.py`: shutdown-on-completion
     off, network off, progress log on.
  - The console's test list comes from the dry run's `Starting` lines.

## Legs

- **Dry run (safety).** The Thor completes, with no crash signal.
- **C1 (instrument).** On the console, all 16 `Alpha func` captures are
  bit-identical to the published goldens. That is what the 2026-09-19
  calibration's small run found, 16/16.
- **Completion.** "Testing completed normally", and the console hands back to
  the dashboard.
- **The references.** Every test in the three suites leaves a capture.

This registers no prediction about values: there is nothing to compare against
yet, which is the point. The captures become the reference, stored on the host
under `~/hakux-work/hardware/runs/2026-09-25-refs6743/`, and the write-up lists
them.
