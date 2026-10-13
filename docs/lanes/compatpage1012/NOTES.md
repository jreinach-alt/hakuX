# lane.compatpage1012 notes

## What I built

`docs/testing/compat_page.py` generates `docs/COMPATIBILITY.md` and
`docs/compatibility.csv` from three inputs: `pm/playable-accepted.tsv` (the
52-row Playable ledger), a `title_registry.py build --no-forge` snapshot
(copy kept at `docs/lanes/compatpage1012/registry.tsv` for reproducing this
run), and the hand-written `docs/testing/compat_notes.tsv` (region, region
source, notes, red reasons, the NFS hand-played override figures).
`docs/testing/compat_page_selftest.py` covers tier assignment per cause
shape, ledger-wins, the NFS override, the "?" region fallback, and `--check`
on a stale page. All 18 selftest cases and `--check` against the committed
files pass. Full reasoning, region sourcing, and every red/left-off decision
is in `PR.md` — this file is the short version for the next lane.

## What to not repeat

- **Registry's `name` column is not a safe join key.** It's a mangled,
  sometimes region/subtitle-suffixed version of the title (e.g. "Ty the
  Tasmanian Tiger Night of the Quinkan USA Australia"). Match registry rows
  to hand-written notes by `title_id`, never by title string. This cost one
  debugging round (`build_below_bar_rows` originally matched by name and
  raised "missing from compat_notes.tsv" for six titles that were actually
  present, just under a different key).
- **`registry.tsv` has two leading `#` comment lines before the header.**
  Skip any line starting with `#` before treating a row as the header or
  data; `load_registry` does this (`read_tsv(path, skip_comments=True)`).
- **`csv.writer`'s default line terminator is `\r\n`.** Writing the CSV with
  `open(path, newline="")` preserves that `\r\n` on disk, but reading it back
  with a plain `open(path).read()` (as `--check` originally did) applies
  universal-newline translation and silently converts it to `\n` — so a
  freshly-written file compared against freshly-rendered text always came
  back "stale," even though nothing was wrong. Fixed by forcing
  `csv.writer(buf, lineterminator="\n")` so both sides agree. If you touch
  `render_csv` or the `--check` comparison again, keep this in mind — the
  selftest's `CheckFailsOnStalePage.test_check_exits_nonzero_when_md_is_stale`
  (which also round-trips a clean generate-then-check) will catch a
  regression here, since it failed loudly on exactly this bug before the fix.
- **`below_bar_qualifies` is a single equality check, not a hand-maintained
  exclusion list**: a row qualifies for 🟡 only if `failing_all == "fps"`
  exactly. This one line correctly excludes every brief-named left-off shape
  (menu_time, duration, reached_gameplay:unconfirmed, audio, hitch, static)
  without needing to enumerate them. Don't replace it with an "excludes
  list" — the equality check is more robust to new failure shapes appearing
  in a future registry rebuild.
- **The brief's own CRASH_OR_HANG example for NHL Hitz Pro is wrong** (or at
  least superseded) — its `hold_detail` carries a later, human-reviewed
  override that reclassifies it as a true hang, not a stale fps-cause
  left-off row. Don't trust a brief's illustrative example over a row's own
  `hold_detail` without checking; I verified this directly against the live
  registry text before deciding. The override is encoded in
  `RED_OVERRIDES["4D57001A"]` in `compat_page.py`, not just prose, so a
  registry rebuild can't silently re-flag it — any other row that trips the
  left-off guard without a matching `RED_OVERRIDES` entry makes the
  generator raise.
- **XBE-certificate region parsing (priority source 5) was deferred, not
  attempted.** `/mnt/d/hakux-staging/sweep/` is readable from this sandbox,
  but there's no verified parser for the game-region flags and nothing to
  check a hand-rolled one against. 25 titles are left as "?" on the page
  rather than risk a silently-wrong region. See PR.md's "For lane.local"
  section before writing one.
- **xemu.app is on the WebFetch deny list** (it's GitHub-Pages-hosted); use
  WebSearch instead. `reports.xemu.app` is Discord-auth-gated and
  `redump.org` returns `ECONNREFUSED` from this sandbox — neither is usable
  for region lookups right now.

## State

Selftest: 18/18 pass. `compat_page.py --check`: passes against the committed
`docs/COMPATIBILITY.md` and `docs/compatibility.csv`. README.md wording
edited at the four brief-specified locations, nothing else touched. Ready to
commit and push.
