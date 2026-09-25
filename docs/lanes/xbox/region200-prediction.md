# #200 on silicon: does the console set the register holes? Registered before the run

**Status: PRE-REGISTERED.** This file, the parser and the tests-tree patch
were committed and pushed before the XBE ran anywhere. That includes the
emulator dry run.

The host routed this to lane.xbox on #112 (item B, 14:20:31Z). #200 is
`blocked_on` it.

The question, from #200's `[job.cloud]` comment of 07:44Z (PR #230's static
enumeration): `pgraph.c` rebuilds 20 registers field by field. Each one has a
mask of bits that `nv2a_regs.h` does not declare and no method handler writes,
called the hole. Three declared fields are also never written:

- `TRAPPED_ADDR` DHV;
- `CSV0_D` FOG_MODE;
- `CSV1_A` T0_ENABLE/MODE/TEXTURE.

Does silicon set any of these bits?

There is no pixel arm. Nothing reads these bits, so this is a register
measurement for #200's tracker row, not an accuracy fix.

## What runs

- **The XBE.** nxdk_pgraph_tests `6743b6a` (the index's pinned tests commit),
  plus `docs/testing/patches/pgraph-per-test-instrument.patch`
  (`hakux/per-test-instrument` `8158852`), plus `region200_force_diff.patch`
  (`0bbd900`).
  - The last patch forces the per-test diff on, because hakuX's
    `make_test_iso.py` writes `enable_pgraph_region_diff: false` into every
    disc config. Without it, the emulator dry run could not exercise the code
    the console runs.
  - The instrument only reads. The PGRAPH region comes from
    `pb_fetch_pgraph_registers`, and PMC `BOOT_0`, `INTR_0`, `INTR_EN_0` and
    `ENABLE` are plain loads. Nothing writes MMIO.
  - XBE sha256 `361c904af704…`, ISO `d9dfbdd79298…`.
- **The suites.** Twenty of them, about 790 tests by the goldens' count:
  - Texture format, Texture palette and Surface format cover SURFACE, TEXFMT
    and TEXPALETTE.
  - Lighting control, Fog gen, Vertex shader rounding tests and Vertex shader
    swizzle tests cover CSV0_C/D and CHEOPS_OFFSET.
  - Texgen and Texgen with texture matrix cover CSV1_A/B.
  - Antialiasing tests cover ANTIALIASING.
  - Blend surface covers BLEND.
  - Alpha func, Stencil, Stencil func, ZPass pixel count and ZMinMaxControl
    cover CONTROL_0..3 and ZCOMPRESSOCCLUDE.
  - Front face covers SETUPRASTER.
  - Combiner and Texture signed component tests cover SHADERCTL.
  - Texture shadow comparator covers SHADOWCTL.
  - No suite drives NSOURCE or TRAPPED_ADDR deliberately.
- **The order.**
  1. Emulator dry run on the Thor through the dispatcher, ref `84a67b9cf8`.
     Its `pgraph.c`, `pgraph.h` and `nv2a_regs.h` are identical to master
     `21946df29b`.
  2. Then the console, via `tools/xbox/pgraph_run.py`, with shutdown-on-completion
     off, network off and the progress log on.
  - The console's per-test list is taken from the dry run's own
    `PGRAPH-DIFF <Suite>::<Test>` labels, because `pgraph_run.py` refuses
    suite-level entries.

## Legs

The judge is `region200_parse.py`. It was fixed before the data and tested on
synthetic logs: a middle-line-only bit, a bad canary, and no instrument.

- **K (canary).** Every `PMC BOOT_0` line on the console reads `0x02A000A3`.
  Otherwise the parser refuses the log and the run is void.
- **E (hakuX, from the dry run's log).** No bit inside any hole mask, and no
  declared-never-written bit, is ever set in a from/to value of these 20
  registers. This is #230's static enumeration checked at runtime. A hit
  means the script missed a write path, which is #200's own refutation test.
- **R (reproduce #201 on silicon).** Wherever SURFACE (`0x710`) appears, bit 0
  is set. Wherever TEXFMT0 appears, bits 4-5 are 3. #201 saw both in 53/53
  and 40/40 observations.
- **Q (the question; no prediction).** For each register, the hole bits and
  declared-never-written bits the console shows set, and which tests show
  them.
  - The instrument's blind spot, stated before the data: a register is listed
    only when it changed inside a test's bracket. A hole bit is therefore
    "seen" only through a register that moved. NOT SEEN means no evidence;
    it does not mean zero.
- **Completion.** Both logs carry "Testing completed normally". The console
  run hands back to the dashboard.

## Where the result goes

The numbers go on #200. The parser's JSON for both sides is committed as a
scored result. The raw logs stay on the host under
`~/hakux-work/hardware/runs/2026-09-25-region200/`.
