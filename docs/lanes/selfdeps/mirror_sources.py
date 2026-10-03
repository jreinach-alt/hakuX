#!/usr/bin/env python3
"""Mirror every external source the Android and desktop builds fetch.

The build must not need github.com, gitlab.com or crates.io at build time.
This script keeps a local mirror of each pinned source:

  <root>/git/<host>/<path>    bare `git clone --mirror` of each git source
  <root>/archives/<filename>  the exact archive each URL source is pinned to

<root> is $HAKUX_MIRRORS, else ~/hakux-work/mirrors.

Git sources are pointed at their mirror with url.<mirror>.insteadOf rules
(--insteadof writes them to the user's git config, or to --gitconfig FILE).
Archive sources are pointed at their mirror by the build itself: the
Android CMake files and the meson packagecache both look for the file here
first and fall back to the upstream URL when it is absent.

Sources are read from the meson wraps (subprojects/*.wrap), from the list of
CMake-only sources below, and from the submodules of the mirrored git
sources, so a new pin in the build is picked up on the next run.

Usage:
  mirror_sources.py                       clone or verify every mirror
  mirror_sources.py --update              also fetch new refs into existing mirrors
  mirror_sources.py --insteadof           write the git insteadOf rules (only for
                                          mirrors that exist: upstream stays the fallback)
  mirror_sources.py --gitconfig FILE      ... into FILE instead of ~/.gitconfig
  mirror_sources.py --check               verify only: no network, no writes
  mirror_sources.py --list                print the source table as markdown
"""

import argparse
import configparser
import glob
import hashlib
import os
import subprocess
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, "..", "..", ".."))
DEFAULT_ROOT = os.environ.get(
    "HAKUX_MIRRORS", os.path.join(os.path.expanduser("~"), "hakux-work", "mirrors"))

# Git sources the CMake build fetches that no wrap names. `master` is what the
# build asks for; the mirror holds whatever master is when it is refreshed.
CMAKE_GIT = [
    # android/app/src/main/cpp/CMakeLists.txt
    ("https://github.com/bylaws/libadrenotools", "master", "android/cmake:adrenotools"),
]

# Archive sources the CMake build fetches: (url, filename, sha256 or None, consumer).
CMAKE_ARCHIVES = [
    # android/app/src/main/cpp/CMakeLists.txt; only fetched when thirdparty/SDL2 is absent
    ("https://github.com/libsdl-org/SDL/archive/refs/tags/release-2.32.10.zip",
     "SDL-release-2.32.10.zip", None, "android/cmake:sdl2"),
    # android/app/src/main/cpp/CMakeLists.txt, ExternalProject_Add(glib_ep)
    ("https://download.gnome.org/sources/glib/2.66/glib-2.66.8.tar.xz",
     "glib-2.66.8.tar.xz",
     "97bc87dd91365589af5cbbfea2574833aea7a1b71840fd365ecd2852c76b9c8b",
     "android/cmake:glib"),
]

# Submodule discovery depth: a git source's .gitmodules, and theirs, and so on.
SUBMODULE_DEPTH = 3


def run(args, cwd=None, check=True):
    return subprocess.run(args, cwd=cwd, check=check, text=True,
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT)


def git_base(url):
    """Mirror path under <root>/git for an upstream URL: host/path, no .git."""
    rest = url.split("://", 1)[1]
    host, path = rest.split("/", 1)
    path = path.rstrip("/")
    if path.endswith(".git"):
        path = path[:-4]
    return host, path


def read_wraps():
    """Git and archive sources named by subprojects/*.wrap."""
    git, archives = [], []
    for wrap in sorted(glob.glob(os.path.join(REPO, "subprojects", "*.wrap"))):
        cp = configparser.ConfigParser(interpolation=None, inline_comment_prefixes=("#",))
        cp.read(wrap)
        name = os.path.basename(wrap)
        for sec in cp.sections():
            if sec == "provide":
                continue
            s = cp[sec]
            if "url" in s and "revision" in s:
                git.append((s["url"].strip(), s["revision"].strip(), "meson:" + name))
            if "source_url" in s:
                archives.append((s["source_url"].strip(), s["source_filename"].strip(),
                                 s.get("source_hash"), "meson:" + name))
            if "patch_url" in s and "patch_filename" in s:
                archives.append((s["patch_url"].strip(), s["patch_filename"].strip(),
                                 s.get("patch_hash"), "meson:" + name + " (wrapdb patch)"))
    return git, archives


def submodules_of(mirror, rev):
    """(url, consumer) for each submodule in the .gitmodules at rev."""
    out = run(["git", "-C", mirror, "config", "--blob", rev + ":.gitmodules",
               "--get-regexp", r"^submodule\..*\.url$"], check=False)
    if out.returncode != 0:
        return []
    urls = []
    for line in out.stdout.splitlines():
        parts = line.split(None, 1)
        if len(parts) == 2:
            urls.append(parts[1].strip())
    return urls


def normalise_git(sources):
    """Merge sources by mirror path; keep every upstream spelling as a key."""
    repos = {}
    for url, rev, consumer in sources:
        host, path = git_base(url)
        key = (host, path)
        repo = repos.setdefault(key, {"keys": set(), "revs": set(), "consumers": set()})
        repo["keys"].add("https://%s/%s" % (host, path))
        repo["keys"].add("https://%s/%s.git" % (host, path))
        repo["revs"].add(rev)
        repo["consumers"].add(consumer)
    return repos


def discover(repos, mirror_root, clone):
    """Clone (when clone is set) and then add the submodules of every git source,
    up to SUBMODULE_DEPTH levels. A submodule's .gitmodules is only readable
    once its parent is mirrored, so each level is cloned before it is read."""
    seen = set(repos)
    frontier = list(repos.items())
    for depth in range(SUBMODULE_DEPTH):
        nxt = []
        for (host, path), repo in frontier:
            if clone:
                ensure_git(host, path, repo, mirror_root, update=False)
            mirror = os.path.join(mirror_root, "git", host, path)
            if not os.path.isdir(mirror):
                continue
            for rev in repo["revs"] or {"HEAD"}:
                for url in submodules_of(mirror, rev):
                    sub = git_base(url)
                    owner = "submodule of %s/%s" % (host, path)
                    if sub in seen:
                        repos[sub]["keys"].update(["https://%s/%s" % sub,
                                                   "https://%s/%s.git" % sub])
                        repos[sub]["consumers"].add(owner)
                        continue
                    seen.add(sub)
                    repos[sub] = {"keys": {url, "https://%s/%s" % sub, "https://%s/%s.git" % sub},
                                  "revs": set(), "consumers": {owner}}
                    nxt.append((sub, repos[sub]))
        frontier = nxt
        if not frontier:
            break
    return repos


def ensure_git(host, path, repo, mirror_root, update):
    mirror = os.path.join(mirror_root, "git", host, path)
    url = "https://%s/%s" % (host, path)
    if not os.path.isdir(mirror):
        os.makedirs(os.path.dirname(mirror), exist_ok=True)
        print("clone  %s" % url, flush=True)
        run(["git", "clone", "--mirror", url + ".git", mirror])
    elif update:
        print("fetch  %s" % url, flush=True)
        run(["git", "-C", mirror, "fetch", "--prune", "origin"])
    missing = []
    for rev in sorted(repo["revs"]):
        if rev == "master" or rev == "HEAD":
            continue
        if run(["git", "-C", mirror, "cat-file", "-e", rev + "^{commit}"],
               check=False).returncode != 0:
            missing.append(rev)
    return mirror, missing


def sha256_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def ensure_archive(url, filename, want, root, dry):
    dest = os.path.join(root, "archives", filename)
    if os.path.exists(dest):
        got = sha256_of(dest)
        if want and got != want.lower():
            print("BAD    %s (sha256 %s, want %s)" % (filename, got, want), flush=True)
            return False
        return True
    if dry:
        print("absent %s" % filename, flush=True)
        return False
    print("fetch  %s" % url, flush=True)
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    tmp = dest + ".part"
    req = urllib.request.Request(url, headers={"User-Agent": "hakux-selfdeps"})
    with urllib.request.urlopen(req, timeout=120) as resp, open(tmp, "wb") as out:
        while True:
            chunk = resp.read(1 << 20)
            if not chunk:
                break
            out.write(chunk)
    got = sha256_of(tmp)
    if want and got != want.lower():
        os.remove(tmp)
        print("BAD    %s (sha256 %s, want %s)" % (filename, got, want), flush=True)
        return False
    os.replace(tmp, dest)
    print("sha256 %s  %s" % (got, filename), flush=True)
    return True


def write_insteadof(repos, mirror_root, gitconfig):
    """url.<mirror>.insteadOf <upstream> for every key. Longest prefix wins in git,
    so the .git and no-.git spellings both get their own rule."""
    scope = ["--file", gitconfig] if gitconfig else ["--global"]
    # Mirror rules rewrite to local paths. Git 2.38+ refuses the file transport
    # for submodule clones unless allowed, and libadrenotools has one
    # (lib/linkernsbypass), so the Android FetchContent fails without this.
    # Allowing file here is safe: every rewrite target is a local mirror.
    run(["git", "config"] + scope + ["protocol.file.allow", "always"])
    for (host, path), repo in sorted(repos.items()):
        base = os.path.join(mirror_root, "git", host, path)
        if not os.path.isdir(base):
            # No mirror: write no rule, so git falls back to the upstream URL.
            print("skip   %s/%s (no mirror; upstream used)" % (host, path), flush=True)
            continue
        section = "url.%s.insteadOf" % base
        existing = run(["git", "config"] + scope + ["--get-all", section],
                       check=False).stdout.split()
        for key in sorted(repo["keys"]):
            if key in existing:
                continue
            run(["git", "config"] + scope + ["--add", section, key])
            print("insteadOf %s -> %s" % (key, base), flush=True)


def table(repos, archives):
    print("| source | upstream | pin | consumer | github? |")
    print("|---|---|---|---|---|")
    for (host, path), repo in sorted(repos.items()):
        pins = ", ".join(sorted(repo["revs"])) or "(submodule pin)"
        gh = "yes" if host == "github.com" else "no"
        print("| %s | https://%s/%s | %s | %s | %s |" % (
            path.split("/")[-1], host, path, pins,
            ", ".join(sorted(repo["consumers"])), gh))
    for url, filename, want, consumer in archives:
        gh = "yes" if "github.com" in url else "no"
        print("| %s | %s | %s | %s | %s |" % (
            filename, url, (want or "")[:12] or "-", consumer, gh))


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--root", default=DEFAULT_ROOT)
    ap.add_argument("--update", action="store_true")
    ap.add_argument("--insteadof", action="store_true")
    ap.add_argument("--gitconfig")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--list", action="store_true")
    args = ap.parse_args()

    wrap_git, wrap_archives = read_wraps()
    repos = normalise_git(wrap_git + CMAKE_GIT)
    archives = wrap_archives + CMAKE_ARCHIVES

    if args.list:
        table(discover(repos, args.root, clone=False), archives)
        return 0

    bad = 0
    if not args.check:
        repos = discover(repos, args.root, clone=True)
        for (host, path), repo in sorted(repos.items()):
            _, missing = ensure_git(host, path, repo, args.root, args.update)
            if missing:
                bad += 1
                print("MISSING %s/%s: %s" % (host, path, ", ".join(missing)), flush=True)
        for url, filename, want, _ in archives:
            if not ensure_archive(url, filename, want, args.root, dry=False):
                bad += 1
    else:
        repos = discover(repos, args.root, clone=False)
        for (host, path), repo in sorted(repos.items()):
            mirror = os.path.join(args.root, "git", host, path)
            if not os.path.isdir(mirror):
                print("absent git %s/%s" % (host, path))
                bad += 1
                continue
            for rev in sorted(repo["revs"]):
                if rev in ("master", "HEAD"):
                    continue
                if run(["git", "-C", mirror, "cat-file", "-e", rev + "^{commit}"],
                       check=False).returncode != 0:
                    print("MISSING %s/%s @ %s" % (host, path, rev))
                    bad += 1
        for url, filename, want, _ in archives:
            if not ensure_archive(url, filename, want, args.root, dry=True):
                bad += 1

    if args.insteadof:
        write_insteadof(repos, args.root, args.gitconfig)

    print("sources: %d git, %d archives, %d problem(s)" % (len(repos), len(archives), bad))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
