# `nxdk_vsh_tests` on silicon: first captures of the three suites without goldens

**Measured 2026-09-25 on the project console (GPU rev 163 / MCP rev 212).**
Registered beforehand in
[`docs/lanes/xbox/vsh-silicon-prediction.md`](../lanes/xbox/vsh-silicon-prediction.md)
(`c13b50c956`, addendum `ba4ce94d33`). #112 items 3 and 4; bears on #223.

## What was run

`abaire/nxdk_vsh_tests` `a8a19bb` plus three local commits on
`~/nxdk_vsh_tests` branch `hakux/completion-marker`. None changes what a test
draws, and stage 1b below proves it for the six suites that ran twice:

- `618a7ce` logs "Testing completed normally" when the test driver returns;
- `7c9068d` reads a per-run suite list from `d:\vsh_tests.cnf`;
- `c3dde45` writes each test's printed text to `<name>.txt` beside its PNG.

nxdk is at `bafba08`, the `pbkit_extensions` branch this program pins. It was
driven by `tools/xbox/pgraph_run.py --kind vsh`, as three runs of about 53 s
each, and every one handed the console back to the dashboard.

| run | suites | files | result |
|---|---|---:|---|
| stage 1 | the six with 2022 goldens | 8 PNG | completed; XBE `9eedaa3a…` |
| stage 1b | the same six | 8 PNG + 8 TXT | completed; **PNGs byte-identical to stage 1** (the text commit draws nothing different, and silicon repeats exactly); XBE `fb530b00…` |
| stage 2 | CPU Shader Tests, Exceptional Float, SpyVsSpy | 2 PNG + 2 TXT | completed; XBE `fb530b00…` |

## Stage 1: why a pixel diff against the 2022 goldens says nothing

All eight stage-1 captures differ from
`abaire/nxdk_vsh_tests_golden_results` @ `b14defa4b2`, by 8,627 to 64,811 px,
and none of it is hardware. **The program changed its font.** In 2022 it
printed with pbkit's debug font; today it draws IBM Plex Mono through SDL_GPU.
The evidence that this is the whole difference:

- every one of the eight has the same maximum delta, the text colour;
- the differences sit only in the text rows;
- on `MAC_mov`, read side by side, the values are identical:
  `1.000000,2.000000,-3.000000,-4.123450` on both.

These tests' results *are* the numbers they print. The `.txt` files from
stage 1b are that result in exact form, and they are what the emulator
comparison should diff. The 2022 goldens can now only be read by eye (or
OCR), which is why no count of "matching" captures is claimed here.

## Stage 2: the three suites that never had goldens

- **`Exceptional Float`**, passthrough, on silicon:

  ```
  Inf, -Inf, NaN, -Nan:            inf, -inf, nan, nan
  Max, -Max, Min, -Min:            3.402823e+38, -3.402823e+38, 0.000000, -0.000000
  MaxSub, -MaxSub, MinSub, -MinSub: 0.000000, -0.000000, 0.000000, -0.000000
  ```

  Infinities and NaN pass through. The program prints with `%f`, so ±Min and
  the subnormals read ±0 whether silicon flushed them or not. That limit is
  the test program's print format, not a measurement; the sign of zero
  survives.
- **`SpyVsSpy`**: the game's menu shader. `oPos`, `R1.x` and `R11` are
  recorded in `Menu.txt`.
- **`CPU Shader Tests`** ran all 17 ops (ADD … SLT, including RCC and RCP)
  and saved nothing, by design. It seeds its inputs from the clock, checks
  nxdk's CPU emulation of each op against silicon, and prints only
  mismatches, to the screen. Not golden-able without changes; recorded so
  nobody expects files from it.

## Silicon values worth having now (stage 1b text, exact)

`ILU_RCP_Tests`, `RCP` on silicon: `rcp(1)=1`, `rcp(2.123)=0.471032`,
`rcp(Min)=8.507059e+37`, `rcp(Max)=0`; `rcp(0)=inf`, `rcp(Inf)=0`,
`rcp(NaN)=nan`; `rcp(-MaxSub)=-inf`, `rcp(MinSub)=inf`, `rcp(-MinSub)=-inf`,
so subnormal inputs are treated as signed zero. #223's largest `W_param`
captures are `_RCC` of a zero W, and #112 item 4 is `_RCC`'s signed-zero
clamp; these are the silicon rows those comparisons need.

## Next

The comparison these runs exist for is hakuX running the same XBE and
diffing the `.txt` files. The dispatcher cannot run it yet. Its disc path
assumes nxdk_pgraph_tests' config and progress log, and this build needs
`vsh_tests.cnf` inside its disc or it stops on the missing file. Captures and
text stay on the host under
`~/hakux-work/hardware/runs/2026-09-25-vsh/`.
