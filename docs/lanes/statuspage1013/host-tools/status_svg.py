#!/usr/bin/env python3
"""Wrap the rendered dashboard (status/index.html) in an SVG that browsers display as a page.

A git host that serves a committed .svg as image/svg+xml opens it rendered with no
Pages build. Body and CSS are carried over unchanged; the page's scripts (age ticker, sort control)
cannot run under that host's sandbox. The svg fills the window and the page scrolls inside it, so no height is guessed.
Usage: status_svg.py in.html out.svg
"""
import re, sys
from html.parser import HTMLParser
from xml.sax.saxutils import escape, quoteattr

VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}
CASE = {"viewbox": "viewBox", "preserveaspectratio": "preserveAspectRatio"}


class P(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out, self.css, self.skip, self.in_style, self.in_body, self.svg = [], [], 0, False, False, 0

    def handle_starttag(self, tag, attrs):
        if tag == "style":
            self.in_style = True
            return
        if tag in ("script", "title"):
            self.skip += 1
            return
        if tag == "body":
            self.in_body = True
            return
        if not self.in_body or self.skip:
            return
        if tag == "svg":
            self.svg += 1
            if self.svg == 1 and not any(k == "xmlns" for k, _ in attrs):
                attrs = [("xmlns", "http://www.w3.org/2000/svg")] + list(attrs)
        a = "".join(" %s=%s" % (CASE.get(k, k) if self.svg else k, quoteattr(v if v is not None else k)) for k, v in attrs)
        self.out.append("<%s%s%s>" % (tag, a, "/" if tag in VOID else ""))

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in VOID and tag not in ("style", "script", "title"):
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        if tag == "style":
            self.in_style = False
        elif tag in ("script", "title"):
            self.skip -= 1
        elif tag == "body":
            self.in_body = False
        elif self.in_body and not self.skip and tag not in VOID:
            if tag == "svg":
                self.svg -= 1
            self.out.append("</%s>" % tag)

    def handle_data(self, d):
        if self.in_style:
            self.css.append(d)
        elif self.in_body and not self.skip:
            self.out.append(escape(d))


def build(html):
    p = P()
    p.feed(html)
    css = re.sub(r"(^|[,}\s])body(?=[\s,{.:#\[])", r"\1.hx-root", "".join(p.css)).replace("]]>", "]]]]><![CDATA[>")
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<svg xmlns="http://www.w3.org/2000/svg" width="100%%" height="100%%">\n'
            '<foreignObject x="0" y="0" width="100%%" height="100%%">\n'
            '<div xmlns="http://www.w3.org/1999/xhtml" class="hx-root" style="width:100%%;height:100%%;overflow:auto;box-sizing:border-box"><style><![CDATA[%s\n'
            '.hx-root{background:var(--bg);color:var(--fg)}]]></style>\n%s\n</div>\n'
            '</foreignObject></svg>\n') % (css, "".join(p.out))


if __name__ == "__main__":
    open(sys.argv[2], "w", encoding="utf-8").write(build(open(sys.argv[1], encoding="utf-8").read()))
