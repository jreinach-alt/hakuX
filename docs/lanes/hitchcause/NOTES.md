# lane.hitchcause (#433): what the unexplained 330 ms hitches in MTV are

Brief: the offline part of the 10-04 MTV hitch brief. Evidence: the 689 s hold
`perf/2026-10-04-mtv-hitches/` (perflog build, Nova), plus Orta
(`lane.pathfind` runs/panzer-dragoon-hold3) and Blood Wake
(`dispatch/results/0-1791086203-lanelocal-3321881`) logs. No device run was
made; see section 5 for why.

## 0. Attempt 2: why attempt 1 did not finish, and what this attempt adds

Attempt 1 ended at section 5. Its one Nova capture needed a perflog line in
`hw/ide/`, which was outside its Files line, so it wrote a grant request, set
the PR ready, and stopped with the device step undone. Nothing was measured
that section 3 could not already see. The grant arrived in the hostops
addendum of 2026-10-04 14:50 PDT (board row `lane.hitchcause`: this directory,
`hw/ide/core.c`, `hw/ide/mmio.c`).

Attempt 2 does what the addendum asks, in order: a perflog line in the IDE PIO
read path (`[ide425]`, documented at `ide425` in `hw/ide/core.c`; telemetry
only, no behaviour change), one build, one MTV hold of about 700 s on the
Nova, and the 2-vs-3 diagnosis from that run's perflog against the candidates
in section 6. Section 10 is that diagnosis.

Scripts (stdlib python, all in this directory):

- `hitchwin.py`: aligns every perflog tag to each `hakuX-pace` window (the
  60-frame window closed at the pace line's time). Run it as
  `python3 hitchwin.py <logcat> --all > allwin.txt`; the output is not committed
  (the repo ignores `*.txt`).
- `blockread.py`: blocked share (100 - idlehalt run%) against each counter.
- `ide_wake.py`: `[rr425w]` IRQ14 (vector 0x3e) busy per 2 s span against the
  worst frame. Run it on each of the three logs (output not committed).
- `rr_split.py`, `pc_exits.py`, `g_conc.py`: the `[rr425]` inside/between-TB
  split, the `[rr425pc]` exit counts, and the translated-block concentration.

## 1. Two facts that frame everything

**The vCPU thread is not the same as the guest's busy clock.** `[rr425w] busy`
is wall time outside the guest idle loop, so a host-side sleep inside a
translated block counts as busy. The host's own view is `[idlehalt] run_us`
(the vCPU thread's on-CPU time from schedstat) and `rq_us` (run-queue wait).
Span time that is neither is the thread sleeping. In these windows `rq_us` is
4 to 14 ms per 2 s, so run-queue wait is not the story. Median sleep share is
9.5% in the baseline (windows under 100 ms) and 7.3% in the 200+ ms windows, so
sleep alone does not mark a hitch.

**The 330 ms hitches are one frame, and they sit in a 60-frame window.** The
gfps line's `G:` field is the last second, not the window, so it cannot time a
single frame. `hakuX-pace max=` is the worst frame in the window; the audio
never starved (`audio_starve_share 0.0`), and the flip latency (`cblat max`)
was at most 17 ms in the worst window, so the display and audio threads were
not what froze.

## 2. What is in each hitch window (MTV, 14:04-14:16 PDT)

The route state is pathfind's coarse timeline. "IRQ14 busy" is the time the
vCPU spent after vector-0x3e wakes in the 2 s spans that cover the window.

| hitch (PDT) | worst ms | route state | IRQ14 wakes / busy | vCPU on-CPU | PFIFO drain max | TLB storm (ff / pf) |
|---|---:|---|---|---:|---:|---|
| 14:04:41.8 | 209 | play | 194 (next span) / 635 ms | 92.7% | 15.6 | 0 / 0 |
| 14:05:19.3 | 242 | play | 119 + 0 / 572 + 640 ms | 96.4% | 43.7 mean, 699 max | 304 / 2795 |
| 14:05:23.7 | 168 | play | 146 / 414 ms | 97.4% | 17.2 | 0 / 0 |
| **14:05:57.6** | **349** | menu | 151 + 316 / 618 + 389 ms | **84.7%** | 33.5 | 333 / 2070 |
| **14:08:39.7** | **346** | play | 53 + 339 / 186 + 346 ms | 92.8% | 14.8 | 67 / 1347 |
| **14:10:25.9** | **344** | play | 374 / 672 ms | 94.1% | 14.4 | 0 / 1263 |
| 14:13:01.7 | 209 | cutscene | 63 + 134 / 128 + 362 ms | 93.5% | 14.4 | 54 / 3620 |
| **14:13:15.3** | **331** | menu | 230 + 257 / 924 + 76 ms | **83.5%** | 16.3 | 488 / 2768 |
| **14:15:21.4** | **330** | play | 130 + 287 / 602 + 82 ms | 92.7% | 8.4 | 149 / 1859 |

Baseline (windows under 100 ms, n=329): IRQ14 wakes 0 in every span, TLB
flushes median 4, INVLPG median 15, on-CPU median 90.5%.

The 14:05:06 (116 ms) and 14:10:05 (107 ms) hitches have no IRQ14 wakes; they
sit in 2 s spans with no idle halt at all (`idle` 0, busy 2 s).

Findings from the table:

1. **Every hitch of 200 ms or more has an IRQ14 burst in its own 2 s span or
   the next one.** There are 8 distinct such hitches (209, 242, 349, 346, 344,
   209, 331, 330 ms). Across 344 spans the IRQ14 busy time against the worst
   frame gives r = 0.74; the spans with worst >= 200 ms have a median 602 ms of
   IRQ14 busy, and the spans under 100 ms have 0. The earlier z-score pass that
   found only fifoskew rising missed this, because it never split by the vector.
2. **IRQ14 is the Xbox primary IDE channel.** The `[rr425w]` key is
   `vec | units<<8`, and the printed bucket `30.00` (vector 0x30, IRQ0, the
   100 Hz tick) fires about 200 times per 2 s, which fixes the mapping. Vector
   0x3e is then IRQ14 (0x30 + 14). This is an inference from the vector
   arithmetic, not a read of the Xbox HAL; the 100 Hz check is what supports it.
3. **Each burst is one stream of PIO sector reads.** A burst is 60 to 370
   wakes per 2 s, so one IRQ per sector at 5 to 17 ms per sector. The code
   (`hw/ide/core.c`, `ide_sector_read`) issues one `ide_buffered_readv` per
   sector, from the completion of the last one, so one read is outstanding at a
   time. The guest's next sector waits for its own copy of the last one and for
   the host read to complete. Busy time keyed to IRQ14 wakes is 0.1 to 0.9 s per
   span; the rest of the busy time is keyed to NV2A and timer wakes, as in the
   baseline, so the IRQ14 figure is a lower bound on the burst's guest work.
4. **Two of the five 330 ms hitches have the vCPU asleep.** In 14:05:57 and
   14:13:15 the thread's on-CPU share falls to 83 to 85%, and rq is normal, so
   about 300 ms of each 2 s was host sleep (not halted, not runnable). The other
   three 330 ms hitches run at 92 to 94% on CPU, so their 330 ms is on-CPU time.
5. **The GPU side stalled in the 14:05:19 burst, and a little in 14:05:57.**
   The PFIFO drain max is 8 to 16 ms in five of the eight hitch spans, 33.5 ms
   at 14:05:57, and 699 ms at 14:05:19 (drain mean 44 ms, where the windows
   checked otherwise run at 0.4 to 4 ms). So the 242 ms hitch at 14:05:19 may
   have a second, GPU-side cause (the guest waiting on a push buffer the
   renderer had not drained). The flip latency (`cblat`) is 17 ms at most in
   every window checked.
6. **TLB storms co-occur, and their measured refill cost is small.** INVLPG
   (`pf`) runs 1.2k to 3.6k per span in 7 of the 8 hitch spans, against a
   median of 15 (the 14:04:41 span has none). Refill time (`tfus`, the
   `[tcg787]` field) in the span before 14:05:57 is 21 ms. So the storm rides
   along with the load; it is not the 330 ms.
7. **Translation is not the cost.** `gus` (time in `tb_gen_code`) is 12 to 17
   ms per span in the hitch windows, against a baseline median of 16.6 ms.

## 3. The three hypotheses, scored

- **(a) guest-side load at a game event** (the game's own loop after a disk
  read: decompress, copy, or a spin on the device): the data says the guest is
  on-CPU and the hitches are on IDE bursts, so this is consistent. But the
  translated-block profile cannot separate a spin from compute: `[rr425pc]`
  lists only the top 8 to 10 blocks per span (the hash table), and its
  concentration is the same as the baseline. **P ≈ 0.4.**
- **(b) host-side stall in the vCPU thread** (sleep on a lock or a host read):
  present in 2 of 5 (14:05:57, 14:13:15, about 300 ms of sleep each). The IDE
  read path itself is asynchronous, so a host sleep has to come from the
  storage or the BQL, not from `ide_buffered_readv`. It explains two hitches,
  not the class. **P ≈ 0.3 as the cause of the three on-CPU hitches; the sleep
  itself is measured for the two.**
- **(c) the per-word IDE data port costs host time inside the guest's TBs**
  (`ide_data_readw` through the nForce MMIO, one slow-path exit per word, 256
  per sector). The IRQ14-keyed busy per sector is 1.0 to 4.6 ms (for example
  389 ms over 316 sectors, 924 over 230), which would need 4 to 18 us per word.
  That is above what a QEMU MMIO slow path normally costs, so (c) is the less
  likely of the on-CPU causes. Nothing on disk measures it. **P ≈ 0.3.**

(a) and (c) both look like on-CPU guest time behind IRQ14; the telemetry that
separates them does not exist in this build. That is the decision in section 5.

## 4. Telemetry missing to separate them

Nothing in the perflog counts the IDE path. Each candidate below is a
measurement the offline data cannot make:

- per-word time in `ide_data_readw`/`writew` (count, ns, per span) and the
  number of words read per sector: separates (c) from (a) directly;
- per-sector request-to-completion time of `ide_buffered_readv` (host storage
  latency): separates storage latency (b) from per-word cost (c);
- the `[rr425pc]` top list uncapped for the IRQ14 span (or a sample profile of
  the vCPU thread, `simpleperf --app` with host symbols, which the harness
  cannot start today).

## 5. Why no Nova capture in this lane

The brief allowed one capture if the offline data could not decide. It cannot
decide between (a) and (c), and a capture of the current build would produce the
same counters again (the rule is no retest without telemetry). The missing
telemetry lives in `hw/ide/` and `accel/tcg/`, which is outside this lane's
Files (docs/lanes/hitchcause/ only). Running MTV again now would only spend
about 12 minutes of the shared Nova. I have not queued anything.

## 6. P x win for the next step

Ranked by expected impact (P x size of win at full scale). The win is the stall
time a title loses, and the data gives it: MTV had 14 hitches in its held run
(12 after warm-up), 8 of them distinct and 200 ms or more, all in or next to an
IDE burst. Orta's 277 and 386 ms hitches are IDE bursts too (section 7).

| candidate | P that it works | win if it works | cost | first? |
|---|---|---|---|---|
| 1. telemetry in `hw/ide` (per-word ns, per-sector storage latency) + one MTV run | 0.9 that it decides (a vs b vs c) | none by itself | a grant for `hw/ide/core.c`, `hw/ide/mmio.c`, one build, one 12 min run | **yes: it decides which of 2 and 3 to build** |
| 2. read-ahead of the next sector in the IDE PIO path (issue the next read before the guest's last word) | 0.6 if storage latency dominates (single outstanding read is the code) | removes the per-sector wait on every HDD stream: up to the whole burst (200-350 ms; 8 such hitches in about 12 min on MTV) | `hw/ide` change; no pixels (no prediction needed) | after 1 |
| 3. batch the data port (a wider MMIO access, or nForce bus-master DMA for multi-sector reads) | 0.3 if per-word exits dominate; no measurement yet | the same burst, as 2 | larger: a device-model change | after 1, only if 1 says per-word cost |
| 4. the game's own loader compute (guest) | 0.2 by the profile (no concentration, inside-TB no higher than baseline) | that title only | none in the harness; sits under the vCPU JIT direction | no |
| 5. Blood Wake's 1.6 to 3.1 s no-wake stalls | unknown; they are a different class (no IDE wakes; 2 s busy spans with no wake at all) | large, per title | a separate capture of one such stall | separate lane |

Candidate 1 goes first because it decides between 2 and 3 and costs one
build and one run. Candidate 2 is the likeliest fix if 1 shows storage latency;
if the per-word cost is what 1 shows, 3 is the fix.

## 7. Is it MTV-specific or harness-wide?

Harness-wide for titles that stream from the HDD through IDE PIO; MTV-specific
for the exact hitch count.

- **MTV:** an IRQ14 burst sits in the own span or the next one of all 8
  distinct hitches of 200 ms or more (section 2). The 14:04:41 hitch's burst is
  in the next span.
- **Orta** (`panzer-dragoon-hold3`, ISO on the SD card): the hitches of 277 and
  386 ms sit on IRQ14 bursts of 251 and 269 wakes (IRQ14 busy 45 and 119 ms in
  the span); the third (249 ms) has 2 wakes. r = 0.46 over 304 spans. Same
  mechanism, weaker link.
- **Blood Wake** (`lanelocal-3321881`, titles.qcow2 on internal storage):
  the 1,037 ms hitch and the 903 ms and 2,091 ms ones have IRQ14 bursts (170,
  118, 391 wakes), but the 3,098 and 1,586 ms stalls have none, and span 2 s of
  busy with no wake. r = 0.09 over 451 spans. So the IRQ14 mechanism explains
  three of its five big stalls; the two largest are a separate class.

## 8. Recommendation for the lanes that follow

1. A grant for `hw/ide/core.c` and `hw/ide/mmio.c`: a perflog line (per span)
   counting `ide_data_readw`/`writew` calls and their ns, and the storage read
   latency per `ide_buffered_readv` completion; build; one MTV hold of 700 s
   with `--state any` (pathfind's route `5454000B.json`). That decides 2 vs 3.
2. Keep `hitch_report.py` as it is (no change to thresholds, per the brief). The
   shader and texture classes do not see this; it should get an IRQ14 column
   (`[rr425w]` buckets with `vec 0x3e`) in a later lane that holds the grant.
3. Do not retest MTV with the current build to see the hitches again: the
   telemetry for the decision is already in this directory.

## 9. Caveats

- The rr425w, idlehalt, pace and gfps cadences are not aligned; a span can be
  off by one. The IRQ14 test uses the span closing within 2.1 s before and 0.6 s
  after each pace window, so a burst can count for two adjacent hitches.
- `run%` is one idlehalt line per span; `busy` is the guest's wall-clock
  measure, which includes host sleep. Both are as the code defines them
  (`system/cpus.c`, `accel/tcg/cpu-exec.c`), not measured against a second
  instrument.
- Vector 0x3e = IRQ14 is an inference (section 2, finding 2).
- The `[rr425pc]` profile is capped at its hash-table size (8 to 10 entries per
  span), so no concentration result from it is meaningful.
