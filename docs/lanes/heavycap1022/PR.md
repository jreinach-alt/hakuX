# heavycap1022: a slow or heavy GTA III frame records what the emulated CPU spent it on, and a sustained stretch saves a state by itself (#433)

State: draft

Lane: heavycap1022              Issue: #433 (0.5)
Base: lane/drive1022 @ 03e01c3aad
Files: docs/lanes/heavycap1022/PR.md, hw/xbox/nv2a/{heavycap.h,heavyrule.h} (new),
  hw/xbox/nv2a/pgraph/{profile.c,profile.h,pgraph.c}, hw/xbox/nv2a/{nv2a.c,pcrtc.c},
  accel/tcg/{cpu-exec.c,cputlb.c,translate-all.c}, hw/ide/{core.c,atapi.c}, system/cpus.c,
  android/app/src/main/cpp/savestate/hxs.c, docs/testing/dispatcher.sh (LOGCAT_SPEC),
  docs/testing/jobs/selftest.d/99-heavycap-rules.sh (new)
Prediction: GTA III light scenes (`[dipwin]` full/flip 300-800, `xemu-pace` G alternating ~19 / ~55 ms), perflog
  build: in the `hakuX-heavy` blocks, the frames over 50 ms carry at least 25 ms more guest idle (`gi`, the
  [rr425w] idle stretches) than the frames under 25 ms beside them, and most of that idle ends on a VBLANK wake
  (`ivb`) or follows a deferred VBLANK (`vdef`); the vCPU's lock waits (`bql`+`pfl`+`pgl`), IDE time on the vCPU
  (`io`) and translation (`tc`) each stay under 3 ms/frame on the `[hcsum]` line; the hook's own cost
  (`self_us` on `[hcsum]`) stays under 300 us.
  Falsified when the extra time of the 55 ms frames lands in the residual (`res`, guest code running) or in
  `bql`+`pfl`+`pgl`, or when the idle ends on non-VBLANK NV2A wakes (`inv`)
Needs device: yes. See section 8 (three runs for lane.local, the third through lane/savestate-req1019)
Needs NDK: yes
Selftest: 99-heavycap-rules -- heavyrule.h's trigger, rate-limit, save and slot rules, the profile.c/hxs.c call
  sites, and the hakuX-heavy tag in the dispatcher's LOGCAT_SPEC

## Step 0: already tried

Sources:
- `git log -i -E --grep='\b(vcpu|jit|tcg|bql|iothread|pacing|vblank|heavy|hitch|ide|atapi|dvd)\b'` since
  2026-09-01 (393 commits; the brief's pattern without `\b` matches 26787, since `ide` is inside most words).
- The lanes gta3instr1018, gta3dip1018, fpstel1018, fpsdiag1018 (FINDINGS.md), fpsdata1018 (fold), fpsnext1019
  (NOTES.md).
- The `hakuX-cpu` and `xemu-pace` producers: hw/xbox/nv2a/pgraph/profile.c:948-961, inside
  `nv2a_profile_flip_stall()` (:403), every 60 flips, perflog only.
- /home/justin/hakux-work/handoffs/fps30-1022/PLAN.md 1.1, and the drive1022 capture README.

| date | commit/doc | what it measured or changed | verdict | meaning here |
|---|---|---|---|---|
| 09-12/13 | 56be1278e4, b80492f6dd, 71ee02dd23, 22cea8fb5b | VBLANK as the guest sees it: phase, coalescing, grid clamp (`s_vbh`, nv2a.c:349-871) | Kept, a 2 s window | A raise-to-ack time per frame does not exist. The window is cited, not rebuilt; the new hook times raise to the PCRTC ack |
| 09-25 | b4fb2433c9 | `hakuX-pace`: exact flips per VBLANK count (v0..v4+) every 60 flips | Kept | Per-frame VBLANK count is the same delta (`pacing.vblank_fired`, profile.c:787), read per flip here |
| 09-25 | 709cfb13aa, 4ef1300091 (tcgchurn) | #311 TLB/arming counters; arming-walk model refuted | Refuted | Translation cost is not this title's lever on its own; the per-frame `tc` field checks it per heavy frame |
| 09-27 | f13290431e, 7187fd9a44 (retreason425) | `[rr425w]`: each guest idle stretch (kernel `sti;nop;nop;cli` loop) booked against the interrupt that ends it | Kept, 2 s window, cpu-exec.c:1168-1352 | The idle counter of mechanism 4. Reused: `rrw_wake()` gains never-reset per-class totals, not a second idle detector |
| 09-27 | 86573cfbea (slowdown462) | GTA open world: guest JIT code 37%, blocked 30%, dispatch 22% of the vCPU | Profile, not per frame | "Blocked 30%" is the share this lane splits per frame into lock, IDE and idle |
| 09-28/29 | c27c86c350 (vcpuplan), dc5b824498 (memfast) | vCPU time split; memfast removal is 6% of GTA's vCPU | Kept as a plan | Guest work is large; it stays the residual here, as the brief says |
| 10-03 | 012fa08a94 | `user_read` takes no pfifo.lock | Shipped | One lock-wait site removed; the remaining sites are `NV2A_LOCKW_*` (debug.h:321-326) |
| 10-03 | 7c791e0e7e (tcg424flip) | TCG flip arm | Does not ship | Not a lever; nothing reused |
| 10-04 | c2dfca18a1 | Post the guest's DMA_PUT store when pfifo.lock is busy | Shipped | The vCPU's biggest pfifo.lock wait now usually posts; `lock_wait_ns` still books what is left |
| 10-04 | b52289cd3c (vcpusleep) | Removed a vCPU sleep | Sleep gone, fps not back, reverted | A vCPU change that only moves the wait does not show; the record must show where a wait moved to |
| 10-05 | 76291926ff, a125009c1e, fold c3625aad90 (frametrace) | Per-frame critical path behind `HAKUX_FRAMETRACE=1`: vCPU waits by reason (BQL, pfifo.lock, pgraph.lock, HALT) and guest idle, with a CSV writer; builder 25 us/frame (frametrace NOTES 5) | Kept, off by default | The lock-wait counters of mechanism 1 exist. Reused in a hooks-only mode (no writer, no CSV, no Vulkan interposer) |
| 10-05 | af37f7a3ea, a160529e4a, fold d354705c69 (hitchcause) | `[ide425d]`: DMA, command-to-IRQ, IRQ-to-command and drain per 2 s window | MTV's 330 ms hitches are guest waits, not the IDE host read | The IDE counters exist but reset each window (ide/core.c `ide425_tick`). This lane adds never-reset totals beside them, per frame |
| 10-06 | 6cef37f426 (waitread1006) | Per-title wait reading | GTA is guest-bound | The premise of this lane; nothing says what the guest does in the slow frame |
| 10-09 | 5e4110e016 (pmucounters) | PMU hook at accel/tcg | Telemetry | Not per frame; not reused (needs perf access the release device may not grant) |
| 10-10 | 77fd9d4881, f1e99aaa0f (pfifowait1009) | Release pfifo.lock across STALLED finish fence waits | FAIL on both legs | Lock release alone did not move fps |
| 10-10 | 5469b1175a (postput1010) | A/B plus frametrace | The 7.3 ms lock wait was mostly gone on that base | Expect `pfl` small; the prediction says so and is falsified if not |
| 10-10 | e9c7bc5bff, b4124f4a52 (nfsframe1010, nfs30plan1010) | NFS heavy frame per thread | Plan | The per-thread heavy-frame method this lane automates for GTA |
| 10-10 | dba22feab0 (drawrec1010) | Draw recorder A/B | Speed legs pass; floor is VBLANK | A VBLANK floor is the pattern the prediction names |
| 10-11 | ee62b4edb5, 39c6dacc5e, 41c252e36f (lockwake1011) | pfifo.lock wait by site; lock-free wake for posted DMA_PUT | PASS, cold 34.54 -> 33.58 | `lock_wait_ns` is `pfl`'s fallback when the frametrace wait read fails |
| 10-12 | e318ae70b5 (savestate1011 fold) | Save states as files: slots 0-9, auto, undo, one qcow2 snapshot per state | Shipped | The save API; heavy states use slots outside the public range (12-15) |
| 10-13 | 53652bdfad (pathtele1013) | KOTOR II and SC DA read as guest-vCPU | Telemetry | Same class as GTA; nothing per frame |
| 10-16 | 3cd14060aa (perflog1016) | `[tcg787]` translate/codegen time under the run-time perflog switch | Kept | The translation counter of mechanism 3 exists (translate-all.c:465-509, cputlb.c:197-210). Reused; gated on heavycap too |
| 10-17 | bc9db33828, b7c20b2dbb (halo1016) | vCPU remedies remove 9 ms/f of work and the guest's poll absorbs it | ~39 ms/f floor | Removing guest work can turn into idle; the record must split idle from work |
| 10-18 | 97403d5c4d (gta3dip1018) | Parked frame after R1-R3; two owner stalls; ranked levers | Confounded arms | No per-frame vCPU split there |
| 10-18 | 79dce6d45c (gta3instr1018) | In-car fence split; the untimed majority | Majority untimed | The untimed part is guest-side; this lane times it |
| 10-18 | ee7f10aef8 (fpstel1018) | Forza guest/vCPU-bound vs Buffy render gap | Ranked levers | Same question for another title |
| 10-18 | fpsdiag1018 FINDINGS.md 1.1/1.4 | GTA dip class G 43-50 ms vs good 33 ms; shared signature | Known, no cause | The record is the diagnostic it asked for |
| 10-19 | 2e6d29d4f8 (fpsdata1018 fold) | FPS dip causes in the 4-title capture | Folded | No per-frame vCPU split |
| 10-19 | fpsnext1019 NOTES.md :407, :513-522 | vCPU idle 10-14 ms; P 38.2 = work 17.4 + idle 18.2 | Measured, per window | The idle half is the candidate; per frame it is unknown |
| 10-19 | lane/savestate-req1019 @ 673698bc63 | `--load-state <slot-or-file>`, `--scene` from scenes.tsv; a host state file is pushed into the scene's slot, which is backed up and restored | Draft, not folded | The replay path for the heavy states. Read only; not merged |
| 10-22 | PLAN.md 1.1, drive1022 README | Light scenes: GPU 18.5 ms, D 13-20 ms, G alternates 19/55 ms; PFIFO Idle 13-19 ms | Measured | The 55 ms frame is the subject. Host main pass is `phase_working.gpu_render_ns` (vk/draw.c:5437), read, not added |

None of these records what the vCPU did inside one guest frame. Every counter the brief names exists in some form
except a per-frame raise-to-ack VBLANK time and a cumulative IDE total; the rest are reused.

## 1. Mechanisms, ranked from code

1. **Guest idle waiting on VBLANK** (mechanism 4). The kernel idle loop is booked by `rrw_sti()`/`rrw_wake()`
   (cpu-exec.c:1234/1274) on every build. PLAN.md 1.1 has PFIFO idle 13-19 ms in light scenes, so the vCPU is
   not feeding work; fpsnext1019 puts 18.2 ms of a 38.2 ms frame in idle. VBLANK is raised under the BQL at
   nv2a.c:932-944 (simple) and :1154-1174 (timer, which can defer), and acked at pcrtc.c:57-60. Ranked first.
2. **Lock waits** (mechanism 1). pfifo.lock: `pfifo_lock_timed()` (nv2a_int.h:299) into `lock_wait_ns` by site,
   always on. BQL: every NV2A MMIO access from the vCPU takes the BQL (no region is lockless), booked by
   `bql_lock_impl()` (cpus.c:947) only under frametrace. pgraph.lock: pgraph.c:964/1078, frametrace only. `rotfen`
   (vk/draw.c:6197-6200, X-macro :1251) holds both nv2a locks while it waits on a fence, so a guest store to a
   USER register in that window waits. postput1010 and lockwake1011 removed most of it. Ranked second.
3. **IDE** (mechanism 2). The submits run on the vCPU thread under the BQL (`blk_aio_preadv`, ide/core.c:744;
   `dma_blk_read/write` :1103/:1107); completions on the main loop under the BQL. hitchcause found the host read
   is not the hitch. Ranked third.
4. **Translation and flushes** (mechanism 3). `tb_gen_code` time (translate-all.c:465-509) and TLB flush time
   (cputlb.c:197-210), on the vCPU thread. tcgchurn and memfast bound it to a few percent. Ranked fourth.
5. **Residual**: guest code running = frame - (idle + locks + IDE on vCPU + translation).

(Line numbers in this section are the base's; sections 3-5 give the worktree's.)

## 2. Territory

gpubreak1022 owns hw/xbox/nv2a/pgraph/vk/. This lane does not edit it. It reads
`g_nv2a_stats.phase_working.gpu_render_ns` (written at vk/draw.c:5437) before profile.c resets it, and cites
`rotfen`. The frametrace Vulkan interposer (`ft_vk_hook`, profile.c:253-393) is not installed in heavycap mode.

Also left alone: the app's own logcat tag list (`LOG_TAGS`, HakuXApplication.kt:15), which has no `hakuX-heavy`;
the in-app log file is the user's bug report, and the record is read from the host capture. run_disc.sh:79 and
soak_title.sh:36 have their own LOGCAT_SPEC fallbacks, used only when they run without the dispatcher; the
dispatcher exports its own, which now has `hakuX-heavy:I`.

## 3. The record

On when `NV2A_PERF_LOG` is 1 (perflog builds), or with `HAKUX_HEAVYCAP=1` (or `HAKUX_HEAVYSAVE=1`, which needs
it) on any build. `hakux_heavycap_init()` (profile.c:526, called from system/cpus.c:449 before any vCPU exists)
reads the environment once and sets `hakux_hc_on`; every site tests `hakux_heavycap_on()` (heavycap.h, a relaxed
load). Off, each site is that load and a branch, and nothing else runs. On, it turns on the frametrace's vCPU wait
hooks only (`hakux_ft_init_hooks()`, profile.h:734: no CSV writer, no Vulkan interposer, `ft_full=0` in the `on:`
line) and logs once:

```
[heavycap] on: perflog_build=1 draws_bar=1000 save=0 ring=256 pre=30 post=30 block_gap_s=10 save_gap_s=60 keep=4 ft_full=0 (rules: hw/xbox/nv2a/heavyrule.h)
```

One record per guest frame, flip to flip, in a ring of 256 (profile.c:448-464), built by `hc_flip()`
(profile.c:830) at the top of `nv2a_profile_flip_stall()` (:949), on the PFIFO thread. Every field is a
difference of never-reset totals read at the flip, in us (printed as ms with two decimals) unless a count:

| field | what it measures | counted at |
|---|---|---|
| `f`, `t` | the frame this flip ends; flip time, monotonic ms | profile.c:850 |
| `g` | flip to flip, `get_clock()` | profile.c:852 |
| `dr` | draws: SET_BEGIN_END begins since the last flip (the same event as `xemu-work`'s `BE:`) | pgraph.c:4937 |
| `vb` | VBLANKs fired, `g_nv2a_stats.pacing.vblank_fired` | (existing) |
| `gpu` | host GPU main pass, `phase_working.gpu_render_ns` (vk/draw.c's timestamp readback; may land a frame late) | read only |
| `gi` | guest idle: the kernel's `sti;nop;nop;cli` stretches, an open stretch counted to the flip | cpu-exec.c:1215-1260, 1320 (`rrw_sti`), 1346 (`rrw_wake`) |
| `ivb inv itm iide ioth`, `iw` | that idle by the interrupt that ended it: vector 0x33 with the PCRTC bit (VBLANK), 0x33 otherwise (other NV2A), 0x30 (PIT), 0x3e (IDE), other; `iw` stretches ended | cpu-exec.c:1229 `hc_rrw_class()` |
| `hlt bql pfl pgl`, `nw` | vCPU halted, waiting for the BQL, for pfifo.lock, for pgraph.lock (the frametrace hooks); `nw` waits. If the wait read fails, `pfl` falls back to `cpu_working.lock_wait_ns` | profile.h:1161 `hakux_ft_vcpu_waits()` |
| `mm` | vCPU MMIO dispatch (frametrace; includes `pfl` and `pgl`) | profile.h |
| `io`, `iom` | IDE/ATAPI time on the vCPU / on any other thread: buffered read submit (core.c:812-815), DMA submit (:1171-1181), cancel drain (:856-861), the synchronous ATAPI sector read (atapi.c:97-121) | hw/ide/core.c:72-135 |
| `dev`, `kb`, `cmd` | command-to-IRQ latency, kB moved, commands | core.c:2430, :3111 |
| `tc`, `cg`, `tn` | `tb_gen_code` time, its codegen part, translations | translate-all.c:498-509 |
| `fl`, `tbf` | TLB flush time, full and page; whole-cache `tb_flush`es | cputlb.c:863/896, :1044/1070; totals :428 |
| `tf` | TLB miss fills (perflog switch only; 0 otherwise) | cputlb.c:2009 |
| `vack`, `nack` | VBLANK raise to the guest's PCRTC acknowledge (sum, count) | nv2a.c:945 (simple), :1179 (timer); pcrtc.c:59-64 |
| `vdef`, `vmiss` | VBLANKs raised late by the deferral; raised while one was still pending | nv2a.c:1179, :945 |
| `res` | `g - max(gi, hlt) - bql - pfl - pgl - io - tc - fl`: guest code running, signed | profile.c:886 |
| `trig`, `sv` | trigger bits / save reasons this record fired | heavyrule.h |
| `lg` | this hook's own time on the previous flip, logging included | profile.c:935 |
| `bad` | 1: the idle read failed, 2: the wait read failed (their deltas roll into the next record), 4: a heavy save ran in this frame | profile.c:890-898 |

The writers: idle, by the vCPU only, under a seqlock (the reader retries 8 times, else `bad=1`); IDE and VBLANK,
under the BQL; TCG, by the vCPU; draws, by the PFIFO thread. Every add is `HC_ADD` (heavycap.h), a relaxed atomic
store of a single writer's sum, so the PFIFO thread reads whole values without a lock.

## 4. Trigger, block, summary, save

All limits are heavyrule.h's (pure functions, no clock, no lock), which the selftest builds on the host.

- **Trigger** (`hc_trigger()`): the frame is over 50 ms (`HC_TRIG_SLOW` 1), or the flip has over 1000 draws
  (`HC_TRIG_DRAWS` 2), or the host main pass is over 33 ms (`HC_TRIG_GPU` 4). Over, not at. The draws bar is
  `HAKUX_HEAVYCAP_DRAWS` when set (1 to 999999).
- **Block** (`hc_block_admit()`): a firing frame starts a block of the 30 records before it, itself and the 30
  after it, unless a block is still collecting or the last one started under 10 s ago; a refused fire is counted
  and printed as `sup=` on the next block header and on every summary. The block prints 4 lines a flip once its
  30 after-records exist (profile.c:805), so no flip pays for 62 lines:

  ```
  [hcblk] b=<block> f=<firing frame> trig=<bits> sup=<refused fires> pre=30 post=30 draws_bar=1000
  b=<block> i=-30 f= t= g= dr= vb= gpu= gi= ivb= inv= itm= iide= ioth= iw= hlt= bql= pfl= pgl= nw= mm= io= iom= dev= kb= cmd= tc= cg= tn= fl= tbf= tf= vack= nack= vdef= vmiss= res= trig= sv= lg= bad=
  ...                                  (i=0 is the firing frame)
  b=<block> i=30 ...
  ```
- **Summary** every 2 s of flips (profile.c:772): `[hcsum] n= span=` then each time field's mean ms per frame
  (`g gpu gi ivb inv itm iide ioth hlt bql pfl pgl mm io iom dev tc cg fl tf vack`), `res`, `dr` per frame,
  `vb100` (VBLANKs per 100 frames), the `slow`/`heavy`/`gpuslow` counts, `self_us`/`self_max_us` (the hook's cost),
  `sup`, `blocks`, `saves`, `save_refused`.
- **Draw units.** `dr` counts what `xemu-work`'s `BE:` counts. Against `[dipwin] full=` per flip (vk/draw.c:1377)
  in the drive1022 captures, BE/full medians are 1.26 (300-800 full, n=10), 1.04 (800-1000, n=2), 0.86 (1000-1200,
  n=1) in pid21946, and 0.95-1.15 in pid9072/pid23374 (n=1-2 per band). Near the bar the two counts agree within
  about 15%, on thin samples; `HAKUX_HEAVYCAP_DRAWS` moves the bar without a build.
- **Save** (`HAKUX_HEAVYSAVE=1`, `hc_save_check()`): fires on 1 s of consecutive flips over the draws bar (the run
  starts at its first heavy frame's start; any flip at or under the bar ends it), or on 3 frames over 50 ms whose
  ends fall within 2 s. At most one per 60 s; a firing inside the gap is refused and counted (`save_refused`).
  Firing clears both conditions. The record that fired is kept and printed with the result:

  ```
  [heavycap] save 5454000e/heavy1.hxs ok=1 ms=<total> pause_ms=<VM paused> why=draws|slow|draws+slow |<the firing record>
  ```
  and `[heavycap] save - ok=0 ...` lines for "no saver registered", "busy" and "not posted".
- **Slots** (`hc_pick_slot()`): 4 files, heavy0.hxs to heavy3.hxs, as hxs.c slots 12-15 (`HC_SLOT_BASE` 12, past
  `HXS_SLOT_COUNT`: slots 0-9, auto 10, undo-save 11). The first empty one, else the one saved longest ago (a
  damaged file has no `saved_at` and goes first). hxs.c asserts the base at build time (hxs.c:85, :757). The
  listing (hxs.c:3059) and auto-load (:3079) scan only 0-11 and 0-10, so a heavy state is never shown, never
  auto-loaded and never written over slots 0-9 or auto.
- **`bad=4`.** A frame during which a heavy save was posted, running or finished holds the VM pause; it fires no
  trigger and feeds no save rule (profile.c:902), so the capture never triggers on itself. It still enters the
  ring and the summary means.

## 5. The save thread, and why it is safe

hxs.c:3434-3503. The rule fires on the PFIFO thread, which holds the PFIFO and pgraph locks there. A save cannot be
made from it: `on_main()` blocks the caller while `save_main()` runs `vm_stop(RUN_STATE_SAVE_VM)` on the main loop,
and `nv2a_vm_state_change()` then takes the PFIFO lock and waits for PFIFO to signal idle, which the blocked PFIFO
thread never does. A vCPU caller deadlocks the same way in `pause_all_vcpus()`, and `on_main()` refuses the main
loop (it holds the BQL). So the flip only posts a semaphore: `heavy_post()` takes no QEMU lock, allocates nothing
and returns. The `hxs-heavy` thread, which holds no QEMU lock, waits on it and makes the save exactly as the Java
thread behind `nativeSaveStateSave` does: `hxs_save_heavy()` (hxs.c:2484) picks the slot under `hxs_op_mu` and
`hxs_mu`, then `save_locked()` in the menu save's default mode, durable before it returns, with the VM work on the
main loop through `on_main()`. One save is in flight at a time (profile.c's busy flag, set by compare-and-swap
before posting and cleared by `hakux_heavycap_saved()` after the count, :671-682), and at most one per 60 s.
`heavy_start()` is off while the savestate self-test runs (`cfg_testing`) and logs `[savestate] heavy-save on:
slots 12-15 (heavy0-3.hxs)` when it registers.

**The disk snapshot goes with the file.** Each heavy save makes its own qcow2 snapshot, named
`hxs-<root>-<title>-h<K>-<uuid8>` (hxs.c:2254-2258). When a heavy slot is written again, the file it replaces goes
the way an auto slot's does (`jobs_settle(..., slot, slot)`, `place_file()`), so its snapshot is deleted once no
other `.hxs` file names it. `hxs_delete()` (hxs.c:2899-2907) now accepts slots 12-15 and deletes the file's
snapshot the same way. A file removed outside the app (adb rm) leaves its snapshot, as for every slot.

## 6. Checks

cc_wt.py (desktop build flags, worktree headers), every touched C file with `-DNV2A_PERF_LOG=1` and `=0`. 0 errors
everywhere; every warning is on a line this lane did not touch (`git blame`: profile.c:967 ee62b4edb5, :1563/:1570
85916e933e, :1652 c34c24954a), and the counts are the same at 1 and 0:

```
hw/ide/atapi.c hw/ide/core.c hw/xbox/nv2a/pcrtc.c system/cpus.c   0 warnings
hw/xbox/nv2a/nv2a.c           1  :96 -Wmissing-prototypes
hw/xbox/nv2a/pgraph/pgraph.c  2  profile.h:190 -Wredundant-decls; :294 (=0) / :254 (=1) -Wmissing-prototypes
hw/xbox/nv2a/pgraph/profile.c 5  profile.h:190; :967 -Wenum-compare; :1563 -Wcomment; :1570 -Wnested-externs;
                                 :1652 -Wunused-variable
accel/tcg/cputlb.c            4  :351, :352 (x2) -Wnested-externs; :1656 -Wmissing-prototypes
accel/tcg/cpu-exec.c          4  :76, :88, :94, :174 -Wmissing-prototypes
accel/tcg/translate-all.c     2  :1340 -Wmissing-prototypes; :1350 -Wunused-variable
```

cpu-exec.c and translate-all.c are checked with their system-emulator (libsystem) compile command; cc_wt.py's
first match is the linux-user one, which does not build them.

The Android-only log calls do not build on the desktop, so all eight hw/accel/system files were also compiled with
`-D__ANDROID__ -Wformat=2` and a stub `android/log.h` declaring `__android_log_print` with `format(printf, 3, 4)`
(its `#warning` shows in each output, so it was the one included), at both perflog values: 0 errors and 0
`-Wformat` warnings in every file. A probe that passes a `uint64_t` to `%d` through that stub is flagged, so the
check can fail.

NDK 29.0.14206865 (clang, the Android Release build's flags from compile_commands.json, worktree includes),
`-DNV2A_PERF_LOG=1` and `=0`:

```
== android/app/src/main/cpp/savestate/hxs.c   rc 0 errors 0 warnings 0     (both values)
== hw/xbox/nv2a/pgraph/profile.c              rc 0 errors 0 warnings 3     (both values)
include/exec/target_page.h:57:12: warning: shifting a negative signed value is undefined [-Wshift-negative-value]
hw/xbox/nv2a/pgraph/profile.c:1563:17: warning: '/*' within block comment [-Wcomment]
hw/xbox/nv2a/pgraph/profile.c:1652:11: warning: unused variable 'idle_pct' [-Wunused-variable]
```

Selftest, `SELFTEST_ONLY=99-heavycap-rules`:

```
heavyrule_test builds against heavyrule.h with -Wall -Wextra -Werror; 16 cases (trig x4, block x3, save x6, slot x3)
11 heavyrule.h mutants, each reinstating a weaker rule, each FALSIFIED by its case:
  ge (at the bar fires), nogpu, nogap, overlap, slow2, nowin, nosavegap, noreset, runend, base10, newest
3 call-site mutants FALSIFIED: profile.c without the bad=4 guard; profile.c clearing busy before the count;
  hxs.c with its own heavy slot base (10)
the hakuX-heavy tag is in the dispatcher's LOGCAT_SPEC at I or below (sourced, not grepped); 2 mutants
  FALSIFIED: the spec without the tag, the tag at W
selftest: 27 passed, 0 failed, PARTIAL: 1 of 161 fragments
```

The frametrace check, whose hooks this lane's mode turns on: `python3 -I docs/lanes/frametrace/selftest.py --cc cc` PASS (43
checks, 21 mutants). The fragments that source dispatcher.sh's LOGCAT_SPEC (51-dispatch-hardening section I,
99-ownerplay-capture): section I 15 of 15 and ownerplay 29 of 29.
Run alone, 51's sections E and E2 fail 7 checks because they need 50's fixture state. So 51 was rerun as part of the
chain it belongs to: `SELFTEST_ONLY` with the 13 dispatcher fragments 10-arms-list .. 94-arms-label-state gave
`selftest: 290 passed, 0 failed, PARTIAL: 13 of 161 fragments`, with exit 0. (51 reports "took -459s" because the host
clock stepped back during the run; the timing is wrong, not the result.)

Not run: the full selftest, an NDK link or APK build, a desktop link, any device.

## 7. Risks

- Never executed. The first device run is the first time `hc_flip()` runs; `self_us` and `self_max_us` on
  `[hcsum]` and `lg` per record are the 0.3 ms check, and nothing has measured them.
- On, the frametrace BQL/lock hooks run on every lock (their cost is frametrace NOTES 5's, not re-measured here).
- `gpu` is the readback of an earlier submit; a frame's `gpu` can belong to the frame before it.
- `res` is signed and the parts overlap a little (an IDE submit can sit inside a BQL hold); a negative `res` is
  overlap, not time.
- An idle stretch open across a flip is in that frame's `gi`, but its class lands in the frame it ends in.
- A heavy save pauses the VM for its `pause_ms`; that frame is marked `bad=4`, and the next 60 s cannot save.
- The draws bar is in BE units, not `[dipwin]` full draws (section 4).

## 8. Device: what lane.local must run

All on the Nova (the Thor is on hold), GTA III (5454000e), with an APK built from this branch. Confirm
`GPU: PurpleVK` in each run's `hakuX-phase` line before reading anything else.

1. **The record.** A perflog build (or `--env HAKUX_HEAVYCAP=1` on a release build), the driving scene. Read the
   `[heavycap] on:` line (`ft_full=0`), `[hcsum]` every 2 s (`self_us` under 300, `self_max_us` noted), and the
   `[hcblk]` blocks (at most one per 10 s). The prediction above is scored from the blocks: the >50 ms frames
   against the <25 ms ones beside them, by `gi`, `ivb`/`inv`, `vdef`, `res` and `bql`+`pfl`+`pgl`.
2. **The heavy save.** The same, with `--env HAKUX_HEAVYSAVE=1`, long enough for five saves (over 4 minutes of
   heavy driving). Check `[savestate] heavy-save on: slots 12-15`, one `[heavycap] save 5454000e/heavyK.hxs ok=1` line per
   save with `ms=`/`pause_ms=` and its record, no save within 60 s of another, the files
   `states/5454000e/heavy0.hxs`..`heavy3.hxs`, and that the fifth save replaced the oldest file and its snapshot
   left the HDD qcow2 (no `[savestate] snapshot-delete ... ok=0`; `qemu-img snapshot -l` on a pulled copy lists
   four `-h<K>-` snapshots). Slots 0-9 must be byte-identical before and after, and no `[heavycap] save` line
   names anything but heavy0-3. Then pull one heavy
   state to `/home/justin/hakux-work/captures/heavycap1022/heavy0.hxs`, and clear the `env_vars` pref (the env
   outlives the run; more heavy saves would rotate the slot the replay needs).
3. **The replay**, through lane/savestate-req1019 (673698bc63), once it is folded and its dispatcher is serving
   (its request.sh refuses `--scene` until then). Add this row to its `docs/testing/scenes.tsv` (tab-separated):

   ```
   gta3-heavy0	5454000e	9	/home/justin/hakux-work/captures/heavycap1022/heavy0.hxs	rt:60
   ```

   (the indent is the list's, not the row's). Appended to 673698bc63's scenes.tsv, request.sh's own reader
   (`csv.DictReader`, tab) gives `{"name": "gta3-heavy0", "title_id": "5454000e", "slot": "9", "state_file":
   "/home/justin/hakux-work/captures/heavycap1022/heavy0.hxs", "default_hold": "rt:60"}`. Then run
   `request.sh --who heavycap1022 --scene gta3-heavy0 --device nova --perflog --issue 433 --no-expect`.
   Slot 9 is the target because the heavy slots cannot be named (`hxs_slot_name()` and request.sh take only 0-9,
   10 and auto); the dispatcher backs slot 9 up to `slot9.hxs.orig.hld`, pushes the file there and restores both
   afterwards. The state's disk snapshot is in the same Nova's HDD qcow2, so the replay must be on that device,
   before the snapshot is rotated away. Pass: `[savestate] op=load` ok for slot 9, then `[hcblk]`/`[hcsum]` lines
   from the heavy scene within the first minute.
