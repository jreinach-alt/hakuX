# lane.idlehaltdefault (#525): should the idle halt default on?

The idle halt (`HAKUX_IDLE_HALT=1`, #528) is opt-in because leg L failed:
the pg callback's p99 raise-to-run is 100-200 us, against a 50 us bound. L
measures the mechanism. This lane measures what a player sees (fps, frame
pacing, audio), with J/frame beside it, on six Nova titles where a slow
pgraph wake is most likely to show.

## Verdict (2026-09-29)

**The halt stays opt-in for now. This PR does not propose the flip, and it
found no cost a player sees.** Neither branch of the brief's "done when" is
met:

- **Default-on needs H, P and A on every title, and E. Not met.** As
  registered, H fails pooled on Fuzion (-6.0 fps of 2.5) and DOA1U (-5.4 of
  4.0), A fails on DOA1U's first pair, E fails (2 of 5 first pairs), and
  Forza has no scored run.
- **Opt-in needs a title that fails H or P on both of its pairs. Not met.**
  No title does. Fuzion and DOA1U each fail on the first pair and hold on
  the second.

What the 16 scored runs show:

- **Six of the eight pairs hold every leg**: Kabuki, Ghoulies, both Blinx 2
  pairs, Fuzion's second pair and DOA1U's second pair. H is within -1.8 fps
  in all six, lateness is under 0.0012 in every run, and the p99 estimate is
  within 1.06x.
- **The two failing pairs compare different workloads.** Fuzion's first
  pair drew two different stages. DOA1U's first halt-on run spent 134 s in a
  flipless state that the second pair's halt-off run also entered (21 s,
  same idle signature), with the larger audio starve of the two (0.0077
  against 0.0048).
- **The saving is real on Blinx 2 and unproven elsewhere.** Blinx 2:
  J/frame -16% and -14%, net_w -1.41 and -1.17 W, against a same-arm spread
  of 0.13 W. Ghoulies -1.9% and Fuzion's matched pair -1.6% are inside the
  same-arm spread. The saving does not follow the guest's idle share:
  Fuzion's halt-on arm slept 44% of the window and saved 0.04 W.

What would settle it is in "What the next lane needs" at the end.

## Titles (all on the Nova, one copy each; `devices.sh titles nova`, 2026-09-28)

| title | why | route, seconds | window |
|---|---|---|---|
| Kabuki Warriors | 60 fps budget, capped at 60 | kabuki-warriors, 420 | `mark gameplay` (~200 s) to end |
| Fuzion Frenzy | 60 fps budget, asks for every VBLANK | fuzion-frenzy, 420 | `mark gameplay` (~85 s) to end |
| Forza Motorsport | pgraph sync (downloads, #414) | survey, 420 | `mark play` (~200 s) to end |
| Dead or Alive 1 Ultimate | pgraph sync; noisy | survey, 420 | `mark play` to end |
| Blinx 2 | near the 30 bar, capped at 30 | survey, 420 | `mark play` to end |
| Grabbed by the Ghoulies | near the 30 bar, swap interval 2 | ghoulies, 730 | `mark gameplay` (~430 s) to end |

I chose Blinx 2 over Halo: CE. Both are on the Nova, but Halo has never
been soaked on either device and has no route, while Blinx 2 has two Nova
survey runs (29.3 median). The Forza Nova runs used the survey route, so
Forza uses it too.

Controls, cited and not re-run (lane.idlehalt at 40fabbaacc, same judge):

| | AUF off | AUF on | Blinx off | Blinx on |
|---|---|---|---|---|
| result | `1-1790582079-idlehalt-2124199` | `1-1790582078-idlehalt-2124125` | `1-1790582080-idlehalt-2124441` | `-2124356` |
| fps median (60-flip windows) | 19.79 | 20.32 | 21.34 | 23.33 |
| net_w | 7.27 | 6.02 | 8.32 | 6.49 |
| J/frame | 0.365 | 0.298 | 0.434 | 0.327 |
| audio starve | 0 | 0 | 0 | 0 |

## Instrument: `ihd_judge.py`

One window per run: title_verdict's scored window, from the first `mark
gameplay` (or survey's `mark play`) to `soak end`. The judge copies each
result dir into `.copies/`, which is not committed, and runs
`title_verdict.judge()` on the copy. That gives the exact per-60-flip fps
windows, the audio starve share, `net_w` and J/frame. From the same logcat
lines it also reads:
- `hakuX-pace`: the vK counts, and the median per-line `max`, which is the
  frame-time p99 estimator;
- `[pace526]`: held frames, and the share of them more than 1 ms late;
- `[idlehalt]`: the `on` value (the arm check) and the halts.

Check: on the AUF control pair it reproduces lane.idlehalt's J/frame
(0.3651 / 0.2975).

## Bounds: same-arm pairs read before registration

Every bound comes from runs of one arm: same ref, same env, the Nova. The
exceptions are labelled BORROWED. All numbers below come from
`ihd_judge.py --share-at 12,13.5,15,20,25,28.5,57`, over each run's
mark-to-end window.

| title | pair (ref) | fps median | share >= 13.5 | frame-time p99 est. (ms) | audio |
|---|---|---|---|---|---|
| Kabuki | 2277012 / 1078233 (ead1086cb5) | 59.94 (3 windows) / 57.97 | 0.05 / 0.65 | 30.8 / 45.0 | 0 / 0 |
| Kabuki | 1078186 (spin limiter) | 58.03 | | 54.6 | 0 |
| DOA1U | 3225184 / 3121451 (32657e9719) | 16.22 / 16.75 | 0.71 / 1.0 | 68.2 / 65.3 | 0 / 0 |
| DOA1U | 3224848 / 3120192 (35ee65562a) | 14.84 / 13.70 | 1.0 / 0.48 | 70.3 / 77.9 | 0 / 0 |
| DOA1U | 1235330 / 1235784 (16b7e14ec9) | 15.72 / 12.58 | 1.0 / 0.0 | 96.0 / 110.8 | 0 / 0 |
| DOA1U | 1235504 / 1235822 (ef66174066) | 15.47 / 15.87 | 0.89 / 1.0 | 69.2 / 67.9 | 0 / 0 |
| DOA1U | 3151021 / 3151101 (9f80bc887a) | 13.81 / 14.56 | 0.60 / 0.70 | 77.3 / 72.0 | 0 / **0.0031** |
| DOA1U | 3150971 / 3151064 (dffb7a8a66) | 14.23 / 13.13 | 1.0 / 0.32 | 73.8 / 80.5 | 0 / 0 |
| DOA1U | 2188203 / 966037 (61e0edf87c) | 30.41 / 33.08 | 1.0 / 0.92 | 38.2 / 34.0 | 0 / 0 |
| DOA1U | 1078282-r2 / 1078381 (ead1086cb5 spin) | 15.11 / 11.11 | 0.93 / 0.0 | 71.8 / 288.5 | 0 / 0 |
| DOA1U | 1078334-r2 / 1078429 (ead1086cb5 sleep) | 11.12 / 23.92 | 0.0 / 1.0 | 396.1 / 44.7 | 0 / 0 |
| Forza | 1930404 / 1054756 (4b22f2526b) | 26.62 / 28.85 | 1.0 / 1.0 | 47.3 / 43.0 | 0.0011 / 0.0013 |
| Blinx 2 | 690171 (e5db66fa37) / 202197 (e156fcdf02), cross-ref | 29.28 / 29.38 | share >= 28.5: 0.57 / 0.51 | 39.1 / 40.1 | 0 / 0 |
| Fuzion | 1059623 (one run) | 30.58 | | 47.6 | 0 |
| Ghoulies | Thor 925659 / 997141 (6bfce4a685) | 7.74 / 29.96 | | 245 / 37 | 0.029 / 0.0034 |

What this set:
- **H is the fps median, not a time share, on every title.** A time share
  moves with scene more than the median does. In DOA1U's nine pairs the
  share at 13.5 fps spread by 0.08-1.0, while the median spread by 0.4-4.0
  fps in eight pairs. At the title's own 60 target, or at 28.5, the share is
  0 in most DOA1U runs, so a leg on it could not fail. On Kabuki one 60-flip
  window lasting 62.6 s held 83% of a run's time.
- **H bounds:** Kabuki 2.0, Fuzion 2.5 (BORROWED: Forza's 8%), Forza 2.3,
  DOA1U 4.0, Blinx 2 and Ghoulies 1.0, plus a 0.10 share at 28.5 fps
  (BORROWED: Kabuki's 3.3% of a cap).
- **P1** (`[pace526]`, held frames more than 1 ms late): B <= A + 0.002,
  from lane.pacing's sleep-limiter runs (0.0008 pooled). It is judged only
  where both arms hold >= 1000 frames. Otherwise it is BLIND.
- **P2** (frame-time p99 estimate): B <= 1.5 x A. Kabuki's pair spread 46%,
  and 7 of 9 DOA1U pairs spread <= 20%.
- **A:** B <= 0.001, or B <= A + 0.0031 when A is over 0.001 itself.
- **E:** B's J/frame is below A's in >= 4 of 6.

The full text of each leg, and the world each fails in, is in
`docs/testing/predictions/idlehaltdefault-*.json` (`mkpred.py` wrote them).

## Registered (2026-09-28, before any run)

Refs: a = b = `3a5d79e3ea` (origin/master; the halt is opt-in, spin 0). B
adds `--env HAKUX_IDLE_HALT=1`.

| file | sha256 |
|---|---|
| idlehaltdefault-kabuki.json | 4aed0c9ec35ed344e45f3ab91111b65224440b9da4603ce28639c1fb47b77f2b |
| idlehaltdefault-fuzion.json | 6b2117ed59987b02b7604f1ed1d921f2af5db340a4b2042796b55f36f3676719 |
| idlehaltdefault-forza.json | aaba486674bf7762984068574e1c22d83af3d9003b3dad4e97763981cff222a7 |
| idlehaltdefault-doa1u.json | 3a846565755ec867118251755a03943df157408a40194f7aeabb031514656085 |
| idlehaltdefault-blinx2.json | 73b1b5516de615f5b1a415bf60ba260393199e164a3752f45c0b24497f96370d |
| idlehaltdefault-ghoulies.json | 9124470f502dc6c63917ed3d893c7c61282f3d270e38608dd54d7f0fdc9465a0 |

Order: Kabuki A B, Fuzion B A, Forza A B, DOA1U B A, Blinx 2 A B,
Ghoulies B A. The leading arm alternates by title, so the Nova's thermal
drift falls on both arms. The brief's "A B A B" would have put B second in
every title.

## Pilot and queue

The whole batch is about 112 min of device time: 5 pairs x 2 x (420 + 90) s,
plus 2 x (730 + 90) s. So the pilot is the Kabuki pair (17 min). Once it is
read, `pilots/lane.idlehaltdefault.ok` goes in and the other ten are queued.

Queued at `1-` (release) priority, pinned to the Nova, at ref 3a5d79e3ea (no
cached build yet, so the first claim builds it):
- Kabuki A1 (off): `1-1790618696-lane.idlehaltdefault-845673`
- Kabuki B1 (on): `1-1790618748-lane.idlehaltdefault-846115`

async413's DOA1U request `1-1790618748-async413-847565` sorts between them.
That costs the pair about 9 min of drift. It does not change the arms.

Preflight on 68be6fd1fc passes everything except `territory`. That failure
is on the board's `territory.toml` (origin/board: `xemu_android.cpp` is
claimed by both rendermode474 and async413), which is not this lane's
file.

## Session 1 end (2026-09-28 ~11:45 PDT): waiting

Waiting on the two pilot request ids above.

On resume:
1. Run `python3 docs/lanes/idlehaltdefault/ihd_judge.py --a
   1-1790618696-lane.idlehaltdefault-845673 --b
   1-1790618748-lane.idlehaltdefault-846115 > <log>`.
2. Check the pilot:
   - V holds (not VOID, a window of >= 120 s, >= 20 windows);
   - `[idlehalt]` reads on=1/0;
   - `[pace526]` held counts are present;
   - power and audio are measured.
3. Write `pilots/lane.idlehaltdefault.ok` with python3.
4. Queue the other ten in this order:
   `bash docs/lanes/idlehaltdefault/queue.sh fuzion B 1`, `fuzion A 1`, `forza A 1`, `forza B 1`,
   `doa1u B 1`, `doa1u A 1`, `blinx2 A 1`, `blinx2 B 1`, `ghoulies B 1`,
   `ghoulies A 1`. Each call is `request.sh --who
   lane.idlehaltdefault --title <T> --route <R> --seconds <S> --perflog
   --device nova --ref 3a5d79e3ea [--env HAKUX_IDLE_HALT=1] --expect
   docs/testing/predictions/idlehaltdefault-<key>.json --issue 525`, run with
   `env HAKUX_RELEASE_PRIO=1`.

## Session 2 (2026-09-28 ~15:45 PDT): pilot read, ten queued

Why session 1 did not finish: it ended correctly, waiting on the two pilot
requests above, which had not run yet. hostops resumed this lane once both
were DONE.

### Pilot reading (Kabuki pair, `ihd_judge.py`)

| | A1 off `-845673` | B1 on `-846115` |
|---|---|---|
| window (mark gameplay to end), s | 204.1 | 199.8 |
| 60-flip windows | 82 | 61 |
| fps median | 58.88 | 58.25 |
| frame-time p99 est. (median `max`), ms | 45.5 | 46.0 |
| `[pace526]` held / late >1 ms | 12009 / 0 | 12014 / 2 (0.00017) |
| audio starve | 0 | 0 |
| net_w | 7.952 | 7.565 |
| J/frame | 0.2879 | 0.3969 |
| `[idlehalt]` on / halts | 0 / 0 | 1 / 175980 |
| no-flip gaps (title_verdict `hang_gaps_s`) | 22.1, 61.6, 21.6, 11.3 | 118.2, 17.6 |

The pilot meets its purpose: both arms reach `mark gameplay`, both arms
have the fps, pace, audio, power and idlehalt lines, and the arm check reads
right. So `pilots/lane.idlehaltdefault.ok` was written and the other ten
were queued.

**Finding: on this route, J/frame is set by screen time, not by the halt.**
- In both arms, 58-68% of the scored window is a static screen with no
  flips. The perf lines stop and `refresh` keeps ticking at 60 Hz with
  `flip=0`. `[rr425w]` shows the guest idle about 95% at `idlepc=8001b02e`,
  and `[idlehalt] pg` reads 0-1, so the guest is not waiting on pgraph.
  These are round-end, continue or loading screens that follow the fight's
  random outcome.
- lane.pacing's Kabuki run `1078233` has the same kind of gaps (11, 11,
  22 s).
- J/frame divides energy by flips, so the arm that happens to spend longer
  on a static screen reads worse. B's J/frame is 38% higher, while its
  net_w is 4.9% lower.
- Fuzion `1059623` and DOA1U `3225184` also carry `hang` gaps on their
  routes. Their J/frame will be confounded the same way.

The registered E leg reads J/frame, and it stays as registered: it is not
edited after the data. Beside it, the table will carry net_w and the no-flip
seconds of each run, labelled post-pilot and descriptive. If E fails only
on titles whose arms differ in no-flip time, that is reported as the
instrument, not as the halt.

H, P1, P2 and A on the Kabuki pair all read inside their bounds. The
formal verdict comes with the batch.

### Queued (release prio `1-`, Nova, ref 3a5d79e3ea, 15:45 PDT)

| title | first | second |
|---|---|---|
| Fuzion | B1 `1-1790634702-lane.idlehaltdefault-3051928` | A1 `1-1790634702-lane.idlehaltdefault-3052286` |
| Forza | A1 `1-1790634702-lane.idlehaltdefault-3052521` | B1 `1-1790634703-lane.idlehaltdefault-3052915` |
| DOA1U | B1 `1-1790634703-lane.idlehaltdefault-3053271` | A1 `1-1790634703-lane.idlehaltdefault-3053613` |
| Blinx 2 | A1 `1-1790634703-lane.idlehaltdefault-3053911` | B1 `1-1790634704-lane.idlehaltdefault-3054293` |
| Ghoulies | B1 `1-1790634704-lane.idlehaltdefault-3054732` | A1 `1-1790634704-lane.idlehaltdefault-3055105` |

The device pin, env, ref and seconds were read back from each `.req`.

On resume, run `ihd_judge.py` over all twelve (`--a` the six A ids, `--b`
the six B ids), with `hang_gaps_s` read beside it. Then fill the per-title
table, judge the six predictions, and decide whether a second pair is
needed (only for a title whose leg fails or sits inside the bound).

## Session 3 (2026-09-28 ~20:40 PDT): first pairs read, three second pairs queued

Why session 2 did not finish: it ended correctly after queueing the ten
runs, waiting on those request ids. hostops resumed this lane once none was
queued or running.

### First pairs (`ihd_judge.py --share-at 13.5,28.5,57`, mark to end)

Full output: `.lane-scratch/batch.log` (not committed). Blinx 2 A1 is
`-3053911-r1`: the first `-3053911` is VOID (the Nova's adb link dropped at
225 s, hostops).

| title | arm | result | fps median | share >= 28.5 | late >1 ms (held) | p99 est. ms | audio | net_w | J/frame | no-flip s (>8 s gaps) |
|---|---|---|---|---|---|---|---|---|---|---|
| Kabuki | A | `1-1790618696-...-845673` | 58.88 | 0.46 | 0 / 12009 | 45.5 | 0 | 7.952 | 0.2879 | 117 (4 gaps) |
| Kabuki | B | `1-1790618748-...-846115` | 58.25 | 0.32 | 0.00017 | 46.0 | 0 | 7.565 | 0.3969 | 136 (2 gaps) |
| Fuzion | A | `0-0-x-1-1790634702-...-3052286` | 49.10 | 0.81 | 0.00035 | 36.7 | 0 | 8.511 | 0.1997 | 0 |
| Fuzion | B | `0-0-x-1-1790634702-...-3051928` | 38.89 | 0.57 | 0.00112 | 37.5 | 0 | 7.235 | 0.2193 | 0 |
| Forza | A | `0-0-x-1-1790634702-...-3052521` | VOID | | | | | | | |
| Forza | B | `0-0-x-1-1790634703-...-3052915` | VOID | | | | | | | |
| DOA1U | A | `0-0-x-1-1790634703-...-3053613` | 26.49 | 0.19 | 0 / 5503 | 65.4 | 0.00026 | 5.838 | 0.2681 | 8 |
| DOA1U | B | `0-0-x-1-1790634703-...-3053271` | 15.18 | 0.00 | 0 / 8072 | 144.0 | **0.00481** | 6.539 | 1.0481 | 134 |
| Blinx 2 | A | `0-0-x-1-1790634703-...-3053911-r1` | 29.93 | 0.62 | 0.00088 | 37.7 | 0 | 8.321 | 0.2889 | 0 |
| Blinx 2 | B | `0-0-x-1-1790634704-...-3054293` | 29.23 | 0.58 | 0.00009 | 38.8 | 0 | 6.914 | 0.2430 | 0 |
| Ghoulies | A | `0-0-x-1-1790634704-...-3055105` | 29.96 | 0.72 | 0.00044 | 37.7 | 0.00035 | 8.164 | 0.2962 | 0 |
| Ghoulies | B | `0-0-x-1-1790634704-...-3054732` | 29.96 | 0.67 | 0 | 39.2 | 0.00088 | 7.889 | 0.2907 | 0 |

Every B run reads `[idlehalt] on=1` with halts > 0. Every A run reads on=0.
All twelve use apk 9ab5709037ca.

Legs on the first pairs, as registered:

| title | H | P1 | P2 | A | 2nd pair? |
|---|---|---|---|---|---|
| Kabuki | holds (-0.63 of 2.0) | holds | holds (1.01x) | holds | no |
| Fuzion | **fails** (-10.2 of 2.5) | holds (+0.0008) | holds (1.02x) | holds | yes |
| Forza | VOID | | | | not at this ref |
| DOA1U | **fails** (-11.3 of 4.0) | holds | **fails** (2.2x) | **fails** (0.0048) | yes |
| Blinx 2 | holds (-0.70 of 1.0; share -0.04 of 0.10) | holds | holds | holds | yes: B is worse than half the H bound |
| Ghoulies | holds (0.00) | holds | holds (1.04x) | holds | no |

E (B's J/frame below A's): Blinx 2 and Ghoulies, 2 of 5 scored titles. **E
fails as registered.** net_w is lower with the halt in 4 of 5 (Kabuki -0.39,
Fuzion -1.28, Blinx 2 -1.41, Ghoulies -0.28 W; DOA1U +0.70 W). The failures
are the three titles whose arms played different scenes (below). J/frame
divides by flips, so it follows the scene.

### What the three failures are

**Fuzion: the arms played different minigame stages.** The route mashes A,
and the game picks the stage itself. A (`-3052286`) drew "Stage 1 -
Downtown": a rhythm game at 49 fps and fireworks at 41 (route-frames
184554, 184704). B (`-3051928`) drew "Stage 1 - Outlands": a bomb arena at
19 fps and a hoverbike game at 27 (183723, 183832). Per 20 s bin, A sits at
45-57 fps from 140 to 260 s while B sits at 21-36. The H failure is a
comparison of two different workloads. It says nothing about the halt either
way.

**DOA1U: B spent 134 s of 178 in a flipless state that A spent 8 s in.**
- B fought Helena and fell through the floor. The frame reads "FPS: 1"
  (190318-play). A fought Gen Fu at the clock face and reached GAME OVER.
- In B's flipless stretch, `[rr425w]` reads the guest ~85% idle at
  `idlepc=8001b02e` (about 1.7 s idle, 0.3 s busy per 2 s), and `[idlehalt]`
  reads `pg=0`, `lpgmax=0`. **The guest is not waiting on pgraph**, which
  is the only wake leg L measured as slow.
- **The same state occurs with the halt off**, with the same numbers.
  lane.pacing's `1-1790575939-lane.pacing-1078334-r2` (41.8 s) and
  `-1078381` (19.3 s) read ~1.69 s idle and 0.3 s busy per 2 s, at the same
  idlepc. Of 18 earlier halt-off DOA1U runs, 5 have such stretches.
- So the state is DOA1U's own. Whether the halt makes it longer or more
  frequent is what the second pair is for. The audio starve (0.0048) and the
  p99 (144 ms) both fall inside B's flipless stretches.
- A is itself high for this title: 26.49 fps against 11-17 in 16 of 18
  earlier halt-off Nova runs.

**Forza: both arms died before `mark play`.** lmkd killed xemu at 4.4 GB PSS,
at 218 s and 212 s: the #414 Forza memory growth on master, which PR #583
fixes (hostops, #525). Neither arm has a scored window. A re-queue at
3a5d79e3ea would die the same way, so Forza is not measurable at this ref.
It needs a pair on master after #583 folds.

### Second pairs (queued 20:4x PDT, release prio, Nova, 3a5d79e3ea)

| title | first | second |
|---|---|---|
| Fuzion | A2 `1-1790651074-lane.idlehaltdefault-2875039` | B2 `1-1790651074-lane.idlehaltdefault-2875118` |
| DOA1U | A2 `1-1790651074-lane.idlehaltdefault-2875201` | B2 `1-1790651074-lane.idlehaltdefault-2875292` |
| Blinx 2 | B2 `1-1790651075-lane.idlehaltdefault-2875391` | A2 `1-1790651075-lane.idlehaltdefault-2875478` |

Deviation from the registration's "same order": each second pair leads with
the other arm, so each arm leads once per title. H is then scored pooled, as
registered: the mean of the two medians per arm.

Do not repeat: a single pair on Fuzion or on the survey route's DOA1U cannot
answer an A/B question. The scene is chosen by the game, not the route, and
it moves fps by 2x. Read the route-frames before reading a leg.

On resume: run `ihd_judge.py` with `--a` set to the A2 ids and `--b` set to
the B2 ids. Pool them with the first pairs. Read route-frames for scene
match. Then judge the verdict. Helpers used this session (uncommitted):
`.lane-scratch/timeline.py` (fps per 20 s bin), `gaps.py` (flipless
stretches), `grepres.py`.

## Session 4 (2026-09-29): second pairs read, verdict

Why session 3 did not finish: it ended correctly after queueing the three
second pairs, waiting on those six request ids. They finished overnight and
job.handback resumed this lane. origin/master is merged in (no rebase); the
registered refs are unchanged.

### Second pairs (`ihd_judge.py --share-at 13.5,28.5,57`, mark to end)

hostops promoted the six to the Nova's head, so each result is under
`0-0-x-<id>`. All six pass V: on the Nova, apk 9ab5709037ca, a window of
194-338 s, 61-213 fps windows, audio and power measured, `[idlehalt]` on=1
with halts > 0 in every B and on=0 in every A.

| title | arm | fps median | share >= 28.5 | late >1 ms / held | p99 est. ms | audio | net_w | J/frame | no-flip s |
|---|---|---|---|---|---|---|---|---|---|
| Fuzion | A2 | 48.19 | 0.72 | 3 / 20421 (0.00015) | 35.8 | 0 | 7.785 | 0.2076 | 9 |
| Fuzion | B2 | 46.40 | 0.72 | 6 / 20421 (0.00029) | 37.8 | 0 | 7.746 | 0.2043 | 18 |
| DOA1U | A2 | 25.77 | 0.12 | 1 / 5503 (0.00018) | 71.7 | **0.00766** | 7.485 | 0.3978 | 32 |
| DOA1U | B2 | 26.22 | 0.15 | 0 / 4877 | 69.3 | 0 | 7.227 | 0.3209 | 0 |
| Blinx 2 | A2 | 29.85 | 0.60 | 5 / 12009 (0.00042) | 37.6 | 0 | 8.214 | 0.2842 | 0 |
| Blinx 2 | B2 | 29.87 | 0.59 | 1 / 12011 (0.00008) | 38.0 | 0 | 7.044 | 0.2448 | 0 |

Scene match, from the route-frames and the fps per 20 s bin:
- **Fuzion: matched.** Both arms drew the Downtown arena first (A2
  213254, B2 020403), and the bins track each other from the mark to the
  end (A2 24 24 30 39 42 51 48 48 57 54 24 21 24 27 57; B2 27 21 33 30 45
  45 48 51 51 48 27 21 24 39 48).
- **Blinx 2: matched.** Flat at 27-30 in every bin of both arms, as in the
  first pair.
- **DOA1U: not matched, and it cannot be on this route.** The fighters and
  stages differ in every run. A2 has two flipless stretches (20.9 s and
  11.1 s); B2 has none.

One difference in timing: Fuzion A2 ran at 21:30 PDT and B2 at 02:02, 4.5
hours apart, because the Nova charged in between. Both started at 45%
battery with the same USB input (2.12 W). The other pairs ran 7 minutes
apart.

### Every scored run, with its result dir

All dirs are under `dispatch/results/`. `<L>` is `lane.idlehaltdefault`.
Idle share is the guest's (`[rr425w]` idle over idle + busy), from
`ihd_idle.py`.

| title | arm | result dir | window s | fps median | late >1 ms share | p99 est. ms | audio | net_w | J/frame | idle share | no-flip s |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Kabuki | A1 | `1-1790618696-<L>-845673` | 204 | 58.88 | 0 | 45.5 | 0 | 7.952 | 0.2879 | 0.46 | 117 |
| Kabuki | B1 | `1-1790618748-<L>-846115` | 200 | 58.25 | 0.00017 | 46.0 | 0 | 7.565 | 0.3969 | 0.63 | 136 |
| Fuzion | A1 | `0-0-x-1-1790634702-<L>-3052286` | 331 | 49.10 | 0.00035 | 36.7 | 0 | 8.511 | 0.1997 | 0.46 | 0 |
| Fuzion | B1 | `0-0-x-1-1790634702-<L>-3051928` | 330 | 38.89 | 0.00112 | 37.5 | 0 | 7.235 | 0.2193 | 0.50 | 10 |
| Fuzion | A2 | `0-0-x-1-1790651074-<L>-2875039` | 337 | 48.19 | 0.00015 | 35.8 | 0 | 7.785 | 0.2076 | 0.48 | 9 |
| Fuzion | B2 | `0-0-x-1-1790651074-<L>-2875118` | 338 | 46.40 | 0.00029 | 37.8 | 0 | 7.746 | 0.2043 | 0.44 | 18 |
| Forza | A1 | `0-0-x-1-1790634702-<L>-3052521` | VOID | | | | | | | | |
| Forza | B1 | `0-0-x-1-1790634703-<L>-3052915` | VOID | | | | | | | | |
| DOA1U | A1 | `0-0-x-1-1790634703-<L>-3053613` | 176 | 26.49 | 0 | 65.4 | 0.00026 | 5.838 | 0.2681 | 0.16 | 8 |
| DOA1U | B1 | `0-0-x-1-1790634703-<L>-3053271` | 178 | 15.18 | 0 | 144.0 | 0.00481 | 6.539 | 1.0481 | 0.51 | 134 |
| DOA1U | A2 | `0-0-x-1-1790651074-<L>-2875201` | 200 | 25.77 | 0.00018 | 71.7 | 0.00766 | 7.485 | 0.3978 | 0.23 | 32 |
| DOA1U | B2 | `0-0-x-1-1790651074-<L>-2875292` | 194 | 26.22 | 0 | 69.3 | 0 | 7.227 | 0.3209 | 0.11 | 0 |
| Blinx 2 | A1 | `0-0-x-1-1790634703-<L>-3053911-r1` | 189 | 29.93 | 0.00088 | 37.7 | 0 | 8.321 | 0.2889 | 0.65 | 0 |
| Blinx 2 | B1 | `0-0-x-1-1790634704-<L>-3054293` | 193 | 29.23 | 0.00009 | 38.8 | 0 | 6.914 | 0.2430 | 0.58 | 0 |
| Blinx 2 | A2 | `0-0-x-1-1790651075-<L>-2875478` | 204 | 29.85 | 0.00042 | 37.6 | 0 | 8.214 | 0.2842 | 0.66 | 0 |
| Blinx 2 | B2 | `0-0-x-1-1790651075-<L>-2875391` | 207 | 29.87 | 0.00008 | 38.0 | 0 | 7.044 | 0.2448 | 0.58 | 0 |
| Ghoulies | A1 | `0-0-x-1-1790634704-<L>-3055105` | 236 | 29.96 | 0.00044 | 37.7 | 0.00035 | 8.164 | 0.2962 | 0.11 | 0 |
| Ghoulies | B1 | `0-0-x-1-1790634704-<L>-3054732` | 235 | 29.96 | 0 | 39.2 | 0.00088 | 7.889 | 0.2907 | 0.08 | 0 |

VOID, not scored: Blinx 2 `0-0-x-1-1790634703-<L>-3053911` (adb link
dropped at 225 s), and both Forza runs (lmkd kill before `mark play`).

### Legs, as registered

H on the two-pair titles is pooled: the mean of the two medians per arm. P
is read on each pair.

| title | H | P1 | P2 | A |
|---|---|---|---|---|
| Kabuki | holds: -0.63 of 2.0 | holds: +0.00017 | holds: 1.01x | holds |
| Fuzion | **fails pooled**: 42.65 vs 48.65, -6.00 of 2.5. Pair 1 -10.21, pair 2 -1.79 | holds: +0.00077, +0.00014 | holds: 1.02x, 1.06x | holds |
| Forza | VOID | | | |
| DOA1U | **fails pooled**: 20.70 vs 26.13, -5.43 of 4.0. Pair 1 -11.31, pair 2 +0.45 | holds: 0, -0.00018 | **fails pair 1** (2.20x), holds pair 2 (0.97x) | **fails pair 1** (B 0.0048), holds pair 2 (B 0, A 0.0077) |
| Blinx 2 | holds pooled: 29.55 vs 29.89, -0.34 of 1.0; share 0.585 vs 0.610, -0.026 of 0.10 | holds: -0.00079, -0.00034 | holds: 1.03x, 1.01x | holds |
| Ghoulies | holds: 0.00 of 1.0; share -0.054 of 0.10 | holds: -0.00044 | holds: 1.04x | holds |

**E fails as registered**: on the first pairs, B's J/frame is below A's in
2 of 5 scored titles (Blinx 2, Ghoulies), and the leg needed 4 of 6.

J/frame and net_w, B against A, on every pair:

| pair | J/frame | net_w | same scene? |
|---|---|---|---|
| Kabuki 1 | +37.9% | -0.39 W (-4.9%) | no: 117 s against 136 s of static screen |
| Fuzion 1 | +9.8% | -1.28 W | no: different stages |
| Fuzion 2 | -1.6% | -0.04 W (-0.5%) | yes |
| DOA1U 1 | +291% | +0.70 W | no: B flipless for 134 s |
| DOA1U 2 | -19.3% | -0.26 W (-3.4%) | no: A flipless for 32 s |
| Blinx 2 1 | -15.9% | -1.41 W (-16.9%) | yes |
| Blinx 2 2 | -13.9% | -1.17 W (-14.2%) | yes |
| Ghoulies 1 | -1.9% | -0.28 W (-3.4%) | yes |

Same-arm spread of net_w, from the titles with two pairs: Blinx 2 0.11 W
(A) and 0.13 W (B); Fuzion 0.73 W (A) and 0.51 W (B), across two stages;
DOA1U 1.65 W (A) and 0.69 W (B). So only Blinx 2's saving is outside the
spread of its own arm. Ghoulies and Kabuki have one run per arm, and their
differences (0.28 and 0.39 W) are smaller than the Fuzion and DOA1U spreads.

### What the second pairs changed

**Fuzion's H failure was the stage.** With both arms on the same stage, B
is 1.79 fps below A, inside the 2.5 bound. That is still more than half the
bound, and the bound is borrowed from Forza, so Fuzion is "holds, not
tight".

**DOA1U's flipless state belongs to the title, not to the halt.**
- A2 (halt off) entered it for 20.9 s at 139 s after the mark. `[rr425w]`
  reads 1.67-1.72 s idle and 0.28-0.33 s busy per 2 s, at
  `idlepc=8001b02e`, with `pg=0`. B1's stretches and lane.pacing's halt-off
  runs read about 1.7 s and 0.3 s at the same idlepc.
- It carries the audio starve with it. A2 reads 0.0077 with the halt off,
  which is over the verdict's 0.001 and over B1's 0.0048.
- Counting runs with a flipless stretch over 8 s: halt on 1 of 2, halt off
  2 of 2 here (8 s, 32 s) and 5 of 18 before. Four runs cannot say whether
  the halt changes how often the title enters the state or how long it
  stays.

**The saving does not follow the guest's idle share.** I checked this
because it would have explained E. It does not hold. Fuzion's B2 slept 44%
of the window and saved 0.04 W. Blinx 2's B arms slept 57-58% and saved
1.2-1.4 W. Ghoulies slept 8% and saved 0.28 W. What separates Blinx 2 from
Fuzion is not measured here.

### What the next lane needs

1. **Forza, after PR #583 folds.** It is one of the two pgraph-sync titles
   and it has no scored run. At 3a5d79e3ea lmkd kills it at about 215 s.
   #583 was still a draft on 2026-09-29.
2. **A scene gate, registered before the run.** On Fuzion, Kabuki and the
   survey route's DOA1U the game chooses what is on screen, and that moves
   fps by up to 2x and J/frame by up to 4x. A pair should count only when
   both arms' route-frames show the same stage and their no-flip seconds
   agree; otherwise it is re-queued, not scored.
3. **An energy leg on net_w, with J/frame beside it.** J/frame divides by
   flips, so a static screen reads as a worse frame. net_w needs a same-arm
   spread per title before it can carry a bound: DOA1U's is 1.65 W.
4. **DOA1U's flipless state is its own question.** It starves audio with
   the halt off (A2, 0.0077). It needs a rate over more runs than four
   before anything is said about the halt and it.

Do not repeat:
- Do not read J/frame across arms without reading the no-flip seconds.
- Do not pool a median across pairs whose scenes differ. The pooled H
  failures above are one confounded run each, averaged in.
- Do not explain the saving by the idle share. It was tested above and it
  does not fit Fuzion.

Helpers: `ihd_judge.py` (every leg), `ihd_idle.py` (idle share and no-flip
seconds). The judge's logs and the fps-per-bin script are in
`.lane-scratch/`, which is not committed.
