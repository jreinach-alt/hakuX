# Handoff: on-hardware work

Written 2026-09-24 at the end of a long session, for whoever picks up the
console next. Everything here is either *not in this repository* or cost more
than an hour to learn. The measured results are in
`pgraph-per-test-emulator-vs-hardware.md`, `nv2a-probe-pmc-findings.md` and
`nv2a-hardware-gap-list.md`; this file is the operating knowledge around them.

## 1. The instrument is not in this repository

The per-test PGRAPH register diff was written as uncommitted modifications to a
sibling checkout, `~/nxdk_pgraph_tests`, which is not a submodule and not
tracked here. **That checkout has since been reverted and is clean**, so the
patch below is now the only copy: apply it before building, or you get an
uninstrumented XBE. Four files:

```
src/pgraph_diff_token.h      src/tests/test_suite.h
src/pgraph_diff_token.cpp    src/tests/test_suite.cpp
```

`patches/pgraph-per-test-instrument.patch` is that diff, captured so
it survives. **Provenance matters:** it was written against tests-tree
`91a0de45` (2026-09-18) and currently applies on `6743b6ab` (2026-09-20, "Adds
more fog tests"). Check `git -C ~/nxdk_pgraph_tests log -1` before assuming it
still applies cleanly.

What it changes, and why each part is load-bearing:

- **Brackets each test body** rather than each suite. Upstream captures at
  suite `Initialize` and dumps at `Deinitialize`, so a difference cannot be
  attributed to a test.
- **A second `PGRAPHDiffToken`.** The per-test capture would otherwise
  overwrite the suite baseline, turning the suite residual into a diff against
  the last test.
- **Routes the dump to the FTP collector.** Upstream sends it only to
  `Logger::Log()`, which writes to a file *on the Xbox filesystem* — readable
  over FTP from a console, invisible on an emulator whose `E:` is a qcow2. The
  emulator half is the whole point of a comparison.
- **A read-only PMC watch** with `NV_PMC_BOOT_0` as a canary (see §4).

The empirical blacklist in `DumpDiff()` stays commented out deliberately. It
was derived on one machine; filtering inside the instrument hides exactly the
divergence it exists to find. Filter on the host, where both sides are visible.

## 2. What else exists only on this host

- **Built artifacts:** `~/nxdk_pgraph_tests/build-xbe/src/xbe/xbe_file/default.xbe`
  and the ISO beside it. Built from the instrumented tree before it was
  reverted; a rebuild from the clean checkout without the patch loses the
  instrument.
- **On the console:** `E:\Apps\PgraphPerTest\` — the XBE, its resources and
  `nxdk_pgraph_tests_config.json`. Launch it with
  `SITE EXEC E:\Apps\PgraphPerTest\default.xbe` over FTP. The older
  `E:\Apps\PgraphCalib\` is the calibration build; leave it alone.
- **Toolchain, installed without sudo.** `bison` and `flex` via
  `apt-get download` + `dpkg -x` into `~/.local/nxdk-tools`; `cmake` 4.4.3 from
  PyPI into `~/.local/nv2a-venv` (apt's 3.28 is too old for pbkitplusplus).
  nxdk is prewarmed. Use `-idirafter`, never `-I`, for extracted includes, or
  extracted libc headers shadow the system ones and the build dies in
  `osdep.h`.

## 3. Running it

Config is `d:\nxdk_pgraph_tests_config.json` — on the console `D:` is the
XBE's own directory, so it sits next to `default.xbe`.
`e:/nxdk_pgraph_tests/nxdk_pgraph_tests_config.json` is tried **first**, so if
that file exists it silently wins.

Four traps, each of which cost a wasted run:

- **`resources/sample-config.json` is stale.** It lists 34 tests for
  `Texture format` where the binary registers 40, and 11 for `Attrib float`
  where it registers 12. Read test names from the source, not from it.
  `TexFmt_R6G5B5` — the subject of `r6g5b5-golden-packing.md` — is one of the
  missing ones.
- **The config key is the test's *description*, not its filename.**
  `-NaN to +NaN (signalling)`, never `-NaNs_NaNs`. An unrecognised name is
  ignored in silence, so a typo means that test just does not run.
- **A suite-level `"skipped": false` sets that suite's per-test default to
  RUN**, overriding `skip_tests_by_default`. To run named tests only, omit the
  suite-level key entirely and list the tests.
- **`enable_shutdown_on_completion: true` powers the console off** at the end
  of the run, with the log still on its disk and no way to reach it. Leave it
  false on hardware; it is fine on the emulator.

FTP to the console: `xbox`/`xbox`, passive. **The server ignores the path
argument to `LIST`** — `CWD` first, then a bare `LIST`, or you will re-list the
root and believe it. A recursive walk written the obvious way reported 19,600
entries and zero hits.

## 4. Two hardware facts that look like bugs and are not

**`NV_PMC_ENABLE` reads `0x01110000` from a probe and `0x13111113` from a
graphics app.** Not a bit-layout mystery: `pb_init()` writes
`NV_PMC_ENABLE_ALL_ENABLE` — `0xFFFFFFFF`, `nxdk lib/pbkit/outer.h:87` — at
`pbkit.c:2400`, so the second value is the read-back of an all-ones write and
is therefore the *implemented-and-settable bit mask*. A probe that never calls
`pb_init()` measures a machine with every engine down. Any "enable", "status"
or "busy" register read from a bare probe describes an idle machine, not the
chip.

Corollary: **writing `0` to that register halts the console.** `outer.h:88`
calls it `NV_PMC_ENABLE_ALL_DISABLE`. It cost a power cycle. Writing the
register is not exotic — every title does it at startup — writing zero is.

**PVIDEO is inert to a probe for the same reason.** `hardware/probe/pvideo`
found all 12 registers dead (`orig=0 ones_readback=0 zeros_readback=0`) and
prescribed a targeted `NV_PMC_ENABLE` write to bring the block up. The
diagnosis was right and the remedy is unnecessary: the prerequisite is
`pb_init()`, not a hand-rolled write to the register that halted the console.

## 5. Corrections owed, and the reason for them

`nv2a-hardware-gap-list.md` list A says **PVIDEO overlay composition is
"modelled nowhere"**, citing `d->vga.enable_overlay` and `overlay_draw_line`
being commented out. **That is wrong, and the row has been struck** (the gap
list now carries a dated note in its place). Those are fossils
of the legacy QEMU VGA path — `VGACommonState` has no such fields anywhere in
the tree and `nv2a_overlay_draw_line` does not exist, so they were never a
switch anyone could flip. The overlay *is* composited, in the renderer's
display shader (`pgraph/gl/display.c:216-222`, gated at `:328` on
`d->pvideo.regs[NV_PVIDEO_BUFFER] & NV_PVIDEO_BUFFER_0_USE`, with a Vulkan
equivalent). A comment on #110 repeats the same error.

The mistake was reading commented-out lines as evidence of absence without
walking the chain to the code that actually drives the display.

What survives from that entry: `pvideo_write`'s `default:` stores all 32 bits
unmasked, and those values now demonstrably feed a shader that composites.

`PvideoTests` is `interactive_only=true` and every test ends in
`FinishDrawNoSave(...)` — the suite saves no images. The overlay is composited
downstream of the framebuffer, so a back-buffer capture shows the background
either way. Running those under the normal harness and diffing captures would
show agreement on both sides and mean nothing.

## 6. Open state at handoff

As of 2026-09-24 23:30 PDT; labels move hourly, so read the PRs, not this.

| item | state |
|---|---|
| #201 per-test diff + probe fixes | folded |
| #202 `-NaNs_NaNs` third explanation | folded |
| #203 `NV_PMC_ENABLE` under load | open, `fold-ready` |
| #206 dispatcher `SCRIPT_DEPS` + two guards | open, `fold-ready` |

**#206 matters beyond its own diff.** It fixes a one-line defect that idled
both handhelds for eighteen hours: `SCRIPT_DEPS` (the re-exec trigger) covered
four files while `snapshot_scripts()` ships nine, so an edit to `affinity.py`
never reached a running worker. During the session the fix was applied directly
to the deploy tree to unstick the fleet; **that edit has since been reverted
and master does not carry it yet.** The bug is latent again — the workers
restarted recently and re-snapshotted, so it is not biting, but the next edit
to any of `affinity.py`, `devices.sh`, `captures.py`, `make_test_iso.py` or
`extract_results.py` brings it back, silently. Folding #206 is the permanent
fix.

## 7. Verified working at handoff

Run on the console on 2026-09-24, after it had been powered down for four days
and cold-booted, with the install already on its disk and nothing rebuilt:

- 7 `PGRAPH-DIFF` markers — 5 tests and 2 suite residuals — so per-test
  attribution works;
- `NV_PMC_BOOT_0` canary `0x02A000A3` on every one, so the read path is sound;
- `NV_PMC_ENABLE` `0x13111113`, **identical to the 2026-09-20 measurement**
  across a power cycle;
- `NV_PGRAPH_SURFACE` bit 0 set in every observation and `NV_PGRAPH_TEXFMT0`
  bits 4-5 set in every observation, matching 53/53 and 40/40 from the
  original sweep.

So the instrument, the console install and the two register findings all
reproduce from cold. If a future run disagrees, suspect the run, not this.

Recipe: point `output_directory_path` at a fresh directory, `SITE EXEC
E:\Apps\PgraphPerTest\default.xbe`, then poll
`RETR <outdir>/pgraph_progress_log.txt` until it contains
`SUITE-RESIDUAL Texture format`. Takes about ninety seconds for five tests.

## 8. A note on choosing the next thing

`ROADMAP.md` says in as many words that "every pgraph test passes" is the wrong
target: priority 1 is crashes and hangs, priority 2 is the ~300 tests over
50,000 pixels, and precision differences are **tracked, not chased**. A good
deal of this session went into register-level divergences with no established
pixel consequence — unnamed bits in `NV_PGRAPH_SURFACE` and `NV_PGRAPH_TEXFMT0`
that are real, reproducible, and by the write-up's own admission produce no
rendering defect today. That is interesting and it is not the roadmap.

The instrument is built and the console is calibrated. Point them at something
the roadmap ranks.
