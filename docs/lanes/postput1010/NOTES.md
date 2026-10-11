# lane.postput1010 (#433): the posted DMA_PUT store at NFS Most Wanted's race start

Step 2b of `docs/lanes/nfs30plan1010/PLAN.md`. Branch `lane/postput1010`, from master @ b74cff74ed with
`origin/lane/reportasync1010` @ 4b50801b21 merged in (0d7948085e), because `HAKUX_REPORT_ASYNC` is only there.

## 1. Why

reportasync1010's frametrace pair at the NFS race start (perflog, ref a21a3361d9;
`1-1791671433-reportasync1010-3857080` without the switches, `1-1791671434-reportasync1010-3857196` with
`HAKUX_REPORT_ASYNC=1 HAKUX_TEXSCAN=1`). Read here with `ppread.py --ft` over the same windows. On the switched
run, over all warm frames:

| | without | with RA + TS |
|---|---|---|
| period P | 53.60 ms | 44.81 ms |
| guest wait for pfifo.lock to store DMA_PUT (`lockw`) | 0.09 ms | 6.27 ms |
| PFIFO thread idle, waiting for the guest (`pidle`) | 10.63 ms | 13.56 ms |
| frames with the guest busy past 2 VBLANKs | 17 % | 46 % (5 % without `lockw`) |

On heavy frames (vb >= 3) the wait is 7.31 ms against 0.09 (the brief's figure). Once the report wait is off the
PFIFO thread, the two threads serialize on `pfifo.lock`: the guest waits for the PFIFO thread to let go of the lock,
then the PFIFO thread waits for the guest's next push. The "5 %" is a bound, not a value: it assumes the wait goes
away with nothing in its place.

## 2. The change (`HAKUX_POSTED_PUT=1`, default off)

Prior art: lane.vcpusleep's `c2dfca18a1` (#507), reverted in `f6ac723228` because Simpsons is GPU-paced and lost
fps (40.05 -> 36.22) even though the guest's sleep went away. This lane ports that design to the current pfifo.c
behind a runtime switch.

- `user_write` (user.c): for a DMA_PUT store when `pfifo_dma_put_may_post()` holds (switch on, skew bound off, the
  channel is in DMA mode and is CACHE1's channel, all read lock-free the way `user_read` reads them), try the lock.
  If it is free, run the locked store below, unchanged. If it is busy, `pfifo_post_dma_put()`: store DMA_PUT with
  release, then `pfifo_post_kick()`. Every other store, and every store with the switch off, runs master's timed
  `qemu_mutex_lock` and the locked path.
- `pfifo_post_kick()`: store `fifo_kick` with release, `smp_mb()`, read `parked`. If parked, take the lock (timed
  into `lock_wait_ns`, so `lockw` still shows every wait the guest makes for the lock), broadcast `fifo_cond`, unlock.
- PFIFO thread, loop top: `pfifo_take_kick()`. Off: master's plain read and clear. On: `qatomic_xchg(&fifo_kick,
  false)`, then `put_seen = load_acquire(DMA_PUT)`.
- PFIFO thread, every idle wait (three sites: after the 100 us spin, the non-spin idle wait, and the build without
  `XEMU_OPT_FIFO_SPIN`): `pfifo_park()`. Off: master's plain `qemu_cond_wait`. On: `parked = true`, `smp_mb()`,
  wait only if the kick is clear and DMA_PUT still equals `put_seen`, then `parked = false`.
- Pusher: with the switch on it loads DMA_PUT with acquire (off: master's plain load), so it sees the pushbuffer
  words the guest wrote before the posted store.
- Instruments: the `fifoskew` line gains `posted=N` (stores posted, Android only). A posted store records only its
  time (`posted_ts`, the oldest not yet taken up); the PFIFO thread records the submission under the lock
  (`pfifo_take_posted()`): at the loop top, or at the pusher's catch-up if the DMA_PUT it caught up with is still
  the newest, so a submission is never retired before it was consumed.
- The switch is read once (`pfifo_posted_put_on()`, a static cached with cmpxchg, the way `HAKUX_REPORT_ASYNC` is
  read). With it on, the build logs `[postput] on, skew bound mode N` on `hakuX-lane`; with the bound on it adds
  "(inert: the bound needs the lock)" and posts nothing.

### 2.1 Why every wakeup still happens, on this base

The PFIFO thread can sleep in exactly one place: `qemu_cond_wait(&fifo_cond)` inside `pfifo_park()`, called from
the three idle sites in `pfifo_thread()` (pfifo.c, the `if (!qatomic_read(&d->pfifo.fifo_kick))` block after
`pgraph_process_pending_reports()`). Everything else it waits on (report fences, `wait_frame_submitted`, the
render thread) is woken by other threads, as on master, and holds the lock, so no poster is involved there: a
store that arrives then is posted, and the thread sees it at its next loop top.

A posted store has to reach a thread that is in one of four states:

1. **Running under the lock** (pusher, pending, reports): the poster's kick is set; the loop comes round to
   `pfifo_take_kick()`, sees it, and runs the pusher again with the acquire-loaded DMA_PUT.
2. **In the unlocked 100 us spin**: the spin reads `fifo_kick` with `qatomic_read` every iteration, sees the
   posted kick, and goes round without parking.
3. **Between the spin and the wait, or already waiting**: the store-buffering handshake. The poster stores DMA_PUT
   and `fifo_kick`, full barrier, reads `parked`. The PFIFO thread stores `parked`, full barrier, reads `fifo_kick`
   and DMA_PUT. With a full barrier between each side's store and its load, the two loads cannot both miss the
   other side's store. Either the thread sees the kick (or a DMA_PUT newer than `put_seen`) and does not wait, or
   the poster sees `parked` and broadcasts under the lock. It can take the lock only once the thread is inside
   `qemu_cond_wait` (which released it) or has left it, so the broadcast cannot fall between the thread's check
   and its wait.
4. **Halted** (`pfifo.halt`, `nv2a_lock_fifo()`): unchanged. Those paths take the lock and kick under it, as on
   master; a posted store that lands then is seen at the next loop top after the halt is lifted.

The DMA_PUT re-read in `pfifo_park()` is the change from `c2dfca18a1`'s handshake, which compared only the kick.
Two cases it covers:

- `c2dfca18a1` stored the kick with a relaxed store after DMA_PUT's release store. Release orders what comes
  BEFORE the store, not the store before what comes after, so on ARMv8 the kick can become visible before
  DMA_PUT. The thread could clear the kick, run the pusher on the old DMA_PUT, and park; the poster, having read
  `parked` false before that, would not wake it. The kick is now a release store (the thread's xchg acquires it,
  so seeing the kick means seeing DMA_PUT), and the park compares DMA_PUT against what the loop top saw.
- A third writer of the kick (any locked `pfifo_kick()` caller, `nv2a_lock_fifo()`): if the thread clears a kick
  set by another thread just after the poster's, it has consumed "the" kick without seeing the poster's DMA_PUT.
  The DMA_PUT re-read catches that whoever set the kick. Neither x86-64 (TSO) nor ARMv8 (other-multi-copy atomic)
  can actually produce that interleaving for these two stores from one thread; C11 allows it, so it is guarded
  anyway. No host test can show it fire, and the selftest's header says so.

The rest of pfifo.c's kick accesses (`pfifo_kick()`'s read and set, the three idle checks) became `qatomic_read`
/ `qatomic_set`, relaxed, which compile to the same plain loads and stores they replace.

Two plain reads outside this lane's files see a posted DMA_PUT without the lock, both benign:

- `pgraph/vk/reports.c:1064`, `*dma_get == *dma_put` before a STALLED finish. A stale (older) DMA_PUT makes the
  finish proceed as master would have at that instant; the posted store is taken up at the next loop top.
- `nv2a.c:1362`, `nv2a_lock_fifo()`'s plain `fifo_kick = true`, under the lock. A concurrent post also stores
  `true`; the xchg at the loop top clears both.

Lock order is unchanged: the poster's wake lock is the same acquisition master's `user_write` made, with nothing
else held.

### 2.2 Switch off = master

With the switch unset, `pfifo_dma_put_may_post()` returns false before touching anything, so `user_write` runs
master's timed lock; `pfifo_take_kick()` and `pfifo_park()` run master's statements; the pusher's DMA_PUT load is
master's plain load; `pfifo_take_posted()` is not called. The selftest's off leg checks it by behaviour (below).

## 3. Selftest (`selftest_postput.sh`)

Brought from `docs/lanes/vcpusleep/` and extended. It compiles user.c and pfifo.c's posted-put block VERBATIM
against a stub `nv2a_int.h` and runs each leg with the switch on and off. Result on c63ec9774f: **PASS** (2 min).

| leg | switch on | switch off |
|---|---|---|
| POSTED / LOCKED: a DMA_PUT store while another thread holds the lock 400 ms | posted in 0 ms, no locked kick | waited 400 ms, locked kick (as master) |
| FREE: the lock free | locked store | locked store |
| BOUND: skew bound on | locked store | locked store |
| WAKEUP: 100,000 stores against a PFIFO stand-in using the real `pfifo_take_kick`/`pfifo_park`, random unlocked spin, a third thread kicking under the lock | 60,186 posted, 39,814 locked, none lost | 0 posted, 100,000 locked, none lost |
| RACE: store-buffering litmus, the poster against `pfifo_park` round by round, 2 s | 3,212,761 rounds, 1,275,188 would have slept, 0 lost | 857,723 rounds, 0 lost |

Static checks: the pusher's acquire load; the loop top through `pfifo_take_kick()`; both `fifo_cond` waits inside
`pfifo_park()`; no plain kick store outside its off branch; one full barrier on each side; user.c's timed lock on
the non-posting path.

Falsifiers (each must go red, and does):

| mutant | what it does | result |
|---|---|---|
| F1 | the poster never wakes a parked thread (`if (0)`) | WAKEUP lost at store 31; RACE lost 851,118 rounds |
| F2 | user.c as on b74cff74ed (before the change) | POSTED FAIL: blocked 399 ms behind the holder |
| F3 | both `smp_mb()` dropped | RACE lost 282,354 of 2,846,221; WAKEUP lost at store 177 |
| F4 | only `pfifo_park()`'s barrier dropped | RACE lost 45,505 of 2,768,157 |
| F5 | only `pfifo_post_kick()`'s barrier dropped | RACE lost 697 of 2,719,773 |

The host is x86-64 (WSL2), where a missing barrier still loses rounds through the store buffer (F3-F5), so the
barrier legs are not vacuous here. ARMv8 is weaker still; the argument in 2.1 does not depend on the host.

A syntax check of pfifo.c and user.c against the desktop build's compile commands, plain, with `-D__ANDROID__`,
and with `NV2A_PERF_LOG=1`, gives the same warnings as the base (pre-existing redundant `__android_log_print`
declarations, an unused `t0`).

## 4. Runs

Registered first: `docs/testing/predictions/postput1010-nfs.json` (pace, A/B/B/A) and
`postput1010-ftpair.json` (frametrace pair). Judge: `ppread.py` (this directory), which reads with
reportasync1010's `raread.py` (pace) and `ftpair.py`/`ftbuckets.py` (frametrace) so the windows are theirs.

A = `HAKUX_REPORT_ASYNC=1 HAKUX_TEXSCAN=1`, B = A + `HAKUX_POSTED_PUT=1`. The baseline for A is
reportasync1010's both-switch runs, read with `ppread.py`: `1-1791659723-reportasync1010-552662` and
`1-1791659725-reportasync1010-552924`, cold start 1 47.4 / 50.3 ms, warm countdown 37.2 / 37.9 ms, post-GO warm
35.1 / 35.3 ms, warm v2/v3/v4 70/21/2 and 69/22/2 %.

(Results go here as they land.)

## 5. For the next lane

- `ppread.py` cannot see motion. V's moving-car check is by eye from `route-frames/*-s*-g11.png`, and goes here.
- Do not judge the frametrace pair on heavy frames only. B is meant to turn heavy frames into light ones, so its
  remaining heavy frames are a different selection from A's; `ppread.py` judges all warm frames and prints both.
