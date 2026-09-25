# Audit pass 2 — PR #201, `claude/nv2a-hw-probe`

*nv2a: per-test PGRAPH diff against the console, and three probe fixes*

- **Auditor:** `job.cloud`, 2026-09-21, pass 2 (scenario verification)
- **Pass 1:** [`nv2a-hw-probe-pass1.md`](nv2a-hw-probe-pass1.md) — 1 HIGH,
  5 MEDIUM, 6 LOW → `needs-remediation`
- **Head at audit:** `569fd86363`. CI `build`/`build` both SUCCESS.
- **Branch position:** 7 ahead / **0 behind** `origin/master` (`01538395b7`,
  merged in at `3f024d021b`). `preflight.sh` passes on this tree.
- **Verdict:** every pass-1 scenario is discharged, and six of the seven were
  discharged *mechanically* rather than by reading the patch → `fold-ready`

---

## How this pass was run

Pass 2's question is not "is there a commit for each finding" but "can the
scenario still happen". Where a scenario named a concrete mechanism, I ran the
mechanism rather than reading it:

| what I ran | why |
|---|---|
| `bash tools/nv2a_probe/run_tests.sh` | 3 baselines green, **21 mutants, all killed**, exit 0, tree clean afterwards |
| both probe builds, from a scratch copy of `probe/` in `/tmp` | H1 mechanisms 1 and 2 end-to-end — this is the only thing that compiles `main.c` at all |
| `make -n -p` across a safe↔hazards↔safe cycle | H1 mechanism 2 in isolation, without waiting on a link |
| each driver and supervisor mutant applied by hand, reading **which row** went red | an exit code is a coarse discriminator; a mutant killed by a crash tests nothing |
| `git apply --check` of the committed instrument patch against the tests-tree sha it names | M4 |
| `Files:` in the PR body diffed against `git diff --name-only origin/master...HEAD` | M5 |

Nothing was run against the worktree's own `host/` or `probe/` — every mutation
and every build happened in `/tmp` copies, and `git status` is clean.

---

## H1 — the hazard-allowed build is indistinguishable from the safe one

**Pass-1 scenario.** An operator builds the emulator variant to exercise
`NV_PMC_ENABLE` under xemu, returns to the console the same day, FTPs
`probe/bin/default.xbe` across, and a hand-issued write finds both hazard
refusals compiled out. Three things had to hold and none did: no separate build
product, no rebuild when the flag is dropped, and a HELLO suffix with no
reader.

**Cannot occur.** All three gaps are closed, and I checked each one running.

### 1. There is a separate build product

`probe/Makefile:42-51` gives the variant its own `XBE_TITLE` and `OUTPUT_DIR`.
Both are the real nxdk variables — `nxdk/Makefile:5-10` defaults them and
`:40`/`:107` consume them as `$(OUTPUT_DIR)/default.xbe` and
`$(CXBE) -TITLE:$(XBE_TITLE)`.

Built both, from a scratch copy, with the toolchain in `NOTES.md:73-76`:

| | `bin/default.xbe` | `bin-hazards/default.xbe` |
|---|---|---|
| `HAZARDS-ALLOWED-EMULATOR-ONLY` in the image | **absent** | **present** |
| XBE title (UTF-16 in the certificate) | `nv2a_probe` | `nv2a_probe_HAZARDS` |

The path the documented build writes and the `SITE EXEC` deploy reads
(`README.md:63`, `:227-232`) can only ever hold the safe image — pass 1's
`:187`/`:200-201` are the same lines before this diff moved them. Both images
also built cleanly, which is the
first time `main.c` has been compiled in **either** configuration — so pass 1's
"nothing compiles the hazard-allowed configuration to confirm this
mechanically" is now retired as well.

### 2. Removing the flag rebuilds

`Makefile:56-64` writes a variant stamp at parse time and deletes
`main.obj`/`main.c.d`/`main.exe`/`main.lib`/`main.exe.manifest` when it
changes. `nxdk/Makefile:73` confirms those are the object paths
(`$(basename $(SRCS)).obj`, and `SRCS = $(CURDIR)/main.c`).

Driven through a full cycle:

```
before any make                     main.obj=present  stamp=none
make            (safe)              main.obj=DELETED  stamp=safe
make            (safe, no switch)   main.obj=present  stamp=safe     <- not touched
make PROBE_ALLOW_HAZARDS=y          main.obj=DELETED  stamp=hazards
make PROBE_ALLOW_HAZARDS=y (again)  main.obj=present  stamp=hazards  <- not touched
make            (back to safe)      main.obj=DELETED  stamp=safe
```

And through the real compiler: the safe object's md5 is
`562e58af5d…`, the hazards object's is `bcbc4bf163…`, and building safe →
hazards → safe with no `clean` returns the object to `562e58af5d…`
byte-for-byte. The hazard-allowed object does not survive a variant switch.
The stamp deletes nothing when the variant is unchanged, so it costs a
same-variant rebuild nothing.

### 3. The HELLO announcement has a reader

`probe_driver.py:133`, `:158-166`: `Session` parses `HAZARD_MARK` out of the
HELLO and raises `ProbeError` unless the caller passed `allow_hazards`.
`ProbeServer.__init__` defaults it to `False` (`:259`, `:263`) and passes it
down to every session (`:271-275`), so both entry points inherit the safe default
— `read_blocks.py:56` constructs the server with no opt-in at all, and
`sweep_writable_bits.py:241` only sets it from `--allow-hazards`.

The check is tested, and tested by rows that discriminate. Applying each mutant
by hand and reading the output:

| mutant | rows that went red |
|---|---|
| `self.hazards_allowed = False` (the marker is not read) | "must not be accepted by default" **and** "accepted when the caller opted in, flagged as hazardous" |
| `if False:` (the refusal is removed) | "must not be accepted by default" only |

Neither mutant dies of a crash, and `test_driver_loopback.py:191-201` carries
the negative control pass 1's fix sketch needed — a plain probe must *not* be
flagged — so a driver that refused every session would fail too.

**The limit of this, stated for pass 3 and the next lane.** `OUTPUT_DIR` and
`XBE_TITLE` are plain `=` assignments, so a command-line
`make PROBE_ALLOW_HAZARDS=y OUTPUT_DIR=bin XBE_TITLE=nv2a_probe` does override
them — I checked, and it does. That is a deliberate act, not pass-1's accident,
and it is still caught: the HELLO suffix is compiled into the binary, so it
does not care where the file was written or what the
image is called (`main.c:62-66`, `:337`), and mechanism 3 refuses the session
anyway. Three mechanisms
were the right answer precisely because each one alone has a hole.

---

## M1 — `main.c` pointed at a Makefile comment that did not exist

**Pass-1 scenario.** Someone building the emulator variant follows the pointer,
finds nothing, and invents their own `CFLAGS` invocation.

**Cannot occur.** `probe/Makefile:7-38` is now 32 lines on exactly this: both
invocations spelled out, why it is a build flag and not a config key, and the
two Makefile-side mechanisms named. `README.md:69-88` adds an "emulator-only
build" section with the three-mechanism table. The pointers in
`main.c:266-269` and `nv2a_window.h:122` both say "see the Makefile" and
the Makefile now answers. `grep -rn PROBE_ALLOW_HAZARDS` returns hits in the
Makefile, the README, `nv2a_window.h`, `gen_window.py` and `run_tests.sh` — no
longer three hits all in one uncompiled file.

## M2 — none of the new probe C is compiled or mutated

**Pass-1 scenario.** The diff adds a safety-relevant refusal and a 20-line
parser to a tool whose stated standard is a mutant per property, and supplies
neither: delete the commit-point refusal and the suite stays green;
`load_config()` has no test; the `PROBE_ALLOW_HAZARDS` branches are never
syntax-checked.

**Cannot occur.** Both decisions moved out of `main.c` into headers the suite
builds:

- the parser is `probe/probe_cfg.h`, exercised by the new `test_probe_cfg.c`
  with **8 mutants**, all killed;
- the write predicate is `nv2a_offset_write_allowed()` in the generated
  `nv2a_window.h:127-133`, and `cmd_write` (`main.c:273`) and
  `mmio_commit_write` (`main.c:203`) now both call it, so pass 1's "the existing mutant cannot
  cover it, because it mutates the header and not the caller" no longer
  applies — the header *is* the caller's decision;
- `test_window.c` compiles in **both** configurations (`run_tests.sh:33-34`),
  and the two hazard-build mutants (`:77-80`) pin the relaxation to exactly one
  thing: "the hazard build still honours the window" and "the hazard build
  really does allow hazards" are both killed, so the variant can neither
  over-relax into unmodelled space nor silently stop relaxing.

`gen_window.py --check` passes, so the committed header is the generated one
and the mutants are mutating shipped code. Full run on this head: 3 baselines
green, 21 mutants, 21 killed, exit 0.

**Residual, and why it is not a finding.** `main.c` is still compiled by
nothing on the host, so the *call sites* — `if (hz && !nv2a_offset_write_allowed(off))`
and the `mmio_commit_write` guard — are not covered by a mutant; deleting a
call still goes unnoticed by `run_tests.sh`. That is the irreducible part
(`main.c` needs nxdk and an Xbox), pass 1 scoped it as pre-existing context
rather than part of the finding, and the remediation answers it the only way
available: `run_tests.sh:9-15` and `NOTES.md:42-43` both now say that a
decision added to `main.c` must move into a header first, or it is untested by
construction. I confirmed the calls by compiling both variants, which is a
one-off, not a gate.

## M3 — the supervisor test cannot fail on the claim it was added to retract

**Pass-1 scenario.** A later edit restores "No ICMP means the processor is
gone" while keeping the AutoTurnOff sentence; both existing checks pass and the
false claim is back.

**Cannot occur.** `test_supervisor.py:109-110` adds the absence check, and
`run_tests.sh:129-130` adds a mutant that performs pass 1's scenario verbatim —
it restores the retracted wording *and keeps* the power-button and AutoTurnOff
sentences. I applied it by hand to confirm which row kills it:

```
ok   supervisor stopped
ok   and says plainly that it needs hands
ok   and does not assert a wedge -- an idle console powers itself off
FAIL and never claims the processor is gone -- ICMP cannot show that
```

Exactly the scenario's shape: the two pre-existing rows pass with the false
claim restored, and the new row is the only thing standing between the suite
and a green run on a retracted diagnosis. `README.md:253-258` carried the same
claim three sections from the code and is corrected in place — which is the
half of this a "fix the test" remediation usually misses.

## M4 — the numbers are unreproducible and the instrument is not identified

**Pass-1 scenario.** The next lane widens the measurement past two suites, gets
a different register total, and cannot tell a real change from a different
instrument, because the instrument is a paragraph.

**Cannot occur.** The instrument is
`docs/testing/patches/nxdk_pgraph_tests-6743b6ab-per-test-pgraph-diff.patch`,
committed and tracked — `.gitignore`'s blanket `*.patch` is negated for
`docs/testing/patches/`, and `git check-ignore` confirms the file is not
ignored. The document names the tests-tree base commit, and it is real and the
patch fits it:

- `6743b6ab164e760e8b995e969c762d829af5d52e` exists in the tests tree,
  "Adds more fog tests." (the document's `17:53 -0700` is its commit date; its
  author date is `16:37`);
- extracted that tree read-only and `git apply --check -p1` → **applies
  cleanly**;
- applied, the claimed markers are where the document says: `PGRAPH-DIFF`
  emitted per test (`src/pgraph_diff_token.cpp:95`) and one
  `SUITE-RESIDUAL <suite>` per suite from `Deinitialize`
  (`src/tests/test_suite.cpp:397`).

The document is also honest about what the patch is *not* evidence of
(`:34-40`): the working files postdate the build the run used, so it is what to
re-measure from and not a warrant for the numbers, and `:42-49` records
outright that the raw dumps and the host attribution script are gone and that a
rerun should commit both. That is the correct disposition — pass 1 asked for
the sha and the parser as the minimum and named committing the dumps as the
stronger answer; the dumps do not exist to commit, and saying so is better than
a reconstruction.

## M5 — the PR body is not the lane template

**Pass-1 scenario.** Four paths are invisible to the board's `Files:` scan, the
board briefs a second lane onto `main.c`, and the collision surfaces at fold
time.

**Cannot occur.** The body now carries `Lane:`, `Base:`, `Files:`,
`Prediction:`, `Needs device:` and `Needs NDK:`. `Files:` parsed and diffed
against `git diff --name-only origin/master...HEAD`: **20 paths on the line, 20
in the diff, set-identical** — nothing claimed that is not edited, nothing
edited that is not claimed. `docs/lanes/nv2a-hw-probe/NOTES.md` exists, is
per-lane rather than branch-root, and carries the three things a next lane
would otherwise re-derive (the dumps are gone; 54 = 52 + 2; the probe suite is
manual).

*(This pass-2 file is the 21st path and is not on that line. It is the
auditor's artifact on the lane branch, as `roles/lane.md` intends; it needs no
claim and the lane should not add it.)*

## LOW — all six closed

Not required, checked anyway because each one is now a mutant or a line I could
read:

| | verified |
|---|---|
| L1 `dhcp=true` silently meant static | `probe_cfg__bool` takes `1/0`, `true/false`, `yes/no`, `on/off`, case-insensitively; mutant "a boolean is not just its first character" killed |
| L2 net-up line printed a static IP in DHCP mode | `main.c:414-417` branches on `g_cfg.dhcp` and prints `dhcp (leased)` |
| L3 `port` unvalidated | `probe_cfg__port` is digits-only and 1..65535; mutant "port is validated as a port" (restoring `atoi`) killed |
| L4 `load_config()` silent about everything | over-long values refused rather than truncated, over-long **lines** drained and refused whole rather than re-parsed as a second record, unknown keys counted, and the effective config printed; four mutants, all killed |
| L5 `shaders.c` citation named the wrong mechanism | the document now says "a dirty check, not a hash" |
| L6 52 tests vs 54 blocks | reconciled as 52 + one `SUITE-RESIDUAL` per suite, and I found that block in the patch itself |

`debugPrint` is `vsnprintf` into `char buffer[512]` (`nxdk/lib/hal/debug.c:163-170`);
the new effective-config line is ~190 bytes worst case, so L4's fix does not
buy an overflow. `probe_cfg__str` rejects at `strlen(val) >= cap` before its
`strcpy`, and `probe_cfg__bool`'s `low[8]` is guarded by `n >= sizeof(low)`.

---

## One new LOW, recorded rather than raised

**`run_tests.sh` mutates the working tree in place.** `pymutate` and the new
`pydrivermutate` `sed -i` the real `host/supervisor.py` and
`host/probe_driver.py`, with the backup inside the `mktemp -d` that the `EXIT`
trap removes. Interrupt the run inside that section and the trap deletes the
backup while the mutated file stays — including
`self.hazards_allowed = False`, which is H1's third mechanism switched off.

Why it is a LOW and not a finding against this PR: the pattern is pre-existing
(`origin/master:tools/nv2a_probe/run_tests.sh:61-74` does exactly this to
`supervisor.py`), the diff only extends it to a second file, the damage is
visible in `git status`, and reaching harm needs the two *other* H1 mechanisms
to have been bypassed as well. Worth a line in a future probe lane: mutate a
copy on a `-I` path, as the C mutants already do (`:44-45`).

## Standing residual, unchanged by this PR

No `.sh` or workflow file outside `tools/nv2a_probe/` references the probe, so
the green CI rollup on this PR says nothing about `run_tests.sh` and the 21
mutants above — they were run by hand, here, on `569fd86363`. Pass 1 recorded
this as pre-existing context and the PR body states it plainly. It is the
reason this pass ran the suite rather than citing the checks.

---

## Verdict

**Clean → `fold-ready`.**

Seven scenarios, seven discharged; six of them by running the mechanism rather
than reading it. The remediation is the shape pass 1 asked for and in two
places went past it: H1 was fixed at all three gaps rather than the one that
would have closed the scenario, and M3's retracted claim was chased into
`README.md` where nothing had flagged it.

`preflight.sh` passes, CI is SUCCESS on `569fd86363`, the branch is 0 behind
`origin/master`, `Files:` matches the diff, and the lane has notes.
