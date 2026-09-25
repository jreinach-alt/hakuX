# lane.remote — resumed 2026-09-20 onto master

The session that ran this lane through 2026-09-18 is the same one writing this.
It has now been reset from master twice, for the same reason each time: a
merged PR cannot track new work.

- PR #45 merged 2026-09-18T23:11Z (fold `fa3d04f2`), 78 commits.
- **PR #162 merged 2026-09-19T22:24:55Z (fold `11ddd94a66`)** — #158's GL
  pad-bit write side. Verified on master by content rather than by the merge
  message: `pad_write_color_factor` in `gl/draw.c`,
  `pgraph_glsl_set_dual_src_pad_supported` in `gl/renderer.c` and `glsl/psh.c`.
  The branch was fast-forwarded to master at `151dc059` and nothing was
  carried forward.

**`gl/draw.c` is no longer this lane's.** It was released 2026-09-19 and granted
to `[lane.clrpad164]` for #164; that lane has PR #172 open. Do not edit it.

## What changed underneath this lane

- **The orchestrator session is retired.** The channel is GitHub issues, tagged
  `[lane.remote]` on the first line. There is no peer session to message.
- **`[skip ci]` is retired** (`preflight.sh:338`): the repository is public and
  Actions are free, so the gate this lane pushed under for four days is gone.
- **The board is `origin/board`**, and a lane may not edit `territory.toml` or
  `nv2a_issues.toml`; `preflight.sh` checks it.
- **Seven of this lane's nine claimed issues are closed.** #138 asked where the
  lane's commits lived and walled the rest behind the answer; answered by
  containment rather than by hunting for a worktree.

## Open, and what each is actually blocked on

| issue | state |
|---|---|
| #34 | not this lane's: four findings in `vk/*`, and the device confirmation is APK packaging in `android/` |
| #60 | **its own fix is landed and correct** (`a105a51a`, the `drawn_format` refresh). What is left is the whole `X1A7R8G8B8` family. **GL is now 449,850 px, equal to Vulkan and byte-identical to it on all ten captures** (`da9e02a2`); the last GL-only swatch turned out to be a texture-cache coherence defect and not a pad bit at all. The remaining 449,850 px is the pad-bit residual, and its read side needs `gl/surface.c` — **asked for, not held**. See the two sections immediately below, in that order |
| #62 | finding 2 was implemented on `a5fdb6a7` and then **WITHDRAWN — reverted in `d7ef9820`** (audit pass 2c, A1): the condition it added is unreachable, because `pgraph_gl_check_surface_to_texture_compatibility()` refuses every replication-expanding texture format at `gl/surface.c:1543`, and has done since `c234c1cc`/`f0095555` on 2026-09-12 — the day *before* #62 was filed. **The device ask is withdrawn**; there is nothing here for a device lane to confirm. `gl/surface.c` is byte-identical to master on this branch. The other five findings were already fixed and verified in master. See the pass-2c section at the end of this file |
| #88 | filed by this lane; needs `vk/surface.c`, which this lane does not hold |

## Audit pass 1 on PR #181: disposition (2026-09-20)

`docs/audits/2026-09-20-claude/docs-tooling-agentic-coding-u152m1-pass1.md`
(`8e0e32bf`) — 1 HIGH, 1 MEDIUM, 4 LOW. The `gl/texture.c` fix was checked
claim-by-claim against the tree and stands; **both actionable findings are in
the prediction files**, and H1 is that the file written to stop a
wrong-renderer arm could not stop one.

| | finding | disposition |
|---|---|---|
| **H1** | the routing requirement is prose, and `arms.sh` reads no prose | **taken** — `title` marker + hand-queue recipe, verified by running the job |
| **M1** | two falsified predictions have live `b_ref`s and would spend four device arms | **taken** — same marker, and each says so in its first paragraph |
| L1 | the PR body has no `roles/lane.md` header | **taken** — header added |
| L2 | `nv2a_index.json` provenance records the sandbox's paths | **accepted, not fixed here** — see below |
| L3 | the superseded file's "uncomfortable outcome" is unreachable | **acknowledged, no edit** — that file is judged; the supersession already replaced the leg with a reachable one |
| **L4** | one path where "cannot be less correct" is not true | **taken** — the live file names `flush_surfaces()` and stops asserting the universal |

### H1 and M1, and how the remediation was verified

`arms.sh`'s queue loop reads `registered_utc`, `amended_utc`, `a_ref`,
`b_ref`, `who`, `issue`, `title`, `runs_per_arm` and the suites, then calls
`request.sh` with **no `--device` and no `--env`** (`arms.sh:671-675`). A
renderer requirement in the `prediction` string is therefore invisible to it.
`title` is the only opt-out the schema has (`arms.sh:654`), and nothing else
in the tree reads a prediction's `title` — the other hits are on GitHub issue
and request objects.

**Verified by running the real job, in both directions**, rather than by
reading the patch. `HAKUX_WORK` and `HAKUX_REPO_DIR` redirect `arms.sh` into
a scratch work dir, and a `refs/remotes/origin/lane/*` ref makes `collect()`
consider the branch:

- **mutant** — the head before the remediation: all three files pass *through*
  the title gate and skip at the next one.
- **positive** — the head after it: all three skip with
  `soak predictions (title=…) are hand-read; queue with request.sh --title yourself`.

The container cannot demonstrate the `WOULD QUEUE` branch itself: `suites_for`
finds no goldens here, so the mutant's fall-through lands on
*"no suite with goldens in its keys or disc"*. **On the host it resolves —
proven by the FAIL verdict itself, which lists all six suites.** So the gate
the remediation moves is the one upstream of everything that differs.

Calling this a "soak prediction" in the skip line is a small inaccuracy in
service of a true one; the schema has no field for a renderer, and inventing
one is a harness change, not this lane's.

### L2, accepted rather than fixed

The regeneration is required (the commit touches `hw/xbox`) and the auditor's
own check says it is sound: `tests_commit` unchanged at `91a0de45`, 103
suites, no suite dropped, every moved `loc` landing correctly. What churns is
`provenance.tests_root` and `support_dirs[0]`, which record the generating
machine's absolute paths. **That is a property of the generator, not of this
diff: the same two lines have flipped between `/home/justin/…` and
`/home/user/…` 17 times each — 34 commits — before this branch existed.**
The fix is one line in `nv2a_index.py` (normalise a leading `$HOME` to `~`,
which keeps `describe_suite_drift`'s message runnable on either host), and it
belongs in a change of its own against a shared generated artefact rather
than smuggled into a PR about a texture cache.

## Remediation re-checked by `job.cloud`, and the one thing that is not a lane's (2026-09-20)

The remediation above was pushed but the PR's `needs-remediation` label was
never moved, so the outlet claimed #181 again. This firing re-checked it
rather than assuming it, and **changed no fix**: H1 and M1 are discharged and
the evidence is the real job's, not a re-reading of the patch.

| | how it was checked this firing |
|---|---|
| **H1** | `arms.sh:653-656` skips on a non-empty `title` — read in the tree, and it sits *after* `live_ancestor` so a live `b_ref` does not get past it. `2026-09-20-gl-stale-surface-blit-opengl.json` carries `title` and hashes to `aafb5bf5eee8`, which the host's own `[job.arms]` comment of 10:05Z lists as skipped |
| **M1** | same marker on `…-x1a7-read-side.json` (`8bbb18a02078`) and `…-x1a7-download.json` (`b259b4104da0`); the same `[job.arms]` comment lists both as skipped. Four device arms on reverted code are not spent |
| L1 | the `Files:` line was missing the audit file the pass-1 auditor pushed to this branch. Added, so it matches `git diff --stat origin/master...HEAD` (8 files). `gh pr edit` applies nothing on this host — done with `gh api -X PATCH` and read back |
| L2 | left as dispositioned above. It is the generator's property and the argument with the 34-commit count stands |

### The `regressed` label cannot clear itself, and that is the owner's call

Recorded here because a PR comment is not where a decision gets read.

`fold.sh:675` gates on the `regressed` label and parses no verdicts — "the
label is the interface" (`fold.sh:581`). `arms.sh`'s `label_decide()` keeps,
per issue, the newest registration **that has a verdict on disk**. For `#60`
that is `e988be896f6d` — the pre-marker snapshot of the OpenGL file, judged
FAIL on a handheld pair whose 269 captures were byte-identical. The marker
that discharges H1 is exactly what stops `aafb5bf5eee8` ever acquiring a
verdict to displace it, so **the remediation and the frozen label are the
same change**, and no tick can undo it.

Three ways out, and none of them is a lane's or this job's:

1. a hand-queued desktop pair for `aafb5bf5eee8`, both arms
   `--device desktop --env HAKUX_RENDERER=OPENGL`, recipe in the file's first
   paragraph. Its verdict is newer, so it takes the live row and the label
   follows by itself;
2. `regression-accepted:60` — **the owner's, explicitly**: "A lane must not
   set it and no job sets it" (`fold.sh:639`). The argument for it is on #60,
   where that gate says the trade has to be argued. Note what it would be
   asserting is unusual: not that a regression is an accepted trade, but that
   the FAIL is a wrong-renderer measurement and there is no regression to
   accept. The gate has no word for that;
3. a `prediction` field `arms.sh` passes to `request.sh --device`/`--env`,
   which is audit pass 1's remedy (2) and the only durable one. That is a
   harness change, and it would make this the last PR to hit this.

Do not "fix" it by removing `regressed` by hand. `fold.sh:638` says why: that
clears the label without clearing the regression, and the next tick's
`label_decide()` recomputes it from the same verdict anyway.

## The pad bit is written by the raster, not applied by a reader (2026-09-20, third judgement)

**Correction first, because the previous section got a fact wrong.** It said
`gl/surface.c` is `[lane.swizzle87]`'s and asked for it on #60. **It is this
lane's.** `[lane.swizzle87]` was retired at wave 108 and released the file;
the live board — `origin/board:territory.toml` at the repository **root**,
wave 129 — lists `hw/xbox/nv2a/pgraph/gl/surface.c` as the first entry in
`[lane.remote]`'s `files`. The in-tree `docs/testing/territory.toml` is at
wave **94** and is 35 waves stale; I read it instead of the board. The ask on
#60 is withdrawn — nothing was blocked.

(`gl/shaders.c` moved the other way and is **not** this lane's on the live
board. The reverted `9e9da01d` touched it; `aa3648cb` restores it
byte-identically, so the net diff does not, the same shape as #62's
`d7ef9820`.)

### The measurement

`5df42da3` put the rule where the last section said it belonged — the surface
download writes `(X << 7) | (host >> 1)`, the upload reads back
`expand7(guest & 0x7F)`. Registered at
`docs/testing/predictions/2026-09-20-gl-x1a7-download.json`. **Four of five
legs held, two of them exactly:**

| capture | a (post-blit-fix) | measured | registered |
|---|---:|---:|---|
| `DstAlpha_XA_O1A7RGB8` | 81,920 | **16,384** | 16,384 ✔ exact |
| `1-DstAlpha_XA_Z1A7RGB8` | 65,536 | **16,384** | 16,384 ✔ exact |
| `1-DstAlpha_XA_O1A7RGB8` | 81,920 | **32,768** | 16,384 *or* 32,768 ✔ |
| `DstAlpha_XA_Z1A7RGB8` | 65,536 | **16,384** | 16,384 *or* 32,768 ✔ |
| `Fmt_X1A7R8G8B8_Z1A7R8G8B8` | 32,774 | **6,311** | must improve ✔ |
| `Fmt_X1A7R8G8B8_O1A7R8G8B8` | 16,414 | **122,552** | must improve ✘ **KILL** |

The fifth leg said *"both strictly improve. FAILS IF either grows."* It grew
sevenfold, so the change is reverted in `ad5f43b6`. **An aggregate cannot
license a capture that gets seven times worse**, which is exactly why that
condition was registered before the run rather than judged after it.

### Where the regression is, and what it says

Not diffuse: **59,025 px of it are the frame's background**, golden
`[32,32,32,255]`, which we produced correctly before and now produce as
`[16,16,16,191]` — a half-opaque composite. Host alpha is `0` there and the
`_O` rule turns `0` into `0x80`.

On the **drawn swatch** the same rule is right: golden `[240,207,15,255]`,
matched before and after, while the `_Z` twin's golden is `[120,103,7,191]`
and this change makes `_Z`'s alpha histogram **byte-identical to its golden**
— `255 ×271205, 191 ×17081, 0 ×3288, 192 ×1116` — with exactly **one** pixel
newly wrong.

### The rival, measured on the same instrument

The same code with the pad bit forced to zero for both suffixes:

| capture | a (post-blit-fix) | pad bit | no pad |
|---|---:|---:|---:|
| `1-DstAlpha_XA_O1A7RGB8` | 81,920 | **32,768** | 81,920 |
| `1-DstAlpha_XA_Z1A7RGB8` | 65,536 | **16,384** | **16,384** |
| `DstAlpha_XA_O1A7RGB8` | 81,920 | **16,384** | 81,920 |
| `DstAlpha_XA_Z1A7RGB8` | 65,536 | **16,384** | **16,384** |
| `Fmt_X1A7R8G8B8_O1A7R8G8B8` | 16,414 | 122,552 | 32,799 |
| `Fmt_X1A7R8G8B8_Z1A7R8G8B8` | 32,774 | **6,311** | **6,311** |
| ten `A7` total | 449,850 | 316,533 | 341,468 |

So the pad bit is **necessary** for Blend surface's `_O` pair — without it
they do not move at all — and **harmful** on Surface format's `_O`
background. Both variants regress that capture, so neither ships.

### The conclusion, and it is a design statement rather than a hypothesis

> **HALF OF THIS IS WITHDRAWN — see “A CLEAR writes the pad bit too”
> at the end of this file (2026-09-20, fourth judgement).** The word
> *raster* is too narrow by 98,208 pixels of 98,304: `NV097_CLEAR_SURFACE`
> writes the pad bit as well, and a design that gates on draw coverage
> alone is worse than one that gates on nothing. The rest of the section
> stands.

**The pad bit is not a property of the memory that a reader applies. It is
written by the raster, per pixel, and is absent where the raster never
wrote.** Blend surface draws two full-surface quads so every pixel carries
it; Surface format has a background the raster never touched, and forcing `X`
there is what breaks it. A download cannot tell those apart — it sees only
bytes — so **the pad bit belongs on the write side**, and that is the same
reason one stored byte cannot answer both the blend's read and the texture
unit's read under identity.

What is not in doubt: **the 7-bit quantisation itself.** `_Z` 32,774 → 6,311,
alpha exact, one pixel newly wrong. It is reverted only because it cannot be
separated from the question the `_O` pair raises.

### The next step, stated so nobody re-derives it

Carry the guest representation in the host surface's alpha *for pixels the
raster writes* — which only the fragment path can know — and make the
download and upload identity again. That is #59's stamp machinery applied to
a format it currently excludes, and `psh.h`'s exclusion note will need
rewriting rather than deleting: it is right that a `PSH_PAD_ALPHA_ONE`-style
constant would destroy seven real bits, and wrong that nothing else can be
stamped. **The cost to price first** is what the blend then reads as
destination alpha: `(X << 7) | A7` where hardware reads `expand7(A7)`, which
is not an off-by-one — it is roughly a factor of two on `_Z`. Today's
identity costs 14 of 32 modelled halves; that variant's cost is unmeasured
and must be measured before it is built.

## The X1A7 read side is not in the sampler, and one GL-only swatch was never a pad-bit defect (2026-09-20)

Two predictions were registered before the runs and both were judged. One was
falsified and reverted; the other landed exactly. Measured on `iso_surf1`, one
GL run per arm from `01047cf3`, against `/tmp/goldens/results`.

### 1. FALSIFIED: the readback rule does not belong at the texture sample

`docs/testing/predictions/2026-09-20-gl-x1a7-read-side.json` said a per-stage
uniform applying `(X << 7) | (stored >> 1)` at the sample would take the four
`TestDstAlpha` captures from 303,104 px to between 81,920 and 114,688.
**Nothing moved. All ten `A7` captures read their master values to the pixel.**
Implemented in `9e9da01d`, reverted in `aa3648cb`.

The gate was `pgraph_gl_check_surface_to_texture_compatibility()`, and that
function's surface-format switch has cases for four formats — `X1R5G5B5_Z`,
`R5G6B5`, `X8R8G8B8_Z`, `A8R8G8B8` — and **no case for `X1A7R8G8B8_Z` or
`_O`**. Instrumented and counted: **96 X1A7 surface lookups reach the
compatibility call and 96 are refused**, with extents and swizzle matching
every time (128×128 texture format `0x12` against a 128×128 unswizzled
surface). The only surface the shader ever sees through that path is
`A8R8G8B8`. The `_O` twins of the two `_Z` formats that *are* listed are
missing as well; that is a second thing to look at and not this one.

So the sampled texel never comes from the host surface. It comes from guest
VRAM, written there by `surface_download_to_buffer()`'s `glReadPixels`
straight through the format map — `GL_BGRA` / `UNSIGNED_INT_8_8_8_8_REV`, the
full eight bits of host alpha — and read back as an ordinary
`LU_IMAGE_A8R8G8B8` texture.

**`(X << 7) | (stored >> 1)` is not something the texture unit does to a host
image. It is what the raster PUT IN MEMORY.** Its address is the surface
download, with its inverse (`expand7`) on upload. Both are in
`hw/xbox/nv2a/pgraph/gl/surface.c`, which is `[lane.swizzle87]`'s at wave 94,
so it is **asked for and not taken**. The rule itself is unchanged and still
measured twice; only its address was wrong.

Reverted rather than left in place because the code was not merely untested,
it was **unreachable on any content**: nothing can make that switch return
true for `0x06` or `0x07`.

### 2. LANDED: a texture the surface blit filled is not the VRAM it was hashed from

`TextureBinding::data_hash` describes the *guest bytes* a binding was
generated from. `pgraph_gl_render_surface_to_texture()` overwrites the
binding's pixels and does not touch it, so the slow path asks the hash whether
the binding is current and gets a confident wrong answer.

Instrumented at the bind, on `DstAlpha_XA_O1A7RGB8`'s first swatch:

| | |
|---|---|
| recorded `data_hash` | `141e1a7bae3fe174` |
| live VRAM hash | `141e1a7bae3fe174` — genuinely equal |
| `vram[0]` | `00000000` (guest memory is all-zero) |
| `glGetTexImage[0]` | `ffffff22` (an earlier `A8R8G8B8` blit) |
| `binding->draw_time` | `306824`, where every other X1A7 swatch reads `0` |

`TestDstAlpha` points stage 0 at `GetTextureMemoryForStage(0)` with the same
shape in every test, so one cache key is shared between tests whose surface
format takes the fast path and tests whose format does not.

Fixed in `da9e02a2` (`gl/texture.c`): a binding with a nonzero `draw_time`
wanted as a VRAM texture is regenerated regardless of the hash. `draw_time` is
the discriminator rather than a new field because it already means exactly
that — `generate_texture()` sets it to `0` and the s2t branch is its only
writer — and because the early-reuse path at the top of the same loop has
always compared draw_times rather than bytes.

**Measured, against the registered values:**

| | master `01047cf3` | with `da9e02a2` | predicted |
|---|---:|---:|---|
| `Blend_surface::DstAlpha_XA_O1A7RGB8` | 90,112 | **81,920** | 81,920 ✔ |
| the other nine `A7` captures | — | unchanged ✔ | unchanged |
| ten `A7` captures, GL total | 458,042 | **449,850** | 449,850 ✔ |
| those ten, GL vs Vulkan | 16,384 px | **0** ✔ | 0 |
| whole disc | 1 better, 0 worse, 235 same | | no capture worse ✔ |

**One leg did not hold as written.** The file predicted whole-disc GL/Vulkan
byte-identity `227/236 → 228/236`; measured `228/236 → 229/236`. The delta is
right and the baseline figure was wrong — 227 was carried from an earlier note
rather than re-measured, and this run re-measured it. The comparison is PNG
bytes with an RGB-array fallback, over the 236 captures present in both.

**`Surface_pitch::Swizzle` is not a stable capture and must not be used as a
tripwire on this disc.** Two runs of the *same* master binary read 12,224 and
11,132 — 1,092 px apart — and the fixed binary read 12,224 again. That is the
guest/pgraph race #39 and #87 already record, and it was nearly mistaken for a
result: the first fix run was scored against a binary the build had not picked
up, and the only capture that "moved" was this one.

### 3. What the model covers, now checked rather than assumed

`TestDstAlpha` draws **eight** swatches in two rows —
`{0x00,0x40,0x80,0xFF}000000`, then the same four alphas over **red** — and
`x1a7_forward_model.py` models the first row only. The second row must be
identical because the blend is `{sfactor, ZERO}`, so the background RGB is
multiplied by zero and cannot reach the surface. **On the goldens the two rows
are byte-identical on all four captures, 0 of 65,536 px each**, so the model's
32 halves do describe all 64. The earlier "303,104 px" figure rested on this
without saying so.

`R2` can only move **top** halves: the bottom half of each swatch is drawn with
`SetFinalCombiner1Just(SRC_ZERO, true, true)`, alpha forced opaque, so the
sampled alpha does not enter it. The four residual halves at `bg 0x80` are
`R1`'s, off by exactly one (127 vs 126, 128 vs 129).

### 4. What #60 still needs, and from whom

- ~~**`gl/surface.c`** (`[lane.swizzle87]`)~~ **— WRONG, see the section above: the file is this lane's on the live board, and the download is not where the pad bit goes.** The superseded text: apply `(X << 7) | (stored >> 1)` in
  the surface download and `expand7(a >> 1)` on upload, for
  `X1A7R8G8B8_{Z,O}`. That is the read side, byte-exact, and it also fixes a
  guest CPU read of the surface, which no sampler-side approximation can.
- Optionally, in the same file: give `X1A7R8G8B8_{Z,O}` (and the missing `_O`
  twins) cases in `pgraph_gl_check_surface_to_texture_compatibility()`. Only
  *after* the download conversion exists — the fast path bypasses it, so a
  shader-side rule would then be needed too, which is the reverted `9e9da01d`.
- The write side's post-blend quantisation remains the known approximation and
  `XA_*_Add_SrcA_DstA` remains the capture that would settle it.

## X1A7R8G8B8: two rules, and 32 of 32 golden halves (2026-09-20)

Measured at master `151dc059`, `iso_surf1`, one run per renderer on one
binary, 236 captures each, zero assert lines. Reproduce with
`docs/testing/x1a7_forward_model.py /tmp/goldens/results`; its `--selftest`
needs no disc.

| | GL | Vulkan | GL − VK |
|---|---:|---:|---:|
| ten `X1A7` captures, px from golden | **458,042** | **449,850** | **8,192** |

Nine of the ten are byte-identical between the backends. **All but 8,192 px of
this is one shared defect, not a renderer disagreement** — which is why every
single-backend pad fix so far has left it untouched. The whole disc is 227/236
byte-identical GL vs Vulkan, consistent with #158's post-fold figure.

### The model

Two rules, composed through Blend surface's own draw sequence, reproduce
**32 of 32 golden swatch halves exactly, worst |delta| 0**, with no free
parameter:

- **R1 — blend destination alpha.** `Ad8 = (A7 << 1) | (A7 >> 6)`, `A7 = stored >> 1`.
  Bit replication of the seven stored bits, and **the pad bit does not
  participate**: the `_Z` and `_O` goldens are equal on every bottom half.
- **R2 — texture readback.** `sampled8 = (X << 7) | (stored >> 1)`.

**R2 is not new.** `vk/constants.h` measured it on 2026-09-12 over 32,755
invertible px of *Surface format*. This derivation is from *Blend surface*, so
the two are independent and agree. **R1 is new.** That same entry left it open
as *"the other half ... the 7-bit quantisation on the way IN"*; it is now
pinned, and it is bit replication rather than truncation or a constant. Today
both renderers use the identity for R1 and no rule at all for R2.

Sixteen of the thirty-two values are **held out**: the `1-DstAlpha` pair is
scored against the goldens and never written into the pinned table, so a wrong
sign cannot be hidden by a table edited to match the model. Four rivals are
refuted by the same values — today's identity among them — so a pass means the
goldens *selected* these rules rather than merely admitting them.

### What this refutes, including the hypothesis it started from

#59/#158 built a write-side stamp that **can** requantise, and the verdict
calling this unimplementable (*"needs the stored alpha requantised to 7 bits,
not a component swizzle"*, `a34d28c4`, 09-12) predates that stamp by one day
(`4381fae5`, 09-13; dual-source output `52411a03`, 09-14). So the obvious move
is to add `X1A7` to the stamp's table. **Measured: that does not work.**
Storing `(X << 7) | (a >> 1)` and reading by identity — the shape the stamp
gives — gets R1 wrong on **six of eight** cases, because R1 and R2 want
different functions of the same seven bits and one stored byte cannot answer
both by identity. **`psh.h`'s exclusion of `X1A7` from the pad table was
right**, and the next lane should not undo it.

What does work, checked exhaustively over all 128 seven-bit values: store
`expand7(a >> 1)` — lossless, 128 distinct values, `expand7(v) >> 1 == v` — so
R1 is correct by identity at the blend, and apply `(X << 7) | (stored >> 1)` at
the texture read. Identity is the *point* on the blend side: a fixed-function
blend unit's destination-alpha read cannot be intercepted from a shader, so the
only place to put R1 is the stored bytes.

### WITHDRAWN: "the proposed fix, simulated at 0 of 32" (audit pass 1, M1)

This section claimed `--proposed` simulated the implementation through the
test's draw sequence and scored **0 of 32**. **That claim carried no
information and is withdrawn.** The mode computed the *same function* as the
default: the write transform `expand7(a >> 1)` is `r1_blend_dst_alpha`
character for character, and the swatch alpha `0x22` is its fixed point, so
both substitutions collapsed. Verified identical on all **1,024** inputs. It
was this model scoring itself. The mode is removed; `--selftest` now *proves*
the coincidence instead of asserting it.

**What survives is worth more than the claim was.** On *TestDstAlpha* the
proposed implementation and this model are indistinguishable, so **these four
captures cannot validate the implementation at all.** Only a capture where
alpha blending is live can — that is exactly where hardware quantises after
the blend and fixed-function cannot. **`XA_*_Add_SrcA_DstA` (43,328 px each)
is the capture that would settle it**, and it is one of the six this model
never covered.

**Predicted yield, and now stated with its real support: the four
`DstAlpha`/`1-DstAlpha` captures go to 0, which is 303,104 px** (81,920 +
65,536 + 90,112 + 65,536), less whatever the GL-only anomaly below holds back
on `DstAlpha_XA_O1A7RGB8`. That rests on the model fitting 32 of 32 goldens
plus the assumption that R1 and R2 implemented correctly produce the modelled
values — **not** on a simulation, because there was none.

**The other six X1A7 captures — 154,938 px — are NOT modelled and nothing here
predicts them.** `XA_*_Add_SrcA_DstA` (43,328 each) is where the known
approximation should bite: hardware quantises *after* the blend and
fixed-function cannot, so the shader gives `expand7(As >> 1) * Fs + Ad * Fd`
where hardware gives `expand7((As * Fs + Ad * Fd) >> 1)`. In `TestDstAlpha`
that costs nothing — `write_transform(0x22) == 0x22`, and the surface is
sampled afterwards rather than blended into again — which is luck, not a
property of the fix, and the `Add_SrcA` pair has no such luck.

Blast radius: exactly **ten** of the disc's 236 captures name `A7`, and the
transform is keyed on the target surface format, so the other 226 must not
move. That is the control to register.

### Still unexplained, and it is the GL-only 8,192 px

`Blend_surface::DstAlpha_XA_O1A7RGB8` is the one capture where the backends
differ, and the whole 8,192 px is the **first swatch, background alpha `0x00`**.

The sharpest statement of it: **GL's `0x00` swatch is byte-identical to both of
its `0xFF` swatches** (indices 3 and 7), and the goldens distinguish them. So
GL renders that swatch as if the background alpha had been `0xFF`. Across the
suite's eight `DstAlpha_*` captures this collapse happens in GL *and* Vulkan
*and* the golden for every format with no real alpha (`R5G6B5`, `X_O1RGB5`,
`X_ORGB8`, `X_Z1RGB5`, `X_ZRGB8`) — correct, since the background alpha cannot
matter there. **`XA_O1A7RGB8` is the only capture where GL collapses and the
golden does not.** `ARGB8` and the `_Z` twin are right on GL.

Ruled out, each by reading master rather than by argument:

- **Not the format table.** `X1A7R8G8B8_Z` and `_O` share one byte-identical
  row in `kelvin_surface_color_format_gl_map` (`gl/constants.h:403/405`), so
  nothing downstream of the table can tell them apart.
- **Not the `Ad = 1` fold.** `surface_color_format_dst_alpha_is_one()`
  (`gl/draw.c:117`) excludes `X1A7` on both backends, and GL gets `0x40` and
  `0x80` right, which a blanket fold could not.
- **Not the clear.** `pgraph_get_clear_color()` is **shared** between the
  renderers (`pgraph.c:4599`) and treats `_Z` and `_O` identically —
  `((clear_color >> 24) & 0x7F) / 127.0f` for both. This was the strongest
  hypothesis, by analogy with #89's `77bd2977`, which fixed the clear's pad
  alpha on Vulkan only; the shared helper refutes it.
- **Not #158's stamp.** `pgraph_glsl_surface_pad_alpha_mode()` returns
  `PSH_PAD_ALPHA_NONE` for both `X1A7` suffixes, so no stamp is emitted.

- **Not the blend-side stamp gate.** `gl/draw.c:468` computes `pad_stamped`
  from `pgraph_glsl_surface_pad_alpha_mode(...) != PSH_PAD_ALPHA_NONE` — the
  *same expression* `psh.c` stages the uniform from, so the shader and the
  blend state cannot disagree about which draws stamp. For `X1A7` both say no.
- **Not the guest.** `TextureFormatForSurfaceFormat()`
  (`pbkitplusplus/src/texture_format.cpp:102`) maps `X1A7R8G8B8_Z` and `_O` to
  **the same** texture format, `SZ_A8R8G8B8`, in one fallthrough group. The
  disc does not distinguish them either.

### And that is the finding: the format cannot be the cause

Enumerate every site outside `vk/` that names either suffix:

```
grep -rn "X1A7R8G8B8_[ZO]" hw/ | grep -v /vk/
```

**11 lines, in six groups** (audit L4: the command as first written here
omitted the `grep -v /vk/` and said "exactly six", conflating groups with
lines — 19 lines with `vk/`, 11 without). None of the six separates the two
suffixes:

| site | what it is |
|---|---|
| `gl/surface.c:3059`, `gl/renderer.h:350` | comments |
| `gl/constants.h:403`, `:405` | two rows, byte-identical |
| `pgraph.c:4620-4621`, `:4658-4659` | both suffixes as **adjacent fallthrough cases** |
| `pgraph.c:4664` | a comment — the eleventh line, and why 11 ≠ 6 |
| `nv2a_regs.h:973-974` | the enum values, `0x06` and `0x07` |

**No code on the GL path treats `_Z` differently from `_O`.** So a difference
in GL's output between the two cannot be caused by the format, and every
format-shaped hypothesis is dead on arrival — which is what the four above
have in common. What remains is **state carried into the test**: the two
captures differ in when they run and in what the surface at that address held
beforehand, and the `_O` test is where it lands rather than what causes it.

Corroborating, and the reason not to call this an `_O` defect: only **one of
the ten** `X1A7` captures diverges between the backends. `1-DstAlpha_XA_O1A7RGB8`
has a first swatch at background alpha `0x00` too, same format, and GL matches
Vulkan there exactly.

### The ordering, measured — and the obvious ordering hypothesis is also wrong

`pgraph_progress_log.txt` ships in every capture run and gives the execution
order for nothing. The suite runs alphabetically, 32 tests:

| # | test | GL vs golden |
|---|---|---|
| 12 | `DstAlpha_R5G6B5` | fine |
| **13** | **`DstAlpha_XA_O1A7RGB8`** | **the anomaly** |
| 14 | `DstAlpha_XA_Z1A7RGB8` | fine |

So the broken test is immediately preceded by `R5G6B5` — the one format in the
suite whose host surface (`GL_RGB565`) has **no alpha component at all**, and
the format `surface_color_format_dst_alpha_is_one()` names as its control. A
binding surviving that switch would read destination alpha as 1.0 exactly as
observed, and the `_Z` twin at 14 is preceded by `X1A7` rather than by
`R5G6B5`, which would explain why it is clean.

**It does not hold.** `1-DstAlpha_XA_O1A7RGB8` is test 3, immediately preceded
by `1-DstAlpha_R5G6B5` at 2 — the same predecessor, the same format, the same
first swatch at background alpha `0x00` — and GL matches Vulkan there exactly.
With the sfactor `1 - DST_ALPHA`, a destination alpha wrongly read as 1 would
paint black where the golden is white (`0xFF` at bg `0x00`, from the model), so
the capture would have diverged loudly. It did not.

So "preceded by a format with no host alpha" is **not sufficient**, and that is
the fifth hypothesis this anomaly has killed. Whatever distinguishes test 13
from test 3 is not the format, not the predecessor's format, and not the
blend factor alone.

Next step for whoever takes it: the state is real but its trigger is not yet
named. Vary the ordering directly — a disc carrying only `Blend surface`, or
only tests 12 and 13 — and see whether the anomaly survives isolation. Do not
start from the format tables or from the predecessor's format; both are
exhausted above. A capture run here is 44 s under GL, so this is cheap.

## #60: the fix landed while the issue stayed open

`a105a51a` — *"a reused surface binding now refreshes its guest format"* — is in
master and carries the `drawn_format` refresh on the `is_compatible` branch of
`update_surface_part()`. **This lane's branch never carried it**: it was one of
the fifteen campaign-branch commits in `gl/*.c` that were never in this branch,
so every measurement this lane published about #60 predates the fix it was
measuring.

What this lane did measure, on its own tree without the refresh, was that
applying it regressed exactly one capture:

| capture | without refresh | with refresh (this lane, 09-13) |
|---|---:|---:|
| `Blend_surface::DstAlpha_XA_O1A7RGB8` | 81,920 | 90,112 |

and attributed those 8,192 px to **#59's pad-alpha semantics** — a surface
rendered while the guest called it a pad format, then sampled as one where
alpha is meaningful, so the raster's raw alpha shows through where hardware
reads the pad as zero.

**#59's write side has since landed in master** (`e761ee31`, with
`dualSrcBlend` enabled in `vk/instance.c` and `surface_sampled_pad_alpha` in
`vk/draw.c`). So the named cause of the regression is gone, and the
combination has never been measured: the refresh and the pad-alpha write side
are both in master and no run of this disc has been taken since.

### Registered before measuring

**Prediction.** On master, `Blend_surface::DstAlpha_XA_O1A7RGB8` reads
**81,920** under OpenGL — the pre-refresh value — because the 8,192 px the
refresh exposed were the pad-alpha defect and that defect is now fixed at its
source.

**Kill conditions, as numbers.**

1. **90,112** means the regression is live in master: the refresh is landed,
   the pad-alpha fix did not reach this path, and #60 is a live regression
   rather than a closable issue. That is the uncomfortable outcome and it is
   the more useful one.
2. Any third value means neither model is right and both get withdrawn.
3. The three captures this lane measured as recovering under #71's filter fix —
   `ARGB8_Add_SrcA_1-SrcA` 9,547, `ARGB8_Add_SrcA_DstA` 11,521 — must still
   read those values. If they moved, something else landed in this path and the
   comparison is confounded.
4. `Surface_pitch::Swizzle` is exempt: it is the guest/pgraph race (#44/#39)
   and moves within 13,160–15,360 on GL regardless.

**Not predicted:** Vulkan's values. The refresh is GL-only, so Vulkan is a
control for everything except the pad-alpha change, which moves both.

## Result: the prediction is REFUTED, kill condition 1 fired

Binary built from `master` at `415dcc69`; `iso_surf1`, one run per renderer,
236 captures each, zero assert lines.

| capture | GL | Vulkan | registered as |
|---|---:|---:|---|
| `Blend_surface::DstAlpha_XA_O1A7RGB8` | **90,112** | **81,920** | 81,920 predicted; **90,112 was kill condition 1** |
| `Blend_surface::ARGB8_Add_SrcA_1-SrcA` | 9,547 | 9,547 | control, held |
| `Blend_surface::ARGB8_Add_SrcA_DstA` | 11,521 | 11,521 | control, held |

**The regression is live in master, and it is GL-only.** Both controls hold at
the values registered before the run, so the comparison is not confounded, and
Vulkan reads the pre-refresh value on the same binary and the same disc.

### Why the prediction was wrong, precisely

It assumed #59's landed write side reaches both backends. It does not, and the
tree says so in its own words:

- `glsl/psh.c:225` — *"The GL renderer never calls the setter, so it keeps
  false and generates exactly the GLSL it generates today."* `g_dual_src_pad_supported`
  is a device property, and #59's write side is gated on `dualSrcBlend`, which
  `vk/instance.c` enables and the GL renderer never does.
- `gl/renderer.h:361` — *"GL has no host_fmt"*, so GL has no
  `sampled_pad_alpha` column at all; the Vulkan readback override lives in
  `kelvin_surface_color_format_vk_map`.

So the mechanism I named on 2026-09-13 was right and the remedy never reached
this backend. **#59's write side is Vulkan-only by construction.**

### What moved, measured rather than inferred

GL and Vulkan disagree on exactly **16,384 px**, one 128×128 region at
x[32..159] y[92..219]:

| | first half (8,192 px) | second half (8,192 px) |
|---|---|---|
| golden | `#2A2A2ABF` | `#000000FF` |
| Vulkan | `#555555FF` | `#000000FF` — **matches** |
| GL | `#6C6C6CE2` | `#FFFFFFFF` — **destination alpha read as one** |

GL differs from the golden on all 16,384; Vulkan on 8,192. The extra 8,192 is
exactly the half where the golden is black and GL paints white — the
destination-alpha-goes-to-one signature this lane described in September and
could not then attribute.

Worth noting against `psh.c:205`: the pad-alpha table has **no override for
`X1A7R8G8B8_{Z,O}`**, *"whose readback is not a constant"*, and this capture is
exactly that format. So this is not a missing table row; it is the case the
table deliberately excludes.

### Disposition

**#60's own fix is correct and landed.** `gl/draw.c:351` still reads the
guest-declared `pg->surface_shape.color_format` for the blend-side fold, which
is right, and the refresh repairs the surface-to-texture decisions that were
being made on a stale format. The 8,192 px it exposes are **#59's GL half**,
not #60's defect: the refresh made the decision correct, and a correct decision
reaches a path GL has never had the fix for.

That is the same shape as the question the board is already holding on #88 —
ship a correction that exposes a pre-existing defect, or hold it — with one
difference: here the correction is **already shipped** in master, so the choice
is only whether the exposed 8,192 px are chased or recorded.

## The finding #60 opened up: GL and Vulkan have diverged, 413,790 px (#158)

The same pair of runs answers a larger question than #60's. Comparing the two
renderers capture by capture on one binary, GL now trails Vulkan on **eleven**
captures. Against this lane's own September runs, still on disk:

**GL-behind total on those eleven: 4,608 px in September → 413,790 px now.** In
September the two renderers were byte-identical on ten of the eleven, the
eleventh differing only by the guest/pgraph race. Nothing regressed in absolute
terms; GL improved on several. Vulkan pulled away.

Every capture but `Surface_pitch::Swizzle` is a pad format — `X_O`, `X_Z`,
`X1R5G5B5_{Z,O}`, `X8R8G8B8_{Z,O}`, `X1A7R8G8B8_O`. One family.

The cause is structural rather than an oversight: #59's only landed code change
(`77bd2977`) touches `vk/draw.c` and no GL file; the readback override is a
column of a **vk** format table that `gl/renderer.h:361` says cannot exist on
this backend; and the write side is gated on a device feature `psh.c:225`
records the GL renderer as never enabling. Each decision was locally reasonable.
The aggregate is what nobody had measured.

`Swizzle` is the same shape from another lane: Vulkan is byte-exact at 0 where
it was 10,240, so #87's Morton fix reached `vk/texture.c`, and GL sits at
12,224 — worth confirming the GL half landed, since that lane held both files
as one claim for exactly this reason.

**The consequence worth more than the pixel count:** *"both renderers agree, so
the cause is upstream of both"* is no longer safe on this family. This lane used
that inference in #87 and was right to; on the pad formats the premise has
quietly expired, and nothing in the tooling flags it.

Filed as #158 rather than started: the fix crosses into #59's model, so it is a
routing question. The target is registered per capture if it comes back here.

## #158 implemented and measured: 9 of 9, and the Vulkan control held

Territory released #158 to this lane at wave 122, with `glsl/psh.c`,
`gl/renderer.c` and `gl/draw.c` — the three files the patch-shape analysis had
named. Implemented as that analysis specified, and **without** the constants-
table column it warned against.

Prediction registered before the run
(`docs/testing/predictions/2026-09-19-gl-pad-bit-write-side.json`), naming nine
targets at Vulkan's values, two captures pinned as **not** moving, and the
uncomfortable outcome in advance.

| capture | GL before | GL after | registered | verdict |
|---|---:|---:|---:|---|
| `1-DstAlpha_X_O1RGB5` | 65,536 | **0** | 0 | pass |
| `1-DstAlpha_X_ORGB8` | 65,536 | **0** | 0 | pass |
| `DstAlpha_X_O1RGB5` | 65,536 | **0** | 0 | pass |
| `DstAlpha_X_ORGB8` | 65,536 | **0** | 0 | pass |
| `DstAlpha_X_ZRGB8` | 65,536 | **0** | 0 | pass |
| `Fmt_X8R8G8B8_Z8R8G8B8` | 32,774 | **31** | 31 | pass |
| `Fmt_X8R8G8B8_O8R8G8B8` | 16,413 | **62** | 62 | pass |
| `Fmt_X1R5G5B5_Z1R5G5B5` | 30,197 | **15,678** | 15,678 | pass |
| `Fmt_X1R5G5B5_O1R5G5B5` | 18,564 | **16,483** | 16,483 | pass |
| `DstAlpha_XA_O1A7RGB8` | 90,112 | **90,112** | 90,112 (pinned) | pass |

**Nine moved, and exactly the nine predicted. Nothing else on the disc moved at
all** — 227 of 236 captures byte-identical to the pre-fix run, 0 worse.
**393,374 px recovered.**

### The control that makes this readable

`glsl/psh.c` is shared, so Vulkan is not automatically a control — but the gate
change is algebraically a no-op there (`opts.vulkan && flag` becomes
`flag && !gles`, and for Vulkan `gles` is false), and the measurement confirms
it: **Vulkan is byte-identical on all 236 captures.** A shared-file change that
moves one backend and provably not the other is the strongest form this
evidence takes.

GL's bit-exact count goes **123 → 128, which is Vulkan's exactly.**

### Where the renderers now stand

Differing captures between the two backends: **18 → 9**, and GL now *leads* on
six of the nine. GL trails on exactly two, and both are the captures registered
in advance as unreachable by this change:

- `Surface_pitch::Swizzle` (12,224) — not a pad capture; #87's layout question
  plus the guest/pgraph race.
- `Blend_surface::DstAlpha_XA_O1A7RGB8` (8,192) — `X1A7R8G8B8_O`, whose seven
  alpha bits are real data, excluded by design on both backends. This is #60's
  residual and it is now the *only* pad-family capture where GL trails.

12,224 + 8,192 = 20,416, and 413,790 − 393,374 = 20,416. The arithmetic closes.

### One correction to my own figure

The #158 analysis and its issue comment said the yield would be "~397,000 px".
The exact derived figure was **393,374** — the sum of the nine gaps — and I
rounded it upward in prose while the registered *values* were exact. The
registration is what was measured against; the prose estimate was loose and is
corrected here.

## #60's residual, characterised after #158 landed

`Blend_surface::DstAlpha_XA_O1A7RGB8` is now the **only** pad-family capture
where GL trails Vulkan. #158 did not touch it and was registered in advance not
to: `X1A7R8G8B8_O` returns `PSH_PAD_ALPHA_NONE`, so `pad_stamped` is false and
`gl/draw.c` takes its unchanged path. The capture read 90,112 before and after,
which is the pin holding.

**Both backends are far from the golden, and that is the larger half.** GL is
90,112 px from it and Vulkan 81,920. The 8,192 between them is the part that
belongs to this renderer; the ~82,000 they share is a model question about this
format and is not GL's to answer alone.

Where the two renderers differ, one 128×128 region at x[32..159] y[92..219],
16,384 px:

| | 8,192 px | the other 8,192 px |
|---|---|---|
| golden | `#000000FF` | `#2A2A2ABF` |
| Vulkan | `#000000FF` — **exact** | `#555555FF` |
| GL | `#FFFFFFFF` | `#6C6C6CE2` |

GL matches the golden on **0** of the 16,384; Vulkan on 8,192. So the whole
GL-minus-Vulkan gap is the half where hardware writes black and GL writes white
— destination alpha read as one, the signature this lane first described on
09-13.

**The structural finding, which is stronger than the pixel count.** Four
colours the golden holds appear **nowhere in our frame on either backend**:
`#2A2A2A`, `#4A4A4A`, `#818181`, `#B6B6B6`. Those are blend *results*, not
quantisation neighbours. A rounding or precision difference cannot produce a
frame that is missing four output values entirely; this is an equation or an
operand that is wrong, not a value that is slightly off.

Note also GL's alpha on the second row: `0xE2`, against the golden's `0xBF` and
Vulkan's `0xFF`. GL is producing a *varying* alpha where Vulkan produces a
constant — so the two backends disagree about what the alpha channel even
carries here, which is exactly what one would expect on the one format whose
seven alpha bits are real data and whose pad bit is not.

**Not this lane's to fix alone.** The remaining question is what
`X1A7R8G8B8_{Z,O}` should read back and blend with, which is #48/#59's model
and the one case both of their tables exclude by construction. Recorded so the
next actor starts from the measurement rather than from the pixel total.

---

## 2026-09-19, later: the environment report, and two things it turned up

The host asked five questions about this container, on the grounds that only
this session can see the answers and that one of them decides whether a second
desktop GL channel retires. The full reply is on PR #162. Two findings from
writing it are worth keeping here, because both correct something that was
being assumed rather than checked.

### The capture runner is now in the repo, and it reproduces its own history

`extract_results.py` was in the repo; its driver was not. A capture run could
therefore only be reproduced by someone who already had a container it had been
run in -- the same defect as a number nobody can re-run, applied to the
instrument instead of the result. `docs/testing/pgraph_capture_run.sh` is that
driver.

Writing it down found two bugs that the scratchpad original had carried
silently, both of which fail as *"the run produced nothing"* when the run was
fine:

* It `cd`s into the binary's directory, so a **relative** binary or disc path
  resolved against the wrong directory. Every call site had passed absolute
  paths, so it had never fired.
* The results directory on E: is a property of the **disc**, not the harness.
  `extract_results.py` defaults to `nxdk_pgraph_tests`; `iso_surf1.iso` writes
  to **`surf1`**. That fourth argument was passed by hand at every call site
  and written down nowhere, so it would have died with the container.
  The script now looks instead of guessing, and names what it found.

**Proof it is the same instrument, not a rewrite of it.** A fresh run through
the committed script -- relative path, no directory argument -- against
`p158gl`, produced four hours earlier by the scratchpad runner on the same
binary, same disc, same renderer:

    236 captures both; byte-identical on 235 of 236

The single mover is `Surface_pitch::Swizzle`, which is the texture-memory race
#71 established and #87 tracks. So the committed runner reproduces the
scratchpad runner exactly, and the run-to-run instability on this disc is still
exactly one capture wide -- an independent re-confirmation of #71 that cost
nothing, since the control was needed anyway.

### The goldens on this container are silicon, not a handheld

`lane.desktopchannel`'s `desktop_channel.sh` declines to score any desktop
capture against goldens, and `docs/lanes/desktopchannel/NOTES.md:249` gives the
reason: *"those goldens came off an Adreno running Vulkan."* On that premise
the refusal is right -- a desktop GL capture differing from another emulator's
output is evidence about renderers before it is evidence about xemu.

**On this container the premise does not hold.** `/tmp/goldens` is a git clone
of `abaire/nxdk_pgraph_tests_golden_results` at `6e159f1`, whose README reads:

> Output of [abaire/nxdk_pgraph_tests](...) on **XBOX 1.0 hardware**.

Those are real silicon captures -- the target, not a second emulator. Scoring
any renderer on any host against them is the accuracy question this campaign
exists to ask.

I cannot read that lane's disk, so I am not claiming their tree is this tree.
The check is one command -- `git -C <goldens> remote -v` -- and the layout is a
tell: `<root>/results/<Suite>/<capture>.png` with `perceptualdiff/` beside
`results/` is this repository's shape. If it matches, that lane's most
cautious sentence is its most interesting result: *"the capture produced here
is bit-identical to its handheld golden"* would read **bit-identical to
hardware**.

**What survives either way, and what this lane must not over-read.** A
software rasteriser and a GPU can both be correct xemu and still differ in the
last bit on filtered or interpolated output, so an **absolute** bit-exact count
is a property of the host as well as of the code. "GL bit-exact 123 -> 128" is
therefore a statement about this container. What is immune to all of it is
every number #158 actually rests on: GL-before against GL-after, and GL against
Vulkan, same binary, same disc, same host. Those are deltas on one machine, and
the host's rasteriser cancels.

---

## Audit pass 1 on PR #162: what was taken, and the one finding that could not be

`job.cloud` returned **1 HIGH, 1 MEDIUM, 4 LOW** on `44b35be1`. It is a good
audit — it confirms the mechanism, the gating, the format coverage and the
control argument, so none of that needs re-deriving, and the two findings that
matter are both real.

### H1, taken — and the audit's cheaper alternative does not work

`GL_SRC1_ALPHA` and `GL_ONE_MINUS_SRC1_ALPHA` are not GLES tokens, and
`pad_write_color_factor()` named them outside any guard, so **the arm64-v8a
build did not compile**. Dead code still has to parse. The runtime exclusion
had landed in `gl/renderer.c` and in both `psh.c` gates; the compile-time one
had landed nowhere.

**I shipped this and reported the head as green.** The desktop build *was*
green and `preflight.sh` *was* green end to end — both true, and neither builds
for Android. I had also just written in the environment report that Desktop
build was green on this head, which was accurate and incomplete: I tried to
read the check runs, the tools I have did not expose them, and I moved on
instead of going after the Actions API. The green I could see is not the green
that matters.

The audit offers two forms and says either is fine: guard the branch, *or*
"make `pad_stamped` `false` under `#ifdef __ANDROID__` before the `if`". **The
second does not work** — a compile-time-false `bool` does not stop
`pad_write_color_factor(...)` inside the branch from having to be parsed, and
under the guard that function does not exist. Guarding the whole branch is the
only one of the two that compiles. Worth recording, because taking a correct
finding's incorrect remedy on trust is a way to be wrong while doing as you
were told.

Verified two ways, neither of them the desktop build alone, since the desktop
build was already green while Android was red:

* **Mechanically** — stripping the `__ANDROID__`-false branches leaves **zero**
  code references to the SRC1 tokens, while the desktop side still names them
  at the two lines that should.
* **Behaviourally** — a full disc run on desktop OpenGL, before and after,
  **byte-identical on 235 of 236**, the single mover being
  `Surface_pitch::Swizzle`, the race #71 established. A compile-only fix has to
  move no pixel, and it moves none.

The check that actually closes H1 is the Android job going green, and that is
CI's to make: **there is no NDK in this container.**

### M1, NOT taken, and it is a measurement limit rather than a judgement call

#59's write side has two halves and I ported one. `vk/draw.c:894-907` overrides
the clear colour's alpha per pad mode; the GL clear calls the shared
`pgraph_get_clear_color()` raw, whose alpha switch has no case for the four pad
formats and falls to `default: *a = 1.0f`. So as of `7ffcd2bc` a GL
`X8R8G8B8_Z8R8G8B8` surface holds alpha **0 where the raster drew** and **1
where the clear wrote**. Hardware holds 0 in both. That internal inconsistency
is new, even though no individual pixel moved away from hardware — which is
why the audit rated it MEDIUM and why the result table cannot show it.

The audit's option (a) is to take the fix *with a prediction registered first*,
bound by `Clear::SCF_X8R8G8B8_Z8R8G8B8` and `Clear::SCF_X1R5G5B5_Z1R5G5B5`, and
warns that taking it **without** one is the thing to avoid.

**I cannot register that prediction, because the Clear suite is not on this
disc.** `iso_surf1.iso` carries fourteen suites — Blend_surface,
Color_Zeta_Disable, Color_mask_blend, Color_zeta_overlap, Image_blit,
Null_surface, Surface_clip, Surface_format, Surface_pitch,
Texture_Framebuffer_Blit, Texture_format, Texture_perspective,
Texture_perspective_enable, Texture_render_target — and **no `Clear`**. A disc
that has it would have to be built with nxdk, which this container does not
have (environment report, question 2). So option (a) is not "harder here", it
is unavailable: I would be shipping a four-line behavioural change to a path I
have no way to observe, which is the same defect as a number nobody can re-run.

Taken as option (b), but with the work specified rather than merely declined:
the omission is named in the PR body beside the `sampled_pad_alpha` one, the
captures it leaves wrong are named, and the fix is filed as its own issue with
the call site, the Vulkan function to mirror and the two prediction keys, so
whoever holds a disc with the Clear suite can take it without re-deriving any
of this.

### L2, taken with the correction it points at

The `GL_SRC_ALPHA_SATURATE` comment had reverted to the argument-from-absence
that `vk/draw.c`'s own pass-1 audit retired as *its* L2. It now carries the
derivation instead — `min(As, 1 - Ad)` is 0 for **both** pad variants once the
stamp lands, so nothing needs substituting whatever a disc contains — with the
corpus observation kept as the secondary note it is there. A wrong comment on
right code is believed, which is the whole reason that finding is worth making
twice.

### L1, taken. L3, taken as prose. L4, noted and not acted on.

**L3** is right: the prediction's prose named `Surface_pitch::Swizzle` in a
kill condition and no leg bound it, so half of a stated kill condition could
not have fired. The reason it was unbound is good — Swizzle's GL value is not
stable run to run, moving within 13,160–15,360, so a machine leg on it would
fire on the race rather than on the change — and today's two control runs put
the same number on it again from a third and fourth direction.

**I am not editing the registered artifact to fix this.** That prediction has
already been measured and its sha256 is cited in the PR body; rewriting it now
would make the hash in the record disagree with the file, and retrofitting a
leg onto a spent prediction is exactly the move the whole registration
discipline exists to prevent. The honest form is the one the audit offers as
its alternative — say it in prose — so: **`Surface_pitch::Swizzle` was excluded
from the machine legs deliberately, because its GL value is not stable run to
run; the kill condition on it was a manual check, and it was made.**

**L4** — the index provenance now records `/home/user/…` where the sweep host
writes `/home/justin/…`, and will flip back next time it is regenerated there.
Nothing reads it; `cmd_check()` compares `symbols`, `sites` and `suites`, and
the gate reads `tests_commit`, which is unchanged. It is churn, and the field
wants to be relative or dropped rather than an absolute path from whichever
machine last built it. Not this PR's to change.

## Audit pass 2 on PR #162: both MEDIUMs were in the instruments, not the renderer

Pass 2 closed all six pass-1 scenarios and did not reopen `hw/`. Its two new
findings (N1, N2) were both in tooling added *after* pass 1 read the diff, and
both were the same defect wearing different clothes: **an instrument that
states a guarantee in prose and does not implement it.** That is the failure
mode this repository has paid for most often, so the remediation is not just
the fix -- it is a fixture per invariant, and a mutant per fixture.

### N1 -- `gles_token_check.py` hid the `#else` arm of every conditional it did not understand

The frame stack inverted `live` on `#else` even for a frame whose condition was
unknown-and-assumed-live, so that arm was marked dead and never scanned. The
docstring promised the exact opposite in as many words: it "can report a line
some other guard excludes, **never hide one**."

Fixed by recording per frame whether `__ANDROID__` decided it and inverting on
`#else` only for those; an unknown condition now leaves both arms live.

Verified rather than asserted:

* `--selftest` is **9/9**, and against a scratch copy with the one-line fix
  removed the N1 fixture **FAILS and the other eight are unmoved** -- so it
  catches that defect and is specific to it.
* The two lines pass 2 named as invisible are now scanned: `gl/debug.c:67-68`
  (the `glEnable(GL_DEBUG_OUTPUT)` arm of `#if defined(__APPLE__)`) and
  `gl/debug.h:55-61` (the macro arm of `#if DEBUG_NV2A_GL`). Both are what an
  Android build compiles. 7,341 non-blank lines are visible on the default
  target now.
* The check has not lost power: `gl/draw.c` at `7ffcd2bc` still reports
  **:151 and :153**, the two lines by number that the arm64-v8a compiler
  reported, and `hw/xbox/nv2a/pgraph/gl` is still `13 files scanned, 0
  findings` -- which is the regression guard on a fix that makes *more* code
  visible.

**The `#elif` half had no failing case, and now does.** Pass 2's remediation
note asked for `#elif` to stop the following `#else` inverting a value that was
never derived; the fix does that, but nothing exercised it, and an invariant
with no failing case has not been tested. Fixture
`else-after-elif-on-an-android-frame` added. Against a mutant that drops the
`decided = False` on `#elif`, that fixture alone goes red -- verified here, not
taken from the commit that added it.

**Its expectation of 1 was recorded as a deliberate FALSE positive, and that is
wrong; it is a true positive.** The claim was that on Android the `#ifndef` arm
is skipped and "the `#elif` chain is what gets compiled, so this `#else` really
is dead there". That silently assumes `SOME_OTHER_THING` is defined. It is not
-- it is a made-up token in a synthetic fixture -- so the `#elif` is not taken
and the `#else` arm is precisely what an Android build compiles. Settled with
the real preprocessor rather than by argument:

    $ gcc -E -D__ANDROID__ fixture.c
    static GLenum c(void) { return GL_SRC1_ALPHA; }

    $ gcc -E -D__ANDROID__ -DSOME_OTHER_THING=1 fixture.c
    static int b(void) { return 0; }

The code and the expectation were right; only the reasoning attached to them
was wrong. **That is pass 1's L2 recurring one level up** -- a wrong
justification on correct code, which is believed -- and here it was load
bearing in a way L2 was not: a reader told this finding is a known false
positive would be right to "correct" the fixture to expect 0, and that reopens
the `#elif` half of N1 with the fixture still green.

### N2 -- `pgraph_capture_run.sh` named the mislabelled-renderer hazard and then did not fail on it

It checked that *some* renderer was reported and never compared it to the one
requested, so a run that asked for OPENGL and came up on Vulkan printed one
informational line, exited 0, and extracted captures under the OPENGL tag.
Worth fixing on this lane rather than later because **the instrument's
silent-failure mode and this lane's headline have the same shape**: "GL is now
byte-identical to Vulkan" is both the result and what a both-on-Vulkan sweep
would manufacture. The instrument has to be the thing that refuses.

The fix is six lines and was already on the branch. What was missing is that it
had been proven **once, in a commit message** -- and a commit message is not a
fixture. `docs/testing/pgraph_capture_run_selftest.sh` now holds three cases
with every external part stubbed (no emulator, no firmware, no disc, no X
server), so it runs on a cloud container in a second:

| case | stub reports | RENDERER | must |
|---|---|---|---|
| 1 | Vulkan | OPENGL | die, naming both renderers, before extracting |
| 2 | OpenGL | OPENGL | **not** fire, and reach the extractor |
| 3 | nothing | VULKAN | hit the pre-existing never-reported-a-renderer die |

13 assertions, all pass. They are a mutant/control set on purpose: case 1 needs
the comparison to fire and case 2 needs it not to, so a blanket `die` -- the
cheapest way to pass case 1 -- fails case 2. Confirmed by deleting the six
lines from a scratch copy and pointing the fixtures at it with `RUNNER=`:
**case 1's three message assertions go red, cases 2 and 3 unmoved.**

Every assertion is on **words in the message, not the exit status**, because
the runner exits non-zero for a dozen other reasons and an exit code cannot
say which refusal happened -- or whether any did.

### Two things writing those fixtures taught, both worth not repeating

1. **The harness reproduced the runner's own `cd` bug against itself.** The
   stub directory went on `PATH` as a relative path, and the runner `cd`s into
   the binary's directory before launching, so `xvfb-run` stopped resolving.
   The runner absolutises `BIN` and `ISO` at :56 for exactly this reason; the
   fixtures now absolutise `$T` for exactly this reason too.
2. **Case 3 was green for the wrong reason first.** With `xvfb-run` missing,
   no renderer was reported, so "the emulator never reported a renderer" fired
   -- the assertion passed while nothing under test had run. Every case now
   also asserts the stub itself ran (`nv2a: init` in the log). A refusal you
   cannot distinguish from a broken harness is not evidence.

### Not done, deliberately

`gles_token_check.py` is still **not wired into `preflight.sh`**. That is part
of why N1 is MEDIUM and not HIGH -- the Android CI job is the gate of record
and runs on every PR -- and `preflight.sh` is not this lane's file. A later
lane that owns it should add the call; the script's `--selftest` is there to
make that safe.

---

## Audit pass 2b: the marker check reported `clean` without scanning anything

Pass 2b closed N1 and N2 by building mutants rather than by reading the commit
messages that claimed them, and confirmed `cb141001`'s preprocessor correction.
It then found a **MEDIUM in the file that had landed after pass 2 and that no
audit had read** — `skip_ci_marker_check.sh`, 117 lines old at the time.

### P1 — `clean`, exit 0, having read nothing

`git log --format='%H' "$range" 2>/dev/null` sent its error to `/dev/null`, so
an unresolvable range produced no commits, the loop ran zero times, `found`
stayed 0, and the caller printed **`clean` and exited 0**. Nothing in the output
told `"I read 24 bodies and none carried it"` apart from `"I read nothing"`,
because the count was never printed. The default range's left endpoint is
`origin/master`, which a single-branch clone or a worktree off a bare mirror
need not have.

**This is the fourth instrument in one day to report success without having
done the work** — after the desktop build standing in for Android, the GLES
checker hiding the arms it could not resolve, and the capture runner scoring a
mislabelled run. Same shape every time, and this one was written in the commit
that was *about* preventing silent failure.

Fixed by resolving the range first and reporting the count, so a clean verdict
now states how many bodies it read.

**The first fix for it did not work, and the way it failed is worth more than
the fix.** `resolve()` called `exit 2`, and the caller ran it as
`N=$(resolve "$RANGE")` — where the `exit` killed the **command-substitution
subshell** and the script carried on to print `clean` and exit 0. The guard
fired and the code proceeded anyway, which is P1's own shape reproduced inside
P1's remedy. It was caught by **re-running the reproduction after fixing**,
not by reading the patch. `resolve` now returns a status and sets a global;
the caller checks it.

### P2 — `pipefail` plus `grep -q` loses a marker in a large body

`git log … | grep -qF` looks equivalent to a string test and is not: `grep -q`
exits at the first match and closes the pipe, `git log` is killed by SIGPIPE,
the pipeline's status becomes 141, and `set -o pipefail` propagates it — so a
body past the 64 KB pipe buffer reports NOT FOUND **for the one reason that it
WAS found.** Reproduced before fixing: 4/16/32/60/64 KB found, 128 KB missed.
Replaced with a `case` on a captured string: no pipe, no buffer, no SIGPIPE.

Pass 2b rated it LOW on a measurement worth keeping: the largest commit-message
body in this repository's last 3,000 commits is **10,919 bytes**, six times
under the threshold, so no commit that exists today can hit it. A latent hazard
in a new instrument, not a live miss.

### Both now have failing cases, and the fixtures are specific

`--selftest` is 7/7. Against a mutant that restores the unresolved-range
behaviour, the two P1 fixtures go red and the rest are unmoved; against one
that restores the pipe, only the large-body fixture goes red.

One fixture failed on its first run for a reason worth recording: the assertion
`grep -q 'clean'` matched the **refusal** text, which contains the sentence
*"This is not a clean result"*. The fixture was right to fail and the assertion
was wrong. Anchored to `^clean`, the verdict being the only line that starts
with it.

### P3 — the file was on no `Files:` line and in no lane record

Corrected: `skip_ci_marker_check.sh` is now on the PR's `Files:` line, and this
section is its lane record. It is **deliberately not wired into
`preflight.sh`**, which is not this lane's file — it is a standalone for
whoever owns that gate, exactly like `gles_token_check.py`.

### P4 — pass 2's record said this branch carries no marker; it does

Pass 2's "checked and did not find wrong" list stated that none of the branch's
commit bodies carries the retired marker. `14312cb34f` does, and **the
instrument this branch added is what shows it**. Already recorded on the PR
before pass 2b raised it; it stays unfixed, because both registered prediction
refs are descendants of that commit and rewording it would rewrite history a
live prediction depends on.

## #62 finding 2, landed on `a5fdb6a7` — and what no audit had read yet

> **SUPERSEDED — read this section as the record of what was believed on
> 2026-09-19 at 19:16Z, not as the state of the tree.** `a5fdb6a7` was
> **reverted** in `d7ef9820` after audit pass 2c found its condition
> unreachable; the correction, the chain that refutes it and the arithmetic
> that survives are in *"Audit pass 2c, A1"* at the end of this file. Every
> reachability claim below is wrong. The *territory* paragraph immediately
> following, and the format-table readings, are unaffected and still correct.

Written by the remediation pass, not by the commit's author, because the commit
landed **three minutes before this PR was claimed for remediation** and after
the lane's own "nothing under `hw/`" status comment. So it is recorded here
rather than left to be re-derived.

**The grant is real, and checking it needs the right copy of the file.** The
`docs/testing/territory.toml` in this worktree is **wave 94 (2026-09-18)**: it
does not list `gl/surface.c` under `[lane.remote]`, it names the file *out* of
the glob and grants it to `lane.swizzle87` at wave 86. Read that copy and this
commit looks like a territory violation. It is not one — that copy is
fold-lagged by thirty waves.

The live board is **`origin/board:territory.toml`** (repository root, not under
`docs/testing/`), and `check_territory.py` reads it from there rather than from
the tree. At **wave 124, 2026-09-19T20:06:21Z** it has
`hw/xbox/nv2a/pgraph/gl/surface.c` first in `[lane.remote].files`, absent from
`[free]`, and `lane.swizzle87` retired out of the file entirely. So the grant
is on the **machine-read field**, not only in prose, and
`check_territory.py` reports `territory ok (wave 124, 29 lanes, 75 files
claimed)` against this tree.

The decision behind it is `[host.session]` on **#62 at 19:24:28Z**:
*"`hw/xbox/nv2a/pgraph/gl/surface.c` is GRANTED. Outright"* — made after
checking that `swizzle87` had retired with PR #139 merged, and **removed from
`[free]` in the same commit**, so the file is never listed both free and
claimed (the #161 repo-wide outage). Two lessons for the next reader: ask the
live board, and a grant that does not also release is not half a grant.

**The change.** One condition at `gl/surface.c:1331`: a surface whose drawn
format is `LE_R5G6B5` no longer takes the Android `render_surface_to()` blit,
because the driver's normalized conversion is the exact ratio
`round(v * 255 / (2^b - 1))` where silicon replicates bits. Excluded, it falls
through to `android_surface_guest_to_rgba8()`, whose R5G6B5 case at `:552`
already replicates. The gate is minimal and it is the right one:
`android_surface_to_texture_rgba8_compatible()` switches on
`pgraph_gl_surface_drawn_format(surface)` and admits `LE_R5G6B5` through
exactly one arm (the case at `:887`, whose only `true` returns are the
`LU_IMAGE_R5G6B5`/`SZ_R5G6B5` textures), so the new term removes that arm and
nothing else.

**What this change is NOT covered by, stated so nobody mistakes a green head
for evidence.** The whole block is `#ifdef __ANDROID__`. The desktop build
cannot execute it and the 236-capture run cannot exercise it; the Android CI
job compiles it and no more. That is H1's lesson in this same PR — the desktop
build standing in for Android — and it applies to the *behaviour* here even
though the *compile* is now gated. Behaviour on a device is unverified and is
the host's by the split agreed on the issue.

### An adjacent path the same argument reaches, NOT taken here

`rgba8_compatible()` also admits **`LE_X1R5G5B5_Z1R5G5B5`** (the case at
`:877`), and `gl/constants.h:388-391` maps both `X1R5G5B5_Z` and `_O` to
**`GL_RGB5_A1`** — read at the table itself, not from the prose comment at
`gl/surface.c:3082` that says the same thing. `GL_RGB5_A1` is
5 bits per colour channel, so `render_surface_to()` hands the driver the same
ratio expansion this commit just excluded R5G6B5 for, and on the face of it the
identical one-step error remains on X1R5G5B5 surface-to-texture on Android.

**It is recorded rather than fixed, deliberately.** #62 finding 2 is R5G6B5;
this is a different format on a path nothing in this container can build or
measure, and widening an Android-only fix on inference — the same inference
that produced the ratio/replicate model, not a measurement of this path — is
how a cheap correct change becomes an unverifiable one. It belongs to whoever
takes #62's device half. Flagged on the PR for the auditor to rate rather than
quietly taken.

---

## Audit pass 2c, A1: the #62 finding-2 fix could not execute, and the finding was stale when I filed it

Pass 2c closed P1–P4, each against a mutant it built rather than against the
commit message claiming them, and then read the one code commit no pass had
seen — `a5fdb6a7`, which I had flagged as the only unaudited code on the head.
**Its condition is unreachable and its central claim is false.**

### The chain, verified here rather than accepted

`a5fdb6a7` rested on: *"Both gates in front of the blit admit R5G6B5 … so the
blit is taken."* Both readings are correct. **There is a third gate in front of
both of them, and it refuses.**

| step | site | fact |
|---|---|---|
| the only call site | `gl/texture.c:927` | `pgraph_gl_render_surface_to_texture()` is called nowhere else in the tree |
| its guard | `gl/texture.c:801` | `surf_to_tex = pgraph_gl_check_surface_to_texture_compatibility(...)` |
| the refusal | `gl/surface.c:1543` | `if (pgraph_texture_format_is_converted(texture_fmt)) return false;` |
| ordering | `:1543` before `:1587` | the refusal precedes **every** `return true`, including the `__ANDROID__` early one |
| why R5G6B5 is caught | `pgraph/texture.c:143` | `is_converted()` falls through to `expands_by_replication()`, true for both `R5G6B5` spellings |
| why no pair escapes | `rgba8_compatible()` | an R5G6B5 **surface** is accepted only for `LU_IMAGE_R5G6B5` / `SZ_R5G6B5` **textures**, and both are converted |

So for every surface/texture pair that could have reached my condition,
`surf_to_tex` is false and `render_surface_to_texture_slow()` is never entered.
The four lines could not run.

### What I actually did wrong, which is not "missed a gate"

I re-verified the two gates the issue named, at the tip, on the day I wrote the
fix — and **never asked whether the function containing them is reached.** Local
facts checked, reachability assumed. That is the day's pattern in its purest
form: not a wrong measurement, but a correct measurement of something that does
not run.

Worse, **the finding was already dead when I filed it.** The `is_converted`
refusal landed in `c234c1cc` and `f0095555` on **2026-09-12**; #62 was filed
**2026-09-13**. So finding 2 described a path that had been closed the day
before, and neither the filing nor six days of subsequent passes over the issue
caught it. Finding 1's abort is in the same position — the `default:
g_assert_not_reached()` it fixed is equally unreachable through this route — so
that fix is inert too, though harmless.

### The decision on the four lines: REVERTED

Pass 2c offered keep-as-documented-guard or revert, and said the choice is the
lane's. Reverted, byte-identical to the pre-commit file, because **a guard that
cannot execute cannot be tested.** There is no fixture for it, no run that
exercises it, and no way to show it does the right thing when it becomes live.
Keeping untested unreachable code because it might be correct later is the same
claim-without-evidence this branch has spent the day removing from its own
instruments; relabelling it "defensive" would make the comment honest and the
code no more verifiable.

`packed-texel-expansion.md` calls the `is_converted` refusal its *"least
certain point"*, so the gate may well be relaxed. Whoever relaxes it will be
running the tests that make this path live, and can write the exclusion then
with a measurement attached — which is strictly better than inheriting four
lines written blind.

### What survives, and it is the larger half

The arithmetic is correct and is about the model, not the route:

* 5-bit channel: 4 of 32 values differ, max one step
* 6-bit channel: 10 of 64 differ
* whole pixel: **23,200 of 65,536 (35.4%)** — R 8,192, G 10,240, B 8,192
* endpoints agree in both rules, so it never shows as a black or white shift
* the 09-13 figure of 30,720 (46.9%) is reconciled: that was against the old
  **truncating** scalar tail; the GPU **rounds**. 30/64 truncating, 10/64
  rounding. Both right for what they measured.

Ratio-versus-replication is still a real divergence from silicon wherever a
5/6-bit surface is decoded by the host. It is the *surface-to-texture blit*
route that does not exist, not the discrepancy.

**The device ask is withdrawn.** #62 finding 2 has nothing for a device lane to
confirm, and the offer should not have stood after this was known.


## A CLEAR writes the pad bit too, and the two "rival mechanisms" are one (2026-09-20, fourth judgement)

**What the section above got wrong, in its own words:**

> The pad bit … is written by the raster, per pixel, and is absent where the
> raster never wrote.

The word *raster* is wrong, and wrong in the direction that costs most. A
`NV097_CLEAR_SURFACE` writes it too.

### The instrument, and why only this one can say so

`Clear::SCF_X1A7R8G8B8_{Z,O}`. `ClearTests::TestSurfaceFmt` renders a 128×128
surface of the format under test, fills it with `NV097_CLEAR_SURFACE`, draws
**one** 4×4 centre mark (`kBlackCenterMarkSize = 2.f`) and nothing else, then
samples that memory back as a **linear `A8B8G8R8`** texture with blending off
on the left half. The texture unit is never told the memory was X1A7, so
anything X1A7-shaped in the result **is in the bytes**. Every other X1A7
capture composites the surface and shows a function of them — which is why
`x1a7_forward_model.py` needs a model of the composition and this does not.

| | |
|---|---:|
| surface pixels, six solid 128×128 rects, zero holes | 98,304 |
| covered by the one 4×4 draw | **96** |
| written by `NV097_CLEAR_SURFACE` and nothing else | **98,208** |
| where `_O == _Z \| 0x80` | **98,304 — every one, no exceptions** |
| inside a surface without it | **0** |
| cleared-only pixels with alpha `0x00` that still carry it | 32,736 |

The 96 drawn pixels read `0x7f` in `_Z` and `0xff` in `_O`: the 7-bit
quantisation visible directly rather than inferred.

### Why the earlier reading was reasonable and still wrong

Both of its observations hold. Blend surface *does* draw two full-surface
quads, so every pixel there carries the bit. Surface format's background
*is* unstamped. What was wrong is the inference joining them. That background
is not "a region the raster never touched" — it is memory the **guest CPU**
memset (`surface_format_tests.cpp:216` memsets the whole texture region
before the pad format is bound), which the GPU then never wrote at all. A
clear is a GPU write and does stamp; a CPU memset is not and does not. Two
different facts wearing one sentence.

### What that does to the next step

The section above says to carry the guest representation "for pixels the
raster writes — which only the fragment path can know". **The fragment path
cannot see a clear**, and on this capture that is 98,208 of 98,304 pixels. So
that next step, implemented literally, would leave almost the whole surface
unconverted — worse than converting all of it, which is what was measured and
reverted.

And the two options recorded as rivals — *a separate per-surface channel* and
*drawn-coverage tracking* — are **one mechanism**. The channel is an
implementation of the tracking, not an alternative to it. There is one open
question, not two: how the download learns which bytes the GPU wrote,
clears included.

### It is not an X1A7 quirk either

`X8R8G8B8_{Z,O}` and `X1R5G5B5_{Z,O}` carry the same story on the same
capture, each in its own terms — X8R8G8B8's X field is the whole alpha byte,
so `_Z` reads `0x00` and `_O` reads `0xff` on all 98,304, and the 1555 pair
is sampled two words to a texel so its bit 15 lands in a colour channel.
**For those two the blend unit has no destination alpha to lose**
(`vk/draw.c:surface_color_format_dst_alpha_is_one()`), so the host alpha byte
is free to carry the X constant. Only X1A7 has seven real alpha bits under
the pad, and therefore only X1A7 has the one-byte-two-readers conflict.

### What did not change

A download still sees only bytes and still cannot tell a GPU-written one from
a guest-written one. Storing the guest byte in the host alpha is still
refuted — and now on a corrected model: `compose()` had been applying the
write side to the swatch pass only, not to the background pass, so a design
that changes the stored byte was scored against a surface that changed
behaviour halfway through the test. Fixing that left `guest byte in the host
surface` at 23 of 32 and took `guest byte stored, blend still reads expand7`
from a spurious **0 of 32** to **23 of 32**. Correcting the blend's read does
not buy anything, because the byte the blend reads is the stored one either
way. The 7-bit quantisation is still carried forward.

### Where the numbers live now

`docs/testing/x1a7_forward_model.py`'s `DESIGNS` table prices the four whole
designs end to end (18 / 0 / 23 / 23 of 32), with `today` and the model as
asserted controls. `docs/testing/x1a7_clear_bytes.py` re-derives every count
in this section from the goldens, and scores a run directory against them.
Both self-test without a disc, because the CI runner has neither goldens nor
numpy.

### The coverage gap this exposed, which is the part worth carrying

**The `Clear` suite is in none of the six suites `[job.arms]` scores and not
among the 236 captures of `iso_surf1`.** The one capture in the corpus that
reads the X-format bytes directly has been outside every instrument this lane
has used, on both renderers, for the whole campaign. It is also where #164's
clear-half fix is measurable: desktop OpenGL, `SCF_X8R8G8B8_Z8R8G8B8`
98,208 → 0 and `SFC_X1R5G5B5_Z1R5G5B5` 49,104 → 0, with `iso_surf1` 0 better
/ 0 worse / 236 same beside it and a same-binary control at 0 / 0 / 236.

## #109: the swizzle stride, measured and fixed (2026-09-25)

**Where it started.** PR #115 registered a GL-vs-Vulkan arm at `4129a349e6`
asking which of two models our renderers follow for a swizzled surface whose
pitch is smaller than `width * bpp`. The arms job cannot run a renderer
variant, so the board routed it here (territory wave 153). Result, on #109 in
5828843964: VERDICT FAIL 3/17. All three violations were the Vulkan-only #59
pad write side at that ref, forecast in 5828665488 before any run. The
discriminating capture split cleanly: **GL is Model E, Vulkan is Model H.**
Wave 162 granted `gl/surface.c` for the fix.

**The defect.** A swizzled surface has no pitch: `generate_swizzle_masks()`
interleaves x and y and nothing else. Every GL site that staged one through a
linear intermediate used `surface->pitch` as that buffer's row stride. At pitch
256 on a 128-wide A8R8G8B8 surface the rows overlap, and the read-back is
`dest(x, y) = src(x - 64, y + 1)` for `x >= 64`. The fix (`e4fb7c24`) adds
`surface_swizzle_linear_pitch()` (`width * bpp`) and uses it at every staging
site in `gl/surface.c`:
- `surface_download_to_buffer()`: the desktop readback stride, the downscale
  loop and `swizzle_rect`, plus its Android RGBA8 branch;
- the Android depth16 and z24s8 helpers;
- the unswizzle in `pgraph_gl_upload_surface_data()`.

Linear surfaces keep the guest's pitch.

**Registered before the code**, on #109 in 5834083923. The draft is sha256
`bf0f60dc...`, and the committed file differs from it only in `b_ref` and
`registered_utc`. File: `docs/testing/predictions/remote-109-swizzle-linear-stride.json`,
judged as registered at sha256 `6e1e8c24...` (commit `e156200f`). `1349125a`
then added a `title` so `[job.arms]` treats it as hand-queued, because the
fleet APK defaults to Vulkan, where the fix is absent. No leg changed.

**Measured**, desktop GL, `surface_scale = 1`, the registered 8-suite disc,
3 runs per arm alternating. The base `0.4.0-j1-2173-g84a67b9c`, sha256
`5dc4737e9b04`, is arm A; `0.4.0-j1-2174-ge4fb7c24`, sha256 `f1f4934be561`, is
arm B. No capture is `unreadable` in any of the eight scores files.

| | A (84a67b9c) | B (e4fb7c24) |
|---|---:|---:|
| `Surface_pitch/Swizzle`, every run | 12,224 | **8,192** |
| per quad q0 / q1 / q2 / q3 | 2,048 / 2,048 / 2,048 / 6,080 | 2,048 / 2,048 / 2,048 / **2,048** |
| q3 signature, of 8,128 (golden 4,096) | 8,128 | **4,096** |
| q3 top-right quadrant, non-green | 4,032 | **0** |
| totals, every run | 943,576 px, 49 exact | 939,544 px, 49 exact |
| `surface_scale = 2`, one run | **aborts**: `gl/surface.c:2473` assert, exit 134, 59 captures | **completes**, 73 captures |

`ab_compare.py`: **PASS, all 75 registered checks hold**, `PRE-REGISTERED`.
The counts are better 1 / worse 0 / same 72, and the byte check found only the
mover different. At scale 2, B's Swizzle reads 10,240: 2,048 on q0 and q1, and
3,072 on q2 and q3 alike. That leg was not registered. It is recorded because
q2 (exact pitch) and q3 (undersized) now read the same, which is the silicon
relation.

**Re-run it.** Build the disc with `make_test_iso.py --suite` for each of the
eight suites, `--progress-log --shutdown-on-completion`. Run each binary under
`xemu.toml` `renderer = 'OPENGL'`, `[display.quality] surface_scale = 1`, from a
fresh HDD with the shader caches cleared. Score with `score_sweep.py --flat`
and judge with `ab_compare.py --expect` on the prediction. For the per-quad
legs, run `docs/lanes/remote/swizzle_pitch_quads.py CAPTURE [GOLDEN]` on the
Swizzle capture.

**Not covered.**
- The Android branches compile, checked with `-D__ANDROID__ -fsyntax-only`
  against stubs, but cannot run here. By reading, the z24s8 helper's swizzled
  buffer was `pitch * height` while every row wrote `width * 4`, so an
  undersized-pitch swizzled zeta surface wrote past the allocation. It is now
  sized from the same stride. Nothing on the disc reaches it.
- The extent sites (`pitch * height` as a surface's size in the dirty ranges
  and DMA asserts) are #109's silicon question and are untouched.
- Vulkan's deferred download still stages at `dl->pitch`, but `vk/surface.c`
  is not this lane's. On this capture Vulkan read Model H in every run.

## #184: two gates on one stale texture, and the first fix found only one (2026-09-25)

**Where it started.** #184 filed the shape: on desktop Vulkan, six of
`Clear::TestSurfaceFmt`'s eight surface-format captures show swatch 0's clear
on every swatch after it. The test clears one 128x128 surface at one address
six times, draws a 4x4 centre mark into it, and samples it back as a linear
`A8B8G8R8` texture each time. An instrument on 09-24 (#184, 5827596169) found
that `pgraph_vk_bind_textures()` was never called for swatches 1-5: every
call site's gate opens only on `texture_state_gen` or `texture_vram_gen`, and
a clear or a draw into the source surface moves neither.
`pgraph_vk_surface_written_while_sampled()` bumped the gen only for a stage
whose direct view *is* the surface; these stages hold a surface-to-texture
copy, or for the 16-bit formats a VRAM upload.

**First attempt: FAIL 4 of 35, reported as such.** `b0470969` added a second
case to that hook: bump when a stage's bound memory overlaps the written
surface. Registered first (5834976599, `remote-184-clear-rebind.json`), then
measured (5835099210): `SFC_A8R8G8B8`, `SCF_R5G6B5` and
`SCF_X8R8G8B8_Z8R8G8B8` went to 0, `SCF_X1A7R8G8B8_Z1A7R8G8B8` stopped
aliasing, and `SCF_X8R8G8B8_O8R8G8B8` and `SCF_X1A7R8G8B8_O1A7R8G8B8` did not
move. My X1A7 alpha model was wrong too: the Vulkan path stores the clear
alpha's low 7 bits widened back to 8 by bit replication, not the raw alpha. I
guessed the `_O` captures copied from a different `SurfaceBinding`. That
guess was also wrong.

**What the instrument showed** (local, never committed; one run of
`iso_pre_clear` on `b0470969`). The stale swatches were copied from the very
`SurfaceBinding` that was written. The bump did open the gate, and
`pgraph_vk_bind_textures()` then skipped the stage twice per swatch:
- at the centre-mark draw nothing was marked dirty, so it returned at
  `check_textures_dirty()`;
- at the display quad, `SetupTextureStages()` re-sets stage 0 with identical
  register values. That sets `texture_dirty` and moves no gen
  (`pgraph_reg_w()` bumps only on a change), and the `tex_reg_cache` shortcut
  skips `create_texture()` when the registers match and the binding's VRAM
  memo reads "checked clean this frame".

For a stage built from a surface, that memo is about guest memory the draw
never wrote. It lasts until the next `FLIP_INCREMENT_WRITE`, which is after all
six swatches, so whether it is current is timing. In the v1 arm the two tests
that follow a VRAM-path format aliased. In the instrumented run the X1A7 twins
swapped. **A partial fix that makes the outcome timing-dependent is worse than
it looks: "each `_O` follows its `_Z` twin" read like a mechanism, and it was
an accident of test order.**

**Second attempt: `1213f50c`, still body-only in the same hook.** For every
stage whose bound memory overlaps the written surface it invalidates
`tex_reg_cache[i]`. It bumps the gen once, and a direct view no longer ends
the scan early. `texture_dirty` is deliberately not set: that would rebuild,
and so recopy, an enabled stage the draw does not sample, on every draw of a
pass that leaves a stage bound to its own target. Invalidating the cache
defers the rebuild to the next write of that stage's registers.

**Registered before the code** (5835426532; drafts `1e4d2530...` and
`d1c61132...`, committed in `ad2860f4`, each differing from its draft only in
`b_ref` and `registered_utc`):

| capture | A `5eab6a87` | registered B | measured B `1213f50c` |
|---|---:|---:|---:|
| `SFC_A8R8G8B8` | 81,840 | 0 | **0** |
| `SCF_R5G6B5` | 40,920 | 0 | **0** |
| `SCF_X8R8G8B8_Z8R8G8B8` | 81,840 | 0 | **0** |
| `SCF_X8R8G8B8_O8R8G8B8` | 81,840 | 0 | **0** |
| `SCF_X1A7R8G8B8_Z1A7R8G8B8` | 81,936 | 65,568 | **65,568** |
| `SCF_X1A7R8G8B8_O1A7R8G8B8` | 98,208 | 65,472 | **65,472** |

Desktop Vulkan, llvmpipe, `surface_scale = 1`, 3 runs per arm, alternating;
every run has progress-log proof, and no capture is `unreadable`.
`remote-184-clear-rebind-v2.json`: **PASS, all 35 registered checks hold**,
`PRE-REGISTERED`. The counts are better 6 / worse 0 / same 27, and only the six
movers differ byte for byte. The prose legs hold by script in all 3 B runs:
- every swatch shows its own clear (`clear_swatch_quads.py`'s stale column is
  `......` on all eight);
- the X1A7 splits are 16 / 16,384 / 16,384 / 16 / 16,384 / 16,384 and
  16,368 / 16,368 / 0 / 16,368 / 16,368 / 0;
- all eight SCF/SFC captures are pixel-identical across the three runs.

The X1A7 residuals equal GL's; they are #60's pad-bit family. Master's arm A
is pixel-identical to `38789df7`'s on all 33 captures; the only `hw/`
difference between those refs is GL-only. Disc totals: 517,568 px (master) ->
296,600 (first attempt) -> 182,024.

**The guard, `remote-184-surf1-guard.json`: PASS, all 238 registered checks
hold**, `PRE-REGISTERED`. The change reaches every stage that overlaps a
written surface, so it was also run on `iso_surf1` (14 suites, 236 captures),
3 runs per arm. Every capture is byte-identical between master and the fix:
better 0 / worse 0 / same 236, and 3,760,226 px with 128 exact in every run of
both arms. That matches what reading those suites predicted:
- `Blend_surface` rebinds stage 0 through the dummy texture between quads;
- `Surface_format` renders once per capture, after a CPU memset;
- `Color_zeta_overlap` enables no stage.

**Not covered, and not claimed.** A stage sampled while its own memory is
written, with no register write in between (a feedback loop), and a stage that
starts being sampled through `SET_SHADER_STAGE_PROGRAM` alone are both still
stale. Both are stale on master too, and neither disc reaches them. A
direct-view stage keeps its old treatment. It samples the surface itself, so
its risk is a skipped barrier, not stale texels, and whether the same shortcut
skips that barrier was not examined.

**A bookkeeping error in the first arm.** Its `result.json` files carried
disc109's `disc_id` string, from a stale file in my assembler. Both arms
carried the same string, the judge's composition check reads `request.json`,
which named `Clear` and `Pixel shader`, and the captures and run logs are
`iso_pre_clear`'s, so the verdict stands. The second arm's ids follow
`dispatcher.sh`'s formula.

**Re-run it.** Both discs are built with `make_test_iso.py --suite` for each
listed suite, `--progress-log --shutdown-on-completion`. Run each binary under
`renderer = 'VULKAN'`, `[display.quality] surface_scale = 1`, from a fresh HDD
with the shader caches cleared. Score with `score_sweep.py --flat` and judge
with `ab_compare.py --expect` on the prediction. For the per-swatch legs, run
`docs/lanes/remote/clear_swatch_quads.py CAPTURE_DIR [GOLDENS_DIR]` on each B
run.

## #109's Vulkan half: a latent defect, measured by forcing it (2026-09-25)

**Where it started.** #247 fixed GL's staging of a swizzled surface at the
guest's pitch. Its PR noted that "Vulkan's deferred download still stages at
`dl->pitch`", and the host granted `vk/surface.c` for that at territory wave
181 (#109, 5836653214).

**Three CPU sites, not one.** Reading `vk/surface.c` on master `5807b54f`
found three places that stage a swizzled surface through a linear buffer at
the guest's pitch:
- **the deferred download's completion** (`pgraph_vk_complete_staged_downloads`),
  for every format. It fills and swizzles a `pitch * height` buffer at
  `dl->pitch`, so with an undersized pitch `swizzle_rect` also reads past the
  buffer on the last row;
- **the synchronous download's CPU branch** (`download_surface_to_buffer`), for
  every format but 4-byte;
- **the upload's CPU branch** (`pgraph_vk_upload_surface_data`), for every
  format but 4-byte.

The 4-byte swizzles and unswizzles run in compute, and those paths take no
pitch.

**No disc reaches them.** A local instrument, never committed, logged every
swizzled transfer on disc109, `iso_surf1` and `iso_pre_clear` under Vulkan:
- every deferred swizzled download had `pitch == width * bpp`, and each wrote
  bytes identical to a pitch-free swizzle;
- no 1- or 2-byte swizzled surface was transferred at all;
- the corpus's only undersized-pitch swizzled surface, Swizzle's target 3
  (`0271b000`, 128x128 A8R8G8B8, pitch 256), took the compute paths. That is
  why Vulkan reads Model H on Swizzle.

**A null from an instrument that cannot see the change is not evidence about
the change**, so the defect was forced. A local patch, never committed, is
inert unless `V109_FORCE` is set. Each mode routes every swizzled transfer
through one CPU site, and logs a `[v109f]` line for each forced transfer of an
undersized-pitch surface:
- `sync` takes the CPU swizzle instead of the compute one;
- `upload` takes the CPU unswizzle;
- `defer` records the download through the deferred recorder and completes it
  at once.

On master plus the patch every mode forced exactly target 3, and only Swizzle
moved:

| `V109_FORCE` | q3 differing | q3 signature (golden 4,096) | q3 top-right non-green |
|---|---:|---:|---:|
| unset | 0 | 4,096 | 0 |
| `sync` | 4,032 | 8,128 | 4,032 |
| `upload` | 6,144 | 992 | 2,048 |
| `defer` | 4,034 | 8,128 | 4,032 |

`sync` and `defer` are GL's Model E pixel for pixel. `defer`'s extra pixels
come from the over-read: A's two runs differ in exactly one pixel there, and
every other arm is identical with itself.

**The fix** (`3f3fe35b`) stages all three sites at `width * bpp` through
`swizzle_linear_pitch()`. Linear surfaces keep the guest's pitch, and the
compute paths and the `pitch * height` extent sites are untouched.

**Registered before the code** (#109, 5837061813; drafts `20121600...`,
`1af2c8aa...`, `a41527ee...` and `bf7a0b39...`; committed in `c190a93c`, each
differing from its draft only in `b_ref` and `registered_utc`). Desktop
Vulkan on llvmpipe, `surface_scale = 1`. Every run has progress-log proof, and
no capture is `unreadable`.

| registration | arms | verdict |
|---|---|---|
| `remote-109-vk-forced-sync.json` | master+patch vs fix+patch, disc109, 2 runs each | **PASS 75/75**: Swizzle 4,032 -> 0, the other 72 byte-identical |
| `remote-109-vk-forced-upload.json` | same, `upload` | **PASS 75/75**: Swizzle 6,144 -> 0 |
| `remote-109-vk-forced-defer.json` | same, `defer` | **PASS 75/75**: Swizzle 4,034 -> 0 |
| `remote-109-vk-swizzle-stride.json` | master vs fix, no forcing, `iso_surf1`, 3 runs each | **PASS 238/238**: all 236 captures byte-identical, better 0, worse 0 |

Every forced B run logged exactly one forced transfer of `0271b000`, and read
q3 = 0, signature 4,096 and top-right 0. In the clean arm, #88's guards read
the host's figures in every run of both arms (`Color_zeta_overlap`
ColorIntoZeta_ZB 10,766, ZetaIntoColor 71,663, Swap 165,447), and Swizzle
reads 0.

One capture was not stable on master. `Blend_surface/R5G6B5_Add_SrcA_DstA`
read 11,964 in master's first clean run and 14,833 in the other five runs of
both arms. It moved in A only and is not on the judge's `KNOWN_UNSTABLE` list,
so it is recorded here as an observation about master, not about this
change.

**Not covered.** The extent sites (`pitch * height` as a swizzled surface's
size in the dirty ranges) are the silicon question and stay lane.xbox's.

**Re-run it.** `docs/lanes/remote/v109_force_paths.py` applies the forcing
edits to a working tree. Its replacements are exact-string, so it applies to
master and to the fix alike. Build, then run disc109 under
`renderer = 'VULKAN'` with `V109_FORCE` set in the emulator's environment,
and read Swizzle with `docs/lanes/remote/swizzle_pitch_quads.py`. Revert with
`git checkout -- hw/xbox/nv2a/pgraph/vk/surface.c` and rebuild. The clean
arm needs nothing forced.
