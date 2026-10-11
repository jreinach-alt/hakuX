# lockwake1011 OUTBOX

For a lane that owns hw/xbox/nv2a/pgraph/vk/renderer.c (outside this lane's files).

## Release pfifo.lock around the display refresh's fence wait

What it would remove: the PFIFO thread's own wait for the lock at NFS Most Wanted's cold race start, which the
lock-free wake (`HAKUX_LOCKFREE_WAKE=1`) leaves in place. The wake frees only the vCPU.

The evidence (NOTES.md section 1):
- Every cold `lockw` wait ended with the PFIFO thread still parked, so a third thread held pfifo.lock for
  5.4-5.5 ms on 28 % of cold frames.
- In those frames, unregistered threads' fence waits (`o_fence`) grow by 10.5-11.6 ms.
- `pgraph_vk_get_framebuffer_surface()` takes pfifo.lock and, on the external-memory (AHB) path the Nova uses,
  calls `vkWaitForFences(ready->fence)` under it.
- The holder is an inference from that and from the timing. Nothing books the holder by name, because the
  display thread is not a frametrace thread.

Why it is not a one-line change: pfifo.lock is what orders that fence wait against `render_display()`, which
resets and reuses the same fence on the render thread (two display images). Without the lock, the waiter can
wait on a fence the render thread has already reset (a hang), or read an image that is being drawn into. Another
guard is needed on the image: a per-image sequence number, or a short lock held only to sample the fence and the
image index.

Probability that it moves the cold frame, by this lane's estimate: 0.35, for the same 0.8-1.5 ms plus the PFIFO
thread's own start. Read the wake's A/B result first. If the wake left the PFIFO thread's start as the new bound,
this is the next fix.
