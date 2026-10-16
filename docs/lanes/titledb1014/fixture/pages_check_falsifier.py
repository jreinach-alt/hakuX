#!/usr/bin/env python3
"""The `check --pages` mutant test (#433 Part 4).

Part 4 asks for one command that reads every public/rendered page's stated
Playable count and fails if any of them disagrees with the table
(`title_registry.py`'s own PLAYABLE row count). This builds a minimal,
self-contained fixture -- a registry with exactly one PLAYABLE row, plus a
fixture status page, README.md, COMPATIBILITY.md and `.wall-synced` that all
agree with it -- and runs `check --pages` twice:

  1. against the agreeing fixture: must PASS (exit 0, every page reported as
     matching);
  2. against the same fixture with one page's own number changed (the
     mutant): must FAIL (exit 3, naming the one page that now disagrees).

A change that stopped reading a page (silently calling it None, or skipping
it) rather than actually comparing its number would pass step 1 by luck but
not demonstrate anything; printing the per-page lines from real output (not
just the exit code) is what step 2 checks for, so a mutant that broke the
comparison without raising still gets caught.

Usage: python3 pages_check_falsifier.py [<repo>]
"""
import importlib.util
import os
import subprocess
import sys
import tempfile
import time

REPO = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else
                        os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
REGISTRY_PY = os.path.join(REPO, "docs", "testing", "title_registry.py")

TID_PLAYABLE = "5451001A"
TID_OTHER = "5451001B"


def _load_registry_module():
    spec = importlib.util.spec_from_file_location("title_registry_falsifier", REGISTRY_PY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def row(cols, tid, name, status):
    r = {c: "" for c in cols}
    r.update(title_id=tid, name=name, status=status)
    return r


def write_registry(tr, root, path):
    """Write through the real `write()`/`Paths`/`sources_digest()` so the
    fixture's own sources_digest matches what `check` recomputes -- a
    hand-rolled digest would make `check` report STALE regardless of
    --pages, which is not what this falsifier is testing."""
    p = tr.Paths(root)
    rows = [row(tr.COLUMNS, TID_PLAYABLE, "Falsifier Playable Title", "PLAYABLE"),
            row(tr.COLUMNS, TID_OTHER, "Falsifier Below-Bar Title", "BELOW_BAR")]
    tr.write(p, rows, out=path)


def write_pages(d, playable):
    """One fixture page per `page_playable_counts()` source, every one
    stating `playable`. Returns the dict of paths, keyed the same as the
    env vars title_registry.py's Paths reads them from."""
    status_page = os.path.join(d, "index.html")
    open(status_page, "w").write(
        "<html><body>Playable <b>%d</b> / 110 and other words</body></html>\n" % playable)

    readme = os.path.join(d, "README.md")
    open(readme, "w").write(
        "[%d Playable games](docs/COMPATIBILITY.md)\n\n- **%d games rated Playable.** Each one...\n"
        % (playable, playable))

    compat = os.path.join(d, "COMPATIBILITY.md")
    rows_md = "\n".join("| Title %d | ? | Nova | 59.9 | 100%% | 2026-10-14 |  |" % i for i in range(playable))
    open(compat, "w").write(
        "# Compat\n\n%d Playable · 0 run below 30 fps · 0 not playable\n\n"
        "## \U0001f7e2 Playable\n\n| Title | Region | Device | Median fps | Time at bar | Tested date | Notes |\n"
        "|---|---|---|---|---|---|---|\n%s\n\n## Next section\n\nmore text\n" % (playable, rows_md))

    wall_synced = os.path.join(d, ".wall-synced")
    open(wall_synced, "w").write("%d %d v1\n" % (playable, int(time.time())))

    return {"TITLE_STATUS_PAGE": status_page, "TITLE_REPO_README": readme,
            "TITLE_REPO_COMPAT": compat, "TITLE_WALL_SYNCED": wall_synced}


def run_check(root, registry, page_env):
    env = dict(os.environ, **page_env)
    p = subprocess.run([sys.executable, REGISTRY_PY, "check", "--root", root, "--registry", registry, "--pages"],
                        cwd=REPO, env=env, capture_output=True, text=True)
    return p.returncode, p.stdout + p.stderr


def main():
    fails = []
    tr = _load_registry_module()
    with tempfile.TemporaryDirectory(prefix="pages-check-") as root:
        registry = os.path.join(root, "title-registry.tsv")
        write_registry(tr, root, registry)

        agree_dir = os.path.join(root, "agree")
        os.makedirs(agree_dir)
        page_env = write_pages(agree_dir, playable=1)

        rc, out = run_check(root, registry, page_env)
        print("agreeing fixture: exit=%d" % rc)
        print(out)
        if rc != 0:
            fails.append("the agreeing fixture (every page says 1, table is 1) was expected to PASS and did not")
        if out.count("matches the table") != 6:
            fails.append("expected all 6 pages to report 'matches the table'; got: %r" % out)

        # The mutant: one page's own number, the README bullet, no longer
        # agrees with the table -- the rest of the fixture is untouched.
        mutant_readme = os.path.join(agree_dir, "README.md")
        text = open(mutant_readme).read()
        mutated = text.replace("1 games rated Playable.", "2 games rated Playable.")
        if mutated == text:
            fails.append("could not construct the mutant: the bullet text to replace was not found")
        open(mutant_readme, "w").write(mutated)

        rc2, out2 = run_check(root, registry, page_env)
        print("mutant fixture (README bullet changed to 2): exit=%d" % rc2)
        print(out2)
        if rc2 == 0:
            fails.append("the mutant (README bullet says 2, table is 1) was expected to FAIL and did not")
        if "PAGE README.md (bullet): Playable 2, table 1" not in out2:
            fails.append("expected the mismatch line naming README.md (bullet); got: %r" % out2)
        # Every OTHER page must still agree -- the mutant touched one line
        # in one file, nothing else.
        if out2.count("matches the table") != 5:
            fails.append("expected the other 5 pages to still match; got: %r" % out2)

    if fails:
        print("FAIL")
        for f in fails:
            print(" - %s" % f)
        return 1
    print("PASS: check --pages passes when every page agrees, and fails naming the one page a mutant disagreed on")
    return 0


if __name__ == "__main__":
    sys.exit(main())
