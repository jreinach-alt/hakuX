# Audit pass 2: PR #512 lane/slowdown462-bindtex (#474)

Head verified: `8e7c62aa71`. `git diff 013f087a52 8e7c62aa71` is the pass-1
audit file only, so the code, NOTES and tools are exactly what pass 1 read.

**Verdict: not clean.** LOW 1 and LOW 3 stand as documented, which pass 1
allowed. LOW 2 was the one condition pass 1 set for pass 2, and it is
unaddressed: NOTES still states the premise without qualification, and it
is not deferred anywhere. -> `needs-remediation`.

## Per finding

### LOW 1 (`bt` calls/flip printed `%.0f`): stands, as allowed
`texture.c:96` still reads `bt%.2f/%.0f`. No figure in this PR uses a
sub-1 call rate. Pass 1 allowed this to stand while the probe stays a lane
probe.

### LOW 3 (clock reads inside the timed regions): stands, as allowed
Unchanged. Its effect is below 0.05 ms/flip and moves no conclusion.

### LOW 2 (direct-bind drain "protects nothing"): the scenario still fires
NOTES line 1184 (AUF) and line 1277 (Blinx) still argue from image writes
only: "the drain before it protects nothing that path writes" and "The drain
protects nothing on this path". There is no qualification beside either
line. Nothing on #474 or #512, and no `dispatch/board-requests/slowdown462.md`
on `origin/board`, hands the descriptor question to the fix lane. The
candidate fix (drain only on the copy path, flip474) is already on the
device, so a reader of this premise is acting on it now.

Scenario that still fires: the fix lane reads NOTES, takes "protects
nothing" as checked, and removes the drain before a direct bind. If a
texture descriptor set that an in-flight frame still references is
rewritten in place, that is a use-while-pending hazard. The image-write
argument does not cover it.

What the code shows (a start, not a proof; for the remediation to confirm
or correct):
- Texture descriptor sets come from a ring. A change in texture bindings
  takes a fresh set (`shaders.c:600-716`, `need_new_tex_set`). The ring
  rewinds to 0 only after the GPU is done (`draw.c:3663`, `3730`, `3838`),
  or after `flush_all_frames` when it is full (`shaders.c:606-608`,
  `714-716`). So the normal path does not rewrite a set that is in flight.
- `shaders.c:699-710` reuses a cached `ce->descriptor_set` and does not
  consume a ring slot. Whether a cache entry can be rewritten while a frame
  that bound it is pending was not checked. That is the open part.

## Remediation asked
Qualify the premise where it is stated, at NOTES 1184 and 1277. Either:
- state that descriptor reuse was checked: fresh ring sets rewind only
  after GPU completion, and the cached-set path does not rewrite a set in
  flight, with the lines checked; or
- state the premise covers image writes only, and that descriptor reuse
  (the ring and the `desc_rebind_skips` cache) is for the fix lane to
  check. Say the same on #474 where the fix lane reads it.

Either one is a NOTES-only edit. No code change is asked.
