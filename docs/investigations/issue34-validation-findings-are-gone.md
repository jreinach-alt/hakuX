# #34's four open validation findings are gone, and the disc that crashed the layer now runs

#34 recorded five findings from the Khronos validation layer, one fixed and
four open, at roughly **35,208 messages** on one run of `Clear`. All four open
ones are now absent, measured rather than inferred.

## Same layer version, so the comparison is like for like

The issue names `vulkan-validationlayers` **1.3.275**. Installed here:

```
ii  vulkan-validationlayers:amd64   1.3.275.0-1   Vulkan validation layers
VkLayer_khronos_validation.json -> VK_LAYER_KHRONOS_validation  api_version 1.3.275
```

Same version, same renderer, same host. That matters: "zero findings" from a
*different* layer build would be a statement about the layer.

## Three discs, 120 captures, nothing

`renderer = 'VULKAN'`, `validation_layers = true`, caches cleared before each
run.

| disc | captures | VUIDs | `SYNC-HAZARD` | `Validation Error` |
|---|---:|---:|---:|---:|
| `Clear` | 32 | **0** | **0** | **0** |
| `Image blit` | 41 | **0** | **0** | **0** |
| `Surface clip` | 47 | **0** | **0** | **0** |

Against the issue's table: finding 1 was 35,208 messages, finding 2 3,470,
finding 3 356, finding 4 17.

**And `Surface clip` is the disc the issue says the validation layer itself
segfaults on** — *"which is why it cannot be used on that disc until this is
fixed."* It runs to completion, 47 captures, `QEMU_EXIT=0`.

## The layer was live — the control

A silent layer and a clean run look identical in a log, which is the trap this
lane has hit twice today. The layer announces itself (`Warning: Validation
layers enabled`) and, more usefully, it still emits **four**
`Undefined-Value-ShaderOutputNotConsumed` warnings per run:

```
vkCreateGraphicsPipelines(): pCreateInfos[0] fragment shader writes to
output location 0 with no matching attachment
```

So the callback is installed and firing. The zeros are measurements.

## What the code says about finding 2, for corroboration only

Finding 2 was *"the push-descriptor template is used with pipeline layouts it
was not created from"* — one template from one layout with no push-constant
ranges, against per-pipeline layouts each carrying a vertex-stage range.

`vk/shaders.c` now builds **one template per pipeline-layout shape**,
`push_template_layout[n]` for `n = 0..NV2A_VERTEXSHADER_ATTRIBUTES`, each with
a vertex-stage range of exactly `n * 4 * sizeof(float)` — and
`create_pipeline` in `vk/draw.c:1621-1637` builds the same range from the same
`__builtin_popcount(uniform_attrs)`. `push_texture_descriptors()` selects the
index with the same popcount. The layouts match by construction, and the
comment in `shaders.c` says so.

Finding 3 was stated as falling out of finding 2, and it does.

That is corroboration, not the result. The result is the layer's own count,
because the layer is the oracle for a layer finding — and reading the code was
what produced two of #51's wrong claims.

## Attribution, explicitly not mine

This lane has not touched `hw/xbox/nv2a/pgraph/vk/` at all. Whoever fixed
these — the template-per-shape construction is recent and deliberate — should
get the entry. What this lane contributes is the measurement that says they
are gone, with the layer version pinned and a control proving the instrument.

## One thing left, and it is not on the list

The four `Undefined-Value-ShaderOutputNotConsumed` warnings are a fragment
shader writing to output location 0 when the subpass has no attachment there.
It is a *warning* about a value that is undefined-but-unread, not a hazard,
and it was not one of #34's five. Recording it so it is not rediscovered as
new: it is the only thing the layer still has to say about these three discs.
