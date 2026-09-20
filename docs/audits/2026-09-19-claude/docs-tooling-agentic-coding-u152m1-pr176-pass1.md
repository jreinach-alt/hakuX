# Audit pass 1 — PR #176, `claude/docs-tooling-agentic-coding-u152m1`: X1A7R8G8B8 is 458,042 px and shared between the backends

**Auditor** `job.cloud` (claims no files; audit record only).
**Subject** PR #176, branch `claude/docs-tooling-agentic-coding-u152m1`, tip
**`aab3a66f41`**, merge-base with `origin/master` **`20e4708d50`**.
`MERGEABLE` / `CLEAN`, ready (not draft).
**Date** 2026-09-19 (2026-09-20 UTC). **Records**
`2026-09-19-claude/docs-tooling-agentic-coding-u152m1-pr176-pass1.{md,json}`.

**Filename note.** The brief named
`…-claude/docs-tooling-agentic-coding-u152m1-pass1.md`, but that path is
already **PR #162's** pass-1 record — this branch is reused across PRs, so the
branch-derived name collides. Writing it would have deleted another reviewer's
audit. This record is `…-u152m1-**pr176**-pass1.md`; pass 2 should look for the
`pr176` name, not the bare one.

**1 HIGH. 2 MEDIUM. 4 LOW.**

The diff is 3 files, +507/−5, all under `docs/`: a new 269-line model
(`docs/testing/x1a7_forward_model.py`), a new 38-line selftest fragment
(`selftest.d/76-x1a7-model.sh`), and +200/−5 of `docs/lanes/remote/NOTES.md`.
No `hw/` change, no prediction, no device. `Files:` matches
`git diff --stat 20e4708d50...HEAD` exactly; `NOTES.md` is per-lane, not the
branch root; `Prediction: none: analysis-only` is the right answer for a diff
that cannot move a pixel. CI is **green** on this head — Android `build`,
Desktop `build`, `jobs selftest`, all `SUCCESS` at 03:32Z on `aab3a66f41`.

There is no behavioural change here, so nothing in this diff can regress the
emulator. What it ships instead is an **instrument and a published number**,
and the whole of #60's remaining 458,042 px is meant to be decided by it. That
is what I audited: not "does this run", but "can this number be wrong and still
read as right". It can, once — H1.

## What I checked and found correct, so remediation does not re-derive it

* **Every claim the model rests on is true against master, checked by reading
  the files and not by argument.**
  * `surface_color_format_dst_alpha_is_one()` (`gl/draw.c:110-122`) lists seven
    formats and `X1A7` is not among them, so the `Ad = 1` fold really is
    excluded. ✔
  * `kelvin_surface_color_format_gl_map`'s `_Z` and `_O` rows
    (`gl/constants.h:403`, `:405`) are byte-identical —
    `{4, GL_RGBA8, GL_BGRA, NV2A_GL_UNSIGNED_INT_8_8_8_8_REV, GL_COLOR_ATTACHMENT0}`
    twice. ✔
  * `pgraph_get_clear_color()` (`pgraph.c:4599`) is shared, and both suffixes
    fall through to one `*a = ((clear_color >> 24) & 0x7F) / 127.0f`
    (`:4658-4667`). The strongest hypothesis really is refuted by a shared
    helper. ✔
  * `gl/draw.c:468` computes `pad_stamped` from
    `pgraph_glsl_surface_pad_alpha_mode(...) != PSH_PAD_ALPHA_NONE`, which is
    the expression the note says `psh.c` stages from. ✔
* **R2's prior measurement is quoted accurately, and the "R1 is new" claim is
  exactly right.** `vk/constants.h:616` records
  `sampled alpha = (X << 7) | (stored_alpha >> 1)` over 32,755 invertible px,
  and `:632-635` is verbatim *"the other half is that 7-bit quantisation on the
  way IN"*. The apparent contradiction — that entry refutes *"seven-bit
  bit-replication"* as a readback rule while this PR asserts bit replication —
  is not one: they are different consumers, which is the PR's central point and
  it states it. This is the kind of thing that usually breaks; it holds.
* **The refutation of the lane's own starting hypothesis is arithmetically
  correct.** Storing `(X << 7) | (a >> 1)` and reading by identity, against
  `expand7(a >> 1)`, over `bg ∈ {0x00,0x40,0x80,0xFF} × X ∈ {0,1}`: agrees only
  at `(0x00, X=0)` and `(0xFF, X=1)`. **6 of 8 wrong**, as claimed.
* **The internal arithmetic closes.** 81,920 + 65,536 + 90,112 + 65,536 =
  303,104; 303,104 + 154,938 = **458,042**, the stated GL total. The predicted
  yield and the disclaimed remainder partition the figure exactly.
* **The write transform is lossless, and the selftest proves it rather than
  asserting it** — `r2_a7(expand7(v)) == v` for all 128 values
  (`x1a7_forward_model.py:222`). I re-derived it independently.
* **The gate has real discriminating power.** I built five mutants in a scratch
  tree (never the real path) and re-ran fragment 76 against each: R1 → identity
  (2 checks fail), R2 → drop the pad bit (3 fail), `write_transform` → identity
  (2 fail), `expand7` → truncate (2 fail), and — the one the lane did not
  claim — **the golden table edited to match a wrong model** (`0x2A` → `0x2B`,
  2 fail). All five are caught. The PR claims three; it is five.
* **`x1a7hasnt()` is the right call and the reasoning behind it is verified,
  not reasoned about.** `check()` is
  `check() { local msg=$1; shift; if "$@" >/dev/null 2>&1; …`
  (`selftest.sh:31`) — it runs its arguments as a command, so a leading `!`
  would be a command lookup and stuck-at-`bad`. The helper is a same-shell
  function over an argument, not a `bash -c` negative over an unexported var,
  so it does not repeat that trap either.
* **The fragment is named so it will actually be sourced.**
  `76-x1a7-model.sh` matches `[0-9][0-9]-*.sh`, the one glob
  `selftest.sh:127-134` accepts before `exit 2`. It sorts after the existing
  `76-pr-sweep.sh` without colliding on a path, and it depends on nothing the
  10..60 dispatcher fragments build, so its position is free. Its three helper
  functions and `$X1A7` are all name-prefixed, so it leaks nothing into the
  fragments after it.
* **The unexplained 8,192 px is reported as unexplained.** Five refuted
  hypotheses, a named non-generalisation ("luck, not a property of the fix"),
  and a concrete next step. The note declines to escalate its own finding,
  which is the failure mode this repo keeps paying for.

## HIGH

### H1 — `score()` counts a golden it never read as a golden that agreed, and exits 0

`docs/testing/x1a7_forward_model.py:231-258`. A capture with no file on disk
prints `NO GOLDEN` and `continue`s (`:240-241`) **without touching `bad`,
`worst`, or any tally**. The summary at `:257` is then

```python
print('\n%d of 32 modelled halves differ; worst |delta| = %d' % (bad, worst))
```

— a hardcoded 32, over a `bad` that only ever counted the halves that existed.
The return is `1 if bad else 0`.

So the function reports perfect agreement on zero evidence. I ran it:

```
$ python3 docs/testing/x1a7_forward_model.py --proposed <empty dir>
scoring the PROPOSED implementation, not today's behaviour
1-DstAlpha_XA_O1A7RGB8       NO GOLDEN
1-DstAlpha_XA_Z1A7RGB8       NO GOLDEN
DstAlpha_XA_O1A7RGB8         NO GOLDEN
DstAlpha_XA_Z1A7RGB8         NO GOLDEN

0 of 32 modelled halves differ; worst |delta| = 0
RC=0
```

That last line is, character for character, the number this PR publishes in its
title, its body and `NOTES.md`. And the **partial** case is worse, because it
has no honest reading at all — with one of the four captures present I get
eight `ok` rows, three `NO GOLDEN` rows, and the same
`0 of 32 modelled halves differ; worst |delta| = 0`, RC 0. Eight halves
compared, thirty-two reported.

**Failure scenario.** The documented default is
`/tmp/goldens/results` (`:4`, `:265`). That path is **empty on this host right
now**, and is empty on any host where the disc has not been unpacked this boot.
A later lane, or the pass-2 auditor, runs the reproduction line the NOTES give
them — `docs/testing/x1a7_forward_model.py /tmp/goldens/results` — reads
`0 of 32 modelled halves differ; worst |delta| = 0`, exit 0, and records the
model as re-confirmed against goldens it never opened. Nothing in the run
distinguishes that from the real result.

This is not a generic robustness nit, and the reason is the PR's own argument.
The sixteen `DstAlpha` halves are pinned in `GOLDEN_DSTALPHA` and checked by
the selftest with no disc. The **held-out sixteen** — the `1-DstAlpha` pair,
which the body and NOTES correctly call the reason "a wrong sign cannot be
hidden by a table written to match" — are checked *only* by `score()`, and they
are exactly the entries that vanish into `NO GOLDEN` without a tally. The half
of the evidence that carries the falsification power is the half that
disappears silently.

**What remediation should do.** Count what was not read. `bad += 1` per missing
capture is not enough on its own — make the summary report the denominator it
actually compared (`%d of %d compared, %d of 32 expected`), and return non-zero
when `compared != len(pred)`. A `--require-all` that is on by default is the
shape this repo has settled on elsewhere. Also print the path of each golden
actually opened (see M2).

## MEDIUM

### M1 — `--proposed` computes the identical function to the default mode, so it cannot disagree with it

`docs/testing/x1a7_forward_model.py:69-76`, `:87-105`.

`write_transform(a8)` is `expand7(r2_a7(a8))` = `(a8>>1)<<1 | (a8>>1)>>6` —
which is `r1_blend_dst_alpha(a8)`, character for character the same expression.
And `write_transform(0x22) == 0x22`, the swatch alpha. Substituting both into
`proposed()` turns it into `swatch()` line for line. I checked it exhaustively
rather than by inspection: over all 1,024 combinations of
`background_alpha ∈ 0..255 × pad_bit ∈ {0,1} × one_minus ∈ {F,T}`,

```
proposed() vs swatch(): 0 differing of 1024
write_transform == r1_blend_dst_alpha over 0..255: True
```

So `--proposed` and the default mode emit byte-identical output on any input,
and the selftest's third section (`:213-221`, *"the PROPOSED fix, simulated
through the same draw sequence — reproduces 16 of 16"*) is a restatement of its
first section. There is no world in which the first passes and the third fails.

**Failure scenario.** The body presents this as a distinct result: *"**The fix,
simulated before any C is written** … scores it against the goldens: 0 of 32
modelled halves differ, worst |delta| 0, held-out pair included."* A lane
picking this up writes the `psh.c` write side, runs `--proposed` against real
goldens, sees 0 of 32, and records the implementation as validated before
device. But `--proposed` reads no C, and at the model level it re-evaluates the
same composition that R1 and R2 were *selected from* using the same 32 numbers.
It can only ever agree. The one thing it does catch is a mutation of
`write_transform` alone (M3 in my battery) — i.e. that R1's definition was not
broken in one of its two copies. That is a consistency check between two
spellings of one formula, not a simulation of a fix.

The lane half-knows this: `proposed()`'s docstring says the approximation "here
… happens to cost nothing, because `write_transform(0x22) == 0x22`". That
sentence is the *reason* the two functions coincide, and it is doing the work of
a disclaimer while the body and NOTES still bank the result.

**What remediation should do.** Either make `proposed()` model something
`swatch()` does not — the honest candidate is the `XA_*_Add_SrcA_DstA` pair the
note already identifies, where `expand7(As>>1)*Fs + Ad*Fd` and
`expand7((As*Fs + Ad*Fd)>>1)` genuinely differ, and where a predicted delta
would be a real forward prediction — or delete `--proposed` and the third
selftest section and say in one line that the fix implements R1 by identity, so
its simulation *is* the model. Either is fine. What is not fine is a headline
number that cannot fail.

### M2 — `score()` picks `hit[0]` out of an unordered multi-match glob and never says which file it read

`docs/testing/x1a7_forward_model.py:238-242`:

```python
hit = glob.glob(os.path.join(goldens, '*', name + '.png'))
if not hit: … continue
g = np.asarray(Image.open(hit[0]).convert('RGBA'))…
```

The `*` is a suite directory. A goldens root that holds more than one directory
carrying `DstAlpha_XA_Z1A7RGB8.png` — a re-run beside a previous one, a GL set
beside a Vulkan set, an unpacked archive beside a live capture dir — silently
scores the first the filesystem happens to return. `glob` does not sort. No
line of output names the file, so the run is not reproducible from its own
transcript and the reader cannot tell which artifact produced the number.

**Failure scenario.** A lane unpacks a fresh `iso_surf1` run next to the one
from an earlier sweep under the same root. `score()` reads the stale one,
prints `0 of 32 modelled halves differ`, and the lane concludes the model still
holds at the new master — the classic shape where a stale artifact measures
beautifully. With H1 this compounds: between the two, the published figures are
attributable to no named artifact at all.

**What remediation should do.** Sort the matches, refuse (or warn loudly and
count) when `len(hit) > 1`, and print the resolved path on every scored row or
once per capture. The PR's numbers should be re-runnable to the file.

## LOW

* **L1 — `model_with()` is a third copy of the composition, and nothing asserts
  it agrees with `swatch()`.** `:182-189` duplicates `:57-66`. Today they agree
  on all 1,024 inputs (I checked). But the rivals are scored through
  `model_with` while the model is scored through `swatch`, so a future
  correction to `swatch` that still satisfies the sixteen pinned goldens — a
  change that only affects `one_minus=True`, for instance, which neither
  `selftest()` nor the rival loop ever evaluates — would leave the four
  refutations being computed against the superseded composition, with the gate
  still green. One composition function taking `(r1, r2)`, called with the real
  pair for the model and the rival pairs for the rivals, removes the class.
* **L2 — the gate's first check counts 18 things and calls them 16.**
  `76-x1a7-model.sh:21-22`, `[ "$(x1a7cnt ' ok' "$X1A7")" -ge 16 ]`. The
  selftest prints 18 lines containing `' ok'` (16 goldens + the proposed line +
  the losslessness line; I counted them). So this check alone passes with two
  golden halves mismatching. It is sound today only because the separate
  `MISMATCH` check at `:23-24` catches them — but the check's own description,
  *"the model reproduces every pinned golden half"*, is then describing
  something it does not measure. Have the model print an explicit
  `16 of 16 pinned halves reproduced` tally and anchor on that string.
* **L3 — an undersized golden crashes rather than reporting.** `:246-250`: if
  an image is smaller than the hardcoded `MARGIN/TOP/SPACING/ROW_PITCH/SIZE`
  grid, `region` is empty and `counts.argmax()` raises
  `ValueError: attempt to get argmax of an empty sequence`. The five geometry
  constants are unvalidated against the image and undocumented as to where they
  came from. A shape assertion with the capture name in the message costs one
  line.
* **L4 — the NOTES' reproduction command does not reproduce its own table.**
  The note says *"Enumerate every site outside `vk/` … `grep -rn
  "X1A7R8G8B8_[ZO]" hw/`* — but that command as written includes `vk/` and
  returns 11 lines here, and the table lists six sites. The uncounted eleventh,
  `pgraph.c:4664`, is a comment, so the conclusion ("no GL-path code
  distinguishes them") is unaffected — but a later reader running the line and
  getting a different count will spend time on it. Quote the command actually
  run (`| grep -v '/vk/'`).

## Verdict

**1 HIGH, 2 MEDIUM → `needs-remediation`.**

None of this touches the emulator and none of it can regress a pixel; the
analysis underneath is unusually careful, every external claim I sampled held,
and the gate is stronger than the PR claims for it. The problem is confined to
the instrument, and it is the specific problem this repo has paid for most
often: a measurement that reports success when it measured nothing (H1), and a
verification leg that its own patch forces true (M1). Both are cheap to fix and
both must be fixed before the 458,042 px figure is used to justify writing C.

Pass 2 should verify, for each:

1. `score()` against an empty directory, and against a directory holding one of
   the four captures, **exits non-zero** and reports the denominator it
   actually compared.
2. `--proposed` either models something the default mode does not (and a
   mutation of that something is caught), or is gone along with the claim.
3. `score()` names the file it opened on every capture, and refuses or warns on
   a duplicate match.
