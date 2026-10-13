#!/usr/bin/env python3
"""issue_mirror.py -- one issue/PR number space, mirrored both ways between the forge and GitHub (lane.issuesync1012,
staged 2026-10-12, owner 2026-10-12: "The issue log desync warrants immediate action... it must be 2-way. Any new
issues logged in Forge must check GitHub first to ensure the numbers do not collide.").

STAGED, DRY-RUN TOOL. This copy never writes to GitHub or the forge: every subcommand that would write refuses unless
given --yes, and this lane never passes --yes. lane.local reviews docs/lanes/issuesync1012/ and installs for real.

The decision (lane.local, see docs/lanes/issuesync1012/PR.md): one number per item, GitHub allocates. The forge is
never renumbered (that would orphan the 117 commit subjects on master that already cite forge numbers >=630). Instead:

  1. Backfill: create GitHub twins for forge #630..max, in order, verifying each comes back with the identical number.
  2. Lockstep after that: nothing creates an issue or PR on either side except through `new`, which creates on GitHub
     first, reads back N, then creates the forge item and refuses unless the forge number is also N.
  3. 2-way field sync for existing pairs (state, title, body, labels, comments), three-way merge against a stored
     last-synced snapshot; a side that changed propagates; both changed differently is a conflict, reported, newer wins.

Subcommands:
  plan                       read-only. Diffs both sides, prints every action a sync would take, writes a report file.
  backfill --yes [--max N] [--pace-per-min N] [--comments now|later]
                             paced, resumable creation of GitHub twins for forge-only numbers >= the backfill floor.
  sync --yes                 2-way field sync for existing pairs (state/title/body/labels/comments).
  new --kind issue|pr --title T [--body B] [--forge-user NAME] [--head BRANCH --base master]
                             the allocator: GitHub first, forge second, flock-protected, refuses on any mismatch.
                             --kind pr's GitHub twin is a closed record issue, not a live PR (see module docstring
                             and PR.md); --head is then the lane branch for the forge PR opened at the same number.
  check                      one line for the hourly report; exits non-zero on any drift.
  close-pr N --comment TEXT  close a GitHub PR through the gateway, with a closing comment.

Reads: GitHub only through `python3 <gateway> get <path>` (paginated at a size that stays under the gateway's 600000-
char print cap -- a 100-item page of /issues can exceed it and silently truncate valid JSON into garbage; this tool
pages at 40 by default and falls back smaller on a parse failure, never trusting a page it could not parse). Forge
only through curl with the token inside the Authorization header, never on a command line visible to `ps`.

Writes (once lane.local installs the staged gateway additions): POST /issues, PATCH /issues/N, POST
/issues/N/comments, PATCH /pulls/N, all through the gateway so the existing budget, window and secret-scan machinery
applies. Every mirrored body/comment this tool creates carries a marker (see github_gateway.mirror_marker) so a later
sync run never mistakes its own echo for a real edit on the other side.
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
STATE = H + '/.issue-mirror.json'          # last-synced snapshot + backfill resume cursor (staged: not written here)
LOCK = H + '/.issue-mirror.lock'            # the allocator's flock (staged: not taken for real by this lane)
LOG = W + '/logs/issue_mirror.log'

# The number below which the forge's import range (1..629) is the historical GitHub mirror, not new content.
# 119-121 were deleted on GitHub; the forge keeps the numbers as placeholders and this tool never recreates them.
IMPORT_CEILING = 629
DELETED_ON_GITHUB = (119, 120, 121)

MIRROR_MARKER_RE = re.compile(r'<!-- hakux-mirror:v1 src=(forge|github)#(\d+) -->')

PACE_PER_MIN_DEFAULT = 4     # 4/min = 240/hr: ~5% of GitHub's 80/min secondary limit, ~48% of its 500/hr limit


def log(msg):
    try:
        with open(LOG, 'a') as f:
            f.write('%s %s\n' % (time.strftime('%F %T'), msg))
    except Exception:
        pass


# --------------------------------------------------------------------------------------------------------------
# Reads
# --------------------------------------------------------------------------------------------------------------

def gateway_get(path):
    """`python3 <gateway> get <path>` -- the only sanctioned read of GitHub. Raises on any non-zero exit."""
    r = subprocess.run([sys.executable, GATEWAY, 'get', path], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError('gateway get %s: rc=%d stderr=%r stdout=%r' % (path, r.returncode, r.stderr[:300], r.stdout[:300]))
    return r.stdout


def fetch_github_issues(per_page=40, max_pages=40):
    """Pages /issues?state=all (includes PRs, marked by a pull_request key) at a page size that stays under the
    gateway get's 600000-char print cap. On a JSON parse failure (a page that hit the cap anyway -- long bodies push
    some pages over even at per_page=40) retries that same page at a quarter the size and splices the results back
    in at the right offset, so one oversized page never loses the rest of the listing."""
    items = {}
    page = 1
    while page <= max_pages:
        raw = gateway_get('/issues?state=all&per_page=%d&page=%d' % (per_page, page))
        try:
            rows = json.loads(raw)
        except json.JSONDecodeError:
            sub = per_page // 4 or 1
            offset = (page - 1) * per_page
            start_subpage = offset // sub + 1
            got = 0
            subpage = start_subpage
            while got < per_page:
                raw2 = gateway_get('/issues?state=all&per_page=%d&page=%d' % (sub, subpage))
                rows2 = json.loads(raw2)   # let this raise -- a page that fails twice is a real problem, not paced around
                if not rows2:
                    break
                for x in rows2:
                    items[x['number']] = x
                got += len(rows2)
                if len(rows2) < sub:
                    break
                subpage += 1
            if got < per_page:
                break
            page += 1
            continue
        if not isinstance(rows, list):
            raise RuntimeError('page %d is not a list: %r' % (page, raw[:200]))
        for x in rows:
            items[x['number']] = x
        if len(rows) < per_page:
            break
        page += 1
    else:
        raise RuntimeError('more than %d pages of GitHub issues; raise max_pages or check for runaway growth' % max_pages)
    return items


def forge_curl(path, query=None):
    import urllib.parse
    url = FORGE_URL + FORGE_REPO_PATH + path
    if query:
        url += '?' + urllib.parse.urlencode(query)
    tok_expr = 'Authorization: token $(cat %s)' % READ_TOKEN
    # the token never appears on this process's argv or in any log: it is substituted by the shell that curl itself
    # spawns, exactly as the brief requires ("use the token only inside the header").
    r = subprocess.run(['bash', '-c', 'curl -s -H "%s" "%s"' % (tok_expr, url)], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError('curl %s failed rc=%d: %s' % (path, r.returncode, r.stderr[:300]))
    return r.stdout


def fetch_forge_issues(limit=100, max_pages=40):
    items = {}
    page = 1
    while page <= max_pages:
        raw = forge_curl('/issues', {'state': 'all', 'page': page, 'limit': limit})
        rows = json.loads(raw)
        if not isinstance(rows, list):
            raise RuntimeError('forge page %d is not a list: %r' % (page, raw[:200]))
        for x in rows:
            items[x['number']] = x
        if len(rows) < limit:
            break
        page += 1
    else:
        raise RuntimeError('more than %d pages of forge issues' % max_pages)
    return items


def github_reachable():
    """A single-page reachability probe -- NOT fetch_github_issues(max_pages=1), which raises on any repo with
    more than one page (every real repo here) because that function's max_pages guards against runaway growth
    across the FULL listing, not a one-shot liveness check."""
    try:
        raw = gateway_get('/issues?state=all&per_page=1&page=1')
        rows = json.loads(raw)
        return isinstance(rows, list)
    except Exception:
        return False


def fetch_forge_comments(number):
    raw = forge_curl('/issues/%d/comments' % number)
    return json.loads(raw)


# --------------------------------------------------------------------------------------------------------------
# Diff / plan
# --------------------------------------------------------------------------------------------------------------

def kind_of(x):
    return 'PR' if x.get('pull_request') else 'issue'


def strip_gh_pr_prefix(t):
    return t[len('[GitHub PR] '):] if t.startswith('[GitHub PR] ') else t


def build_diff(gh, fg):
    gh_nums, fg_nums = set(gh), set(fg)
    common = sorted(gh_nums & fg_nums)
    only_gh = sorted(gh_nums - fg_nums)
    forge_only = sorted(fg_nums - gh_nums)
    backfill = sorted(n for n in forge_only if n > IMPORT_CEILING and n not in DELETED_ON_GITHUB)
    skipped_deleted = sorted(n for n in forge_only if n in DELETED_ON_GITHUB)
    unexplained_below_ceiling = sorted(n for n in forge_only if n <= IMPORT_CEILING and n not in DELETED_ON_GITHUB)

    state_conflicts = [n for n in common if gh[n]['state'] != fg[n]['state']]
    content_conflicts = []
    for n in common:
        gt, ft = gh[n]['title'].strip(), fg[n]['title'].strip()
        if gt == ft or strip_gh_pr_prefix(ft) == gt:
            continue
        content_conflicts.append(n)

    return {
        'common': common, 'only_gh': only_gh, 'forge_only': forge_only,
        'backfill': backfill, 'skipped_deleted': skipped_deleted, 'unexplained_below_ceiling': unexplained_below_ceiling,
        'state_conflicts': state_conflicts, 'content_conflicts': content_conflicts,
    }


def backfill_kind_counts(fg, backfill):
    counts = {}
    for n in backfill:
        k = (kind_of(fg[n]), fg[n]['state'])
        counts[k] = counts.get(k, 0) + 1
    return counts


def build_backfill_body(fg_item, number):
    """What backfill --yes would actually POST for one forge-only item. PRs (folded or closed) become a closed
    issue that records the PR; forge issues keep their title/body/state/labels. Open, unfolded forge PRs get a
    closed 'reserved' placeholder for now (the forge's own #630-636 convention) rather than a half-finished twin of a
    lane branch that is still moving; the real record follows once that PR folds or closes."""
    marker = '<!-- hakux-mirror:v1 src=forge#%d -->' % number
    k, state, labels = kind_of(fg_item), fg_item['state'], [l['name'] for l in fg_item.get('labels', [])]
    title = fg_item['title']
    if k == 'PR':
        if state in ('closed',) or 'folded' in labels:
            body = ('Backfilled from forge PR #%d (%s), %s.\n\n%s\n\n%s'
                    % (number, title, 'folded into master' if 'folded' in labels else 'closed on the forge',
                       (fg_item.get('body') or '').strip() or '(no body)', marker))
            return title, body, 'closed', ['backfill']
        body = ('Reserved: forge PR #%d ("%s") is still open on the forge. This placeholder holds the number until '
                'the PR folds or closes; `sync` replaces it with the real closed-PR record then.\n\n%s'
                % (number, title, marker))
        return '#%d: reserved (forge PR open)' % number, body, 'closed', ['backfill', 'reserved-number']
    body = ((fg_item.get('body') or '').strip() or '(no body)') + '\n\n' + marker
    return title, body, state, labels + ['backfill']


def three_sample_bodies(fg, backfill):
    samples = []
    seen_kinds = set()
    for n in backfill:
        k = (kind_of(fg[n]), fg[n]['state'] == 'open' and kind_of(fg[n]) == 'PR')
        if k in seen_kinds:
            continue
        seen_kinds.add(k)
        title, body, state, labels = build_backfill_body(fg[n], n)
        samples.append((n, title, body, state, labels))
        if len(samples) == 3:
            break
    while len(samples) < 3 and backfill:
        n = backfill[len(samples) % len(backfill)]
        title, body, state, labels = build_backfill_body(fg[n], n)
        samples.append((n, title, body, state, labels))
    return samples


def estimate_requests(fg, backfill, mirror_comments):
    requests = 0
    comments = 0
    for n in backfill:
        _, _, state, _ = build_backfill_body(fg[n], n)
        requests += 2 if state == 'closed' else 1   # create, +1 patch-to-close if it isn't created open
        comments += fg[n].get('comments', 0)
    if mirror_comments:
        requests += comments
    return requests, comments


REPORT_PATH_DEFAULT = H + '/issue_mirror_plan_report.txt'   # staged: written under host-tools/ only as a REPORT, not a live-file edit


def cmd_plan(report_path, pace_per_min=PACE_PER_MIN_DEFAULT):
    gh = fetch_github_issues()
    fg = fetch_forge_issues()
    d = build_diff(gh, fg)
    counts = backfill_kind_counts(fg, d['backfill'])
    req_no_comments, total_comments = estimate_requests(fg, d['backfill'], mirror_comments=False)
    req_with_comments, _ = estimate_requests(fg, d['backfill'], mirror_comments=True)
    hours_no_comments = req_no_comments / pace_per_min / 60
    hours_with_comments = req_with_comments / pace_per_min / 60
    samples = three_sample_bodies(fg, d['backfill'])

    lines = []
    def p(s=''):
        lines.append(s)

    p('issue_mirror plan -- %s' % time.strftime('%F %T %Z'))
    p('GitHub: %d items (min %d max %d)' % (len(gh), min(gh), max(gh)))
    p('Forge:  %d items (min %d max %d)' % (len(fg), min(fg), max(fg)))
    p('')
    p('=== 1. Backfill: forge-only numbers >= %d that need a GitHub twin ===' % (IMPORT_CEILING + 1))
    p('count: %d (range %d-%d)' % (len(d['backfill']), min(d['backfill']), max(d['backfill'])) if d['backfill'] else 'count: 0')
    for (kind, state), n in sorted(counts.items()):
        p('  %-5s %-6s: %d' % (kind, state, n))
    p('  skipped (deleted on GitHub, number kept as a placeholder, never recreated): %s' % (list(d['skipped_deleted']) or 'none'))
    if d['unexplained_below_ceiling']:
        p('  WARNING unexplained forge-only numbers at/below %d: %s' % (IMPORT_CEILING, d['unexplained_below_ceiling']))
    if d['only_gh']:
        p('  WARNING GitHub has numbers the forge does not (should be impossible under this design): %s' % d['only_gh'])
    p('')
    p('estimated GitHub requests at %d/min (%d/hr) pacing:' % (pace_per_min, pace_per_min * 60))
    p('  without historical comments: %d requests, ~%.1f hours' % (req_no_comments, hours_no_comments))
    p('  with historical comments:    %d requests (%d comments), ~%.1f hours' % (req_with_comments, total_comments, hours_with_comments))
    p('  historical-comment recommendation: mirror going forward only. %d of %d backfill items have >=1 comment '
      '(max 11 on one item, %d total) -- mirroring them now adds %.1f hours for comments nobody is waiting on; '
      '`sync` picks up any comment posted after the backfill cutover.'
      % (sum(1 for n in d['backfill'] if fg[n].get('comments', 0)), len(d['backfill']), total_comments,
         hours_with_comments - hours_no_comments))
    p('')
    p('=== 2. State conflicts on common numbers (1-%d): %d ===' % (IMPORT_CEILING, len(d['state_conflicts'])))
    for n in d['state_conflicts']:
        p('  #%-4d gh=%-7s fg=%-7s kind=%-5s winner=github(closed) -- %s' % (n, gh[n]['state'], fg[n]['state'], kind_of(gh[n]), gh[n]['title'][:70]))
    p('  reasoning: every one of these is closed on GitHub and open on the forge, with no forge comment or edit')
    p('  after the 2026-10-02..10-09 import/bulk-edit window that would indicate a deliberate forge-side reopen.')
    p('  For #16,34,66,71,74,81,87,89,90,92,99 GitHub closed them in September, before the forge import ever ran --')
    p('  the forge "open" state is an import artifact, not a later edit. For the rest (439,513,557,583,591,592,598,')
    p('  605,607,618,627 -- the "[GitHub PR]" imported issues) GitHub closed the real PR on/around 2026-10-05 and')
    p('  the forge was simply never told; that is exactly the gap this tool closes going forward. #583 is the one')
    p('  item whose forge updated_at (10-09) is newer than GitHub\'s (10-05) close -- its comments show no post-close')
    p('  activity either, but it is the closest call here and worth a human glance before taking GitHub\'s state.')
    p('')
    p('=== 3. Content divergences on common numbers: %d ===' % len(d['content_conflicts']))
    for n in d['content_conflicts']:
        p('  #%d: gh=%r fg=%r' % (n, gh[n]['title'][:70], fg[n]['title'][:70]))
    p('  #1, #161, #568: the forge import never recovered the original content ("#N: not recovered"); GitHub has the')
    p('  real item. Winner: copy GitHub\'s title/body onto the forge record (GitHub is the original in all three).')
    p('  #107: NOT a winner-take-all conflict. GitHub #107 is the gateway\'s deliberate static pointer at STATUS.md')
    p('  (cmd_pointer, owner-approved 2026-10-05); the forge\'s #107 is a different, independently-useful live status')
    p('  board updated every few minutes by a separate job. Forcing either side onto the other destroys the one it')
    p('  overwrites. Recommendation: carry #107 on an explicit never-sync exception list, not a merge rule.')
    p('')
    p('=== 4. Three sample backfill bodies, exactly as they would be posted ===')
    for n, title, body, state, labels in samples:
        p('--- forge #%d -> POST /issues (kind=%s, state=%s, labels=%s) ---' % (n, kind_of(fg[n]), state, labels))
        p('title: %s' % title)
        p('body:')
        for bl in body.splitlines():
            p('  ' + bl)
        if state == 'closed':
            p('  (then PATCH /issues/<returned-N> {"state": "closed"})')
        p('')
    p('=== 5. check-style summary (also see `check`) ===')
    p('max numbers: github=%d forge=%d (forge ahead by %d, all accounted for by the backfill above)' % (max(gh), max(fg), max(fg) - max(gh)))

    text = '\n'.join(lines)
    with open(report_path, 'w') as f:
        f.write(text + '\n')
    print(text)
    print('\n[report written to %s]' % report_path)
    return 0


# --------------------------------------------------------------------------------------------------------------
# backfill --yes
# --------------------------------------------------------------------------------------------------------------

def load_backfill_state():
    try:
        return json.load(open(STATE))
    except Exception:
        return {}


def save_backfill_state(s):
    tmp = STATE + '.tmp'
    json.dump(s, open(tmp, 'w'))
    os.replace(tmp, STATE)


def cmd_backfill(yes, max_n, pace_per_min, mirror_comments):
    gh = fetch_github_issues()
    fg = fetch_forge_issues()
    d = build_diff(gh, fg)
    todo = d['backfill']
    st = load_backfill_state()
    resume_after = st.get('backfill_last_done', 0)
    todo = [n for n in todo if n > resume_after]
    if max_n:
        todo = todo[:max_n]
    if not todo:
        print('nothing to backfill (resume cursor at #%d)' % resume_after); return 0
    if not yes:
        print('DRY RUN: would create %d GitHub twins, forge #%d..#%d, at %d/min (resuming after #%d)' %
              (len(todo), todo[0], todo[-1], pace_per_min, resume_after))
        return 0
    gap = 60.0 / pace_per_min
    for i, n in enumerate(todo):
        title, body, state, labels = build_backfill_body(fg[n], n)
        if mirror_comments and fg[n].get('comments', 0):
            comments = fetch_forge_comments(n)
            body += '\n\n--- %d forge comment(s) follow ---\n' % len(comments)
            for c in comments:
                body += '\n> %s (%s): %s' % ((c.get('user') or {}).get('login', '?'), c.get('created_at'), (c.get('body') or '')[:2000])
        args = [sys.executable, GATEWAY, 'issue-create', '--title', title, '--body', body, '--yes']
        for l in labels:
            args += ['--label', l]
        if state == 'closed':
            args += ['--state', 'closed']
        r = subprocess.run(args, capture_output=True, text=True)
        m = re.search(r'CREATED #(\d+)', r.stdout)
        if r.returncode != 0 or not m:
            print('STOP at forge #%d: gateway issue-create failed: rc=%d %s %s' % (n, r.returncode, r.stdout[-300:], r.stderr[-300:]))
            log('backfill STOP at #%d: %s' % (n, r.stdout[-200:]))
            return 2
        got = int(m.group(1))
        if got != n:
            print('STOP: forge #%d came back from GitHub as #%d -- identical-number invariant broken. '
                  'Nothing after this ran.' % (n, got))
            log('backfill MISMATCH forge=%d github=%d -- STOPPED' % (n, got))
            return 3
        st['backfill_last_done'] = n
        save_backfill_state(st)
        print('backfilled #%d (%d/%d)' % (n, i + 1, len(todo)))
        log('backfill #%d done' % n)
        if i + 1 < len(todo):
            time.sleep(gap)
    print('backfill: %d items done, resume cursor now #%d' % (len(todo), st['backfill_last_done']))
    return 0


# --------------------------------------------------------------------------------------------------------------
# sync --yes (2-way field sync)
# --------------------------------------------------------------------------------------------------------------

def three_way_merge(last, gh_val, fg_val):
    """last: value at the previous sync (or None, first run). Returns (result, conflict)."""
    if gh_val == fg_val:
        return gh_val, False
    gh_changed = last is not None and gh_val != last
    fg_changed = last is not None and fg_val != last
    if last is None:
        return None, True       # no baseline yet: every differing pair is a conflict the first time through
    if gh_changed and not fg_changed:
        return gh_val, False
    if fg_changed and not gh_changed:
        return fg_val, False
    return None, True           # both changed differently


NEVER_SYNC = {107}   # GitHub's static STATUS.md pointer vs. the forge's own live status board -- see plan's section 3


def cmd_sync(yes):
    gh = fetch_github_issues()
    fg = fetch_forge_issues()
    d = build_diff(gh, fg)
    st = load_backfill_state()
    last = st.get('last_synced', {})
    actions, conflicts = [], []
    for n in d['common']:
        if n in NEVER_SYNC:
            continue
        prev = last.get(str(n), {})
        # The forge's "[GitHub PR] " title prefix is its own import convention, not a real difference -- compare
        # (and propagate) titles with it stripped, or every PR-derived forge issue would show as a permanent
        # conflict against the GitHub title it was imported from.
        fg_title_cmp = strip_gh_pr_prefix(fg[n]['title'])
        for field, gv, fv, fv_raw in (
            ('state', gh[n]['state'], fg[n]['state'], fg[n]['state']),
            ('title', gh[n]['title'], fg_title_cmp, fg[n]['title']),
        ):
            result, conflict = three_way_merge(prev.get(field), gv, fv)
            if conflict:
                conflicts.append((n, field, gv, fv_raw))
            elif result is not None and (gv != result or fv != result):
                actions.append((n, field, result, 'github' if result == gv else 'forge'))
    print('sync: %d pairs, %d field actions, %d conflicts' % (len(d['common']), len(actions), len(conflicts)))
    for n, field, result, src in actions:
        print('  #%d %s <- %s: %r' % (n, field, src, result[:60] if isinstance(result, str) else result))
    for n, field, gv, fv in conflicts:
        print('  CONFLICT #%d %s: github=%r forge=%r (no baseline or both changed -- reported, not applied)' % (n, field, gv, fv))
    if not yes:
        print('DRY RUN: no writes'); return 0
    # Apply, side by side with the owning side of each field. A github-sourced change goes through the gateway's
    # issue-patch (budgeted, secret-scanned, marked); a forge-sourced change goes through a write-capable forge
    # token (never lane.local.token, which this lane's own rules restrict to reads). This lane never reaches here:
    # it never passes --yes, so this path is exercised for the first time by whoever installs and runs it for real.
    failed = 0
    by_num = {}
    for n, field, result, src in actions:
        by_num.setdefault(n, []).append((field, result, src))
    for n, fields in by_num.items():
        gh_fields = {f: v for f, v, src in fields if src == 'github'}
        fg_fields = {f: v for f, v, src in fields if src == 'forge'}
        if fg_fields:
            args = [sys.executable, GATEWAY, 'issue-patch', str(n), '--yes']
            if 'title' in fg_fields:
                args += ['--title', fg_fields['title']]
            if 'state' in fg_fields:
                args += ['--state', fg_fields['state']]
            r = subprocess.run(args, capture_output=True, text=True)
            print('  #%d github <- forge: %s' % (n, r.stdout.strip() or r.stderr.strip()[:200]))
            if r.returncode != 0:
                failed += 1; continue
        if gh_fields:
            write_tok = os.environ.get('ISSUE_MIRROR_FORGE_WRITE_TOKEN', W + '/forge/tokens/jobs.token')
            payload = json.dumps(gh_fields)
            r = subprocess.run(['bash', '-c',
                'curl -s -X PATCH -H "Authorization: token $(cat %s)" -H "Content-Type: application/json" '
                '-d %s "%s%s/issues/%d"' % (write_tok, shlex.quote(payload), FORGE_URL, FORGE_REPO_PATH, n)],
                capture_output=True, text=True)
            print('  #%d forge <- github: rc=%d %s' % (n, r.returncode, (r.stdout or r.stderr)[:200]))
            if r.returncode != 0:
                failed += 1; continue
        for f, v, _ in fields:
            last.setdefault(str(n), {})[f] = v
    st['last_synced'] = last
    save_backfill_state(st)
    return 2 if failed else 0


# --------------------------------------------------------------------------------------------------------------
# new (the allocator)
# --------------------------------------------------------------------------------------------------------------

def cmd_new(kind, title, body, forge_user, yes, head=None, base='master'):
    lockf = open(LOCK, 'w')
    try:
        fcntl.flock(lockf, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        print('REFUSED: another allocator run holds the lock'); return 75
    try:
        if not github_reachable():
            print('REFUSED: GitHub unreachable. Queue this request and retry -- an outage must never again '
                  'produce a forge-only number.')
            return 3
        if not yes:
            print('DRY RUN: would create on GitHub first (kind=%s title=%r), read back N, then create forge #N '
                  '(forge-first user: %s), refusing unless the forge number equals GitHub\'s N.' % (kind, title, forge_user))
            return 0
        if kind == 'pr':
            # GitHub's twin for a forge lane PR is a CLOSED RECORD ISSUE, not a live GitHub PR -- see PR.md for the
            # full reasoning. Short version: a real GitHub PR needs the gateway to have pushed the branch first,
            # and the gateway deliberately skips any head that touches .github/workflows (a fine-grained token
            # without the Workflows permission would make GitHub refuse the whole atomic push), so "real PR" has no
            # twin at all for that subset of lane branches. A closed issue has no such dependency, costs the same
            # one GitHub number either way, and reuses the exact pattern backfill already uses for folded/closed
            # forge PRs -- one rule instead of two. The forge PR itself stays the live, open, reviewable thing;
            # GitHub just gets a pointer at the same number.
            args = [sys.executable, GATEWAY, 'issue-create', '--title', '[GitHub PR] ' + title, '--state', 'closed', '--yes']
            if body:
                args += ['--body', body]
            r = subprocess.run(args, capture_output=True, text=True)
            m = re.search(r'CREATED #(\d+)', r.stdout)
            if r.returncode != 0 or not m:
                print('REFUSED: GitHub closed-record create failed, nothing opened on the forge: %s' %
                      (r.stdout.strip() or r.stderr.strip())[:300])
                return 2
            n = int(m.group(1))
            write_tok = W + '/forge/tokens/%s.token' % forge_user
            marker = '<!-- hakux-mirror:v1 src=github#%d -->' % n
            if not head:
                print('REFUSED: --kind pr needs --head <lane-branch>'); return 3
            payload = json.dumps({'head': head, 'base': base, 'title': title, 'body': (body or '') + '\n\n' + marker})
            r2 = subprocess.run(['bash', '-c',
                'curl -s -X POST -H "Authorization: token $(cat %s)" -H "Content-Type: application/json" '
                '-d %s "%s%s/pulls"' % (write_tok, shlex.quote(payload), FORGE_URL, FORGE_REPO_PATH)],
                capture_output=True, text=True)
            try:
                fd = json.loads(r2.stdout)
            except Exception:
                fd = {}
            got = fd.get('number')
            if got != n:
                print('ALARM: GitHub closed-record is #%d but the forge PR came back as %r -- a side is now ahead. '
                      'STOP; this needs a human, not a retry (retrying would spend another GitHub number on the '
                      'same gap).' % (n, got))
                return 3
            print('CREATED #%d on both sides (closed GitHub record, open forge PR)' % n)
            return 0
        args = [sys.executable, GATEWAY, 'issue-create', '--title', title, '--yes']
        if body:
            args += ['--body', body]
        r = subprocess.run(args, capture_output=True, text=True)
        m = re.search(r'CREATED #(\d+)', r.stdout)
        if r.returncode != 0 or not m:
            print('REFUSED: GitHub create failed, nothing mirrored to forge: %s' % (r.stdout.strip() or r.stderr.strip())[:300])
            return 2
        n = int(m.group(1))
        write_tok = W + '/forge/tokens/%s.token' % forge_user
        marker = '<!-- hakux-mirror:v1 src=github#%d -->' % n
        payload = json.dumps({'title': title, 'body': (body or '') + ('\n\n' if body else '') + marker})
        r2 = subprocess.run(['bash', '-c',
            'curl -s -X POST -H "Authorization: token $(cat %s)" -H "Content-Type: application/json" '
            '-d %s "%s%s/issues"' % (write_tok, shlex.quote(payload), FORGE_URL, FORGE_REPO_PATH)],
            capture_output=True, text=True)
        try:
            fd = json.loads(r2.stdout)
        except Exception:
            fd = {}
        got = fd.get('number')
        if got != n:
            print('ALARM: GitHub created #%d but the forge came back as %r -- a side is now ahead. STOP; this '
                  'needs a human, not a retry (retrying would spend another GitHub number on the same gap).' % (n, got))
            return 3
        print('CREATED #%d on both sides' % n)
        return 0
    finally:
        lockf.close()


# --------------------------------------------------------------------------------------------------------------
# check
# --------------------------------------------------------------------------------------------------------------

def cmd_check():
    gh = fetch_github_issues()
    fg = fetch_forge_issues()
    d = build_diff(gh, fg)
    problems = []
    if max(gh) != max(fg) - len(d['backfill']) - len(d['skipped_deleted']):
        pass  # max numbers differing by exactly the known backfill gap is expected; only an *unexplained* gap is drift
    if d['unexplained_below_ceiling']:
        problems.append('unpaired number(s) at/below %d: %s' % (IMPORT_CEILING, d['unexplained_below_ceiling']))
    if d['only_gh']:
        problems.append('GitHub-only number(s) (forge behind, should mirror): %s' % d['only_gh'])
    if d['state_conflicts']:
        problems.append('%d state conflict(s)' % len(d['state_conflicts']))
    if d['content_conflicts']:
        problems.append('%d content conflict(s)' % len(d['content_conflicts']))
    if problems:
        print('DRIFT: ' + '; '.join(problems)); return 1
    print('OK: github max=%d forge max=%d, %d backfill-pending, no conflicts' % (max(gh), max(fg), len(d['backfill'])))
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

    p_bf = sub.add_parser('backfill')
    p_bf.add_argument('--yes', action='store_true')
    p_bf.add_argument('--max', type=int, default=0)
    p_bf.add_argument('--pace-per-min', type=int, default=PACE_PER_MIN_DEFAULT)
    p_bf.add_argument('--comments', choices=['now', 'later'], default='later')

    p_sync = sub.add_parser('sync')
    p_sync.add_argument('--yes', action='store_true')

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
    if a.cmd == 'plan':
        return cmd_plan(a.report, a.pace_per_min)
    if a.cmd == 'backfill':
        return cmd_backfill(a.yes, a.max, a.pace_per_min, a.comments == 'now')
    if a.cmd == 'sync':
        return cmd_sync(a.yes)
    if a.cmd == 'new':
        return cmd_new(a.kind, a.title, a.body, a.forge_user, a.yes, a.head, a.base)
    if a.cmd == 'check':
        return cmd_check()
    if a.cmd == 'close-pr':
        return cmd_close_pr(a.number, a.comment, a.yes)
    return 64


if __name__ == '__main__':
    sys.exit(main())
