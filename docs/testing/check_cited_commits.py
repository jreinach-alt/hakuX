#!/usr/bin/env python3
"""Check every commit the tracker cites against this branch.

WHY THIS IS A SCRIPT. A tracker entry says "the fix is 8ab35a6167". The
obvious check is `git merge-base --is-ancestor`, and on this repo it gives the
wrong answer most of the time, because lane work is rebased in constantly and
lands under a different sha. An absent sha is the NORMAL state for work that
shipped.

So the question worth asking is about PATCHES, not shas. Ancestry is a fact
about shas.

Written after getting this wrong in public. On 2026-09-13 I read
`merge-base --is-ancestor 8d2bf50075 HEAD` returning false as "#43's sign-fold
fix is not present", published a refutation of #43's attribution on the
strength of it, and had to withdraw it: 8d2bf50075 was not the fix at all --
it was the arm-B REF of the pair `322adc3a01 -> 8d2bf50075` -- and the real
fix 322adc3a01 was on the branch as c2d57ba21a66, identical patch-id, and was
an ancestor of the very arm I had called clean. #60's own entry documents the
same trap, which I had read hours earlier.

Two further ways I got the instrument wrong before it worked, both worth
keeping so nobody rebuilds them:

  - `git cherry HEAD <sha>` lists the WHOLE divergent range, so reading its
    first line answers about an unrelated commit. It told me everything had
    landed, which was the opposite error.
  - Searching patch-ids over `HEAD -200` misses anything older. Scope the log
    to the paths the commit touches instead: same answer, whole history,
    and fast.

WHAT THIS CANNOT SEE, stated because a clean report would otherwise read as
proof. patch-id matches a patch EXACTLY. A commit that was folded in with any
edit at all -- a resolved conflict, one extra comment line -- will be reported
ABSENT while its substance is present. That is real here: #62's a763b1d4fc is
reported absent and our 013181dfef is the same fix carrying one extra comment
line, because it landed on a tree where the helper already existed. So ABSENT
means "no byte-identical patch", not "the work is missing" -- it is a prompt
to go and look, and the subject line is there to make looking cheap.

And print every sha's SUBJECT. Half the hex strings in this tracker are not
fix commits: they are A/B arm refs, dispatch request ids, sha256 prefixes of
prediction files, and docs commits. #72's `fixed_by` named a docs commit as
its fix until this script printed the subject next to it.
"""
import os, re, subprocess, sys, tomllib

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.join(HERE, "..", "..")


def git(*a):
    return subprocess.run(["git", "-C", REPO] + list(a),
                          capture_output=True, text=True)


def patch_id(rev):
    p1 = subprocess.Popen(["git", "-C", REPO, "show", rev],
                          stdout=subprocess.PIPE)
    p2 = subprocess.Popen(["git", "-C", REPO, "patch-id", "--stable"],
                          stdin=p1.stdout, stdout=subprocess.PIPE, text=True)
    p1.stdout.close()
    out = p2.communicate()[0].strip()
    return out.split(" ")[0] if out else ""


def classify(sha):
    """(kind, subject, landed_as). kind: on-branch | rebased-in | ABSENT."""
    if git("rev-parse", "-q", "--verify", sha + "^{commit}").returncode != 0:
        return None, "", ""
    subj = git("log", "-1", "--format=%s", sha).stdout.strip()
    if git("merge-base", "--is-ancestor", sha, "HEAD").returncode == 0:
        return "on-branch", subj, sha
    want = patch_id(sha)
    paths = [p for p in git("show", "--name-only", "--format=", sha)
             .stdout.split("\n") if p.strip()]
    if want and paths:
        for h in git("log", "--format=%H", "HEAD", "--", *paths).stdout.split():
            if patch_id(h) == want:
                return "rebased-in", subj, h
    return "ABSENT", subj, ""


def main():
    with open(os.path.join(HERE, "nv2a_issues.toml"), "rb") as fh:
        tracker = tomllib.load(fh)["issue"]

    absent, seen = [], {}
    for num, v in sorted(tracker.items()):
        blob = " ".join(str(v.get(k) or "")
                        for k in ("status_note", "blocked_on", "note"))
        blob += " " + " ".join(v.get("fixed_by") or [])
        for sha in sorted(set(re.findall(r"\b[0-9a-f]{8,12}\b", blob))):
            if sha not in seen:
                seen[sha] = classify(sha)
            kind, subj, _ = seen[sha]
            if kind == "ABSENT":
                absent.append((num, v.get("status"), sha, subj))

    real = sum(1 for k, _, _ in seen.values() if k)
    print("cited commits: %d hex tokens, %d are real commits on this repo"
          % (len(seen), real))

    if not absent:
        print("every cited commit is present (as itself or rebased in)")
        return 0

    # A `fixed-*` entry resting on an absent commit is the #72 shape: closed,
    # or called fixed, with the work on somebody else's branch. That is worth
    # failing. `fixed-unlanded` says so deliberately and is exempt -- it has
    # its own check in check_coverage.py.
    bad = [r for r in absent
           if str(r[1]).startswith("fixed") and r[1] != "fixed-unlanded"]
    print("\n%d cited commit(s) NOT present on this branch, as a patch:"
          % len(absent))
    for num, st, sha, subj in absent:
        print("  #%-4s [%-14s] %s  %s" % (num, st, sha, subj[:62]))
    print("\n  Read the subject before treating one as a gap: A/B arm refs,\n"
          "  docs commits and prediction sha256 prefixes all look like this.")
    if bad:
        print("\nFAIL: %d entr%s claim a fix that is not on this branch:"
              % (len(bad), "y" if len(bad) == 1 else "ies"), file=sys.stderr)
        for num, st, sha, subj in bad:
            print("  #%-4s [%s] %s" % (num, st, sha), file=sys.stderr)
        print("\n  Either the work landed under another sha -- then cite that\n"
              "  one -- or it did not, and the status is wrong. "
              "`fixed-unlanded`\n  is the honest value when a fix exists "
              "elsewhere.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
