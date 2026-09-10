# NV2A pipeline and state ownership

Where the code lives, what owns which state, and what invalidates it.

Read [`vocabulary.md`](vocabulary.md) first — it covers the naming rules and how
a guest method reaches a register. This file covers what happens after that.

## The layers

| layer | path | size | owns |
|---|---|---|---|
| Device | `hw/xbox/nv2a/*.c` | 14 files, 2.6k lines | The engine blocks — `pfifo`, `pcrtc`, `pfb`, `pmc`, `pramdac`, `ptimer`, `pvideo`, `pbus`. MMIO, interrupts, the command FIFO |
| State machine | `hw/xbox/nv2a/pgraph/*.c` | 9 files, 7.0k lines | Method handlers, the PGRAPH register file, texture decode, swizzle, primitive rewriting |
| Translation | `hw/xbox/nv2a/pgraph/glsl/*.c` | 7 files, 4.2k lines | NV2A state to **GLSL source text**. Backend-independent |
| Vulkan backend | `hw/xbox/nv2a/pgraph/vk/*.c` | 21 files, 23.2k lines | The renderer Android actually uses |
| GL backend | `hw/xbox/nv2a/pgraph/gl/*.c` | 10 files, 8.2k lines | Not shipped on Android — see the note below |

**Android runs Vulkan.** `config_spec.yml:230` defaults to `OPENGL`;
`android/app/src/main/cpp/xemu_android.cpp:616` and
`xemu_settings_android.cc:69` override it. A change confined to `gl/` does not
affect the device.

The translation layer is the one people underestimate. NV2A's pixel stage is
fixed-function register combiners with no modern equivalent, so the emulated
behaviour is **compiled into GLSL at runtime** — it lives inside C string
literals and no C analysis tool can see it. `query ident` exists for that.

## Where a change goes

| symptom | layer | start at |
|---|---|---|
| A method does nothing | state machine | `query symbol NV097_...` — is there a `HANDLER` role? |
| State is set but has no effect | state machine | is the register in a category? (see Invalidation) |
| Wrong pixels, right geometry | translation | `glsl/psh.c` — the combiner compiler |
| Wrong geometry | translation | `glsl/vsh*.c`, `pgraph/prim_rewrite.c` |
| Wrong on one renderer only | backend | the mirrored file (below) |
| Right image, wrong texture content | state machine + backend | `pgraph/texture.c` decode, then `vk/texture.c` cache |
| Content that changes when another test runs first | **invalidation** | the three mechanisms below |

## The mirrored-backend contract

`vk/` and `gl/` share twelve filenames:

```
blit  constants  debug  display  draw  meson
renderer  reports  shaders  surface  texture  vertex
```

Same name means same responsibility. Thirteen more are Vulkan-only — command
buffers, submit and compile workers, the image pool, texture dump and replace —
because VK carries machinery GL does not.

**Nothing enforces the mirror.** A fix in `vk/texture.c` usually needs the same
fix in `gl/texture.c`, and the build will not tell you. Verified divergences are
recorded in
[`../investigations/nv2a-sweep-2026-09.md`](../investigations/nv2a-sweep-2026-09.md).

## State ownership

Three caches, three different keys, three different invalidation rules. Most
order-dependence bugs live in the gap between them.

### Texture cache

| | |
|---|---|
| Key | `TextureKey` — 10 fields (`vk/renderer.h:676-687`): shape, VRAM offset and length, palette offset and length, scale, `filter`, `address`, `border_color`, `max_anisotropy` |
| Entry | `TextureBinding` (`vk/renderer.h:724-742`), an `Lru` node |
| Lookup | `lru_lookup(&r->texture_cache, key_hash, &key)` (`vk/texture.c:1443`) |
| Gate | `check_textures_dirty` (`vk/texture.c:1942`) — the whole rebind returns early at `:1986` unless a binding is missing or `pg->texture_dirty[i]` is set |

The gate is the part that bites: **if `texture_dirty[i]` is false, the key is
never recomputed**, so key fields that no handler marks dirty cannot take
effect. Every texture method handler now sets it, `SET_TEXTURE_ADDRESS` and
`SET_TEXTURE_BORDER_COLOR` included, and sets it on every write rather than
only on a changed value: a title that rewrote a texture in place re-sends the
same register values, and that write is the only sign the binder gets. The
draw path (`vk/draw.c`, `any_texture_dirty`) reaches the rebind on that flag
as well as on the generation counters, which only move when a value changes.

### Surface cache

| | |
|---|---|
| Key | **the VRAM address alone** |
| Lookup | VK: `g_hash_table_lookup(r->surface_addr_map, addr)` (`vk/surface.c:1768`). GL: a linear scan on `surface->vram_addr == addr` (`gl/surface.c:1574`) |

Format, dimensions and pitch are validated *after* the hit, not part of the key,
so a mismatch evicts rather than misses. Two backends, two data structures, one
key rule that must stay identical.

### Shader and pipeline caches

Both `Lru`, keyed on a state struct built from PGRAPH registers
(`vk/shaders.c:815`). What refreshes that struct is a generation counter, below.

## Invalidation — three mechanisms, no shared owner

**1. Register categories to generation counters.** `pgraph_reg_w`
(`pgraph.h:333-354`) bumps `shader_state_gen`, `pipeline_state_gen` or
`texture_state_gen` according to `pgraph_reg_category_table`
(`pgraph.c:107-145`). A register in **no** category bumps only `any_reg_gen`,
and nothing downstream regenerates.

**2. `pg->texture_dirty[unit]`.** Per texture unit, set by hand in individual
method handlers. Gates the entire texture rebind.

**3. The VRAM dirty bitmap.** Tracks guest writes to video memory. Six
consumers, no coordination between them, and `memory_region_test_and_clear_dirty`
*consumes* the bit across a whole page:

```
gl/surface.c:2712   memory_region_test_and_clear_dirty(...)
gl/texture.c:517    memory_region_test_and_clear_dirty(...)
gl/vertex.c:66      memory_region_test_and_clear_dirty(...)
vk/texture.c:480    memory_region_test_and_clear_dirty(...)
vk/surface.c:2789   bitmap_test_and_clear_atomic(...)    <- hand-inlined
vk/draw.c:5119      bitmap_test_and_clear_atomic(...)    <- hand-inlined
```

**Two bypass the API**, so grepping the function name finds four of six.

For textures the consumption is coordinated: `check_texture_dirty`
(`vk/texture.c`) passes a hit on to every cached binding over the pages
(`possibly_dirty`), so a 2D texture under a 3D one, or the same bytes bound at
a second format, re-hashes its content whichever binding read the bits. The
bits are read on every bind of a flagged stage, not once per flip; a binding
flagged by another's check is re-hashed even when its own read finds the bits
already clear.

The three mechanisms are independent. State reached through one is invisible to
the other two, and no single place records which state uses which. That is the
shape behind order-dependent rendering: whichever consumer runs first wins.

## The fork's second dispatch path

Beyond upstream's table dispatch there is `method_fast[0x800]`
(`pgraph.c:343-642`) and a **lockless** `pgraph_method_try_fast`
(`pgraph.c:727-793`) that runs without `pgraph.lock`. It arrived in `1666e81`
and is this fork's own.

It is a **second implementation** of some handlers. A handler edited in one
place and not the other silently diverges depending on which path takes the
method — verified for `SET_DEPTH_MASK`, where the fast entry omits the
`write_enabled_cache` update the slow handler performs. When changing a handler,
check `method_fast[]` for an entry at the same address.

## Asking the index

```sh
docs/testing/nv2a_index.py query symbol NV097_SET_TEXTURE_FILTER
docs/testing/nv2a_index.py query suite  "Bump map"
docs/testing/nv2a_index.py query ident  snorm_tex     # struct fields
docs/testing/nv2a_index.py query gaps   "Fog gen"     # known-wrong markers
docs/testing/nv2a_index.py query unread "Fog gen"     # state nothing reads
docs/testing/nv2a_index.py blast hw/xbox/nv2a/pgraph/texture.c
```

`blast` is the one to run before a device measurement: it names the suites that
share code with your change, which is the set that has to be re-measured.

## Asking the shader generator

`query unread` finds state nothing *reads*, by reading the source. The pixel
shader generator can be asked the stronger question directly, because
`pgraph_glsl_gen_psh()` is a pure function of `PshState`:

```sh
cd docs/testing/psh_differ && make
./build/psh-differ                          # every field, every baseline
./build/psh-differ --show 'alphakill[2]=1'  # the diff for one of them
```

Change one field, generate again, compare the text. Byte-identical GLSL means
that state never reached the GPU — which is a defect only if the hardware acts
on it, and only if a baseline actually reached the code path. Both caveats are
in [`../testing/psh_differ/README.md`](../testing/psh_differ/README.md).
