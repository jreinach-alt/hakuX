# lane.idlehaltdefault (#525): should the idle halt default on?

The idle halt (`HAKUX_IDLE_HALT=1`, #528) is opt-in because leg L failed:
the pg callback's p99 raise-to-run is 100-200 us, against a 50 us bound. L
measures the mechanism. This lane measures what a player sees (fps, frame
pacing, audio), with J/frame beside it, on six Nova titles where a slow
pgraph wake is most likely to show.

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
