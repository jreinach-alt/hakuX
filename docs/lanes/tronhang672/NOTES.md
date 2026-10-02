# lane.tronhang672 -- Tron 2.0: Killer App hangs entering the first level (Nova)

Issue #672 (local forge), umbrella #433. Base master 4c76e80bd3.

## 1. What the three runs show (offline, 2026-10-02 13:30-14:00 PDT)

### Run 1790971658-lanelocal-1220020 (master 6b0c4a131f, Nova, 13:08-13:23 PDT)

Soak start 13:08:09. Frames: cutscenes to t=420 s, the "Unauthorized User"
loading card with the Action-button tutorial at t=450 s (13:15:39), near-black
from t=480 s to the end.

| time (PDT) | guest flips / 10 s (`[pace526]`) | guest state (`[rr425w]`, 2-s windows) |
|---|---|---|
| 13:15:30 | 579 | busy in NV2A wakes (`33.44`), normal play |
| 13:15:41-47 | 427 | busy after a timer wake (`30.02`) |
| 13:15:49-53 | 361 | IDE wakes (`3e.00`, vector 0x3e = IRQ14), ~500 per 2 s: the level load reading |
| 13:15:55-57 | -- | guest IDLE 1.96 s of 2 s (only timer/USB wakes) |
| 13:15:59 | 19 (13:16:00) | 84 IDE wakes, then busy |
| 13:16:01 to 13:23:39 (end) | 3, then 0 for 7.5 min | **busy 100% charged to the last IDE wake, never idle again**; `3e` nb=0 (no IDE interrupt after it) |

During the hang (13:18:01, w=293):

- `[rr425]` hc=78.4M `helper_lookup_tb_ptr` calls per 2 s, hm=0, against it=29k
  dispatches: the guest runs a call/ret (indirect-branch) loop inside chained
  TBs. `[rr425pc]` only sees returns to the loop, so its top entries are the
  interrupt paths (kernel 8001xxxx) and one game `sti` at 005a7a63 (253/s).
- Interrupts are delivered: timer `30.00` nb=2003 per 2 s (1 kHz), USB `31.00`
  501, NV2A vblank `33.02` 121 (60 Hz). Interrupts are enabled and the kernel
  scheduler runs; some thread is always ready.
- `fifoskew kicks=0 backlog=0`: the guest submits nothing to the GPU and the GPU
  has nothing pending. Host presents continue (pres=601/10 s): the screen shows
  the last surface, near-black.
- Audio keeps running (`voice_headroom` 30000 active voice-frames per window).
- `hakuX-tier1` logs no promotion after 13:15:56 and consumed only 5 tier-1
  blocks in the whole run (consume #0-#4, all before 13:10:28).
- No `hakuX-vk` error, no `hakuX-stderr` after 13:12:00, no tombstone, no
  libc/DEBUG line in this run.

### The two earlier runs (titleroutes2, 08:03 and 08:13 PDT)

Both never left the Xbox Live sign-in loop (route.txt notes), so they never
reached the level load. Their `media.extractor` tombstones (08:05:47 at 213 s
uptime, 08:13:54 at 73 s) sit in the middle of normal play: `[pace526]` reads
599-601 flips per 10 s to the last line of both logcats.

**The media.extractor crash is a bystander.** hakuX does not use Android's
media stack: no `MediaExtractor`, `MediaCodec`, `MediaPlayer`, `AMedia*`,
`SoundPool` or `MediaMetadataRetriever` anywhere under `android/`. Video and
audio decode are the guest's own, in software, inside the emulator.

## 2. Ranked hypotheses

Probability x size: every one of these, if right, is the whole defect (the
title cannot be played at all past the first load), so the sort is by
probability.

| # | hypothesis | p | right: a device run shows | wrong: it shows |
|---|---|---|---|---|
| H1 | A thread polls (spin or yield loop) for an async operation whose completion hakuX never signals: a status bit, a DMA-written word, or an event that needs an interrupt that never comes. Candidates by device: the APU/DSP (XACT/DirectSound load of the level's wave banks), the GPU (a fence/semaphore word written by pgraph), the IDE/ATAPI (a read whose completion state is wrong, since the busy period follows the last IDE wake directly). | 0.45 | `[spin672]` top pcs in the XDK library code of the XBE (DSound/XACT, D3D, or XAPI file I/O), the loop's code bytes reading an MMIO address (fe8xxxxx APU, fd00xxxx NV2A) or a fixed RAM word, `[spin672r]` the same thread every window | the loop is game logic with no device read |
| H2 | A software loop that does not terminate because an emulated instruction computes the wrong result (x87/SSE precision or flush-to-zero, a flags miscompute, a JIT/IBC fast path). | 0.25 | the loop is pure compute (FP or integer), no device or shared-RAM read; its exit compare is on a computed value | the loop polls state another agent writes |
| H3 | Priority inversion or a race the emulator's timing exposes: a high-priority thread yields/spins waiting for a lower-priority one that never gets the CPU, or for a flag set in a window the emulator's instant I/O closes. | 0.20 | the loop calls the kernel's yield/wait with zero timeout (NtYieldExecution, KeDelayExecutionThread(0)) and reads a RAM flag; another thread's pc appears in some windows (thr= changes) | one thread, no yield |
| H4 | A kernel-level loop (the utility-drive cache on the HDD, Tron's Z: cache, or the file system). | 0.10 | top pcs at 8001xxxx-8003xxxx, irql > 0 | top pcs in the XBE |

The near-black frames are a consequence (the guest stopped drawing), not a
renderer fault: no Vulkan error, no GPU backlog.

## 3. Instrument (device run 1)

`[spin672]` / `[spin672r]` (accel/tcg/cpu-exec.c,
target/i386/tcg/system/seg_helper.c), one pair per 2-s `[rr425]` window,
read-only:

- 1 in 4096 `helper_lookup_tb_ptr` calls books its target pc; the window prints
  the top 8 with 32 code bytes each. The loop's call targets and return sites
  are what this sees. Disassemble with
  `objdump -D -b binary -m i386 --adjust-vma=<pc>`.
- the registers at the tick, IRQL and current KTHREAD from the KPCR, 16 stack
  dwords, 6 return addresses down the ebp chain.

Run 1 expectation: the title reaches the loading card at ~450 s as before and
the guest goes busy with 0 flips; the `[spin672]` lines from then on name the
loop. If the hang does not reproduce, the run itself is the news (the hang is
intermittent; record its frames).

## 4. Device run 1: 0-1790974820-tronhang672-2186958 (ref 16f09aa346, 14:00-14:11 PDT)

**No hang.** The instrument works (`[spin672]` 2 lines per 2 s). The run took a
different path from the hung one:

- 1790971658 left a save, so the Single Player cursor now starts on **Auto
  Load** (route-frame 140237). The route's A loaded the post-intro checkpoint,
  which is **the same second load** ("Unauthorized User", Action-button card)
  that hung in 1790971658.
- That load finished in ~40 s (card 14:02:43-14:03:03). Then a cutscene, the
  basic-training prompt, a Save Game screen, and live play with the HUD from
  t=240 s to the end at 30-39 fps.

So the second load does not hang by itself on a fresh boot. The hung run reached
it after New Game's first load and ~4.5 min of in-engine intro, at 471 s of
process uptime. Either the hang needs the state the intro leaves (guest heap,
an emulator-side cache or counter that grows with run time), or it is
intermittent. Run 2 repeats the hung run's path: route
`docs/lanes/tronhang672/tron-newgame.route` (one DOWN to pick New Game, the rest
of the inputs unchanged).

## 5. Device run 2: 0-1790975634-tronhang672-2276276 (14:14-14:26 PDT): void, route timing

Boot was ~10 s slower than 1790971658: the ESRB card was still up at the
route's START (141524), the title came at 141535, so B landed on the title and
the run looped the Xbox Live sign-in at 60 fps for the rest of the soak. No
information about the hang. Route v2 waits until ~80 s before START.

## 6. Device run 3: 0-1790976263-tronhang672-2397053 (14:26-14:38 PDT): void, route timing again

At 80 s the attract video was playing (142828). START dropped it to the title
(142846), B landed on the title, and the run looped the sign-in. Boot-to-title
varies by at least 15 s between boots, so no single START time is safe. Route
v3 presses START five times, 7 s apart, from 55 s (START is a no-op on the
sign-in screen), then the one B.

Device runs used: 3 of 6 (two of them lost to the route, none to the hang).

## 7. Device run 4: 0-1790976604-tronhang672-2513164 (14:40-14:52 PDT): Auto Load path again

Route v3 reached the sign-in (five STARTs) and the main menu, but `press DOWN`
did not move the Single Player cursor (route-frame 144159): this pad's D-pad is
a hat axis, as other routes use (`axis HATY max` / `mid`). A loaded Auto Load
again, so this run is a second sample of the path that passed in run 1, not of
the hung path. Route v4 moves the cursor with `axis HATY max`.
