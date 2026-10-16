# ce1016 -- display name becomes hakuX CE (Community Edition): docs pass (#433)

## What changed

Per the owner's 10-16 decision and instruction ("I wouldn't just do a
search/replace for all hakuX references. Just make the necessary changes to
bolds/titles."), only places where the app's name is displayed *as a name*
were changed -- H1 titles, bold product-name callouts, and the ES-DE menu
label. Read every file in full before editing; no sed across the tree.

| File | Change |
|---|---|
| `README.md` | H1 `# hakuX (fork)` -> `# hakuX CE`; opening bold sentence now says hakuX CE is the Community Edition; "It appears as **hakuX (fork)**" -> "**hakuX CE**"; "Android 10 or newer" -> "Android 13 or newer" (0.5.1 minSdk 33, sign1016 `56bb989b0c`, owner-confirmed no sub-13 handheld can run it); `_Last updated_` set to 2026-10-16, version left at 0.5.0 |
| `PRIVACY.md` | Opening sentence "hakuX (fork) runs on your device" -> "hakuX CE runs on your device" |
| `ROADMAP.md` | "Where hakuX (fork) is heading" -> "Where hakuX CE is heading" |
| `android/MIGRATING.md` | Bold "installs as its own app, **hakuX (fork)**" -> "**hakuX CE**"; "needs Android 10 and a Snapdragon 845-class chip" -> "needs Android 13 and a Snapdragon 845-class chip" (same minSdk-33 reason as README) |
| `docs/es-de/es_systems.xml` | `<command label="hakuX fork (Standalone)">` -> `<command label="hakuX CE (Standalone)">` -- the label is what ES-DE's menu shows |
| `docs/es-de/README.md` | Both the prose step ("choose **hakuX fork (Standalone)**") and the `<command label=...>` snippet in the "own es_systems.xml" section updated to match, so the doc and the shipped file never disagree |
| `docs/frontends/stock-launcher.md` | Three mentions of the observed app-drawer/search label ("hakuX (fork)") updated to "hakuX CE" -- this doc is an operator guide (what to tap), not a historical artifact; see "What I left alone" for why the embedded screenshots were not treated as blocking this |
| `docs/frontends/README.md` | The "About the app name" section rewrote its forward-looking "the owner may rename it later" note into a past-tense record of this rename, keeping the package-id/activity-is-not-a-display-name point intact |

`docs/lanes/ce1016/PR.md` and this file are the only other additions.

## What I deliberately left unchanged, and why

- **Plain "hakuX"** naming the emulator, the official project, or the
  upstream (e.g. README.md "An independent build of the hakuX emulator",
  "Installs alongside the official hakuX", Credits section, "repository was
  forked from") -- not a display-name instance, per the brief.
- **Identifiers**: the ES-DE `<emulator name="HAKUX-FORK">` block and the
  `%EMULATOR_HAKUX-FORK%` variable in `docs/es-de/es_find_rules.xml` and
  `es_systems.xml`/`README.md` -- renaming these breaks every user's existing
  `custom_systems` files. Package id `com.jreinach.hakux` and activity
  `com.rfandango.haku_x.LauncherActivity`/`GameLibraryActivity` -- not display
  names either.
- **XML developer comments** in `docs/es-de/es_find_rules.xml` (lines 3, 7,
  15) and `es_systems.xml` (lines 3, 12) that describe "the hakuX fork
  build"/"the fork's command" -- these are internal comments never rendered
  to a user (not a bold/title/label), so left as-is per the owner's
  no-blanket-replace instruction. Flagging here in case a future pass wants
  them for consistency, but they're not load-bearing for anyone reading the
  docs.
- **`docs/frontends/stock-launcher.md` screenshots**
  (`images/stock-app-drawer.png`, `images/stock-launch.png`): I updated the
  surrounding *prose* to hakuX CE (it's a how-to guide, and a stale label in
  the text would send a reader looking for the wrong name), but the PNGs
  themselves still show whatever the device rendered during the frontends1016
  test (0.4.1 build, pre-rename) and were not touched -- images aren't in
  scope for a text rename and regenerating them needs a device, which this
  lane doesn't have. The app-drawer screenshot I could inspect doesn't
  actually show the "hakuX" search result text (crops above it), so there's
  no visible mismatch today; if a later screenshot ever shows the literal
  string "hakuX (fork)", that's expected until the shots are redone after a
  0.5.1 device test.
- **`docs/frontends/es-de.md`, `daijisho.md`, `pegasus.md`**: grepped, only
  plain "hakuX" (package id lines, "hakuX cannot be wired..." prose) --
  nothing to change.
- **`android/README.md`**: has its own "Android 10"-style requirement text
  but is explicitly **not** my territory per the brief -- listed here for
  lane.xbox / whoever owns it next, since it will disagree with README.md's
  new "Android 13 or newer" until it's updated too.
- **`CHANGELOG.md`** and **`android/app/build.gradle.kts`** line ~167
  (`resValue("string", "app_name", "hakuX (fork)")`): explicitly out of my
  territory per the brief -- **lane.xbox owns both** as part of the 0.5.1
  release commit.
- **Historic/out-of-territory hits noticed but not touched** (found while
  grepping the repo for consistency, not part of my file list):
  `docs/reporting-bugs.md` (two "hakuX (fork)" mentions, a bug-report
  template describing today's build name) and
  `docs/investigations/known-issues-reverified-2026-09-12.md` (dated
  investigation note, "hakuX (fork)" describing a build at that time) --
  neither is in my territory list; flagging for whoever next does a sweep.
- **`PRIVACY.md` / `ROADMAP.md` `_Last updated_` dates**: left at their
  existing dates (2026-10-13 / 2026-10-12). The brief's "set the date to
  today" instruction was under "README.md specifically"; PRIVACY/ROADMAP
  weren't otherwise touched enough to warrant a freshness bump, and
  `docs_freshness.py` still reports them OK (within the staleness window).

## Remaining `fork` hits in my territory (git grep -n "fork")

- `README.md:122` -- "repository was forked from" (Credits, lineage --
  legitimate).
- `docs/es-de/es_find_rules.xml:3,7,15` -- developer comments, see above.
- `docs/es-de/es_systems.xml:3,12` -- developer comments, see above.
- `docs/frontends/README.md:19` -- quotes the *old* name
  ("hakuX (fork)") in past tense while explaining the rename happened;
  legitimate historical reference, not a current display.
- `docs/lanes/ce1016/PR.md:12` -- this lane's own PR description, quoting
  both names while describing the task.

## Verify

- `python3 docs/testing/docs_freshness.py` -- 11 OK, 0 not OK (same as
  before this change; README.md's date line now reads 0 d stale).
- `home_page.py` has no `--check` flag; read `readme()` and confirmed by
  script that all four of its regexes (`Playable games` link,
  `**N games rated Playable.**`, `See them all.` link, the Compatibility
  table-row anchor) still match the new README.md exactly once, and
  `## Credits\n` still appears exactly once -- none of the lines those
  regexes/replace touch were edited by this lane.
- All relative markdown links in the eight changed files resolve to files
  that exist in this worktree (checked by script, not by eye alone).

## For lane.xbox (0.5.1 release commit)

1. `CHANGELOG.md` -- not touched; update per the brief's instruction (this
   lane's territory excludes it).
2. `android/app/build.gradle.kts:167` --
   `resValue("string", "app_name", "hakuX (fork)")` -- not touched; this is
   where the actual installed app label changes to hakuX CE.

Also worth knowing: `android/README.md` (not my territory) still says
"Android 10" in its build/requirements text and will read inconsistently
with README.md's new "Android 13 or newer" until someone updates it.
