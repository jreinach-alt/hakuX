# storydoc1017: add the project history page, link it from the README's More table

## Step 0: already-tried

| approach | where | verdict | what it means here |
|---|---|---|---|
| `git log --all --grep='HISTORY.md'` | repo history | no hits | no prior attempt put a page at this path |
| `git log --all --grep='history' -i` | repo history | hits are unrelated: `apu: HRTF history cleared on voice start` (audio ring buffer), and routine `fold:`/path commits with "history" only in unrelated prose | no prior project-history doc effort to reuse |
| `git log --all --grep='story' -i` | repo history | one relevant hit: `release052c` (`a6ec42fadc`, #433) added `docs/releases/*.md` -- a version-by-version release-notes page ("the 0.5.2 release page tells the story since v0.3.1"). That's a different document (dated release notes per version) from this one (a single narrative history of the whole project, owner-reviewed, staged separately); not reused, not superseded. | this lane's page is new and distinct from `docs/releases/` |
| `ls docs/HISTORY.md` | working tree | does not exist | path is free, no collision |

## What this lane did

1. Copied `/home/justin/hakux-work/briefs/storydoc1017.HISTORY.md` to `docs/HISTORY.md` byte for byte via
   `shutil.copyfile` (python3; the file is outside the worktree so the Bash tool's own read may refuse it, though
   `sha256sum` on the source path worked directly in this session). Verified sha256 of the copy against the staged
   sha256 `47884a90112be7f4b462c9b7b6ec5cc3bb440d56c07eda351fecfe425f69b9bb` -- match. Text not edited.
2. Added one row to README.md's `## More` table, directly after the Roadmap row:
   `| [How we got here](docs/HISTORY.md) | The story of hakuX CE so far |`
   Nothing else in README.md touched. The `_Last updated_` line is not bumped: this is a link addition, not a review
   of the document.
3. Did not add `docs/HISTORY.md` to `docs/testing/public_docs.txt`: that list (`docs/testing/docs_freshness.py`)
   drives a 14-day freshness alarm for pages that describe the current build. `docs/HISTORY.md` is a dated narrative
   of how the project got here, not a page about the current build's state, so the alarm would flag it for no
   reason it can act on.
4. Checked `docs/testing/title_registry.py`'s README-reading code (`page_playable_counts`, around line 879-885):
   it opens `p.repo_readme` (README.md) and applies two regexes, `\[(\d+) Playable games\]` and
   `(\d+) games rated Playable\.`, to the whole text. The new row's text --
   `[How we got here](docs/HISTORY.md) | The story of hakuX CE so far` -- contains neither `Playable games` nor
   `games rated Playable.`, so it cannot match either regex, before or after. Read only; not re-run, since the
   regex and the new text are both in hand and the result is structural (no digit sequence next to either phrase).
5. Searched `docs/testing/jobs/selftest.d/` for `public_docs`, `HISTORY.md`, and "More table": no fragment reads any
   of the three. A broader grep for `README.md`/`readme` in that directory hits 10 files, but every one of them uses
   `README.md` as a generic fixture filename inside a synthetic throwaway repo the fragment builds itself (e.g.
   `86-nightly-notes.sh`'s `commit_touching ... README.md`, `99-cloud-lane-branch.sh`'s
   `echo one > "$CL/repo/README.md"`), never the real repo's README or its More table. `Selftest: none` for this
   change.

## Open questions

None.
