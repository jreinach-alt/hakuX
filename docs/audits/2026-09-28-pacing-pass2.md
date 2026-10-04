# Audit pass 2: PR #529 (lane/pacing)

PR: #529, "lane.pacing: sleep the frame limiter, request 60 Hz for the game surface (#526)"
Head verified: 637d39c9a5 (pass 1 audited 29ddd809d1)
Pass 1: `docs/audits/2026-09-28-pacing-pass1.md` (one MEDIUM, three LOW)
Remediation: 637d39c9a5, "make the 60 Hz surface request opt-in". Diff since
the pass-1 head: `SDLSurface.java` (+8/-5), `NOTES.md` (+10/-3), and the
pass-1 file. CI (`build`, both runs) is green on 637d39c9a5.

Verdict: **clean. fold-ready.**

## MEDIUM 1: the shipped `HAKUX_SURFACE_RATE` default -- no longer occurs

Pass-1 scenario: with no `HAKUX_SURFACE_RATE` in `env_vars`, a user on an
unpinned 120 Hz panel gets `setFrameRate(60, FIXED_SOURCE, ALWAYS)`, a
default change the PR says it does not make.

Traced on 637d39c9a5, `requestGameFrameRate`:

- `envPref` returns `null` when no line starts with `HAKUX_SURFACE_RATE=`
  (and on any exception reading the pref).
- The gate is now `if (!"on".equals(how) && !"mode".equals(how)) return;`.
  `"on".equals(null)` and `"mode".equals(null)` are both false, so an unset
  value returns before `holder.getSurface()`; so do `off`, the empty string
  and any other value. No `setFrameRate` call and no
  `preferredDisplayModeId` write is reachable without `=on` or `=mode`.
- The only things still done on the default path are the `[rate526]
  before` log line and the `DisplayListener` registration, both
  observation only, as before.
- `HAKUX_SURFACE_RATE` is read nowhere else in the tree
  (`git grep` outside the lane's docs, predictions and audits: only
  `SDLSurface.java:200,265`).

Code, PR body, NOTES and release note now state the same default:

- Code comment (`SDLSurface.java:200-207`): "unset (or "off", or any other
  value) makes no request, the default".
- PR body: "only when `HAKUX_SURFACE_RATE=on` or `=mode` is set ... Unset
  (or `off`) makes no request, and that is the default", and "Nobody has
  measured the request on an unpinned 120 Hz panel, so it stays opt-in."
- NOTES table row and the open-items line say opt-in / default `off`.
- The release note mentions only the limiter, which is correct: the
  default build makes no surface request, so there is nothing to announce.

The registered display prediction is still coherent. `pacing-display.json`
pins `a_ref = b_ref = ead1086cb5`, the binary on which `b_env: []` selected
the request, so a re-run of that file reproduces the measured arms. The
NOTES (line 176) and PR body say that B on ead1086cb5 is `=on` on this head.
The two limiter predictions and the vsync prediction set the variable
explicitly (`off` / `mode`), so the new gate does not change what they
select.

## LOWs

Not required for pass 2; recorded as still standing so nobody reads them
as done.

- LOW 1 (the `DisplayListener` is never unregistered): unchanged. The
  blast radius is still bounded by `:xemu` being its own process, killed on
  exit.
- LOW 2 (`[pace526]` is always on in release): unchanged. The NOTES table
  says "always on, Android only", so the behaviour is disclosed.
- LOW 3 (the cross-device pixel pair): unchanged, disclosed in the PR body.

## New in the remediation

Nothing. The remediation diff touches one condition, one comment and prose;
no new path, no new failure scenario.
