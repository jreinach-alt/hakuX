# Reaching Blend's 1,568 `TestDetailed` goldens: two routes, one already open

Written 2026-09-13. Read
[`../investigations/test-coverage-gaps.md`](../investigations/test-coverage-gaps.md)
first -- it holds the mechanism and the correction this page builds on.

## The gap is not a gap any more, and that is the first thing to know

`Blend tests` has 1,673 goldens; the current disc runs the 105 `#spot_` grids.
The other 1,568 -- the full `(sfactor, eqn, dfactor)` cross-product -- are
marked interactive-only at `blend_tests.cpp:92` and excluded by
`test_driver.cpp:132`'s unconditional `suite->RunAll(false)`. A disc runtime
config cannot lift that: `RuntimeConfig::ApplyConfig` only ever calls
`TestSuite::DisableTests`, which erases from `tests_`.

**They have nevertheless already been captured.** The `v2025-03-14` release
predates the retirement and still registers them non-interactively.
`~/hakux-work/res_oldblend` holds **1,568 captures, one per golden**, with a
progress log showing every test completing, run 2026-09-12 from
`~/hakux-work/iso-old-blend.iso` (base `~/hakux-work/iso-2025-03-14.iso`).
Their names match the 1,568 non-`#spot_` goldens exactly -- 1,568 in both
sets, 0 goldens uncovered. Three investigations already score against them:
`blend-fifth-quad.md`, `blend-signed-full-oracle.md`,
`blend-stack-c-is-render-target-aliasing.md`, and issue #50.

So anyone told that 28% of the corpus is unreachable should stop there. The
oracle is on disk. What follows is about a *second* route with one specific
advantage, not about a hole.

## What the second route buys

The 2025 disc is a different test binary, so its results carry a different
`disc_id` and cannot be combined with anything else in one run. A patched
*current* XBE would put the 1,568 on the same test revision as every other
suite, which is what the scoreboard needs to stop reporting `Blend` as a
floor, and what lets `TestDetailed` ride a multi-suite sweep disc.

## The patch, and why it is one byte

`docs/testing/patch_xbe_run_all_interactive.py` flips the `false` at
`test_driver.cpp:132` in a prebuilt image. It needs no toolchain.

    push $0x0   ->   push $0x1        6a 00 -> 6a 01

On the stock image (`~/nxdk_pgraph_tests_xiso.iso`, md5
`624699f58e98f503d8098c82678daf24`): `default.xbe` at sector 265, call site at
virtual address `0x349381`, the immediate at XBE offset `0x339384`, ISO offset
`0x3BDB84`. The patched image differs from the stock one in **exactly that one
byte** (`cmp -l`, one line).

The tool locates the site by pattern and refuses rather than guessing. Five
independent checks must all agree:

1. The strings `DEBUG: [TestDriver] Starting suite ` and
   `...Completed suite ` are each unique in `.rdata` and referenced from
   `.text`; their references bound `TestDriver::RunAllTestsNonInteractive`.
   The menu site has no such neighbours -- this is what separates the two.
2. `8b 0b 6a 00 e8` (`mov (%ebx),%ecx; push $0x0; call`) is unique in the
   whole of `.text`, and lies inside those bounds.
3. It is immediately preceded by `call *0x4(%eax)` and followed by
   `mov (%ebx),%ecx; mov (%ecx),%eax; call *0x8(%eax)` -- the `Initialize()`
   and `Deinitialize()` virtual calls that bracket `RunAll` in the source.
4. The callee has **exactly two** call sites, as the source does.
5. The other one is identified positively as
   `MenuItemSuite::ActivateCurrentSuite` by the inlined
   `SetSavingAllowed(true)` store (`movb $0x1,0x21(%eax)`) that sits between
   its `Initialize()` and its `RunAll` and has no counterpart in the driver.

It refuses on the 2025 image (no such log strings), which is the behaviour
wanted: a tool that patched whatever matched loosest would be worse than no
tool.

All six XBE section digests are zero in an nxdk build, so a `.text` edit
invalidates nothing, and XISO carries no per-file checksum. Both are checked
at run time, not assumed.

## The flip adds Blend's 1,568 and nothing else

Verified against the test-suite source at `~/nxdk_pgraph_tests`, not assumed.
There are **two independent filters**:

* **per test**, `interactive_only_tests_`, which is what `RunAll`'s argument
  gates. It is inserted into from exactly two places in the tree:
  `blend_tests.cpp:92` and `clipping_precision_tests.cpp:32`.
* **per suite**, `interactive_only_`, checked at `test_driver.cpp:120` with a
  `continue` **before** `RunAll` is reached, so `RunAll`'s argument cannot
  affect it. Exactly two suites set it: `PVIDEO` (`pvideo_tests.cpp:46`) and
  `Clipping precision` (`clipping_precision_tests.cpp:23`).

`Clipping precision` is on both lists, and the suite-level one wins first, so
its per-test entries are unreachable either way. `PVIDEO` has no per-test
entries. That leaves Blend as the only suite whose test count changes: 105 ->
1,673.

## What still blocks a scored run from the patched disc

**The request path cannot name a base ISO.** `dispatcher.sh` reads
`DISPATCH_BASE_ISO` from its own environment (lines 346 and 377), and
`request.sh` has no option that sets it, so a single request cannot ask for a
non-stock disc; setting it on the serving dispatcher would silently re-base
every other queued request. Plumbing a per-request `base_iso` through those
two files is the missing piece, and neither is this page's to change.

Two smaller things found while looking:

* **`request.sh --tests` is accepted and then dropped.** It is parsed, written
  into the request JSON, and documented in `dispatcher.sh`'s header comment as
  "optional, solo arm only" -- but the dispatcher builds
  `make_test_iso.py` arguments only from `suites` and `skip_tests`. A
  requester who narrows with `--tests` gets the whole suite and no warning.
* **Narrowing the patched disc needs an allow-list, not `--skip-test`.**
  `DisableTests` does erase from `tests_` before `RunAll` runs, so skipping
  works -- but trimming 1,673 tests to a handful means ~1,660 `--skip-test`
  arguments, and `check_disc.py` already fails silently on a 104 KB config.
  The config schema supports the opposite polarity (`skip_tests_by_default`,
  which `make_test_iso.py` already sets when `--suite` is given), so a
  `--only-test SUITE::TEST` flag would express it in a few hundred bytes.

## Disc identity, confirmed rather than trusted

`dispatcher.sh` keys `disc_id` on the base ISO's basename, size and mtime and
prefixes anything that is not the stock path. Run against the same
single-suite `Blend_tests` request:

| base image | `disc_id` |
|---|---|
| `~/nxdk_pgraph_tests_xiso.iso` (stock) | `Blend_tests` |
| `~/nxdk_pgraph_tests_xiso_interactive.iso` (patched) | `iso:85b525/Blend_tests` |
| `~/hakux-work/iso-2025-03-14.iso` (2025 release) | `iso:fddc95/Blend_tests` |

`ab_compare.py:256` dies when `disc_id` differs, so a patched-disc result
cannot be compared against a stock-disc one by accident.

## Reproducing

    # report only, writes nothing
    docs/testing/patch_xbe_run_all_interactive.py ~/nxdk_pgraph_tests_xiso.iso --dry-run

    # write a new image; it refuses to write over its input
    docs/testing/patch_xbe_run_all_interactive.py ~/nxdk_pgraph_tests_xiso.iso \
        -o ~/nxdk_pgraph_tests_xiso_interactive.iso

The stock image is opened read-only and its md5 and mtime are unchanged by
either invocation. **Never patch it in place**: every result on disk was
scored against that exact file, and replacing it would silently re-base the
corpus.
