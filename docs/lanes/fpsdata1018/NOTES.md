# fpsdata1018 NOTES (#433)

Lane: fpsdata1018. Brief: `/home/justin/hakux-work/briefs/fpsdata1018.md` (owner 2026-10-18 ~22:00 PDT): find the
causes of the FPS dips in the owner's 4-title capture (`/home/justin/hakux-work/captures/fps-owner-1018/`, master
perflog 72af9cb92c, Nova, PurpleVK) and land fixes.

## Attempt log

- **Attempt 1** (session 4431cc4c, 2026-10-19 04:39-04:51Z): committed nothing. It added two candidates to
  `fpsdiag.py` (`c2b_fin_sub_renderthread_wait`, `c9_surf_download_wait`), bumped the 99-fpsdiag candidate count
  10 -> 12, regenerated the four `<title>.analyze.txt` files in the capture dir, and was cut off while running the
  99-fpsdiag selftest fragment in the foreground. Its lane log (`logs/lane/fpsdata1018.20261019T043934Z.json`) is
  0 bytes: the session ended with no closing words, so handback resumed it as idle. Why it did not finish: it went
  to the tool before Step 0, never wrote NOTES.md, and the session ended (12 minutes in) before its first commit.
  Its two edits are kept (they read the capture correctly, checked below). This attempt commits Step 0 first.
- **Attempt 2** (this session): Step 0, then the mechanism account (G2), then fixes.

## Step 0: Already-tried (G1)

One row per lever or theory a prior lane tried or measured. A candidate this lane proposes that is already a row is
dropped unless the row's "what is different" is stated where it is proposed.
Sources: `L/` = `docs/lanes/`; README = `captures/lanexbox-fps1018/README.md`; instr = the gta3instr1018 worktree
NOTES (newer than master's); ralli = `wt/ralli2audio1018/docs/lanes/ralli2audio1018/`.

| # | Lever / theory | Title | What moved (as written) | Control / spread | Verdict | Source |
|---|---|---|---|---|---|---|
| 1 | R1: skip the #474 drain (folded 4a504d9aaa; `HAKUX_S2T_DRAIN=1` restores) | GTA III | Nova parked +1.9 (b2), +2.7 (b5) fps, ~50 -> ~46 ms/frame; desktop drains/flip 1.86 -> 0 | b2 palindrome P A B C C2 B2 A2 P2; b5 W P A A2 P2 | works, small; folded | `L/gta3fps1017/NOTES.md` 2.4; README |
| 1a | R1 driving | GTA III | 29.80 vs 29.77 fps | scenes not aligned | confounded | `L/gta3fps1017/NOTES.md` 2.5 |
| 2 | R2 `HAKUX_S2T_WIDEN=1` (remove all copies/flip) | GTA III | copies 133.2/69.8 -> 0/0; fps vs R1 -0.3 (b2), -0.9 (b4) | b2, b4 palindromes | **falsified** (copy theory) | README; `L/gta3fps1017b/NOTES.md` 2.2 |
| 3 | R3 `HAKUX_S2T_SHARE=1` | GTA III | share 0.00, dup 0 | b2 | inert | README |
| 4 | Copies cause the parked dip | GTA III | RP/frame 54.6 / 52.5 / 53.5 at 133 / 0 / 0 copies | b3 arms | falsified (parked) | `L/gta3dip1018/FINDINGS.md` 1.1 |
| 5 | R1-R3 on Blinx 2 | Blinx 2 | `[s2c]` cp 0 idle and moving | bc-A | inert (nothing to act on) | README |
| 6 | Cold shader/pipeline compile | GTA III, Fable | explains GTA's 1.46 s / 3.89 s single stalls and one Fable 3.78 s frame; not the sustained dips (counters flat during them) | per-capture timeline | ruled out for sustained dips | `L/gta3dip1018/FINDINGS.md` 2; `L/fabledip1018/FINDINGS.md` 1b |
| 7 | GPU saturation | all four | busy 55-72 % GTA/R2, 25-29 % others in this capture; earlier ~34 % flat | dip/good classes | refuted (c1-A1 in-car 90/43 % tension open) | HANDOFF.md; `L/fpsdiag1018/FINDINGS.md` 2.1 |
| 8 | TLB/texture-dirty walk cost | all four | 0.3-0.6 % of render-thread CPU (this capture); 0.4-2 % earlier | 4+4 captures | falsified | HANDOFF.md; `L/fpsdiag1018/FINDINGS.md` 2.2 |
| 9 | ART GC pause | all four | 0 GC lines | 167 + this capture's dip windows | falsified | HANDOFF.md; `L/fpsdiag1018/FINDINGS.md` 2.8 |
| 10 | Fin/Fen fence wait = #796 queue depth | GTA III | parked G/Fin 48.1/14.7 ... 33.2/3.3; in car fen 15.57 = rotfen 11.03 + stale 4.00; c1-A1 Fen 13.6 vs 2.5 | within-arm windows | correlate supported; mechanism not isolated; never A/B'd | `L/gta3dip1018/FINDINGS.md` 1.5; `L/gta3car1018/NOTES.md` 4.1 |
| 10a | Fen queue depth | Fable | 1.4 vs 0.1 ms (owner-play-1018c) | 56/57 windows | refuted | `L/fpsdiag1018/FINDINGS.md` 4 |
| 10b | RalliSport 2 Fin split | RalliSport 2 | Fen 0.1-0.5 flat; Fin 11-26 ms "almost all Sub" | 36 phase lines | Sub, not Fen | ralli `FINDINGS.md` "New telemetry" |
| 11 | `hakuX-rpbrk` / `RPBreaks:` per-window breakdown | GTA III | two tids write it; ~4900 <-> ~9500 | -- | instrument racy; replaced by `[dipwin]` | `L/gta3dip1018/FINDINGS.md` 1.3; instr 1.1 |
| 12 | `[dipwin]` pass attribution, in car | GTA III | 151.65 rp/flip, 141.43 `bnd` copy_surface_to_texture; ms/flip = 30.89 + 0.1309 x rp (r^2 0.66) | 46 windows | measured: feedback-loop copy per draw | `L/gta3car1018/NOTES.md` 4.1 |
| 13 | `HAKUX_S2T_FB=1/2` (texture.c) | GTA III in car | O1 24.8 fps / 57.11 rp; F1 26.8 / 20.15; S1 27.9 / 38.20; F2 22.6 / 33.67 | one run per value, not a palindrome | cuts passes; fps confounded; 30 not reached | `L/gta3car1018/NOTES.md` 6 |
| 14 | Page-granular stale vertex copy (vtxstale1018) | GTA III | selftest bytes 891.6 M -> 118.5 M; in car stale ~4 ms | selftest only | not device-measured | `L/fpsdiag1018/NOTES.md` 0 |
| 15 | Vertex hazards (~0.3/flip), pgraph.lock (lw 0), compile <= 2 ms, guest 23.3 ms | GTA III pilot 343857 | as written | one pilot | ruled out there | `L/gta3fps1017/NOTES.md` 0 |
| 16 | redo/shc volume | Fable, Blinx 2 | Fable redo/dirty 2.0-2.8x flat; Blinx 2 3.16 -> 4.87 | counts only | cost never timed | `L/fabledip1018/FINDINGS.md` 1 |
| 17 | Df "deferred flushes" | all | VBLANK-governor retry count | code read | downstream metric, not a lever | `L/gta3dip1018/FINDINGS.md` 1.2 |
| 18 | RalliSport 2 audio (`vp.c` direct read, `HAKUX_APU_PRIO`, `prod:` model) | RalliSport 2 | starve 0.000153; fps_ok 0.8618 | pilot + 2 bar runs | audio fixed; fps not | ralli `FINDINGS.md` Status |
| 19 | RalliSport 2 fps cliff ~59 -> 25-50 at 180-240 s | RalliSport 2 | 59.0 (0-150 s) -> 38.3 (240 s) | 4 runs, prio on/off | not the audio change; thermal/sustained load suspected, handed off | ralli `NOTES.md` attempts 14-15 |
| 20 | Faster clock / governor / perf mode / sysmem | any | -- | -- | forbidden (owner) | memory `investigate-the-wait-not-the-clock` |
| 21 | Scripted gameplay navigation (6 GTA routes) | GTA III | all VOID | -- | do not repeat | `L/gta3fps1017/NOTES.md` 0 |

Correction carried from the research pass: `L/fpsdiag1018/FINDINGS.md` 2 item 4 credits "R3 -0.9 fps"; README gives
-0.3 (b2) and -0.9 (b4) both to R2 vs R1, and R3 no fps number (dup 0, inert).

Proposed by prior lanes, never built or never A/B'd (candidates for this lane only with what is different stated):
#796 deferred-finish queue depth (draw.c RCMD_FINISH path); the PRESENTING finish (display.c `render_display`);
deferred surface download ending passes (surface.c `download_surface_record_deferred`); in-pass feedback-loop layout;
the c4/c5/c6/c8 OS candidates (sampler never run). **No prior lane looked at `Sub` (RalliSport 2 / Fable) or at
`dfF` / the Surf phase (Blinx 2).**
