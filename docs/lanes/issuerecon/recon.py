#!/usr/bin/env python3
"""recon.py: rebuild the GitHub issue/PR log of jreinach-alt/hakuX from what survives locally.

  python3 recon.py scan   [--scratch DIR]          stream ~/.claude/projects/**/*.jsonl -> DIR/events.jsonl
  python3 recon.py build  [--scratch DIR] [--out DIR]  events + board + git -> OUT/issues/<n>.json, coverage.tsv

Only GitHub issue/PR/comment content is kept: the scan looks only at Bash tool calls that run `gh`
(or name the GitHub API), and from those keeps only parsed issue/comment fields, never other output.
The posting side (gh issue comment / pr comment / issue create / pr create / api PATCH|POST) gives the
exact text an agent posted, paired with the URL GitHub returned. The reading side (gh --json, gh api
JSON) gives what GitHub held at that moment, including comments posted on the web.
"""
import collections, glob, hashlib, json, os, re, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from multiprocessing import Pool

HOME = os.path.expanduser('~')
ROOT = os.path.join(HOME, '.claude/projects')
REPO = 'jreinach-alt/hakuX'
GH_CALL = re.compile(r'\bgh\s+(issue|pr|api|search)\b')
GH_ANY = re.compile(r'\bgh\s+(issue|pr|api|search|run\s+view)\b|api\.github\.com|github\.com/jreinach|deliver\.sh\s+(send|inbox)')
URL = re.compile(r'github\.com/jreinach-alt/hakuX/(issues|pull)/(\d+)(?:/files|/commits)?(?:#(issuecomment|pullrequestreview|discussion_r)-?(\d+))?')
CMT_URL = re.compile(r'github\.com/jreinach-alt/hakuX/(?:issues|pull)/(\d+)#issuecomment-(\d+)')
MIN_CID = 10 ** 9           # real comment ids on this repo are ~5.8e9; fixtures use small ids
MAX_NUM = 2000              # sanity bound; tightened in build from creates


# ---------------------------------------------------------------- shell helpers
def assignments(cmd):
    """Simple VAR=value assignments in a command (enough to expand $S/file.md paths)."""
    env = {}
    for m in re.finditer(r'(?:^|[\s;&|(])([A-Za-z_]\w*)=("([^"$`]*)"|\'([^\']*)\'|([^\s;&|"\'`$()]*))', cmd):
        v = m.group(3) if m.group(3) is not None else m.group(4) if m.group(4) is not None else m.group(5)
        if m.group(5) is not None and cmd[m.end():m.end() + 1] in ('$', '`', '('):
            v = None                      # VAR=$(...): a value we do not know
        env[m.group(1)] = v
    return env


def expand(path, env, cwd):
    if path is None:
        return None
    path = path.strip('\'"')
    for _ in range(3):
        path = re.sub(r'\$\{(\w+)\}|\$(\w+)', lambda m: env.get(m.group(1) or m.group(2)) or m.group(0), path)
    if path.startswith('~'):
        path = HOME + path[1:]
    if '$' in path or '`' in path:
        return None
    if not path.startswith('/') and cwd:
        path = os.path.normpath(os.path.join(cwd, path))
    return path


HD = re.compile(r"<<(-?)[ \t]*(['\"]?)([A-Za-z_][A-Za-z_0-9]*)\2")


def heredocs(cmd):
    """[(start, end, line, content, quoted)] for each heredoc in a command."""
    out = []
    pos = 0
    while True:
        m = HD.search(cmd, pos)
        if not m:
            return out
        nl = cmd.find('\n', m.end())
        if nl < 0:
            return out
        delim = m.group(3)
        term = re.compile(r'^' + (r'\t*' if m.group(1) else '') + re.escape(delim) + r'[ \t]*\)?\s*$', re.M)
        t = term.search(cmd, nl + 1)
        if not t:
            return out
        ls = cmd.rfind('\n', 0, m.start()) + 1
        line = cmd[ls:nl]
        content = cmd[nl + 1:t.start()]
        out.append((m.start(), t.end(), line, content, bool(m.group(2))))
        pos = t.end()


def heredoc_target(line):
    """File a heredoc line writes: cat > F <<EOF, cat <<EOF > F, tee F <<EOF."""
    s = HD.sub(' ', line)
    m = re.search(r'(?:^|[\s;&(])(?:cat|tee(?:\s+-a)?)\b[^|;&]*?(?<![0-9&])>{1,2}\s*([^\s;&|)]+)', s) or \
        re.search(r'\btee\s+(?:-a\s+)?([^\s;&|)-][^\s;&|)]*)', s)
    return m.group(1) if m else None


def inline_vars(cmd):
    """VAR=$(date ...) then "$VAR": put the substitution in place so the clock can resolve it."""
    for m in re.finditer(r'(?:^|[\s;&(])([A-Za-z_]\w*)="?\$\(((?:TZ=\S+\s+)?date\b[^()]*)\)"?', cmd):
        var, inner = m.group(1), m.group(2)
        head, tail = cmd[:m.end()], cmd[m.end():]
        tail = re.sub(r'\$\{' + var + r'\}|\$' + var + r'\b', lambda _: '$(' + inner + ')', tail)
        cmd = head + tail
    return cmd


def unquoted_heredoc(content, env, ts):
    """An unquoted heredoc expands $(...), $VAR and backslash escapes. Resolve what we can; None if anything
    remains that we cannot know."""
    out, i, n = [], 0, len(content)
    while i < n:
        c = content[i]
        if c == '\\' and i + 1 < n and content[i + 1] in '$`\\\n':
            if content[i + 1] != '\n':
                out.append(content[i + 1])
            i += 2
        elif c == '$' and i + 1 < n and content[i + 1] == '(':
            k, depth = i + 2, 1
            while k < n and depth:
                depth += {'(': 1, ')': -1}.get(content[k], 0)
                k += 1
            v = clock(content[i + 2:k - 1].strip(), ts)
            if v is None:
                return None
            out.append(v)
            i = k
        elif c == '$' and i + 1 < n and (content[i + 1].isalpha() or content[i + 1] in '_{'):
            m = re.match(r'\$\{?([A-Za-z_]\w*)\}?', content[i:])
            if env.get(m.group(1)) is None or '$' in env[m.group(1)]:
                return None
            out.append(env[m.group(1)])
            i += m.end()
        elif c == '`':
            return None
        else:
            out.append(c)
            i += 1
    return ''.join(out)


def inline_writes(cmd, env, cwd, fs=None, ts=None):
    """Files a command writes with literal content: heredoc to a file, printf '%s\\n' "x" > f, echo "x" > f."""
    out = {}
    for (s, e, line, content, quoted) in heredocs(cmd):
        tgt = heredoc_target(line)
        p = expand(tgt, env, cwd) if tgt else None
        if p and not quoted:
            content = unquoted_heredoc(content, env, ts)
        if p:
            if content is None:
                out[p] = None
            elif re.search(r'>>\s*' + re.escape(tgt), line):
                prev = out.get(p) if p in out else (fs.lookup(p) if fs else None)
                out[p] = None if prev is None else prev + content
            else:
                out[p] = content
    for m in re.finditer(r"(?:^|[\s;&(])(printf\s+'%s\\n'|echo)\s+(?=[\"'])", cmd):
        w, j, ex = shell_word(cmd, m.end())
        r = re.match(r'\s*>\s*([^\s;&|)]+)', cmd[j:])
        if ex and r and '\x00' not in w:
            p = expand(r.group(1), env, cwd)
            if p:
                out[p] = w + '\n'
    return out


def shell_word(s, i):
    """Parse one shell word starting at s[i]. Returns (text, end, exact). exact=False if it holds an
    expansion we could not resolve."""
    out = []
    exact = True
    n = len(s)
    while i < n and s[i] in ' \t':
        i += 1
    while i < n and s[i] not in ' \t\n;&|)':
        c = s[i]
        if c == "'":
            j = s.find("'", i + 1)
            if j < 0:
                return ''.join(out) + s[i + 1:], n, False
            out.append(s[i + 1:j]); i = j + 1
        elif c == '$' and i + 1 < n and s[i + 1] == "'":
            j = i + 2
            buf = []
            while j < n and s[j] != "'":
                if s[j] == '\\' and j + 1 < n:
                    e = s[j + 1]
                    buf.append({'n': '\n', 't': '\t', '\\': '\\', "'": "'", '"': '"'}.get(e, '\\' + e)); j += 2
                else:
                    buf.append(s[j]); j += 1
            out.append(''.join(buf)); i = j + 1
        elif c == '"':
            j = i + 1
            buf = []
            while j < n and s[j] != '"':
                if s[j] == '\\' and j + 1 < n and s[j + 1] in '"\\$`\n':
                    if s[j + 1] != '\n':
                        buf.append(s[j + 1])
                    j += 2
                elif s[j] == '$' and j + 1 < n and s[j + 1] == '(':
                    k, depth = j + 2, 1          # command substitution: keep raw, resolved by caller
                    while k < n and depth:
                        if s[k] == '(':
                            depth += 1
                        elif s[k] == ')':
                            depth -= 1
                        k += 1
                    buf.append('\x00SUB' + s[j + 2:k - 1] + '\x00'); j = k
                elif s[j] == '$' and j + 1 < n and (s[j + 1].isalnum() or s[j + 1] in '_{@*#?!'):
                    exact = False; buf.append(s[j]); j += 1
                elif s[j] == '`':
                    exact = False; buf.append(s[j]); j += 1
                else:
                    buf.append(s[j]); j += 1
            out.append(''.join(buf)); i = j + 1
        elif c == '\\' and i + 1 < n:
            out.append(s[i + 1]); i += 2
        elif c == '$':
            exact = False; out.append(c); i += 1
        else:
            out.append(c); i += 1
    return ''.join(out), i, exact


# ---------------------------------------------------------------- per-transcript scan
class FileState:
    def __init__(self, rel):
        self.rel = rel
        self.writes = {}          # abs path -> content (Write tool, Bash heredoc to file); None = unknown
        self.edits_pending = {}

    def lookup(self, path):
        if not path:
            return None
        if path in self.writes:
            return self.writes[path]
        b = os.path.basename(path)
        cands = [p for p in self.writes if os.path.basename(p) == b]
        if len(cands) == 1:
            return self.writes[cands[0]]
        return None


DATE_SUB = re.compile(r"""^(?:TZ=['"]?([\w/]+)['"]?\s+)?date(\s+-u)?\s+(['"]?)\+([^'"\s]*(?:\s[^'"\s]*)?)\3$""")


def clock(inner, ts):
    """$(date ...) evaluated at the transcript's clock. Only when the call is far from a minute boundary
    (the command ran within seconds of the timestamp) and the format has no seconds."""
    m = DATE_SUB.match(inner)
    if not m or not ts:
        return None
    fmt = m.group(4)
    if re.search(r'%[sSTNr]', fmt):
        return None
    from datetime import datetime, timezone
    from zoneinfo import ZoneInfo
    t = datetime.strptime(ts[:19], '%Y-%m-%dT%H:%M:%S').replace(tzinfo=timezone.utc)
    if t.second >= 45:
        return None
    tz = 'UTC' if m.group(2) else (m.group(1) or 'America/Los_Angeles')
    try:
        return t.astimezone(ZoneInfo(tz)).strftime(fmt.replace('%F', '%Y-%m-%d'))
    except Exception:
        return None


def resolve_subst(text, fs, env, cwd, local, ts=None):
    """Resolve \x00SUB...\x00 markers for $(cat F), $(tail -n +K F), $(head -N F), $(cat <<EOF...), $(date ...)."""
    exact = True

    def rep(m):
        nonlocal exact
        inner = m.group(1).strip()
        dv = clock(inner, ts)
        if dv is not None:
            return dv
        hd = heredocs(inner)
        if hd and re.match(r'cat\s*<<', inner):
            return hd[0][3].rstrip('\n')
        mm = re.fullmatch(r'cat\s+(\S+)', inner) or re.fullmatch(r'(tail)\s+-n\s*\+(\d+)\s+(\S+)', inner) or \
            re.fullmatch(r'(head)\s+-(?:n\s*)?(\d+)\s+(\S+)', inner)
        if mm:
            if len(mm.groups()) == 1:
                kind, k, p = 'cat', 0, mm.group(1)
            else:
                kind, k, p = mm.group(1), int(mm.group(2)), mm.group(3)
            path = expand(p, env, cwd)
            content = local.get(path) if path in local else fs.lookup(path)
            if content is not None:
                lines = content.split('\n')
                if content.endswith('\n'):
                    lines = lines[:-1]
                if kind == 'tail':
                    lines = lines[k - 1:]
                elif kind == 'head':
                    lines = lines[:k]
                return '\n'.join(lines).rstrip('\n')
        exact = False
        return '$(' + m.group(1) + ')'
    out = re.sub(r'\x00SUB(.*?)\x00', rep, text, flags=re.S)
    return out, exact


def flag_arg(seg, names):
    """Value of the first of the given flags in a gh call segment: (raw_word, exact) or None."""
    for nm in names:
        for m in re.finditer(r'(?:^|\s)' + re.escape(nm) + r'(?:\s+|=)', seg):
            w, _, ex = shell_word(seg, m.end())
            return w, ex
    return None


def gh_segments(cmd):
    """Split a command into gh call segments (start offsets) with heredoc bodies removed."""
    segs = []
    for m in re.finditer(r'\bgh\s+(issue|pr|api|search|label)\b', cmd):
        # segment runs to the next unquoted ; && || | newline; approximate with shell_word walking
        i = m.start()
        j = m.end()
        n = len(cmd)
        while j < n:
            while j < n and cmd[j] in ' \t':
                j += 1
            if j >= n or cmd[j] in ';&|\n)':
                break
            if cmd.startswith('<<', j):
                break
            _, j2, _ = shell_word(cmd, j)
            if j2 == j:
                j += 1
            else:
                j = j2
        segs.append((i, j, cmd[i:j]))
    return segs


def jq_of(seg):
    r = flag_arg(seg, ['--jq', '-q'])
    return r[0] if r else None


SLICE = re.compile(r'\[\s*(-?\d*)\s*:\s*(-?\d*)\s*\]')
TRANSFORM = re.compile(r'\b(gsub|sub|split|ltrimstr|rtrimstr|ascii_downcase|ascii_upcase|explode|implode|tojson|@sh|@json|@base64|join|tostring|length|limit|first|last)\b|\.\[\s*\d|\[\s*\d+\s*\]')


def body_bound(jq):
    """None = body untouched; int = bodies shorter than this are complete; 0 = never complete."""
    if not jq:
        return None
    bound = None
    for lo, hi in SLICE.findall(jq):
        if lo not in ('', '0') or not hi or hi.startswith('-'):
            return 0
        bound = int(hi) if bound is None else min(bound, int(hi))
    if re.search(r'\b(gsub|sub|ltrimstr|rtrimstr|ascii_downcase|ascii_upcase|explode|implode)\b', jq):
        return 0
    return bound


def num(x):
    try:
        return int(x)
    except Exception:
        return None


def norm_state(s, merged=None):
    if not isinstance(s, str):
        return None
    s = s.lower()
    if merged:
        return 'merged'
    return {'open': 'open', 'closed': 'closed', 'merged': 'merged'}.get(s)


def label_names(v):
    if not isinstance(v, list):
        return None
    out = []
    for x in v:
        if isinstance(x, dict) and isinstance(x.get('name'), str):
            out.append(x['name'])
        elif isinstance(x, str):
            out.append(x)
        else:
            return None
    return out


def login(v):
    if isinstance(v, dict):
        return v.get('login')
    if isinstance(v, str):
        return v
    return None


def json_values(text):
    """Every top-level JSON object/array found in a tool output (handles --paginate concatenation)."""
    dec = json.JSONDecoder()
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if c in '{[' and (i == 0 or text[i - 1] in '\n]}' or text[i - 1] in ' \t' and text.rfind('\n', 0, i) == text.rfind('\n', 0, i)):
            try:
                v, end = dec.raw_decode(text, i)
                if isinstance(v, (dict, list)) and (v or c == '['):
                    yield v
                    i = end
                    continue
            except ValueError:
                pass
        nl = text.find('\n', i + 1)
        j = min([p for p in (text.find('{', i + 1), text.find('[', i + 1)) if p >= 0] or [n])
        i = j if (nl < 0 or j <= nl or j == n) else j
        if j == n:
            break


class Scan:
    def __init__(self, fs, rec):
        self.fs = fs
        self.rec = rec
        self.ev = []
        self.claimed = set()

    def emit(self, **kw):
        kw.setdefault('ts', self.rec['ts'])
        kw.setdefault('src', self.rec['src'])
        self.ev.append(kw)


def walk_json(sc, v, ctx, bound, depth=0, parent_n=None):
    """Emit issue/comment observations from JSON value v."""
    if depth > 6:
        return
    if isinstance(v, list):
        for x in v:
            walk_json(sc, x, ctx, bound, depth + 1, parent_n)
        return
    if not isinstance(v, dict):
        return
    url = v.get('html_url') or v.get('url') or ''
    url = url if isinstance(url, str) else ''
    um = URL.search(url)
    if url and 'github.com' in url and not um and 'api.github.com/repos/' + REPO not in url:
        return                                           # some other repo
    body = v.get('body') if isinstance(v.get('body'), str) else None
    exact = True
    if body is not None and bound is not None:
        exact = bound > 0 and len(body) < bound
    # ---- comments / reviews
    frag = um.group(3) if um else None
    cid = num(um.group(4)) if um and um.group(4) else None
    if frag is None and isinstance(v.get('issue_url'), str) and 'body' in v and num(v.get('id')):
        im = re.search(r'/repos/' + REPO + r'/issues/(\d+)$', v['issue_url'])
        if not im:
            return
        frag, cid, nn = 'issuecomment', num(v.get('id')), int(im.group(1))
    else:
        nn = int(um.group(2)) if um else None
    if frag in ('issuecomment', 'pullrequestreview', 'discussion_r'):
        if frag == 'issuecomment' and (cid is None or cid < MIN_CID):
            return
        sc.emit(t='comment', n=nn, id=cid, ctype={'issuecomment': 'comment', 'pullrequestreview': 'review',
                                                   'discussion_r': 'review_comment'}[frag],
                author=login(v.get('user')) or login(v.get('author')),
                created_at=v.get('created_at') or v.get('createdAt') or v.get('submitted_at') or v.get('submittedAt'),
                updated_at=v.get('updated_at') or v.get('updatedAt') or v.get('lastEditedAt'),
                body=body, exact=exact, how='json')
        return
    # ---- issue / PR objects
    n = num(v.get('number'))
    kind = None
    if um and not frag:
        n2 = int(um.group(2))
        if n is not None and n != n2:
            return
        n, kind = n2, ('pr' if um.group(1) == 'pull' else 'issue')
    if n is None and ctx.get('n') is not None and body is not None and 'title' not in v and \
            re.search(r'\.comments\b', ctx.get('jq') or '') and \
            any(k in v for k in ('createdAt', 'created_at', 'created', 'author', 'login', 'user')):
        sc.emit(t='comment', n=ctx['n'], id=None, ctype='comment',
                author=login(v.get('author')) or login(v.get('user')) or (v.get('login') if isinstance(v.get('login'), str) else None),
                created_at=next((v[k] for k in ('createdAt', 'created_at', 'created') if isinstance(v.get(k), str)
                                 and re.fullmatch(r'\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ', v[k])), None),
                updated_at=None, body=body, exact=exact, how='json-jq', clean=True)
        return
    if n is None and depth == 0 and ctx.get('n') is not None and \
            any(k in v for k in ('body', 'comments', 'title', 'labels', 'state')) and \
            not re.search(r'\.(comments|reviews)\b(?!\s*\|\s*length)', ctx.get('jq') or '') and \
            not ({'createdAt', 'author'} <= set(v) and 'title' not in v and 'comments' not in v):
        n = ctx['n']
    if n is not None and not um and not ctx.get('hakux'):
        return
    if n is not None and (n <= 0 or n > MAX_NUM):
        return
    if n is not None and ('title' in v or 'body' in v or 'state' in v or 'labels' in v or 'comments' in v):
        if kind is None:
            if 'pull_request' in v or 'merged_at' in v or 'mergedAt' in v or 'headRefName' in v or 'isDraft' in v or 'head' in v:
                kind = 'pr'
            elif ctx.get('kind'):
                kind = ctx['kind']
        f = {}
        if isinstance(v.get('title'), str):
            f['title'] = v['title']
        if body is not None:
            f['body'] = body
            f['body_exact'] = exact
        merged = v.get('merged_at') or v.get('mergedAt') or (v.get('merged') is True)
        st = norm_state(v.get('state'), merged)
        if st:
            f['state'] = st
        lb = label_names(v.get('labels'))
        if lb is not None and bound is None or (lb is not None and not re.search(r'labels\s*\|', ctx.get('jq') or '')):
            if lb is not None:
                f['labels'] = lb
        a = login(v.get('user')) or login(v.get('author'))
        if a:
            f['author'] = a
        for k_out, keys in (('created_at', ('created_at', 'createdAt')), ('closed_at', ('closed_at', 'closedAt')),
                            ('merged_at', ('merged_at', 'mergedAt')), ('updated_at', ('updated_at', 'updatedAt'))):
            for k in keys:
                if isinstance(v.get(k), str) and v.get(k):
                    f[k_out] = v[k]
        if isinstance(v.get('draft'), bool):
            f['draft'] = v['draft']
        elif isinstance(v.get('isDraft'), bool):
            f['draft'] = v['isDraft']
        if isinstance(v.get('headRefName'), str):
            f['head'] = v['headRefName']
        elif isinstance(v.get('head'), dict) and isinstance(v['head'].get('ref'), str):
            f['head'] = v['head']['ref']
        if isinstance(v.get('baseRefName'), str):
            f['base'] = v['baseRefName']
        elif isinstance(v.get('base'), dict) and isinstance(v['base'].get('ref'), str):
            f['base'] = v['base']['ref']
        if isinstance(v.get('comments'), int) and not isinstance(v.get('comments'), bool):
            f['comments_count'] = v['comments']
        if f:
            sc.emit(t='issue', n=n, kind=kind, f=f, how='json')
        cm = v.get('comments')
        if isinstance(cm, dict) and isinstance(cm.get('totalCount'), int):
            sc.emit(t='issue', n=n, kind=kind, f={'comments_count': cm['totalCount']}, how='json')
        if isinstance(cm, list):
            for i, c in enumerate(cm):
                if not isinstance(c, dict):
                    continue
                cu = c.get('url') or c.get('html_url') or ''
                m2 = CMT_URL.search(cu) if isinstance(cu, str) else None
                cb = c.get('body') if isinstance(c.get('body'), str) else None
                cex = True if bound is None else (bound > 0 and cb is not None and len(cb) < bound)
                sc.emit(t='comment', n=n, id=int(m2.group(2)) if m2 else None, ctype='comment',
                        author=login(c.get('author')) or login(c.get('user')),
                        created_at=c.get('createdAt') or c.get('created_at'),
                        updated_at=c.get('updatedAt') or c.get('lastEditedAt') or c.get('updated_at'),
                        body=cb, exact=cex, how='json-nested', order=i)
        for k in ('reviews',):
            if isinstance(v.get(k), list):
                for c in v[k]:
                    if isinstance(c, dict) and isinstance(c.get('body'), str) and c['body'].strip():
                        cex = True if bound is None else (bound > 0 and len(c['body']) < bound)
                        sc.emit(t='comment', n=n, id=num(c.get('id')) if num(c.get('id')) else None, ctype='review',
                                author=login(c.get('author')), created_at=c.get('submittedAt'),
                                updated_at=None, body=c['body'], exact=cex, how='json-nested')
        return
    for x in v.values():
        if isinstance(x, (list, dict)):
            walk_json(sc, x, ctx, bound, depth + 1, parent_n)


def is_hakux_ctx(cmd, cwd):
    others = [r for r in re.findall(r'repos/([\w.-]+/[\w.-]+)', cmd) if r != REPO]
    others += [r for r in re.findall(r'--repo[ =]([\w.-]+/[\w.-]+)', cmd) if r != REPO]
    if others:
        return False
    return bool(cwd and ('/hakuX' in cwd or '/hakux-work/' in cwd and '/wt/' in cwd or 'hakux-work/units' in cwd))


DELIVER_FOOTER = ("---\n"
                  "_Routed by `docs/testing/jobs/deliver.sh`. This comment IS the "
                  "delivery: the thread is append-only, both sides can read it, and "
                  "`deliver.sh inbox %s` lists every one of these. "
                  "`$DISPATCH_DIR/deliveries/%s.md` is retired and is not read by "
                  "anything._\n")


def deliver_posts(sc, cmd, out, cwd, env, local):
    """deliver.sh send <lane> <n> -b TEXT|-F FILE posts "[job.deliver] lane.<lane>" + text + a fixed footer
    (docs/testing/jobs/deliver.sh, unchanged since it was added on 2026-09-19)."""
    sends = []
    for m in re.finditer(r'deliver\.sh\s+send\s+([\w.-]+)\s+(\d+)\s+(-F|--file|-b|--body)\s+', cmd):
        w, _, ex = shell_word(cmd, m.end())
        lane, nn = m.group(1), int(m.group(2))
        if m.group(3) in ('-F', '--file'):
            p = expand(w, env, cwd)
            text = local.get(p) if p in local else sc.fs.lookup(p)
            if text is not None:
                text = text.rstrip('\n')      # $(cat file)
        else:
            text, ex2 = resolve_subst(w, sc.fs, env, cwd, local, sc.rec['ts'])
            text = text if (ex and ex2) else None
        sends.append((lane, nn, text))
    if not sends:
        return
    got = re.findall(r'delivered to lane\.([\w.-]+) on #(\d+) at (\S+)\s*\n\s*(https://github\.com/jreinach-alt/hakuX/(?:issues|pull)/\d+#issuecomment-\d+)', out or '')
    if not got:
        # output cut to the URL line (| tail -1): pair bare URL lines by thread, only when nothing else in
        # the command posts to that thread
        bare = re.findall(r'(?m)^\s*(https://github\.com/jreinach-alt/hakuX/(?:issues|pull)/(\d+)#issuecomment-\d+)\s*$', out or '')
        for nn in set(x[1] for x in sends):
            mine = [x for x in sends if x[1] == nn]
            urls = [u for u, k in bare if int(k) == nn]
            others = re.search(r'gh\s+(issue|pr)\s+comment\s+%d\b|issues/%d/comments' % (nn, nn), cmd)
            if len(mine) == len(urls) and not others:
                got += [(lane, str(nn), None, u) for (lane, _, _), u in zip(mine, urls)]
    for (lane, nn, text) in sends:
        for g in got:
            if g[0] == lane and int(g[1]) == nn:
                got.remove(g)
                m = CMT_URL.search(g[3])
                cid = int(m.group(2))
                sc.claimed.add(cid)
                body = None
                if text is not None:
                    body = "[job.deliver] lane.%s\n\n%s\n\n" % (lane, text.rstrip()) + DELIVER_FOOTER % (lane, lane)
                sc.emit(t='comment', n=nn, id=cid, ctype='comment', author=None, created_at=g[2], updated_at=None,
                        body=body, exact=body is not None, how='posted-deliver', posted=True)
                break


def scan_posts(sc, cmd, out, cwd):
    """Comments, issues and PRs an agent created or edited: the text from the command, the id from the output."""
    cmd = inline_vars(cmd)
    env = assignments(cmd)
    ts = sc.rec['ts']
    local = inline_writes(cmd, env, cwd, sc.fs, ts)
    hd_by_start = heredocs(cmd)
    deliver_posts(sc, cmd, out, cwd, env, local)
    urls = [(m.start(), m.group(1), int(m.group(2)), m.group(3), num(m.group(4))) for m in URL.finditer(out or '')]
    created = [u for u in urls if u[3] is None]
    cmts = [u for u in urls if u[3] == 'issuecomment' and re.match(r'\s*(https://)?$', out[out.rfind('\n', 0, u[0]) + 1:u[0]])]
    segs = gh_segments(cmd)
    posts = []
    for (s, e, seg) in segs:
        m = re.match(r'gh\s+(issue|pr)\s+(comment|create|edit|close|reopen|review|merge|ready)\b', seg)
        api = re.match(r'gh\s+api\b', seg)
        if not m and not api:
            continue
        if api:
            meth = re.search(r'(?:-X|--method)\s+(\w+)', seg)
            meth = meth.group(1).upper() if meth else ('POST' if re.search(r'\s-[fF]\s|--field|--raw-field', seg) else 'GET')
            pm = re.search(r'repos/(?:jreinach-alt/hakuX|:owner/:repo|\{owner\}/\{repo\})/(issues|pulls)(?:/(\d+|\$\w+))?(/comments|/labels(?:/[\w%:.-]+)?)?\b', seg)
            if meth == 'GET' or not pm:
                continue
            what = {'POST': {'/comments': 'comment'}, 'PATCH': {None: 'edit'}}.get(meth, {}).get(pm.group(3))
            if pm.group(3) and pm.group(3).startswith('/labels'):
                what = 'labels'
            if meth == 'POST' and pm.group(2) is None and pm.group(3) is None:
                what = 'create'
            if what is None:
                continue
            nn = num(pm.group(2))
            fields = {}
            for fm in re.finditer(r'(?:^|\s)(-f|-F|--field|--raw-field)\s+', seg):
                w, _, ex = shell_word(seg, fm.end())
                if '=' in w:
                    k, val = w.split('=', 1)
                    if k.startswith('labels'):
                        fields.setdefault('labels', []).append(val); continue
                    if fm.group(1) in ('-F', '--field') and val.startswith('@'):
                        p = expand(val[1:], env, cwd)
                        val = local.get(p) if p in local else sc.fs.lookup(p)
                        ex = val is not None
                    elif val is not None:
                        val, ex2 = resolve_subst(val, sc.fs, env, cwd, local, ts)
                        ex = ex and ex2
                    fields[k] = (val, ex)
            posts.append(dict(kind='api', what=what, n=nn, seg=seg, fields=fields,
                              noun='pr' if pm.group(1) == 'pulls' else 'issue', start=s))
            continue
        noun, verb = m.group(1), m.group(2)
        nm = re.match(r'gh\s+\w+\s+\w+\s+(\d+)\b', seg)
        nn = int(nm.group(1)) if nm else None
        body, bex = None, False
        b = flag_arg(seg, ['--body', '-b'])
        if verb in ('close', 'reopen', 'merge') and not b:
            b = flag_arg(seg, ['--comment', '-c']) if verb != 'merge' else None
        if b:
            body, bex = b
            body, ex2 = resolve_subst(body, sc.fs, env, cwd, local, ts)
            bex = bex and ex2
        bf = flag_arg(seg, ['--body-file', '-F'])
        if bf and verb != 'merge':
            p = bf[0]
            if p == '-':
                # stdin heredoc attached to this call
                hs = [h for h in hd_by_start if h[0] >= s and h[0] <= e + 3]
                body, bex = (hs[0][3], True) if hs else (None, False)
            else:
                p = expand(p, env, cwd)
                body = local.get(p) if p in local else sc.fs.lookup(p)
                bex = body is not None
        title = None
        t = flag_arg(seg, ['--title', '-t'])
        if t:
            title, tex = t
            title, tex2 = resolve_subst(title, sc.fs, env, cwd, local, ts)
            if not (tex and tex2):
                title = None
        labels = []
        for lm in re.finditer(r'(?:^|\s)(?:--label|-l|--add-label)(?:\s+|=)', seg):
            w, _, ex = shell_word(seg, lm.end())
            if ex:
                labels += [x.strip() for x in w.split(',') if x.strip()]
        rm_labels = []
        for lm in re.finditer(r'(?:^|\s)--remove-label(?:\s+|=)', seg):
            w, _, ex = shell_word(seg, lm.end())
            if ex:
                rm_labels += [x.strip() for x in w.split(',') if x.strip()]
        draft = '--draft' in seg or re.search(r'\s-d\b', seg) is not None
        base = flag_arg(seg, ['--base', '-B'])
        head = flag_arg(seg, ['--head', '-H'])
        rv = None
        if verb == 'review':
            rv = 'APPROVED' if re.search(r'--approve|\s-a\b', seg) else 'CHANGES_REQUESTED' if re.search(r'--request-changes|\s-r\b', seg) else 'COMMENTED'
        posts.append(dict(kind='gh', noun=noun, what=verb, n=nn, body=body, bex=bex, title=title, labels=labels,
                          rm_labels=rm_labels, draft=draft, base=base[0] if base else None,
                          head=head[0] if head else None, review=rv, start=s))
    if not posts:
        return
    if sc.rec['err'] and not urls:
        return
    # pair comment posts with comment URLs, creates with new-object URLs, in order
    cposts = [p for p in posts if (p['kind'] == 'gh' and p['what'] == 'comment') or (p['kind'] == 'api' and p['what'] == 'comment')]
    crs = [p for p in posts if p['what'] == 'create']
    claimed = sc.claimed
    uniq, seen_ids = [], set()
    for u in cmts:
        if u[4] not in seen_ids and u[4] not in claimed:
            seen_ids.add(u[4]); uniq.append(u)
    pairs = []
    if cposts and all(p['n'] is not None for p in cposts):
        for nn in sorted(set(p['n'] for p in cposts)):
            ps = [p for p in cposts if p['n'] == nn]
            us = [u for u in uniq if u[2] == nn]
            if len(ps) == len(us):
                pairs += list(zip(ps, us))
    elif cposts and len(cposts) == len(uniq):
        pairs = [(p, u) for p, u in zip(cposts, uniq) if p['n'] is None or p['n'] == u[2]]
    for p, u in pairs:
        if p['kind'] == 'gh':
            body, bex = p['body'], p['bex']
        else:
            body, bex = p['fields'].get('body', (None, False))
        sc.emit(t='comment', n=u[2], id=u[4], ctype='comment', author=None, created_at=None, updated_at=None,
                body=body if bex else None, exact=bool(bex), how='posted', posted=True)
    if crs:
        news = [u for u in created if u[0] >= 0]
        # outputs of creates are the bare URL lines; keep the order of distinct new URLs
        seen, order = set(), []
        for u in news:
            if (u[1], u[2]) not in seen and re.search(r'(^|\n|: )https://github\.com/jreinach-alt/hakuX/(issues|pull)/%d\s*($|\n)' % u[2], out):
                seen.add((u[1], u[2])); order.append(u)
        if len(order) == len(crs):
            for p, u in zip(crs, order):
                kind = 'pr' if u[1] == 'pull' else 'issue'
                if p['kind'] == 'gh':
                    if (p['noun'] == 'pr') != (kind == 'pr'):
                        continue
                    f = {'author': None}
                    if p['title']:
                        f['title'] = p['title']
                    if p['body'] is not None and p['bex']:
                        f['body'] = p['body']; f['body_exact'] = True
                    if p['labels']:
                        f['labels_added'] = p['labels']
                    if kind == 'pr':
                        f['draft'] = p['draft']
                        if p['base']:
                            f['base'] = p['base']
                        if p['head']:
                            f['head'] = p['head']
                    f['state'] = 'open'
                    f.pop('author')
                    sc.emit(t='issue', n=u[2], kind=kind, f=f, how='created', created=True)
                else:
                    f = {'state': 'open'}
                    for k in ('title', 'body'):
                        val, ex = p['fields'].get(k, (None, False))
                        if val is not None and ex:
                            f[k] = val
                    if 'body' in f:
                        f['body_exact'] = True
                    sc.emit(t='issue', n=u[2], kind=kind, f=f, how='created', created=True)
    # edits, state changes, labels, reviews: only when the call targets one literal number and did not fail
    if sc.rec['err']:
        return
    for p in posts:
        if p['n'] is None:
            continue
        if p['kind'] == 'gh':
            if p['what'] == 'edit':
                f = {}
                if p['title']:
                    f['title'] = p['title']
                if p['body'] is not None and p['bex']:
                    f['body'] = p['body']; f['body_exact'] = True
                if (f.get('body') or f.get('title')) and re.search(r'GraphQL: Projects \(classic\)', out or '') and p['noun'] == 'pr':
                    f = {}           # gh pr edit failed on this repo (projectCards error); nothing applied
                if f:
                    sc.emit(t='issue', n=p['n'], kind=p['noun'], f=f, how='edited')
                if p['labels'] or p['rm_labels']:
                    sc.emit(t='labels', n=p['n'], add=p['labels'], rm=p['rm_labels'], how='edited')
            elif p['what'] in ('close', 'reopen', 'merge'):
                if re.search(r'already (closed|merged|open)|could not|not found|GraphQL: ', out or '') and \
                        not re.search(r'✓ (Closed|Reopened|Merged|Squashed|Rebased)', out or ''):
                    continue
                st = {'close': 'closed', 'reopen': 'open', 'merge': 'merged'}[p['what']]
                sc.emit(t='issue', n=p['n'], kind=p['noun'], f={'state': st}, how=p['what'])
                tm = re.search(r'✓ (?:Closed|Reopened) (?:issue|pull request) (?:jreinach-alt/hakuX)?#%d \((.*)\)\s*$' % p['n'], out or '', re.M)
                if tm:
                    sc.emit(t='issue', n=p['n'], kind=p['noun'], f={'title': tm.group(1)}, how='state-msg')
                if p['body'] and p['bex'] and p['what'] != 'merge':
                    sc.emit(t='comment', n=p['n'], id=None, ctype='comment', author=None, created_at=None,
                            updated_at=None, body=p['body'], exact=True, how='posted-with-' + p['what'], posted=True)
            elif p['what'] == 'review':
                if p['body'] and p['bex'] and not re.search(r'(?i)error|failed|could not', out or ''):
                    sc.emit(t='comment', n=p['n'], id=None, ctype='review', review_state=p['review'], author=None,
                            created_at=None, updated_at=None, body=p['body'], exact=True, how='posted-review', posted=True)
            elif p['what'] == 'ready':
                if re.search(r'marked as "ready for review"', out or ''):
                    sc.emit(t='issue', n=p['n'], kind='pr', f={'draft': False}, how='ready')
        else:
            if p['what'] == 'edit':
                f = {}
                for k in ('title', 'body', 'state'):
                    val, ex = p['fields'].get(k, (None, False))
                    if val is not None and ex:
                        f[k] = val if k != 'state' else norm_state(val)
                if 'body' in f:
                    f['body_exact'] = True
                if f and not re.search(r'(?i)"message":|HTTP 4\d\d', out or ''):
                    sc.emit(t='issue', n=p['n'], kind=p['noun'], f=f, how='api-patch')
            elif p['what'] == 'labels':
                lb = p['fields'].get('labels') or []
                if lb and not re.search(r'HTTP 4\d\d', out or ''):
                    meth = 'DELETE' if re.search(r'(-X|--method)\s+DELETE', p['seg']) else 'POST'
                    if meth == 'POST':
                        sc.emit(t='labels', n=p['n'], add=lb, rm=[], how='api-labels')


SILENT = {'cd', 'export', 'sleep', 'mkdir', 'rm', 'set', 'true', ':', 'local', 'source', '.', 'for', 'do', 'done',
          'if', 'then', 'fi', 'else', 'elif', 'while', 'until', 'wait', 'unset', 'trap', 'cp', 'mv', 'touch', 'chmod',
          'S', 'T', 'umask', 'shopt', 'esac', 'case', '{', '}'}


def producers(cmd):
    """Simple commands in `cmd` that can write to stdout (rough)."""
    s = cmd
    for (a, b, line, content, q) in reversed(heredocs(cmd)):
        nl = s.find('\n', a)
        s = s[:nl] + '\n' + s[b:] if nl >= 0 else s
    n = 0
    for piece in re.split(r'\s*(?:;|&&|\|\||\n)\s*', s):
        piece = piece.strip()
        if not piece:
            continue
        piece = re.sub(r'^(?:(?:do|then|else|elif|\{|\()\s+)+', '', piece)
        w = re.sub(r'^(?:[A-Za-z_]\w*=\S*\s+)*', '', piece)
        first = w.split()[0] if w.split() else ''
        if re.fullmatch(r'[A-Za-z_]\w*=.*', piece) and ' ' not in piece:
            continue
        if first in SILENT or first.startswith('#'):
            continue
        if re.search(r'(?<![2&])>\s*\S+\s*(2>&1)?\s*$', piece) and '|' not in piece.split('>')[-1]:
            continue
        if first == 'git' and re.search(r'\s-q\b|--quiet', piece):
            continue
        n += 1
    return n


def loop_foreign(cmd, s):
    """Is the call at offset s inside a loop whose body also writes to stdout? (Then one iteration's last
    record may run into the next iteration's other output.)"""
    for m in reversed(list(re.finditer(r'\bdo\b', cmd[:s]))):
        depth = 0
        for mm in re.finditer(r'\b(do|done)\b', cmd[m.end():]):
            if mm.group(1) == 'do':
                depth += 1
            elif depth == 0:
                end = m.end() + mm.start()
                if end > s:
                    return producers(cmd[m.end():end]) > 1
                break
            else:
                depth -= 1
    return False


def after_pipe(cmd, e):
    """What the shell does to a gh call's stdout: (ok, head_lines)."""
    rest = cmd[e:]
    for (a, b, line, content, q) in reversed(heredocs(rest)):
        rest = rest[:a] + rest[b:]
    # the pipeline this call is in, plus the pipeline after the `done` of each loop around it
    pipes = [re.split(r';|&&|\|\||\n', rest)[0]]
    depth = len(re.findall(r'\bdo\b', cmd[:e])) - len(re.findall(r'\bdone\b', cmd[:e]))
    pos = 0
    while depth > 0:
        m = re.search(r'\b(do|done)\b', rest[pos:])
        if not m:
            break
        pos += m.end()
        if m.group(1) == 'do':
            depth += 1
            continue
        depth -= 1
        pipes.append(re.split(r';|&&|\|\||\n', rest[pos:])[0])
    head = None
    for m in re.finditer(r'(?<!\|)\|(?!\|)\s*([^|;&\n]*)', '\n'.join(pipes)):
        st = m.group(1).strip()
        if not st or st == 'cat':
            continue
        h = re.fullmatch(r'head\s+(?:-n\s*)?-?(\d+)(\s*2>&1)?', st)
        if h:
            head = int(h.group(1)) if head is None else min(head, int(h.group(1)))
            continue
        return False, None
    return True, head


def scan_templates(sc, cmd, out, cwd, ctx_hakux):
    import jqtmpl
    if 'deliver.sh inbox' in cmd and len(re.findall(r'deliver\.sh\s+inbox', cmd)) == 1 and '|' not in cmd.split('deliver.sh inbox')[1].split('\n')[0]:
        segs = [(0, len(cmd), 'deliver-inbox', '"\\n=== \\(.created_at)  \\(.html_url)\\n\\(.body)"', 'comments')]
    else:
        segs = []
        for (s, e, seg) in gh_segments(cmd):
            jq = jq_of(seg)
            if not jq:
                continue
            m = re.search(r'gh\s+(issue|pr)\s+view\s+(\d+|\$\w+)', seg)
            a = re.search(r'repos/[^/\s"\']+/[^/\s"\']+/(issues|pulls)/(\d+|\$\{?\w+\}?)/(comments|reviews)\b', seg) or \
                re.search(r'repos/[^/\s"\']+/[^/\s"\']+/(issues)/(comments)\b', seg)
            lst = re.match(r'gh\s+(issue|pr|search)\s+(list|issues|prs)\b', seg) or \
                re.search(r'repos/[^/\s"\']+/[^/\s"\']+/(issues|pulls)(?:\?|["\'\s]|$)', seg)
            iv = re.match(r'gh\s+(issue|pr)\s+view\s+(\d+)\b', seg) or \
                re.search(r'repos/[^/\s"\']+/[^/\s"\']+/(issues|pulls)/(\d+)(?=["\'\s]|$)', seg)
            if iv and not re.search(r'\.(comments|reviews)\b', jq) and '\\(' in jq or iv and '+' in jq and not re.search(r'\.(comments|reviews)\b', jq):
                segs.append((s, e, seg, jq, 'issue', int(iv.group(2)), 'pr' if iv.group(1) in ('pr', 'pulls') else 'issue'))
                continue
            if m and re.search(r'\.(comments|reviews)\b', jq):
                kind = 'reviews' if re.search(r'^\s*\.reviews', jq) else 'comments'
                segs.append((s, e, seg, jq, kind, int(m.group(2)) if m.group(2).isdigit() else None))
            elif a:
                if a.group(1) == 'issues' and a.group(2) == 'comments':
                    segs.append((s, e, seg, jq, 'comments', None))
                else:
                    nn = a.group(2)
                    kind = {'comments': 'comments' if a.group(1) == 'issues' else 'review_comments',
                            'reviews': 'reviews'}[a.group(3)]
                    segs.append((s, e, seg, jq, kind, int(nn) if nn.isdigit() else None))
            elif lst:
                segs.append((s, e, seg, jq, 'list', None))
        segs = [x if len(x) == 7 else x + (None,) for x in segs]
    if not segs:
        return
    nprod = producers(cmd)
    reads = [g for g in gh_segments(cmd) if re.match(r'gh\s+(issue|pr|search)\s+(view|list|issues|prs)|gh\s+api\b(?!.*(-X|--method)\s+(POST|PATCH|DELETE|PUT))', g[2])]
    for sg in segs:
        if re.search(r'(?<![0-9&])>\s*(?!&)', sg[2]) and sg[2] != 'deliver-inbox':
            continue                      # stdout went to a file
        if sg[2] == 'deliver-inbox':
            s, e, seg, jq, kind = sg
            nn, ok, head = None, True, None
        else:
            s, e, seg, jq, kind, nn, noun = sg
            ok, head = after_pipe(cmd, e)
        if not ok:
            continue
        loop = 'xargs' in cmd or (sg[2] != 'deliver-inbox' and loop_foreign(cmd, s))
        spec = jqtmpl.compile_jq(jq)
        if spec is None:
            continue
        if head is not None and out.count('\n') + 4 <= head:
            head = None
        sole = nprod <= 1 and len(segs) == 1
        if not sole and not spec['strong']:
            continue
        hdr = re.sub(r'\(\?P<\w+>', '(?:', spec['header'])
        same = [x for x in segs if x is not sg and (jqtmpl.compile_jq(x[3]) or {}).get('header') is not None
                and re.sub(r'\(\?P<\w+>', '(?:', jqtmpl.compile_jq(x[3])['header']) == hdr]
        mixed = bool(same) and any(x[3] != jq for x in same)
        if kind == 'list':
            if not ctx_hakux:
                continue
            for d in jqtmpl.read_records(spec, out, sole, head, loop):
                if 'number' in d and 'title' in d:
                    sc.emit(t='issue', n=int(d['number']), kind=None, f={'title': d['title']}, how='jq-list')
            continue
        if kind == 'issue':
            if not (ctx_hakux and spec['single']):
                continue
            for d in jqtmpl.read_records(spec, out, sole, head, loop):
                f = {}
                if d.get('title'):
                    f['title'] = d['title']
                if 'body' in d and d['body']:
                    f['body'] = d['body']; f['body_exact'] = bool(d.get('exact')) and not mixed
                    if not f['body_exact'] and not (sole and not mixed):
                        f.pop('body'); f.pop('body_exact')
                if f:
                    sc.emit(t='issue', n=nn, kind=noun, f=f, how='jq-issue')
                break
            continue
        if not spec['fields'].get('body'):
            continue
        if spec['single'] and spec['rx'] == '(?P<body>(?s:.*?))\\n' and not (kind != 'list' and nn is not None):
            continue
        for d in jqtmpl.read_records(spec, out, sole, head, loop):
            n2 = num(d.get('issue')) or nn
            cid = None
            if d.get('url'):
                um = URL.search(d['url'])
                if um:
                    n2 = int(um.group(2))
                    if um.group(3) == 'issuecomment':
                        cid = num(um.group(4))
            if d.get('id') and num(d['id']) and num(d['id']) >= MIN_CID and kind == 'comments':
                cid = num(d['id'])
            if n2 is None or not (ctx_hakux or d.get('url')):
                continue
            ctype = {'comments': 'comment', 'reviews': 'review', 'review_comments': 'review_comment'}[kind]
            sc.emit(t='comment', n=n2, id=cid if ctype == 'comment' else None, ctype=ctype, author=d.get('author'),
                    created_at=d.get('created'), updated_at=d.get('updated'), body=d['body'],
                    exact=bool(d.get('exact')) and d['body'] != '' and not mixed, how='jq', single=spec['single'],
                    clean=(sole or d.get('term') == 'next' and not loop) and not mixed)


def scan_reads(sc, cmd, out, cwd):
    if not out:
        return
    if re.search(r'fixture|selftest|\bstub\b|FAKE_GH|GH_STUB', cmd):
        return
    try:
        scan_templates(sc, cmd, out, cwd, is_hakux_ctx(cmd, cwd))
    except re.error:
        pass
    segs = [sg for sg in gh_segments(cmd) if not re.match(r'gh\s+label', sg[2])]
    views = set()
    kinds = set()
    for (_, _, seg) in segs:
        m = re.match(r'gh\s+(issue|pr)\s+view\s+(\d+)', seg)
        if m:
            views.add(int(m.group(2))); kinds.add(m.group(1))
        m = re.match(r'gh\s+api\s+(?:-\S+\s+(?:\S+\s+)?)*["\']?repos/[^/\s]+/[^/\s]+/(issues|pulls)/(\d+)["\']?(\s|$)', seg)
        if m:
            views.add(int(m.group(2))); kinds.add('pr' if m.group(1) == 'pulls' else 'issue')
        m = re.match(r'gh\s+(issue|pr)\s+list', seg)
        if m:
            kinds.add(m.group(1))
    jqs = [jq_of(sg[2]) for sg in segs if jq_of(sg[2])]
    jq = ' '.join(jqs) if jqs else None
    bound = body_bound(jq)
    # bodies piped through head/cut after the gh call are not complete; JSON that still parses is complete per object
    ctx = {'n': next(iter(views)) if len(views) == 1 else None,
           'kind': next(iter(kinds)) if len(kinds) == 1 else None,
           'hakux': is_hakux_ctx(cmd, cwd), 'jq': jq}
    for v in json_values(out):
        walk_json(sc, v, ctx, bound)
    # single-field raw reads: one gh call, --jq .body / .title, output unpiped
    if len(segs) == 1:
        s, e, seg = segs[0]
        rest = cmd[e:]
        pre = cmd[:s]
        jq1 = jq_of(seg)
        ap = after_pipe(cmd, e)
        if jq1 in ('.body', '.title') and ap[0] and (ap[1] is None or out.count('\n') + 4 <= ap[1]) and \
                producers(cmd) <= 1 and not re.search(r'(?<![0-9&])>\s*(?!&)', seg) and \
                not re.search(r'[;&|]', re.sub(r'^\s*(cd\s+\S+\s*(&&|;)\s*)*(timeout\s+\d+\s+)?', '', pre)):
            val = out.rstrip('\n')
            if val.startswith('Exit code') or 'HTTP 4' in val or sc.rec['err']:
                return
            m = re.search(r'repos/[^/\s]+/[^/\s]+/issues/comments/(\d+)', seg)
            fld = jq1[1:]
            if m and fld == 'body' and ctx['hakux']:
                sc.emit(t='comment', n=None, id=int(m.group(1)), ctype='comment', author=None, created_at=None,
                        updated_at=None, body=val, exact=True, how='raw-body')
            elif len(views) == 1 and ctx['hakux']:
                sc.emit(t='issue', n=ctx['n'], kind=ctx['kind'] if len(kinds) == 1 else None,
                        f={fld: val, **({'body_exact': True} if fld == 'body' else {})}, how='raw-' + fld)
    # gh issue list / pr list tab tables (no --json)
    for (_, _, seg) in segs:
        m = re.match(r'gh\s+(issue|pr)\s+list\b', seg)
        if m and '--json' not in seg and ctx['hakux']:
            for line in out.split('\n'):
                p = line.split('\t')
                if m.group(1) == 'issue' and len(p) == 5 and p[0].isdigit() and p[1] in ('OPEN', 'CLOSED'):
                    sc.emit(t='issue', n=int(p[0]), kind='issue', f={'title': p[2], 'state': p[1].lower(),
                            'labels': [x for x in p[3].split(', ') if x]}, how='list-text')
                elif m.group(1) == 'pr' and len(p) == 5 and p[0].isdigit() and p[3] in ('OPEN', 'DRAFT', 'MERGED', 'CLOSED'):
                    st = {'DRAFT': 'open'}.get(p[3], p[3].lower())
                    f = {'title': p[1], 'state': st, 'head': p[2]}
                    if p[3] == 'DRAFT':
                        f['draft'] = True
                    sc.emit(t='issue', n=int(p[0]), kind='pr', f=f, how='list-text')


def scan_file(path):
    rel = path[len(ROOT) + 1:]
    fs = FileState(rel)
    pending = {}
    events = []
    seen = []
    try:
        fh = open(path, errors='replace')
    except Exception:
        return rel, events, seen
    for line in fh:
        if 'jreinach-alt/hakuX' in line:
            for m in CMT_URL.finditer(line):
                seen.append((int(m.group(1)), int(m.group(2))))
            for m in re.finditer(r'github\.com/jreinach-alt/hakuX/(issues|pull)/(\d+)', line):
                seen.append((int(m.group(2)), None, m.group(1)))
        if '"tool_use"' not in line and '"tool_result"' not in line:
            continue
        try:
            d = json.loads(line)
        except Exception:
            continue
        msg = d.get('message') or {}
        c = msg.get('content')
        if not isinstance(c, list):
            continue
        for x in c:
            if not isinstance(x, dict):
                continue
            if x.get('type') == 'tool_use':
                inp = x.get('input') or {}
                if x.get('name') == 'Write' and isinstance(inp.get('content'), str) and isinstance(inp.get('file_path'), str):
                    fs.writes[inp['file_path']] = inp['content']
                    continue
                if x.get('name') == 'Edit':
                    fp = inp.get('file_path')
                    cur = fs.writes.get(fp)
                    if isinstance(cur, str) and isinstance(inp.get('old_string'), str) and inp['old_string'] in cur:
                        fs.edits_pending[x.get('id')] = (fp, cur.replace(inp['old_string'], inp.get('new_string', ''),
                                                                         -1 if inp.get('replace_all') else 1))
                    elif fp in fs.writes:
                        fs.writes[fp] = None
                    continue
                cmd = inp.get('command')
                if not isinstance(cmd, str):
                    continue
                cwd = d.get('cwd') or ''
                # file writes by heredoc in any Bash command (body files are often written this way)
                if '<<' in cmd or '>' in cmd:
                    fs.writes.update(inline_writes(cmd, assignments(cmd), cwd, fs, d.get('timestamp')))
                stale = []
                if re.search(r'>>|sed\s+-i|perl\s+-[a-z]*i|python|tee\b|\bmv\b|\bcp\b|(?<![0-9&])>\s*(?!&|/dev/null)\S', cmd):
                    mine = inline_writes(cmd, assignments(cmd), cwd, fs, d.get('timestamp'))
                    stale = [wp for wp in fs.writes if wp not in mine and os.path.basename(wp) in cmd]
                if GH_ANY.search(cmd):
                    pending[x.get('id')] = {'cmd': cmd, 'cwd': cwd, 'ts': d.get('timestamp'), 'stale': stale}
                else:
                    for wp in stale:
                        fs.writes[wp] = None
            elif x.get('type') == 'tool_result':
                rid = x.get('tool_use_id')
                if rid in fs.edits_pending:
                    fp, new = fs.edits_pending.pop(rid)
                    fs.writes[fp] = None if x.get('is_error') else new
                    continue
                if rid not in pending:
                    continue
                p = pending.pop(rid)
                cnt = x.get('content')
                out = cnt if isinstance(cnt, str) else '\n'.join(
                    y.get('text', '') for y in cnt if isinstance(y, dict) and y.get('type') == 'text') if isinstance(cnt, list) else ''
                tur = d.get('toolUseResult')
                if isinstance(tur, dict) and isinstance(tur.get('stdout'), str) and len(tur['stdout']) >= len(out or ''):
                    out = tur['stdout'] + (('\n' + tur['stderr']) if tur.get('stderr') else '')
                sc = Scan(fs, {'ts': p['ts'], 'src': rel, 'err': bool(x.get('is_error'))})
                try:
                    if GH_CALL.search(p['cmd']) or 'deliver.sh' in p['cmd']:
                        scan_posts(sc, p['cmd'], out or '', p['cwd'])
                    scan_reads(sc, p['cmd'], out or '', p['cwd'])
                except RecursionError:
                    pass
                events.extend(sc.ev)
                for wp in p['stale']:
                    fs.writes[wp] = None
    return rel, events, seen


def cmd_scan(scratch):
    files = sorted(glob.glob(ROOT + '/**/*.jsonl', recursive=True), key=os.path.getsize, reverse=True)
    n = 0
    seen_c, seen_n = set(), collections.Counter()
    with open(os.path.join(scratch, 'events.jsonl'), 'w') as o, Pool(8) as pool:
        for rel, evs, seen in pool.imap_unordered(scan_file, files, chunksize=1):
            for e in evs:
                o.write(json.dumps(e) + '\n'); n += 1
            for s in seen:
                if len(s) == 2:
                    seen_c.add(s)
                else:
                    seen_n[(s[0], s[2])] += 1
    json.dump({'comment_ids': sorted(seen_c), 'numbers': [[k[0], k[1], v] for k, v in seen_n.items()]},
              open(os.path.join(scratch, 'seen.json'), 'w'))
    print('events', n, 'files', len(files), 'comment ids seen', len(seen_c))


if __name__ == '__main__':
    args = sys.argv[1:]
    scratch = os.path.join(os.getcwd(), 'scratch')
    if '--scratch' in args:
        scratch = args[args.index('--scratch') + 1]
    os.makedirs(scratch, exist_ok=True)
    if args and args[0] == 'scan':
        cmd_scan(scratch)
    elif args and args[0] in ('build', 'finalize'):
        import recon_build
        recon_build.build(scratch, args)
        if args[0] == 'finalize':
            import shutil
            out = args[args.index('--out') + 1] if '--out' in args else os.path.join(HOME, 'hakux-work/forge-import')
            here = os.path.dirname(os.path.abspath(__file__))
            shutil.copy(os.path.join(here, 'secretscan-allow.json'), os.path.join(out, 'secretscan-allow.json'))
            r = subprocess.run([sys.executable, os.path.join(here, 'secretscan.py'), out, '--redact'],
                               capture_output=True, text=True)
            look = [l for l in r.stdout.splitlines() if ' look ' in l[:30]]
            print(r.stdout.splitlines()[-1] if r.stdout else r.stderr[-500:])
            if look:
                print('UNREVIEWED secret-scan hits (judge them, then add their keys to secretscan-allow.json):')
                print('\n'.join(look))
                sys.exit(1)
            recon_build.write_readme(out)
    else:
        print(__doc__)
