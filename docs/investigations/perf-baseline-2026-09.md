# Performance baseline at master, 2026-09-25: where the guest thread's time goes

Nova (`ee317437`, Snapdragon 8 Gen 2), apk built from `20a1a20eec` (master
`90a8dc1c1a` plus the `hakuX-pace` line, which prints once per 60 flips).
Runs were taken 23:04-23:49 UTC on 2026-09-25 (16:04-16:49 PDT), after the
Nova's validation-layer window had closed; the prefs carried no
`validation_layers` key. Shader caches were cleared once, before the first
run. Raw logs, screenshots, prefs and `perf.data` are in
`/home/justin/hakux-work/perf/2026-09-26/`.

- **Perf runs:** `run_perf.sh 1 <tag> <s>` (surface_scale 1).
- **Profiles:** `profile_guest.sh 30 <tag>` (simpleperf cpu-clock, 1 kHz,
  dwarf call graphs).
- **Reports:** `profile_report.py` for groups and callers, and
  `pace_check.py` / `tcg_pages.py` for the logs.
- **Sampling:** two perf runs and two profiles per title, each from its own
  boot.

## Summary

| Title (workload) | At full speed | Guest thread | Top three guest-thread self costs (two profiles) |
|---|---|---|---|
| Crimson Skies, heavy flying | 31% / 35% of 60-flip windows; 25-31% of flips late | hottest, 84% of a core | `tlb_reset_dirty` 11.1-11.4%, `tcg_flush_jmp_cache` 8.5-8.6%, `qht_lookup_custom` 4.6-4.7% |
| Fuzion Frenzy (profiles are probably menus, see below) | run 2 (a minigame round): 37% of windows; 35% of flips late | hottest, 60-96% | `cpu_exec_loop` 22.0-23.3%, one generated-code address 10.6-11.1%, `helper_cc_compute_c` 6.1-6.5% |
| Galleon, attract demo | run 2: 24% of windows; 16% of flips late | not the hottest: the renderer is (57-85%) | `helper_lookup_tb_ptr` 7.1-9.1%, `qht_lookup_custom` 3.7-5.0%, `cpu_exec_loop` 3.8-12.0% |

**Crimson Skies is where the brief's premise holds, and it has not moved
since 09-11.** In Crimson, translation-cache maintenance is 40.4-40.9% of the
guest thread. That is up from the 35-40% read on 09-11: neither #73's fix nor
the voice-lock release reduced this bill. `voice_lock` did fall, to
0.76-0.84% (from 1.41%).

**The jump-cache flush is driven by block discards, not by full TLB
flushes.** On i386 system emulation every translated block carries
`CF_PCREL` (`target/i386/cpu.c:9325`), and for such a block
`tb_jmp_cache_inval_tb` (`accel/tcg/tb-maint.c:1292-1299`) clears the
**whole** 4096-entry jump cache of every CPU. `do_tb_phys_invalidate` calls it
on every discard (`:1390`), and Crimson discards about 1,600 blocks per guest
frame, or about 43,000 per second.

The measured cost fits this. If the 8.5% of an 84%-busy guest thread
(~71 ms/s) were all discard-driven, each flush would cost about 1.7 µs. That
is about right for 4,096 pointer stores. For full TLB flushes to carry a
comparable share, the guest would need tens of thousands of them per second.

This is a consistency argument, not a count. The build prints no full-flush
counter (`cpu->neg.tlb.c.full_flush_count` exists but is not logged).
lane.tcgchurn (#309) is adding the trigger counters. The unwinder also loses
the stack inside `tcg_flush_jmp_cache`, so simpleperf cannot split it by
caller.

## Crimson Skies: heavy flying (nominal 30 fps, 2 VBLANKs per flip)

A scripted A-mash leads into the first flying section, then the sticks stay
centred for 120 s. Both runs ended in level flight
(`crimson-r*-end.png`).

**Pacing** (`hakuX-pace`, first line of each process dropped):

| run | windows | full-speed windows (no late flip) | late flips (> 2 VBLANKs) | v1/v2/v3/v4+ | worst flip interval (ms): median / p90 / max | window fps median |
|---|---|---|---|---|---|---|
| r1 | 71 | 22 (31%) | 1309 / 4260 (30.7%) | 30 / 2921 / 1107 / 202 | 48.1 / 71.0 / 188.0 | 27.9 |
| r2 | 74 | 26 (35%) | 1125 / 4440 (25.3%) | 13 / 3302 / 925 / 200 | 46.7 / 62.5 / 160.3 | 27.4 |

**Spread between the two runs:**

- Full-speed windows: 4 points.
- Late-flip share: 5.4 points.
- Window fps: 0.5 fps.

A difference smaller than these is not a difference on this workload.

**Thread load** (`loadsample.sh` via `summarise.py`):

| run | guest fps median (min-max) | game ms median | hottest thread | all threads | GPU |
|---|---|---|---|---|---|
| r1 | 27 (11-31) | 36.5 | 84% `qemu_main` | 206% of one core | 15% at 550 MHz |
| r2 | 28 (15-30) | 34.6 | 84% `qemu_main` | 205% | 15% at 550 MHz |

**Guest-thread profile.** Profile p1 was re-taken as p1b; the first attempt
is void (see NOTES). The guest thread is tid `qemu_main`, 37.6-37.8% of all
samples, and the renderer (`Thread-6`) is 25.1-25.6%.

| group | p1b | p2 |
|---|---|---|
| translation-cache maintenance | **40.43%** | **40.89%** |
| generated code | 28.52% | 28.63% |
| other | 18.55% | 17.52% |
| softmmu slow paths | 9.41% | 10.03% |
| helpers | 1.90% | 1.89% |
| translate (new TBs) | 1.20% | 1.03% |

The group patterns are in `profile_report.py`'s docstring.
`tlb_flush*` is counted as maintenance.

Top 25 self symbols, guest thread (p1b; the p2 value follows where it
differs by more than 0.3 points):

| # | symbol | group | p1b | p2 |
|---|---|---|---|---|
| 1 | `tlb_reset_dirty` | tc-maint | 11.12% | 11.42% |
| 2 | `tcg_flush_jmp_cache` | tc-maint | 8.47% | 8.64% |
| 3 | `qht_lookup_custom` | tc-maint | 4.68% | 4.57% |
| 4 | `__kernel_clock_gettime` [vdso] | other | 4.50% | 3.08% |
| 5 | `helper_lookup_tb_ptr` | tc-maint | 4.22% | 4.24% |
| 6 | `flush_idcache_range` | tc-maint | 3.95% | 3.87% |
| 7 | `mem_access_callback_address_matches` | softmmu | 2.28% | 2.36% |
| 8 | `cpu_exec_loop` | other | 1.95% | 2.27% |
| 9 | `tb_lookup_cmp` | tc-maint | 1.86% | 1.81% |
| 10 | `mmu_lookup1` | softmmu | 1.52% | 1.49% |
| 11 | [kernel] | other | 1.49% | 1.59% |
| 12 | `notdirty_write` | tc-maint | 1.44% | 1.43% |
| 13 | `probe_access_internal` | softmmu | 1.18% | 1.34% |
| 14 | `@plt` | other | 1.06% | 1.19% |
| 15 | `tb_tc_cmp` | tc-maint | 1.05% | 0.97% |
| 16 | `__emutls_get_address` (SDL2) | other | 1.01% | 0.98% |
| 17 | `tlb_set_page_full` | softmmu | 0.97% | 1.06% |
| 18 | `voice_lock` | other | 0.76% | 0.84% |
| 19 | `__aarch64_swp4_acq_rel` | other | 0.67% | 0.58% |
| 20 | `mmu_lookup` | softmmu | 0.65% | 0.77% |
| 21 | `mem_check_access_callback_vaddr` | softmmu | 0.61% | 0.84% |
| 22 | `helper_mulss` | helpers | 0.60% | 0.62% |
| 23 | `pthread_getspecific` | other | 0.53% | 0.56% |
| 24 | `qemu_ram_block_from_host` | softmmu | 0.46% | - |
| 25 | `curr_cflags` | tc-maint | 0.43% | - |

**Against 09-11 (same title, same scene, older build):**

| symbol | 09-11 | now |
|---|---|---|
| `tlb_reset_dirty` | 10.68% | 11.1-11.4% |
| `tcg_flush_jmp_cache` | 8.37% | 8.5-8.6% |
| `qht_lookup_custom` | 5.23% | 4.6-4.7% |
| `flush_idcache_range` | 3.90% | 3.9-4.0% |
| `helper_lookup_tb_ptr` | 3.87% | 4.2% |

The whole list is within the two-profile spread of where it was.
`__kernel_clock_gettime` (3.1-4.5%) is new in the top ten. Its callers are not
resolved: the vDSO frame does not unwind. One candidate is
`tlb_flush_by_mmuidx_async_work`, which calls `get_clock_realtime()` on every
flush (`accel/tcg/cputlb.c:373`). Treat that as a hypothesis, not a finding.

### The top three items: callers and counts

The counts come from `hakuX-pages`, 120 guest frames per window, via
`tcg_pages.py`. They are shown as min / median / max over the run.

| counter | r1 | r2 |
|---|---|---|
| `di`: discards (blocks really unlinked) | 130,406 / 192,107 / 333,243 | 119,971 / 192,140 / 333,029 |
| `pr`: arming TLB walks (`tlb_protect_code`) | 17,756 / 25,891 / 43,834 | 16,581 / 25,989 / 43,779 |
| discards per generation | 1,149 | 1,217 |
| discards with no guest-written byte | 100.0% | 100.0% |

1. **`tlb_reset_dirty` (11.1-11.4%).** All attributed callers come through
   one chain: `tb_gen_code` → `tb_link_page` →
   `physical_memory_test_and_clear_dirty` → `tlb_reset_dirty_range_all` →
   `tlb_reset_dirty`.

   This is the arming walk that re-protects a page after its code was
   discarded. It walks every TLB entry of every MMU index, and it runs
   about 216 times per guest frame (`pr` median / 120).

   Every one of those walks follows an event that emptied the page (`em`),
   and a range test would have spared 100% of them (`ws/em = 1.000`).
   `tcg_pages.py` also classifies the build as whole-page invalidation.
   A store to a code page discards every block on it, including blocks
   whose bytes the guest never wrote.
2. **`tcg_flush_jmp_cache` (8.5-8.6%).** Every discard calls it through
   `do_tb_phys_invalidate` → `tb_jmp_cache_inval_tb` (the `CF_PCREL`
   branch), and each call clears 4,096 entries. That is about 1,600 flushes
   per guest frame. See the summary for why full TLB flushes cannot be the
   bulk of this share.
3. **`qht_lookup_custom` (4.6-4.7%).**
   - 39.5-41.7% of its samples come from `tb_htable_lookup` ←
     `helper_lookup_tb_ptr`: indirect-jump lookups that miss the jump cache.
     The jump cache is being emptied 43,000 times a second, so these misses
     are partly a consequence of item 2.
   - 21.2-22.9% come from `inv_tb_htable_lookup` ← `tb_gen_code`: the
     recycle probe, which runs once per codegen call (`iv == calls`).
   - The remainder did not unwind.

**The full-TLB-flush question.** lane.tcgchurn asked how often the guest
causes a full TLB flush, and from which instruction or path. That is **not
answered by count here**.

- Sampled `tlb_flush*` code on the guest thread is 2-4 samples of 24,000.
  They are single-page flushes reached from `tlb_set_page_full` and
  `tlb_fill_align` (victim-TLB maintenance), not from a CR3, CR0 or CR4 write
  or from INVLPG.
- The flush itself is therefore cheap. What costs is the jump-cache clear
  that follows it, and discards alone account for that clear at the measured
  share.
- If lane.tcgchurn's counters show full flushes in the hundreds per second,
  they are under 1% of the jump-cache calls. The lever is then the per-discard
  whole-cache clear, not the guest's flush rate.

## Fuzion Frenzy (nominal 60 fps, 1 VBLANK per flip)

The workload is `bench_ff.sh`: a Start/A mash, 3 s settle, then measure. It
reaches different places on different boots:

- **Run 1** measured menus and instruction screens. 82 of 84 windows were at
  60, and the end screen was a "Rollmentum" instruction card.
- **Run 2** played a round. It ended on "Coliseum - Round one" results.
- **The profiles** use the same 3 s settle and are probably menus too.

So this is **not** the four-player minigame baseline the brief asked for.
That needs a pad sequence into a minigame, which is lane.titlerun's
`pad.sh`, not this lane's.

| run | windows | full-speed windows | late flips (> 1 VBLANK) | v0/v1/v2/v3/v4+ | worst interval (ms): median / p90 / max | window fps median |
|---|---|---|---|---|---|---|
| r1 (menus) | 84 | 82 (98%) | 3 / 5040 (0.1%) | 0 / 5037 / 0 / 0 / 3 | 17.5 / 23.1 / 430.3 | 59.9 |
| r2 (a round) | 54 | 20 (37%) | 1128 / 3240 (34.8%) | 7 / 2105 / 1069 / 48 / 11 | 32.5 / 152.7 / 3347.4 | 42.5 |

| run | guest fps median (min-max) | hottest thread | all threads | GPU |
|---|---|---|---|---|
| r1 | 59 (27-60) | 96% `qemu_main` | 159% | 13% at 550 MHz |
| r2 | 40 (29-59) | 60% `qemu_main` | 178% | 23% at 550 MHz |

The guest thread is 56.8-57.6% of all samples.

| group | p1 | p2 |
|---|---|---|
| generated code | 56.86% | 57.30% |
| other | 29.12% | 28.16% |
| tc-maint | 6.75% | 6.70% |
| helpers | 6.29% | 6.70% |
| softmmu | 0.85% | 0.96% |
| translate | 0.13% | 0.18% |

The top self symbols in both profiles:

- `cpu_exec_loop` 23.33% / 21.99%;
- a single generated-code address 11.05% / 10.60%;
- `helper_cc_compute_c` 6.07% / 6.45%;
- `cpu_tb_exec` 3.11% / 2.95%;
- then `helper_lookup_tb_ptr` 1.8%, `x86_get_tb_cpu_state` 1.0-1.2%,
  `curr_cflags` 1.0-1.1%, `tlb_reset_dirty` 0.8%.

The rest of the top 25 is generated code at 0.6-1.8% each.

This shape is a guest spin loop: one hot block, very short TBs leaving to
`cpu_exec_loop`, and a carry-flag helper. The code is polling, not doing
work. The next Fuzion Frenzy lane should profile a minigame before reading
anything into it.

`tcg_pages` in r2 counts 8,296 median discards per window, 23 times fewer
than Crimson. Its waste ratio is 69 discards per generation.

## Galleon: attract demo (nominal 30 fps)

The brief asked for gameplay driven by hand, as `galleon-flashing-deck.md`
did. This lane cannot drive by hand. It measured the attract demo instead:
the input-free, scripted, repeating workload that document identified.
`galleon-r1-end.png` shows demo combat at 21 fps.

The demo cycles scenes with loading gaps between them, so the windows mix
play and loading.

| run | windows | full-speed windows | late flips | worst interval (ms): median / p90 / max | guest fps median (min-max) | hottest thread | GPU |
|---|---|---|---|---|---|---|---|
| r1 | 5 | 0 | 247 / 300 (82%) | 3510 / 7663 / 11417 | 16 (0-22) | 85% `Thread-6` (renderer) | 0% |
| r2 | 21 | 5 (24%) | 195 / 1260 (15.5%) | 973 / 2187 / 3413 | 29 (17-30) | 57% `Thread-6` | 10% |

**Galleon is renderer-thread bound, not guest-bound.** In both runs the
hottest thread is `Thread-6`.

The two profiles caught different scenes:

- In p1 the guest thread is 12.0% of samples and the renderer 61.0%.
- In p2 the guest thread is 30.6% and the renderer 22.9%.

| group | p1 | p2 |
|---|---|---|
| generated code | 48.47% | 43.84% |
| other | 17.24% | 27.87% |
| tc-maint | 19.55% | 16.74% |
| softmmu | 7.40% | 5.83% |
| helpers | 6.97% | 5.26% |
| translate | 0.36% | 0.45% |

The top self symbols:

- `helper_lookup_tb_ptr` 9.10% / 7.06%;
- `qht_lookup_custom` 5.00% / 3.70%;
- `cpu_exec_loop` 3.78% / 11.99%;
- `mem_check_access_callback_vaddr` 3.42% / 2.75%;
- `helper_mulss` 3.42% / 2.14%;
- `voice_lock` 0.72% / 3.35%;
- `surface_access_callback` 2.01% / 1.78%;
- `tb_lookup_cmp` 1.6%;
- `tlb_reset_dirty` 0.8-1.4%.

Galleon discards 1,638 blocks per window (median), 117 times fewer than
Crimson. Its maintenance share is lookup (indirect jumps), not
invalidation. The lever for Galleon is on the renderer thread.

## The levers, in order

1. **Per-discard jump-cache clears (Crimson: 8.5%, plus part of the 4.6%
   htable lookups they cause).** `CF_PCREL` makes every discard clear all
   4,096 entries. A discard only needs to remove entries that point at the
   discarded block, and with `CF_PCREL` a block may sit at any virtual
   address. So the fix is either a reverse map, or a check-on-hit (the entry
   is already validated against `tb->pc`/flags on lookup), in place of the
   eager wipe.
2. **Whole-page invalidation and the arming walk (Crimson: 11.1-11.4% for
   `tlb_reset_dirty`, plus `flush_idcache_range` 3.9% and `notdirty_write`
   1.4%).** None of the discarded blocks held a byte the guest wrote, and a
   range test would have avoided every page-empty. This is the #68 premise, and today's counters
   confirm it at 100%.
3. **For Fuzion Frenzy and Galleon, neither of these.** Fuzion Frenzy's
   profiled window is a spin, and Galleon is renderer-bound. The Crimson
   levers do not reach 60 fps in either title.

## Limits

- One device (Nova), one build. The Thor was not used.
- The Fuzion Frenzy profile is not of a minigame, and the Galleon runs are
  of the demo, not driven play.
- The full-TLB-flush rate is argued, not counted.
- `__kernel_clock_gettime`'s caller is unresolved.
- `crimson-p1` was void: simpleperf refused `cpu-clock` and the old script
  pulled a stale file. It was re-taken as `crimson-p1b` with the fixed
  `profile_guest.sh`.
