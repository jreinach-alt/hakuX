# lane.postput1010 (#433): the posted DMA_PUT store at NFS Most Wanted's race start

Step 2b of `docs/lanes/nfs30plan1010/PLAN.md`. Branch `lane/postput1010`, from master @ b74cff74ed with
`origin/lane/reportasync1010` @ 4b50801b21 merged in (0d7948085e), because `HAKUX_REPORT_ASYNC` is only there.
reportasync1010 folded as 6052ff98d4, and origin/master was merged in at b9b36d655c (no conflict). Since then the
diff against master is this lane's files only.

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

### 4.2 Why attempt 2 stopped (attempt 3, 2026-10-10 ~19:05 PDT)

Attempt 2 did not fail either. It ended on purpose, waiting on B2, A2 and the frametrace pair (`WAITING` @
ccfda33cbe): four device runs of about 9 minutes each, which a session cannot wait out. All four finished DONE at
18:36, 18:44, 18:55 and 19:03 PDT, on ref c63ec9774f. Attempt 3 read them (4.3, 4.4), merged origin/master once
reportasync1010 had folded, and set up Addendum 1's full-switch pair (4.6).

### 4.3 The pace A/B: P, T and G fail

`ppread.py <A1> <B2> <B1> <A2> --expect docs/testing/predictions/postput1010-nfs.json`:

| run | arm | cold 1 | warm countdown | post-GO warm | warm v2/v3/v4 | valid | posted, countdown / post-GO |
|---|---|---|---|---|---|---|---|
| `1-1791680038-postput1010-1949730` | A1 | 41.4 | 33.90 | 33.50 | 78/10/1 % | 12/12 | 0 |
| `1-1791682037-postput1010-2642454` | B2 | 41.1 | 34.0 | 33.5 | 78/11/1 % | 12/12 | 12.2 % / 8.6 % of kicks |
| `1-1791680039-postput1010-1954673` | B1 | 41.5 | 33.99 | 33.49 | 81/10/1 % | 12/12 | 16.4 % / 9.3 % |
| `1-1791682038-postput1010-2643101` | A2 | 40.1 | 34.0 | 33.5 | 77/12/1 % | 12/12 | 0 |
| **A** (mean of runs) | | 40.77 | 33.96 | 33.49 | 77.7 % v2 | | |
| **B** (mean of runs) | | 41.28 | 34.01 | 33.51 | 79.6 % v2 | | |

| check | verdict | figure |
|---|---|---|
| V | PASS | 12 marks and 12 valid starts on every run; env, perflog off and the switch lines as registered. Moving car: all 48 `s*-g11` frames of the four runs, one contact sheet per run, show the Punto at 58-88 MPH with 11.4-13.9 s on the race clock |
| P | **FAIL** | warm countdown B - A = **+0.06 ms** (needed <= -2.0) |
| T | FAIL | B 34.01 ms (needed <= 34.0) |
| G | **FAIL** | post-GO warm B - A = **+0.02 ms** (needed <= -1.5) |
| C | PASS | cold start 1 B - A = +0.52 ms (allowed up to +3.0) |

phaseread.py, the brief's pace reader, agrees. Its pooled countdown windows, cold start included, are A1 34.3,
B2 34.4, B1 34.3, A2 34.6 ms/frame, so B - A is -0.1 ms. The store is posted on every B run (`[postput] on` logged,
and fifoskew's `posted=` share above), and the period does not move. P fails, so the pixel leg (brief step 5) is
not run.

### 4.4 The frametrace pair

`ppread.py <A> <B> --expect docs/testing/predictions/postput1010-ftpair.json`. A is
`1-1791682044-postput1010-2647298`, B is `1-1791682045-postput1010-2647896`, both perflog with `HAKUX_FRAMETRACE=1`
on c63ec9774f. The left column is the trace the brief's 7.3 ms comes from, reportasync1010's both-switch run
`1-1791671434-reportasync1010-3857196` (ref a21a3361d9), read with `ppread.py --ft` over the same windows.
Per frame, in ms:

| warm countdown, all frames | reportasync1010 B (a21a3361d9) | **A** (c63ec9774f) | **B** (+ posted) | B - A |
|---|---|---|---|---|
| period P | 44.81 | 39.77 | 39.49 | -0.29 |
| PFIFO `p_run` | 27.08 | 27.03 | 27.00 | -0.03 |
| PFIFO `pidle` (waiting for the guest) | 13.56 | 10.72 | 10.60 | -0.12 |
| PFIFO other-fence wait `o_fence` | 25.73 | 15.10 | 15.22 | +0.12 |
| GPU busy | 18.85 | 12.81 | 12.81 | 0.00 |
| guest `lockw` (pfifo.lock, DMA_PUT) | **6.27** | **1.85** | **1.09** | -0.76 |
| guest idle `gidle` | 11.9 | 13.1 | 13.9 | +0.8 |
| guest busy past 2 VBLANKs | 46 % | 9 % | 6 % | |
| PFIFO busy past 2 VBLANKs | 26 % | 8 % | 8 % | |
| either thread past 2 VBLANKs | 58 % | 14 % | 12 % | |
| v2/v3/v4+ | 41/55/3 % | 63/35/1 % | 63/35/1 % | |
| frames | 859 | 967 | 977 | |

| other windows | A | B | B - A |
|---|---|---|---|
| warm heavy (vb >= 3): P / `lockw` / `pidle` / `p_run` | 43.53 / 2.41 / 12.86 / 28.12 | 42.53 / 1.55 / 12.24 / 27.86 | -1.01 / -0.86 / -0.62 / -0.27 |
| warm heavy: v2/v3/v4+, frames | 0/96/4 %, 349 | 0/98/2 %, 352 | |
| cold (start 1): P / `lockw` / `gidle` / `p_run` | 50.10 / 5.36 / 14.0 / 33.03 | 50.38 / 2.29 / 17.0 / 33.40 | +0.28 / -3.07 / +3.0 / +0.37 |
| cold: PFIFO busy past 2 VBLANKs, v2/v3/v4+ | 74 %, 13/74/13 % | 80 %, 9/80/12 % | |
| post-GO: P / `lockw` / `p_run` / GPU | 35.58 / 1.07 / 22.83 / 10.58 | 35.11 / 0.65 / 22.21 / 10.17 | -0.48 / -0.42 / -0.62 / -0.41 |
| post-GO: v2/v3/v4+ | 75/19/0 % | 74/18/0 % | |
| posted share of kicks, countdown / post-GO | 0 | 32.1 % / 26.2 % | |

The judged legs: **L FAIL** (warm `lockw` A 1.85, registered >= 3.0; B 1.09, registered <= 0.5) and **Q FAIL** (the
guest busy past 2 VBLANKs, A 9 %, registered >= 30; B 6 %). Both fail on A's side: the wait they were written for
is not there on this base. V passes, including a moving car in all 24 g11 frames (52-89 MPH).

The heavy-frame row (-1.0 ms) is not a gain. B's remaining heavy frames are a different selection from A's, and
over all warm frames the period moves -0.29 ms with an unchanged v2/v3/v4 split (section 5). The plain A/B (4.3) is
the pace measurement.

### 4.5 Where the 7.3 ms went

1. **Most of it was gone before the posted store.** The only emulator difference between reportasync1010's trace
   ref (a21a3361d9) and this lane's base without the posted store (0d7948085e) is one row,
   `{0x4541007B, "sysmem"}` in `kTitleRenderModes` (`81ab5f3418`, gpupass1010). `git diff --stat` on hw/ target/
   accel/ android/ tcg/ ui/ audio/ shows that one line. Across the two traces, both with REPORT_ASYNC + TEXSCAN:
   GPU busy fell 18.85 -> 12.81 ms, the PFIFO thread's other-fence wait fell 25.73 -> 15.10, and the guest's lock
   wait fell 6.27 -> 1.85 ms per warm frame (7.31 -> 2.41 heavy). The period fell 44.81 -> 39.77 under frametrace,
   and plain pace fell 37.5 -> 34.0 (4.1). `p_run` did not move (27.08 -> 27.03). So the guest was waiting for the
   lock while the PFIFO thread held it across GPU fence waits. With sysmem render mode those waits are shorter,
   and so is the guest's. This compares two separate sessions, not an A/B. One code line is the only difference
   between them, and both readers show the same direction and size.
   gpupass1010 measured the period as flat with that row, but on a base where the report wait was still on the
   PFIFO thread. With REPORT_ASYNC on, the GPU is on the path, and the row is worth ~3.5 ms of plain pace.
2. **The posted store takes 41 % of what was left.** Warm `lockw` went 1.85 -> 1.09, and cold 5.36 -> 2.29.
3. **The guest spends what it saves idle.** `gidle` rose +0.8 ms warm and +3.0 ms cold, about what `lockw` lost.
   `p_run` is unchanged (27.03 / 27.00 warm, 33.03 / 33.40 cold), and so is the period.
4. **What sets the period.** Cold, it is the PFIFO thread alone. Its busy time (36.5 / 37.2 ms) is past 2 VBLANKs
   on 74 / 80 % of frames, in both arms. Warm, at 34.0 ms on the plain build, the countdown is 0.5 ms over the
   33.5 ms v2 floor that drawrec1010 measured. Under frametrace, a thread is past 2 VBLANKs on only 12-14 % of
   frames, so the guest's lock wait was no longer on the path.

What is left of B's `lockw` (1.09 ms warm) cannot be split with the instruments in this build. Two things count
into it: the poster's wake lock, taken when it reads `parked` while another holder (the waking PFIFO thread
itself, or a report or render path) has the lock, and stores to user registers other than DMA_PUT. A separate
counter for `pfifo_post_kick()`'s wait would split them. It is not worth adding, because the guest is idle, not
waiting, once it is freed.

For PLAN.md section 6, the recorder thread: the cold period is `p_run` (33 ms of PFIFO CPU in a 50 ms frame), so
any cold-start lever has to shorten the PFIFO thread's own work. The warm countdown is within 0.5 ms of the
vblank floor on this base, and a recorder thread has little to take there. drawrec1010's probes reached the same
conclusion ("floor is vblank").

### 4.6 Addendum 1: the full-switch pair (waiting on drawrec1010's fold)

The pair is A2' = REPORT_ASYNC + TEXSCAN + DRAWREC + UNI_BULK + UNI_UBERCACHE + UNI_FOGCACHE and B2' = A2' +
POSTED_PUT. The primes keep them apart from the A2/B2 runs above. `HAKUX_DRAWREC` is only on
`origin/lane/drawrec1010` (ready, dba22feab0), and the brief says to merge origin/master once that has folded,
never the lane branch. The UNI_* switches are already on master (`shaders.c` `perdraw_flags_init`). At 19:14
PDT `git log origin/master` ends at 6052ff98d4, so drawrec1010 has not folded. `WAITING` says
`fold drawrec1010`, and lanewaker resumes this lane when origin/lane/drawrec1010 is an ancestor of origin/master.

Ready for the resume:
- `ppread.py` now judges any leg the prediction names, in its `expect` order. The keys are `<leg>_d_max`
  (B - A <= limit), `<leg>_b_max` (B <= limit) and `<leg>_dv2_min` (warm v2 share, B - A >= limit, mean of runs).
  The leg letter picks the window: P/T/F warm countdown, G post-GO, C cold start 1, H v2 share. The digit after
  it names the leg, as in P2. With an a_env that holds them, it requires `[drawrec1010] drawrec=1 vtx=1 shc=1` and
  `[perdraw433] bulk=1 ubercache=1 fogcache=1` on every run. Re-run on 4.3 and 4.4, it gives the same verdicts,
  and a mock of the nfsall keys over the 4.3 runs gives P2/F2/C2/H2 FAIL (+0.06, 34.01, +0.52, +2.0 points).
- On the resume: merge origin/master, then register `docs/testing/predictions/postput1010-nfsall.json` on the
  merge commit, with `expect` V as before, `P2_d_max` -0.5, `F2_b_max` 33.8, `C2_d_max` -2.0, `H2_dv2_min` 10.0.
  Commit and push it, then queue A2', B2', B2', A2' (`--seconds 500`, plain, 12 starts). The pilot file
  (`pilots/postput1010.ok`, 18:27 PDT) covers the batch until 18:27 tomorrow. The lane has used about 60 min of
  its 3 h: six runs at request.sh's estimate of 500 s + 90 s each. The pair adds four more, about 40 min.

Prior, stated before the runs: low. At this base the guest is idle, not waiting, once its lock wait goes. DRAWREC
cuts the PFIFO thread's work (-1.5 ms/frame warm, per drawrec1010), and that also shortens the time the PFIFO
thread holds the lock, so it leaves less for the posted store to remove. P2 ~10 %, C2 ~10 %. The size of the win
is small either way: the warm countdown is near the floor, and cold start 1 is one start in twelve. It is run
because the brief needs P2/F2/C2 for the recommendation.

### 4.7 Why attempt 3 stopped (attempt 4, 2026-10-10 ~19:20 PDT)

Attempt 3 did not fail. It ended on purpose, waiting on drawrec1010's fold (`WAITING` @ 5469b1175a said
`fold drawrec1010`), because Addendum 1 said to merge origin/master once drawrec1010 had folded and never the lane
branch. Addendum 2 (19:17 PDT) reversed that: lane.local merged master into lane/drawrec1010 (f3d0e45979) and
asked this lane to merge `origin/lane/drawrec1010` now. drawrec1010 had still not folded at attempt 4's start
(`git log origin/master` ends at 6052ff98d4).

Attempt 4 merged `origin/lane/drawrec1010` @ f3d0e45979 at 772429156c. No conflict; drawrec1010 touches only
`pgraph/vk/draw.c` among the emulator files. `nv2a_index.py check --tests ~/nxdk_pgraph_tests --support
~/pbkitplusplus` passes (line drift only, 12 symbols), so the index is not regenerated and stays off `Files:`.
Then it registered `docs/testing/predictions/postput1010-nfsall.json` on ref 772429156c and queued A2', B2', B2',
A2' (4.8).

### 4.8 The full-switch pair, queued

`postput1010-nfsall.json` (sha256 5b11550a770622fbe27bbc6fafae1ea6791d88891d749baa7858185ca57b5df7, committed in
8765e42a54) on ref 772429156c: A2' = REPORT_ASYNC + TEXSCAN + DRAWREC + UNI_BULK + UNI_UBERCACHE + UNI_FOGCACHE,
B2' = A2' + POSTED_PUT, plain, 500 s, 12 starts, legs V, P2 (B - A <= -0.5), F2 (B <= 33.8), C2 (cold B - A <=
-2.0), H2 (v2 +10 points), none loosened. The prediction's point estimate is B - A = 0.0 warm and 0 +- 1.5 cold,
with P2 ~7 %, F2 ~40 % (mostly A2' already being there), C2 ~12 %, H2 ~5 %.

Queued 2026-10-10 ~19:20 PDT on the Nova, release tier (`HAKUX_RELEASE_PRIO=1`), all four at once under the
pilot file (18:27 PDT). The Nova queue was empty.

| request | arm |
|---|---|
| `1-1791685180-postput1010-3732954` | A2'a |
| `1-1791685199-postput1010-3733954` | B2'a |
| `1-1791685200-postput1010-3736342` | B2'b |
| `1-1791685202-postput1010-3737568` | A2'b |

Nova time: the six earlier runs at request.sh's estimate (500 + 90 s) are about 59 min; these four add about 39,
so about 98 min of the 3 h. On their return: check `[drawrec1010] drawrec=1 vtx=1 shc=1` and `[perdraw433] bulk=1
ubercache=1 fogcache=1` on all four, `[postput] on` on B2' only (ppread.py's V does that), and the g11 frames for
a moving car by eye; then judge with `ppread.py 3732954 3733954 3736342 3737568 --expect
postput1010-nfsall.json` (full ids), and merge origin/master once drawrec1010 has folded.

### 4.9 Why attempt 4 stopped, and the full-switch read (attempt 5, 2026-10-10 ~20:00 PDT)

Attempt 4 did not fail. It ended on purpose, waiting on the four full-switch runs (`WAITING` @ 3fd1d9d96b). All
four finished DONE by 19:57 PDT. (The resume's brief calls this attempt 1; it is the fifth session on this lane.)
drawrec1010 had still not folded at 20:00 PDT: `git log origin/master` ends at 7a44ee4d97 (usagerule1010).

`ppread.py 3732954 3733954 3736342 3737568 --expect postput1010-nfsall.json` (full ids in 4.8):

| run | arm | cold 1 | warm countdown | post-GO warm | warm v2/v3/v4 | valid |
|---|---|---|---|---|---|---|
| `1-1791685180-postput1010-3732954` | A2'a | 38.1 | 33.7 | 33.4 | 77/11/1 % | 12/12 |
| `1-1791685199-postput1010-3733954` | B2'a | 35.8 | 33.6 | 33.4 | 73/12/1 % | 12/12 |
| `1-1791685200-postput1010-3736342` | B2'b | 34.9 | 33.6 | 33.4 | 75/11/1 % | 12/12 |
| `1-1791685202-postput1010-3737568` | A2'b | - | 27.1 | 28.2 | 56/2/0 % | 10/12, **void** |

**A2'b is void.** Its g11 frames, one contact sheet per run, show the name-entry keyboard, the save prompt, the
autosave notice, career cutscenes and a BMW parked against a wall at 1:38-1:41 on a race clock. They do not show
the Punto at the quick-race start. 27.1 ms/frame is below the 33.3 ms two-VBLANK floor because menus and cutscenes
run at 60 fps. The cause, from run.log: at the boot's first save prompt (step s04), `pad.sh axis HATY max` hung
20 s and returned rc 124. The adb transport was stalling then: `COOLDOWN: ... daemon still not running` at the
start, a WSL `UtilAcceptVsock: accept4 failed 110` and an adb liveness probe failure later in the run. The d-pad
down that picks No on that prompt was lost, so the A that followed answered the prompt the other way, and every
blind step after it landed on a different screen. hdd.json is the same for A2'a and A2'b: both first-run, built
from the same goldens. So the disk is not the cause.

The gap: `route.sh` (`pad()`, docs/testing/titles/route.sh:220) logs a failed pad step and carries on, and
nothing reads that line except `raread.bad_starts`. bad_starts dropped only start 1 ("gameplay") and kept the
other ten starts, so ppread's V passed the run by count. Only the by-eye frame check caught it. Two guards:

- **This lane's reader (done):** `ppread.py`'s V now fails a run when any input before `mark gameplay` failed or
  hung, because every start rests on that menu path. It fails A2'b and passes all eight other plain runs (4.3 and
  the three above), and their verdicts are unchanged.
- **The harness (not this lane's territory, named for lane.local):** `route.sh` should stop the route, and the run
  should end VOID at once, when a pad step fails before the route's first `mark`. Blind steps after a lost input
  measure an unknown screen. It would also have saved about 8 minutes of Nova time.

The three valid runs show the Punto moving at 48-88 MPH in all 36 g11 frames, with 11.4-13.7 s on the race clock
and opponents on screen.

Judged on the three valid runs (A = A2'a alone), before the replacement:

| check | verdict | figure |
|---|---|---|
| P2 | FAIL | warm countdown B - A = -0.1 ms (needed <= -0.5) |
| F2 | PASS | B 33.6 ms (needed <= 33.8), but A2'a is 33.7, so F2 says nothing about the store |
| C2 | PASS on one A run | cold start 1 B - A = -2.75 ms (35.35 - 38.1; needed <= -2.0) |
| H2 | FAIL | warm v2 share B - A = -3 points (74 - 77; needed >= +10) |

C2 rests on a single cold start in a single A run, and cold start 1 moved 1.3 ms between the two A runs of 4.3
(41.4, 40.1). C2 is also the one leg that could change the recommendation. So one replacement A2' run was queued
at 20:03 PDT, with the same env, ref, route and expect file: `1-1791687762-postput1010-417368` (A2'c). It runs
after both B runs, so the order is A, B, B, (void), A. The judge passes the four valid runs.

### 4.10 The full-switch pair: P2 and H2 fail, C2 passes by 0.17 ms

A2'c finished DONE at 20:11 PDT on 772429156c. No input failed, 12 of 12 starts are valid, and all 12 g11 frames
show the Punto moving at 45-88 MPH with 11.3-12.5 s on the race clock. `ppread.py 1-1791685180-postput1010-3732954
1-1791685199-postput1010-3733954 1-1791685200-postput1010-3736342 1-1791687762-postput1010-417368 --expect
docs/testing/predictions/postput1010-nfsall.json`:

| run | arm | cold 1 | warm countdown | post-GO warm | warm v2/v3/v4 | valid |
|---|---|---|---|---|---|---|
| `1-1791685180-postput1010-3732954` | A2'a | 38.1 | 33.7 | 33.4 | 77/11/1 % | 12/12 |
| `1-1791685199-postput1010-3733954` | B2'a | 35.8 | 33.6 | 33.4 | 73/12/1 % | 12/12 |
| `1-1791685200-postput1010-3736342` | B2'b | 34.9 | 33.6 | 33.4 | 75/11/1 % | 12/12 |
| `1-1791687762-postput1010-417368` | A2'c | 36.9 | 33.8 | 33.4 | 78/10/1 % | 12/12 |
| **A2'** (mean of runs) | | 37.49 | 33.76 | 33.4 | 77.4 % v2 | |
| **B2'** (mean of runs) | | 35.32 | 33.59 | 33.4 | 73.9 % v2 | |

| check | verdict | figure |
|---|---|---|
| V | PASS | four valid runs: every switch line on all four, `[postput] on` on B2' only, no failed boot input, a moving car in all 48 g11 frames. A2'b is void (4.9) |
| P2 | **FAIL** | warm countdown B - A = **-0.18 ms** (needed <= -0.5) |
| F2 | PASS, uninformative | B 33.59 ms (needed <= 33.8). A2' is 33.76, under the bar as well, so F2 says nothing about the store |
| C2 | **PASS, narrowly** | cold start 1 B - A = **-2.17 ms** (needed <= -2.0) |
| H2 | **FAIL** | warm v2 share B - A = **-3.5 points** (needed >= +10) |

Reading it:

- **Warm, the store does nothing that counts.** -0.18 ms/frame is inside the spread of A2' alone (33.7, 33.8). Both
  arms sit 0.1-0.3 ms over the 33.5 ms floor that drawrec1010 measured, so a CPU lever has little left to move there.
  B's v2 share is lower, not higher. Its frames outside v2-v4 rose from 11 % to 13-14 %. That is a shift in
  frame pacing, not in pace.
- **Cold start 1 is where it shows.** Both B2' cold starts (35.8, 34.9) are below both A2' cold starts (38.1,
  36.9). No earlier pair in this lane showed it: on the REPORT_ASYNC + TEXSCAN base, cold B - A was +0.52 (4.3). This is the
  prediction's case "C2 passes and P2 fails". With DRAWREC on, the PFIFO thread's per-draw work is shorter, so in
  the cold frames the guest's DMA_PUT store is late more often, and posting it helps. The 4.4 trace saw the
  mechanism without the gain: cold `lockw` fell 5.36 -> 2.29 ms on the older base, and the period stayed flat
  because `p_run` set it.
- **How much C2 rests on.** There is one cold start per run and two runs per arm. The margin over the bar is 0.17
  ms. The chance that both B values rank below both A values when the store does nothing is 1 in 6. The prior,
  stated before the runs, was ~12 %. It is the first evidence for the cold effect, and it is not a measured size.
  A cold-only design would settle it: N boots, start 1 each, B against A. Each boot is about 3 min of menus.
- **What a player would see.** Cold start 1 is the first 3.5 s countdown after a race loads, about 2 ms a frame
  faster, which is still above the floor (~1.8 ms over at 35.3). Nothing changes in the race itself.

Prediction verdicts, all on this lane's runs:

| prediction | base | verdict |
|---|---|---|
| `postput1010-nfs.json` | REPORT_ASYNC + TEXSCAN | FAIL: P +0.06, T 34.01, G +0.02; C passes (+0.52 <= +3.0) |
| `postput1010-ftpair.json` | same, frametrace | FAIL: L and Q fail on A's side, so the wait was not on this base (4.4, 4.5) |
| `postput1010-nfsall.json` | all six switches | FAIL: P2 -0.18, H2 -3.5 points; F2 passes but says nothing; C2 passes (-2.17) |

**Recommendation: keep opt-in.** The only check the store passes is C2, a cold-start leg that passes by 0.17 ms on
two starts per arm. That is not "drop" (the nfsall prediction's rule: drop only if P, P2 and C2 all fail), and it is
not grounds for default-on. Default-on needs two checks, neither of which this lane runs:

1. **A GPU-paced title:** The Simpsons Hit & Run in free roam, a plain fps A/B with the store. That title lost
   40.05 -> 36.22 fps with `c2dfca18a1`.
2. **The cold start, measured as a cold start:** NFS race start, several boots per arm, start 1 only, on the
   full-switch base.

The pixel leg (brief step 5) is not run: it was gated on P, and P failed. Nova time: eleven runs at request.sh's
estimate of 590 s each, about 108 min of the 3 h.

The selftest re-run on 713cd67a8a (drawrec1010 merged in) passes: switch on and off, the static checks, and all five
mutants red.

### 4.11 Waiting on drawrec1010's fold (attempt 5 stops, 2026-10-10 20:43 PDT)

Everything the brief asks of this lane is done: every run is read, the verdicts and the recommendation are in 4.10
and PR.md, the selftest and preflight pass on 7cac3e5b90. One step is left. Addendum 2 says to merge origin/master
once drawrec1010 has folded, and only then to mark ready, because until then this branch's diff carries
drawrec1010's commits. Its fold has not failed. At 20:10 the foldqueue found no device run built from its head
f3d0e45979 and queued a gate boot check (`1791688241-foldqueue-506278`) and a restore run
(`1791688242-foldqueue-506327`). Both have run. The next tick started at 20:25 and had not folded it by 20:42.
`WAITING` says `fold drawrec1010`.

On the resume: `git fetch && git merge origin/master` (it should be clean, since drawrec's commits are already
here), check that `git diff --stat origin/master...HEAD` shows only this lane's files, run preflight, set
`State: ready` in PR.md, push, and remove `WAITING`. No device time is needed.

## 5. For the next lane

- `ppread.py` cannot see motion. V's moving-car check is by eye from `route-frames/*-s*-g11.png`, and goes here.
- Do not judge the frametrace pair on heavy frames only. B is meant to turn heavy frames into light ones, so its
  remaining heavy frames are a different selection from A's; `ppread.py` judges all warm frames and prints both.
  Here, heavy frames show B - A = -1.0 ms while all warm frames show -0.29 with an identical v2/v3/v4 split.
- A frametrace mechanism figure goes stale when the base moves under it. This lane's 7.3 ms came from a trace one
  render-mode row behind its base, and that row had already removed 4.4 ms of the 6.3. Re-trace A on the lane's
  own base before registering checks on a mechanism figure (L and Q here failed on A's side).
- Do not re-run the posted store at NFS's race start on the REPORT_ASYNC + TEXSCAN base. It is posted on 12-32 %
  of kicks and the period does not move. On the full-switch base it also leaves the warm countdown alone
  (-0.18 ms). Only cold start 1 is open (-2.17 ms on two starts per arm), and a cold-only design is the way to
  test it, not another 12-start soak.
- Look at every run's g11 frames, even when the reader passes V. A pad.sh hang in a blind route's boot sends the
  menus somewhere else, and the count checks still pass. `ppread.py` now fails that case. `route.sh` does not, and
  should end such a run VOID at its first failed boot input (4.9).
