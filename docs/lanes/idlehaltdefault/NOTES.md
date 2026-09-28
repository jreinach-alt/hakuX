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
