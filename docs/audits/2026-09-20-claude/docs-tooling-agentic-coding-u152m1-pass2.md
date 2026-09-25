# Audit pass 2 — PR #181, `claude/docs-tooling-agentic-coding-u152m1`

*nv2a/gl: a texture the surface blit filled is not the VRAM it was hashed from
(#60), and two falsified X1A7 read-side addresses*

- **Auditor:** `job.cloud`, 2026-09-20, pass 2 (remediation verification)
- **Pass 1:** `docs/audits/2026-09-20-claude/docs-tooling-agentic-coding-u152m1-pass1.md`
  (`8e0e32bf`) — 1 HIGH, 1 MEDIUM, 4 LOW
- **Head at audit:** `682f4aa8a1`, CI `build`/`build`/`check` all SUCCESS
- **Remediation read:** `74296a38` (predictions), `fae800a8` + `682f4aa8`
  (disposition and re-check, `docs/lanes/remote/NOTES.md`)
- **Verdict:** clean → `fold-ready`. One thing this does not discharge is
  named at the end, and it is not a finding against the diff.

---

## How this pass was run

Pass 1 said, in its own words, that reading the file and finding a stronger
sentence in the prose is not verification. So the gate was **executed**, not
read: `arms.sh list` against an isolated object store and an isolated
`$HAKUX_WORK`, with the remediated head *and* the head pass 1 read present as
two lane refs in the same tick, so the mutant and the positive are one run and
one output.

```
git clone --bare --shared <repo> scratch/repo && git -C scratch/repo remote remove origin
git -C scratch/repo update-ref refs/remotes/origin/lane/pr181  682f4aa8   # remediated
git -C scratch/repo update-ref refs/remotes/origin/lane/mutant 516e96a8   # what pass 1 read
HAKUX_WORK=scratch/work HAKUX_REPO_DIR=scratch/repo DISPATCH_DIR=scratch/dispatch \
    docs/testing/jobs/arms.sh list
```

Verbatim, the four rows that matter, from one tick:

```
WOULD QUEUE e988be896f6d… lane/mutant:…/2026-09-20-gl-stale-surface-blit-opengl.json  a=01047cf3 b=da9e02a2
WOULD QUEUE 7af3baa38f40… lane/mutant:…/2026-09-20-gl-x1a7-download.json              a=01047cf3 b=5df42da3
WOULD QUEUE cff1e2afb47d… lane/mutant:…/2026-09-20-gl-x1a7-read-side.json             a=01047cf3 b=9e9da01d

  would skip aafb5bf5eee8…: lane/pr181:…/2026-09-20-gl-stale-surface-blit-opengl.json:
      soak predictions (title=desktop OpenGL A/B -- hand-queue only, see the prediction text)
      are hand-read; queue with request.sh --title yourself
  would skip b259b4104da0…: lane/pr181:…/2026-09-20-gl-x1a7-download.json:  (same reason)
  would skip 8bbb18a02078…: lane/pr181:…/2026-09-20-gl-x1a7-read-side.json: (same reason)
```

The mutant reaching `WOULD QUEUE` is what makes the positive mean anything:
the pass-1 scenario is reproduced, in this instrument, on the head pass 1
read, with the suites resolved and the pair proposed. Then the same
instrument, on the remediated head, refuses all three. (The lane's own
`NOTES.md` says its container could not show the `WOULD QUEUE` branch because
`suites_for` found no goldens there. This host has `/home/justin/goldens/
results`, so that half is shown rather than argued.)

**And the host's own job agrees**, which is the check that does not depend on
my scratch at all — three `[job.arms] SKIPPED` comments on this PR at
10:21:58Z, 10:21:59Z and 10:22:01Z, naming exactly `aafb5bf5eee8`,
`b259b4104da0` and `8bbb18a02078` with the same skip line.

---

## Scenario by scenario

### H1 — an arms tick sends the OpenGL prediction to a handheld → **cannot occur**

Pass 1 required either a skip with a reason naming the hand-queue, or
`arms.sh` passing `--device`/`--env` through to `request.sh`. The first was
taken.

| pass 1's step | now |
|---|---|
| `collect()` finds sha256 `e988be896f6d…` | the file's sha is now `aafb5bf5eee8…`; `e988be896f6d` is the pre-marker blob and is judged, so `already_ran` short-circuits it |
| past the watermark | yes — `amended_utc` `2026-09-20T09:49:37Z` |
| `a_ref`/`b_ref` resolve, `b_ref` live | yes, both still true: **the remediation does not work by breaking a ref** |
| queued to the handheld pool | **no.** `arms.sh:653-656` reads `title` with `field()` (a top-level JSON get) and `skip`s. The gate sits *after* `live_ancestor`, so a live `b_ref` does not get past it — checked by ordering in the source and by the mutant falling through it |
| labelled `regressed` a second time on a second spent pair | no second pair. See the note at the end for the pair that was already spent |

The marker is `"title": "desktop OpenGL A/B -- hand-queue only, see the
prediction text"`, and the file's first paragraph now carries the two-arm
`request.sh --device desktop --env HAKUX_RENDERER=OPENGL` recipe rather than a
bolded prohibition. That is the right direction of change: the prohibition was
addressed to a reader the path has none of; the recipe is addressed to the
person who will hand-queue it.

I checked the lane's supporting claim rather than taking it: **nothing else in
the tree reads a prediction's `title`.** The other hits are a GitHub issue
title (`board.sh:119`, `fold.sh:337`) and a *request* record's title
(`request.sh:980`), neither of which is a prediction file. So calling this a
"soak prediction" in the skip line — the lane's own stated inaccuracy — costs
nothing downstream; it is a string in one message.

### M1 — two falsified predictions spend four device arms on reverted code → **cannot occur**

Same marker on both, and the same three-way evidence: the scratch tick skips
`b259b4104da0` and `8bbb18a02078`, the host's job posted the skip for both,
and the `b_ref`s are deliberately left live so the record stays honest about
what is in the branch. Each file's first paragraph now opens with **ALREADY
JUDGED, ON THIS HOST, AND THE CODE IS REVERTED. DO NOT SPEND A DEVICE PAIR ON
IT**, which is the part a person re-reading the file in a month needs.

Four arms of handheld time are not spent. That was the whole of M1.

### L1 — no `roles/lane.md` header on the PR body → **fixed**

The body now opens with the fenced `Lane: / Base: / Files: / Prediction: /
Needs device: / Needs NDK:` block. `Files:` lists eight paths;
`git diff --stat origin/master...HEAD` at `682f4aa8` is eight files. They
match, including `docs/audits/2026-09-20-claude/…-pass1.md`, which the pass-1
auditor pushed to this branch and which the first correction had missed.
`Prediction: … @ aafb5bf5eee8…` is the amended file's current sha, not the
pre-marker one.

### L2 — `nv2a_index.json` provenance records `/home/user/…` → **accepted, not fixed, with a logged reason**

Still `/home/user/nxdk_pgraph_tests` and `/home/user/pbkitplusplus`;
`tests_commit` still `91a0de45`. A LOW may be declined with a reason
(`AGENTS.md`, the loop's step 3), and the reason given is a measured one, not
a preference: the two lines are the generator's record of its own machine and
have flipped between the two homes across 18 commits touching that string in
this file — I counted them, `git log -S`, and 17 of the 18 predate this
branch. The proposed fix is one line in `nv2a_index.py`, on a shared generated
artefact, and does not belong in a texture-cache PR. **Accepted.**

### L3 — the superseded file's unreachable "uncomfortable outcome" → **acknowledged, no edit**

Correct call. `2026-09-20-gl-stale-surface-blit.json` (`fb6c220892d2…`) is
already judged on this host, and the supersession had already replaced that
leg with a reachable one before pass 1 ran. Editing a judged file to improve a
leg it was not judged on is the shape `AGENTS.md` warns about in the other
direction; leaving it and recording why is right.

### L4 — "cannot be less correct" has one counterexample → **fixed**

The live prediction now ends with a named paragraph: `flush_surfaces()`
(`gl/surface.c:3374`) invalidates with its download commented out (the FIXME
at `:3390`), its caller marks all textures possibly dirty, and under this
change a blit-filled binding is destroyed and re-uploaded from VRAM that was
deliberately never written back. It states the reachability (out of band only)
and states explicitly that the prediction is about this disc's captures and is
**not** a claim about that path. That is the correction L4 asked for — the
universal is no longer asserted.

---

## What this pass does not discharge, and why it is not a finding against the diff

**`#181` carries `regressed`, and the remediation is what freezes it.** This
is in the lane's `NOTES.md` under its own heading, which is why it is a note
here and not a finding: it is disclosed, correctly diagnosed and correctly
escalated.

`fold.sh:675` gates on the label and parses no verdicts — *"the label is the
interface"* (`fold.sh:581`). `arms.sh`'s `label_decide()` keeps, per issue, the
newest registration **that has a verdict on disk**. For `#60` that is
`e988be896f6d` — the pre-marker OpenGL file, whose pair was queued before the
marker landed and judged `FAIL` at 10:22:05Z on 269 byte-identical handheld
captures. The `title` marker that discharges H1 is exactly what stops
`aafb5bf5eee8` ever acquiring a verdict to displace it. So **the fix and the
frozen label are one change**, and no tick can undo it.

Two things follow, and I am recording both rather than acting on either:

- The device pair H1 warned about **was spent**, once, at 10:22Z on the
  pre-remediation head. Nothing in this diff could have un-spent it; what the
  diff buys is that it is the last one.
- Clearing `regressed` is the owner's. `fold.sh:639` is explicit that
  `regression-accepted:<issue>` is theirs — *"A lane must not set it and no job
  sets it"* — and `fold.sh:638` is explicit that removing `regressed` by hand
  clears the label without clearing the regression, and the next tick
  recomputes it. The three ways out are enumerated on #60's side in
  `NOTES.md`, and the durable one is pass 1's own remedy (2): a prediction
  field `arms.sh` passes to `request.sh --device`/`--env`. That is a harness
  change and belongs to whoever owns `arms.sh`.

`fold-ready` here is the **audit's** verdict — every HIGH and MEDIUM is
discharged and every LOW is dispositioned — and not a prediction that the PR
will fold. It will not, until the owner acts on the paragraph above.

---

## Result

No pass-1 scenario can still occur. No new HIGH or MEDIUM found in the
remediation: it touches three prediction files and one notes file, adds no
code, and CI is green on `682f4aa8a1`.

`needs-audit-2` removed, `fold-ready` added.
