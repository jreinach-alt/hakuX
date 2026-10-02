# lane.bf2ubosize433 outbox

## #433 -- 2026-10-02 09:40 PDT

[lane.bf2ubosize433] waiting: one Nova soak, `1790958948-lane.bf2ubosize433-1976093`. It is queued behind lane.pathfind's direct-drive hold on the Nova. It resolves when the run is DONE in `dispatch/results/`.

- **Built and checked without a device:** a perflog-only counter (`ubosz[...]` on hakuX-stall, every 60 flips). For each uniform upload it reports how many 16-byte chunks of the shader uniform blocks changed since the previous upload, and how many of the 192 vertex-constant registers changed. It also counts shader switches and replays the fix's policy: push up to 8 or 16 changed vec4 and rebind only past that, counting the uploads that would still rebind. A host selftest compiles the exact code from the tree and passes all 31 checks. The judge reproduces the 17 heavy windows bf2stall433 found in its master soak.
- **Found while reading:** the per-register dirty bits are never cleared on the Vulkan path, so they could not be the counter. If Turnip allows 256 bytes of push constants, as I believe it does (not yet confirmed on the fleet's driver), the Nova has 15 vec4 free after the existing geometry vec4, and inline attribute values already ride in the uniform block.
- **Registered before the run** (`bf2ubosize433-bf2-ubosz.json`):
  - PUSH: most heavy-view uploads change 16 vec4 or fewer, and the policy keeps the rebind off most of them. Then a successor brief for the push-constant fix.
  - SWITCH-BOUND: the changes fit, but shader switches still force rebinds.
  - LARGE: most uploads change more than 32 vec4. Then the lever is batching draws that share constants.
