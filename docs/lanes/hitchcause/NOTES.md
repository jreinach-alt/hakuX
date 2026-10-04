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

## 5. Why no Nova capture in this lane (attempt 1; superseded by section 10)

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

## 10. Attempt 2: the instrument, the one MTV hold, and what it changes

Build: `b559c094eb` (perflog; the `[ide425]` window line in `hw/ide/core.c`).
Runs, all on the Nova:

| run | what | result |
|---|---|---|
| `1-1791150826-lane.hitchcause-2424636` | smoke, `805cb8054f`, per-command line, 120 s MTV survey | no `[ide425]` line at all |
| `1-1791151242-lane.hitchcause-2557798` | smoke, `b559c094eb`, window line, 150 s MTV survey | 24 windows; boot bursts (552 IRQs in one 2.0 s window) with no PIO |
| `docs/lanes/hitchcause/capture_mtv_ide425.sh` (hold `lane.hitchcause`) | pathfind 5454000B, `--hold-s 700 --state any`, 15 min wall | **FAIL**: 166 s of play, then pathfind's hold went to the main menu for 13 steps and stopped. 23 windows, 160 pace lines, one hitch at 100 ms or more (210 ms at 15:22:26) |

The hold ran once (owner's one-hold allowance). It was not the 700 s play the
brief asked for, so the 330 ms class did not recur in it and cannot be
diagnosed from it. Logcat: `perf/2026-10-04-hitchcause/mtv-ide425/pf/logcat.txt`.
Analysis: `ide425_windows.py` (stdlib; in this directory).

**The window line settles the path question.** Across 23 windows of the hold
and 24 of the smoke run, `rd_sec` (PIO read sectors submitted) is 0 in every
window, and the data-port word count `w` is 0 in every hold window. No PIO
sector read happened during 11 minutes of MTV. The per-command line in the
first smoke printed nothing for the same reason: no PIO read command began.

**The IRQ14 wakes are not the IDE model's interrupts.** In the 15:22:26
hitch's span, `[rr425w]` shows 200 wakes on vector 0x3e, while the IDE model
raised 7 interrupts in its 7 s window. So the wakes outnumber the IDE raises by
about 30 to 1. The boot shows the same shape the other way: 552 IDE raises in
one 2.0 s window with no sectors and no words. The IDE raises come from
`ide_bus_set_irq` (about 40 call sites), and none of the sites is a PIO read.

### Corrections to sections 1 to 8

- **Finding 3 (one IRQ per PIO sector, one burst is one stream) is refuted.**
  No PIO sector was read in the hold.
- **Section 2 finding 1 (r = 0.74 of IRQ14 busy against the worst frame)** keys
  on vector 0x3e. The mapping 0x3e = IRQ14 = primary IDE is an inference, and
  the hold contradicts it: the wakes are not the IDE's interrupts. Read the r as
  a correlation with a vector key, not with the IDE device.
- **Sections 3 (c) and 6, candidates 2 and 3** (read-ahead of PIO sectors,
  batching the data port) assume PIO sector reads. None was observed.
- **Section 7 (MTV-specific or harness-wide)** rests on the same key. The claim
  that the bursts are one mechanism across Orta and Blood Wake is unverified;
  what holds is that vector 0x3e wakes co-occur with hitches in those logs.
- **Section 5** (no Nova capture) is superseded by this section.

### Diagnosis: the 2-vs-3 question

Neither branch. The data does not show the IRQ14/0x3e stream as PIO sector
reads, so branch 2 (storage latency, read-ahead) and branch 3 (per-word data
port cost) have nothing to act on for these hitches. The question becomes what
raises vector 0x3e at about 100 per second with no PIO traffic, and whether that
source is what the hitch waits on. One hitch in this hold is not enough to say.

Per hitch, from this run:

| hitch (PDT) | worst ms | route | IDE raises / window | vector 0x3e wakes | PIO sectors | cause |
|---|---:|---|---:|---:|---:|---|
| 15:22:26 | 210 | play | 7 (7 s window) | 200 (span) | 0 | not separable: the wakes have no IDE source here |

The five 330 ms hitches of the 10-04 hold are not in this run, so their causes
are **not separable with this telemetry**.

### P x win for the next step

Ranked by expected impact. The win is the stall the hitch class costs a
title; the 10-04 hold had 14 hitches in 689 s (1.15 per minute, worst 349 ms).

| candidate | P that it decides or works | win if it works | cost | order |
|---|---|---|---|---|
| A. Count what raises IRQ14 at the PIC input: `pic_set_irq` in `hw/intc/i8259.c`, per 2 s, tagged by caller, next to the `[rr425w]` vector | 0.7 that it names the source: the 200 wakes vs 7 raises says the vector has a source the IDE model does not see | the 330 ms class, if that source is what the hitch waits on: 1.15 per minute on MTV, up to 349 ms each | a grant for `hw/intc/i8259.c` (not in this lane's Files); one build; one 2-minute smoke | **first** |
| B. Count `ide_bus_set_irq` by call site and `ide_bus_exec_cmd` by command byte, and count `ide_dma_cb` completions, per window | 0.5 that the boot's 552 raises are commands or DMA; 0.1 that it explains the hitch's 200 wakes (7 raises at the hitch) | same as A, if it names the source | `hw/ide` only (granted); rides in A's build | with A |
| C. A second MTV hold, 700 s of play, on A+B's build | 0.5 that it reproduces the class (1 hitch in 166 s here, 14 in 689 s on 10-04) | none by itself; needed to test A | one 700 s hold; **the owner's decision** (the addendum allows one) | after A+B |
| D. Read-ahead of the next PIO sector (old candidate 2) | 0.05: no PIO sector read was observed in 11 min | 330 ms per burst, if it worked | `hw/ide`; no pixels | no |
| E. Batch the PIO data port (old candidate 3) | 0.02: no PIO words were observed | as D | `hw/ide` plus MMIO; larger | no |
| F. Blood Wake's 1.6 to 3.1 s stalls (no IRQ14 wakes at all) | unknown; separate class | large, per title | separate lane | separate |

A first, because it decides whether the 200 wakes have a source outside the IDE
device; everything else is downstream of that name. B rides in the same build
for free. C needs the owner's approval for the second hold, and it is the only
way to test A's result against the hitch class.

### What is needed from the board

1. **A grant for `hw/intc/i8259.c`** (candidate A's counter). Without it, A is
   not possible in this lane.
2. **The owner's decision on the second MTV hold** (candidate C).
3. Nothing else. `hitch_report.py` is unchanged (no change to thresholds, per the
   brief); its shader and texture classes do not see the vector-0x3e wakes, and
   a later lane with the grant should add a column for them.

### Caveats

- One hold, 166 s of play. A 23-window sample cannot rank causes, only refute
  the PIO path.
- The `[ide425]` window closes from the IDE IRQ path, so a window with no IDE
  interrupt prints nothing; the 7 s window at the hitch is the only one covering it.
- `w` times the data-port handler only; the TCG MMIO dispatch in front of it is
  not timed, as the line says.
- Vector 0x3e = IRQ14 is still an inference, and this section lowers its weight.

## 11. Attempt 3: why attempt 2 did not finish, and what this attempt adds

**Why attempt 2 did not finish.** It did the build and the one MTV hold it
was granted, but the hold stopped at 166 s of play (section 10), so the
330 ms class never recurred and section 10 could not place any of the five
330 ms hitches. It also named the next step, a count of what raises IRQ14
at the PIC input, without the grant for `hw/intc/i8259.c` that makes that
count possible. The grant reached the board afterwards (`cfefd28651`). Its
PR.md stayed `State: ready` with a Next that depended on that grant, so
a fold could have landed a claim whose own next step was still open. This
attempt picks up that step and does not change the fold state until it is
closed.

**What this attempt adds.** A `[pic14]` window line in `hw/intc/i8259.c`
(commit `d4b0169ab2`, telemetry only): per 2 s, the slave PIC's raises of
pin 14 (`raise`), the raises that find `last_irr` clear (`edge`), the
deassertions (`lower`), the CPU's acks (`ack`) and the EOIs (`eoi`), with
the slave's ISR and IMR at the window's close. The line prints on any PIC
event after the 2 s elapse, so an idle window is not silent.

**The test.** `ide_bus_set_irq` in `hw/ide/core.c` raises the line through
`qemu_irq_raise`, and the `[ide425] irq=` field counts those raises. So the
two lines in the same window are comparable:

- If `[pic14] edge` tracks `[ide425] irq` in the hitch windows, the IDE model
  is the source, and the 200 vector-0x3e wakes of section 10 were a
  mis-keyed count, not a second device.
- If `[pic14] edge` is far above `[ide425] irq` (about 200 against 7) in the
  hitch windows, something other than `ide_bus_set_irq` asserts pin 14, and
  the next step is to tag its caller (a wrapper at the `qemu_irq` source,
  outside this lane's grant unless the board says otherwise).
- If `[pic14] ack` is near zero while `raise` is high, the line is asserted
  but masked or not serviced; `isr`/`imr` at the close says which.

**Priors, scored.** Each is the probability the test picks it, with its
evidence:

| candidate | P | evidence | win if it is the source |
|---|---:|---|---|
| the non-IDE source asserts pin 14 (outside `ide_bus_set_irq`) | 0.6 | section 10: 200 wakes on vector 0x3e against 7 IDE raises at the one hitch | the 330 ms class (14 hitches in 689 s on MTV), if the vCPU waits on that source |
| the IDE model raises, and section 10's 200-wake count was keyed wrongly | 0.3 | the vector key is an inference (section 9); the window line was added after the one hitch | none; it closes the IDE question |
| the line is masked or unserviced (`ack` low, `imr` set) | 0.1 | no measurement yet | depends on what it blocks |

**Decision rule, fixed before the run.** Queue ONE 700 s MTV hold only if the
smoke's `[pic14]` lines print on the build. The hold's result is read
against the table above; the 330 ms class recurring in the hold is what
makes the windows usable. If the class does not recur in 700 s, park with the
table and report it on #433; the brief allows no third hold.

**Build and run.** Commit `d4b0169ab2` (the `[pic14]` counters, pushed).
Smoke `1-1791153154-lane.hitchcause-3372110`: 150 s MTV, `--perflog`,
`--ref d4b0169ab2`. The smoke builds the APK (the dispatcher builds on a
claim); the hold uses `builds/d4b0169ab2-perflog.apk`.

**Checks.** The change is inside `hw/intc/i8259.c`, and every counter update
is a plain increment with no change to the IRQ, IRR, ISR or EOI logic.
The Android build is the only compile check the dispatcher gives. A desktop
build is not run here: AGENTS.md's desktop build needs `libcurl`, which is
not installed on this host, so this lane cannot claim a desktop build.
