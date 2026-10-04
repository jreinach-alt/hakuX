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

## 5. For the next lane

- Do not read "vCPU 100% busy" in Kabuki as guest work: it spins in every
  window.
- "Blocks invalidated per flush" is 0 by construction for a TLB flush;
  `disc` per window is the #68 number.
- A `tb_flush()` is invisible in every run's logcat (hakuX-tb is not in the
  spec); use `[tcg787]` tbf, or jc - jct - jci on older runs.
