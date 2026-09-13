# Every guest memory barrier is elided on this machine

Verified in source 2026-09-12, independently by an agent and then by me. This
is a root cause shared by several issues that have been investigated
separately, and it explains a host asymmetry we had already measured without
understanding.

## The patch

`tcg/tcg-op.c`, `tcg_gen_mb()`. Upstream has three branches; the fork added the
middle one in `1d8a51aff9` ("tcg: eliminate unnecessary ARM64 memory barriers
for single-CPU Xbox"):

```c
#ifdef CONFIG_USER_ONLY
    bool parallel = tcg_ctx->gen_tb->cflags & CF_PARALLEL;
#elif defined(XBOX)
    /* Xbox has a single CPU and never sets CF_PARALLEL.  All I/O device
     * threads (NV2A, APU, etc.) access guest memory through the QEMU
     * memory API or under BQL, which provides its own ordering.
     * Eliding per-instruction DMB barriers saves ~30-50 cycles per
     * guest memory operation on ARM64. */
    bool parallel = tcg_ctx->gen_tb->cflags & CF_PARALIEL;
#else
    /* It is tempting to elide the barrier in a uniprocessor context.
     * However, even with a single cpu we have i/o threads running in
     * parallel, and lack of memory order can result in e.g. virtio
     * queue entries being read incorrectly. */
    bool parallel = true;
#endif
```

(The `CF_PARALIEL` above is a transcription slip in this document, not in the
tree — the code reads `CF_PARALLEL`.)

**Upstream's own comment, in the branch the fork bypassed, warns about exactly
this hazard.**

## CF_PARALLEL is never set here

- `accel/tcg/tcg-accel-ops-rr.c:324` — `tcg_cpu_init_cflags(cpu, false)`
- `accel/tcg/tcg-accel-ops-mttcg.c:280` — `tcg_cpu_init_cflags(cpu, smp.max_cpus > 1)`, and an Xbox has one CPU
- `accel/tcg/tcg-accel-ops.c:67` — `cflags |= parallel ? CF_PARALLEL : 0`

So under `XBOX`, `tcg_gen_mb()` emits **nothing, unconditionally**, in both TCG
modes. That includes the `TCG_MO_LD_ST | TCG_MO_ST_ST` that
`tcg_gen_req_mo` requests on every guest store to hold x86's TSO on a weak
host. `guest_mo` is unpatched and x86 is `TCG_MO_ALL & ~TCG_MO_ST_LD`, so those
barriers are genuinely requested and then dropped.

## The justification in the commit is false for the NV2A

"All I/O device threads access guest memory through the QEMU memory API or
under BQL" does not hold. `pfifo_thread` (`hw/xbox/nv2a/nv2a.c:521`) and the
`pgraph.vk.render` thread read guest RAM with **bare loads** off
`d->vram_ptr` — for example `vk/texture.c:228` and `:291`. Nothing mediates
the guest's individual texel stores.

The guarantee *assumed* by that design is x86 store-store ordering. The
guarantee *provided* on aarch64 since `1d8a51aff9` is none.

## Why the host asymmetry is provable rather than statistical

On x86-64, `TCG_TARGET_DEFAULT_MO` already contains store-store, so
`tcg_gen_req_mo` masks the request to zero and `tcg_gen_mb` is never called —
**the patch is a no-op on the desktop lane by construction.** On aarch64
`TCG_TARGET_DEFAULT_MO = 0`, so the barrier is required and elided.

One commit therefore predicts exactly what we measured on #44 before knowing
the cause: **20 of 20 desktop runs byte-identical, ~46% failures on the Nova.**

## Why the corruption is permanent rather than transient

A store-visibility race would normally self-heal on the next frame. It does not
here because `check_texture_dirty` (`vk/texture.c:508-527`) test-and-**clears**
the dirty evidence and bakes the result into `snode->hash` (`:1692`). The torn
read is latched into the cache key, so the stale texels persist until something
else invalidates them. That is why #44's failure masks are stable within a run
and why the frontier never advances.

## Issues this plausibly subsumes

Stated as a hypothesis with its own falsifier, not as a conclusion:

- **#44** — the texture-upload race. Directly explained.
- **#39** — "a draw's result is intermittently lost, same disc and binary".
  Same class: a device thread reading guest RAM that is not yet coherent.
- **#51's run-to-run variance** — had a separate confirmed cause (undefined
  behaviour from a cube view against a 2D shader declaration, fixed), so this
  is a test of whether any variance *remains* there after that fix.
- The intermittent `SIGABRT` inside the validation layer via
  `pgraph_vk_clear_surface`, seen twice in `W buffering` at different tests.
- Possibly audio: `hw/xbox/mcpx/apu/**` reads guest RAM from its own thread and
  is exposed by the same mechanism.

**The falsifier for the general claim:** if #44 goes green and #39 plus #51's
residual variance stay equally noisy, then the specific fix worked and the
general device-thread publication account is wrong.

## The cost, which is the whole decision

Reverting restores roughly one `dmb ish` per guest memory operation. The fork's
own comment claims the elision saves 30–50 cycles per guest memory operation on
ARM64, so this is a whole-emulator throughput cost — plausibly tens of percent
on memory-heavy code, not a per-handoff cost. That is a product decision on a
handheld, and it needs a measured number rather than an estimate.

A narrower option, recorded and deliberately not yet implemented:

```c
bool parallel = (mb_type & TCG_MO_ST_ST) ? true
                                         : (tcg_ctx->gen_tb->cflags & CF_PARALLEL);
```

That restores store-store only — enough for device threads to see coherent
texture, vertex and surface writes, at about half the barrier sites — but it
does **not** restore full TSO, so guest loads racing device writes (surface
downloads, reports and notifies) stay exposed.

Sequencing: full revert first to confirm the prediction, then measure the cost,
then narrow only if the cost demands it. Narrowing before confirming would
leave two variables moving at once.

---

## MEASURED: the full revert costs 44% of frame time

A/B/A/B on the Nova, Galleon, 240 s per arm with the first quarter discarded,
alternating so thermal drift cannot be confounded with arm order.

| arm | gfps | game frame ms | renderer idle ms | Tq | `mb_emitted` |
|---|---:|---:|---:|---:|---:|
| A1 barriers elided | 18.0 | 53.00 | 26.90 | 212 | **0** |
| B1 barriers restored | 14.0 | 70.40 | 44.05 | 203 | **347,473** |
| A2 barriers elided | 18.0 | 52.00 | 27.30 | 224 | **0** |
| B2 barriers restored | 14.0 | 70.40 | 43.50 | 204 | **347,446** |

**+34.1% game frame time (52.50 → 70.40 ms), throughput 18.0 → 14.0 gfps.**

CORRECTION: an earlier version of this file said +44% and −31%. That came from
reading B1 while it was still running, on 42 of its eventual 46 samples, where
its median stood at 75.60 ms. The completed run settles at 70.40 ms. The
conclusion is unchanged and the mistake is the same class as several others
recorded here -- quoting a number before the thing producing it had finished.

Three checks that make the number trustworthy rather than suggestive:

- **The arms are provably different binaries.** `mb_emitted` is exactly 0 on
  both A arms and 346,418 on B. That counter exists precisely because the
  worst failure mode here is measuring one binary twice — the change is a
  header plus a codegen file in a shared tree, and a build that silently
  missed it would produce a clean, plausible, meaningless result.
- **Thermal drift is not the explanation.** The two A arms agree to 1.00 ms and
  the two B arms to **0.00 ms**, against a 17.90 ms A↔B delta. Had thermal
  drift dominated, the within-arm spread would be comparable to the between-arm
  one. It is roughly twenty times smaller.
- **The workload is the same on both sides.** `Tq` — dirty-bitmap
  test-and-clear calls per frame, a property of the workload rather than of
  barriers — is 212/224 against 200.

Two caveats stated rather than buried. The arms report `Ul:N`, so the frame
limiter was not bypassed even though `unlock_framerate` defaults true; at 18
fps the guest is far below any cap so the limiter is not the binding
constraint and game-frame time remains a valid throughput measure, but the
plan's unlock-mode condition was not actually met. And `Ri` shows the renderer
idle for roughly half of every frame in **both** arms, so this title is
guest-bound — which is exactly where a barrier-per-memory-operation bites
hardest. One title is not a library, and a renderer-bound title would show
less.

## Consequence: the full revert does not land

34% is far outside the ~3% threshold set in advance for "the claimed 30–50
cycles per operation does not translate into user-visible cost, so just land
it". So the decision moves to the narrow variant, which was written down before
any of this was measured and deliberately not implemented until the full
revert had answered the correctness question on its own:

```c
bool parallel = (mb_type & TCG_MO_ST_ST)
                    ? true
                    : (tcg_ctx->gen_tb->cflags & CF_PARALLEL);
```

Store-store only — about half the sites, and the half a device thread needs in
order to see a coherent texture, vertex buffer or surface. It does **not**
restore full TSO: guest loads racing device writes (surface downloads, reports,
notifies) stay exposed, and if those matter the answer is a targeted fence at
those sites rather than a blanket one in the code generator.

Tagged `exp-54-stst-only`. Its two measurements are queued: `Texture_border`
failing **0 of 10** runs against a ~46% base rate, and a perf arm to price it.
Sequencing the narrow variant second was deliberate — measuring it first would
have left two questions moving at once, whether store-store is sufficient for
correctness and whether its cost is acceptable.

---

## RETRACTED: the guest's stores are not the problem

Measured. The store-store variant (`exp-54-stst-only`) left `2D_BorderTex_SZ`
at **6 failures in 10 runs** against a ~46% base rate — no improvement at all.

And it restored more than its name suggests, which is what makes this
conclusive rather than inconclusive. `tcg_gen_req_mo` (`tcg/tcg-op-ldst.c`)
asks for its orderings as **sets**, one call per access:

    guest store   tcg_gen_req_mo(TCG_MO_LD_ST | TCG_MO_ST_ST)   :312, :429
    guest load    tcg_gen_req_mo(TCG_MO_LD_LD | TCG_MO_ST_LD)   :261, :369, :570

so a test on `ST_ST` is true for **every** guest store, and the barrier is then
emitted carrying the whole set. Both store-side orderings were restored. The
corruption survived untouched.

**So this file's original mechanism — "the guest's texel stores becoming
visible out of order among themselves" — is false.** It was plausible, it
explained the latching, and it is wrong.

What survives from the original account, because it rests on source rather than
on that mechanism: the `#elif defined(XBOX)` branch exists, `CF_PARALLEL` is
never set for this machine, `tcg_gen_mb` therefore emits nothing, device
threads read `vram_ptr` with bare loads, and the commit's justification about
the memory API and BQL is false for the NV2A. All still true. Only the
*explanation of how that produces #44* is retracted.

## What the failure narrows it to

`TCG_TARGET_DEFAULT_MO` is `0` on aarch64 (`tcg/aarch64/tcg-target-mo.h:10`)
and `TCG_MO_ALL & ~TCG_MO_ST_LD` on x86 (`tcg/i386/tcg-target-mo.h:17`).

Read that carefully against the request sets above. On x86, a guest **store**'s
`LD_ST|ST_ST` is masked to nothing and no barrier is emitted — so x86 never
had store ordering barriers here either, which is consistent with store
ordering not being the defect. A guest **load**'s `LD_LD|ST_LD` masks down to
`ST_LD`, which survives: **store-load is the one ordering x86 does not supply
natively, and therefore the only barrier an x86 host actually emits.**

That states the asymmetry exactly rather than approximately:

| | store barriers emitted | store-load emitted | #44 |
|---|---|---|---|
| x86 desktop | no (masked) | **yes** | 0 of 20 runs |
| aarch64, XBOX branch | no (elided) | **no** (elided) | ~46% of runs |
| aarch64, store-store variant | yes | no | 6 of 10 runs |

The only column that tracks the defect is store-load.

## The third variant, and its falsifier

`exp-54-x86-equivalent` emits when the requested set contains `TCG_MO_ST_LD`,
making this host no weaker than the one where the defect does not reproduce.
Predicted: **0 of 10**, at a cost below the full revert's +34.1% because it
fires on one bit rather than all of them.

**If this also fails**, then between them the two cheap variants have ruled out
every ordering x86 supplies, the elision is not the cause of #44, and the
desktop asymmetry needs a different explanation — different renderer paths,
different timing, or something not about memory ordering at all. That would be
a larger correction than this one and it should be taken seriously rather than
patched around.

Sequencing, stated because it is doing real work here: the full revert asks
whether restoring everything is sufficient; store-store asked whether the store
side alone is; this asks whether x86-equivalence is. Each answer narrows the
next, and none of them would have been interpretable measured together.

---

# RETRACTED IN FULL: the barrier elision does not cause #44

**Restoring every guest memory barrier leaves `2D_BorderTex_SZ` at 6 failures
in 10 runs** — indistinguishable from the ~46% base rate and identical to the
store-store variant. Per run: 28, 68 px fail, pass, pass, 32 px, pass, 6 px,
pass, 52 px, 517 px.

| variant | `mb_emitted` | game frame ms | #44 failures |
|---|---:|---:|---|
| barriers elided (baseline) | 0 | 52.50 | 11/24 (~46%) |
| store-store only | 80,411 | 54.90 (+4.6%) | 6/10 |
| **full revert** | **347,473** | **70.40 (+34.1%)** | **6/10** |

This was the falsifier written down before any of it was measured, and it
fired. **The elision is not the cause of #44.** The `exp-54-x86-equivalent`
arm was cancelled unrun: it emits a strict subset of the full revert's
barriers, so it cannot pass a test the full revert failed.

## What still stands, and it is not nothing

Every claim resting on source rather than on the causal link:

- The `#elif defined(XBOX)` branch exists and `CF_PARALLEL` is never set for
  this machine, so `tcg_gen_mb()` emits nothing.
- **Upstream's own comment, in the branch the fork bypassed, warns about
  exactly this class of hazard** — i/o threads running in parallel with a
  single CPU.
- The commit's justification is false for the NV2A: `pfifo_thread` and
  `pgraph.vk.render` read `vram_ptr` with bare loads, through neither the QEMU
  memory API nor the BQL.
- The cost of putting it back is now measured precisely rather than estimated:
  +34.1% for everything, +4.6% for store-store alone.

So #54 remains a real latent correctness issue with **no demonstrated
symptom**. That is a weaker claim than it was filed with and it should be
carried as such, not quietly kept at its original strength.

## What this breaks, and it is the part to take seriously

The desktop/Nova asymmetry was the strongest evidence in this file: 20 of 20
byte-identical on x86 against ~46% failures on the Nova, from one commit that
is provably a no-op on x86. That argument is now known to prove something
other than what it was used for, because restoring the barriers on the Nova
changes nothing.

**The comparison never controlled for the renderer.** The desktop lane runs
lavapipe, a software rasteriser; the Nova runs Turnip on Adreno. Those two
arms differ in host memory model *and* renderer *and* timing *and* driver, and
the elision was only the difference anyone had a mechanism for. The 2,782 px
uniform `(0, −1, −1)` residual on every desktop run — lavapipe rounding two
channels down where Adreno does not — is direct evidence that the renderers
are not interchangeable, and it was sitting in the same measurement the whole
time.

So #44's cause is open again, and the honest position is that the host
asymmetry is unexplained rather than explained. Candidates that the elision
was crowding out, none of them measured:

- a renderer-side race in the Turnip/Adreno path that lavapipe's serialisation
  hides;
- timing: the Nova is roughly 3x slower per frame, so any window widens;
- the texture upload path's own synchronisation, independent of guest memory
  ordering — note the failure *magnitudes* here (6 to 517 px) are smaller and
  more variable than the 136 px originally recorded, which itself wants
  explaining.

What does not change: the frontier being monotone, the twelve nested masks,
the stale texels being this texture's own pass-1 content, and the two swatches
failing independently. Those are measurements of #44 and they survive intact.
Only the cause is gone.
