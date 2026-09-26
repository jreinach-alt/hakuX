Lane: blinx372c            Issue: #372
Base: master @ 6c25a829ef
Files: docs/lanes/blinx372c/NOTES.md, docs/lanes/blinx372c/pr-body.md, docs/lanes/blinx372c/stallread.py, docs/testing/predictions/blinx372c-demo-soak.json
Prediction: docs/testing/predictions/blinx372c-demo-soak.json @ 475ff4d9502379c22b14b935554bba77e573b7379061d0a96975f0fb78399eb3   (a soak, not an A/B arm; arms.sh skips soaks)
Needs device: yes    Needs NDK: no

This lane names the SURFACE_DOWN site behind Blinx's two `Sd` finishes per frame in the attract demo, using the perflog `hakuX-stall` line.

**Waiting on the dispatcher update.** The live dispatcher tree (`/home/justin/hakuX` at c4d541bd72, 52 commits behind) and its worker snapshot still use the old LOGCAT_SPEC without `hakuX-stall`. The newest result's `logcat.spec` lacks the tag too. No soak was queued. `host-tools/dispatcher_update_window.sh` unblocks it.

Done offline, before any data:
- The prediction is registered: instrument legs, the impossible-row sum check, a rate range, a >= 80% single-site leg, a guessed top site (cDef), and a demo-fps range. Each site is mapped onto the brief's readback-vs-flush falsifier.
- `stallread.py` reads and judges the soak. `--selftest` builds its fixture from draw.c's own format string.
- Code corrections to the inherited notes:
  - `pDl` also fires from the CPU-access watch (`surface_access_callback`), so it is not ruled out on the AHB-presenting Thor.
  - vk never increments the S2T fallback counter, so `S2T:x/0` excludes nothing.
  - The range path's coalesced `vkWaitForFences` (`cDefC`) is a GPU wait that `Finish sd` does not count.
- One hunk per candidate site, with a bound on its price. It is marked where it would overlap vk/surface.c's watch code (only the pDl-write case).

🤖 Generated with [Claude Code](https://claude.com/claude-code)
