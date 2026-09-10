# NV2A vocabulary

The controlled terms this project uses in code, issues and
[`nv2a_index.py`](../testing/nv2a_index.py). Every claim here was read out of
the tree and is cited; nothing is inherited prose.

If you are tracing a defect, read this first — the naming rules below turn a
symbol into its handler mechanically, which is otherwise five greps.

## The two families

`hw/xbox/nv2a/nv2a_regs.h` defines everything, in two families that are easy to
confuse because they describe the same hardware from opposite ends.

| family | what it is | example |
|---|---|---|
| `NV097_*` | A **method** — a byte offset in the Kelvin class 0x97 command space, pushed by the guest through the FIFO. Not an MMIO address. | `NV097_SET_TEXTURE_FILTER = 0x1B14` (`nv2a_regs.h:1245`) |
| `NV_PGRAPH_*` | A **register** in PGRAPH's own file, which is where the emulator keeps the state a method wrote. | `NV_PGRAPH_TEXFILTER0 = 0x19F4` (`nv2a_regs.h:561`) |

The guest never writes `NV_PGRAPH_*` directly. It pushes methods; handlers
translate them into register writes. A defect is usually in that translation,
which is why both names matter and why they are not interchangeable.

### Indentation encodes the hierarchy

`nv2a_regs.h` uses `#define` depth as structure. It is load-bearing:

```c
#define NV_PGRAPH_TEXFILTER0                          0x000019F4   /* register  */
#   define NV_PGRAPH_TEXFILTER0_CONVOLUTION_KERNEL    0x0000E000   /* field mask */
#       define NV_PGRAPH_TEXFILTER0_..._QUINCUNX               1   /* enum value */
```

A field is a **mask**, never a mask plus a shift constant, because
`GET_MASK(v, mask)` derives the shift from the mask itself
(`nv2a_regs.h:25`, via `ctz32`). `SET_MASK` (`:27`) is the inverse, and
`PG_SET_MASK` (`pgraph.c:40`) is the read-modify-write wrapper over a register.

So a *field* has no address of its own. When an issue says "state bit", it means
one of these masks, and the thing to grep for is the mask name.

## How a guest write becomes a pixel

The chain, with the rule for each hop.

**1. Method reaches PGRAPH.** The FIFO hands over `(method, parameter)`.

**2. Method to table slot.** `METHOD_ADDR_TO_INDEX(x) = (x) >> 2`
(`pgraph.c:724`, `:1332`). Methods are dword-addressed, so the dispatch table is
a quarter the size of the address space.

**3. Slot to handler.** `METHOD_FUNC_NAME(gclass, name)` expands to
`pgraph_<gclass>_<name>_handler` (`pgraph.c:1336-1337`). So the handler for
`NV097_SET_TEXTURE_FILTER` is always `pgraph_NV097_SET_TEXTURE_FILTER_handler`,
with no exceptions — that is the rule that makes handlers findable.

**The catch:** the handler name is produced by token pasting, so the full symbol
`NV097_SET_TEXTURE_FILTER` **never appears as text** at the handler.
`DEF_METHOD(NV097, SET_TEXTURE_FILTER)` is what you will find. Grepping the
symbol misses every handler in the emulator; `nv2a_index.py` reconstructs them.

**4. The method list.** `pgraph/methods.h.inc` is a pure X-macro list, included
**three times** by `pgraph.c` (lines 1356, 1410, 1429) with different
`DEF_METHOD*` bindings — prototypes, table initialisers, range-end constants.

It is **hand-maintained**. There is no generator and no meson target for it, so
adding a method means three coordinated edits, four if the fast path also needs
an entry.

**5. Handler writes a register.** Multi-unit methods carry the unit in the
address, at a stride the handler divides out:

```c
DEF_METHOD(NV097, SET_TEXTURE_FILTER)              /* pgraph.c:3700 */
{
    int slot = (method - NV097_SET_TEXTURE_FILTER) / 64;
    ...
}
```

Register slots are `+ slot * 4`; method slots are `+ slot * <stride>`. The two
strides differ and mixing them up is a whole class of bug.

**6. The register write bumps a generation counter.** This is the hop most
people miss. `pgraph_reg_w` (`pgraph.h:333-354`) looks the register up in
`pgraph_reg_category_table` and, if it changed, bumps a counter by category:

| category | counter | meaning |
|---|---|---|
| `REG_CAT_SHADER` | `shader_state_gen` | the emitted GLSL may need regenerating |
| `REG_CAT_PIPELINE` | `pipeline_state_gen` | the graphics pipeline may need rebuilding |
| `REG_CAT_TEXTURE` | `texture_state_gen` | texture bindings may need re-evaluating |

Categories are assigned in `pgraph_init_reg_category_table` (`pgraph.c:107-145`).
A register can be in several — `NV_PGRAPH_TEXFILTER0` is in both `SHADER`
(`:131`) and `TEXTURE` (`:141`).

**A register in no category bumps only `any_reg_gen`.** Nothing downstream
regenerates. That is not a hypothetical: `NV_PGRAPH_WINDOWCLIPX0`/`Y0` are
written at `pgraph.c:2249`/`:2257` and appear in no category, while the clip
region *count* is compiled into the shader source as a loop bound
(`glsl/psh.c:1067`). See
[`../investigations/nv2a-sweep-2026-09.md`](../investigations/nv2a-sweep-2026-09.md).

So: **if you add state that the shader or pipeline reads, put its register in a
category, or it will be silently stale.**

## Worked example, end to end

Setting the texture filter on unit 2:

```
guest pushes method 0x1B94
  = NV097_SET_TEXTURE_FILTER (0x1B14) + 128            nv2a_regs.h:1245
  stride 64  ->  slot = 128 / 64 = 2                   pgraph.c:3702
METHOD_ADDR_TO_INDEX(0x1B94) = 0x1B94 >> 2 = 0x6E5     pgraph.c:724
  -> pgraph_NV097_SET_TEXTURE_FILTER_handler           pgraph.c:1336, :3700
writes NV_PGRAPH_TEXFILTER0 + 2*4 = 0x19FC             nv2a_regs.h:561
  category SHADER | TEXTURE                            pgraph.c:131, :141
  -> shader_state_gen++, texture_state_gen++           pgraph.h:341-348
```

Ask the index for any of it:

```sh
docs/testing/nv2a_index.py query symbol NV097_SET_TEXTURE_FILTER
```

## Terms the index emits

`nv2a_index.py` classifies each reference. These are the words to use in issues
so a search finds both the code and the discussion.

| role | means |
|---|---|
| `HANDLER` | the `DEF_METHOD*` line implementing a method |
| `DECL` | its declaration in `methods.h.inc` |
| `TABLE-ENTRY` | a designated-initializer row in a format or dispatch table |
| `DISPATCH` | a `case` branching on the symbol |
| `READ` / `WRITE` | `GET_MASK` / `SET_MASK` / `pgraph_reg_r` / `pgraph_reg_w` |
| `STUB` | an `NV2A_UNIMPLEMENTED` site |
| `REF` | any other mention |
| `COMMENT` | the mention is in prose, not code |

And for known-wrong markers (`query gaps`), ordered by scarcity:

| kind | means |
|---|---|
| `HEDGE` | an unmarked guess in prose — *"R is probably unsigned"*. Carries no marker, so nobody will ever grep for it |
| `STUB` | `NV2A_UNIMPLEMENTED`, which compiles to a no-op (`debug.h:67`) and does not even log |
| `MARKED` | `FIXME`, `TODO`, `XXX`, `HACK` |
| `ABORT` | `assert(false)`, `assert(!"...")`, `abort()`. Always live — `NDEBUG` is an `#error` (`osdep.h:311`) |

## Other names worth knowing

| term | meaning |
|---|---|
| **suite** | A group in `nxdk_pgraph_tests`, e.g. `Bump map`. Spelled with spaces in source, underscores in the results directory; the index carries both |
| **site** | One `file.c:line` where a symbol is referenced |
| **backend** | `pgraph/vk/` or `pgraph/gl/`. Android runs **Vulkan** — `xemu_android.cpp:616` overrides the `OPENGL` default in `config_spec.yml:230` |
| **fast path** | `method_fast[]` (`pgraph.c:343-642`) and the lockless `pgraph_method_try_fast` (`:727`). Fork-introduced, and a second implementation of some handlers |
