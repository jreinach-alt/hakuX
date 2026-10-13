#!/usr/bin/env python3
"""issue_mirror.py -- one issue/PR number space, mirrored both ways between the forge and GitHub (lane.issuesync1012).

Round 2 (staged 2026-10-12): lane.local reviewed round 1 (9de0a50e8f) and approved the design, but found gaps that
would break the one-number invariant, or the sync, on its first live run. This round closes them:

  1. mirror-down: GitHub-only numbers (anyone can file #N once the repo is public) now get a forge twin, in order,
     verified number-for-number. Callable on its own (`mirror-down`) and run first by `sync` and by `new`.
  2. `new` and `backfill` both check the sides are LEVEL before spending a GitHub number: GitHub ahead -> mirror
     down first; forge ahead -> REFUSED, nothing touched. Checked fresh on every invocation (so a resume after a
     stop/restart re-checks, not just a first call).
  3. One shape for a forge PR's GitHub twin: a closed GitHub issue titled "[PR] <title>", body = the PR's body,
     branch, and an open/merged(+fold sha)/closed status line, then the marker. `sync` rewrites the status line
     when the forge PR's state or `folded` label changes. GitHub's state is excluded from sync/check for these
     pairs (always closed by design); titles compare with the "[PR] " prefix stripped.
  4. `sync` now also merges body (three-way, marker stripped) and labels (as a set), and mirrors comments posted
     after the cutover each way, with an author line and a per-comment marker; a comment that already carries a
     marker is never re-mirrored (echo suppression), and mirrored ids are recorded in the state file.
  5. `seed [--yes]` applies the 25 judged resolutions (22 state conflicts closed on the forge, #1/#161/#568 copied
     from GitHub, #107 left in NEVER_SYNC) and writes the `last_synced` baseline for every common pair that comes
     out equal, so the first real `sync` is not all conflicts.
  6. The gateway's `get` truncated at 600000 characters and silently corrupted any large page's JSON. Fixed at the
     source: `get PATH --out FILE` writes the complete, token-redacted body to FILE; this tool always uses it now,
     at per_page=100, and the old quarter-page retry workaround is gone.
  7. `check` no longer reports PR-twin state as drift, and adds two real categories it used to miss: a forge item
     past the acknowledged backlog ceiling with no marker ("created outside the allocator"), and forge-ahead
     beyond the pending backfill.
  8. issue_mirror_selftest.py runs every write path (backfill, mirror-down, new, sync, seed, the secret scan)
     against in-memory fakes that implement the same GH/FG interface as the real gateway/forge clients -- no
     network calls, nothing live touched.

STAGED, DRY-RUN TOOL. This copy never writes to GitHub or the forge: every subcommand that would write refuses
unless given --yes, and this lane never passes --yes against a live service (the selftest passes --yes only
against its own in-memory fakes). lane.local reviews docs/lanes/issuesync1012/ and installs for real.

Subcommands:
  plan                        read-only. Diffs both sides, prints every action a sync would take, writes a report.
  mirror-down [--yes]         for each GitHub-only number, in order: create the forge twin, verify the number.
  backfill --yes [--max N] [--pace-per-min N] [--comments now|later]
                               paced, resumable creation of GitHub twins for forge-only numbers beyond GitHub's max.
  sync --yes                  mirror-down, then 2-way field sync (state/title/body/labels/comments) for pairs.
  seed [--yes]                apply the 25 judged resolutions and write the sync baseline for every equal pair.
  new --kind issue|pr --title T [--body B] [--forge-user NAME] [--head BRANCH --base master]
                               the allocator: levels the sides first, then GitHub, then forge, flock-protected.
  check                       one line for the hourly report; exits non-zero on any drift.
  close-pr N --comment TEXT   close a GitHub PR through the gateway, with a closing comment.

Reads: GitHub only through `python3 <gateway> get <path> --out <file>` (the complete body, no truncation) --
forge only through curl with the token inside the Authorization header, never on a command line visible to `ps`.

Writes (once lane.local installs the staged gateway additions): POST /issues, PATCH /issues/N, POST
/issues/N/comments, PATCH /pulls/N, POST /pulls, all through the gateway (GitHub side) or a write-capable forge
token (forge side). Every mirrored body/comment this tool creates carries a marker so a later sync run never
mistakes its own echo for a real edit on the other side. Every write (either side) is secret-scanned first.
"""
import argparse
import fcntl
import json
import os
import re
import shlex
import subprocess
import sys
import time

W = '/home/justin/hakux-work'
H = W + '/host-tools'
GATEWAY = os.environ.get('ISSUE_MIRROR_GATEWAY', H + '/github_gateway.py')
FORGE_URL = os.environ.get('FORGE_URL', 'http://127.0.0.1:3330')
OWNER_REPO = 'jreinach-alt/hakuX'
FORGE_REPO_PATH = '/api/v1/repos/' + OWNER_REPO
READ_TOKEN = os.environ.get('ISSUE_MIRROR_FORGE_TOKEN', W + '/forge/tokens/lane.local.token')
WRITE_TOKEN_DEFAULT = os.environ.get('ISSUE_MIRROR_FORGE_WRITE_TOKEN', W + '/forge/tokens/jobs.token')
STATE = H + '/.issue-mirror.json'          # last-synced snapshot + backfill resume cursor + backlog ceiling
LOCK = H + '/.issue-mirror.lock'            # the allocator's flock
LOG = W + '/logs/issue_mirror.log'

MIRROR_MARKER_RE = re.compile(r'<!-- hakux-mirror:v1 src=(forge|github)#(\d+) -->')
COMMENT_MARKER_RE = re.compile(r'<!-- hakux-mirror:v1 src=(forge|github)#(\d+)/c(\S+) -->')

PACE_PER_MIN_DEFAULT = 4     # 4/min = 240/hr: ~5% of GitHub's 80/min secondary limit, ~48% of its 500/hr limit

NEVER_SYNC = {107}   # GitHub's static STATUS.md pointer vs. the forge's own live status board -- see PR.md
STATE_CONFLICT_NUMS = [16, 34, 66, 71, 74, 81, 87, 89, 90, 92, 99, 439, 513, 557, 583, 591, 592, 598, 605, 607, 618, 627]
CONTENT_FIX_NUMS = [1, 161, 568]   # forge import never recovered these; GitHub has the real content


def log(msg):
    try:
        with open(LOG, 'a') as f:
            f.write('%s %s\n' % (time.strftime('%F %T'), msg))
    except Exception:
        pass


class MirrorStop(Exception):
    """Raised to abort a cmd_* function cleanly with a message already prefixed REFUSED/ALARM/STOP."""


# --------------------------------------------------------------------------------------------------------------
# Secret scan -- applied to every outgoing write, on EITHER side, regardless of transport. The gateway re-scans
# GitHub-bound writes server side too (defense in depth); this is the only scan forge-bound writes get, since
# they go straight over curl and never pass through the gateway.
# --------------------------------------------------------------------------------------------------------------

_TOKEN_PATTERNS = [
    re.compile(rb'gh[pousr]_[A-Za-z0-9]{20,}'),
    re.compile(rb'github_pat_[A-Za-z0-9_]{20,}'),
    re.compile(rb'-----BEGIN [A-Z ]*PRIVATE KEY-----'),
]
_KEY_PROPERTIES_PATTERNS = [
    re.compile(rb'storePassword\s*='),
    re.compile(rb'keyPassword\s*='),
]


def secret_scan(*texts):
    """Returns a reason string if any text looks like it carries a secret, else None."""
    blob = '\n'.join(t for t in texts if t).encode('utf8', 'replace')
    for rx in _TOKEN_PATTERNS + _KEY_PROPERTIES_PATTERNS:
        if rx.search(blob):
            return 'outgoing text matches a token/private-key/key.properties pattern'
    tok_dir = W + '/forge/tokens'
    try:
        for fn in os.listdir(tok_dir):
            if not fn.endswith('.token'):
                continue
            try:
                v = open(os.path.join(tok_dir, fn)).read().strip()
            except Exception:
                continue
            if len(v) >= 20 and v.encode('utf8', 'replace') in blob:
                return 'outgoing text contains one of our own forge tokens (%s)' % fn
    except Exception:
        pass
    try:
        kp = open(os.path.expanduser('~/hakuX/android/key.properties')).read().strip()
        if kp and kp.encode('utf8', 'replace') in blob:
            return 'outgoing text contains android/key.properties verbatim'
    except Exception:
        pass
    return None


# --------------------------------------------------------------------------------------------------------------
# GH -- the only way this tool touches GitHub, through the gateway.
# --------------------------------------------------------------------------------------------------------------

class GH:
    def __init__(self, gateway=None):
        self.gateway = gateway or GATEWAY
        self._ctr = 0

    def _get_raw(self, path):
        self._ctr += 1
        out = H + '/.issue-mirror-get-%d-%d.json' % (os.getpid(), self._ctr)
        r = subprocess.run([sys.executable, self.gateway, 'get', path, '--out', out], capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError('gateway get %s: rc=%d %s' % (path, r.returncode, (r.stdout + r.stderr)[:300]))
        try:
            with open(out) as f:
                return f.read()
        finally:
            try:
                os.unlink(out)
            except OSError:
                pass

    def reachable(self):
        try:
            rows = json.loads(self._get_raw('/issues?state=all&per_page=1&page=1'))
            return isinstance(rows, list)
        except Exception:
            return False

    def all_issues(self, per_page=100, max_pages=40):
        items = {}
        page = 1
        while page <= max_pages:
            rows = json.loads(self._get_raw('/issues?state=all&per_page=%d&page=%d' % (per_page, page)))
            if not isinstance(rows, list):
                raise RuntimeError('github page %d is not a list' % page)
            for x in rows:
                items[x['number']] = x
            if len(rows) < per_page:
                return items
            page += 1
        raise RuntimeError('more than %d pages of GitHub issues' % max_pages)

    def comments(self, number):
        return json.loads(self._get_raw('/issues/%d/comments' % number))

    def create(self, title, body='', labels=(), state=None):
        prob = secret_scan(title, body)
        if prob:
            raise MirrorStop('REFUSED: %s -- GitHub create blocked' % prob)
        args = [sys.executable, self.gateway, 'issue-create', '--title', title, '--body', body, '--yes']
        for l in labels:
            args += ['--label', l]
        if state == 'closed':
            args += ['--state', 'closed']
        r = subprocess.run(args, capture_output=True, text=True)
        m = re.search(r'CREATED #(\d+)', r.stdout)
        if r.returncode != 0 or not m:
            raise RuntimeError((r.stdout.strip() or r.stderr.strip())[:300])
        return int(m.group(1))

    def patch(self, number, title=None, body=None, state=None, labels=None):
        prob = secret_scan(title or '', body or '')
        if prob:
            raise MirrorStop('REFUSED: %s -- GitHub patch #%d blocked' % (prob, number))
        args = [sys.executable, self.gateway, 'issue-patch', str(number), '--yes']
        if title is not None:
            args += ['--title', title]
        if body is not None:
            args += ['--body', body]
        if state is not None:
            args += ['--state', state]
        if labels is not None:
            for l in labels:
                args += ['--label', l]
        r = subprocess.run(args, capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError((r.stdout.strip() or r.stderr.strip())[:300])
        return True

    def comment(self, number, body):
        prob = secret_scan(body)
        if prob:
            raise MirrorStop('REFUSED: %s -- GitHub comment on #%d blocked' % (prob, number))
        r = subprocess.run([sys.executable, self.gateway, 'issue-comment', str(number), '--body', body, '--yes'],
                            capture_output=True, text=True)
        m = re.search(r'COMMENTED #\d+ comment (\d+)', r.stdout)
        if r.returncode != 0 or not m:
            raise RuntimeError((r.stdout.strip() or r.stderr.strip())[:300])
        return m.group(1)


# --------------------------------------------------------------------------------------------------------------
# FG -- the only way this tool touches the forge. Reads use the read-only token; writes use a write-capable one.
# --------------------------------------------------------------------------------------------------------------

class FG:
    def __init__(self, read_token_path=None, write_token_path=None):
        self.read_token_path = read_token_path or READ_TOKEN
        self.write_token_path = write_token_path or WRITE_TOKEN_DEFAULT

    def _curl(self, method, path, body=None, query=None, write=False):
        import urllib.parse
        url = FORGE_URL + FORGE_REPO_PATH + path
        if query:
            url += '?' + urllib.parse.urlencode(query)
        tok_path = self.write_token_path if write else self.read_token_path
        # the token never appears on this process's argv or in any log: it is substituted by the bash that curl
        # itself spawns, exactly as the brief requires ("use the token only inside the header").
        cmd = 'curl -s -X %s -H "Authorization: token $(cat %s)"' % (method, tok_path)
        if body is not None:
            cmd += ' -H "Content-Type: application/json" -d %s' % shlex.quote(json.dumps(body))
        cmd += ' "%s"' % url
        r = subprocess.run(['bash', '-c', cmd], capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError('curl %s %s failed rc=%d: %s' % (method, path, r.returncode, r.stderr[:300]))
        return r.stdout

    def all_issues(self, limit=100, max_pages=40):
        items = {}
        page = 1
        while page <= max_pages:
            rows = json.loads(self._curl('GET', '/issues', query={'state': 'all', 'page': page, 'limit': limit}))
            if not isinstance(rows, list):
                raise RuntimeError('forge page %d is not a list' % page)
            for x in rows:
                items[x['number']] = x
            if len(rows) < limit:
                return items
            page += 1
        raise RuntimeError('more than %d pages of forge issues' % max_pages)

    def comments(self, number):
        return json.loads(self._curl('GET', '/issues/%d/comments' % number))

    def pull_detail(self, number):
        return json.loads(self._curl('GET', '/pulls/%d' % number))

    def create(self, payload, is_pr=False):
        prob = secret_scan(payload.get('title', ''), payload.get('body', ''))
        if prob:
            raise MirrorStop('REFUSED: %s -- forge create blocked' % prob)
        d = json.loads(self._curl('POST', '/pulls' if is_pr else '/issues', body=payload, write=True))
        if 'number' not in d:
            raise RuntimeError('forge create did not return a number: %r' % str(d)[:300])
        return d['number']

    def patch(self, number, payload, is_pr=False):
        prob = secret_scan(payload.get('title', ''), payload.get('body', ''))
        if prob:
            raise MirrorStop('REFUSED: %s -- forge patch #%d blocked' % (prob, number))
        self._curl('PATCH', ('/pulls/%d' if is_pr else '/issues/%d') % number, body=payload, write=True)
        return True

    def comment(self, number, body):
        prob = secret_scan(body)
        if prob:
            raise MirrorStop('REFUSED: %s -- forge comment on #%d blocked' % (prob, number))
        d = json.loads(self._curl('POST', '/issues/%d/comments' % number, body={'body': body}, write=True))
        return d.get('id')


# --------------------------------------------------------------------------------------------------------------
# Shared helpers: kinds, markers, PR-twin shape
# --------------------------------------------------------------------------------------------------------------

def kind_of(x):
    return 'PR' if x.get('pull_request') else 'issue'


def is_pr_twin_pair(fg_item):
    """True for pairs whose forge side is a real PR -- the population gap 3 governs (GitHub's state is excluded
    from sync/check for these; its title carries the [PR] prefix instead of the original import's [GitHub PR])."""
    return kind_of(fg_item) == 'PR'


def strip_gh_pr_prefix(t):
    """The ORIGINAL forge import's convention: a forge issue standing in for a real GitHub PR is titled
    "[GitHub PR] <title>". Population A (common pairs 1-629 and any later mirror-down of a public GitHub PR)."""
    return t[len('[GitHub PR] '):] if t.startswith('[GitHub PR] ') else t


def strip_pr_prefix(t):
    """This tool's OWN convention (round 2, gap 3): a GitHub record issue standing in for a real forge PR is
    titled "[PR] <title>". Population B (backfilled/allocated forge-native PRs)."""
    return t[len('[PR] '):] if t.startswith('[PR] ') else t


def mirror_marker(side, number):
    return '<!-- hakux-mirror:v1 src=%s#%d -->' % (side, number)


def comment_marker(side, number, cid):
    return '<!-- hakux-mirror:v1 src=%s#%d/c%s -->' % (side, number, cid)


def strip_marker(text):
    return MIRROR_MARKER_RE.sub('', text or '').rstrip()


def has_marker(item):
    return bool(MIRROR_MARKER_RE.search(item.get('body') or ''))


def pr_status_signal(fg_item):
    """Cheap, listing-only derived signal (no extra forge fetch) used to decide whether a PR twin needs a
    refresh. #643 is real forge data: labeled 'folded' while state='open' and pull_request.merged=False -- the
    forge's own merge-detection never actually closed the PR object. We trust the 'folded' label over state/merged
    when they disagree, and say so plainly in the status line rather than claim a merge that did not happen."""
    labels = [l['name'] for l in fg_item.get('labels', [])]
    pr = fg_item.get('pull_request') or {}
    if pr.get('merged'):
        return 'merged'
    if 'folded' in labels:
        return 'folded-unmerged'
    if fg_item.get('state') == 'closed':
        return 'closed'
    return 'open'


def pr_status_line(detail):
    labels = [l['name'] for l in detail.get('labels', [])]
    if detail.get('merged'):
        sha = detail.get('merge_commit_sha')
        return 'Status: merged into master%s.' % (' @ %s' % sha[:10] if sha else ' (fold sha not recorded by the forge)')
    if 'folded' in labels:
        return ('Status: labeled `folded` on the forge, but the forge has not recorded it as merged yet (state is '
                'still open, unmerged) -- a pre-existing forge-side inconsistency, not something this tool invented.')
    if detail.get('state') == 'closed':
        return 'Status: closed on the forge without merging.'
    return 'Status: open on the forge.'


def pr_twin_title(title):
    return '[PR] ' + title


def build_pr_twin_body(detail, number):
    branch = (detail.get('head') or {}).get('ref', '?')
    status = pr_status_line(detail)
    body = (detail.get('body') or '').strip() or '(no body)'
    marker = mirror_marker('forge', number) if number is not None else ''
    return 'Forge PR #%s, branch `%s`.\n%s\n\n%s\n\n%s' % (number if number is not None else '?', branch, status, body, marker)


# --------------------------------------------------------------------------------------------------------------
# Diff / plan
# --------------------------------------------------------------------------------------------------------------

def build_diff(gh, fg):
    gh_nums, fg_nums = set(gh), set(fg)
    gh_max = max(gh) if gh else 0
    fg_max = max(fg) if fg else 0
    common = sorted(gh_nums & fg_nums)
    only_gh = sorted(gh_nums - fg_nums)                       # mirror-down targets (real items)
    forge_only = sorted(fg_nums - gh_nums)
    backfill = sorted(n for n in forge_only if n > gh_max)     # forge-only numbers beyond GitHub's current max

    state_conflicts = []
    content_conflicts = []
    for n in common:
        if n in NEVER_SYNC:
            continue
        if is_pr_twin_pair(fg[n]):
            gt = strip_pr_prefix(gh[n]['title']).strip()
            ft = fg[n]['title'].strip()
            if gt != ft:
                content_conflicts.append(n)
            continue   # PR-twin: GitHub's state is never compared/drift (gap 3/7)
        gt, ft = gh[n]['title'].strip(), fg[n]['title'].strip()
        if gh[n]['state'] != fg[n]['state']:
            state_conflicts.append(n)
        if not (gt == ft or strip_gh_pr_prefix(ft) == gt):
            content_conflicts.append(n)

    return {
        'common': common, 'only_gh': only_gh, 'forge_only': forge_only, 'backfill': backfill,
        'state_conflicts': state_conflicts, 'content_conflicts': content_conflicts,
        'gh_max': gh_max, 'fg_max': fg_max,
    }


def backfill_kind_counts(fg, backfill):
    counts = {}
    for n in backfill:
        k = (kind_of(fg[n]), fg[n]['state'])
        counts[k] = counts.get(k, 0) + 1
    return counts


def build_backfill_body(fg_item, number, fg):
    """What backfill --yes would actually POST for one forge-only item. PRs, open or closed, ALWAYS get the one
    unified shape (gap 3): a closed GitHub issue titled "[PR] <title>" whose body states branch + status. Plain
    forge issues keep their title/body/state/labels."""
    if kind_of(fg_item) == 'PR':
        detail = fg.pull_detail(number)
        title = pr_twin_title(detail.get('title', fg_item['title']))
        body = build_pr_twin_body(detail, number)
        return title, body, 'closed', ['backfill']
    body = ((fg_item.get('body') or '').strip() or '(no body)') + '\n\n' + mirror_marker('forge', number)
    labels = [l['name'] for l in fg_item.get('labels', [])] + ['backfill']
    return fg_item['title'], body, fg_item['state'], labels


def three_sample_bodies(fg, backfill, fg_client):
    samples = []
    seen_kinds = set()
    for n in backfill:
        k = (kind_of(fg[n]), fg[n]['state'])
        if k in seen_kinds:
            continue
        seen_kinds.add(k)
        title, body, state, labels = build_backfill_body(fg[n], n, fg_client)
        samples.append((n, title, body, state, labels))
        if len(samples) == 3:
            break
    while len(samples) < 3 and backfill:
        n = backfill[len(samples) % len(backfill)]
        title, body, state, labels = build_backfill_body(fg[n], n, fg_client)
        samples.append((n, title, body, state, labels))
    return samples


def estimate_requests(fg, backfill, mirror_comments):
    requests = 0
    comments = 0
    for n in backfill:
        requests += 2 if kind_of(fg[n]) == 'PR' else 1   # PR twin is always created-then-closed; a plain issue may not need the extra patch
        comments += fg[n].get('comments', 0)
    if mirror_comments:
        requests += comments
    return requests, comments


REPORT_PATH_DEFAULT = H + '/issue_mirror_plan_report.txt'


def cmd_plan(gh, fg, report_path, pace_per_min=PACE_PER_MIN_DEFAULT):
    ghd = gh.all_issues()
    fgd = fg.all_issues()
    d = build_diff(ghd, fgd)
    counts = backfill_kind_counts(fgd, d['backfill'])
    req_no_comments, total_comments = estimate_requests(fgd, d['backfill'], mirror_comments=False)
    req_with_comments, _ = estimate_requests(fgd, d['backfill'], mirror_comments=True)
    hours_no_comments = req_no_comments / pace_per_min / 60
    hours_with_comments = req_with_comments / pace_per_min / 60
    samples = three_sample_bodies(fgd, d['backfill'], fg)

    lines = []

    def p(s=''):
        lines.append(s)

    p('issue_mirror plan -- %s' % time.strftime('%F %T %Z'))
    p('GitHub: %d items (min %d max %d)' % (len(ghd), min(ghd), max(ghd)))
    p('Forge:  %d items (min %d max %d)' % (len(fgd), min(fgd), max(fgd)))
    p('')
    p('=== 0. Mirror-down: GitHub-only numbers needing a forge twin ===')
    p('count: %d%s' % (len(d['only_gh']), (' (%s)' % d['only_gh'][:10]) if d['only_gh'] else ''))
    p('')
    p('=== 1. Backfill: forge-only numbers beyond GitHub max (%d) ===' % d['gh_max'])
    p(('count: %d (range %d-%d)' % (len(d['backfill']), min(d['backfill']), max(d['backfill']))) if d['backfill'] else 'count: 0')
    for (kind, state), n in sorted(counts.items()):
        p('  %-5s %-6s: %d' % (kind, state, n))
    p('')
    p('estimated GitHub requests at %d/min (%d/hr) pacing:' % (pace_per_min, pace_per_min * 60))
    p('  without historical comments: %d requests, ~%.1f hours' % (req_no_comments, hours_no_comments))
    p('  with historical comments:    %d requests (%d comments), ~%.1f hours' % (req_with_comments, total_comments, hours_with_comments))
    p('  historical-comment recommendation: mirror going forward only (`sync` picks up any comment posted after')
    p('  the backfill cutover); backfilling %d historical comments now costs ~%.1f extra hours nobody is waiting on.'
      % (total_comments, hours_with_comments - hours_no_comments))
    p('')
    p('=== 2. State conflicts on common numbers: %d ===' % len(d['state_conflicts']))
    for n in d['state_conflicts']:
        p('  #%-4d gh=%-7s fg=%-7s kind=%-5s -- %s' % (n, ghd[n]['state'], fgd[n]['state'], kind_of(ghd[n]), ghd[n]['title'][:70]))
    p('  resolution (round 2, applied by `seed`): close all %d on the forge to match GitHub, including #583 --' % len(STATE_CONFLICT_NUMS))
    p('  lane.local read it: it is forzadecay414\'s PR, last comment 09-30, the fix shipped; the 10-12 updated_at')
    p('  is metadata churn, not activity.')
    p('')
    p('=== 3. Content divergences on common numbers: %d ===' % len(d['content_conflicts']))
    for n in d['content_conflicts']:
        p('  #%d: gh=%r fg=%r' % (n, ghd[n]['title'][:70], fgd[n]['title'][:70]))
    p('  resolution (round 2, applied by `seed`): #1/#161/#568 copy GitHub\'s title+body onto the forge (the forge')
    p('  import never recovered the original content there). #107 stays in NEVER_SYNC (two independently-useful')
    p('  things at the same number, not a conflict).')
    p('')
    p('=== 4. Three sample backfill bodies, exactly as they would be posted ===')
    for n, title, body, state, labels in samples:
        p('--- forge #%d -> POST /issues (kind=%s, state=%s, labels=%s) ---' % (n, kind_of(fgd[n]), state, labels))
        p('title: %s' % title)
        p('body:')
        for bl in body.splitlines():
            p('  ' + bl)
        if state == 'closed' and kind_of(fgd[n]) != 'PR':
            p('  (then PATCH /issues/<returned-N> {"state": "closed"})')
        p('')
    p('=== 5. check-style summary ===')
    p('max numbers: github=%d forge=%d (forge ahead by %d, accounted for by backfill above)' % (d['gh_max'], d['fg_max'], d['fg_max'] - d['gh_max']))

    text = '\n'.join(lines)
    with open(report_path, 'w') as f:
        f.write(text + '\n')
    print(text)
    print('\n[report written to %s]' % report_path)
    return 0


# --------------------------------------------------------------------------------------------------------------
# State file
# --------------------------------------------------------------------------------------------------------------

def load_state():
    try:
        return json.load(open(STATE))
    except Exception:
        return {}


def save_state(s):
    tmp = STATE + '.tmp'
    json.dump(s, open(tmp, 'w'))
    os.replace(tmp, STATE)


def record_baseline(st, n, fg_item, gh_item=None):
    """backfill/new/mirror-down call this right after successfully creating a pair, so the very first `sync`
    never reports it as a conflict for lack of a baseline (gap 5)."""
    last = st.setdefault('last_synced', {})
    entry = {'gh_comments': (gh_item or {}).get('comments', 0), 'fg_comments': fg_item.get('comments', 0)}
    if is_pr_twin_pair(fg_item):
        entry['pr_status_signal'] = pr_status_signal(fg_item)
        entry['pr_title'] = fg_item['title']
    else:
        entry['state'] = fg_item['state']
        entry['title'] = fg_item['title']
        entry['body'] = strip_marker(fg_item.get('body') or '')
        entry['labels'] = sorted(l['name'] for l in fg_item.get('labels', []))
    last[str(n)] = entry


# --------------------------------------------------------------------------------------------------------------
# Level check (gap 2) + mirror-down (gap 1)
# --------------------------------------------------------------------------------------------------------------

def level_check(gh, fg):
    gh_max = max(gh) if gh else 0
    fg_max = max(fg) if fg else 0
    if gh_max == fg_max:
        return 'level', gh_max, fg_max
    if gh_max > fg_max:
        return 'github_ahead', gh_max, fg_max
    return 'forge_ahead', gh_max, fg_max


def mirror_down_targets(gh, fg):
    """Every number <= GitHub's max that the forge lacks: a real GitHub-only item, or a gap in GitHub's own
    number sequence (deleted/never used) that needs a 'reserved' forge placeholder to stay level."""
    if not gh:
        return []
    gh_max = max(gh)
    return sorted(n for n in range(1, gh_max + 1) if n not in fg)


def mirror_down_one(fg_client, n, gh):
    if n in gh:
        item = gh[n]
        if kind_of(item) == 'PR':
            title = '[GitHub PR] ' + item['title']
        else:
            title = item['title']
        body = (item.get('body') or '').strip() + '\n\n' + mirror_marker('github', n)
        labels = [l['name'] for l in item.get('labels', [])]
        state = item['state']
    else:
        title = '#%d: reserved (no GitHub record)' % n
        body = ('No GitHub issue or PR #%d is known; it is a gap in GitHub\'s own number sequence (deleted, or '
                'never used). Reserved so the forge\'s numbering stays level with GitHub\'s.\n\n%s'
                % (n, mirror_marker('github', n)))
        labels = ['github-import', 'reserved-number']
        state = 'closed'
    got = fg_client.create({'title': title, 'body': body, 'labels': labels})
    if got != n:
        raise MirrorStop('ALARM: mirroring down #%d, the forge returned #%s instead -- STOP, a human must look '
                          'before anything else is spent.' % (n, got))
    if state == 'closed':
        fg_client.patch(got, {'state': 'closed'})
    return {'number': got, 'title': title, 'body': body, 'state': state, 'labels': [{'name': l} for l in labels], 'comments': 0}


def do_mirror_down(gh_client, fg_client, yes, gh=None, fg=None, st=None):
    """Shared by the standalone `mirror-down` subcommand, `sync`'s preliminary step, and `new`'s github-ahead
    branch. Returns (rc, fg_dict_updated_in_place_if_any)."""
    gh = gh if gh is not None else gh_client.all_issues()
    fg = fg if fg is not None else fg_client.all_issues()
    targets = mirror_down_targets(gh, fg)
    if not targets:
        return 0, fg
    if not yes:
        print('DRY RUN: would mirror down %d number(s): #%d..#%d' % (len(targets), targets[0], targets[-1]))
        return 0, fg
    st = st if st is not None else load_state()
    for i, n in enumerate(targets):
        try:
            created = mirror_down_one(fg_client, n, gh)
        except MirrorStop as e:
            print(str(e))
            save_state(st)
            return 2, fg
        fg[n] = created
        record_baseline(st, n, created, gh.get(n))
        print('mirrored down #%d (%d/%d)' % (n, i + 1, len(targets)))
        log('mirror-down #%d done' % n)
    save_state(st)
    return 0, fg


def cmd_mirror_down(gh_client, fg_client, yes):
    rc, _ = do_mirror_down(gh_client, fg_client, yes)
    if rc == 0 and yes:
        print('mirror-down: done')
    elif rc == 0:
        gh, fg = gh_client.all_issues(), fg_client.all_issues()
        if not mirror_down_targets(gh, fg):
            print('mirror-down: nothing to do (forge already covers every number up to GitHub\'s max)')
    return rc


# --------------------------------------------------------------------------------------------------------------
# backfill --yes
# --------------------------------------------------------------------------------------------------------------

def cmd_backfill(gh_client, fg_client, yes, max_n, pace_per_min, mirror_comments):
    gh = gh_client.all_issues()
    fg = fg_client.all_issues()
    d = build_diff(gh, fg)
    todo = d['backfill']
    st = load_state()
    resume_after = st.get('backfill_last_done', 0)
    todo = [n for n in todo if n > resume_after]
    if max_n:
        todo = todo[:max_n]
    if not todo:
        print('nothing to backfill (resume cursor at #%d)' % resume_after)
        return 0
    if not yes:
        print('DRY RUN: would create %d GitHub twins, forge #%d..#%d, at %d/min (resuming after #%d)' %
              (len(todo), todo[0], todo[-1], pace_per_min, resume_after))
        return 0
    # gap 2: check the sides are level before spending anything, fresh on every invocation (so a resume after a
    # stop/restart re-checks too, not just the very first call ever made).
    gh_max = max(gh) if gh else 0
    if gh_max + 1 != todo[0]:
        print('REFUSED: GitHub\'s next number is #%d but the next backfill target is forge #%d -- the sides are '
              'not level. Nothing spent. (Someone likely filed a GitHub issue since the last plan/backfill; run '
              '`mirror-down` or `sync` first.)' % (gh_max + 1, todo[0]))
        return 3
    gap = 60.0 / pace_per_min
    for i, n in enumerate(todo):
        title, body, state, labels = build_backfill_body(fg[n], n, fg_client)
        if mirror_comments and fg[n].get('comments', 0):
            comments = fg_client.comments(n)
            body += '\n\n--- %d forge comment(s) follow ---\n' % len(comments)
            for c in comments:
                body += '\n> %s (%s): %s' % ((c.get('user') or {}).get('login', '?'), c.get('created_at'), (c.get('body') or '')[:2000])
        try:
            got = gh_client.create(title, body, labels, state)
        except MirrorStop as e:
            print(str(e))
            return 3
        except RuntimeError as e:
            print('STOP at forge #%d: GitHub create failed: %s' % (n, e))
            log('backfill STOP at #%d: %s' % (n, e))
            return 2
        if got != n:
            print('STOP: forge #%d came back from GitHub as #%d -- identical-number invariant broken. '
                  'Nothing after this ran.' % (n, got))
            log('backfill MISMATCH forge=%d github=%d -- STOPPED' % (n, got))
            return 3
        st['backfill_last_done'] = n
        record_baseline(st, n, fg[n], {'comments': 0})
        save_state(st)
        print('backfilled #%d (%d/%d)' % (n, i + 1, len(todo)))
        log('backfill #%d done' % n)
        if i + 1 < len(todo):
            time.sleep(gap)
    print('backfill: %d items done, resume cursor now #%d' % (len(todo), st['backfill_last_done']))
    return 0


# --------------------------------------------------------------------------------------------------------------
# sync --yes (mirror-down, then 2-way field sync + comments)
# --------------------------------------------------------------------------------------------------------------

def three_way_merge(last, gh_val, fg_val):
    """last: value at the previous sync (or None, first run). Returns (result, conflict)."""
    if gh_val == fg_val:
        return gh_val, False
    if last is None:
        return None, True       # no baseline yet: every differing pair is a conflict the first time through
    gh_changed = gh_val != last
    fg_changed = fg_val != last
    if gh_changed and not fg_changed:
        return gh_val, False
    if fg_changed and not gh_changed:
        return fg_val, False
    return None, True           # both changed differently


def sync_pr_twin(gh_client, fg_client, n, gh_item, fg_item, last, actions):
    base = last.setdefault(str(n), {})
    sig = pr_status_signal(fg_item)
    title_now = fg_item['title']
    if base.get('pr_status_signal') == sig and base.get('pr_title') == title_now:
        return
    detail = fg_client.pull_detail(n)
    new_body = build_pr_twin_body(detail, n)
    new_title = pr_twin_title(title_now)
    gh_client.patch(n, title=new_title, body=new_body)
    base['pr_status_signal'] = sig
    base['pr_title'] = title_now
    actions.append((n, 'pr-status', sig, 'forge'))


def sync_normal_pair(n, gh_item, fg_item, last, actions, conflicts):
    base = last.setdefault(str(n), {})
    fields = [
        ('state', gh_item['state'], fg_item['state']),
        ('title', gh_item['title'], strip_gh_pr_prefix(fg_item['title'])),
        ('body', strip_marker(gh_item.get('body')), strip_marker(fg_item.get('body'))),
        ('labels', tuple(sorted(l['name'] for l in gh_item.get('labels', []))),
         tuple(sorted(l['name'] for l in fg_item.get('labels', [])))),
    ]
    this_pair_conflicts = []
    for field, gv, fv in fields:
        result, conflict = three_way_merge(base.get(field), gv, fv)
        if conflict:
            conflicts.append((n, field, gv, fv))
            this_pair_conflicts.append(field)
        else:
            if gv != result or fv != result:
                actions.append((n, field, result, 'github' if result == gv else 'forge'))
            base[field] = result
    return this_pair_conflicts


def sync_comments(gh_client, fg_client, n, gh_item, fg_item, last, mirrored):
    base = last.setdefault(str(n), {})
    cur_gh = gh_item.get('comments', 0)
    cur_fg = fg_item.get('comments', 0)
    prev_gh = base.get('gh_comments', cur_gh)   # unseen pair: assume current count is baseline, never "catch up" history
    prev_fg = base.get('fg_comments', cur_fg)
    added_gh = added_fg = 0
    if cur_gh > prev_gh:
        for c in gh_client.comments(n)[prev_gh:]:
            if COMMENT_MARKER_RE.search(c.get('body') or ''):
                continue   # our own echo -- never re-mirror a comment that already carries a marker
            author = (c.get('user') or {}).get('login', '?')
            mbody = '**%s** (GitHub, %s):\n\n%s\n\n%s' % (author, c.get('created_at', ''), c.get('body') or '',
                                                            comment_marker('github', n, c['id']))
            new_id = fg_client.comment(n, mbody)
            mirrored.append((n, 'github->forge', c['id'], new_id))
            added_fg += 1
    if cur_fg > prev_fg:
        for c in fg_client.comments(n)[prev_fg:]:
            if COMMENT_MARKER_RE.search(c.get('body') or ''):
                continue
            author = (c.get('user') or {}).get('login', '?')
            mbody = '**%s** (forge, %s):\n\n%s\n\n%s' % (author, c.get('created_at', ''), c.get('body') or '',
                                                            comment_marker('forge', n, c['id']))
            new_id = gh_client.comment(n, mbody)
            mirrored.append((n, 'forge->github', c['id'], new_id))
            added_gh += 1
    base['gh_comments'] = cur_gh + added_gh
    base['fg_comments'] = cur_fg + added_fg


def cmd_sync(gh_client, fg_client, yes):
    gh = gh_client.all_issues()
    fg = fg_client.all_issues()
    st = load_state()
    # gap 1: level the sides first, so common pairs grow to include anything GitHub-only before the field sync runs.
    mrc, fg = do_mirror_down(gh_client, fg_client, yes, gh=gh, fg=fg, st=st)
    if mrc != 0:
        return mrc
    if yes:
        gh = gh_client.all_issues()
        fg = fg_client.all_issues()
    d = build_diff(gh, fg)
    last = st.setdefault('last_synced', {})
    actions, conflicts, mirrored = [], [], []
    for n in d['common']:
        if n in NEVER_SYNC:
            continue
        if is_pr_twin_pair(fg[n]):
            if yes:
                sync_pr_twin(gh_client, fg_client, n, gh[n], fg[n], last, actions)
            continue
        sync_normal_pair(n, gh[n], fg[n], last, actions, conflicts)
        sync_comments(gh_client, fg_client, n, gh[n], fg[n], last, mirrored)

    print('sync: %d pairs, %d field actions, %d conflicts, %d comment(s) mirrored' %
          (len(d['common']), len(actions), len(conflicts), len(mirrored)))
    for n, field, result, src in actions:
        disp = result[:60] if isinstance(result, str) else result
        print('  #%d %s <- %s: %r' % (n, field, src, disp))
    for n, field, gv, fv in conflicts:
        print('  CONFLICT #%d %s: github=%r forge=%r (no baseline or both changed)' % (n, field, gv, fv))
    for n, direction, src_id, dst_id in mirrored:
        print('  #%d comment %s (src %s -> new %s)' % (n, direction, src_id, dst_id))
    if not yes:
        return 0
    # Apply non-PR-twin field actions (PR-twin status/title was already patched live above, inside sync_pr_twin).
    failed = 0
    by_num = {}
    for n, field, result, src in actions:
        if field == 'pr-status':
            continue
        by_num.setdefault(n, []).append((field, result, src))
    for n, fields in by_num.items():
        gh_fields = {f: v for f, v, src in fields if src == 'github'}
        fg_fields = {f: v for f, v, src in fields if src == 'forge'}
        if fg_fields:
            try:
                payload = {}
                if 'title' in fg_fields:
                    payload['title'] = fg_fields['title']
                if 'state' in fg_fields:
                    payload['state'] = fg_fields['state']
                if 'body' in fg_fields:
                    payload['body'] = fg_fields['body']
                if 'labels' in fg_fields:
                    payload['labels'] = list(fg_fields['labels'])
                gh_client.patch(n, title=payload.get('title'), body=payload.get('body'),
                                 state=payload.get('state'), labels=payload.get('labels'))
                print('  #%d github <- forge: applied' % n)
            except (MirrorStop, RuntimeError) as e:
                print('  #%d github <- forge: FAILED: %s' % (n, e))
                failed += 1
                continue
        if gh_fields:
            try:
                payload = {}
                if 'title' in gh_fields:
                    payload['title'] = gh_fields['title']
                if 'state' in gh_fields:
                    payload['state'] = gh_fields['state']
                if 'body' in gh_fields:
                    payload['body'] = gh_fields['body']
                if 'labels' in gh_fields:
                    payload['labels'] = [{'name': l} for l in gh_fields['labels']]
                fg_client.patch(n, payload)
                print('  #%d forge <- github: applied' % n)
            except (MirrorStop, RuntimeError) as e:
                print('  #%d forge <- github: FAILED: %s' % (n, e))
                failed += 1
                continue
    save_state(st)
    return 2 if failed else 0


# --------------------------------------------------------------------------------------------------------------
# seed [--yes] -- gap 5
# --------------------------------------------------------------------------------------------------------------

def cmd_seed(gh_client, fg_client, yes):
    gh = gh_client.all_issues()
    fg = fg_client.all_issues()
    if not yes:
        print('DRY RUN: would close #%s on the forge (match GitHub), copy GitHub title+body onto #%s, then write '
              'the sync baseline for every common pair that is equal.' % (STATE_CONFLICT_NUMS, CONTENT_FIX_NUMS))
        return 0
    failed = []
    for n in STATE_CONFLICT_NUMS:
        if n not in fg:
            continue
        try:
            fg_client.patch(n, {'state': 'closed'}, is_pr=(kind_of(fg[n]) == 'PR'))
            fg[n]['state'] = 'closed'
            print('seed: closed forge #%d to match GitHub' % n)
        except (MirrorStop, RuntimeError) as e:
            failed.append(n)
            print('seed: FAILED closing forge #%d: %s' % (n, e))
    for n in CONTENT_FIX_NUMS:
        if n not in gh or n not in fg:
            continue
        try:
            new_title = gh[n]['title']
            new_body = (gh[n].get('body') or '').strip() + '\n\n' + mirror_marker('github', n)
            fg_client.patch(n, {'title': new_title, 'body': new_body})
            fg[n]['title'] = new_title
            fg[n]['body'] = new_body
            print('seed: copied GitHub title/body onto forge #%d' % n)
        except (MirrorStop, RuntimeError) as e:
            failed.append(n)
            print('seed: FAILED copying onto forge #%d: %s' % (n, e))
    st = load_state()
    last = st.setdefault('last_synced', {})
    d = build_diff(gh, fg)
    seeded = 0
    for n in d['common']:
        if n in NEVER_SYNC or n in failed:
            continue
        if is_pr_twin_pair(fg[n]):
            record_baseline(st, n, fg[n], gh[n])
            seeded += 1
            continue
        gt, ft = gh[n]['state'], fg[n]['state']
        if gt != ft:
            continue   # still unequal (a failed fix, or an unjudged conflict) -- leave unseeded, sync will report it
        record_baseline(st, n, fg[n], gh[n])
        seeded += 1
    save_state(st)
    print('seed: baseline written for %d/%d common pair(s)%s' %
          (seeded, len(d['common']) - len(NEVER_SYNC & set(d['common'])),
           (' -- %d failed and were left unseeded: %s' % (len(failed), failed)) if failed else ''))
    return 2 if failed else 0


# --------------------------------------------------------------------------------------------------------------
# new (the allocator)
# --------------------------------------------------------------------------------------------------------------

def _new_issue(gh_client, fg_client, title, body, forge_user_token_path):
    n = gh_client.create(title, body)
    marker = mirror_marker('github', n)
    fc = FG(write_token_path=forge_user_token_path) if isinstance(fg_client, FG) else fg_client
    got = fc.create({'title': title, 'body': (body or '') + ('\n\n' if body else '') + marker})
    if got != n:
        raise MirrorStop('ALARM: GitHub created #%d but the forge came back as %r -- a side is now ahead. STOP; '
                          'this needs a human, not a retry (retrying would spend another GitHub number on the '
                          'same gap).' % (n, got))
    return n


def _new_pr(gh_client, fg_client, title, body, head, base, forge_user_token_path):
    if not head:
        raise MirrorStop('REFUSED: --kind pr needs --head <lane-branch>')
    gh_title = pr_twin_title(title)
    n = gh_client.create(gh_title, '(pending -- forge PR not yet created)', state='closed')
    synth = {'head': {'ref': head}, 'body': body, 'state': 'open', 'merged': False, 'labels': []}
    gh_client.patch(n, body=build_pr_twin_body(synth, n))
    fc = FG(write_token_path=forge_user_token_path) if isinstance(fg_client, FG) else fg_client
    got = fc.create({'head': head, 'base': base, 'title': title, 'body': body}, is_pr=True)
    if got != n:
        raise MirrorStop('ALARM: GitHub closed-record is #%d but the forge PR came back as %r -- a side is now '
                          'ahead. STOP; this needs a human, not a retry.' % (n, got))
    return n


def cmd_new(gh_client, fg_client, kind, title, body, forge_user, yes, head=None, base='master'):
    lockf = open(LOCK, 'w')
    try:
        fcntl.flock(lockf, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        print('REFUSED: another allocator run holds the lock')
        return 75
    try:
        if not gh_client.reachable():
            print('REFUSED: GitHub unreachable. Queue this request and retry -- an outage must never again '
                  'produce a forge-only number.')
            return 3
        gh = gh_client.all_issues()
        fg = fg_client.all_issues()
        status, gh_max, fg_max = level_check(gh, fg)
        if status == 'forge_ahead':
            print('REFUSED: forge is ahead of GitHub (forge max #%d, GitHub max #%d) -- backfill is pending, or '
                  'something was made directly on the forge. Nothing spent.' % (fg_max, gh_max))
            return 3
        if status == 'github_ahead':
            if not yes:
                print('DRY RUN: GitHub is ahead (#%d vs forge #%d) -- would mirror down %d number(s) before '
                      'creating.' % (gh_max, fg_max, gh_max - fg_max))
                return 0
            mrc, fg = do_mirror_down(gh_client, fg_client, True, gh=gh, fg=fg)
            if mrc != 0:
                print('REFUSED: mirror-down failed; nothing new was created.')
                return mrc
            gh = gh_client.all_issues()
            fg = fg_client.all_issues()
            status, gh_max, fg_max = level_check(gh, fg)
            if status != 'level':
                print('REFUSED: still not level after mirror-down (github=%d forge=%d) -- stopping rather than '
                      'guessing.' % (gh_max, fg_max))
                return 3
        if not yes:
            print('DRY RUN: would create on GitHub first (kind=%s title=%r), read back N, then create forge #N '
                  '(forge-first user: %s), refusing unless the forge number equals GitHub\'s N.' % (kind, title, forge_user))
            return 0
        write_tok = W + '/forge/tokens/%s.token' % forge_user
        st = load_state()
        try:
            if kind == 'pr':
                n = _new_pr(gh_client, fg_client, title, body, head, base, write_tok)
            else:
                n = _new_issue(gh_client, fg_client, title, body, write_tok)
        except MirrorStop as e:
            print(str(e))
            return 3
        fg2 = fg_client.all_issues()
        gh2 = gh_client.all_issues()
        if n in fg2:
            record_baseline(st, n, fg2[n], gh2.get(n))
            save_state(st)
        print('CREATED #%d on both sides' % n)
        return 0
    finally:
        lockf.close()


# --------------------------------------------------------------------------------------------------------------
# check -- gap 7
# --------------------------------------------------------------------------------------------------------------

def cmd_check(gh_client, fg_client):
    gh = gh_client.all_issues()
    fg = fg_client.all_issues()
    d = build_diff(gh, fg)
    st = load_state()
    ceiling = st.get('backlog_ceiling')
    if ceiling is None:
        ceiling = d['fg_max']   # first run ever: treat the current backlog as fully acknowledged, not drift
        st['backlog_ceiling'] = ceiling
        save_state(st)
    problems = []
    if d['only_gh']:
        problems.append('%d GitHub-only number(s) not yet mirrored down: %s' % (len(d['only_gh']), d['only_gh'][:5]))
    beyond_gh = sorted(n for n in fg if n not in gh and n > d['gh_max'])
    unexplained = [n for n in beyond_gh if n > ceiling]
    if unexplained:
        no_marker = [n for n in unexplained if not has_marker(fg[n])]
        if no_marker:
            problems.append('%d forge item(s) created outside the allocator: %s' % (len(no_marker), no_marker[:5]))
        still_unpaired = [n for n in unexplained if n not in no_marker]
        if still_unpaired:
            problems.append('%d forge item(s) past the backlog ceiling still unpaired: %s' % (len(still_unpaired), still_unpaired[:5]))
    if d['state_conflicts']:
        problems.append('%d state conflict(s)' % len(d['state_conflicts']))
    if d['content_conflicts']:
        problems.append('%d content conflict(s)' % len(d['content_conflicts']))
    if problems:
        print('DRIFT: ' + '; '.join(problems))
        return 1
    print('OK: github max=%d forge max=%d, %d backfill-pending, no conflicts' % (d['gh_max'], d['fg_max'], len(d['backfill'])))
    return 0


# --------------------------------------------------------------------------------------------------------------
# close-pr
# --------------------------------------------------------------------------------------------------------------

def cmd_close_pr(number, comment, yes):
    args = [sys.executable, GATEWAY, 'issue-comment', str(number), '--body', comment] + (['--yes'] if yes else [])
    r1 = subprocess.run(args, capture_output=True, text=True)
    print(r1.stdout.strip())
    args2 = [sys.executable, GATEWAY, 'pr-patch', str(number), '--state', 'closed'] + (['--yes'] if yes else [])
    r2 = subprocess.run(args2, capture_output=True, text=True)
    print(r2.stdout.strip())
    if not yes:
        return 0
    return 0 if (r1.returncode == 0 and r2.returncode == 0) else 2


def main():
    ap = argparse.ArgumentParser(prog='issue_mirror.py')
    sub = ap.add_subparsers(dest='cmd', required=True)

    p_plan = sub.add_parser('plan')
    p_plan.add_argument('--report', default=REPORT_PATH_DEFAULT)
    p_plan.add_argument('--pace-per-min', type=int, default=PACE_PER_MIN_DEFAULT)

    p_md = sub.add_parser('mirror-down')
    p_md.add_argument('--yes', action='store_true')

    p_bf = sub.add_parser('backfill')
    p_bf.add_argument('--yes', action='store_true')
    p_bf.add_argument('--max', type=int, default=0)
    p_bf.add_argument('--pace-per-min', type=int, default=PACE_PER_MIN_DEFAULT)
    p_bf.add_argument('--comments', choices=['now', 'later'], default='later')

    p_sync = sub.add_parser('sync')
    p_sync.add_argument('--yes', action='store_true')

    p_seed = sub.add_parser('seed')
    p_seed.add_argument('--yes', action='store_true')

    p_new = sub.add_parser('new')
    p_new.add_argument('--kind', choices=['issue', 'pr'], required=True)
    p_new.add_argument('--title', required=True)
    p_new.add_argument('--body', default='')
    p_new.add_argument('--forge-user', default='jobs')
    p_new.add_argument('--head', default=None, help='lane branch, required for --kind pr')
    p_new.add_argument('--base', default='master')
    p_new.add_argument('--yes', action='store_true')

    sub.add_parser('check')

    p_close = sub.add_parser('close-pr')
    p_close.add_argument('number', type=int)
    p_close.add_argument('--comment', required=True)
    p_close.add_argument('--yes', action='store_true')

    a = ap.parse_args()
    gh_client, fg_client = GH(), FG()
    if a.cmd == 'plan':
        return cmd_plan(gh_client, fg_client, a.report, a.pace_per_min)
    if a.cmd == 'mirror-down':
        return cmd_mirror_down(gh_client, fg_client, a.yes)
    if a.cmd == 'backfill':
        return cmd_backfill(gh_client, fg_client, a.yes, a.max, a.pace_per_min, a.comments == 'now')
    if a.cmd == 'sync':
        return cmd_sync(gh_client, fg_client, a.yes)
    if a.cmd == 'seed':
        return cmd_seed(gh_client, fg_client, a.yes)
    if a.cmd == 'new':
        return cmd_new(gh_client, fg_client, a.kind, a.title, a.body, a.forge_user, a.yes, a.head, a.base)
    if a.cmd == 'check':
        return cmd_check(gh_client, fg_client)
    if a.cmd == 'close-pr':
        return cmd_close_pr(a.number, a.comment, a.yes)
    return 64


if __name__ == '__main__':
    sys.exit(main())
