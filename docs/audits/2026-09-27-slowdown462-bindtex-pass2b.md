# Audit pass 2 (second run): PR #512 lane/slowdown462-bindtex (#474)

Head verified: `2fa752115d`. `git diff 3d3c22f8c0 2fa752115d` is
`docs/lanes/slowdown462/NOTES.md` only (+33 -1). The code and tools are the
same ones pass 1 and the first pass 2 read. CI on this head: build x2 and
check pass. The PR is mergeable.

**Verdict: clean.** The scenario behind LOW 2 can no longer happen. LOW 1
and LOW 3 stand, as pass 1 allowed. One sub-premise in the new bullet is
misstated, but the conclusion does not depend on it. It is recorded below
as a new LOW for the fix lane, and it does not block the fold.
-> `fold-ready`.

## LOW 2: verified

The scenario was that a fix lane reads NOTES, removes the drain before a
direct bind, and a descriptor set that an in-flight frame still holds gets
rewritten. The NOTES now carry a "Descriptor sets, checked" bullet (line
1186), and the Blinx bullet (line 1309) points to it. I checked each cited
line against the code at head:

- `shaders.c:604-608` and `713-717`: a full ring rewinds only after
  `pgraph_vk_finish` + `pgraph_vk_flush_all_frames`. Confirmed.
- `draw.c:3663` and `3730`: both rewinds sit after the frame's fence or
  finish event ("GPU done"). Confirmed.
- `draw.c:3838`: rewinds only when `!any_in_flight`. Confirmed.
- `draw.c:3446`: `flush_all_frames` waits on every submitted fence
  (`draw.c:3400-3407`), then rewinds only if `!r->in_command_buffer`.
  Confirmed.
- `shaders.c:699-710`: a cache hit calls no `vkUpdateDescriptorSets`.
  Confirmed.

So every rewind happens when no submitted frame is pending and no command
buffer is recording. A fresh ring set is therefore never one that an
in-flight frame holds, whether or not the drain runs. Removing the drain
cannot cause the use-while-pending write that pass 1 described. The premise
is now stated with the lines checked, which is what the first pass 2 asked
for.

## New LOW 4: "the s2t drain runs inside a recording command buffer" is not always true

NOTES line 1203 says: "The s2t drain (`texture.c:2300-2303`) runs inside a
recording command buffer, so its `flush_all_frames` does not rewind the
ring." On the full draw path this is false for the first draw after a
submit. `create_pipeline` (`draw.c:4324`) calls `pgraph_vk_bind_textures`
(`draw.c:2223`), and `pgraph_vk_ensure_command_buffer` only runs later
(`draw.c:4339`, `4357`, `4393`). After a finish clears `in_command_buffer`
(`draw.c:3903`), the next draw's s2t drain runs with
`!in_command_buffer`, so its `flush_all_frames` does rewind the ring.

Scenario: someone reasoning from this sentence about the cache-aliasing
hazard would decide that drains never add rewinds. In fact they can, and a
rewind that does not clear `tex_desc_cache` is exactly what that hazard
needs. So the line "removing the drain does not touch it" is slightly off:
removing the drain removes some rewinds, which narrows the hazard rather
than widening it. No conclusion here changes. That rewind happens with
nothing pending and nothing recording, so it is safe for the same reason as
the others, and "the drain protects no descriptor write" still holds. The
fix lane should correct this sentence if it reasons from it.

## LOW 1, LOW 3: stand, as allowed
Unchanged since pass 1. `texture.c:96` still prints `bt%.2f/%.0f`, and the
probe's clock reads cost less than 0.05 ms/flip.
