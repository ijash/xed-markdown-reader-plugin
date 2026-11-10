from html import escape

from markdown import Markdown


_STYLESHEET = """
:root { color-scheme: light; }
* { box-sizing: border-box; }
body {
  margin: 0 auto;
  padding: 28px 36px 48px;
  max-width: 900px;
  color: #24292f;
  background: #ffffff;
  font: 15px/1.65 sans-serif;
  overflow-wrap: anywhere;
}
h1, h2, h3, h4, h5, h6 {
  color: #1f2328;
  line-height: 1.3;
  margin: 1.5em 0 0.6em;
}
h1 { font-size: 2em; border-bottom: 1px solid #d8dee4; padding-bottom: .3em; }
h2 { font-size: 1.55em; border-bottom: 1px solid #d8dee4; padding-bottom: .25em; }
h3 { font-size: 1.25em; }
p, ul, ol, blockquote, table, pre { margin: 0 0 1em; }
ul, ol { padding-left: 2em; }
li + li { margin-top: .2em; }
a { color: #0969da; text-decoration: none; }
a:hover { text-decoration: underline; }
blockquote {
  margin-left: 0;
  padding: .15em 1em;
  color: #59636e;
  border-left: 3px solid #d0d7de;
}
code, pre { font-family: monospace; }
code {
  padding: .15em .35em;
  border-radius: 4px;
  background: #eff1f3;
  font-size: .9em;
}
pre {
  overflow-x: auto;
  padding: 16px;
  border: 1px solid #d8dee4;
  border-radius: 7px;
  background: #f6f8fa;
  line-height: 1.5;
}
pre code { padding: 0; background: transparent; font-size: .92em; }
table { border-collapse: collapse; width: 100%; display: block; overflow-x: auto; }
th, td { padding: 7px 12px; border: 1px solid #d0d7de; text-align: left; }
th { background: #f6f8fa; font-weight: 600; }
tr:nth-child(even) { background: #f6f8fa; }
img { max-width: 100%; height: auto; border-radius: 4px; }
hr { height: 1px; border: 0; background: #d8dee4; margin: 1.5em 0; }
body.dark {
  color: #e6edf3;
  background: #242629;
}
.dark h1, .dark h2, .dark h3, .dark h4, .dark h5, .dark h6 { color: #f0f3f6; }
.dark h1, .dark h2 { border-color: #44484e; }
.dark a { color: #78aeff; }
.dark blockquote { color: #a3acb5; border-color: #59636e; }
.dark code { background: #35383d; }
.dark pre { background: #1c1e21; border-color: #44484e; }
.dark th, .dark td { border-color: #44484e; }
.dark th, .dark tr:nth-child(even) { background: #2d3035; }
.dark hr { background: #44484e; }
"""

_MARKDOWN = Markdown(extensions=("fenced_code", "sane_lists", "tables"))


def render_markdown(source, dark=False):
    body = _MARKDOWN.convert(escape(source, quote=False))
    theme_class = ' class="dark"' if dark else ""
    return (
        "<!doctype html><html><head><meta charset=\"utf-8\">"
        '<meta http-equiv="Content-Security-Policy" '
        'content="default-src \'none\'; img-src data: file:; '
        "style-src 'unsafe-inline'; font-src 'none'; "
        'connect-src \'none\'>'
        '<meta name="referrer" content="no-referrer">'
        f"<style>{_STYLESHEET}</style></head>"
        f"<body{theme_class}>{body}</body></html>"
    )
