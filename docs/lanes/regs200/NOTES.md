# lane.regs200 -- #200: which PGRAPH bits no method can set, and who reads them

Analysis only. Base `6550967a5e`. Nothing under `hw/` edited. Every table
below comes from `holes.py` in this directory, which reads
`hw/xbox/nv2a/nv2a_regs.h` and `hw/xbox/nv2a/pgraph/pgraph.c` and nothing
else:

```
python3 docs/lanes/regs200/holes.py              # (a) per-register table + (b) widths
python3 docs/lanes/regs200/holes.py --measured   # (c) the three Blend spot_0_ADD rows
python3 docs/lanes/regs200/holes.py --readers    # who reads each hole
```

## Result in one paragraph

The mechanism reproduces all three measured rows from source with no
fitting: every bit where hardware and emulator disagree at the end of
`Blend spot_0_ADD` is a bit no method path can write, and in every case
hardware has it set and we have it clear. That is the only direction the
mechanism allows. **But the renderer reads none of those bits.** Across
`hw/xbox/nv2a` no consumer extracts a hole bit of any register. The only
readers of the whole word use it as an identity: a cache key, a change
check, a hash, or a debug print. So the three disagreements are inert for
pixels in this tree, and they cannot be the source of the 5,412 px
max-delta-1 residual. Two claims in the issue do not survive:

- **The DIMENSIONALITY width mismatch does not explain bits 4-5.** It drops
  bits 2-3 of the *value* (parameter bits 6-7) and never writes register
  bits 4-5. pbkit only sends dimensionality 1-3, so it drops nothing at all.
- **Passing the guest word through would not match hardware either.** The
  guest's word has bits 4-5 = `10` (dim 2); hardware holds `11`.
  Hardware's bits 4-5 come from somewhere other than this method's
  parameter. From source alone that is unexplained.

## What "unreachable" means here, exactly

Four write paths reach `pg->regs_`:

| path | where | writes |
|---|---|---|
| `PG_SET_MASK` in a method handler | `pgraph.c`, 112 calls | read-modify-write of one mask. **Other bits are preserved, never set.** |
| `method_fast[]` `MF_MASKED` / `MF_XLAT` | `pgraph.c:357-661`, applied at `pgraph.c:698` / `729` | same: `SET_MASK(rv, mask_lut[i], p)` |
| `pgraph_reg_w(pg, R, parameter)` / `MF_DIRECT` / `MF_TEX` | e.g. `pgraph.c:4570` | the guest's whole word: **no holes** |
| MMIO `pgraph_write` default case | `pgraph.c:1020-1021` | **any register, whole word**, from the CPU |

So a hole is a bit that **no pushbuffer method** can set. The guest CPU can
still set it with an MMIO store, and after that `PG_SET_MASK` keeps it,
because it only rewrites its own mask. The emulator reads 0 at SURFACE bit 0
and TEXFMT bits 4-5. So on this run no MMIO store set them either.

`vk/draw.c:5319-5330` also stores into `pg->regs_` directly. It saves the
register and puts it back around a queued draw, so it adds no new state.

## (a) Per-register table: registers some method rebuilds from masks

`named` = union of the header's field masks. `cover` = union of every mask a
method writer applies. `holes` = `~cover`: bits no method can set.
Registers with a whole-word writer have no holes and are omitted. There are
94 of them (the texture control, filter, offset, image-rect and address
registers, window clips, combiners, clear values and so on). Run the script
for the full list.

| register | addr | named | cover | holes | writers |
|---|---|---|---|---|---|
| `SURFACE` | `0710` | 20-22,24-26,28-30 | same | **0-19,23,27,31** | `pgraph.c:935` (MMIO INCREMENT), `2276, 2282, 2288, 2297` (FLIP_*), fast `496-500` |
| `TEXFMT0..3` | `1A04..1A10` | 1-3,6-14,16-31 | same | **0,4-5,15** | `pgraph.c:4552-4560` (`SET_TEXTURE_FORMAT`, slot*4) |
| `TEXPALETTE0..3` | `1A34..1A40` | 0,2-3,6-31 | same | 1,4-5 | `SET_TEXTURE_PALETTE` |
| `BLEND` | `1804` | 0-16 | same | 17-31 | fast `510, 562-564, 578-582`, handlers |
| `CONTROL_0` | `194C` | 0-12,14,16-20,22-29 | same | 13,15,21,30-31 | handlers + fast |
| `CONTROL_1` | `1950` | 0,4-31 | same | 1-3 | handlers + fast |
| `CONTROL_2` | `1954` | 0-11 | same | 12-31 | handlers + fast |
| `CONTROL_3` | `1958` | 0,7-9,16-18 | same | 1-6,10-15,19-31 | handlers + fast |
| `SETUPRASTER` | `1990` | 0-3,6-12,21-23,28-29,31 | same | 4-5,13-20,24-27,30 | handlers + fast |
| `SHADERCTL` | `1998` | none | 0-27 (literal `0xFFF`, `0xFFFF000`) | 28-31 | `pgraph.c:4970, 4976`, fast `573` |
| `CSV0_C` | `0FB8` | 8-28,30-31 | same | 0-7,29 | handlers + fast |
| `CSV0_D` | `0FB4` | 0-15,18-28,30-31 | 0-15,18-20,22-28,30-31 | 16-17,**21**,29 | handlers + fast |
| `SHADOWCTL` | `19A4` | 0-2 | same | 3-31 | `pgraph.c:4959`, fast |
| `CHEOPS_OFFSET` | `0FC4` | 0-15 | same | 16-31 | `pgraph.c:5031, 5045`, fast |
| `ANTIALIASING` | `1800` | 0 | same | 1-31 | fast |
| `ZCOMPRESSOCCLUDE` | `1A84` | 4 | same | 0-3,5-31 | handler |
| `FOGCOLOR` | `1980` | 0-31 | 0-31 | none | handler |
| `TRAPPED_ADDR` | `0704` | 0-12,16-18,20-24,28 | 0-12,16-18,20-24 | 13-15,19,25-31 | trap bookkeeping, not a method |
| `RDI_INDEX` | `0750` | 2-12,16-24 | 2-12 | 0-1,13-31 | MMIO auto-increment only; the guest writes it whole over MMIO |

`CSV0_D` bit 21 is the only **named** field in a method register that no
method writes (`CSV0_D_FOG_MODE`). Its only mention outside the header is the
`FIXME` comment at `pgraph.c:2640`. Nothing reads it.

## (b) Width mismatches: method field vs register field

From `PG_SET_MASK(reg, NV_PGRAPH_F, GET_MASK(parameter, NV097_G))` where
`|F| != |G|`:

| site | method field | register field | what is lost | reaches a measured bit? |
|---|---|---|---|---|
| `pgraph.c:4555` | `SET_TEXTURE_FORMAT_DIMENSIONALITY` `0xF0` (4) | `TEXFMT0_DIMENSIONALITY` `0xC0` (2) | value bits 2-3 (= parameter bits 6-7). pbkit sends 1..3 (`texture_stage.cpp:535`), so nothing | **no.** `SET_MASK` shifts the value to bit 6; register bits 4-5 are never a destination |
| `pgraph.c:4556` | `SET_TEXTURE_FORMAT_COLOR` `0xFF00` (8) | `TEXFMT0_COLOR` `0x7F00` (7) | value bit 7 (parameter bit 15). Largest defined format is `0x41` | no (bit 15 equal on both sides) |
| `pgraph.c:4552` | `SET_TEXTURE_FORMAT_CONTEXT_DMA` `0x3` (2) | `TEXFMT0_CONTEXT_DMA` bit 1 (1) | by design: stored as `== 2` | no |
| `pgraph.c:5018` | `SET_TRANSFORM_EXECUTION_MODE_RANGE_MODE` `0xFFFFFFFC` (30) | `CSV0_D_RANGE_MODE` bit 18 (1) | parameter bits 3-31 (values are 0/1) | no |

A second, larger class the script also prints: 37 sites store the whole
`parameter` into a 1- to 16-bit field, e.g. `SET_BLEND_ENABLE` into
`BLEND_EN`. `SET_MASK` keeps the value's low bits, so a boolean sent as `2`
reads as off. That is a truncation, not a hole. None of the measured rows
touch it and it is not ranked below.

## (c) The measured rows, reproduced (the falsifier)

A bit is **explained** if it is a hole, hardware holds 1 and the emulator
holds 0. That is the only difference the mechanism can produce. Any other
differing bit is **unexplained**.

| register | snapshot | hw | emu | differing bits | explained (hole) | unexplained |
|---|---|---|---|---|---|---|
| `SURFACE` | before | `30100001` | `30100000` | 0 | **0** | none |
| `SURFACE` | after | `30200001` | `30200000` | 0 | **0** | none |
| `TEXFMT0` | before | `089104B8` | `0AA1068A` | 1,4-5,9,20-21,25 | **4-5** | 1,9,20-21,25 |
| `TEXFMT0` | after | `08813AB8` | `08813A88` | 4-5 | **4-5** | none |
| `TEXFMT1` | before | `000105B8` | `0881198A` | 1,4-5,10-12,23,27 | **4-5** | 1,10-12,23,27 |
| `TEXFMT1` | after | `09913AB8` | `09913A88` | 4-5 | **4-5** | none |

All three rows the brief names (SURFACE bit 0; TEXFMT0 and TEXFMT1 bits 4-5)
come out exactly. Across all 12 register values, no hole bit is ever set on
the emulator side.

**Reported, not absorbed:** the *before* snapshots of TEXFMT0/1 also differ
in bits 1, 9-12, 20-21, 23, 25 and 27. The source table in
`emulator-vs-hardware-registers.md` lists only the *after* XOR as the
differing bits. These bits are `CONTEXT_DMA`, `COLOR` and
`BASE_SIZE_U/V`: named and method-written, so every one of them is
reachable. They are two different textures bound at capture time (emulator
DMA B, 1024x1024 `0x06`; hardware DMA A, 512x256 `0x04`), not a hole. This
mechanism does not explain them. They are prior-state differences at the
`Initialize()` capture point.

**Hardware side, unexplained:** hardware holds TEXFMT bits 4-5 = `11` in all
four values: two registers, before and after, three different textures.
From the emulator's `after` value the guest word is `0x08813A29`: DMA A,
border colour, dim 2, `SZ_A8B8G8R8`, 1 level, 256x256. Its bits 4-5 are `10`
and bit 0 is `1`. Hardware holds bit 4 set and bit 0 clear, so its bits 4-5
are not the parameter's bits 4-5. SURFACE bit 0 is likewise in no `FLIP_*`
parameter's field. A constant, texture-independent value looks like a reset
value or internal state, but nothing in this tree can decide that. Only a
hardware map can.

## Read-by-renderer column

The script's `--readers` mode finds every read of each hole register in
`hw/xbox/nv2a/**` (`pgraph_reg_r`, `pgraph_vk_reg_r`, `PG_GET_MASK`). For
each whole-word read into a local it follows every use to the end of the
block, and reports any use that is not `GET_MASK(x, NAMED)` or
`x & NAMED`. The remaining uses were then classified by hand:

| register | hole bits | interpreted by a consumer? | whole-word uses (identity only) |
|---|---|---|---|
| `TEXFMT0..3` | 0,4-5,15 | **no** (`texture.c:178-365`, `psh.c:58,370`, `vk/renderer.c:1291` all extract named fields) | `vk/renderer.c:1181` state fingerprint, `vk/texture.c:2794` reg cache compare, `vk/display.c:1612` signature hash, `vk/texture.c:2703` and `vk/renderer.c:2092` debug prints |
| `SURFACE` | 0-19,23,27,31 | **no** (`pfifo.c:1273` extracts `READ_3D`/`WRITE_3D`/`MODULO_3D`) | none |
| `BLEND` | 17-31 | **no** guest bit is read, **but `vk/draw.c:607-648` stores a synthetic field at bits 18-19** (`NV2A_VK_BLEND_PAD_ALPHA`, #59) in the *effective* value. It is safe only because those bits are holes | `q->dyn_blend` snapshots/compares, `vk/renderer.c:1156` fingerprint |
| `CONTROL_0..3`, `SETUPRASTER` | see (a) | **no** | `q->dyn_*` / `e->dyn_*` snapshot and compare (`vk/draw.c:4977-5166, 5596-5604, 6564-6627`), `r->dyn_state` compare (`vk/draw.c:4546-4726`), `vk/renderer.c:1097-1101, 1156`, assert `vk/draw.c:7986-7988` |
| `SHADERCTL` | 28-31 | **no**: `psh.c:277` copies the word, `psh.c:3850-3857` reads bits 0-11 and 16-23 | none |
| `CSV0_C`, `CSV0_D` (incl. named bit 21), `TEXPALETTE0..3`, `SHADOWCTL`, `CHEOPS_OFFSET`, `ANTIALIASING`, `ZCOMPRESSOCCLUDE` | see (a) | **no** | none |
| `TRAPPED_ADDR`, `RDI_INDEX` | see (a) | not method registers; `RDI_INDEX_SELECT` is read at `pgraph.c:836, 947` but written whole by guest MMIO | none |

An identity use can only see a bit that changes. A hole is a constant 0,
so for every row above the hole is inert today. It stops being inert only
if a code lane makes it writable: then the keys and compares would see it
(more cache misses), and still no pixel would change until some consumer
extracts it.

**Nothing on the list is read by the renderer.** That is the result.

The scanner does not see reads through a computed register expression
other than `BASE + i*4`, or through `pg->regs_[...]` indexing. A grep of
`regs_[` in `hw/xbox/nv2a` finds only `pfifo.c:1262` (`FIFO`),
`gl/draw.c:331` (`COLORCLEARVALUE`, whole-word written) and the
`vk/draw.c:5319-5330` save/restore. None of these reads a hole register's
bits.

## Hunks for a code lane, ranked by whether a consumer reads the bit

Named, not edited. Before touching either file, merge master, or PR #368's
branch, which releases `pgraph.c` and `nv2a_regs.h`.

No hunk ranks above "identity only", because no consumer interprets a hole
bit. Ranked by the most a change could affect:

1. **`hw/xbox/nv2a/pgraph/vk/draw.c:607-648`**, the `NV2A_VK_BLEND_PAD_ALPHA`
   synthetic field at BLEND bits 18-19. This is the only code that *depends*
   on a hole. Any change that makes BLEND bits 17-31 reachable (a whole-word
   store, or a new named field there) collides with it. The compile-time
   assert at `vk/draw.c:616-626` checks only `NV2A_VK_BLEND_PAD_ALPHA_DEFINED_BITS`,
   so a whole-word store would not trip it. Do this first if anyone widens
   BLEND.
2. **`hw/xbox/nv2a/nv2a_regs.h:606-617` + `pgraph.c:4528-4563`** (`TEXFMT0`,
   bits 0,4-5,15). Identity readers only. A fix needs a hardware value to
   copy, and the guest word is not it (bits 4-5 would come out `10`, not
   `11`). So there is **no source-only fix that matches hardware**. Do not
   "pass the parameter through". It is refuted above and would only add
   cache misses.
3. **`nv2a_regs.h:265-268` + `pgraph.c:2274-2300`, fast `496-500`**
   (`SURFACE` bit 0). Read by nothing but `pfifo.c:1273`'s named fields. No
   method parameter carries it. Inert.
4. **`pgraph.c:4555`** (DIMENSIONALITY 4 to 2 bits) and **`4556`** (COLOR 8 to 7
   bits). Truncations that drop no bit for any value the tests send. Name
   them in a comment if anything. They explain no measured bit.
5. Everything else in table (a) (`CONTROL_*`, `SETUPRASTER`, `CSV0_*`,
   `SHADERCTL`, `TEXPALETTE*`, `SHADOWCTL`, `CHEOPS_OFFSET`,
   `ANTIALIASING`, `ZCOMPRESSOCCLUDE`): holes read by nothing, or by
   identity compares only. Bottom of the list. `CSV0_D_FOG_MODE` (bit 21)
   is named and never written, and never read.

## What the next lane should not repeat

- Do not chase #38's one-step residual through these registers. With no
  consumer reading the bits, a pixel cannot depend on them in this tree.
  If you want an arm to confirm it, a control that **must** move is needed
  first. See the `inert-control-is-not-a-measurement` memory.
- Do not treat "the method field is wider than the register field" as
  explaining a register bit. `SET_MASK` shifts the value to the field's low
  bit. A wider method field loses **high value bits**, and they land
  nowhere.
- The register-diff table's "bits" column is the *after* XOR only. The
  *before* snapshots differ in reachable fields because the two sides had
  different textures bound at `Initialize()`. Compare both snapshots before
  calling a bit structural.
- If the region-diff tool needs to stop reporting these rows, mask the known
  holes in the *comparator*, not by setting reset values in the emulator.
  Setting a reset value to make a diff go away is fitting.
