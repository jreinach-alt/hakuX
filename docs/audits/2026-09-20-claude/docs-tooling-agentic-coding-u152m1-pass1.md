# Audit pass 1 — PR #181, `claude/docs-tooling-agentic-coding-u152m1`

*nv2a/gl: a texture the surface blit filled is not the VRAM it was hashed from
(#60), and two falsified X1A7 read-side addresses*

- **Auditor:** `job.cloud`, 2026-09-20, pass 1 (diff read)
- **Diff read:** `git diff origin/master...HEAD`, 7 files, +401/−11
- **Head at audit:** `516e96a85d`, CI `build`/`build`/`check` all SUCCESS
- **Verdict:** 1 HIGH, 1 MEDIUM, 4 LOW → `needs-remediation`

---

## What the diff is

One code change — `hw/xbox/nv2a/pgraph/gl/texture.c`, +41/−1, of which 36
lines are comment. Four prediction files, a `nv2a_index.json` regeneration,
and 220 lines of `docs/lanes/remote/NOTES.md`.

**The code change is correct and I could not break it.** I checked each of
its load-bearing claims against the tree rather than against the comment:

| claim in the comment | checked |
|---|---|
| `generate_texture()` sets `draw_time` to 0 | `gl/texture.c:1460`, `ret->draw_time = 0` ✔ |
| the s2t branch is `TextureBinding::draw_time`'s only writer | `gl/texture.c:968` is the only assignment to a *binding's* `draw_time`; every other hit in `gl/` is `SurfaceBinding` or `pg->draw_time` ✔ |
| `tex_data_hash` is only computed when `possibly_dirty` is set, so forcing it is load-bearing | `gl/texture.c:942`, `if (!surf_to_tex && possibly_dirty)`; `stale_surface_fill` implies `!surf_to_tex`, so the forced bit is exactly what makes the hash exist for the regenerated binding ✔ |
| the early-reuse path already compares draw_times | `gl/texture.c:757` ✔, and it `continue`s only when `tbind->draw_time == surface->draw_time`, i.e. when the blit *is* current — so the new check is not bypassed in a case it should fire in |

No unbounded regeneration loop: `must_destroy` → `generate_texture()` →
`draw_time == 0`, and with `surf_to_tex` false the s2t branch below cannot
re-set it, so the next draw on the same key reads `stale_surface_fill` false.
One extra hash and one re-upload per transition, as the prediction says.

Correctness of the *replacement* pixels: every surface-eviction path in
`gl/surface.c` calls `pgraph_gl_surface_download_if_dirty()` before
`pgraph_gl_surface_invalidate()` — `:1696`, `:1811`, `:3120` — so VRAM is
current wherever a surface disappears under a live binding. The one exception
is L4 below.

**The findings are in the prediction files, not in the C.** That matters:
this PR's whole subject is a prediction that was judged on an arm that could
not exercise it, and the file written to prevent that recurring cannot
prevent it.

---

## HIGH

### H1 — the superseding prediction's routing requirement is prose, and `arms.sh` reads no prose: the arm it forbids is the arm that will run

`docs/testing/predictions/2026-09-20-gl-stale-surface-blit-opengl.json:5`

The file exists for one sentence, and it is the first one in it:

> **THIS ARM MUST RUN THE OPENGL RENDERER. `--env HAKUX_RENDERER=OPENGL`, on
> the desktop channel. A HANDHELD ARM CANNOT JUDGE IT AND MUST NOT BE SPENT
> ON IT.**

That sentence is inside the `prediction` string. `arms.sh` never opens it.
The queue loop reads exactly these fields from a prediction file —
`registered_utc`, `amended_utc`, `amended_utc_2`, `a_ref`, `b_ref`, `who`,
`issue`, `title`, `runs_per_arm`, and the suites — and builds both arms with

```
request.sh --who … --ref … --suites … --runs … --expect "$path" --purpose …
```

(`docs/testing/jobs/arms.sh:671-675`). No `--device`, no `--env`, and no
field in the schema that could carry either. `request.sh:67` is explicit that
`--device desktop` "names this host's own xemu build, running the OpenGL
renderer, **and it is the only spelling that reaches it**" — so the one
mechanism that could satisfy this file's requirement is a flag nothing in the
path from the file to the device can set.

**Failure scenario, concretely.** Next arms tick: `collect()` finds sha256
`e988be896f6dd14a…` on this PR's head; it is not in `judged/`, `pairs/` or
`skipped/`; `registered_utc` `2026-09-20T09:23:54Z` is past the watermark;
`a_ref 01047cf3` and `b_ref da9e02a2` both resolve and `da9e02a2` is an
ancestor of this branch (verified). It is queued — to the handheld pool, on
the default renderer, exactly as `fb6c220892d2…` was. The 269 captures come
back byte-identical, the six `expect` keys miss, `VERDICT: FAIL`. Then
`label_decide()` groups by issue, `#60`'s newest registration is this file,
so it is the *live* verdict and nothing supersedes it: the PR is labelled
`regressed` a second time, on a second spent device pair, for a change the
arm still cannot see.

This is the same defect the file documents, unchanged. What the supersession
actually fixed was the *prose*; the routing is where it was. The file's own
diagnosis — "the outlet had nothing to route on" — is right, and it remains
true of the replacement.

**Two shapes of remedy exist in the tree today; either discharges this.**

1. Opt out of the automatic queue so the pair is queued by hand on the
   desktop channel. `arms.sh:655` already skips any prediction carrying a
   `title` field — *"hand-read; queue with `request.sh --title` yourself"* —
   and tells the lane once. A file that must not be auto-queued needs some
   such marker, and this is the only one that exists.
2. Give the schema a field `arms.sh` passes through to
   `request.sh --device` / `--env`, so the requirement is machine-read rather
   than asserted. That is a harness change and may not be this lane's to
   make — but then (1) is, and one of them has to be in the diff.

What must **not** happen is the file shipping as written: it guarantees the
failure it was written about, and says so in bold while doing it.

---

## MEDIUM

### M1 — two falsified predictions are committed with live `b_ref`s, so the arms job will spend two more device pairs measuring code this branch reverted

`docs/testing/predictions/2026-09-20-gl-x1a7-read-side.json:7`,
`docs/testing/predictions/2026-09-20-gl-x1a7-download.json`

Both are additions in this diff. Both were falsified by the lane's own
desktop measurement and both have had their code reverted inside this branch
— `9e9da01d` → `aa3648cb`, `5df42da3` → `ad5f43b6`. Neither carries any
marker of that, and there is no field `arms.sh` would read if it did.

The revert does not take the `b_ref` out of reach. I verified all three:

```
git merge-base --is-ancestor 9e9da01d HEAD   → ancestor
git merge-base --is-ancestor 5df42da3 HEAD   → ancestor
```

so `live_ancestor "$b"` (`arms.sh:652`) passes for both. The arm builds the
**`b_ref` commit**, not the tip, so each one builds a tree that still has the
falsified change in it and runs it on a device. Two pairs, four arms, at
roughly ninety minutes each, to re-derive two results this branch's own
`NOTES.md` already states: the read-side uniform moved nothing at all
(96 of 96 X1A7 surface lookups refused at the s2t gate), and the download
rule took `Fmt_X1A7R8G8B8_O1A7R8G8B8` from 16,414 px to 122,552.

Both will be judged FAIL, and two more FAIL records land against `#60` on
disk.

Why MEDIUM and not HIGH: `label_decide()` groups verdicts by issue and only
the newest registration per issue is live, so these two — 07:42:50Z and
08:25:36Z — are superseded for *labelling* purposes by the 09:23:54Z file.
The damage is the device time and the record, not the PR's state. But device
time is the scarcest thing the harness has, and this diff spends four arms of
it on two questions already answered.

---

## LOW

### L1 — the PR body has no `Files:` line, or any of `roles/lane.md`'s template header

`roles/lane.md` requires `Lane: / Base: / Files: / Prediction: … @ <sha256> /
Needs device: / Needs NDK:`, and says the board reads `Files:` "from every
open PR to keep two lanes off one file". The body opens straight into prose.
It does name the file set in its second paragraph, and territory is in fact
clean — `hw/xbox/nv2a/pgraph/gl/texture.c` is `[lane.remote]`'s third entry
on `origin/board:territory.toml` (wave 129) and `#60` is in that row's
`issues` — so nothing is *actually* colliding. It is the definition-of-done
item that is missing, not the safety. LOW rather than MEDIUM because I could
find no job that parses the line (only `handback.sh` and `pr-sweep.sh`
mention it, both in prose saying no script can check it).

### L2 — `nv2a_index.json`'s provenance now records the sandbox's paths

`docs/testing/nv2a_index.json`, `provenance.tests_root` and
`support_dirs[0]` go from `/home/justin/nxdk_pgraph_tests` and
`/home/justin/pbkitplusplus` to `/home/user/…`. The regeneration itself is
sound and I checked it the way `index-regen-needs-a-dated-tests-tree` says
to: `tests_commit` is unchanged at `91a0de45`, `suites` 103, `sites` 2840,
`gaps` 498 — no suite was silently dropped. The six moved `loc` entries all
land on the right line in the tree at HEAD (`1022` → `assert(!"Invalid
format")`, `1056`/`1321`/`1361` → `assert(false)`, `1134`/`1181` → the border
FIXMEs). But the two paths are the lane container's, not the host's, and the
host's next regeneration flips them back — churn on a shared generated file,
and a provenance record that names a root nothing on the host has.

### L3 — the superseded file's "uncomfortable outcome" names a case the patch cannot produce

`docs/testing/predictions/2026-09-20-gl-stale-surface-blit.json:5`:

> the case to look at is a key whose every draw takes the fast path, where
> forcing `possibly_dirty` now hashes VRAM that nothing reads.

`stale_surface_fill` requires `!surf_to_tex`. A key whose every draw takes
the fast path never sets it and never forces `possibly_dirty`, so the named
outcome has no world in which it occurs. A pre-registered discomfort that the
patch makes unreachable discharges nothing. The superseding file replaced it
with one that *is* reachable ("if an OpenGL arm also comes back
byte-identical…"), which is the right shape — recording this so the
superseded file is not read later as if its leg had held.

### L4 — one path where "cannot be less correct" is not true

Both stale-blit files argue that no capture may regress because "a binding
that regenerates from VRAM when the guest asked for VRAM cannot be less
correct than one that serves an unrelated blit". There is exactly one path
where that sentence is false. `flush_surfaces()` (`gl/surface.c:3374`)
invalidates every surface with the download **commented out** — the
`// FIXME: We should download all surfaces to ram, but need to investigate
corruption issue` at `:3390` — and does not flush the texture cache. Its
caller `pgraph_gl_flush()` then calls
`pgraph_gl_mark_textures_possibly_dirty(d, 0, <all vram>)`, so on the next
draw a blit-filled binding has `possibly_dirty` true and, under the old code,
a `data_hash` that still matches unchanged VRAM — it was kept, blit and all.
Under this change it is destroyed and re-uploaded from VRAM that was
deliberately never written back.

Reachable only out of band: `nv2a_pre_save`/`nv2a_post_load`
(`nv2a.c:1355`, `:1503`), a renderer switch (`pgraph.c:4774`), and
`pgraph_gl_set_surface_scale_factor()` (`gl/surface.c:972`). In the last of
those the binding's `scale` is stale anyway, and the flush's own intent is
that bindings be re-validated against VRAM, so the new behaviour is arguably
the more aligned one. LOW, and not a request to change the code — a request
to stop asserting the universal, because there is a counterexample and it is
in the same file the fix is in.

---

## What pass 2 must verify

Not that a commit exists — that each scenario above can no longer occur.

1. **H1:** that an arms tick on this branch can no longer send
   `2026-09-20-gl-stale-surface-blit-opengl.json` to a handheld. Either
   `arms.sh list` shows it skipped with a reason naming the hand-queue, or
   `arms.sh` reads a field from the file and passes `--device`/`--env` to
   `request.sh` and a `WOULD QUEUE` line shows it. Reading the file and
   finding a stronger sentence in the prose is not verification.
2. **M1:** that `arms.sh list` no longer proposes `…-x1a7-read-side.json` or
   `…-x1a7-download.json` as pairs, by whatever means — or, if they are meant
   to run, a stated reason why four device arms on reverted code is the right
   spend.
3. **L1:** the `Files:` line present and matching
   `git diff --stat origin/master...HEAD`.
4. **L2:** `provenance.tests_root` / `support_dirs` back to the host's paths,
   with `tests_commit` still `91a0de45`.

L3 and L4 are record corrections; a sentence in the file or in `NOTES.md`
closes each.
