# Audit pass 2 — `lane.remote`'s 71 unfolded commits

Verification that the scenarios [pass 1](2026-09-14-remote-pass1.md) named **can
no longer occur**, plus a **pass 1** over the compiled code that arrived after
that audit ran. Machine-readable companion:
[`2026-09-18-remote-pass2.json`](2026-09-18-remote-pass2.json).

| | |
|---|---|
| Auditor | lane.audit2-remote (pass 2 of 2, plus pass 1 on the new code) |
| Base | `8c5218af3f0` (merge-base with the campaign branch) |
| Pass-1 head | `082878a1ca7` |
| Head | `6efac9c808` *#71 closed on HEAD — GL trails Vulkan on one capture* |
| Campaign tip | `6817aea04e` (worktree was **1,134 commits behind**; fast-forwarded before reading anything) |
| Scope | 71 commits. Pass 2 over 1 HIGH / 5 MEDIUM / 9 LOW; pass 1 over **+177 / −28** lines of new compiled code in 4 files |
| Method | reading, plus **five executed checks**: the x87 checker at two refs, an independent 2²⁴ exhaustive over the blend divide, and the shipped `gate.sh` delta block carved and run against synthetic inputs at both revisions. **Nothing was built.** |

## The result, plainly

**Pass 2 is clean on everything that was remediated, and two MEDIUMs were never
remediated at all.**

Of the 15 pass-1 findings: **9 CLOSED**, **3 DECIDED**, **3 OPEN** (M1, M2,
L8 — all three in `glsl/psh.c`, which **no commit has touched since pass 1**).
Every remediation that was attempted holds up, several of them better than the
commit messages claim, and none of them is the "assert implied by the condition
it sat under" failure this protocol exists to catch. The new compiled code
carries **no HIGH and no MEDIUM**.

**A clean pass 2 does not imply the fold.** That is the owner's call. Three
things bear on it and none is mine to decide: M1 and M2 are unremediated
MEDIUMs, and AGENTS.md:145 says "Every HIGH and MEDIUM is remediated before the
code folds in. Not deferred, not noted. The fold waits." Second, **four commits
carry no `[skip ci]`** — `622183271b`, `4a08abef66`, `6b78d91f24`,
`d843e41883`. Third, the Vulkan halves of both blit findings are still unfolded
(below).

## A scope correction, because the brief's figure overstates what was new

The brief lists six files and 383 lines as "the compiled code the first pass
never saw". That is the **whole unfolded diff** (merge-base → head), most of
which pass 1 did read. Measured:

| file | new since `082878a1ca7` | in pass 1's scope |
|---|---:|---:|
| `hw/xbox/nv2a/pgraph/gl/blit.c` | **+89 / −5** | — |
| `target/i386/tcg/fpu_helper.c` | **+45 / −10** | +142 / −9 |
| `hw/xbox/nv2a/pgraph/gl/draw.c` | **+33 / −6** | — |
| `hw/xbox/nv2a/pgraph/gl/texture.c` | **+10 / −7** | +18 / −3 |
| `hw/xbox/nv2a/pgraph/glsl/psh.c` | **0** | +29 / −3 |
| `hw/xbox/nv2a/pgraph/gl/surface.c` | **0** | +8 / −0 |
| | **+177 / −28**, 4 files | |

`glsl/psh.c` and `gl/surface.c` are not new code — they are pass 1's own
subject. That matters here for one reason only: psh.c being unchanged is
*exactly* why M1, M2 and L8 are open.

---

# Part 1 — verdicts on every pass-1 finding

## H1 — `fpu_helper.c` saturation — **CLOSED**

Remediated by `197370948e`, and the code delta is **four lines, one per
helper**, nothing else:

```c
-        return INT32_MIN;
+        return r < 0 ? INT32_MIN : INT32_MAX;
```

Five independent things establish the scenario cannot occur.

**1. Softfloat parity is now exact, checked at the source.**
`fpu/softfloat-parts.c.inc` `partsN(float_to_sint)`: qNaN/sNaN → `r = max`
(`:1233-1239`), infinity → `r = p->sign ? min : max` (`:1241-1244`), normal
overflow → `min` for negative and `max` for positive (`:1263-1271`). The hard
path now returns the same on every one. `r < 0` is false for NaN, which lands
it on MAX exactly as softfloat does.

**2. The checker has power, and it is aimed at the right half.**
`docs/testing/x87_conv_check.py` run at both refs, by me:

| ref | result |
|---|---|
| `origin/claude/docs-tooling-agentic-coding-u152m1` (head) | **35 assertions, 0 failed**; aarch64 cross-compile clean |
| `622183271b` (the commit that introduced the defect) | **35 assertions, 13 failed** |

The 13 are exactly: positive overflow ×5 (`2147483648`, `+2^40`, `+inf`, `rtz
+2^40`, and `2^63`), NaN ×4, `+2^70`/`rtz +2^70`, and the two FSCALE rows where
`+2^40` gives `0`/`-0` where `+inf`/`-inf` is required. **All eleven
rounding-mode rows pass on both sides. Every negative-overflow row passes on
both sides. Both exactness rows pass on both sides.** So the failures isolate
the half the defect was in and nothing else — which is the property that makes
this a check rather than a tautology. I derived the expected count of 13 from
the defect before running it and it matched.

**3. The carved region is the shipped text, and cannot diverge by an `#if`.**
The carve is `git show <ref>:target/i386/tcg/fpu_helper.c` sliced by
line-start markers — not a retyping. Verified further:

- byte-identical from the fix to head: sha256 `70eab9681e898307b9b5`, 123 lines
  at both `197370948e` and the lane head;
- all four `floatx80_to_int{32,64}[_rtz]_nds` bodies are inside the carve;
- **the carve contains no preprocessor conditionals at all** — so the text the
  checker compiles cannot differ from the text the real build compiles by a
  conditional selecting another body. This was the specific drift risk and it
  is structurally absent.

**4. The stub is faithful where fidelity is load-bearing.** The `inv=` half of
every assertion depends on `float_raise`; the stub's definition is
`include/fpu/softfloat.h:104-107` **verbatim**. The stub's
`float_round_nearest_even/down/up/to_zero = 0/1/2/3` and
`float_flag_invalid = 0x0001` match `include/fpu/softfloat-types.h:147-165`
exactly.

**5. The remediation does not introduce a new defect where #74 was aimed.**
Saturating is *not* the x87-architectural result for an out-of-range FIST — the
indefinite value is — so the fix would be wrong if any store site passed the
value through. None does, checked one at a time:

| site | overwrite | saturated value trips it? |
|---|---|---|
| `helper_fistl_ST0` :1073, `helper_fistll_ST0` :1086 | on `float_flag_invalid` | yes, flag-keyed |
| `helper_fisttl_ST0` :1113, `helper_fisttll_ST0` :1126 | on `float_flag_invalid` | yes, flag-keyed |
| `helper_fist_ST0` :1058, `helper_fistt_ST0` :1099 | `val != (int16_t)val` → `-32768` | yes — `(int16_t)INT32_MAX == -1`, `(int16_t)INT32_MIN == 0`, both ≠ |
| `helper_fbst_ST0` :1631 | `val >= 1e18 \|\| val <= -1e18` | yes — `INT64_MAX` and `INT64_MIN` both trip |

`helper_fscale` (:3188) still reads the value **unguarded**, and that is
correct: pass 1 offered clamping at the consumer as an alternative and warned it
"leaves the hard/soft divergence in place for any future caller." The lane took
the better option.

**Residual, unobservable:** softfloat also sets `float_flag_invalid_cvti` and
`float_flag_invalid_snan`; the hard path does not. Neither has a single reader
anywhere in `target/i386/`, so there is nothing to diverge. The missing
`float_flag_inexact` does have a reader (`:900`, → `FPUS_PE`) but that is the
documented KNOWN INCOMPLETE the other chain's P2 closed as documented-not-fixed,
and is unchanged by this commit.

## M1 — `psh.c:2376`, cube signs read after the border remap — **OPEN**

**No remediation commit exists.** `git diff --numstat 082878a1ca7..6efac9c808`
does not list `hw/xbox/nv2a/pgraph/glsl/psh.c` at all. The code is what pass 1
read:

```c
apply_border_adjustment(ps, vars, i, "dotSTR%d");          /* psh.c:2356 */
...
"vec3 dotSTR%dDir = vec3("
"dotSTR%d.x >= 0.0 ? DOT_STR_3D_K : -DOT_STR_3D_K, "       /* psh.c:2377 */
"dotSTR%d.y >= 0.0 ? -DOT_STR_3D_K : DOT_STR_3D_K, "       /* psh.c:2378 */
```

The read is still twenty lines after the call that rewrites the vector, and
`remapBorderCube` (`:1673`) still reconstructs a direction with the major axis
forced to ±1.0. With a border enabled, `.x` is the sign of the major axis, not
of `dot_{i-2}`. **The scenario survives unchanged.** No decision is logged
anywhere: the lane branch carries no `docs/audits/` directory, and no file on it
mentions M1, M2 or the audit at all.

The brief asked whether the fix "merely moved the read" — there is no fix to
ask that of.

## M2 — `psh.c:2381`, implicit-LOD fetch of a step function — **OPEN**

Same commit, same absence. `psh.c:2380` is still
`texture(texSamp%d, dotSTR%dDir)`; `grep -n textureLod hw/xbox/nv2a/pgraph/glsl/psh.c`
returns nothing on either branch. The coordinate still takes exactly four
values, so the derivative the sampler sees is still identically zero inside a
sign region and ~2K across a boundary. **The scenario survives unchanged.**

**One thing pass 2 can add that pass 1 could not.** The campaign branch does not
carry `4a08abef66` at all — `psh.c:3120-3141` at `6817aea04e` still passes the
whole direction in, with neither the sign step nor `DOT_STR_3D_K`. So M1, M2 and
L8 are **entirely confined to the unfolded work**: nothing in the campaign
branch is exposed today, and the fold is the moment they would become live. That
is a reason the fold should wait, not a reason the findings are less severe.

## M3 — `gate.sh`, a header could never enter the intersection — **CLOSED, functionally**

Remediated by `4020fa286f`, which replaced the source-path-to-object-name
mangling with `ninja -t deps`. Reading it is not enough — the new path could
have been the same bug differently shaped, since it requires an exact full-line
match between the object path `ninja -t deps` reports and the one `objs()`
scrapes out of the gate log. So I ran it.

`ninja` is **not installed on this host and there is no `build/`**, so I carved
the shipped delta block (`docs/testing/gate.sh:154-220`, verbatim) and ran it
against two synthetic gate logs with a stub `ninja -t deps`, then ran the
**pre-fix** block (`082878a1ca7:docs/testing/gate.sh:133-160`) against byte-identical inputs.

Inputs: `accel/tcg/tb-cache-hints.h` warns in the previous run only, and its
dependent object `accel_tcg_cputlb.c.o` was compiled in **both**. Control:
`vk/stb_image_write.h` warns in the previous run only and its object was
compiled in **one** run only.

| | intersection | `removed:` |
|---|---:|---|
| **pre-fix** | 1 file | *(empty)* — the header removal is silently dropped |
| **post-fix** | 2 files | `accel/tcg/tb-cache-hints.h :: HEADER-WARN-REMOVED` |

**A header can now appear, and the fix did not simply widen everything in**: the
one-sided control header was correctly excluded from the intersection by both
versions. That is the discrimination leg — a remediation that reported
everything would also have "fixed" this test.

## M4 — the skew doc's mode-2 conclusion — **DECIDED (REFUTED)**

Not re-audited, per the brief. Disposition confirmed on `[issue.44]`, quoted:

> REFUTED BY THE SAME LANE AND THE REFUTATION IS BETTER THAN THE FINDING: the
> SCAN_MAX_WORDS bail counter already rides the `fifoskew` line as `big=` and
> `fifo_skew_report.py` already parses it. Measured on every mode-2 run on disk,
> `big/scan_n` is 0.0044% on Galleon, 0.0077% on Crimson, 0.0134% on the Texture
> border disc — three orders of magnitude from a scan that bails […] AND THE
> PRIOR IN M4 IS THE DISC'S, NOT THE WORKLOAD'S: 148,704 submissions for 180
> draws is the test disc […] Galleon skips 5.2% and runs 94.2%/93.2%
> draw-carrying.

The refutation is the stronger document. Recorded and moved on.

## M5 — "bounds the noise floor's cause completely" — **DECIDED (accepted, routed, logged)**

Not re-audited. `[issue.44]` records the finding as accepted and delivered to
`lane.skew44` in flight "with the text rather than a pointer", with the
remediation stated:

> M5 (doc:47): 'it also bounds the noise floor's cause completely' generalises a
> TWO-TEST DISC to a full-disc band whose recorded signature DIFFERS — pixels
> moving at a constant score there, a varying score here. **Restrict the claim
> to the disc it was measured on and carry the full-disc observation as open.**

One factual observation, offered without re-opening the finding: the sentence
itself is **still unrestricted** at
`docs/investigations/skew-bound-closes-the-desktop-race.md:72-74` on the lane
branch. The decision is logged; the edit it asks for has not been made.

## L1 — the `fp_safe` comment — **CLOSED**

`8c864b1d22` corrected it. Verified independently: `nativeGetFpSafe` occurs
exactly once in the tree outside the comment —
`android/app/src/main/java/com/rfandango/haku_x/SettingsActivity.kt:1454`,
`private external fun nativeGetFpSafe(): Boolean`. **No caller.** The comment now
says so, and keeps the correct half (the setting is inert either way).

## L2 — "two flag-reading helpers" stated as exhaustive — **CLOSED at the cited site; one residual**

`fpu_helper.c:239-245` now names all four and explains the 16-bit pair's value
test. Verified: the `get_float_exception_flags(&env->fp_status) &
float_flag_invalid` guard appears at **:1079, :1092, :1119, :1132** — four
helpers, exactly as the correction says.

**Residual, LOW (new finding N1 below).** The identical understatement survives
in a **second** comment in the same file, at `:369-370`: "helper_fistl_ST0 and
helper_fistll_ST0 test precisely that flag". Two of four. That text is
`622183271b`'s, so it was in front of the same sweep that fixed `:239`. A
correction applied to the row that raised the suspicion and not to the others.

## L3 — `downloaded` / "actually written back" — **CLOSED**

Verified at the callee, not the comment.
`pgraph_gl_download_surfaces_in_range_if_dirty()` (`gl/surface.c:1628-1644`)
returns `found_overlap`, set whenever `check_surface_overlaps_range()` is true
regardless of dirtiness. The variable is now `overlapped` and the comment reads
"Only when an overlapping surface was found." **Behaviour deliberately
unchanged, and still right** — overlap is exactly what the old
`if (overlapping)` tested, which is the whole point of #80's fix.

## L4 — `emulator_pids()` returning 1 on success — **CLOSED, functionally**

Executed the shipped function: `status=0` with no match. Pass 1 had probed the
old one returning 1 *while printing a pid*. The added `return 0` is the last
statement, so the loop's final test can no longer leak out.

## L5 — hard-coded `REPO`, unchecked `cd` — **CLOSED, functionally**

Executed all three legs of the shipped expression: `REPO` derives from
`BASH_SOURCE`'s directory; `GATE_REPO` overrides it; and `cd` to a bad `REPO`
prints `REFUSING: cannot cd to REPO=…` and exits **2** — which is the status the
gate reserves for refusing, closing L4's related concern about aborting with 1.

## L6 — two loose matches — **CLOSED, functionally, both halves**

Each with a control, because a remediation that cannot be shown to discriminate
is not one.

*Unescaped `.` in the ERE.* Against a decoy object
`libqemu.a.p/target_i386_tcg_fpu_helperXc.o`: the old pattern **matched** it
(the `.` was a wildcard); the new one does not, **and still matches the real
`…_fpu_helper.c.o`** — so it was not over-tightened.

*Unanchored substring in `incommon()`.* With `common_src` holding only
`gl/texture.c`, the old `grep -Ff` returned both `gl/texture.c` and
`vendor/gl/texture.c`; the new awk exact-first-field form returns only
`gl/texture.c`.

One inaccuracy in the remediation's own control claim, not in the code:
`4020fa286f`'s message says the old form also returned `gl/texture.c.inc`. It
does not — `keyed()`'s regex requires `.c`/`.h` immediately before `:line:col`,
so `.inc` never reaches `incommon()`. Harmless; noted because the commit offers
it as evidence.

## L7 — `find build -name '*.c.o'` as the denominator — **CLOSED by reading; not runnable here**

The denominator now comes from `ninja -C build -t commands qemu-system-i386 |
grep -c ' -c '`, which does not depend on what is on disk, with an explicit
`(denominator unavailable)` fallback line. **I could not execute this**: no
`ninja` and no `build/` on this host. Read-verified only, and said so.

## L8 — `#define DOT_STR_3D_K` in every pixel shader — **OPEN, and unlogged**

`psh.c:2729` still emits it unconditionally into every shader for the benefit of
one case arm. psh.c is untouched since pass 1, and no decision is logged. Per
AGENTS.md:147 a LOW may be reviewed and not fixed — but "silence is not" an
acceptable outcome, and this is silence. It is the cheapest item on the list.

## L9 — the skew doc's unnamed Vulkan tree — **DECIDED, and the caveat is wider than the finding**

`8c864b1d22` added the caveat rather than re-running, and went further than the
finding did. Verified present at
`skew-bound-closes-the-desktop-race.md:47-70`:

> **CAVEAT, and it weakens the sentence above — audit L9.** […] Its five-run
> digest comes from `docs/testing/desktop-noise-floor.md`, where the measurement
> is dated 2026-09-13 and described as "an unmodified binary" — but **no commit
> is recorded, and neither is the ISO**. Checked rather than assumed: the only
> shas in that file are at its lines 158 and 198, both for other measurements
> […] So this is an equality **across two trees**, not a within-tree identity.

And it declines the re-run for a stated reason: the disc is unrecorded, there
are 58 ISOs, and "guessing which […] would have produced a number that looked
like a confirmation without being one." That is the right call and the right
shape of record.

## Verdict table

| id | severity | verdict | how established |
|---|---|---|---|
| H1 | HIGH | **CLOSED** | checker at both refs (35/35 vs 13/35), softfloat parity read at source, carve hash-identical and conditional-free, all 7 store sites re-checked |
| M1 | MEDIUM | **OPEN** | no commit touches `psh.c` after pass 1; read at `:2356` vs `:2377` |
| M2 | MEDIUM | **OPEN** | same; no `textureLod` in the file |
| M3 | MEDIUM | **CLOSED** | shipped block executed at both revisions; header appears post-fix, dropped pre-fix, one-sided control excluded by both |
| M4 | MEDIUM | **DECIDED** (REFUTED) | `[issue.44]`, quoted |
| M5 | MEDIUM | **DECIDED** (accepted/routed) | `[issue.44]`, quoted |
| L1 | LOW | **CLOSED** | one occurrence in the tree, no caller |
| L2 | LOW | **CLOSED** at `:239`; residual at `:369` → N1 | four guards confirmed at :1079/:1092/:1119/:1132 |
| L3 | LOW | **CLOSED** | callee returns `found_overlap`, verified |
| L4 | LOW | **CLOSED** | executed: status 0 |
| L5 | LOW | **CLOSED** | executed: derivation, override, refusal with exit 2 |
| L6 | LOW | **CLOSED** | executed, both halves, each with a decoy control |
| L7 | LOW | **CLOSED** (read only) | no ninja on this host |
| L8 | LOW | **OPEN**, unlogged | `psh.c:2729` unchanged, no decision anywhere |
| L9 | LOW | **DECIDED** | caveat present and wider than the finding |

---

# Part 2 — pass 1 over the new compiled code

+177 / −28 in four files. **No HIGH. No MEDIUM.** Six LOWs.

## `gl/blit.c` — `d843e41883`, the #38 round-not-truncate port

**The GL port is the same arithmetic in result, not in expression** — and that
is the answer to the margin question, because the expressions have very
different failure behaviour.

| | expression | bias | divisor |
|---|---|---|---|
| Vulkan `blend_and_div()` (`24a75d6e3c`) | `((W + 0x3FC0) >> 7) * 0x8081 >> 23` | `0x3FC0` | `>>7` then `/255` |
| GL (`d843e41883`) | `(a + b + max_beta_mult/2) / max_beta_mult` | `max_beta_mult/2` = `0x3FC0` | `/0x7f80` |

Same bias, same effective divisor, same round-half-up; `floor(floor(v/128)/255)
== floor(v/32640)` makes them equal. GL uses a genuine `uint32_t` division
rather than the reciprocal.

**Verified exhaustively by me, not taken from the comment.** `beta` is masked
with `0x7f800000` at `pgraph.c:1951` and read as `beta >> 16`, so `beta_mult`
steps by `0x80` to `0x7f80`: 256 values × 256 src × 256 dst = **16,777,216**
triples. Against an exact 64-bit integer round-half-up reference:

| | measured |
|---|---:|
| `beta_mult` values | 256 |
| new form, mismatches | **0** |
| truncating form, mismatches | **8,164,890** — low on every one, high on none, worst error 1 |
| exact half-ties in the domain | **0** |
| new-form results exceeding 255 | **0** |
| largest reachable `a + b + bias` | **8,339,520** |

Every figure in the GL comment reproduced. Two things that deserve saying: the
comment's "NOT ESTABLISHED: the tie-break" is **honest** — there really is no
half-tie anywhere in the domain, so nothing here chooses half-up over half-even;
and the comment explicitly refuses to reconcile its 8,164,890 with
`lane.blit38`'s 8,388,608, correctly, because those are different expressions
(divisor 32,640 vs 32,768). A lane that had silently reconciled them would have
manufactured agreement.

**Does GL have the same margin as Vulkan? No — a much larger one, and of a
different kind.** Vulkan's audit M1 is that `(W * 0x8081) >> 23 == W / 255`
holds only for `W < 2¹⁶`, largest reachable 65,152 against first failure 66,299
— **1.76%**, and the first failure is a silently wrong pixel. **GL has no such
precondition at all**: there is no reciprocal approximation to lose exactness,
so the only bound is `uint32_t` overflow of `a + b + 16320`, whose largest
reachable value is 8,339,520 — **0.19% of 2³², roughly 515× headroom.** GL also
has **no NEON path** in `blit.c` (the only `glLineWidth`-style vector body is
Vulkan's), so Vulkan M1's "the two paths would be wrong *differently*" hazard
has no GL analogue either.

What GL does still share is the **underflow** half: `inv_beta_mult =
max_beta_mult - beta_mult` wraps if the `pgraph.c` mask were ever widened, and
`b` then overflows silently. There is no `assert(beta_mult <= max_beta_mult)`.
But Vulkan M1's actual complaint — "nothing in `blit.c` names that dependency,
nothing asserts it, and the two files carry no cross-reference" — is **half
discharged on the GL side**: `blit.c:107` now says "beta is masked with
0x7f800000 in pgraph.c", which is precisely the cheaper remediation Vulkan M1
offered as an alternative to the assert ("a comment in `blend_and_div()` naming
`pgraph.c:1951` as the enforcer […] gives a mask change a thread to pull"). LOW
N2 below, not a repeat of M1.

## `gl/blit.c` — `b9d845d316`, the GL half of #84

**The GL fix does refuse, and the refusal is complete.** `bytes_per_pixel` is
threaded into `perform_blit()`; the `!= 4` warn-once early return is the **first
statement** of the `BLEND_AND` branch, before any dereference of `s` or `d`; and
every path forwards it — `perform_blit_tiled()` (`:244`) and all three
`perform_blit()` call sites (`:420`, `:443`, and via tiled at `:413`/`:434`).

**There is no second path.** `patch_alpha()` and `patch_alpha_tiled()` also
hard-code `/4`, but `needs_alpha_patching` is set only for
`LE_X8R8G8B8` and `LE_X8R8G8B8_Z8R8G8B8` (`blit.c:451-462`, `default:` is
false), both `bytes_per_pixel == 4`. So the narrow formats cannot reach it.

**Did GL have the same exposure? Same in kind, same in the mechanism that fails
to catch it, and bounded the same way.** Verified:

- `nv_dma_map()`'s end-of-object assert **is** commented out —
  `nv2a.c:96`, `// assert(dma.address + dma.limit < memory_region_size(d->vram));`
- `pgraph_gl_image_blit()` asserts only `context_surfaces->dest_offset <
  dest_dma_len` (`blit.c:322`) — the **start offset**, not the extent. Nothing
  compares `dest_offset + dest_size` against `dest_dma_len`.

**But "unbounded" overstates it, and overstates the Vulkan audit too.** The
pre-fix per-row walk was `row_pixels * 4` bytes where the row is `row_pixels *
bpp`, and `row_pixels ≤ MIN(source_pitch, dest_pitch) / bpp` (`blit.c:335-338`),
so the furthest write is at most `4/bpp` pitches into the row — roughly **3
extra pitches past the nominal object end on Y8, 1 on R5G6B5**. Vulkan carries
the **identical** clamp at `vk/blit.c:376-379`, so the two sides' bounds are the
same. And the Vulkan audit itself says so:
`2026-09-14-blit-pass1.md:118-120` — *"I did **not** establish that the overrun
can leave the VRAM mapping entirely; that depends on where the guest places the
surface. The claim is corruption beyond the blit rect, not a host-memory
escape."* **For #84's row: GL's exposure was the same as Vulkan's, corruption
beyond the rect rather than a host-memory escape, and the GL half is now
refused.**

**And the Vulkan half of #84 is still unfixed.** `vk/blit.c:34`'s
`perform_blit()` takes no `bytes_per_pixel` and its `BLEND_AND` branch has no
guard — at campaign HEAD *and* at lane head. `[issue.84]` is `status = "open"`
and titled against `vk/blit.c`, consistent. Likewise `24a75d6e3c` (#38, Vulkan)
is contained only by `worktree-agent-a800eb98ac1ec5861` — not by the campaign
branch — so `vk/blit.c` at HEAD still carries the old `(val + 0x3FC0) >> 15`
divide-by-32768. Two of the three blit fixes are unfolded.

## `gl/draw.c` — `5b70760210`, `glLineWidth(0)`

Clean. `set_line_width()` guards on `width > 0.0f`, which also excludes NaN and
negatives (both of which `glLineWidth` rejects). **All three call sites go
through it**: `grep -rn 'glLineWidth' hw/` returns exactly one raw call, inside
the guard, plus the three `set_line_width()` sites at `:394`, `:400`, `:404`.
The "behaviour-identical" claim is sound — a call GL rejects is a no-op, so the
context's line width is the same either way — and the commit proved it with 134
of 134 captures `cmp`-identical rather than arguing it. The `#else` assert at
`gl/shaders.c:413` is confirmed to be on the error state **on entry**, and the
`__ANDROID__` arm drains instead, so the abort really was desktop-only.

The commit also registers what it deliberately does not settle — what hardware
draws at line width 0, and whether to clamp up to the minimum supported width —
which is a logged decision rather than a silence. Cross-checked the twin:
`vk/draw.c:3122-3124` reads `lineWidthRange[0]` as a floor, so Vulkan does not
share the hazard.

## `gl/texture.c` and `fpu_helper.c`

The new lines in these two are the L3 rename plus comment and the H1 fix plus
L1/L2 comments, both verified above. Nothing further.

## New findings

| id | sev | site | one line |
|---|---|---|---|
| N1 | LOW | `fpu_helper.c:369-370` | L2's understatement survives here: names two of the four helpers that read `float_flag_invalid`. The sweep fixed `:239` and not this. |
| N2 | LOW | `gl/blit.c:77-79` | No `assert(beta_mult <= max_beta_mult)`; `inv_beta_mult` underflows silently if `pgraph.c:1951`'s mask widens. Weaker than Vulkan M1 — the comment now names the enforcer, and GL has no exactness cliff — but the invariant is still unenforced. |
| N3 | LOW | `gl/blit.c:66-76` | `static bool warned` fires once per process for the **first** offending `bytes_per_pixel`, so a title doing Y8 then R5G6B5 reports only the first, and the message names only that one. Plain `static bool`, no atomicity, on a vcpu-thread path. |
| N4 | LOW | `gate.sh:178-181` | The M3 fix is **silent** when `ninja -t deps` yields nothing: `.deps` ends up empty, `hit` stays 0, and no header enters — with no notice, unlike the L7 fix which prints `(denominator unavailable)`. Not reachable in a real gate run (gate.sh invokes ninja itself), hence LOW, but the failure mode is the same silence M3 was about. |
| N5 | LOW | `gate.sh:159` | `objs()` still greps only `Compiling C object`, never `Compiling C++ object`, while `COMPILES` and the new `OBJS` count both. A header included only by C++ TUs still cannot enter the intersection. Narrow residual of M3. |
| N6 | LOW | `gate.sh:192` | The header lookup is `grep -F "/$src"`, so a generated header with no directory component (a `config-host.h` at the top of `build/`) cannot match. Narrow residual of M3. |

---

# Part 3 — the lane's own three closes, and the withdrawn overclaim

## The overclaim did not survive in a second document

`8c938792fa` withdrew the claim that a corpus binary compiled the #82 fix. The
brief's concern is that an overclaim withdrawn once can survive elsewhere.
**Searched, and it did not.**

- `grep -rn '19737094|d7dfe146|0\.4\.0-j1-331' docs/` on the lane branch returns
  nine other hits. Every one uses `d7dfe146` as the **corpus-binary label** for
  GL/pgraph pixel measurements — legitimate, since the git-describe string names
  the source and those runs are the desktop x86-64 build. **None** asserts an
  arm64 target or that the binary compiled the `_nds` block.
- `grep -rn 'arm64|aarch64' docs/investigations/ docs/testing/predictions/`
  outside the #82 document returns only scoping discussion (#74, #67) and a
  swizzle note. No build claim.
- `[issue.82]`'s `status_note` carries the withdrawal itself, correctly, and no
  residue of the original sentence.

**Verified the right way rather than by grep alone:**
`git branch -a --contains 197370948e` returns **only**
`remotes/origin/claude/docs-tooling-agentic-coding-u152m1`. The commit is not in
the campaign branch and not in any other ref, so **no arm64 build can contain
it.** The conclusion holds.

One supporting sentence in the withdrawal is nonetheless false, and it is worth
one line precisely because that commit exists to stop a false sentence riding a
true conclusion. It says "there is no APK on this host". There are **seven**, in
`/home/justin/hakuX` — `hakuX.apk`, `hakux-0.3.3-release.apk`,
`hakuX-0.3.3-j1.apk`, `hakuxfork.apk`, `hakuxj1unsigned.apk`,
`hakux-unsigned.apk`, and a zero-byte `control.apk` — all dated 2026-09-06 and
therefore incapable of containing a 2026-09-14 commit. The right argument is the
containment check, which the same paragraph also makes.

## #66, #71, #82 and #85–#88

Dispositions on the campaign branch's `nv2a_issues.toml` are consistent and
carry their provenance: **#66 `fixed-verified`**, **#71 `fixed-verified`**,
**#82 `fixed-verified`**. `#85`–`#88` are all `open` and each names what it was
split out of and why — #85 and #86 out of #66, #87 out of #71, #88 found while
closing #71. That is the correct shape: a second defect wearing a closed issue's
clothes is invisible, and these do not.

`[issue.82]`'s own summary of the checker's power matches my independent run
line for line — "against 62218327 […] 13 of 35 FAIL — every positive overflow,
every NaN, and FSCALE with +2^40 giving 0 and -0 where +inf and -inf are
required — while every negative-overflow and every ro[unding-mode row passes]".
The record is accurate.

Note the lane branch's own copy of `nv2a_issues.toml` stops at `[issue.53]`; the
tracker lives on the campaign branch, which is correct — it is board territory,
not the lane's.

---

# What I could not audit, and why

- **Nothing was built.** The desktop build is a **known named gap on this host**
  (`libcurl4-openssl-dev` not installed), and the `fpu_helper.c` block is inside
  `#if defined(XBOX) && defined(__aarch64__)`, so a working desktop build would
  not compile it anyway. **`ninja` is not installed on this host and there is no
  `build/` directory** in either the worktree or the shared checkout. I compiled
  none of the four changed files as part of the QEMU build.
- **What I *did* execute**, stated so the difference is visible: the x87
  checker's own native build of the **carved shipped text** (and its aarch64
  cross-compile leg, compile only) at two refs; a standalone 2²⁴ exhaustive of
  the blend divide that I wrote myself; and the shipped `gate.sh` delta block,
  carved and run at both revisions against synthetic inputs. Those are real runs
  of real shipped text, and they are not a build of the emulator.
- **`gate.sh`'s L7 denominator is read-verified only** — it needs `ninja`.
- **No device.** Both handhelds are out of service; `hold/thor` and `hold/nova`
  are in place and I did not touch them or queue anything. Every measurement
  claim in the window — the 12 BLENDAND captures to byte-exact, `iso_line`'s 134
  captures, 235 of 236 on `iso_surf1`, the #66/#71/#82 closes' pixel numbers —
  is taken on trust. M1 and M2 remain unreachable by anything on the test disc:
  no capture carries a bordered cubemap on a DOT_STR_3D stage, and nothing on
  any buildable disc issues an `FSCALE` with a runaway exponent.
- **M2's LOD question is still unmeasured on silicon.** Whether hardware's
  DOT_STR_3D cube fetch uses LOD 0 or a computed level is not established
  anywhere in the record, so pass 1's `textureLod(..., 0.0)` still picks the
  level that matches the derivation rather than one that was measured. This is
  not an argument for leaving M2 open — the current code takes a level nobody
  chose at all.
- **I did not re-audit M4 or M5**, per the brief.

# Outside my territory

I hold no files. Two items are recorded in
`$DISPATCH_DIR/board-requests/audit2-remote.md` rather than acted on here:

1. **M1, M2 and L8 are unremediated and need dispatching** before the fold, per
   AGENTS.md:145-149. All three are in `glsl/psh.c`, none is in my territory,
   and an auditor that patched them would be grading its own homework.
2. **The Vulkan halves of #84 and #38 are unfolded**, and `[issue.84]`'s row has
   an open question this audit answers — GL's exposure was the same in kind and
   bounded the same way, and the GL half now refuses. That belongs on the row,
   and rows are board territory.

I did not edit `nv2a_issues.toml`, `territory.toml` or any board file. (For the
record, the lane did not repeat pass 1's finding either: `git log
082878a1ca7..6efac9c808 -- docs/testing/nv2a_issues.toml docs/testing/territory.toml`
is empty, so `45c8adb4f6` remains the single instance, already filed.)
