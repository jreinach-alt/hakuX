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
| A2 barriers elided | 18.0 | 52.00 | 27.30 | 224 | **0** |
| B1 barriers restored | 12.5 | 75.60 | 47.55 | 200 | **346,418** |

**+44% game frame time, −31% throughput.**

Three checks that make the number trustworthy rather than suggestive:

- **The arms are provably different binaries.** `mb_emitted` is exactly 0 on
  both A arms and 346,418 on B. That counter exists precisely because the
  worst failure mode here is measuring one binary twice — the change is a
  header plus a codegen file in a shared tree, and a build that silently
  missed it would produce a clean, plausible, meaningless result.
- **Thermal drift is not the explanation.** The two A arms agree to 1 ms while
  A↔B differs by 23 ms. Had the ordering effect dominated, A1 and A2 would
  differ by something comparable to the A↔B delta.
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

44% is far outside the ~3% threshold set in advance for "the claimed 30–50
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
