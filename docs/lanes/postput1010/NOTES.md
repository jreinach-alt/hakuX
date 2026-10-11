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

Queued 2026-10-10 17:5x PDT on the Nova, release tier, behind drawrec1010's probe arms (not reordered):

| request | arm |
|---|---|
| `1-1791680038-postput1010-1949730` | A1 (pilot) |
| `1-1791680039-postput1010-1954673` | B1 (pilot) |

Four runs of 590 s are past request.sh's 30 min pilot gate, so A1 and B1 go first. On their return: check both
built and ran c63ec9774f, 12 marks, the three log lines (`[postput] on` on B1 only), fifoskew's `posted=` > 0 on
B1, and the g11 frames for a moving car; write `pilots/postput1010.ok`; then queue B2, A2, then the frametrace
pair A, B.

### 4.1 Why attempt 1 stopped, and the pilot (attempt 2, 2026-10-10 ~18:25 PDT)

Attempt 1 did not fail. It ended on purpose, waiting on A1 and B1 (`WAITING` @ 9569a98bb7): the pilot gate does not
let the other runs be queued until the pilot has been reviewed, and nothing else in the brief could move until the
pilot was back. Both runs finished DONE at 18:11 and 18:20 PDT (device clock). Attempt 2 reviewed them, wrote
`pilots/postput1010.ok`, and queued the rest of the batch at 18:27 PDT, behind nothing. The Nova queue was empty,
and none of drawrec1010's probe arms were waiting.

| request | arm |
|---|---|
| `1-1791682037-postput1010-2642454` | B2, plain |
| `1-1791682038-postput1010-2643101` | A2, plain |
| `1-1791682044-postput1010-2647298` | frametrace A, perflog, `--pull 'frametrace_*'` |
| `1-1791682045-postput1010-2647896` | frametrace B, perflog, `--pull 'frametrace_*'` |

Pilot, read with `ppread.py`:

| run | arm | cold 1 | warm countdown | post-GO warm | warm v2/v3/v4 | valid |
|---|---|---|---|---|---|---|
| `1-1791680038-postput1010-1949730` | A1 | 41.4 | 33.90 | 33.50 | 78/10/1 % | 12/12 |
| `1-1791680039-postput1010-1954673` | B1 | 41.5 | 33.99 | 33.49 | 81/10/1 % | 12/12 |

The pilot passes as a method check: both runs ran c63ec9774f (apk 73f78762d3e1), `[reportasync] on` and
`[texscan] on` appear in both, and `[postput] on, skew bound mode 0` appears in B1 only. All 24 `s*-g11` frames,
looked at on one contact sheet per run, show the Punto moving at 60-88 MPH with about 11.5 s on the race clock,
and an opponent is on screen in most of them.

**B posts a lot of stores.** From fifoskew lines whose time falls in the go2..go12 windows: B1 posted 16.3 % of the
kicks in the countdown (317 a second, about 10 a frame) and 9.3 % after GO (175 a second). A1 posted 0. So the
mechanism runs, and the period does not move: B - A is +0.09 ms in the countdown and -0.01 ms after GO. That is
the brief's case "the period is unchanged because `p_run` alone sets it", or the case where the wait moved to
another sync point. The frametrace pair decides which.

**A's baseline is not the registered one.** The prediction's baseline for A is reportasync1010's both-switch runs on
3cd9d6b7e3, with a warm countdown of 37.2 and 37.9 ms. A1 on c63ec9774f is 33.9 ms, which is 3.5 ms faster, with
v3+v4 at 11 % against 23 %. Two emulator commits lie between those refs, and both are on this branch's base:

- `81ab5f3418`, gpupass1010's `kTitleRenderModes` row: NFS now runs in sysmem render mode (folded via 071aea27ff).
  gpupass1010 measured the period as flat with it, but on a base without `HAKUX_REPORT_ASYNC`, where the GPU was
  not on the path.
- `477893cdbf`, reportasync1010 deferring only armed reports.

No existing plain run with these switches separates the two. reportasync1010's frametrace pair (a21a3361d9), which
the brief's 7.3 ms comes from, has `477893cdbf` but not the sysmem row. So the 6.3 ms `lockw` it measured may not
hold on this base. Frametrace A will show whether it does.

What that does to the prediction: at A = 33.9 ms, 78 % of warm frames are already 2-VBLANK frames and about 11 %
are 1-VBLANK frames. Turning every v3 and v4 frame into a v2 frame would take off about 0.10 x 16.7 + 0.01 x 33.3,
roughly 2.0 ms. P (B - A <= -2.0) can only pass if every heavy frame goes, and T (B <= 34.0) passes for A as well,
so T says nothing about B. The registered checks stand as written. They are not loosened, and they are read with
this caveat.

## 5. For the next lane

- `ppread.py` cannot see motion. V's moving-car check is by eye from `route-frames/*-s*-g11.png`, and goes here.
- Do not judge the frametrace pair on heavy frames only. B is meant to turn heavy frames into light ones, so its
  remaining heavy frames are a different selection from A's; `ppread.py` judges all warm frames and prints both.
