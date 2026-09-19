#!/usr/bin/env python3
"""The open-issue and open-PR lists over REST, because GraphQL is not everywhere.

    from gh_rest import open_issues, open_prs
    issues, dropped_prs, err = open_issues(REPO)

WHY THIS EXISTS. `gh issue list` and `gh pr list` are GraphQL. In a Claude Code
cloud session the proxy refuses GraphQL wholesale and says so:

    HTTP 403: GitHub GraphQL is not available from Claude Code sessions;
    use the REST API (gh api repos/{owner}/{repo}/...)

REST on the same credential works there. So every caller that wanted a plain
list was, in that one environment, getting nothing -- and the callers that fail
open (check_coverage.py, fleet.py, backlog-gate.sh) fail open by design, which
means the gate reported a pass having done no work at all. Found by lane.remote
on PR #162, 2026-09-19, from the container where it bites hardest.

The fail-open is right and stays. What was wrong is that it was invisible, and
that it happened at all where REST would have answered.

THE TRAP, AND IT IS WHY THIS IS A MODULE AND NOT A ONE-LINER AT EACH SITE.
`GET /repos/{owner}/{repo}/issues` RETURNS PULL REQUESTS TOO. GitHub's data
model makes every PR an issue, and the endpoint hands both back; a PR is
distinguished only by carrying a `pull_request` key. Measured on this
repository 2026-09-19T21:0xZ: 31 rows came back, 8 of them pull requests, 23
genuine issues -- the same 23 `gh issue list` reports. Drop the filter and the
coverage gate starts demanding a tracker row and a lane for every open PR, and
goes red on work that is not an issue at all. That is a worse failure than the
one being fixed: the old bug made a gate silent, this one would make it wrong.

The filter is `pull_request is None`, not `not row.get("pull_request")`. An
empty dict is falsey and would read as "not a PR"; the key's PRESENCE is the
signal.

PAGINATION IS THE SAME BUG IN A DIFFERENT COAT. REST pages at 30 by default.
There are 23 open issues today; a gate that silently reads only the first page
is a gate that starts lying the day the backlog grows. So: `per_page=100`,
explicit `page=N`, and running out of pages is an ERROR rather than a
truncation -- a caller that cannot see the whole list must fail open loudly,
exactly as it does when the network is down. Silently short is the one answer
this module will not give.

`gh api --paginate` would also page, but it concatenates JSON documents and
hides the boundary, so a short read and a complete one look alike downstream.
Counting rows per page keeps the check where it can be asserted on.
"""
import json
import subprocess

PER_PAGE = 100
MAX_PAGES = 25          # 2500 rows; past that a person should be looking
TIMEOUT = 40            # per page, and the risk here is a stall, not the limit


def _api(path, timeout=TIMEOUT):
    """One REST GET through `gh api`. -> (parsed, None) or (None, reason).

    A reason is always a short single line: it ends up on a gate's summary
    line, next to the word that says the gate did not run.
    """
    try:
        out = subprocess.run(["gh", "api", path],
                             capture_output=True, text=True, timeout=timeout)
    except FileNotFoundError:
        return None, "gh is not installed"
    except subprocess.TimeoutExpired:
        return None, "gh did not answer within %ds (GET %s)" % (timeout, path)
    except Exception as e:
        return None, "could not run gh: %s" % e
    if out.returncode != 0:
        why = (out.stderr or out.stdout or "gh failed").strip()
        return None, (why.splitlines() or ["gh failed"])[0][:200]
    try:
        return json.loads(out.stdout), None
    except Exception as e:
        return None, "could not parse gh output: %s" % e


def _paged(repo, endpoint, query, per_page=PER_PAGE, max_pages=MAX_PAGES,
           timeout=TIMEOUT):
    """Every page of a REST list endpoint, or a reason it could not be read."""
    rows = []
    for page in range(1, max_pages + 1):
        batch, err = _api("repos/%s/%s?%s&per_page=%d&page=%d"
                          % (repo, endpoint, query, per_page, page), timeout)
        if err:
            return None, err
        if not isinstance(batch, list):
            # A dict here is GitHub's error envelope ({"message": ...}), which
            # `gh` hands back with a zero exit on some 200-with-body cases.
            msg = (batch or {}).get("message") if isinstance(batch, dict) else None
            return None, ("REST /%s returned %s, not a list%s"
                          % (endpoint, type(batch).__name__,
                             (": " + str(msg)[:120]) if msg else ""))
        rows.extend(batch)
        if len(batch) < per_page:
            return rows, None
    return None, ("/%s has more than %d rows over %d pages -- refusing to "
                  "report a truncated list" % (endpoint, max_pages * per_page,
                                               max_pages))


def open_issues(repo, **kw):
    """Open ISSUES -- pull requests removed. -> (rows, dropped_prs, None)
    or (None, 0, reason).

    Each row is {"number": int, "title": str}, the two fields every caller of
    the old `gh issue list --json number,title` used.
    """
    rows, err = _paged(repo, "issues", "state=open", **kw)
    if err:
        return None, 0, err
    issues = [{"number": r["number"], "title": r.get("title") or ""}
              for r in rows if r.get("pull_request") is None]
    return issues, len(rows) - len(issues), None


def open_prs(repo, **kw):
    """Open pull requests. -> (rows, None) or (None, reason).

    Normalised onto the field names `gh pr list --json` produced, so callers
    read the same keys they always did: number, headRefName, isDraft, labels,
    updatedAt, title.
    """
    rows, err = _paged(repo, "pulls", "state=open", **kw)
    if err:
        return None, err
    out = []
    for p in rows:
        out.append({
            "number": p["number"],
            "headRefName": (p.get("head") or {}).get("ref") or "",
            "isDraft": bool(p.get("draft")),
            "labels": [{"name": l.get("name")} for l in (p.get("labels") or [])],
            "updatedAt": p.get("updated_at") or "",
            "title": p.get("title") or "",
        })
    return out, None
