"""recon_build.py: merge scan events, the board and git into forge-import/issues/<n>.json + coverage.

Rules:
- A field's value is the latest observation (by transcript time) from a source that holds it exactly.
- A body only ever seen truncated is written with body_complete=false; nothing is paraphrased or filled in.
- Comments are keyed by GitHub comment id. Records with no id (reviews, close comments, jq reads that did
  not print the URL) are matched to an id'd comment by text; the rest are kept with id null.
"""
import collections, json, os, re, subprocess, sys

HOME = os.path.expanduser('~')
GH_LOGIN = 'jreinach-alt'


def nb(b):
    return re.sub(r'[ \t]+\n', '\n', (b or '').replace('\r\n', '\n')).strip()


def src(e):
    return '%s@%s %s' % (e['how'], (e.get('ts') or '')[:19], e.get('src', ''))


def ts(e):
    return e.get('ts') or ''


def board_rows(repo):
    try:
        import tomllib
    except ImportError:
        return {}
    try:
        t = subprocess.run(['git', 'show', 'origin/board:nv2a_issues.toml'], cwd=repo, capture_output=True,
                           text=True).stdout
        d = tomllib.loads(t)
    except Exception:
        return {}
    out = {}
    for k, v in (d.get('issue') or {}).items():
        if k.isdigit() and isinstance(v, dict):
            out[int(k)] = {x: v[x] for x in ('title', 'status', 'disposition', 'component') if x in v}
    return out


def git_folds(repo):
    """fold: PR #N lane/X -- TITLE (#issue) and Merge pull request #N: merged PRs with their titles."""
    out = {}
    t = subprocess.run(['git', 'log', 'origin/master', '--format=%H%x09%cI%x09%s'], cwd=repo, capture_output=True,
                       text=True).stdout
    for line in t.split('\n'):
        p = line.split('\t', 2)
        if len(p) != 3:
            continue
        h, when, subj = p
        from datetime import datetime, timezone
        when = datetime.fromisoformat(when).astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
        m = re.match(r'fold: PR #(\d+) (\S+) -- (.*)$', subj)
        if m:
            n = int(m.group(1))
            if n not in out or when < out[n]['when']:
                out[n] = {'head': m.group(2), 'title_fold': m.group(3), 'when': when, 'sha': h[:10], 'how': 'fold'}
            continue
        m = re.match(r'Merge pull request #(\d+) from [\w-]+/(\S+)', subj)
        if m:
            n = int(m.group(1))
            out.setdefault(n, {'head': m.group(2), 'when': when, 'sha': h[:10], 'how': 'merge-commit'})
    return out


def build(scratch, args):
    out_dir = os.path.join(HOME, 'hakux-work/forge-import')
    if '--out' in args:
        out_dir = args[args.index('--out') + 1]
    repo = os.getcwd()
    ev = [json.loads(l) for l in open(os.path.join(scratch, 'events.jsonl'))]
    seen = json.load(open(os.path.join(scratch, 'seen.json')))
    id_n = {}
    for n, c in seen['comment_ids']:
        id_n.setdefault(c, n)
    nums_seen = collections.defaultdict(set)
    for n, kind, cnt in seen['numbers']:
        nums_seen[n].add('pr' if kind == 'pull' else 'issue')
    for e in ev:
        if e['t'] == 'comment' and e.get('id') and e.get('n'):
            id_n.setdefault(e['id'], e['n'])
    board = board_rows(repo)
    folds = git_folds(repo)

    iss = collections.defaultdict(list)
    lab = collections.defaultdict(list)
    cm = collections.defaultdict(list)
    for e in ev:
        if e['t'] == 'issue' and e.get('n'):
            iss[e['n']].append(e)
        elif e['t'] == 'labels' and e.get('n'):
            lab[e['n']].append(e)
        elif e['t'] == 'comment':
            n = e.get('n') or id_n.get(e.get('id'))
            if n:
                e['n'] = n
                cm[n].append(e)
    # all numbers that existed: 1..max seen anywhere (numbers are sequential on GitHub)
    known = set(iss) | set(cm) | set(nums_seen) | set(board) | set(folds)
    top = max(n for n in known if n < 5000)
    numbers = range(1, top + 1)
    os.makedirs(os.path.join(out_dir, 'issues'), exist_ok=True)
    cov = []
    for n in numbers:
        rec, cov_row = build_one(n, iss.get(n, []), lab.get(n, []), cm.get(n, []), nums_seen.get(n, set()),
                                 board.get(n), folds.get(n), seen_ids=[c for c, nn in id_n.items() if nn == n])
        path = os.path.join(out_dir, 'issues', '%d.json' % n)
        if rec is None:
            if os.path.exists(path):
                os.remove(path)
        else:
            with open(path, 'w') as f:
                json.dump(rec, f, indent=1, ensure_ascii=False)
                f.write('\n')
        cov.append(cov_row)
    write_coverage(out_dir, cov, top)


def latest(obs, field, exact_only=True):
    best = None
    for e in obs:
        f = e.get('f') or {}
        if field not in f or f[field] is None:
            continue
        if field == 'body' and exact_only and not f.get('body_exact', True):
            continue
        if best is None or ts(e) >= ts(best):
            best = e
    return best


def build_one(n, obs, labels_ev, cms, kinds_seen, board, fold, seen_ids):
    rec = {'number': n}
    sources = {}
    if fold and fold.get('title_fold'):
        obs = obs + [{'t': 'issue', 'n': n, 'kind': 'pr', 'ts': fold['when'], 'how': 'git-fold',
                      'src': 'origin/master %s (fold.sh merge subject carries the PR title)' % fold['sha'],
                      'f': {'title': fold['title_fold'], 'state': 'merged', 'head': fold['head']}}]
    # kind
    kinds = collections.Counter(e['kind'] for e in obs if e.get('kind'))
    for k in kinds_seen:
        kinds[k] += 1
    if fold:
        kinds['pr'] += 3
    kind = kinds.most_common(1)[0][0] if kinds else None
    if kinds.get('pr') and kinds.get('issue'):
        # a URL /issues/N redirects for PRs, so 'issue' from a URL is weak; pr evidence from objects wins
        strong = collections.Counter(e['kind'] for e in obs if e.get('kind') and e['how'] in ('json', 'created', 'list-text'))
        if strong:
            kind = strong.most_common(1)[0][0]
        elif fold:
            kind = 'pr'
    if kind is None and any(k in (x.get('f') or {}) for x in obs for k in ('head', 'draft', 'merged_at', 'base')):
        kind = 'pr'
    rec['kind'] = kind
    # title
    e = latest(obs, 'title')
    if e:
        rec['title'] = e['f']['title']; sources['title'] = src(e)
    elif board and board.get('title'):
        rec['title'] = board['title']; sources['title'] = 'board:nv2a_issues.toml (board title, not necessarily GitHub\'s)'
    # body
    e = latest(obs, 'body')
    if e:
        rec['body'] = e['f']['body'].replace('\r\n', '\n'); rec['body_complete'] = True; sources['body'] = src(e)
    else:
        parts = [x for x in obs if (x.get('f') or {}).get('body')]
        if parts:
            e = max(parts, key=lambda x: len(x['f']['body']))
            rec['body'] = e['f']['body'].replace('\r\n', '\n'); rec['body_complete'] = False
            sources['body'] = src(e) + ' (truncated read)'
    # state
    st = [x for x in obs if (x.get('f') or {}).get('state')]
    if st:
        e = max(st, key=ts)
        rec['state'] = e['f']['state']; sources['state'] = src(e) + ' (last observation before the 2026-09-29 suspension)'
    if fold and rec.get('state') != 'merged':
        last_obs = max((ts(x) for x in st), default='')
        if not st or fold['when'] >= last_obs[:19] or rec.get('state') in (None, 'open', 'closed'):
            rec['state'] = 'merged'
            sources['state'] = 'git:%s %s' % (fold['how'], fold['sha'])
    # labels: latest full set, then later add/remove events
    full = [x for x in obs if isinstance((x.get('f') or {}).get('labels'), list)]
    base_t = ''
    labels = None
    if full:
        e = max(full, key=ts)
        labels = list(e['f']['labels']); base_t = ts(e); sources['labels'] = src(e)
    adds = [x for x in obs if (x.get('f') or {}).get('labels_added')]
    evs = sorted([x for x in labels_ev if ts(x) > base_t] +
                 [{'ts': ts(x), 'add': x['f']['labels_added'], 'rm': [], 'how': 'created', 'src': x['src']}
                  for x in adds if ts(x) > base_t], key=ts)
    if evs:
        labels = labels or []
        for x in evs:
            for l in x.get('add') or []:
                if l not in labels:
                    labels.append(l)
            for l in x.get('rm') or []:
                if l in labels:
                    labels.remove(l)
        sources['labels'] = (sources.get('labels', '') + ' + %d later label edits' % len(evs)).strip(' +')
    if labels is not None:
        rec['labels'] = labels
    # simple fields
    for fld in ('author', 'created_at', 'closed_at', 'merged_at', 'draft', 'head', 'base'):
        e = latest(obs, fld)
        if e:
            rec[fld] = e['f'][fld]; sources[fld] = src(e)
    if 'head' not in rec and fold:
        rec['head'] = fold['head'].replace('lane/', 'lane/', 1); sources['head'] = 'git:%s %s' % (fold['how'], fold['sha'])
    if rec.get('state') == 'merged' and 'merged_at' not in rec and fold:
        rec['merged_at'] = fold['when']; sources['merged_at'] = 'git:%s %s (commit time of the fold, not GitHub\'s)' % (fold['how'], fold['sha'])
    cr = [x for x in obs if x.get('created')]
    if 'created_at' not in rec and cr:
        e = min(cr, key=ts)
        rec['created_at'] = e['ts'][:19] + 'Z'; sources['created_at'] = src(e) + ' (transcript clock of the create call)'
    if 'author' not in rec and (cr or rec.get('title')):
        rec['author'] = GH_LOGIN
        sources['author'] = 'inferred: every gh call on this machine ran as %s, and every author field read back is %s' % (GH_LOGIN, GH_LOGIN)
    if rec.get('state') == 'closed' and 'closed_at' not in rec:
        cl = [x for x in obs if x['how'] == 'close']
        if cl:
            e = max(cl, key=ts)
            rec['closed_at'] = e['ts'][:19] + 'Z'; sources['closed_at'] = src(e) + ' (transcript clock of the close call)'
    cc = latest(obs, 'comments_count')
    if cc:
        rec['comments_count_on_github'] = {'count': cc['f']['comments_count'], 'as_of': cc['ts'][:19] + 'Z'}
    if board:
        rec['board_row'] = board
    # comments
    comments, missing = build_comments(cms, seen_ids)
    rec['comments'] = comments
    rec['comment_ids_without_text'] = sorted(missing)
    rec['sources'] = sources
    have_any = any(k in rec for k in ('title', 'body')) or comments
    exact_c = sum(1 for c in comments if c['id'] and c.get('body_complete'))
    part_c = sum(1 for c in comments if c['id'] and c.get('body') is not None and not c.get('body_complete'))
    idless = sum(1 for c in comments if not c['id'])
    cov = {
        'number': n, 'kind': kind or '', 'title': 'y' if 'title' in rec else '',
        'title_src': sources.get('title', '').split(':')[0].split('@')[0],
        'body': ('complete' if rec.get('body_complete') else 'partial') if 'body' in rec else '',
        'labels': 'y' if 'labels' in rec else '', 'state': rec.get('state', ''),
        'comments_with_text': exact_c, 'comments_partial': part_c, 'comment_ids_seen': len(set(seen_ids) | set(c['id'] for c in comments if c['id'])),
        'comment_ids_without_text': len(missing), 'comments_no_id': idless,
        'github_count': (rec.get('comments_count_on_github') or {}).get('count', ''),
        'sources': ','.join(sorted(set(x.split('@')[0].split(' ')[0] for x in sources.values()) |
                                   set(c['source'].split('@')[0] for c in comments))),
    }
    if not have_any:
        cov['status'] = 'none'
    elif cov['title'] and cov['body'] == 'complete' and cov['state'] and not missing and part_c == 0 and \
            (cov['github_count'] == '' or exact_c + idless >= cov['github_count']):
        cov['status'] = 'full'
    else:
        cov['status'] = 'partial'
    return (rec if have_any else None), cov


def build_comments(cms, seen_ids):
    by_id = collections.defaultdict(list)
    idless = []
    for e in cms:
        if e.get('id'):
            by_id[e['id']].append(e)
        else:
            idless.append(e)
    out = []
    texts = {}            # normalized body -> comment (for matching id-less records)
    for cid, es in by_id.items():
        c = {'id': cid, 'type': 'comment'}
        ex = [x for x in es if x.get('body') is not None and x.get('exact')]
        if ex:
            e = max(ex, key=ts)
            c['body'] = e['body'].replace('\r\n', '\n'); c['body_complete'] = True; c['source'] = src(e)
        else:
            pa = [x for x in es if x.get('body') and x.get('clean', x['how'] != 'jq')]
            if pa:
                e = max(pa, key=lambda x: len(x['body']))
                c['body'] = e['body'].replace('\r\n', '\n'); c['body_complete'] = False; c['source'] = src(e) + ' (truncated read)'
            else:
                c['body'] = None; c['body_complete'] = False; c['source'] = src(es[0])
        au = [x['author'] for x in es if x.get('author')]
        c['author'] = au[0] if au else GH_LOGIN
        if not au:
            c['author_source'] = 'inferred: posted through gh, which ran as %s' % GH_LOGIN if any(x.get('posted') for x in es) else 'inferred: the only login seen on this repository'
        cr = [x['created_at'] for x in es if x.get('created_at')]
        if cr:
            c['created_at'] = min(cr)
        else:
            p = [x for x in es if x.get('posted')]
            c['created_at'] = (min(ts(x) for x in (p or es)))[:19] + 'Z'
            c['created_at_source'] = 'transcript clock of the %s call (GitHub time not seen)' % ('posting' if p else 'reading')
        up = [x['updated_at'] for x in es if x.get('updated_at')]
        if up:
            c['updated_at'] = max(up)
        out.append(c)
        if c['body']:
            texts.setdefault(nb(c['body']), c)
    # id-less: merge into id'd comments by text, else keep
    kept = {}
    for e in sorted(idless, key=lambda x: (not x.get('exact'), -len(x.get('body') or ''))):
        b = nb(e.get('body'))
        if not b or re.fullmatch(r'[-=_*#\s]*', b):
            continue                         # empty, or a separator line read as a record
        hit = texts.get(b)
        if hit is None and not e.get('exact'):
            hit = next((c for c in out if c.get('body') and nb(c['body']).startswith(b)), None)
        if hit is None and e.get('exact'):
            # a truncated id'd body that this exact text completes
            hit = next((c for c in out if c.get('body') and not c.get('body_complete') and c['id'] and b.startswith(nb(c['body']))), None)
            if hit is not None:
                hit['body'] = e['body'].replace('\r\n', '\n'); hit['body_complete'] = True; hit['source'] = src(e) + ' (matched by text)'
        if hit is not None:
            if e.get('created_at') and hit.get('created_at_source'):
                hit['created_at'] = e['created_at']; hit.pop('created_at_source')
            if e.get('author') and hit.get('author_source'):
                hit['author'] = e['author']; hit.pop('author_source')
            if e.get('ctype') == 'review' and hit.get('type') == 'comment' and not hit['id']:
                hit['type'] = 'review'
            continue
        if not e.get('exact') and not e.get('clean', e['how'] != 'jq'):
            continue
        key = (e.get('ctype'), e.get('created_at')) if e.get('created_at') else (e.get('ctype'), b[:4000])
        prev = kept.get(key)
        if prev is not None:
            if not prev.get('body_complete') and e.get('exact'):
                prev.update(body=e['body'].replace('\r\n', '\n'), body_complete=True, source=src(e))
            continue
        # a partial that is a prefix of an already kept text
        if not e.get('exact') and any(nb(k.get('body')).startswith(b) for k in kept.values()):
            continue
        c = {'id': None, 'type': e.get('ctype') or 'comment', 'body': e['body'].replace('\r\n', '\n'),
             'body_complete': bool(e.get('exact')), 'source': src(e),
             'author': e.get('author') or GH_LOGIN}
        if not e.get('author'):
            c['author_source'] = 'inferred: posted through gh, which ran as %s' % GH_LOGIN if e.get('posted') else 'inferred: the only login seen on this repository'
        if e.get('review_state'):
            c['review_state'] = e['review_state']
        if e.get('created_at'):
            c['created_at'] = e['created_at']
        elif e.get('posted'):
            c['created_at'] = ts(e)[:19] + 'Z'; c['created_at_source'] = 'transcript clock of the posting call'
        else:
            c['created_at'] = None; c['observed_before'] = ts(e)[:19] + 'Z'
        kept[key] = c
        texts.setdefault(b, c)
    out += list(kept.values())
    out.sort(key=lambda c: (c.get('created_at') or c.get('observed_before') or '', c['id'] or 0))
    have = set(c['id'] for c in out if c['id'] and c.get('body') is not None)
    missing = set(seen_ids) - have
    return out, missing


README = """# hakuX issue log, reconstructed (forge import set)

Built {built} by lane.issuerecon (`docs/lanes/issuerecon/recon.py` on branch `lane/issuerecon`).
GitHub suspended jreinach-alt/hakuX on 2026-09-29; this set rebuilds its issues, pull requests and
comment threads from what survives on this machine. Nothing here was paraphrased or filled in: a text that
could not be recovered is absent and counted below.

## Layout

- `issues/<n>.json`: one file per issue or PR number. Fields: `number`, `kind` (issue|pr), `title`, `body`,
  `body_complete`, `state` (open|closed|merged), `labels`, `author`, `created_at`, `closed_at`,
  `merged_at`, `draft`, `head`, `base`, `comments`, `comment_ids_without_text`, `comments_count_on_github`
  (the REST count when a read showed it, with its date), `board_row` (our board's own row, not GitHub's),
  and `sources` (where each field came from: the method, the transcript time, the transcript file).
- `comments[]`: `id` (GitHub comment id; null when the read did not show it), `type`
  (comment|review|review_comment), `author`, `created_at`, `updated_at`, `body`, `body_complete`,
  `source`. `created_at_source` / `author_source` mark values that are not GitHub's own: the transcript
  clock of the posting call, or the inferred login.
- `coverage.tsv`: one row per number 1..{top}.
- `totals.json`: the numbers below. `redactions.json`: what the secret scan removed (place and kind only).

## Totals

| | count |
|---|---:|
| numbers 1..{top} (GitHub numbers issues and PRs in one sequence) | {numbers} |
| fully recovered | {full} |
| partly recovered | {partial} |
| not recovered (no title, body or comment seen) | {none} |
| issues / PRs | {issues} / {prs} |
| title | {with_title} |
| body complete / only truncated | {body_complete} / {body_partial} |
| labels | {with_labels} |
| state | {with_state} |
| comment ids seen anywhere | {comment_ids_seen} |
| ... with full text | {comments_with_text} |
| ... with truncated text only | {comments_partial} |
| ... with no text | {comment_ids_without_text} |
| comments recovered without an id (reviews, close notes, reads that did not print the URL) | {comments_no_id} |

"Fully" means: title, complete body, state, every comment id seen has full text, and no fewer comments than
the last count GitHub reported (when one was seen). It cannot promise that no comment was missed: a
comment nobody on this machine ever read, posted or linked leaves no trace here.

## Sources, in order of use

1. Agent transcripts (`~/.claude/projects/**/*.jsonl`). Only Bash calls that ran `gh` (or
   `deliver.sh`, which wraps `gh api`) were read, and only GitHub issue/PR/comment fields were kept.
   - Posting calls (`gh issue|pr comment`, `gh issue|pr create`, `gh api -X POST .../comments`,
     `gh api -X PATCH`, `gh pr review`, `gh issue close --comment`, `deliver.sh send`): the text the agent
     sent, from the command, its heredoc, or the file it wrote earlier in the same session, paired with the
     URL GitHub returned. A body file changed by anything the parser cannot replay (`sed -i`, python, `>>`
     of unknown text) was dropped rather than guessed. `$(date ...)` in a posted text was evaluated at the
     transcript clock only when the call started at least 15 s before the minute turned.
   - Reading calls (`gh ... --json`, `gh api`, and `--jq` templates such as
     `"\\(.created_at) \\(.html_url)\\n\\(.body)"`): what GitHub held at that moment, including the owner's
     comments posted on the web. A body cut by `.body[:N]`, `| head`, or shared with other output is kept
     only as `body_complete: false`.
   - Where a comment was both posted and read, the latest text wins (comments were sometimes edited).
2. `origin/board:nv2a_issues.toml`: `board_row`, and the title only where GitHub's was never seen.
3. git `origin/master`: `fold: PR #N <branch> -- <title>` merges (fold.sh puts the PR title there) give
   merged state, head branch, the title at fold time, and the fold commit time as `merged_at` when
   GitHub's was not seen.
4. Wayback Machine: the CDX API answered on 2026-10-02 with zero captures for `github.com/jreinach-alt/*`.
   Nothing came from it.

Not used: the offline-era `docs/lanes/*/PR.md` and `OUTBOX.md` files written after the suspension. They
never reached GitHub; they are in git, and `recover_github.py` posts them after reinstatement.

## Known limits

- `author` is `jreinach-alt` throughout: every gh call on this machine ran as that login, and every author
  field read back is that login, so agent posts and the owner's web comments share it. The `[lane.x]`,
  `[job.x]`, `[host]` prefixes in the bodies say which agent wrote what.
- `state` is the last observation before the suspension (or the git fold); a PR merged or an issue closed
  after the last read on this machine may still read `open`.
- Labels are the last full read plus later `--add-label`/`--remove-label`/labels API calls seen in
  transcripts; label changes made by jobs outside a transcript are not seen.
- Comment ids that appear only as links inside other text are counted as "seen, no text".

## Secret scan

`secretscan.py` checked every string for GitHub/AWS/Slack/Anthropic tokens, private keys, `password=`-style
assignments, credentials in URLs and after "login ... as", keystore names, and high-entropy tokens.
{redacted}
High-entropy hits judged not secret (test names, Vulkan VUIDs, file names, run and session ids already public
on GitHub) are listed by hash in `secretscan-allow.json`.
"""


def write_readme(out_dir):
    import datetime
    tot = json.load(open(os.path.join(out_dir, 'totals.json')))
    red = []
    rp = os.path.join(out_dir, 'redactions.json')
    if os.path.exists(rp):
        red = json.load(open(rp))
    if red:
        lines = ['Redacted (replaced with `[REDACTED:<kind>]`):', '']
        for r in red:
            lines.append('- #%s %s: %s' % (r['place'][0], ' / '.join(map(str, r['place'][1:])), r['kind']))
        redacted = '\n'.join(lines)
    else:
        redacted = 'Nothing needed redacting.'
    now = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
    with open(os.path.join(out_dir, 'README.md'), 'w') as f:
        f.write(README.format(built=now, top=tot['numbers'], redacted=redacted, **tot))


def write_coverage(out_dir, cov, top):
    cols = ['number', 'status', 'kind', 'title', 'title_src', 'body', 'labels', 'state', 'comments_with_text',
            'comments_partial', 'comment_ids_without_text', 'comment_ids_seen', 'comments_no_id', 'github_count', 'sources']
    with open(os.path.join(out_dir, 'coverage.tsv'), 'w') as f:
        f.write('\t'.join(cols) + '\n')
        for r in cov:
            f.write('\t'.join(str(r.get(c, '')) for c in cols) + '\n')
    st = collections.Counter(r['status'] for r in cov)
    tot = {
        'numbers': top, 'full': st['full'], 'partial': st['partial'], 'none': st['none'],
        'issues': sum(1 for r in cov if r['kind'] == 'issue'), 'prs': sum(1 for r in cov if r['kind'] == 'pr'),
        'with_title': sum(1 for r in cov if r['title']), 'body_complete': sum(1 for r in cov if r['body'] == 'complete'),
        'body_partial': sum(1 for r in cov if r['body'] == 'partial'),
        'with_labels': sum(1 for r in cov if r['labels']), 'with_state': sum(1 for r in cov if r['state']),
        'comments_with_text': sum(r['comments_with_text'] for r in cov),
        'comments_partial': sum(r['comments_partial'] for r in cov),
        'comment_ids_without_text': sum(r['comment_ids_without_text'] for r in cov),
        'comment_ids_seen': sum(r['comment_ids_seen'] for r in cov),
        'comments_no_id': sum(r['comments_no_id'] for r in cov),
    }
    json.dump(tot, open(os.path.join(out_dir, 'totals.json'), 'w'), indent=1)
    print(json.dumps(tot, indent=1))
