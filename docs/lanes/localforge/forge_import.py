#!/usr/bin/env python3
"""Import the GitHub issue log into the local forge, keeping every original number.

  forge_import.py [--recon DIR] [--ceiling N] [--board-ref REF] [--execute]

The issue and PR numbers come from one sequence, and Forgejo hands each new
issue the next free number. A number can only be kept by creating numbers in
order, 1..N, before anything else claims one. So this script walks 1..N. For
each number it uses the best record it has:

  1. lane.issuerecon's `<recon>/issues/<n>.json` (kind, title, body, state,
     labels, author, times, comments[]). Field names are read leniently.
  2. The board's tracker row, `<board-ref>:nv2a_issues.toml`. This gives a
     title, state and a rendering of the row. It is the seed until (1)
     exists.
  3. Neither: a closed placeholder, "#n: not recovered".

Numbers above the highest known one, up to --ceiling (default 640), become
closed placeholders labelled `reserved-number`. Forge-native issues and PRs
start above the ceiling, so a late-found GitHub number cannot collide with a
forge number.

The script is IDEMPOTENT. Each imported issue carries the marker
`<!-- forge-import:github#<n> -->` in its body:
  * a marked issue is updated in place: title, body, state, labels;
  * a comment is posted only if its `github-comment:<id>` marker is not
    already on the issue;
  * an issue without the marker is never touched.
It refuses to run (exit 3) if the forge's next free number is below a number
it still has to create but another actor already took that number.

Comments go in time order, posted by the forge user `ghimport`. Each opens
with a header line that names the original author and time. The forge's own
timestamps show when the import ran.

Dry run by default: it prints the plan and changes nothing. --execute writes.
"""
import argparse
import glob
import json
import os
import re
import subprocess
import sys
import tomllib
import urllib.error
import urllib.parse
import urllib.request

FORGE = os.environ.get("FORGE_URL", "http://127.0.0.1:3330")
TOKENS = os.environ.get("FORGE_TOKENS", os.path.expanduser("~/hakux-work/forge/tokens"))
IMPORT_USER = os.environ.get("FORGE_IMPORT_USER", "ghimport")
MARK = "<!-- forge-import:github#{n} -->"
CMARK = "<!-- github-comment:{id} -->"
OPEN_STATUSES = {"open", "fixed-part", "fixed-verified", "fixed", "unmodellable"}
LABEL_COLORS = {"github-import": "#c5def5", "github-pr": "#6f42c1", "not-recovered": "#ededed",
                "reserved-number": "#ededed", "seeded-from-board": "#bfd4f2"}


class Forge:
    def __init__(self, repo, user):
        self.repo = repo
        self.tok = open(os.path.join(TOKENS, user + ".token")).read().strip()

    def call(self, method, path, body=None, query=None):
        url = FORGE + "/api/v1" + path
        if query:
            url += "?" + urllib.parse.urlencode(query)
        req = urllib.request.Request(url, method=method, data=json.dumps(body).encode() if body is not None else None)
        req.add_header("Authorization", "token " + self.tok)
        req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                b = r.read()
                return json.loads(b) if b.strip() else None
        except urllib.error.HTTPError as e:
            sys.exit(f"forge_import: HTTP {e.code} on {method} {path}: {e.read()[:300]!r}")

    def all(self, path, query=None):
        out, page = [], 1
        while True:
            rows = self.call("GET", path, query=dict(query or {}, page=page, limit=50))
            out.extend(rows)
            if len(rows) < 50:
                return out
            page += 1

    def r(self, sub=""):
        return f"/repos/{self.repo}{sub}"


# ------------------------------------------------------------------ records

def pick(d, *keys, default=None):
    for k in keys:
        if isinstance(d, dict) and d.get(k) not in (None, ""):
            return d[k]
    return default


def login(a):
    if isinstance(a, dict):
        return a.get("login") or a.get("name") or "unknown"
    return str(a) if a else "unknown"


def load_recon(d):
    recs = {}
    for f in glob.glob(os.path.join(d, "issues", "*.json")):
        try:
            j = json.load(open(f))
        except (OSError, ValueError) as e:
            sys.exit(f"forge_import: unreadable recon file {f}: {e}")
        n = int(pick(j, "number", default=os.path.basename(f).split(".")[0]))
        st = str(pick(j, "state", default="")).lower()
        recs[n] = dict(
            source="recon", kind=str(pick(j, "kind", default="issue")).lower(),
            title=pick(j, "title"), body=pick(j, "body"),
            state=("closed" if st in ("closed", "merged") else "open" if st == "open" else None),
            merged=st == "merged" or bool(pick(j, "merged", "merged_at", "mergedAt")),
            labels=[l if isinstance(l, str) else l.get("name") for l in pick(j, "labels", default=[]) or []],
            author=login(pick(j, "author", "user")),
            created=pick(j, "created_at", "createdAt", "created"),
            closed=pick(j, "closed_at", "closedAt", "closed"),
            sources=pick(j, "source", "sources", default={}),
            comments=sorted(
                [dict(id=str(pick(c, "id", "comment_id", default="")), author=login(pick(c, "author", "user")),
                      created=pick(c, "created_at", "createdAt", default=""),
                      updated=pick(c, "updated_at", "updatedAt", default=""),
                      body=pick(c, "body", default=""), source=pick(c, "source", default=""))
                 for c in pick(j, "comments", default=[]) or []],
                key=lambda c: (c["created"] or "", c["id"])))
    return recs


def load_board(ref):
    txt = subprocess.run(["git", "show", f"{ref}:nv2a_issues.toml"], capture_output=True, text=True, check=True).stdout
    sha = subprocess.run(["git", "rev-parse", "--short", ref], capture_output=True, text=True).stdout.strip()
    rows = tomllib.loads(txt)["issue"]
    return {int(k): v for k, v in rows.items() if k.isdigit()}, sha, [k for k in rows if not k.isdigit()]


def render_row(n, row, ref, sha):
    lines = [f"Seeded from the board's tracker row `{ref}:nv2a_issues.toml` @ {sha}. "
             f"The original issue body was not recovered yet. lane.issuerecon's import will replace this text.",
             "", "| field | value |", "|---|---|"]
    for k in ("status", "disposition", "component", "dispatch_state", "suites", "no_suites", "fixed_by",
              "impact_px", "impact_onestep_px", "impact_basis", "game_visible", "blocker_tested",
              "blocker_falsifier"):
        if k in row and row[k] not in ("", [], None):
            v = ", ".join(row[k]) if isinstance(row[k], list) else str(row[k])
            lines.append(f"| {k} | {v.replace('|', '¦').replace(chr(10), ' ')} |")
    for k in ("status_note", "blocked_on"):
        if row.get(k):
            lines += ["", f"**{k}**", "", str(row[k]).replace(" || ", "\n\n")]
    return "\n".join(lines)


def plan_for(n, recon, board, ref, sha, known_max):
    """-> dict(title, body, state, labels, comments, kind)."""
    r, row = recon.get(n), board.get(n)
    mark = MARK.format(n=n)
    if r and (r.get("title") or r.get("body") or r.get("comments")):
        kind = "pr" if r["kind"] in ("pr", "pull", "pull_request") else "issue"
        src = r.get("sources")
        src = ", ".join(sorted(set(src.values()) if isinstance(src, dict) else src if isinstance(src, list) else [str(src)])) if src else "transcripts"
        head = (f"{mark}\n> **GitHub {'PR' if kind == 'pr' else 'issue'} #{n}**"
                f" opened by @{r['author']}" + (f" on {r['created']}" if r.get("created") else "")
                + (f"; {'merged' if r.get('merged') else 'closed'} {r['closed']}" if r.get("closed") else "")
                + f". Recovered by lane.issuerecon from: {src}.\n"
                f"> Imported into the local forge by lane.localforge. The forge's dates are the import's, not GitHub's.")
        body = head + "\n\n" + (r.get("body") or "_(body not recovered)_")
        if row:
            body += ("\n\n<details><summary>Board tracker row (nv2a_issues.toml @ " + sha + ")</summary>\n\n"
                     + render_row(n, row, ref, sha) + "\n\n</details>")
        title = r.get("title") or (row or {}).get("title") or f"#{n}: title not recovered"
        if kind == "pr":
            title = f"[GitHub PR] {title}"
        labels = ["github-import"] + (["github-pr"] if kind == "pr" else []) + [l for l in r["labels"] if l]
        state = r.get("state") or ("open" if row and row.get("status") in OPEN_STATUSES else "closed" if row else "open")
        return dict(title=title, body=body, state=state, labels=labels, comments=r["comments"], kind=kind)
    if row:
        head = (f"{mark}\n> **GitHub issue #{n}**, seeded from the board tracker row only. "
                f"Imported into the local forge by lane.localforge.")
        st = "open" if row.get("status") in OPEN_STATUSES else "closed"
        return dict(title=row["title"], body=head + "\n\n" + render_row(n, row, ref, sha), state=st,
                    labels=["github-import", "seeded-from-board"], comments=[], kind="issue")
    if n <= known_max:
        return dict(title=f"#{n}: not recovered",
                    body=f"{mark}\nNo record of GitHub #{n} (issue or PR) has been recovered. The number is kept "
                         f"so that every later number matches GitHub's.",
                    state="closed", labels=["github-import", "not-recovered"], comments=[], kind="placeholder")
    return dict(title=f"#{n}: reserved (no GitHub record)",
                body=f"{mark}\nNo GitHub issue or PR #{n} is known. The highest known is #{known_max}. "
                     f"Numbers up to the import ceiling are reserved, so that a GitHub number found later "
                     f"cannot collide with a forge-native one. Forge-native issues and PRs start above the ceiling.",
                state="closed", labels=["github-import", "reserved-number"], comments=[], kind="placeholder")


def tier(body):
    """How good an imported body's source is: 2 recovered, 1 board seed, 0 placeholder."""
    body = body or ""
    return 2 if "Recovered by lane.issuerecon" in body else 1 if "seeded from the board tracker row" in body else 0


def comment_body(c):
    head = (CMARK.format(id=c["id"]) + f"\n> **@{c['author']}** commented on GitHub"
            + (f" at {c['created']}" if c.get("created") else "")
            + (f" (edited {c['updated']})" if c.get("updated") and c.get("updated") != c.get("created") else "")
            + (f" · comment {c['id']}" if c.get("id") else "") + (f" · recovered from {c['source']}" if c.get("source") else ""))
    return head + "\n\n" + (c.get("body") or "")


# ------------------------------------------------------------------ main

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=os.environ.get("GH_REPO", "jreinach-alt/hakuX"))
    ap.add_argument("--recon", default=None, help="lane.issuerecon's forge-import dir")
    ap.add_argument("--ceiling", type=int, default=640)
    ap.add_argument("--board-ref", default="origin/board")
    ap.add_argument("--through", type=int, default=None, help="stop after this number (tests only)")
    ap.add_argument("--execute", action="store_true")
    a = ap.parse_args()

    board, sha, skipped = load_board(a.board_ref)
    recon = load_recon(a.recon) if a.recon else {}
    known_max = max(list(board) + list(recon) + [629])  # #629: the highest number git history names (hddcrash's PR)
    top = max(a.ceiling, known_max)
    if a.through:
        top = min(top, a.through)
    fg = Forge(a.repo, IMPORT_USER)
    existing = {i["number"]: i for i in fg.all(fg.r("/issues"), dict(state="all", type="issues"))}
    prs = {p["number"]: p for p in fg.all(fg.r("/pulls"), dict(state="all"))}
    taken = set(existing) | set(prs)
    nxt = max(taken) + 1 if taken else 1
    print(f"board rows {len(board)} (non-numeric, not imported: {', '.join(skipped)}); recon records {len(recon)}; "
          f"known max #{known_max}; ceiling #{top}; forge has {len(existing)} issues + {len(prs)} PRs, next free #{nxt}")
    missing = [n for n in range(1, top + 1) if n not in taken]
    if missing and missing[0] < nxt:
        print(f"forge_import: REFUSED: #{missing[0]} must still be created but the forge would assign #{nxt} "
              f"(another actor created issues first)", file=sys.stderr)
        sys.exit(3)
    for n in range(1, top + 1):
        if n in prs and n not in existing:
            sys.exit(f"forge_import: #{n} is a forge PR inside the import range; refusing")

    labels = {l["name"]: l for l in fg.all(fg.r("/labels"))}

    def label_ids(names):
        out = []
        for nm in dict.fromkeys(names):
            if nm not in labels:
                if a.execute:
                    labels[nm] = fg.call("POST", fg.r("/labels"), dict(name=nm, color=LABEL_COLORS.get(nm, "#ededed"),
                                                                         description="created by the GitHub import"))
                else:
                    labels[nm] = dict(id=-1, name=nm)
            out.append(labels[nm]["id"])
        return out

    stats = dict(created=0, updated=0, unchanged=0, comments=0, foreign=0)
    for n in range(1, top + 1):
        p = plan_for(n, recon, board, a.board_ref, sha, known_max)
        cur = existing.get(n)
        if cur is None:
            if a.execute:
                it = fg.call("POST", fg.r("/issues"), dict(title=p["title"], body=p["body"], labels=label_ids(p["labels"]),
                                                          closed=p["state"] == "closed"))
                if it["number"] != n:
                    sys.exit(f"forge_import: wanted #{n}, forge assigned #{it['number']}; stopping")
                if p["state"] == "closed" and it.get("state") != "closed":
                    fg.call("PATCH", fg.r(f"/issues/{n}"), dict(state="closed"))
            stats["created"] += 1
            have_c = set()
        else:
            if MARK.format(n=n) not in (cur.get("body") or ""):
                stats["foreign"] += 1
                print(f"#{n}: not an imported issue (no marker); left alone")
                continue
            want_l = set(p["labels"])
            have_l = {l["name"] for l in cur.get("labels") or []}
            if tier(cur.get("body")) > tier(p["body"]):
                # never downgrade: a run without --recon must not replace recovered text with the seed
                stats["unchanged"] += 1
                p["comments"] = []
            elif (cur.get("title"), cur.get("body"), cur.get("state")) != (p["title"], p["body"], p["state"]) or want_l - have_l:
                if a.execute:
                    fg.call("PATCH", fg.r(f"/issues/{n}"), dict(title=p["title"], body=p["body"], state=p["state"]))
                    # replace import-owned labels; keep labels a job added since (fold-ready, lane:x, ...)
                    ownable = {"not-recovered", "reserved-number", "seeded-from-board"}
                    keep = [l for l in have_l if l not in ownable]
                    fg.call("PUT", fg.r(f"/issues/{n}/labels"), dict(labels=label_ids(sorted(set(keep) | want_l))))
                stats["updated"] += 1
            else:
                stats["unchanged"] += 1
            have_c = set()
            if p["comments"]:
                for c in fg.all(fg.r(f"/issues/{n}/comments")):
                    m = re.search(r"<!-- github-comment:([^ ]*) -->", c.get("body") or "")
                    if m:
                        have_c.add(m.group(1))
        for c in p["comments"]:
            if c["id"] and c["id"] in have_c:
                continue
            if a.execute:
                fg.call("POST", fg.r(f"/issues/{n}/comments"), dict(body=comment_body(c)))
            stats["comments"] += 1
    print(("EXECUTED: " if a.execute else "DRY RUN (nothing written): ") +
          ", ".join(f"{k} {v}" for k, v in stats.items()))


if __name__ == "__main__":
    main()
