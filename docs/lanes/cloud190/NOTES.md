# lane.cloud190 -- #190: PMC reads 1 at 0x160 and across 0x204-0x2FC

Status: work done, attempt 1. One hunk in `pmc_read` (+41 lines, no deletions),
the existing PMC selftest extended to cover it, a committed mutant suite, and
two documentation rows corrected. PR #211. `Prediction: none` and no device
time -- see "Why there is no arm" below.

## The brief, and what actually changed

`hw/xbox/nv2a/pmc.c:pmc_read` had no case for `0x160` or for anything in
`0x204-0x2FC`; all 64 offsets fell to `default: r = 0`. Two independent
read-only sweeps of real NV2A silicon, with a reboot between them and
1,024/1,024 PMC dwords reproducible, read `0x00000001` at every one of them.
Read side only.

| file | what |
|---|---|
| `hw/xbox/nv2a/pmc.c` | the one behavioural change: `case 0x160:` / `case 0x204 ... 0x2FC:` returning `0x00000001` for dword-aligned offsets |
| `docs/testing/pmc_enable_selftest.c` | #190's checks added; 8 checks -> 16 |
| `docs/testing/pmc_enable_selftest.sh` | write-side guard widened to #190's region, and #188 audit pass 2's named hole (P2) closed |
| `docs/testing/nv2a-hardware-gap-list.md` | the #190 row rewritten in place, "read landed, what the region IS still untested" |
| `docs/lanes/pmc188/mutants.py` | three expectations moved by this change; see "What I had to touch in another lane's file" |
| `docs/lanes/cloud190/mutants.py` | 24 mutants, new |

`nv2a_regs.h` is **not** in the diff and no macro was invented. The header
declares nothing at `0x160` or anywhere in `0x204-0x2FC`, and a name asserts a
meaning this measurement does not carry. The raw offsets are what was read.

`pmc_write` is byte-for-byte untouched -- `sha256` of
`sed -n '/^void pmc_write/,$p'` is `20150c04ab69...` at the base commit and
identical here, the same digest PR #198 recorded. The `pmc.c` diff is `+41, -0`.

## The three things this does NOT claim

**1. Not 63 registers.** Whether `0x204-0x2FC` is 63 live registers that
happen to hold 1, one register aliased across the range, or a fixed
unimplemented-read pattern is UNTESTED, and all three are indistinguishable
from reads alone. Separating them needs a write into the range, four bytes
from the register whose write halted the physical console (#188). The brief
forbade attempting it and that is the right call. Nothing in the diff, the
test or the gap-list row picks one of the three -- and it does not need to,
because all three agree about what a read returns, which is the whole of what
landed.

**2. Not state-independence.** Both sweeps were the console idle out of the
dashboard, engines quiescent. 1,024/1,024 across a reboot bounds
REPEATABILITY IN ONE STATE. Nobody has read these offsets on a machine that is
rendering. This is exactly the caveat #188 carries for `NV_PMC_ENABLE`, and
`nv2a-probe-pmc-findings.md` says it of its own numbers; it applies unchanged
here and is recorded beside the constant.

**3. Not unaligned offsets.** `case 0x204 ... 0x2FC:` covers every byte
address in the range, so `pmc_read` guards on `(addr & 3) == 0`. The probe
read dword-aligned offsets and nothing else, and byte 1 of a register holding
`0x00000001` is 0 under all three readings above -- so answering 1 at `0x205`
would be a value nobody measured and that no model predicts. Unaligned offsets
keep the 0 they returned before. The aligned sub-dword case is not a guess: a
1-byte read at `0x204` gets `0x01`, the correct low byte, and the test asserts
both halves (`0x204/1 -> 1`, `0x205/1 -> 0`).

## One arithmetic cross-check, and its limit

`nv2a-probe-pmc-findings.md` reports 957 of PMC's 1,024 dwords reading 0, so
67 are non-zero. This lane's 64, plus `BOOT_0` and `NV_PMC_ENABLE`, is 66. So
exactly **one non-zero PMC dword is unaccounted for** and the findings do not
name it. `0x004`/`BOOT_1` is the obvious candidate -- it is #189's register and
the survey discusses it at length -- but **no read value for it is recorded
anywhere in this tree**, so that is arithmetic, not a measurement, and it is
written that way in `pmc.c`. Whoever takes #189 can settle it in one line from
the raw sweep if that data still exists.

The useful half of the check is what it *does* establish: 63 + 1 + 1 + 1 = 66
of 67 leaves no room for a second unmodelled region hiding in PMC.

## The falsifier, and why it went into #188's file

`docs/testing/pmc_enable_selftest.sh` + `.c`, extended rather than forked.
Both issues are claims about what the same `switch` returns, measured by the
same survey, and #190's region starts four bytes after #188's register. A
second script extracting the same function drifts from the first and the two
then disagree about a shared switch with nobody watching. The file keeps its
`pmc_enable` name so pmc188's committed mutant suite still drives it.

Red then green on this tree, and the red is the informative one:

```
before -- base pmc.c, new test:
  FAIL 0x160 (#190, unnamed)        addr=0x160 got=0x00000000 want=0x00000001
  FAIL 0x204-0x2FC (#190)           0x204-0x2fc: 63 of 63 dwords wrong (first 0x204, last 0x2fc), want 0x00000001
  FAIL 0x204-0x2FC (#190)           addr=0x204 got=0x00000000 want=0x00000001    <- the loud re-run of the first offender
  FAIL aligned byte in the region   addr=0x204 got=0x00000000 want=0x00000001
  16 checks, 3 failures     exit 1

after:
  ok   0x160 (#190, unnamed)        addr=0x160/4 -> 0x00000001
  ok   0x204-0x2FC (#190)           0x204-0x2fc, 63 dwords -> 0x00000001
  ok   aligned byte in the region   addr=0x204/1 -> 0x00000001
  16 checks, 0 failures     exit 0
```

That red run is mutant `PRE` in the suite below, pinned to base sha
`3fe18366cd` rather than to `origin/master` -- master will contain this fix as
soon as it folds, and a row defined against a moving ref would quietly invert.
Three assertions red, thirteen checks green in both runs, so it is a
disagreement about three claims and not a build failure. Note which stayed
green: `NV_PMC_ENABLE`, both `INTR` pairs, both 0x160 edges, both region
edges, `unmodelled 0x000c` and the unaligned byte -- everything this change is
not about.

The region is ONE check over 63 offsets, not 63 checks: 63 `ok` lines would
bury the seven that carry information. The failure path prints the count and
the first and last offending offsets, then re-runs the first offender loudly,
so a partial region is diagnosable from the output without a rerun. Mutant N3
(range one dword short) prints `1 of 63 dwords wrong (first 0x2fc, last
0x2fc)`; N6b prints `32 of 63`.

### The guards were checked against mutants, not assumed

`python3 docs/lanes/cloud190/mutants.py` -> **24 mutants, 0 unexpected**.
Every row names the LINE the run must go red on, because an exit code is a
coarse discriminator. Four rows must PASS and two must pass *uncomfortably*.

| mutant | expected | went red on |
|---|---|---|
| N0 unmutated | exit 0 | -- the row that makes the rest mean anything |
| **PRE** base `pmc.c`, new test | exit 1 | `FAIL 0x160 (#190, unnamed)` |
| N1 region case deleted | exit 1 | `FAIL 0x160 (#190, unnamed)` |
| N2 region reads 0 | exit 1 | `63 of 63 dwords wrong` |
| N3 range stops at 0x2F8 | exit 1 | `1 of 63 dwords wrong (first 0x2fc, last 0x2fc)` |
| N4 range runs to 0x300 | exit 1 | `FAIL above the region` |
| N4b range widened down past 0x200 | exit 1 | `duplicate (or overlapping) case value` -- **gcc**, not us |
| N4c 0x1FC given the value | exit 1 | `FAIL below the region` |
| N5 / N5b 0x160 dropped / off by one | exit 1 | `FAIL 0x160 (#190, unnamed)` |
| N6 alignment guard dropped | exit 1 | `FAIL unaligned byte, not ours` |
| N6b guard widened to `& 7` | exit 1 | `32 of 63 dwords wrong` |
| N7 constant leaks into `default` | exit 1 | `FAIL unmodelled 0x000c` |
| N8 constant lands on 0x200's arm | exit 1 | `FAIL NV_PMC_ENABLE` |
| N9-N12 `pmc_write` gains `0x204 ... 0x2FC` / `0x160` / `352` / `0x2FC` | exit 1 | `REFUSED: pmc_write has a case in #190's read-1 region` |
| N13 `pmc_write` gains `case 0x1FC ... 0x2FC:` | exit 1 | same REFUSED -- #188 audit pass 2's hole P2, now closed |
| **K1** `case 0x100 ... 0x400:` in `pmc_write` | exit **0** | **a known hole, recorded as a passing row** |
| **K2** `case 516:` in `pmc_write` | exit **0** | **the same, decimal** |
| P1 a `pmc_write` COMMENT naming 0x204 and #190 | exit 0 | must NOT fire -- anchored on code, not prose |
| P2 region implemented in `default` with an `if` | exit 0 | must NOT fire -- the test is behavioural, not textual |
| P3 an unrelated later function holds `0x00000001` | exit 0 | must NOT fire |

**N4b is the mechanical half of "keep #188 and #190 disjoint", and it is
stronger than anything this lane wrote.** A range extended down far enough to
swallow `0x200` overlaps `case NV_PMC_ENABLE:` and *gcc refuses the
translation unit*. It is recorded as a compile refusal rather than dressed up
as a check of ours. N4c covers the lower edge with an assertion, at an offset
that does not collide.

**K1 and K2 are the guard's reach, as a measurement.** #188's audit pass 2
asked that it "be written down somewhere other than the regex". A sentence
rots; a row that must come back green does not. Grep cannot evaluate an
interval, so a range with both endpoints outside the region (`0x100 ... 0x400`)
and the decimal spellings 516-764 are not caught. If the write lane parses
case labels as numbers, these two rows go red and should be deleted -- that is
the intended way for them to die.

### "Newly caught" is measured, and `--at` alone would have lied

`python3 docs/lanes/cloud190/mutants.py --newly-caught` -> all four write-side
rows come back **`8 checks, 0 failures`, exit 0**: the pre-existing script
certified a tree whose `pmc_write` had a case for `0x204 ... 0x2FC`, for
`0x160`, for `352` and for `0x2FC`.

That needed its own mode, and the reason is the trap one level down from
"an exit code is coarse". Running `--at 3fe18366cd` the ordinary way pairs the
OLD script with THIS `pmc.c`, where the old `unmodelled 0x204 == 0` assertion
fails -- so N9-N12 come back exit 1 and look caught, for a reason that has
nothing to do with the write side. `--newly-caught` pairs the old script with
the OLD `pmc.c`, leaving the write guard as the only variable. Of the 18
disagreements a bare `--at` reports, most are the check count moving 8 -> 16;
the genuinely uncaught read-side rows are PRE, N1, N2 and N6b.

## What I had to touch in another lane's file

`docs/lanes/pmc188/mutants.py` is committed, retired, and **broken by this
change** unless edited -- a committed suite that fails after a fold is a
broken gate, not a historical record. Three of its rows moved:

- M0, L1, L2 expected the literal `8 checks, 0 failures`. Now 16. The exact
  count is deliberately kept exact rather than relaxed to `0 failures`: it is
  what catches a later edit silently *deleting* checks. A lane adding checks
  updates it, as I did.
- **M4 changed meaning and is the interesting one.** It widens #188's arm to
  `NV_PMC_ENABLE + 4` and used to go red on `FAIL unmodelled 0x204` -- the
  line #190 was told to change. That assertion no longer exists, and the
  mutant now fails to *compile*, because `0x204` is inside this lane's range.
  So the guard that catches M4 is no longer that script; it is gcc. Repointing
  the expected text silently would have left a row that looks like it still
  tests what it tested. It says what happened instead, and #190's N3/N4 cover
  the widening question with mutants that still reach the assertions.

`docs/lanes/pmc188/mutants.py` and the two `docs/testing/` files are **not on
this lane's territory row**, which lists `hw/xbox/nv2a/pmc.c` alone. They were
released to `[free]` when `lane.pmc188` retired (its row says so), no open PR
touches them, and the PR body's `Files:` names all six paths so the board can
see the claim. I did not edit `territory.toml` -- that is the board's file.

## Why there is no arm and no prediction

`Prediction: none`. There is no golden that could see this. A PMC register
read never reaches a framebuffer, so an A/B on captures returns "no change"
and that verdict would be vacuous rather than informative -- the same
reasoning PR #198 recorded for #188, and #190 is filed low severity precisely
because an undocumented-register read is an unusual guest access pattern. No
device time was requested.

Nor could a device arm have seen it even in principle: the change is inside
`pmc_read`, which no capture path observes, and the one behavioural
consequence is what a *guest* reads if it asks -- and whether any title asks is
unmeasured. "Unmeasured" is not "nothing differs": the live behavioural change
is that 64 offsets now answer 1 instead of 0 to any guest read, at all times.

## The red `check` is the trunk's, and folding this re-arms it on master

PR #211's `check` (workflow **NV2A index**) is FAILURE, on both of the first
two heads, and it belongs to no lane:

| check | result |
|---|---|
| `git rev-parse origin/master:docs/testing/nv2a_index.json HEAD:...` | `953215679f` **both sides** -- the index blob here IS master's |
| files in `git diff --name-only origin/master...HEAD` that the index reads | none |
| the failure text | `1 suite(s) changed content ...: Texture render target. Ordinary staleness; regenerate.` |
| `.github/workflows/nv2a-index.yml:47` | `git clone --depth 1 https://github.com/abaire/nxdk_pgraph_tests` -- **no ref** |
| last green run on that workflow | master `01538395b7`, 15:53Z the same day |
| the same gate locally | `preflight.sh` -> `nv2a index ok` |

Green here and red in CI is **two trees, not two verdicts**: `preflight.sh`
resolves `nxdk_pgraph_tests` to this host's clone, which is at `6743b6a`
(2026-09-20) -- the commit `93bc128ff0` regenerated the index over. CI clones
upstream's tip at run time, and upstream moved.

**I did not regenerate it, deliberately.** `nv2a_index.json` is not this
lane's file, and the only tests tree I can reach is the stale one, so
regenerating would re-commit today's answer while looking like a fix -- and
an older tests checkout can silently drop a suite while it fixes line numbers,
which is how a stale index becomes a confidently wrong one.

Two things for whoever owns index freshness, recorded here because this lane
is the second to pay for it: the workflow also triggers on `push` to `master`
with `paths: hw/xbox/**`, so **folding any PMC change re-arms the same red on
the trunk**; and the same failure already cost PR #198 two handbacks earlier
the same day. The durable fix is pinning the clone -- ideally deriving the pin
from the index's own `provenance.tests_commit`, so the gate compares the index
against the tree it was built from rather than against whatever upstream did
overnight.

## What the next lane should not repeat

- **Do not attempt a write into `0x204-0x2FC` to find out what the region
  is.** It is four bytes from the register that halted the console, the cost
  of getting that wrong has already been paid once, and #190's own brief
  forbids it. If the question is worth answering it needs the envytools
  cross-reference #188 asks for first, not a probe run.
- **Do not turn the 63 dwords into 63 registers, or into one register, in a
  comment.** The read model is correct under all three readings and says so;
  picking one would be a story the data does not support.
- **Do not fork the selftest.** One instrument covers `pmc_read`'s whole
  table; both mutant suites drive it, and the file name is load-bearing for
  pmc188's.
- **If you change the selftest, run BOTH suites** --
  `docs/lanes/pmc188/mutants.py` and `docs/lanes/cloud190/mutants.py` -- and
  expect the check-count string in three rows of the former to need updating.
- **Nothing in CI runs this selftest.** Same as #188's: `jobs-selftest.yml` is
  scoped to `docs/testing/jobs/**`, and `audio_starve_selftest.sh`,
  `glerr_report_selftest.sh` and this one are all unwired. Stated because a
  gate nobody invokes is not a gate. Wiring all three is its own small piece of
  work; adding a call to another job's tick from here would make every existing
  fixture for that job drive this code.
- **The desktop build is CI's, not this worktree's.** There is no configured
  build tree here and a local desktop build needs a system package this host
  does not have (`AGENTS.md`, "libcurl"). What ran locally:
  `check_android_guards.py` (ok, 3298 files), both mutant suites, and the
  selftest, whose `gcc -Wall -Wextra -Wformat=2 -Werror` compile of the
  extracted `pmc_read` is the only local evidence the hunk compiles. The
  build of record is the PR's.
