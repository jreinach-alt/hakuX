# lane.flushstall787 (#787): is the guest-late stall the TLB flush?

Brief: `briefs/flushstall787.md`. Instrument first, one Kabuki measurement,
then fix it (re-translation) or name the guest cause (guest-side).

## 1. What a TLB flush can cost, read from the code

A full TLB flush does **not** discard translated blocks in this tree.
`tlb_flush_by_mmuidx_async_work()` (accel/tcg/cputlb.c) clears the TLB of
each dirty mode and calls `tcg_flush_jmp_cache()`; TBs are found by physical
address in `tb_ctx.htable` and survive. So "re-translation after the flush"
has no mechanism behind it, and the flush's fallout is:

1. the flush work itself (TLB memset + jump-cache wipe; `[tlb68]` jcus times
   only the second),
2. **TLB refills**: every page touched after a CR3 reload misses and pays
   `tlb_fill_align()` (a guest page walk + `tlb_set_page_full`). That runs
   inside TB execution (the softmmu slow path), so `[rr425]` tbus counts it as
   guest time, and nothing timed it,
3. the jump-cache misses after a wipe (a qht lookup per TB entry, in
   `[rr425]` gapus).

What DOES discard blocks is (a) a code-page write (#68's whole-page
invalidation, `hakux_tb_discarded`) and (b) `tb_flush()` when the code buffer
fills, which discards every block. (b) logs `hakuX-tb` ... `TB FLUSH`, a tag
that is in no LOGCAT_SPEC, so no run on disk shows one directly. A run
predating `[tcg787]` still has one trace of it: a jump-cache wipe that is
neither a TLB flush's (`jct`) nor an invalidation's (`jci`), i.e.
`[tlb68]` jc - jct - jci > 0 (`fs_jcx.py`).

## 2. What the runs on disk already say (no device time)

Tools: `fs_windows.py` (per-window counters), `fs_pages.py` (hakuX-pages
generation counts next to stalls and bursts), `fs_jcx.py`, `fs_judge.py`.

**Kabuki, 1791054199-lanelocal-1518681 (perflog, GPL=3).** Ten of its eleven
stalls >= 400 ms overlap a `[tlb68]` burst. The 698 ms stall (w=188-189):

| | w=187 (before) | w=188 (stall) | w=189 (after) |
|---|---:|---:|---:|
| ff (all cr3s, same-value CR3 reloads) | 0 | 377 | 0 |
| pf (INVLPG) | 0 | 16,509 | 0 |
| `[rr425]` it (dispatches) | 53,944 | 349,702 | 49,192 |
| `[rr425]` gapus (loop time between TBs, contains tb_gen_code) | 22.7 ms | 46.5 ms | 17.7 ms |
| `[rr425]` tbus (inside TBs) | 2.63 s | 2.20 s | 2.52 s |
| `[rr425w]` idle_us (kernel idle loop) | 0 | 21 ms | 0 |
| fast TLB entries (mode 5) | 2048 | 512 (5 resizes) | 512 |

hakuX-pages' 120-frame line holding that stall: **79 blocks generated of
2,874 tb_gen_code calls** (2,795 recycles). Across the nine post-boot burst
stalls: 20 to 861 generated, and 2,727 for one 539 ms stall before the
gameplay mark; the boot window generated 25,070 with gapus 1.35 s, which
bounds a generation at <= ~54 us. The other Kabuki run
(1791040252-lanelocal-978819) repeats it: 747 ms stall, 161 generated;
697 ms stall, 73 generated. The burst signature repeats too (ff 377 / pf ~16k,
ff 176 / pf ~21k).

Kabuki spins: the vCPU is ~100% busy in every window, stall or not, with
~50k dispatches per 2 s and no idle. "vCPU busy" cannot separate guest work
from spin here. What changes in the stall window is the exits: the kernel
idle loop (8001b02e) returns 102,876 times, blocks ended by FLDCW at 000bb4ce
and 000bb8f9 ~25k times each, INVLPG sites at 8001f4e3 / 8001fb32
(`[rr425pc]`).

**Reading before the run:** translation cannot be Kabuki's 0.7 s (at most
~64 ms of loop-gap time in the stall windows). The open part is the refill
cost after 377 flushes, which hides in tbus; bound: <= ~600 live entries per
flush interval x 377 x ~1 us = ~230 ms.

**Tron, 1-1791057797-lanelocal-2547673 (perflog).** Different. Seven of its
eight post-boot stalls >= 400 ms sit in 120-frame lines with **15,785 to
48,572 blocks generated** (one, 1,375 ms at ~56 s, has 2,186), and the
`[rr425]` loop-gap time over the stall windows is 0.75 to 5.1 s. The 1,762 ms
stall carries a `tb_flush()` trace (jc - jct - jci = 1 at w=72) and 48,572
regenerations; the others carry 1.7k-8.3k blocks discarded by code-page
writes. That is re-translation, but its trigger is a code-cache flush or code
loading, not a TLB flush.

## 3. The instrument (commit 1fe520a709)

`[tcg787]`, one line per `[tlb68]` window with the same w, printed from
`hakux_tlb68_tick()`:

- `gc gus cgus gmax`: tb_gen_code calls that returned, their total us, the us
  of those that generated code, the longest call (a wrapper in
  translate-all.c around the old body; every caller goes through it);
- `cg`: generations; `disc`: blocks discarded by code-page writes;
  `tbf`: tb_flush()es;
- `ffus pfus`: full-flush and INVLPG worker time;
- `tf tfx tfus`: tlb_fill_align calls, those that raised a guest fault, and
  the time of the returned ones (perflog builds only; `pl=1`).

`[tpc787]`, one line per `[rr425]` window: each of `[rr425]`'s timed
dispatches (1 in 64) is charged its run time against the pc it entered at, so
the top entries are a duration-weighted profile of where TB time goes (a
chained loop is charged to its entry block). `[rr425pc]` counts returns, which
a long chained run does not make.

Cost, as bounds (not measured): tb_gen_code 2 clock reads per call at
<= 10,000 calls per 2 s (Kabuki's maximum on disk) = <= 2 ms per window
at <= 100 ns a read; flush workers <= ~21k + 400 per window, only in burst
windows; fills are timed only under perflog because their rate is not bounded
by anything above.

Checks: `ndk_check.py` compiles the three files with the dispatcher build
tree's NDK command, plain and `NV2A_PERF_LOG=1` (rc 0 both, no new warnings).
No desktop build on this host (AGENTS.md: the known gap), so the "counter
moves when translation happens and reads ~0 when it does not" check is in the
run itself, as validity legs V2-V4 of the predictions: the boot window's
heavy translation must read gus >= 50 ms while windows with <= 20 generations
read <= 20 ms; summed gus must sit inside `[rr425]`'s independent loop-gap
estimate; gc must track hakuX-pages' call count.

## 4. Measurement runs

Predictions, registered before queueing, on ref 1fe520a709:
`docs/testing/predictions/flushstall787-kabuki.json` (the brief's run) and
`flushstall787-tron.json` (added: the on-disk data predicts the opposite
answer for Tron, and one run of the same build settles it).

Queued 2026-10-03 17:05 PDT at release tier, pinned to the Nova, ref
1fe520a709 (perflog; the same commit builds locally, GRADLE_EXIT=0, 8m21s):

- Kabuki `1-1791072687-lane.flushstall787-1209260`, 840 s, HAKUX_GPL=3,
  route `kabuki-warriors`. request.sh resolved it to the route's own
  `first-run` state; Kabuki has no returning route, and both runs on disk ran
  this state, so they compare directly.
- Tron `1-1791072697-lane.flushstall787-1209966`, 750 s, route
  `vcpuwait433/tron-newgame-anystate` (the route of the on-disk Tron run).

**Waiting (17:45 PDT):** both requests are first in the queue, behind
pathfind's Halo 2 holds on the Nova (`hold/nova`, renewed 00:38Z). The session
stops here; handback resumes it when the runs finish. Then:
`fs_judge.py <dir>` (Kabuki) and `fs_judge.py <dir> --all` (Tron).

## 5. Attempt 2 (2026-10-03 19:20 PDT): why attempt 1 stopped, and the results

Attempt 1 did not fail: it stopped by design on a `waiting:` for its two
Nova runs, which sat behind pathfind's Halo 2 hold. Both have now finished
(Kabuki DONE 18:09 PDT, Tron 18:22 PDT, apk 66ded35425cd, `[tcg787]`
`pl=1` on every window), and this attempt judges them.

### 5.1 Kabuki (the brief's run): **not the flush, and not translation**

`fs_judge.py 1-1791072687-lane.flushstall787-1209260`: validity V1-V5 all
pass (422 `[tcg787]` = 422 `[tlb68]`; heavy-translation windows read up to
154 ms gus against a 4.6 ms quiet median; gc / hakuX-pages calls = 1.001).
**Leg G PASS, leg F PASS.** Per stall >= 400 ms that overlaps a burst, summed
over its windows:

| stall t (log s) | max ms | windows | ff | pf | gen | gus ms | refill tfus ms | F ms (all flush fallout) | loop gap ms |
|---|---:|---|---:|---:|---:|---:|---:|---:|---:|
| 64560.7 | 632 | 23-24 | 378 | 12,724 | 871 | 19.6 | 15.7 | 40.0 | 68 |
| 64669.3 | 439 | 77-78 | 75 | 11,853 | 418 | 14.3 | 8.5 | 26.8 | 94 |
| 64698.5 | 507 | 92 | 214 | 22,258 | 2,692 | 41.7 | 15.5 | 66.1 | 372 |
| 64776.6 | 588 | 130-131 | 74 | 15,899 | 602 | 34.6 | 19.4 | 63.5 | 340 |
| 64780.2 | 569 | 132-133 | 219 | 19,189 | 134 | 29.9 | 29.1 | 73.8 | 234 |
| 64783.3 | 705 | 133-134 | 198 | 24,711 | 96 | 29.3 | 34.6 | 83.4 | 452 |
| 64868.6 | 672 | 176-177 | 377 | 15,862 | 102 | 13.4 | 19.3 | 38.6 | 62 |
| 64874.0 | 401 | 179 | 77 | 12,463 | 19 | 5.7 | 8.0 | 17.5 | 77 |

One more stall (64704.4, 736 ms, w=95) has no burst (ff=0, pf=0): the guest
is idle there (`[rr425w]` idle 1.06-1.29 s per window, woken mostly by the
timer vector 0x30), i.e. waiting, not computing.

**What the guest does instead** (`fs_guest.py`, `[tpc787]` scaled by
`[rr425]` tbus). In a quiet window the title's wait loop entered at
`000a8330` holds 91-98% of TB time and everything else is 70-270 ms. In every
burst-stall window that loop falls to 11-76% and other guest code takes
**400-1,320 ms**, in the same routines each time:

- title FP routines `000bb4d2` / `000bb8fc` / `000bb9e6` (130-250 ms per
  window; the blocks ending at FLDCW at 000bb4ce / 000bb8f9 in the on-disk
  `[rr425pc]`),
- `000b8fff` (an x87 loop, `d8 07` fadd [edi]) at 275-548 ms in w=92 and
  w=133-134,
- the guest kernel: `80014386` (75-145 ms) and the INVLPG site `8001fb35`,
  with the memory manager's 12-25k INVLPGs and 75-378 same-value CR3 reloads.

So the stall is the title's own CPU work at a scene/memory transition (it
unmaps and remaps thousands of pages and runs FP-heavy routines), executed at
TCG speed. The flush is a symptom of that work, not its cost: the flush and
everything it causes (worker time + refills + all translation) is <= 83 ms of
a 400-736 ms stall.

**One TCG-side cost that is not the flush** (reported, not fixed, per the
brief): `000b8fff` starts one byte before a page boundary, so its TB spans two
pages, and QEMU never chains into a two-page TB (`[rr425]` gs). w=92 made
3,776,471 such dispatches (median window: 1,806) and its loop gap is 372 ms
against a 19 ms median; w=133 / 134 made 1.44M / 2.36M and read 175 / 277 ms.
That is ~96 ns of dispatch per pass, about 350 ms of the 507 ms stall at w=92
and ~400 ms over the 705 ms stall at w=133-134. It touches 2-3 of the 9
stalls; the rest are pure guest TB time.

### 5.2 Tron (the added run): translation is real but small, and not from a flush

`fs_judge.py ... --all` on 1-1791072697-lane.flushstall787-1209966: validity
all pass. Against `flushstall787-tron.json`:

- **G holds as worded** (>= 400 ms in at least one stall: 474 ms over the
  1,732 ms stall, 428 ms over the 739 ms one), but those sums span 5-6
  windows (10-12 s). Per 2-s window gus peaks at **189 ms** (w=180).
- **T refuted on its trigger**: tbf = 0 in every stall (no code-cache flush
  this run). Generations exceed discards ~5-7x (50,941 gen vs 9,562 disc;
  47,832 vs 6,691): mostly **first-time translation of newly loaded code**,
  which no invalidation change can remove.
- **F holds**: the TLB flush's own fallout (tfus + ffus + pfus) is 11-117 ms
  per stall, under the 150 ms band in all eight.

And what holds the stall windows: `fs_guest.py --spin none`. Right after a
translation window (w=68, w=180: 19-23k generations, page-crossing
`000dafff`), the next windows (w=69-70, 181-182) spend 1.2-1.35 s of 2 s in
the guest kernel at `80014386` and a loop at `80027beb-80027c5d`, then the
title resumes at `004ea0f7` / `0045e46b`. The stalls are the guest loading
code and running kernel routines over it (a loader or a copy/zero pass), not
the emulator's translation.

### 5.3 Answer to the brief

**Is the guest-late stall the TLB flush? No, in both titles.** A TLB flush
discards no translated block here; what it costs (its worker time plus the
refills after it) is at most 83 ms per Kabuki stall and 117 ms per Tron
stall. Translation is at most 42 ms per Kabuki stall, and in Tron at most
189 ms per window, mostly first-time code. The stall time is guest
execution: Kabuki's FP routines and kernel memory management at a transition,
and Tron's kernel routines after a code load. Per step 4: stop, no fix.

Options for whoever takes it next, ranked by P x win:

1. **vCPU execution speed** (the owner's 09-28 JIT direction). It is the only
   lever on the whole stall: every stall above is guest TB time.
   P high that it scales these stalls down, win: all of them in all three
   titles. Large effort.
2. **Chain into two-page TBs** (at least a two-page TB looping to itself,
   which on a single-vCPU guest cannot see its second page remapped
   mid-chain without leaving through an exit). P medium: the safety argument
   needs to be made against the code, and it removes only dispatch overhead.
   Win: ~0.2-0.35 s in 2-3 of Kabuki's 9 stalls, and some of Tron's loop gap
   (gs up to 62k per window there, so small). Small effort; it is a
   measurement-backed lever and not a hoped-for one, but it does not fix
   Kabuki on its own.
3. Page-range invalidation (#68): removes only re-translation of discarded
   blocks, here <= 42 ms (Kabuki) and a minority of Tron's 189 ms. Do not
   start with it for these stalls.

## 6. For the next lane

- Do not read "vCPU 100% busy" in Kabuki as guest work: it spins in every
  window.
- "Blocks invalidated per flush" is 0 by construction for a TLB flush;
  `disc` per window is the #68 number.
- A `tb_flush()` is invisible in every run's logcat (hakuX-tb is not in the
  spec); use `[tcg787]` tbf, or jc - jct - jci on older runs.
- Do not chase the TLB flush or #68's invalidation for Kabuki's, Tron's or
  (by the same signature) SW3's late stalls: measured, it is <= 83 / 117 ms
  per stall. A `[tlb68]` burst marks the guest's own memory work.
- `fs_guest.py <dir> <windows>` reads where the guest's time goes per window;
  `[rr425]` gs is the count of unchained two-page-TB dispatches.
- A stall's judged span covers every window its 60 flips touch, so a sum over
  it can pass a per-stall threshold while no window is dominated by it. Read
  per window too.

## 7. Attempt 3 (2026-10-03 20:52 PDT): why attempt 2 did not finish

Attempt 2 ended after the OUTBOX and PR body (0e0aab6a5e) without a
`WAITING` file, so nothing would resume the lane for the head device run the
fold needs. This session only writes `WAITING` (`time 2026-10-04T00:15`), per
hostops' 20:5x addendum: the Nova is on the Playable push until midnight.
Still to do at 00:15: gate every `[tcg787]`/`[tpc787]` hook under
NV2A_PERF_LOG (lane.local's 20:2x item 1), queue the Kabuki `--perflog` head
run from that head, then write `WAITING` with `run <request-id>`.

## 8. Attempt 4 (2026-10-04 00:19 PDT): why attempt 3 stopped, and what this one did

Attempt 3 did not fail: it did only what hostops' 20:5x addendum ordered
(write `WAITING` `time 2026-10-04T00:15` and end), because the Nova was on the
Playable push until midnight. lanewaker resumed this attempt at 00:19.

- **Hooks perflog-only** (lane.local 20:2x item 1), 7b4ab7823e. `HAKUX_TCG787`
  (`XBOX && NV2A_PERF_LOG`) gates: translate-all.c's tb_gen_code wrapper;
  cputlb.c's full-flush and INVLPG worker timers, the tlb_fill_align wrapper
  and the `[tcg787]` line (always `pl=1` now, kept for fs_judge); cpu-exec.c's
  `tpc787_pc`/`tpc787_book` on the execution path, `tpc787_tick` and the reset.
  `ndk_check.py` counts #787 symbols per object: plain 0/0/0, perflog 4/20/4.
  **Its old "plain" leg was a second perflog compile**: the dispatcher build
  tree's command already carries `-DNV2A_PERF_LOG=1`. It strips it now. Do not
  trust a plain/perflog compile check without looking at the define list.
- **Head run** queued after merging origin/master (4991143fde) into the
  branch: `1-1791098627-lane.flushstall787-847488`, ref 0b8b63bef1, Kabuki,
  840 s, perflog, GPL=3, Nova, release tier, no prediction. To read it:
  `fs_judge.py <dir>` validity V1-V5, `[tcg787]` and `[tpc787]` on every window.
- **cputlb.c and memfast**: lane.local's 21:2x addendum held cputlb.c until
  memfast folded. Since then origin/board retired `[lane.memfast]` and granted
  cputlb.c to this row, and memfast's head b41a8e4c2f (00:08) closed its F1 PR
  (F1 rejected). No memfast fold is coming, so WAITING does not name one.
- **Two-page TB chaining priced** (item 3), `fs_gs_scan.py`: 590 runs on disk;
  6 titles have any window at gs >= 1M. THPS2x carries most of it (504 of 1,321
  windows, loop gap 1.0-1.6 s per 2-s window there vs 25-32 ms), then Kabuki's
  stalls and MechAssault 2. Per-gs cost is not constant: ~95 ns in Kabuki,
  ~0.6-1 us in THPS2x. Estimate ~0.2 titles moved to their fps target; it
  clears no title alone. OUTBOX has the table and the P x titles; waiting for
  lane.local before any work on it.
- Preflight `--allow-tracker`: every gate passes except `coverage` (#794-#797
  have no lane or blocker), which is the board's.
