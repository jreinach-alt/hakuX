# lane.blinx372b -- name the SURFACE_DOWN site behind Blinx's attract-demo wait (#372)

Issue: #372 (game-visible: Blinx: The Time Sweeper ~14 fps in the attract demo on the Thor). Base: master 7a2036020d.
Files: docs/testing/dispatcher.sh, docs/lanes/blinx372b/**, docs/testing/predictions/blinx372b-*.json.
dispatcher.sh was released at ready by lane.titlerun (PR #307, merged). No hw/ file is granted: a hunk is NAMED, not edited.

## Where lane.blinx372 left it (PR #374, docs/investigations/perf-blinx-372.md, comment on #372)
Renderer thread 96-98% busy. Per guest frame in the demo: guest frame 68.1 ms, GPU-completion waits inside
pgraph_vk_finish 32.1 ms (`Sd2 St1`: two non-deferred finishes for surface download per frame, draw.c ~3516/3592),
draw recording 23.0 ms, GPU 37.1 ms. Recording and GPU execution are serialised. Removing both waits has a ceiling near 27 fps.
The lever is unnamed: which of the seven SURFACE_DOWN sites fires is counted on the perflog `hakuX-stall` line, and
the dispatcher's logcat allow-list drops it (and `hakuX-pace` from every dispatched soak).

## Goal
1. In docs/testing/dispatcher.sh (grep the logcat allow-list near line 1356; the line moved if master moved) add
   `hakuX-pace:I hakuX-stall:I xemu-gpu:I` to the filter. Check the selftest that covers the dispatcher still passes.
2. One perflog soak of Blinx on the Thor through the dispatcher (master apk, the attract-demo window; reproduce the
   13.8 fps figure first). Read the `hakuX-stall` counters per site.
3. Name the site(s) that fire, why each needs a synchronous download (guest read? CPU-visible surface? readback of a
   render target the guest later samples?), and whether a small vk hunk defers it. Write the hunk as a patch in
   docs/lanes/blinx372b/ (passes -fsyntax-only), priced: predicted fps if removed vs the 27 fps ceiling.

## Falsifier
"One site accounts for most of Sd2": the counters show one site with >= 80% of the finishes. If they spread over
several, say so and rank them; do not pick one. Register the prediction before the soak.

## Notes
3 of 5 Thor soaks on 09-26 lost the guest early with no crash line (also seen on the Nova with other titles): rerun
twice before reading a lone soak (memory: device-run-flakes). vk/draw.c is held by lane.remote and released
by lane.aasample; do not edit it.

## Done when
Allow-list fix in a PR (out of draft, CI green), the soak's run id and per-site counters posted on #372, the patch
and its price in NOTES. If no small hunk exists, that is the result; say what would be needed.
