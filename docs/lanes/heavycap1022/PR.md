# heavycap1022: a slow or heavy GTA III frame records what the emulated CPU spent it on, and a sustained stretch saves a state by itself (#433)

State: draft

Lane: heavycap1022              Issue: #433 (0.5)
Base: lane/drive1022 @ 03e01c3aad
Files: docs/lanes/heavycap1022/PR.md (Step 0; the code list is filled in section 5 when it lands)
Prediction: GTA III light scenes (`[dipwin]` full/flip 300-800, `xemu-pace` G alternating ~19 / ~55 ms), perflog
  build: in the `hakuX-heavy` blocks, the frames over 50 ms carry at least 25 ms more guest idle (`gi`, the [rr425w]
  idle stretches) than the frames under 25 ms beside them, and those stretches end on a VBLANK-class wake (`vb`) or
  follow a deferred VBLANK; the vCPU's lock waits (`lk`), IDE time on the vCPU (`io`) and translation (`tc`) each
  stay under 3 ms/frame on the summary line.
  Falsified when the extra time of the 55 ms frames lands in the residual (`res`, guest code running) or in `lk`,
  or when the idle ends on non-VBLANK NV2A wakes (`nv`)
Needs device: yes. See section 8
Needs NDK: yes
Selftest: (named when the fragment lands)

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
| 10-10 | 5469b1175a (postput1010) | A/B plus frametrace | The 7.3 ms lock wait was mostly gone on that base | Expect `lk` small; the prediction says so and is falsified if not |
| 10-10 | e9c7bc5bff, b4124f4a52 (nfsframe1010, nfs30plan1010) | NFS heavy frame per thread | Plan | The per-thread heavy-frame method this lane automates for GTA |
| 10-10 | dba22feab0 (drawrec1010) | Draw recorder A/B | Speed legs pass; floor is VBLANK | A VBLANK floor is the pattern the prediction names |
| 10-11 | ee62b4edb5, 39c6dacc5e, 41c252e36f (lockwake1011) | pfifo.lock wait by site; lock-free wake for posted DMA_PUT | PASS, cold 34.54 -> 33.58 | `lockw_site_ns` is reused as the `lk` pfifo part |
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
| 10-19 | lane/savestate-req1019 @ 673698bc63 | `--load-state <slot-or-file>`, scenes.tsv, dispatcher file mode pushes the file as `auto.hxs` | Draft, not folded | The replay path for the heavy states. Read only; not merged |
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

## 2. Territory

gpubreak1022 owns hw/xbox/nv2a/pgraph/vk/. This lane does not edit it. It reads
`g_nv2a_stats.phase_working.gpu_render_ns` (written at vk/draw.c:5437) before profile.c resets it, and cites
`rotfen`. The frametrace Vulkan interposer (`ft_vk_hook`, profile.c:253-393) is not installed in heavycap mode.
