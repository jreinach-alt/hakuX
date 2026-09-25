# #112 items 3 and 4: `nxdk_vsh_tests` on the console -- registered before the run

**Status: PRE-REGISTERED.** Committed and pushed before either stage boots.

## What exists, and what this adds

Published silicon goldens for the vertex-shader program already exist:
[`abaire/nxdk_vsh_tests_golden_results`](https://github.com/abaire/nxdk_vsh_tests_golden_results)
@ `b14defa4b2`, pushed 2022-06-16. They cover **six** of the current program's
nine suites. The three with none are `CPU Shader Tests`, `SpyVsSpy` and
`Exceptional Float` (added 2025-06-04). The last is #112 item 4's direct test
(NaN / Inf / -0 through `_MUL` and `_RCC`), and #223's largest `W_param`
captures are `_RCC` of a zero W.

## What runs

| | |
|---|---|
| program | `abaire/nxdk_vsh_tests` `a8a19bb` + two local commits on branch `hakux/completion-marker` (`~/nxdk_vsh_tests`): `618a7ce` logs "Testing completed normally" when the driver returns; `7c9068d` reads a suite list from `d:\vsh_tests.cnf`. Neither changes what any test draws. Built with `AUTORUN_IMMEDIATELY` and `ENABLE_PROGRESS_LOG`; `ENABLE_SHUTDOWN` off |
| XBE | sha256 `9eedaa3ac5338c7ead81cb23f8e3865977b5f5d5ebcba37db1ec8df787fc7e35` |
| nxdk | `bafba08` (the `pbkit_extensions` branch this program pins, not the pgraph tree's `73c9590`) |
| runner | `tools/xbox/pgraph_run.py --kind vsh` (PR #219 branch). It refuses an XBE lacking the reboot message, the autorun entry, the completion line or the suite-list path, and it uploads and size-checks the suite list before launch: a build that reads the list ASSERTs inside the XBE when the list is missing |
| console | GPU rev 163 / MCP rev 212 |

## Two stages, as a lockup safeguard

The console cannot be power-cycled remotely yet, and this program has never
run on it.

- **Stage 1** (`E:\Apps\VshStage1\`): the six suites with goldens. The goldens
  show these ran on silicon.
- **Stage 2** (`E:\Apps\VshStage2\`): `CPU Shader Tests`, `Exceptional Float`,
  `SpyVsSpy`. Stage 2 runs only after stage 1 has completed and been fetched,
  so a hang in stage 2 costs no stage-1 data.

## What is predicted

**Stage 1 is a calibration.** Every capture is compared with its golden and
classified bit-identical, differs-in-label or differs-in-body. The program has
changed since 2022 (renamed tests, the math library replaced on 2025-10-04),
so a difference is first checked against the test file's history. Only a body
difference that no program change explains counts against this console
standing in for the 2022 hardware. No count is predicted; the classification
is the result.

**Stage 2 is a survey:** no value is predicted. Its captures become the
project's first silicon goldens for those three suites. The one leg is that
it completes ("Testing completed normally") with a capture for every test
the log names.

What neither stage does is compare the emulator. That comparison, hakuX
against these captures, is the step these runs make possible, and it needs
the vsh program running under the dispatcher.

## Addendum, registered after stage 1 and before anything else runs

**Stage 1 ran** (23:49:50 PDT, 53 s, "Testing completed normally", eight
captures). All eight differ from their 2022 goldens, and **none of it is
hardware**. The program switched from pbkit's debug font to IBM Plex Mono
since 2022. Every difference has the same maximum delta (the text colour),
sits in the text rows, and on `MAC_mov`, read by eye, the printed values are
identical (`1.000000,2.000000,-3.000000,-4.123450`). A pixel diff against
these goldens is a font diff.

So the build gains a third local commit: `TextOverlay::Dump` writes each
test's printed strings to `<name>.txt` beside its PNG. That text is the exact
form of the result, and the emulator comparison will diff it too. This
commit changes no pixel the tests draw. New XBE sha256
`fb530b00f02f5aefe4331a6169eee87c057e96f2a550f6769bbc6fd2d66b342a`.

Runs that follow: **stage 1b** repeats stage 1's six suites with this XBE
(`E:\Apps\VshStage1b\`); its PNGs must be bit-identical to stage 1's, a
control that the new commit draws nothing different. Then **stage 2** as
registered (`E:\Apps\VshStage2\`), with this XBE.
