# Lane `nv2a-hw-probe` (PR #201)

Branch `claude/nv2a-hw-probe`. Two unrelated halves: a per-test PGRAPH register
diff of this emulator against the project's console, and three fixes to
`tools/nv2a_probe`.

## What is here

| | |
|---|---|
| `docs/testing/pgraph-per-test-emulator-vs-hardware.md` | the measurement: 24 registers move on the emulator, all declared; 336 on the console, 308 undeclared |
| `docs/testing/patches/nxdk_pgraph_tests-6743b6ab-per-test-pgraph-diff.patch` | the instrument, so the measurement can be repeated |
| `tools/nv2a_probe/probe/probe_cfg.h`, `test_probe_cfg.c` | `D:\nv2a_probe.cfg`, so one binary runs on hardware and under emulation |
| `tools/nv2a_probe/probe/Makefile`, `nv2a_window.h`, `host/probe_driver.py` | `PROBE_ALLOW_HAZARDS`, the emulator-only build |
| `tools/nv2a_probe/host/supervisor.py` | an unreachable console is not proof of a wedge |

## What the remediation changed, and why it is the shape it is

Audit pass 1 (`docs/audits/2026-09-21-claude/nv2a-hw-probe-pass1.md`) found
1 HIGH and 5 MEDIUM. The HIGH is the one worth carrying forward.

**A build flag is not a safety property until something can observe it.** The
first version of `PROBE_ALLOW_HAZARDS` argued -- correctly -- that a build flag
beats a config key, because a config key means the console binary can be talked
into a hazardous write by editing a file next to it. But it then wrote the
hazard-allowed image to `probe/bin/default.xbe`, the same path the FTP deploy
reads, under the same title, with the same size; nxdk's Makefile tracks sources
and not `CFLAGS`, so dropping the flag did not even rebuild the object; and the
`-HAZARDS-ALLOWED-EMULATOR-ONLY` suffix the probe announces in its HELLO was
read by nothing on the host. Three ways to end up with a no-refusal probe on
the console and no way to notice. The fix is one per gap: separate
`XBE_TITLE`/`bin-hazards/`, a variant stamp that deletes the objects when the
flag changes, and `probe_driver.py` refusing the session unless the caller
passed `allow_hazards`. **All three are load-bearing; none of them alone is.**

**Untestable code migrates into a header.** `probe/main.c` is compiled by
nothing on the host -- it needs nxdk and an Xbox -- so anything decided inside
it is unreachable by `run_tests.sh`, the suite whose own preamble says a check
that cannot fail is decoration. The config parser moved to `probe_cfg.h` and
the write predicate to the generated `nv2a_window.h`, and both configurations
of the allow-list are now compiled and mutated. What is left in `main.c` is the
socket loop and the single MMIO store. **If you add a decision to `main.c`,
move it into a header first, or it is untested by construction.**

**A retraction needs an absence check.** The supervisor stopped claiming "the
processor is gone" from ICMP alone, and the tests asserted the two sentences
that replaced it -- which pass just as happily with the old claim still in the
message. There is now a check for the absence of the phrase and a mutant that
puts the wording back, and the same retracted claim had also survived in
`README.md`, three sections away from the code.

**A measurement's instrument has to be in the repository.** The numbers in the
document came from a modified `nxdk_pgraph_tests` described in prose, with no
sha and no patch, and the modification existed only as uncommitted changes in
one checkout. The patch and the base sha are committed now, dated against the
tests tree's own mtimes -- which turn out to be *later* than the build the run
used, so the patch is what to re-measure from, not a warrant for the numbers.
`*.patch` in the root `.gitignore` had been quietly keeping files like it out
of commits; there is now a negation for `docs/testing/patches/`.

## What the next lane should not repeat

- **Do not look for the raw PGRAPH dumps.** They were not preserved. A sweep of
  this box on 2026-09-21 found `PGRAPH-DIFF` in the tests tree's own source and
  binaries and nowhere else. Rerunning costs one run per side; recovering them
  costs more than that and will fail.
- **Do not trust `52 tests, 54 blocks` to mean two tests dumped twice.** The
  patch emits one `SUITE-RESIDUAL <suite>` block per suite on top of the
  per-test ones: 52 + 2.
- **The probe suite is manual.** No workflow references `tools/nv2a_probe`, so
  a green CI rollup on a PR touching it says nothing. Run
  `bash tools/nv2a_probe/run_tests.sh`; it needs only `cc` and `python3`.
- **Building the probe needs no device and works on this host:**
  `NXDK_DIR=$HOME/nxdk_pgraph_tests/third_party/nxdk`,
  `PATH=$HOME/.local/nxdk-tools/bin:$NXDK_DIR/bin:$PATH`. Both variants were
  built during remediation, which is how `main.c` gets compiled at all.
