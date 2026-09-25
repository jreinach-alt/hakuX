# Performance baseline at master: where the guest thread's time goes now, and a frame-pacing line

Lane: perfbase            Issue: #68 (context; the CPU-speed family)
Base: origin/master
Files: hw/xbox/nv2a/pgraph/profile.c, docs/testing/perf/** except perf/pad.sh (lane.titlerun's),
docs/investigations/perf-baseline-2026-09.md, docs/lanes/perfbase/**
Needs device: yes, the **Nova** (`ee317437`) under bounded holds. The Thor is on the 0.5 release sweeps
until about 20:30 PDT; after that, the Thor too. Needs NDK: yes (profile.c). Prediction: register one
for the profile.c change (see Proof).

## Why

The owner's 1.0 target is a list of commercial titles at **full speed** on our Snapdragon 8 Gen 2
handhelds. Full speed is the wall, not rendering.

**The newest numbers are old:**
- **Crimson Skies** (a 30 fps game): heavy flying frames are 45-75 ms. It is at full speed in 25-36%
  of windows (Nova, 09-11).
- **Other titles:** JSRF has a median of 43 of 60 (Thor, 09-13), and Fuzion Frenzy's four-player
  minigames run 43-47 of 60 (Nova, 09-11).

**The emulated CPU is the critical path:**
- In a heavy Crimson frame (50.2 ms), the guest thread is busy 41.5 ms. The GPU is at 25% of 220 MHz
  (`frame-pacing-and-parallelism.md:97-105,189-204`).
- The 09-11 guest-thread profile (`docs/testing/perf/run-2026-09-11-crimson-profile-guestthread.txt`,
  gitignored and local) shows about 35-40% of that thread spent on translation-cache bookkeeping,
  not game code:

| Item | Share |
|---|---|
| `tlb_reset_dirty` | 10.68% |
| `tcg_flush_jmp_cache` | 8.37% |
| `qht_lookup_custom` | 5.23% |
| `flush_idcache_range` | 3.90% |
| `helper_lookup_tb_ptr` | 3.87% |
| `tb_lookup_cmp` | 1.96% |
| `notdirty_write` | 1.36% |
| `tlb_set_page_full` | 1.14% |
| `tb_tc_cmp` | 1.12% |

**That profile predates two changes:**
- #73's fix (−85% invalidation visits);
- the voice-lock release (`voice_lock` 4.98% → 1.41%).

No performance run exists after the accuracy fixes (`performance-next-three.md:393-398`). So the
first job is a fresh baseline. lane.tcgchurn (#68) waits on your profile to confirm its target.

**The Nova ran Vulkan validation layers from ~11:11 to 13:05 PDT on 2026-09-25**, from an app
Settings switch the host cleared. Discard any Nova timing from that window. Verify with
`run-as ... cat shared_prefs/x1box_prefs.xml` that `validation_layers` is absent before you measure,
and record the prefs in your NOTES.

## The job

1. **A pacing line.** In `profile.c`, beside the always-on `hakuX-perf` line (`:590-606`), add a
   `hakuX-pace` line every 60 flips. It carries:
   - the count of flip intervals at 1, 2, 3 and 4+ VBLANKs (from `vblank_fired` deltas, already
     tracked at `:570-575`);
   - the longest flip interval in ms;
   - the frame count.

   This gives exact late-frame counts and the worst stall, which the smoothed G cannot. Keep it to
   one `snprintf` per 60 flips. Do not change the `hakuX-perf` line: existing parsers read it.
   lane.titlerun's verdict reads your line. Agree the format with it on your first PR, and write it
   in NOTES.
2. **The baseline, at master, on the Nova, with scripted input.** Use `run_perf.sh` /
   `bench_ff.sh` (hand-run, under holds of at most 60 minutes) and `profile_guest.sh` (simpleperf,
   guest thread):
   - Crimson Skies' heavy-flying window;
   - Fuzion Frenzy four-player;
   - Galleon: drive the gameplay by hand, as `galleon-flashing-deck.md` did.

   For each title, record:
   - fps windows against target (30/60), and the `hakuX-pace` numbers;
   - the guest-thread profile's top 25 self symbols;
   - the thread-load split.

   Take **two runs each**. Record the run-to-run spread before you call a difference.
3. **Name the levers.** Group the guest-thread profile into:
   - translation-cache maintenance (invalidate, dirty tracking, jump-cache flushes, lookups,
     I-cache flushes);
   - softmmu slow paths;
   - helpers;
   - generated code;
   - other.

   For the top three items, say what calls them and how often: the `hakuX-pages` counters
   (`profile.c:420-489`, `tcg_pages.py`) and simpleperf call graphs. **The question lane.tcgchurn
   needs answered:** how often does the guest cause a FULL TLB flush (which clears the jump cache),
   and from which instruction or path? Examples: a CR3 reload, CR0/CR4 writes, INVLPG storms.
4. **Write it up** in `docs/investigations/perf-baseline-2026-09.md`, with a table per title. Post
   the summary on #68.

## Proof

- **The pacing line.** Register a prediction before your first build of the line: on a Nova run of
  Crimson Skies the line appears every 60 flips; the 1/2/3/4+ counts sum to 60; and the late-frame
  share (intervals above the title's nominal VBLANKs per flip) matches the `Vpf` field of the
  `hakuX-perf` line in the same window to within 5%. Run it. A leg that names no capture is not a
  measurement (host memory).
- **The baseline:** two runs per title, the raw logs kept under
  `/home/justin/hakux-work/perf/2026-09-26/`, and the spread stated.

## Do not

- **Edit `perf/pad.sh`**, which is lane.titlerun's. If you need a new pad command, ask it on its PR.
- **Leave a setting changed on a device.** Put back `surface_scale` and any env or bool prefs the
  perf scripts write, and verify by read-back.
- **Hold a device while another lane's request runs there,** or for more than 60 minutes.
- **Trigger CI as a self-check.**

## Done when

- The pacing line is folded.
- The baseline document names the top three guest-thread costs per title, with measured shares
  and spreads.
- #68 carries the summary.
- NOTES record the prefs each run used.
