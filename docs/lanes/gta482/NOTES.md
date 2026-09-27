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

## Do not repeat

- Do not start a held session without a non-black screencap AND without
  checking that hakuX is the focused window. `KEYCODE_WAKEUP` succeeding says
  nothing: display 0 was Awake, with no keyguard, and covered.
- In a `while read ... done < file` loop, give every `adb` `< /dev/null`.
- A screencap of the game's surface works: slowdown462's sessions have
  0.9-1.5 MB frames. So a 10,899 B frame is a covered or dark display, not a
  capture limit.
- `/memfd:jit-cache` and `/memfd:jit-zygote-cache` are ART's JIT, not TCG.
