# Audit pass 1 — PR #201, `claude/nv2a-hw-probe`

*nv2a: per-test PGRAPH diff against the console, and three probe fixes*

- **Auditor:** `job.cloud`, 2026-09-21, pass 1 (diff read)
- **Diff read:** `git diff origin/master...HEAD`, 4 files, +179/−8
- **Head at audit:** `d5a3f2071c`, CI `build`/`build` both SUCCESS
- **Branch position:** 4 ahead / 23 behind `origin/master`. `hw/xbox/nv2a/` is
  byte-identical to master on this branch, so the source claims checked below
  were checked against a current tree.
- **Verdict:** 1 HIGH, 5 MEDIUM, 6 LOW → `needs-remediation`

---

## What the diff is

Two unrelated halves.

**A 113-line document** asserting the first emulator-vs-console PGRAPH diff at
register granularity. No data, no parser, no instrument: the numbers are the
whole artifact.

**Three changes to `tools/nv2a_probe`** — a `D:\nv2a_probe.cfg` reader, a
`PROBE_ALLOW_HAZARDS` build flag that removes the probe's hazard refusal, and a
reworded supervisor stop message plus two test assertions.

### The document's checkable claims all hold

The report makes six claims about this tree that a reader can check, and every
one of them is right. I checked them rather than the prose around them:

| claim in the document | checked |
|---|---|
| `NV_PGRAPH_SURFACE` is touched only through `READ_3D`/`WRITE_3D`/`MODULO_3D`, all at bit 20 and above | `pgraph.c:2275`, `:2281`, `:2287`, `:934` are the only `PG_SET_MASK` writers; the method fast path reaches it only via `mask_lut[1..3]` (`pgraph.c:295-297`), which are exactly those three masks. `nv2a_regs.h:265-268` declares nothing else. Bit 0 is unnamed and unwritten ✔ |
| `SET_TEXTURE_FORMAT` makes nine `PG_SET_MASK` calls, and bits 0, 4, 5 are written by nothing | `pgraph.c:4082-4090`, nine calls, covering exactly bits 1, 2, 3, 6–7, 8–14, 16–19, 20–23, 24–27, 28–31 ✔ |
| `NV_PGRAPH_TEXFMT0` bits 4–5 are undeclared | `nv2a_regs.h:606-617` — `BORDER_SOURCE` is bit 3, `DIMENSIONALITY` is 0xC0 (bits 6–7). Bits 0, 4, 5 have no name ✔ |
| `CSV1_A_T0_ENABLE`/`_T0_MODE`/`_T0_TEXTURE` are declared and referenced nowhere else in `hw/xbox/nv2a/` | `nv2a_regs.h:335-337` are the only three hits in the whole subtree ✔ |
| `CSV1_A` is written only by `SET_TEXGEN_S/T/R/Q` | `pgraph.c:3272`, `:3282`, `:3292`, `:3302`, through the `T0_S`/`T0_T`/`T0_R`/`T0_Q` masks. Every other hit (`vsh.c:51-57`, `vk/renderer.c:1270-1275`, `shaders.c:99`, `pgraph.c:113`) reads ✔ |
| `ZCLIPMAX` 0x4B7FFFFF → 0x477FFF00 is 2²⁴−1 → 65535.0 | decodes to 16777215.0 and 65535.0 ✔ |

The `TEXOFFSET0`/`TEXPALETTE0` paragraph is also sound, and it is the one I
expected to break: an xor of 0x0002F000 does not generally imply a difference
of 0x21000. Here it does — `x − y = (x^y) − 2·(y & ~x)` gives `y & ~x = 0x7000`,
which is a subset of 0x2F000, so the two statements are consistent. Recording a
non-finding because it has the shape of one is the right instinct and it is
correctly reasoned.

The report's self-limits are honest and I am not going to second-guess them:
"a register that moved on one side cannot be judged", the `ZCLIPMAX` row parked
until there is an absolute read, and the scope section refusing to generalise
past 54 diff blocks. That discipline is why the findings below are about the
record and the probe, not about the analysis.

### What that leaves

Every finding is on the other side of the ledger: the numbers cannot be
reproduced from this repository (M4), and the probe changes hand the console a
loaded gun with no safety catch anyone downstream can see (H1).

---

## HIGH

### H1 — the hazard-allowed build lands at the same path under the same name, and nothing downstream can tell it from the safe one

`tools/nv2a_probe/probe/main.c:253`, `:197`, `:338`

The new comment states the guarantee this design is supposed to buy:

> Deliberately a BUILD flag and not a config key. A config key would mean the
> console binary could be talked into a hazardous write by editing a file next
> to it […] A separate build cannot: the refusal is either compiled in or the
> binary is not the one on the console.

The second half is not true as built. "The binary is not the one on the
console" requires that something be able to tell the two binaries apart. Three
things would have to hold, and none does:

**1. There is no separate build product.** `README.md:63` documents the build
as `make -C tools/nv2a_probe/probe -j4  # -> probe/bin/default.xbe`. The
Makefile has one `XBE_TITLE = nv2a_probe` and one output path. Adding
`-DPROBE_ALLOW_HAZARDS` to `CFLAGS` overwrites `probe/bin/default.xbe` — the
same path the FTP deploy and `SITE EXEC` steps (`README.md:187`, `:200-201`)
read — with the hazard-allowed image. Nothing about the file's name, location
or size says which one it is.

**2. Removing the flag does not necessarily rebuild.** nxdk's Makefile tracks
source files, not `CFLAGS`. Build the emulator variant, then re-run `make`
without `clean`: `main.o` is newer than `main.c` and is not rebuilt. The
hazard-allowed object survives into what the operator believes is the safe XBE.

**3. The HELLO announcement is read by nobody.** `probe_driver.py:139` is the
only consumer, and it is `if not self.hello.startswith("HELLO")`. The
`-HAZARDS-ALLOWED-EMULATOR-ONLY` suffix reaches a log line and a human's eyes
and no check anywhere.

**Failure scenario.** An operator builds the emulator variant to exercise
`NV_PMC_ENABLE` under xemu, then returns to the console the same day and FTPs
`probe/bin/default.xbe` across. `probe_driver.py` connects, accepts the HELLO,
and a hand-issued `W 000FC0 00000000` — or any ad-hoc write through the driver
— passes `nv2a_offset_writable()`, finds both hazard refusals compiled out
(`main.c:253` in `cmd_write`, `main.c:197` in `mmio_commit_write`), is
journalled, and stores. That is precisely the write this file's own comment
records as having "killed the console outright" on 2026-09-20.

**The limit of this finding, stated.** `sweep_writable_bits.py:256` still
excludes hazards host-side, so a *sweep* through that tool remains guarded on
either binary. What is lost is the probe-side refusal on every path that is not
a sweep — and `probe_driver.py` itself carries no hazard list, which is the path
an operator uses by hand. The README calls the probe-side refusal structural
("refused *in the* probe", `:141`) on the stated grounds that "the host is the
thing most likely to carry a bug" (`main.c:268`). This change makes that
property a function of which `CFLAGS` were in the shell, invisibly.

**What would fix it**, any one of which discharges the scenario:

- give the variant its own `XBE_TITLE`/output path in the Makefile, so the
  hazard-allowed image cannot occupy `default.xbe`; **and/or**
- have `probe_driver.py` parse the HELLO and refuse to proceed when the suffix
  is present unless the caller passed an explicit opt-in flag — the check the
  HELLO change was made for, which currently has no reader.

The `mmio_commit_write` addition itself (`main.c:197-199`) is a good change in
the safe build: defence in depth at the only store in the program. It is only
the `#ifdef` half that is the problem.

---

## MEDIUM

### M1 — `main.c:254` says "See the Makefile comment"; there is no Makefile comment, and no way to build the variant

`tools/nv2a_probe/probe/main.c:254`

The comment marked **EMULATOR-ONLY BUILD** points the reader at the Makefile
for the procedure. `probe/Makefile` is 12 lines and contains no mention of
`PROBE_ALLOW_HAZARDS`, no target, no guard, and no note about keeping the
variant off the console. `grep -rn PROBE_ALLOW_HAZARDS` over the repository
returns three hits, all in `main.c`.

**Scenario:** someone building the emulator variant follows the pointer, finds
nothing, and invents their own invocation — which is the ad-hoc `CFLAGS` edit
that produces H1's indistinguishable artifact. The documented rule that would
keep it off the console does not exist to be followed.

### M2 — none of the new probe C is compiled or mutated by the suite that exists to mutate it

`tools/nv2a_probe/run_tests.sh`

`run_tests.sh` opens with "Passing tests prove nothing on their own: a check
that cannot fail is decoration. […] If a mutant survives, the corresponding
check is not testing what it claims and the suite fails." It builds
`test_window.c` against `nv2a_window.h` and mutates that header and
`supervisor.py`. **`main.c` is compiled by nothing on this side of the wire, in
either configuration.** Consequences specific to this diff:

- the new commit-point hazard refusal (`main.c:197-199`) has no mutant. Delete
  those three lines and the suite stays green — and the existing mutant
  `"hazard list is consulted"` cannot cover it, because it mutates
  `nv2a_window.h`, not the caller;
- `load_config()` has no test at all, and it is 20 lines of hand-rolled parsing
  that decide which host the console dials;
- the `PROBE_ALLOW_HAZARDS` branches are never so much as syntax-checked.

Context, not part of the finding: no `.sh` or workflow file anywhere in the
repository references `nv2a_probe`, so `run_tests.sh` is manual-only and CI's
green rollup on this PR says nothing about any of it. That is pre-existing. The
finding is that the diff adds a safety-relevant refusal and a parser to a tool
whose own stated standard is a mutant per property, and supplies neither.

### M3 — the supervisor test cannot fail on the claim it was added to retract

`tools/nv2a_probe/host/test_supervisor.py:99-102`

The commit exists to stop the supervisor asserting that an unreachable console
proves the processor is gone. The two checks are `"power button" in reason` and
`"AutoTurnOff" in reason`. Neither asserts the *absence* of the retracted claim.

**Scenario:** a later edit restores "No ICMP means the processor is gone" while
keeping the AutoTurnOff sentence. Both checks pass, the suite is green, and the
false claim is back. `run_tests.sh`'s pymutate for this region
(`elif False:`) only kills the "is it reported at all" check, so the mutation
suite does not cover the wording either.

Fix: add `check("processor is gone" not in (sup.stopped_reason or ""), ...)`,
and add a pymutate that restores the old wording so the new check is itself
proven to fire — otherwise it joins the decorations.

### M4 — every number in the document is unreproducible from this repository, and the instrument is not identified

`docs/testing/pgraph-per-test-emulator-vs-hardware.md:24-43`

The document is a measurement, and the measurement's entire value is its
numbers: 24 / 336 / 308, 54 diff blocks, 191 comparable observations of which
92 agreed, 53/53, 40/40, 764 mirror observations. None can be checked or
repeated from this tree, because:

- the instrument changes are "in the tests tree, not in this repo" — described
  in prose, with **no commit sha, branch, or patch** for the
  `nxdk_pgraph_tests` checkout they were made against;
- the host-side parser that attributes `PGRAPH-DIFF <suite>::<test>` lines to
  tests, and the host-side blacklist the document says is "applied on the host
  instead", are not in the PR;
- no raw dump from either side is committed.

This repository already has the convention: `nv2a_index.json` carries
`provenance.tests_commit`, written by `nv2a_index.py:525` and compared on
regeneration at `:566`, precisely so a result cannot be silently re-derived
against a different tests tree.

**Scenario:** the Scope section invites the obvious follow-up — widening past
two suites "costs one run per side and no new tooling" (`:103-108`). The next
lane runs it, gets a different register total, and has no way to tell a real
change from a different instrument, because the instrument is a paragraph.

Minimum fix: record the `nxdk_pgraph_tests` commit sha the runs were built
from, and commit the host parser (or name where it lives). Committing the raw
per-test dumps would make the whole table checkable and is the stronger answer.

### M5 — the PR body is not the lane template: `Files:` is absent, so four paths are claimed by nothing

PR #201 body

`docs/testing/jobs/roles/lane.md:11-26` requires `Lane:`, `Base:`, `Files:`,
`Prediction:`, `Needs device:`. The body has none of them, and states the
reason for `Files:` plainly: "The board reads `Files:` from every open PR to
keep two lanes off one file. A path you edit that is not on that line is a
collision nothing can see."

All four paths in this diff are invisible to that scan, including
`tools/nv2a_probe/probe/main.c` and `tools/nv2a_probe/host/supervisor.py`,
which are live subjects of ongoing probe work.

**Scenario:** the board briefs a second lane onto `main.c` — which it has no
reason not to do — and the two edits collide at fold time with no earlier
signal.

Also missing, same role file, item 3: there is no `docs/lanes/<lane>/NOTES.md`
anywhere on this branch for this work (`git ls-tree` finds no probe or nv2a
lane notes). The PR body is the only record, and it does not survive the fold.

**Note for remediation:** `gh pr edit --body-file` fails on this host — the
Projects-classic GraphQL error breaks every field, not just labels, and it
exits non-zero having applied nothing. PATCH the body through
`gh api -X PATCH repos/jreinach-alt/hakuX/pulls/201 -f body=@file` and read the
value back.

---

## LOW

- **L1 — `dhcp=true` silently means static.** `main.c:101`,
  `g_use_dhcp = (eq[1] == '1')`, tests a single character. Anything but a
  literal leading `1` is false. The config format is documented nowhere:
  `README.md` has no mention of `nv2a_probe.cfg`, so the only description of
  the file is the comment inside the function that parses it. A plausible
  `dhcp=true` leaves the probe in static mode, dialling an address that does
  not exist under slirp, with no diagnostic.
- **L2 — the "net up" line prints the wrong address in DHCP mode.**
  `main.c:417` prints `g_static_ip` unconditionally. In DHCP mode that value
  was never used; the operator reads a static IP off the screen for a console
  that has a leased one.
- **L3 — `port` is unvalidated.** `main.c:100`, `atoi`. `port=` or `port=http`
  yields 0, and the probe then dials port 0 for the full `NO_HOST_MS` (120 s)
  before the escape hatch returns it to the dashboard, with nothing on screen
  naming the cause.
- **L4 — `load_config()` is silent about everything.** A 128-byte `fgets`
  buffer splits a longer line and parses its tail as a fresh `key=value`;
  leading whitespace before a key defeats `strcmp`; an unrecognised key is
  dropped. None of these print. A cfg that is present but wholly unparsed is
  indistinguishable on screen from no cfg at all. One `debugPrint` of the
  effective host/port/mode after the call would close all four.
- **L5 — the `shaders.c` citation names the wrong mechanism.** The document
  says "`shaders.c` hashes `CSV1_A` into the shader cache key". `shaders.c:99`
  is the register list of `pgraph_glsl_check_shader_state_dirty()`, a dirty
  check, not a hash. The conclusion drawn — that two states differing only in
  `T0_ENABLE` are indistinguishable here because nothing reads that bit into a
  `ShaderState` — is correct, but a reader following the citation lands on a
  function that does something else.
- **L6 — 52 tests, 54 diff blocks, never reconciled.** The two counts appear
  three paragraphs apart with no explanation of the two extra blocks. A reader
  cannot tell whether that is per-suite bracketing or two tests dumping twice,
  and the 53/53 and 40/40 denominators depend on knowing which.

---

## What I checked and did not find

Stated so pass 2 does not re-derive them:

- **No buffer overflow in `load_config()`.** `strncpy(dst, src, sizeof(dst)-1)`
  never writes the final byte, and every destination is a `static` array whose
  tail is zero-filled past its initialiser, so all six remain NUL-terminated
  for any input the 128-byte line buffer can hold.
- **The HELLO line still fits.** With the 30-character suffix the formatted
  string is ~131 bytes, inside `hello[224]` and inside `send_line`'s 254-byte
  limit.
- **The `#ifdef`/`#else`/`#endif` nesting in `cmd_write` is well-formed** in
  both configurations; `out` and `grant` stay in scope and no declaration is
  orphaned. (Nothing compiles the hazard-allowed configuration to confirm this
  mechanically — see M2 — but it reads correctly.)
- **`docs/testing/xbox-console-provenance.md` exists** and the cross-references
  resolve.
- **The supervisor change itself is right.** An idle console reaching
  UnleashX's `AutoTurnOff` and a wedged console are genuinely identical over
  ICMP, and the old message asserted a diagnosis the evidence could not carry.
  The finding at M3 is about the test, not the message.

---

## Verdict

**1 HIGH, 5 MEDIUM → `needs-remediation`.**

H1 is the one that matters: the change is a real capability the emulator work
needs, and the reason to fix rather than drop it is that the guarantee its own
comment claims is one Makefile target and one `startswith` away from being
true.
