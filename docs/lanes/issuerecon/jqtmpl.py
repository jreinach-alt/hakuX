"""jqtmpl.py: read back records from gh output formatted by a jq program.

Agents mostly read comments through `--jq '.comments[] | "\\(.createdAt) \\(.author.login)\\n\\(.body)"'` and
the like. For a jq program whose last stage is a string template or a `+` concatenation of simple paths,
compile_jq() returns a regex that matches one output record, with named groups for the fields it can name
(body, created, author, url, id, issue, number, title, state). Anything else returns None: no guessing.
"""
import re

TS = r'\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ'


def skip_string(s, i):
    i += 1
    while i < len(s):
        c = s[i]
        if c == '\\':
            if s[i + 1:i + 2] == '(':
                i = skip_parens(s, i + 1)
                continue
            i += 2
            continue
        if c == '"':
            return i + 1
        i += 1
    return i


def skip_parens(s, i):
    depth = 0
    while i < len(s):
        c = s[i]
        if c == '"':
            i = skip_string(s, i)
            continue
        if c in '([{':
            depth += 1
        elif c in ')]}':
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    return i


def split_top(s, sep):
    parts, depth, start, i = [], 0, 0, 0
    while i < len(s):
        c = s[i]
        if c == '"':
            i = skip_string(s, i)
            continue
        if c in '([{':
            depth += 1
        elif c in ')]}':
            depth -= 1
        elif depth == 0 and s.startswith(sep, i) and not (sep == '|' and s[i + 1:i + 2] == '=') \
                and not (sep == '+' and s[i + 1:i + 2] == '='):
            parts.append(s[start:i])
            start = i + len(sep)
            i += len(sep)
            continue
        i += 1
    parts.append(s[start:])
    return [p.strip() for p in parts]


def unparen(e):
    e = e.strip()
    while e.startswith('(') and skip_parens(e, 0) == len(e):
        e = e[1:-1].strip()
    return e


ESC = {'n': '\n', 't': '\t', 'r': '\r', '"': '"', '\\': '\\', '/': '/'}


def string_parts(lit):
    """jq string literal -> [('lit', text) | ('expr', e)]."""
    out, buf, i = [], [], 1
    while i < len(lit) - 1:
        c = lit[i]
        if c == '\\':
            n = lit[i + 1]
            if n == '(':
                j = skip_parens(lit, i + 1)
                if buf:
                    out.append(('lit', ''.join(buf))); buf = []
                out.append(('expr', lit[i + 2:j - 1]))
                i = j
                continue
            if n == 'u':
                buf.append(chr(int(lit[i + 2:i + 6], 16))); i += 6; continue
            buf.append(ESC.get(n, n)); i += 2
            continue
        buf.append(c); i += 1
    if buf:
        out.append(('lit', ''.join(buf)))
    return out


def classify(e):
    """Field kind of a jq path expression relative to one record."""
    e = unparen(e)
    ns = re.sub(r'\s+', '', e)
    if ns == '.body':
        return ('body', None)
    m = re.fullmatch(r'\.body(?:\|\.)?\[(\d*):(\d+)\]', ns)
    if m:
        return ('body', int(m.group(2))) if m.group(1) in ('', '0') else ('text',)
    if ns in ('.created_at', '.createdAt', '.submitted_at', '.submittedAt'):
        return ('created',)
    if ns in ('.updated_at', '.updatedAt'):
        return ('updated',)
    if ns in ('.user.login', '.author.login', '.author'):
        return ('author',)
    if ns in ('.html_url', '.url'):
        return ('url',)
    if ns in ('.id', '(.id|tostring)', '.id|tostring'):
        return ('id',)
    if ns in ('.issue_url|split("/")|last', '.issue_url|split("/")[-1]', '.issue_url|split("/")|.[-1]'):
        return ('issue',)
    if ns == '.number':
        return ('number',)
    if ns == '.title':
        return ('title',)
    if ns == '.state':
        return ('state',)
    return ('text',)


GEN = re.compile(r'^\.(?:comments|reviews)?(?:\[-?\d*:?-?\d*\])*(?:\[\])?$')
FILTER = re.compile(r'^(select\(.*\)|reverse|sort_by\(.*\)|unique_by\(.*\)|\.\[\])$', re.S)


def compile_jq(jq):
    """-> (record_regex, fields, header_regex, single) or None."""
    if not jq or ',' in ''.join(split_top(jq, ',')[1:2]):
        return None
    if len(split_top(jq, ',')) > 1:
        return None
    stages = split_top(jq, '|')
    # leading generator stages and filters
    gen = []
    while stages and (GEN.match(re.sub(r'\s+', '', stages[0])) or FILTER.match(stages[0])) and len(stages) > 1:
        gen.append(stages.pop(0))
    if len(stages) != 1:
        # a final '.x | .y' path chain such as '.comments[-1] | .body' was split above; or something unsupported
        return None
    last = stages[0]
    # '.comments[-1].body' style: a generator prefix glued to the path
    m = re.match(r'^(\.(?:comments|reviews)?(?:\[-?\d*:?-?\d*\])+)(\..+)$', re.sub(r'\s+', '', last))
    if m and not last.startswith('"'):
        gen.append(m.group(1))
        last = m.group(2)
    gtext = ''.join(re.sub(r'\s+', '', g) for g in gen)
    single = bool(re.search(r'\[-?\d+\]$', gtext)) and '[]' not in gtext or not gen
    items = split_top(last, '+')
    parts = []
    for it in items:
        it = it.strip()
        if it.startswith('"') and skip_string(it, 0) == len(it):
            for k, v in string_parts(it):
                if k == 'lit':
                    parts.append(('lit', v))
                else:
                    parts.append(('fld',) + classify(v))
        else:
            parts.append(('fld',) + classify(it))
    if sum(1 for p in parts if p[0] == 'fld' and p[1] == 'body') > 1:
        return None
    # shell-expanded $n inside the template is the issue number
    p2 = []
    for p in parts:
        if p[0] == 'lit' and re.search(r'\$\{?[A-Za-z_]\w*\}?', p[1]):
            bits = re.split(r'(\$\{?[A-Za-z_]\w*\}?)', p[1])
            for b in bits:
                if not b:
                    continue
                if b.startswith('$'):
                    v = b.strip('${}')
                    p2.append(('fld', 'issue') if v in ('n', 'N', 'i', 'num', 'issue', 'pr', 'p') else ('fld', 'text'))
                else:
                    p2.append(('lit', b))
        else:
            p2.append(p)
    parts = p2 + [('lit', '\n')]
    # regex: body is dotall non-greedy; text/title single-line
    rx, header, seen_body = [], None, False
    names = []
    for idx, p in enumerate(parts):
        if p[0] == 'lit':
            rx.append(re.escape(p[1]))
            continue
        k = p[1]
        nxt_lit = next((q for q in parts[idx + 1:] if True), None)
        if k == 'body':
            header = ''.join(rx)
            hparts = parts[:idx]
            rx.append('(?P<body>(?s:.*?))')
            seen_body = True
        elif k in ('created', 'updated'):
            rx.append('(?P<%s>%s)' % (k, TS) if k not in names else TS)
        elif k == 'author':
            rx.append('(?P<author>[A-Za-z0-9-]+(?:\\[bot\\])?)' if 'author' not in names else '[A-Za-z0-9-]+')
        elif k == 'url':
            rx.append('(?P<url>https://github\\.com/jreinach-alt/hakuX/(?:issues|pull)/\\d+(?:#issuecomment-\\d+)?)' if 'url' not in names else '\\S+')
        elif k == 'id':
            rx.append('(?P<id>\\d{9,12})' if 'id' not in names else '\\d+')
        elif k in ('issue', 'number'):
            rx.append('(?P<%s>\\d+)' % k if k not in names else '\\d+')
        elif k in ('title', 'state'):
            # only a field that runs to the end of its line can be read back exactly
            if nxt_lit and nxt_lit[0] == 'lit' and nxt_lit[1].startswith('\n') and k not in names:
                rx.append('(?P<%s>[^\\n]*)' % k)
            else:
                rx.append('[^\\n]*?')
                k = 'text'
        else:
            rx.append('(?:[^\\n]*?)' if not seen_body else '(?:.*?)')
        names.append(k)
    if 'body' not in names and not ({'number', 'title'} <= set(names)):
        return None
    fields = {n: True for n in names}
    bound = next((p[2] for p in parts if p[0] == 'fld' and p[1] == 'body'), None)
    if header is None:
        header = ''.join(rx)
        hparts = parts
    strong = any(p[0] == 'fld' and p[1] in ('url', 'id', 'author') for p in hparts) or \
        any(p[0] == 'lit' and len(re.sub(r'\s', '', p[1])) >= 3 for p in hparts)
    return {'rx': ''.join(rx), 'header': header, 'fields': fields, 'strong': strong, 'single': single, 'bound': bound,
            'body_last': parts[-2][0] == 'fld' and parts[-2][1] == 'body'}


def read_records(spec, out, sole, head_lines=None, loop=False):
    """Yield dicts of fields for each record of `out`. exact: whether the body is known complete."""
    if spec is None:
        return
    if spec['single'] and spec['fields'].get('body') and spec['rx'] == '(?P<body>(?s:.*?))\\n':
        if sole and out:
            yield {'body': out[:-1] if out.endswith('\n') else out, 'exact': head_lines is None, 'term': 'all'}
        return
    if spec['header'] == '':
        return                              # records with no header cannot be told apart
    plain = re.sub(r'\(\?P<\w+>', '(?:', spec['header'])
    rx = re.compile('(?m)^' + spec['rx'] + '(?=' + plain + '|\\Z)')
    if not spec['fields'].get('body'):
        rx = re.compile('(?m)^' + spec['rx'])
    pos = 0
    while True:
        m = rx.search(out, pos)
        if not m:
            return
        d = {k: v for k, v in m.groupdict().items() if v is not None}
        if 'body' in d:
            end = m.end()
            at_end = end >= len(out.rstrip('\n')) or out[end:].strip() == ''
            if at_end:
                d['exact'] = sole and head_lines is None
                d['term'] = 'end'
            else:
                d['exact'] = sole or not loop
                d['term'] = 'next'
            b = spec['bound']
            if b is not None and len(d['body']) >= b:
                d['exact'] = False
        yield d
        pos = max(m.end(), pos + 1)
