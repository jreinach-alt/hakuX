# lane.blitsafe — #92, #89, #88, #91

Surface/clear path on the Vulkan renderer. Four issues held by one lane because
they all land in `vk/surface.c` and `vk/draw.c`.

Files: `hw/xbox/nv2a/pgraph/vk/draw.c`, `hw/xbox/nv2a/pgraph/vk/surface.c`.
`vk/blit.c` and `pgraph/surface.h` were in the grant and are **untouched** —
see "blast radius" below for why `surface.h` stayed shut.

---

## Why attempt 1 did not finish, in the terms the next reader needs

It finished the *work* and failed the *bookkeeping*, and the bookkeeping was
load-bearing. Three things:

1. **It never wrote this file.** Attempt 1 put its findings in
   `docs/investigations/` and in the PR body. The lane contract asks for
   `docs/lanes/<name>/NOTES.md`, and a lane that records nothing here is
   invisible to the next resume, which is why attempt 2 began by re-deriving
   state from `git log` and the PR.
2. **The PR body carried no `Lane:/Files:/Prediction:` header block.** The
   board reads `Files:` from every open PR to keep two lanes off one file. For
   the whole of attempt 1 this lane's two files were held by nothing the board
   could see.
3. **It left #88's and #91's arms bound to shas that no longer existed** — the
   defect that actually cost the lane its results. Detail below, because it has
   now happened *twice* on this branch and the mechanism is worth more than the
   fix.

A fourth thing was not a failure of attempt 1: it marked the PR ready, and the
board then labelled it `needs-remediation` off audit pass 1. This attempt is
that remediation.

### The rebase/registration trap, which caught this lane twice

`arms.sh:213` refuses any prediction whose `b_ref` fails `live_ancestor()`, and
`already_ran()` records that refusal as a **structural** skip — one that
"stands until the prediction itself changes, because no edit to this script can
turn one of them into a run."

So an orphaned `b_ref` does not fail loudly. The prediction sits in the tree
looking live, gets skipped every tick, and reports nothing. #91's was worse
than stale: it was *registered onto an already-orphaned pair*, so it was dead on
arrival and has never once been runnable.

Sequence, so the shape is visible:

| when | pair | killed by |
|---|---|---|
| first registration | `12870b8fde → e71a9952d1` | a rebase; caught by audit pass 2 |
| re-bind (`b6017b1b9`) | `f343580647 → 4726557b0f` | **another rebase**, onto `55bc6c6c` |
| now (`659e2c07e`) | `55bc6c6c2b → 67dc7724ee` | — both are ancestors |

The re-bind commit's own message says "Both new refs are ancestors of HEAD,
checked with merge-base rather than assumed." That was true when written. The
branch was rebased again afterwards, and **nothing re-checks a registration
after the fact** — the check is a point-in-time assertion in a commit message,
and the history moved out from under it.

**What the next lane should not repeat:** do not re-verify a registration once
and consider it settled. Either register after the last history rewrite and
then merge (never rebase) — which is what the lane contract says and what this
attempt did — or re-check `merge-base --is-ancestor` immediately before
concluding. A verified-once ref is not a live ref.

The one cheap guard that would have caught all three: `git branch -a --contains
<b_ref>` returning empty is the whole tell, and it costs nothing.

---

## #92 — the instrumented run, and its verdict

**The brief asked for `framebuffer_dirty()`'s verdict logged across
`TestSwap()`'s `SET_CONTEXT_DMA_COLOR` writes. That verdict cannot answer the
question, so the instrument was changed and the substitution is declared.**

The premise is true and stands: `SurfaceShape` carries no address and
`framebuffer_dirty()` is a `memcmp` of it. But the shape is the *shape*-change
signal. The *address*-change signal is `buffer_dirty`, and
`SET_CONTEXT_DMA_COLOR` sets it one line below the `dma_color` write it is
accused of hiding (`pgraph.c:2387`), as do `SET_SURFACE_COLOR_OFFSET` and
`SET_SURFACE_PITCH`. A `framebuffer_dirty()` verdict of `false` at a swap is
what **both** worlds produce — stale binding kept, or binding re-resolved by
the other flag — so that log would have read identically either way. It is a
tautological instrument.

`surf92_probe()` counts the discriminating event instead: an upload-side
`update_surface_part()` whose target address differs from the address of the
binding it currently holds, **while the gate that would re-resolve it is shut**.

### The log, from the device

The probes shipped in both arms of #89's A/B, so the arms job produced the
instrumented run as a by-product. Base arm
`1789794908-arms-blitsafe-base-4139807`, disc `Blend surface, Color mask blend,
Color zeta overlap` — which contains `TestSwap()`, #92's subject.

```
[surf92] updates=40960 shapedirty=548 addrchg=0 missed=0 color fbdirty=0 gate=0
         held=0x0301c000 want=0x0301c000
[clr89]  clears=33280 nobind=0 diverged=0 shape_fmt=0x08 drawn_fmt=0x08
         shape_pad=0 drawn_pad=0 addr=0x0301c000
```

Final cumulative counters over the whole run; 20 `[surf92]` and 65 `[clr89]`
lines, printing continuously until the workload ends at 22:20:38 (the last five
seconds are teardown — `qemu_main returned 0` at 22:20:43 — with no surface
updates or clears in them). `held == want` on every line printed.

**Verdict: #92's premise is confirmed and its consequence is REFUTED for this
suite.** Over 40,960 upload-side updates, no update ever found its held binding
pointing somewhere other than its target. `missed=0` follows.

### What the instrument can and cannot see — established before reading the zero

This matters more than the number, because a zero from a blind instrument
looks exactly like a zero from a sharp one.

- **It is placed where it can see.** `current_binding` is read live at
  `surface.c:3305` and `target` is freshly populated at `:3276`, both **before**
  the gate at `:3308` acts and before `unbind_surface()` at `:3322`. So the
  comparison is genuinely held-vs-wanted, not a post-resolve tautology. I
  checked this specifically because `addrchg=0` across a run in which the clear
  probe shows three distinct surface addresses (`0x034cc000`, `0x0397c000`,
  `0x0301c000`) cycling is surprising enough to suspect the probe rather than
  the renderer.
- **It can see the route the investigation named as most likely.**
  `target->vram_addr` is `dma.address + offset`, and `dma.address` is re-read
  from the DMA object in instance memory by `nv_dma_load()` on *every* call. So
  a guest that rewrites that object in place — moving the surface with no method
  write at all, unseen by *both* signals — shows up here as `addrchg > 0` with
  the gate shut, i.e. as `missed > 0`. The probe is capable of catching it. It
  caught none.
- **`missed` is not an independent measurement.** `missed ⊆ addrchg`, so
  `missed=0` is entailed by `addrchg=0` and discharges nothing on its own. The
  discriminating counter is `addrchg`.
- **It is blind when `current_binding == NULL`** — `addr_change` is false by
  construction there. That blind spot is structurally safe rather than
  worrying: a NULL binding opens the gate at `:3308`, so it re-resolves and
  *cannot* be a missed address change. Blind spot and safe region coincide.

So: no missed address change was possible in this run, not merely none seen.

**Not established:** anything outside this three-suite disc. A title that
rewrites a DMA object in place would still be the way in, and nothing here
exercises one. The `!color_format && !zeta_format` hole in `framebuffer_dirty()`
(`surface.c:121-124`) is real and untouched — see blast radius.

---

## #89 — patch, prediction, and a PASS

`pgraph_vk_get_clear_color()` took its pad-alpha decision from
`pgraph_vk_surface_drawn_format(r->color_binding)` — what the surface was LAST
DRAWN WITH — and now takes it from `pg->surface_shape.color_format`, the
register hardware stamps from at the time of the clear. A **narrowing** of
#59's stamp, not a revert: the clear always wrote `1.0` before #59, so
reverting restores a different defect.

**Registered as an INERTNESS claim** (`issue89-clear-pad-alpha-shape.json`),
because the reading said nothing would move and the honest move was to register
that rather than hope. **Arm ran 2026-09-19: PASS, all 44 checks.** 42 of 42
captures byte-identical between arms; `better 0 worse 0 same 42`.

The brief's falsifier was **kept and inverted**, which is the part to read
carefully. The brief said: if the drawn/shape divergence is the mechanism,
`Blend surface` moves and `Color mask blend` does not. Both were registered
`must_not_move` instead, because the reading said neither moves. The partition
still discriminates — `Blend_surface` alone moving would mean the divergence is
live and the reading wrong; `Color_mask_blend` alone moving is the impossible
row (`PAD_ALPHA_NONE` takes neither branch under either source).

And the cheaper instrument agrees with the A/B directly rather than by its
shadow: **`diverged=0` over 33,280 clears**. The two expressions were never
once unequal at a clear on the device. That is the mechanism measured, not the
pixels it would have moved.

**So #89's code question is closed, and #89's 141,125 is NOT.** That mechanism
was withdrawn on the issue by its own arms D/E/F. The narrowing is correct and
inert; the 141,125 is a disc-composition effect and belongs to whoever picks up
`Swap_ZB`.

### The one leg that was supposed to be more than a tripwire, and wasn't

`Swap_ZB` was registered `must_not_move`, and the prediction gave it a second
job:

> on this disc it should read 141,125 in BOTH arms (33 captures in two
> preceding suites, above the measured threshold of 2), so it doubles as a
> positive control that the composition effect is present and untouched.

**It read 0 in both arms.** (`scores1.tsv`: `Swap_ZB` 0/0, `Swap`
304,750/304,750.) The `must_not_move` leg passes — 0 → 0 does not move — but
the *control* did not fire: the composition effect it was meant to witness was
absent, so it confirmed nothing.

The error was in the threshold reasoning, and #88's own analysis had already
established why: `Swap_ZB` scores **0 on six handheld Vulkan runs** across six
`apk_sha`s, bit-exact on three. The 141,125 is a *desktop-lane / `iso_surf1`*
figure. Predicting it on a handheld three-suite disc carried an absolute across
platforms — which that same prediction's section (b) explicitly warns against,
one paragraph earlier.

**What the next lane should not repeat:** a `must_not_move` leg given a
second, positive-control job needs its expected value derived on *the platform
and disc it will run on*. Here the leg's two jobs disagreed and only the weak
one was scored, so a PASS looked like it had confirmed composition when it had
confirmed nothing. An inert control is not a measurement, and it is hardest to
spot when it is bolted onto a leg that passes for other reasons.

Unplanned corroboration from the same table: `Swap` reads 304,750 in both arms
here, and both refs carry #88's policy (`67dc7724ee` is an ancestor of each).
That independently reproduces the arm-B value of the 165,447 → 304,750 move
#91 is about, on a different disc and a different pair.

---

## #88 and #91 — patch and arm registered; no verdict yet

Both arms are now queueable for the first time (see the trap above). Both are
`55bc6c6c2b → 67dc7724ee`, differing in `vk/surface.c` alone — verified by
patch-id `4e14c872b095…` on both the old and new pair, so the re-bind preserved
the property rather than merely claiming to.

**#88.** `update_surface_part()`: when the surface at the target address is the
other role's current binding, colour still takes it and zeta now declines. GL's
policy, ported; the gate half of GL's `fada1d89` was already present in Vulkan
(`9161e3e14a`, 2024) and is strictly more permissive, so only the policy
crossed. Absolutes (`ColorIntoZeta_ZB → 10,766`, `ZetaIntoColor → 71,663`) are
derived from the goldens' own histograms. **They are conditioned, not
re-derived:** the pair now sits on 109 further commits of master and nothing
this session re-measured them. `ARM A IS THE CHECK` governs — a miss on an
absolute with the delta intact is a base/composition effect, not the mechanism
failing.

**#91 — no patch, deliberately, and this is the written statement of what is
missing.** The issue attributes the `Swap` regression to the missing depth
attachment. **The captures refute that.** The three colour populations are
partitioned *identically* in both arms (165,447 / 139,303 / 2,450), which a
change to depth *testing* cannot do. Only the background's value moved:
`0xFE242424 → 0x00000024` — bits 8–31 zeroed, bits 0–7 preserved, which is a
Z24S8 depth-only clear of 0 written over a colour surface, the surviving `0x24`
being the clear colour's own low byte.

So it is a clear landing on the wrong attachment, not a test being skipped —
`pgraph_vk_clear_surface()`, not the pipeline state. But both clear paths guard
`write_zeta && r->zeta_binding`, so neither issues a depth clear with no zeta
binding, and the signature needs **one image to have taken both clears**. That
is the aliasing case — a design question about supporting a same colour/zeta
target, not a drive-by fix.

**Precisely what is missing:** a route by which one image takes the colour clear
and then the depth clear inside `TestSwap()`. Reading `update_surface_part()`
against `TestSwap()` does not reproduce the decline firing there at all —
`SET_CONTEXT_DMA_COLOR` sets `surface_color.buffer_dirty` (`pgraph.c:2387`), so
colour rebinds first and `surface == other` is false when zeta asks. I could not
close the gap between "the decline does not fire in `Swap`" and "`Swap`
measurably moved", and did not fit a fix to the half I could not establish.
#91's arm is the solo/contamination classification that decides which fix is
even the right *shape*.

Note also: neither 165,447 nor 304,750 is correct. Even at 165,447 the quad is
`#E91A24` against the golden's `#E91624`.

---

## Blast radius — `surface.h` checked, and that is why it is untouched

The brief required saying what was checked *before* any edit to `SurfaceShape`.
The check is the reason there is no edit:

- `SurfaceShape` is compared by `memcmp` in `framebuffer_dirty()`, which exists
  **verbatim in both renderers** (`vk/surface.c:117`, `gl/surface.c:997`). A
  field added to the struct changes when *both* renderers consider a framebuffer
  dirty — i.e. surface-binding identity, which is #55's and #60's ground.
- It is also **migration state**: ten `VMSTATE_UINT32` entries in
  `nv2a.c:1572-1581` name `last_surface_shape`'s fields individually, so a new
  field is a vmstate question as well as a renderer one.
- `target->shape` is assigned wholesale on the create path, and a **zeta target
  takes the colour binding's shape entire**, so a new field would have no single
  right source there.

The one real hole reading found — `framebuffer_dirty()` returning false on a
changed shape when `!color_format && !zeta_format` (`surface.c:121-124`) — is in
that shared function, not in the struct. It is left for an arm of its own, and
it is the named world in which #89's inertness leg could have failed.

Also recorded because it cuts against #92's framing: the shape is not wholly
address-blind *in effect*. `clip_x`/`clip_y` feed the target address and they
**are** in the shape.

---

## The probes' lifetime — chosen, not left to omission

Both probes are unconditional in the shipping Android build. That is a choice,
and audit L2 was right that it has to be one: a compile-time gate would also
remove them from the device arms, which are the only place they are ever read.

**They stay until #88's and #91's arms return a verdict, and come out after.**
The condition is written into the comment at `vk/surface.c` so the fold cannot
lose it. #89's probe has already answered its question and is kept only so the
two leave together.

## Build status — no longer an open question

Attempt 1's PR body said the branch was uncompiled and that building it was the
most important next step. **It has since been built and run**: the arms job
compiled both refs into APKs (`808a74e96fee`, `4912782893cd`) and ran them on
the device. Both probes' `__android_log_print` paths, the `#ifdef __ANDROID__`
split and the `HWADDR_PRIx` format strings are all exercised by that run.

The desktop build remains a genuine gap on this host, and with it the Khronos
validation layer — which is what #88's change to framebuffer attachments most
wants, since a colour-only framebuffer and a `pDepthStencilState == NULL`
pipeline are exactly its class. Reading was substituted and is recorded in
#88's prediction; reading is not a run, and no capture can stand in for it
because a validation error need not move a pixel.

## For the fold

Nothing outstanding. `preflight.sh` passes on this branch with no
`--allow-tracker`.

The `nv2a` index **was** regenerated here, and the story is worth keeping
because it is a blocker that expired. Attempt 1 handed it to the fold as
unfixable: the committed index was built from `nxdk_pgraph_tests` at
`91a0de45` while the checkout on this host was `33e7c6b0`, which lacks the
`Surface as vertex array` suite — so regenerating would have written 102 suites
where 103 are committed, *deleting a suite from the issue↔suite map in order to
fix line numbers*.

That was true when written. The checkout is now at `91a0de45`, byte-for-byte
the `tests_commit` the committed index names, so the precondition for a safe
regeneration is met. Verified rather than assumed, because the failure being
avoided is a silent deletion: suite and symbol key sets equal, and every
provenance count unchanged (103 suites, 951 symbols, 2,833 sites, 498 gaps, 145
unread). The diff is line numbers.

**The general lesson, and it cost this lane twice over:** a blocker inherited
from a previous session's notes is a *claim with a date on it*. One comparison
of `provenance.tests_commit` against the checkout was the entire test of this
one. Check the blocker before routing around it.
