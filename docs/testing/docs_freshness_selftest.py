#!/usr/bin/env python3
"""Selftest for docs_freshness.py (#433): every state it can report, the
14-day boundary, --release overriding the Gradle version, numeric version
comparison, the H1-anchored date line, and the exit codes.

Builds a throwaway fixture repo per case under a temp dir -- never this
worktree -- with just enough of android/app/build.gradle.kts and
docs/testing/public_docs.txt for the script to run against. Each case
asserts on the printed STATE for its doc, not just the exit code: the
script can exit 1 for OK-but-another-doc-is-stale as easily as for the case
under test, so the line is the check.

    docs_freshness_selftest.py            run every case; exit 0 all green, 1 otherwise
    docs_freshness_selftest.py -v         also print each case's full output on failure

Needs no device, no network, no git checkout other than the fixtures it
builds itself.
"""
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.environ.get("SCRIPT", os.path.join(HERE, "docs_freshness.py"))
VERBOSE = "-v" in sys.argv

FAIL = 0


def gradle_text(version):
    # only the one literal docs_freshness.py actually reads: a quoted
    # X.Y.Z(-suffix) string, in the shape of build.gradle.kts's real
    # "<base>-unknown" fallback.
    return (
        'android {\n'
        '    defaultConfig {\n'
        '        versionCode = 9\n'
        '        versionName = versionedRelease ?: stampedVersionName() ?: "%s-unknown"\n'
        '    }\n'
        '}\n' % version
    )


def make_repo(root, version="0.5.0", docs=None):
    """docs: {relpath: file text or None for "listed but absent"}."""
    os.makedirs(os.path.join(root, "android", "app"), exist_ok=True)
    with open(os.path.join(root, "android", "app", "build.gradle.kts"), "w") as fh:
        fh.write(gradle_text(version))
    os.makedirs(os.path.join(root, "docs", "testing"), exist_ok=True)
    docs = docs or {}
    with open(os.path.join(root, "docs", "testing", "public_docs.txt"), "w") as fh:
        fh.write("# fixture list\n")
        for relpath in docs:
            fh.write(relpath + "\n")
    for relpath, text in docs.items():
        if text is None:
            continue
        full = os.path.join(root, relpath)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w") as fh:
            fh.write(text)


def doc(date, version, lines_before="", lines_after=""):
    return (
        "# Example Doc\n"
        + lines_before
        + "_Last updated %s, for version %s._\n" % (date, version)
        + lines_after
    )


def run(root, extra_args):
    p = subprocess.run(
        [sys.executable, SCRIPT, "--repo", root] + extra_args,
        capture_output=True, text=True)
    return p.returncode, p.stdout, p.stderr


def check(desc, root, extra_args, want_state, want_doc="doc.md", want_exit=None):
    global FAIL
    rc, out, err = run(root, extra_args)
    line = next((l for l in out.splitlines() if want_doc in l), None)
    got_state = line.split()[0] if line else "<no line>"
    ok = got_state == want_state
    if want_exit is not None:
        ok = ok and rc == want_exit
    if ok:
        print("ok - %s" % desc)
    else:
        FAIL += 1
        print("NOT OK - %s: want state=%s%s, got state=%s rc=%s" % (
            desc, want_state,
            (" exit=%d" % want_exit) if want_exit is not None else "",
            got_state, rc))
        if VERBOSE:
            print("  --- stdout ---")
            print("\n".join("  " + l for l in out.splitlines()))
            print("  --- stderr ---")
            print("\n".join("  " + l for l in err.splitlines()))


def with_repo(fn):
    tmp = tempfile.mkdtemp(prefix="docsfresh-selftest-")
    try:
        fn(tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def case_ok():
    def fn(root):
        make_repo(root, version="0.5.0", docs={
            "doc.md": doc("2026-10-01", "0.5.0"),
        })
        check("OK: fresh doc at the current version", root,
              ["--today", "2026-10-10"], "OK")
    with_repo(fn)


def case_boundary():
    def fn(root):
        make_repo(root, version="0.5.0", docs={
            "doc.md": doc("2026-10-01", "0.5.0"),
        })
        # 2026-10-15 is exactly 14 days after 2026-10-01: OK
        check("boundary: 14 days old is OK", root,
              ["--today", "2026-10-15"], "OK")
        # 2026-10-16 is 15 days: STALE
        check("boundary: 15 days old is STALE", root,
              ["--today", "2026-10-16"], "STALE")
    with_repo(fn)


def case_stale_version():
    def fn(root):
        make_repo(root, version="0.6.0", docs={
            "doc.md": doc("2026-10-10", "0.5.0"),
        })
        check("STALE: fresh date, but an older version than the build",
              root, ["--today", "2026-10-10"], "STALE")
    with_repo(fn)


def case_version_numeric_not_string():
    def fn(root):
        # 0.10.0 is newer than 0.9.0 as numbers, but "0.10.0" < "0.9.0" as
        # strings (the '1' loses to the '9' one character in). A build at
        # 0.9.0 with a doc already dated for 0.10.0 must read OK: a string
        # comparison would call the doc older than the build and mark it
        # STALE instead.
        make_repo(root, version="0.9.0", docs={
            "doc.md": doc("2026-10-10", "0.10.0"),
        })
        check("version compared as numbers: a 0.10.0 doc is OK against a 0.9.0 build "
              "(string comparison would wrongly call it STALE)",
              root, ["--today", "2026-10-10"], "OK")
    with_repo(fn)


def case_release_override():
    def fn(root):
        make_repo(root, version="0.5.0", docs={
            "doc.md": doc("2026-10-10", "0.6.0"),
        })
        # The Gradle version is 0.5.0 (doc would be "newer", i.e. fine), but
        # --release overrides it to 0.7.0: now the doc is stale.
        check("--release overrides the Gradle version", root,
              ["--today", "2026-10-10", "--release", "0.7.0"], "STALE")
        check("without --release the same doc reads OK against Gradle's 0.5.0",
              root, ["--today", "2026-10-10"], "OK")
    with_repo(fn)


def case_missing_file():
    def fn(root):
        make_repo(root, version="0.5.0", docs={"doc.md": None})
        check("MISSING-FILE: listed but absent", root,
              ["--today", "2026-10-10"], "MISSING-FILE")
    with_repo(fn)


def case_missing_line():
    def fn(root):
        make_repo(root, version="0.5.0", docs={
            "doc.md": "# Example Doc\n\nNo date line here, just prose.\n",
        })
        check("MISSING-LINE: file exists, no date line after the H1",
              root, ["--today", "2026-10-10"], "MISSING-LINE")
    with_repo(fn)


def case_line_only_right_after_h1():
    def fn(root):
        # The date line exists, but inside a code block further down, not
        # as the first non-blank line after the H1: must not count.
        text = (
            "# Example Doc\n"
            "\n"
            "Some intro text before any date line.\n"
            "\n"
            "```\n"
            "_Last updated 2026-10-10, for version 0.5.0._\n"
            "```\n"
        )
        make_repo(root, version="0.5.0", docs={"doc.md": text})
        check("a date line not immediately after the H1 is MISSING-LINE",
              root, ["--today", "2026-10-10"], "MISSING-LINE")
    with_repo(fn)


def case_bad_date_unparseable():
    def fn(root):
        make_repo(root, version="0.5.0", docs={
            "doc.md": doc("not-a-date", "0.5.0"),
        })
        check("BAD-DATE: unparseable date", root,
              ["--today", "2026-10-10"], "BAD-DATE")
    with_repo(fn)


def case_bad_date_future():
    def fn(root):
        make_repo(root, version="0.5.0", docs={
            "doc.md": doc("2026-10-20", "0.5.0"),
        })
        check("BAD-DATE: dated later than today", root,
              ["--today", "2026-10-10"], "BAD-DATE")
    with_repo(fn)


def case_exit_codes():
    def fn(root):
        make_repo(root, version="0.5.0", docs={
            "doc.md": doc("2026-10-01", "0.5.0"),
        })
        rc, _, _ = run(root, ["--today", "2026-10-10"])
        if rc == 0:
            print("ok - exit 0 when every doc is OK")
        else:
            global FAIL
            FAIL += 1
            print("NOT OK - exit 0 when every doc is OK: got %d" % rc)
    with_repo(fn)

    def fn2(root):
        make_repo(root, version="0.5.0", docs={
            "doc.md": doc("2026-09-01", "0.5.0"),
        })
        rc, _, _ = run(root, ["--today", "2026-10-10"])
        if rc == 1:
            print("ok - exit 1 when a doc is not OK")
        else:
            global FAIL
            FAIL += 1
            print("NOT OK - exit 1 when a doc is not OK: got %d" % rc)
    with_repo(fn2)

    def fn3(root):
        rc, _, _ = run(root, ["--not-a-real-flag"])
        if rc == 2:
            print("ok - exit 2 on a usage error")
        else:
            global FAIL
            FAIL += 1
            print("NOT OK - exit 2 on a usage error: got %d" % rc)
    with_repo(fn3)


def main():
    if not os.path.isfile(SCRIPT):
        print("docs_freshness_selftest.py: no script at %s" % SCRIPT, file=sys.stderr)
        return 1

    case_ok()
    case_boundary()
    case_stale_version()
    case_version_numeric_not_string()
    case_release_override()
    case_missing_file()
    case_missing_line()
    case_line_only_right_after_h1()
    case_bad_date_unparseable()
    case_bad_date_future()
    case_exit_codes()

    if FAIL:
        print("\n%d case(s) failed" % FAIL)
        return 1
    print("\nall cases passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
