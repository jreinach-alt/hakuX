# lane.gta482 -- GTA: San Andreas open world at ~4.5 fps: what the guest runs and why it blocks (#482)

Base: master @ c91697f116. Thor (bdc158a5) only; GTA (54540082) lives there.
Prior work: docs/lanes/slowdown462/NOTES.md, "Attempt 5" and "Attempt 6"
(open world 208.7-229.6 ms/flip; vCPU 70% on-CPU; guest JIT 77.6 ms/frame;
blocked 61.9 ms/frame, cause unmeasured).

## Files

| file | what |
|---|---|
| `capture_gta.sh` | one held Thor session: on-CPU record, `--trace-offcpu` record, then a dump of the TCG code buffer and guest RAM through `/proc/<pid>/mem` under `run-as` (no code change, no `-perfmap`). It refuses to start when the display is not on, stops when the route's `gameplay` frame is black, and stops the soak and its route when hakuX loses focus |
| `tbmap.py` | maps a thread's JIT samples to guest pcs. Each TranslationBlock header sits in the code buffer just before its code, and `tc.ptr` points 192 B past the header. Self-checks: the delta mode, tier-1 promote pcs as known answers, and the mapped share |
| `codewrites.py` | #424 code-page store churn over a window of any soak logcat (`hakuX-pages` lines), per second and per frame, with the pages written |
| `winfps.py` | flips and fps between two route markers (profwin.py's arithmetic, any marker pair) |

How a guest pc is recovered without instrumenting the build: `tcg_tb_alloc`
puts the header at the aligned `code_gen_ptr` and the code right after it
(tcg/tcg.c). `tb->pc` is stored even under CF_PCREL (translate-all.c:637).
The layout (aarch64, XBOX) puts pc at +0, cflags at +20, the guest size at
+24, tc.ptr at +40, tc.size at +48, page_addr[0] at +72 and exec_count at
+160, with the header 184 B, rounded up to 192. `translation-block.h` is
unchanged from a593d8eb85 to c91697f116. On Android the TCG buffer is the
unnamed executable mapping of 128 MiB (session 1: `74cbf08000-74d3f07000`).
The two `/memfd:jit*-cache` mappings are ART's.

## Established offline (from slowdown462's open-world data, a593d8eb85)

### Code-page writes (#424): 83.5 false invalidations per frame in the open world

`codewrites.py` over `0-0-x-1790522043-slowdown462-3573620` (e5db66fa37,
Thor, frames every 10 s). The windows are placed by slowdown462's frames: the
alley is `mark gameplay` +2..+38 s and the open world +50..+275 s.

| per frame (per s) | alley, 23.5 fps | open world, 3.9 fps |
|---|---|---|
| stores that reached the invalidator | 20.8 (490) | 83.5 (324) |
| blocks discarded | 28.4 (668) | 83.6 (325) |
| of them, blocks whose bytes the guest wrote (`ov`) | 0.0 (0.9) | 0.0 (0.0) |
| of them, spared by a range test (`sp`) | 99.87% | 100.00% |
| page emptied, so re-armed (`em`, `pr`) | 20.8 | 83.5 |
| tb_gen_code calls / real generations / recycled | 33.1 / 12.3 / 20.8 | 110.3 / 26.8 / 83.6 |
| stores to pfn 0x4808 (va `0x758488..0x758500`) | 11.1 (262) | 62.6 (243) |
| stores to pfn 0x441c (va `0x36d890..0x36d894`) | 3.5 (84) | 15.9 (62) |

Reading. The guest stores to a few data words that share 4 KB pages with
code. The hottest is `0x758488-0x758500` in the title's image. Every store
after a re-arm throws away the page's one block, empties the page, and
recycles the block (`ih`) and re-arms the page on its next run. No discarded
block was ever written, so the range test (`HAKUX_TCG424_RANGE=1`) would spare
all of them. Per SECOND the churn is flat (324-490/s) or lower in the open
world. Per FRAME it is 4x the alley's, like every other vCPU cost:
slowdown462 measured the open world at ~4.2x the alley per frame. So the
churn follows the guest's work rate. It does not cause the slow frame.

Price, from `gta-open.data` (tid 20343, 21,096 samples = 146.8 ms/frame
on-CPU; inclusive `--children`): `tb_gen_code` 5.31%, of which the re-arm
walk `tlb_protect_code` -> `tlb_reset_dirty` is 3.74% and real codegen
(`tcg_gen_code`) 0.46%, plus `notdirty_write` 0.97%. That is 6.28% = **9.2
ms/frame (4.4% of the 208.7 ms frame)**. It is a bound on what the range test
recovers on GTA: 208.7 -> >= 199.5 ms, <= 5.0 fps. Owner: #424.

### The rest of the on-CPU vCPU time (same profile, inclusive, ms/frame)

| cost | share of vCPU samples | ms/frame |
|---|---|---|
| guest JIT code, self | 52.9% | 77.6 |
| `helper_lookup_tb_ptr` (indirect-jump lookup; the jump cache was OFF in a593d8eb85, `[jc425] jc=0`) | 21.3% | 31.2 |
| `cpu_exec_loop` minus `tb_gen_code` | 4.2% | 6.2 |
| `tb_gen_code` + `notdirty_write` (#424 above) | 6.3% | 9.2 |
| `x86_cpu_tlb_fill` (softmmu TLB refills) | 3.9% | 5.7 |
| `do_st_mmio_leN` (MMIO stores; `voice_lock` 2.1% self, APU) | 3.6% | 5.3 |
| `cpu_io_recompile` | 0.9% | 1.3 |

## Device sessions

### Session 1 (held, 18:37-18:43Z): void, the display was covered

`capture_gta.sh 60`, a593d8eb85, output `perf/2026-09-27-gta482/s1/`.
Battery 87%, perf_harden 0 / paranoid 1. The on-CPU record (40,876 samples)
and the `--trace-offcpu` record (429,393 samples) both ran. REST was restored,
the caches were cleared and the hold released after 361 s of device time.

**The window is not gameplay.** Every route frame and screencap is a
10,899 B all-black PNG, and GTA flipped only in 59 fps bursts: no `gfps`
line for 105 s, then none in either record. Root cause (hostops, #494): at
11:06 PDT Lime3DS started on the Thor, and the AYN dual-screen assistant's
full-screen window covered hakuX on display 0. Hostops placed
`hold/thor` (hostops-display) at 11:51. The code-buffer dump took ART's
`jit-zygote-cache` only: adb read the loop's stdin and ate the other regions.
Both are fixed in the script.

One thing survives: `--trace-offcpu` and `offcpu.py` work on the Thor. There
were 70,596 switch records on the vCPU (tid 14972), with off-CPU 712 ms of
25 s, 92% of it on `qemu_mutex_lock_impl` from `cpu_exec_loop`. That is a
stalled game, not the open world. Do not read it as GTA's blocked time.

### Soak `0-0-x-1790533127-gta482-3508140` (c91697f116, 18:45-18:54Z): void, same cause

Queued so that `[rr425]`/`[rr425w]` could split the guest's idle loop from its
work in the open world. It ran under the same overlay: 9 of 9 route frames and
23 of 23 frames are black, and it flipped for only 45 s of the 284 s after
`mark gameplay`. Nothing of the open world can be read from it.

### Session 2 (held, 19:10:08-19:10:51Z): stopped by the foreground guard, nothing recorded

Taken when hostops-display lifted. Display 0 was Awake and clear: the
screencap was 106,019 B, Daijisho. The Thor had rebooted (uptime 427 s), and
`perf_harden` 1 / paranoid 3 were back. 21 s and 26 s after launch the focused
window was `com.android.launcher3/...secondarydisplay.SecondaryDisplayLauncher`
(display 1), not hakuX, so the guard stopped the soak before the route's first
input (+63 s). Route input is gamepad events, and they go to the focused
window. REST was restored, the caches were cleared and the hold released
after 38 s of device time. The case and the ask for one replacement session
are in hostops-inbox (12:14 PDT).

## State at the end of this session (2026-09-27 12:25 PDT): waiting

- Posted: the per-cost table on #482 (comment 5859028974). Rows 1 (guest
  JIT, 77.6 ms) and 2 (blocked, 61.9 ms) are pending. The #424 churn finding
  and its bound are on #424 (5858850203). Row 3 (lookup) is #425's, which
  slowdown462 already routed.
- Waiting on hostops for ONE replacement held Thor session
  (hostops-inbox 12:14 PDT). With it, ideally, `PERF_HARDEN0=1`.
- The next attempt: `env OUT=~/hakux-work/perf/2026-09-27-gta482/s3
  PERF_HARDEN0=1 bash docs/lanes/gta482/capture_gta.sh 60` (take hold/thor
  first with `jobs/hold.sh take`, between runs). Then run
  `winfps.py <dir>` and `winfps.py <dir> 'prof on end' 'prof off end'`,
  which should read ~4-5 fps. Then `tbmap.py <dir>` (rows 1's guest pcs),
  `offcpu.py <dir>/rec-off.data <vCPU tid>` (row 2) and `codewrites.py
  <dir>/logcat.txt 50 200`. Post the filled table on #482 and #462.
- Nothing of this lane's is queued, running or held.

## Attempt 2 (resumed 2026-09-27, after the 12:36 PDT addendum)

Why attempt 1 did not finish: it ended correctly in a wait. Both device
sessions were voided by the Thor's shared display (session 1 covered by the
AYN assistant, session 2 with the focus on display 1's launcher), and a third
session needed hostops's leave. The addendum grants ONE replacement session
(perf_harden 0 set by hostops at 12:31 PDT) and lets the guard re-issue
hakuX's `am start --display 0` once on a focus miss. `capture_gta.sh` does
that now (first check at +12 s, before the route's first input at ~+63 s);
a second miss after the re-issue still stops the session.

### Session 3 (held, replacement, 19:35:16-19:35:54Z): stopped by the foreground guard again, nothing recorded

Taken at 19:33:17Z. It waited for `arms-forza414-base` to leave the Thor
(free at 19:35:08) and started with the Thor at 86%, perf_harden 0 /
paranoid 1 (uptime 1,929 s: the Thor had rebooted again at about 19:03Z,
and hostops's 12:31 setting was applied after that). Display 0 was Awake
and clear (screencap 106,528 B, Daijisho's Settings page). hakuX launched
and rendered on display 0: logcat has `SDL_main: display ready` and
`render_display done` from 12:35:29 PDT. Even so, the focused window was:

- at +14 s: `com.android.launcher3/...secondarydisplay.SecondaryDisplayLauncher`
- after the one `am start --display 0` re-issue (+20 s, then 6 s later): the same
- at +25 s: the same, so the guard stopped the soak. The route had reached
  only its first `wait 26.7`, so no input was sent.

REST was restored (`perf_restored=true`), the caches were cleared, the screen
was put to sleep and the hold released after 38 s of device time. This used
the addendum's one replacement session. Data: `perf/2026-09-27-gta482/s3/`
(soak.log, logcat.txt, shot0.png; no records).

Reading: on the Thor, a launch on display 0 does not take the input focus
from display 1's launcher, and `am start --display 0` does not move it
either. This is #494's (lane.displayguard, PR #495). Gamepad route input
goes to the focused window, so no held session or soak on the Thor can drive
GTA to the open world until the focus is fixed, or until route input is
addressed to hakuX's display.

## State at the end of attempt 2 (2026-09-27 12:40 PDT): blocked

- Blocked on the Thor's input focus (#494). Unblocks when a Thor launch of
  hakuX reads `mCurrentFocus=...com.jreinach.hakux...`, e.g. once
  displayguard's fix or a hostops setting (display 1 off, or the launcher on
  display 1 made unfocusable) is in place. Then one held session:
  `env OUT=~/hakux-work/perf/2026-09-27-gta482/s4 DEADLINE_S=430
  bash docs/lanes/gta482/capture_gta.sh 60` (hold first, foreground,
  `timeout 570`). perf_harden resets at a reboot, so it needs
  `PERF_HARDEN0=1` again if hostops agrees.
- Rows 1 and 2 of the #482 table remain pending. Rows 3-8 (TCG-side, from
  slowdown462's data) are posted and routed (#424, #425).
- Nothing of this lane's is queued, running or held.

## Do not repeat

- Do not start a held session without a non-black screencap AND without
  checking that hakuX is the focused window. `KEYCODE_WAKEUP` succeeding says
  nothing: display 0 was Awake, with no keyguard, and covered.
- In a `while read ... done < file` loop, give every `adb` `< /dev/null`.
- A screencap of the game's surface works: slowdown462's sessions have
  0.9-1.5 MB frames. So a 10,899 B frame is a covered or dark display, not a
  capture limit.
- `/memfd:jit-cache` and `/memfd:jit-zygote-cache` are ART's JIT, not TCG.
- On the dual-screen Thor, a clear display 0 does not mean hakuX has the
  input focus. Read `mCurrentFocus` after launch and before any route input.
- A reboot resets `security.perf_harden` to 1 (paranoid 3). Read `perf:` in
  the session log. `PERF_HARDEN0=1` sets it to 0 for one session, only with
  hostops's leave.
- Do not spend a held Thor session before reading the focus with no launch:
  on 09-27, twice after a reboot, display 1's launcher held the focus, and
  neither a display-0 launch nor `am start --display 0` took it.
- In this sandbox, `systemd-run` and `setsid` need approval. Run the session
  in the foreground under `timeout 570`, with the hold taken and the running
  request waited out in an earlier call.

## Attempt 3 (resumed 2026-09-27 12:45 PDT, after hostops's addendum 2)

Why attempt 2 did not finish: its guard misread the focus, so it recorded
itself blocked on #494. `capture_gta.sh` read `dumpsys window | grep -m1
mCurrentFocus=`; `dumpsys window` prints one `mCurrentFocus=` per display and
on the Thor display 4's SecondaryDisplayLauncher is listed first, so the read
saw the launcher every time, even with hakuX focused. Hostops's launch-only
test (12:43 PDT) read `FocusedDisplayId: 0` with display 0's focused window
hakuX's GameLibraryActivity. Sessions 2 and 3 were most likely voided by the
misread, not by the focus; the "Reading" under session 3 above is wrong.

Fix: `focus.py` reads `dumpsys input`: `FocusedDisplayId: N`, then the
`FocusedWindows:` entry `displayId=N`; in front means N = 0 and that window
is `com.jreinach.hakux*`. `focus.py --selftest` runs three Thor-shaped
fixtures (written by `focus_fixtures.py`, display 4 listed first in every
block, so a first-match read fails) plus an empty read:

| fixture | focus.py | old first-match read |
|---|---|---|
| hakux (FocusedDisplayId 0, display 0 = hakuX) | in-front | display 4 launcher (miss) |
| launcher (FocusedDisplayId 0, display 0 = Daijisho) | miss | display 4 launcher |
| display4 (FocusedDisplayId 4) | miss | display 4 launcher |
| empty (adb failed) | miss | - |

No saved real `dumpsys input` from the Thor was on disk (hostops's inbox
quotes the excerpt only), so the session now saves one before launch
(`dumpsys-input-prelaunch.txt`) and refuses to launch if the reader cannot
find `FocusedDisplayId`/`FocusedWindows` in it; every guard read is saved too.
