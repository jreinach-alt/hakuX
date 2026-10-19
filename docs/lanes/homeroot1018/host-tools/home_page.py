#!/usr/bin/env python3
"""The `home` branch: GitHub's default branch, the page a visitor lands on (owner 10-13: "Yes switch the branch";
10-13 23:2x: STATUS.md and its charts reside on home, and the README links to it).

home carries the landing files from master -- README.md, CONTRIBUTING.md, KNOWN_ISSUES.md, PRIVACY.md, CHANGELOG.md,
SECURITY.md and CODE_OF_CONDUCT.md (owner 10-16), the licence files, the issue/PR templates and FUNDING.yml -- plus
STATUS.md and its chart SVGs, which status_page.py renders. Relative links in master's Markdown are rewritten to
absolute .../{blob,tree}/master/... URLs (home has no source tree), except a link to a file home carries, which stays
relative, and a relative `src="..."` (the logo): GitHub renders no image from a /blob/ URL, so home carries that file
at the same path and the src stays relative. The README gains a "Source code"
section, its Playable count is set to the one STATUS.md shows (so the two never disagree), and its count links point at
STATUS.md. No .github/workflows (the gateway token cannot push them, and Actions stays off).

Every commit's parent is the current home, so each update is a fast-forward the gateway can push (it never forces).
Model-free. Called by status_page.py; `home_page.py` alone rebuilds home from master with the STATUS.md and charts
already on home.
"""
import os, re, subprocess, sys, tempfile

G = "/home/justin/hakux-work/offline-git/hakuX.git"
SRC = "master"
BASE = "https://github.com/jreinach-alt/hakuX"
FILES = ["README.md", "CONTRIBUTING.md", "KNOWN_ISSUES.md", "PRIVACY.md", "CHANGELOG.md", "SECURITY.md",
         "CODE_OF_CONDUCT.md", "LICENSE", "COPYING", "COPYING.LIB",
         ".github/FUNDING.yml", ".github/pull_request_template.md",
         ".github/ISSUE_TEMPLATE/config.yml", ".github/ISSUE_TEMPLATE/feature-request.yml",
         ".github/ISSUE_TEMPLATE/general-issue.yml", ".github/ISSUE_TEMPLATE/title-issue.yml"]
# Carried when master has them (GitHub shows the security policy and code of conduct from the default branch); any
# other file in FILES missing from master is an error.
OPTIONAL = {"SECURITY.md", "CODE_OF_CONDUCT.md"}
REWRITE = {"README.md", "CONTRIBUTING.md", "KNOWN_ISSUES.md", "PRIVACY.md", "CHANGELOG.md", "SECURITY.md",
           "CODE_OF_CONDUCT.md", ".github/pull_request_template.md"}
# homeroot1018 (#433, owner 10-18: a sloppy-looking root): a file in FILES whose home path differs from its path on
# master. COPYING.LIB holds no source code on home (only LICENSE/COPYING need to sit in the root for GitHub to read
# the licence from there), so it moves under docs/licenses/ -- the source stays at master's COPYING.LIB.
RENAME = {"COPYING.LIB": "docs/licenses/COPYING.LIB"}
STATUS_FILES = ("STATUS.md", "docs/images/chart.svg", "docs/images/chart2.svg")
SOURCE_SECTION = ("## Source code\n\n"
                  "The code is on the [master branch](" + BASE + "/tree/master). To clone it:\n\n"
                  "```\ngit clone -b master " + BASE + ".git\n```\n\n")


def git(*a, inp=None, env=None):
    r = subprocess.run(["git", "-C", G, *a], input=inp, capture_output=True, env=env)
    if r.returncode:
        raise RuntimeError("git %s failed: %s" % (" ".join(a[:3]), r.stderr.decode(errors="replace").strip()))
    return r.stdout


def kind(path):
    r = subprocess.run(["git", "-C", G, "cat-file", "-t", "%s:%s" % (SRC, path)], capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else None


def absolute(target, here, home=()):
    """A relative link target in file `here` -> absolute master URL, unless it names a file in `home` (the files home
    carries), which stays relative so the visitor stays on home (its RENAME path, if it has one); anything else
    unchanged."""
    if re.match(r"^([a-z][a-z0-9+.-]*:|#|/)", target, re.I):
        return target
    path, frag = (target.split("#", 1) + [""])[:2]
    path = os.path.normpath(os.path.join(os.path.dirname(here), path)) if path else here
    if path.startswith(".."):
        raise RuntimeError("%s links outside the repository: %r" % (here, target))
    k = kind(path.rstrip("/"))
    if k is None:
        raise RuntimeError("%s links to %r, which is not on %s" % (here, target, SRC))
    if path in home:
        if path in RENAME:
            return RENAME[path] + ("#" + frag if frag else "")
        return target
    return "%s/%s/master/%s%s" % (BASE, "tree" if k == "tree" else "blob", path.rstrip("/"), "#" + frag if frag else "")


def source(target, here, carry):
    """A src="..." target in file `here`: a relative one stays relative and its path is added to `carry`, for home to
    hold the file itself (it must be a file on master); with no `carry`, or a non-relative target, as absolute()."""
    if carry is None or re.match(r"^([a-z][a-z0-9+.-]*:|#|/)", target, re.I):
        return absolute(target, here)
    path = os.path.normpath(os.path.join(os.path.dirname(here), target))
    if path.startswith("..") or kind(path) != "blob":
        raise RuntimeError("%s shows %r, which is not a file on %s" % (here, target, SRC))
    carry.add(path)
    return target


def rewrite(text, here, carry=None, home=()):
    out, fence = [], False
    for line in text.splitlines(keepends=True):
        if line.lstrip().startswith("```"):
            fence = not fence
        if not fence:
            line = re.sub(r"(\]\()([^)\s]+)(\))",
                          lambda m: m.group(1) + absolute(m.group(2), here, home) + m.group(3), line)
            line = re.sub(r"^(\s*\[[^\]]+\]:\s*)(\S+)", lambda m: m.group(1) + absolute(m.group(2), here, home), line)
            line = re.sub(r'(href=")([^"]+)(")',
                          lambda m: m.group(1) + absolute(m.group(2), here, home) + m.group(3), line)
            line = re.sub(r'(src=")([^"]+)(")', lambda m: m.group(1) + source(m.group(2), here, carry) + m.group(3), line)
        out.append(line)
    return "".join(out)


def readme(text, playable):
    """master's README (links already absolute) -> home's: the source section, and when `playable` is known, the live
    Playable count with its links pointing at STATUS.md. Each edit must find exactly one place, or nothing is changed
    and the reason is raised (a README rewrite on master then shows up here, not as a silently stale count)."""
    text = text.replace("## Credits\n", SOURCE_SECTION + "## Credits\n", 1) if "## Credits\n" in text \
        else text.rstrip("\n") + "\n\n" + SOURCE_SECTION.rstrip("\n") + "\n"
    if playable is None:
        return text
    # Owner 10-16: the count is a running total ("so far"), on its own line, not beside the 0.5.0 download or in the
    # release highlights. master's line has no number and links to home's STATUS.md, the one source.
    edits = [
        (r"\*\*Games rated Playable so far:\*\* \[the list, with progress charts\]\("
         + re.escape(BASE + "/blob/home/STATUS.md") + r"\)\.",
         "**%d games rated Playable so far.** [The list, with progress charts.](STATUS.md)" % playable),
        (r"(\| \[Compatibility\]\()", "| [Status](STATUS.md) | Every title's status, and how close the next "
                                      "release is, with charts |\n\\1"),
    ]
    for pat, rep in edits:
        n = len(re.findall(pat, text))
        if n != 1:
            raise RuntimeError("README: %r matched %d times, expected 1" % (pat, n))
        text = re.sub(pat, lambda m: m.expand(rep), text)
    return text


def update(status_blobs=None, playable=None):
    """Rebuild home from master's landing files plus `status_blobs` ({name: blob sha} for STATUS_FILES; files not given
    are kept from the current home). Moves refs/heads/home and returns the new commit, or None when unchanged."""
    have = subprocess.run(["git", "-C", G, "rev-parse", "-q", "--verify", "refs/heads/home"], capture_output=True, text=True)
    parent = have.stdout.strip() if have.returncode == 0 else None
    blobs = {}
    if parent:
        # -r: STATUS_FILES now includes paths under docs/ (homeroot1018, #433), invisible to a flat ls-tree.
        for ln in git("ls-tree", "-r", parent).decode().splitlines():
            meta, name = ln.split("\t", 1)
            if name in STATUS_FILES:
                blobs[name] = meta.split()[2]
    blobs.update(status_blobs or {})
    if playable is None and "STATUS.md" in blobs:
        m = re.search(r"Playable \*\*(\d+)\*\*", git("cat-file", "blob", blobs["STATUS.md"]).decode("utf-8"))
        playable = int(m.group(1)) if m else None
    fd, idx = tempfile.mkstemp(prefix="home-index-"); os.close(fd); os.unlink(idx)
    env = dict(os.environ, GIT_INDEX_FILE=idx)
    carry = set()
    files = [f for f in FILES if f not in OPTIONAL or kind(f) == "blob"]
    try:
        for f in files:
            data = git("show", "%s:%s" % (SRC, f))
            if f in REWRITE:
                # The PR template is pasted into a pull request's description, where a relative link resolves
                # against the PR's URL: its links stay absolute.
                text = rewrite(data.decode("utf-8"), f, carry, () if f.startswith(".github/") else set(files))
                if f == "README.md":
                    text = readme(text, playable)
                data = text.encode("utf-8")
            blob = git("hash-object", "-w", "--stdin", inp=data).decode().strip()
            git("update-index", "--add", "--cacheinfo", "100644,%s,%s" % (blob, RENAME.get(f, f)), env=env)
        for path in sorted(carry - set(files)):
            blob = git("rev-parse", "%s:%s" % (SRC, path)).decode().strip()
            git("update-index", "--add", "--cacheinfo", "100644,%s,%s" % (blob, path), env=env)
        for name, b in sorted(blobs.items()):
            git("update-index", "--add", "--cacheinfo", "100644,%s,%s" % (b, name), env=env)
        tree = git("write-tree", env=env).decode().strip()
    finally:
        if os.path.exists(idx):
            os.unlink(idx)
    if parent and git("rev-parse", parent + "^{tree}").decode().strip() == tree:
        return None
    src = git("rev-parse", "--short=10", SRC).decode().strip()
    msg = "home: landing page from master %s%s\n" % (src, ", status updated" if status_blobs else "")
    env = dict(os.environ, GIT_AUTHOR_NAME="hakuX status", GIT_AUTHOR_EMAIL="status@hakux.invalid",
               GIT_COMMITTER_NAME="hakuX status", GIT_COMMITTER_EMAIL="status@hakux.invalid")
    c = git("commit-tree", tree, *(["-p", parent] if parent else []), "-F", "-", inp=msg.encode(), env=env).decode().strip()
    git("update-ref", "refs/heads/home", c, *([parent] if parent else []))
    return c


if __name__ == "__main__":
    c = update()
    print(c or "unchanged")
