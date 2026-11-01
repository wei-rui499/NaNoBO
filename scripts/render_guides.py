"""Render the same Markdown guides shipped on GitHub into offline app help."""
from collections import Counter
from html import escape
from html.parser import HTMLParser
from pathlib import Path
import os
import re
import shutil
from urllib.parse import quote, unquote, urlsplit, urlunsplit

from markdown_it import MarkdownIt

ROOT = Path(__file__).resolve().parents[1]


def render_guides(root=ROOT):
    root = Path(root).resolve()
    output = root / "docs/html"
    output.mkdir(parents=True, exist_ok=True)
    sources = sorted(root.glob("*.md")) + sorted((root / "docs").glob("*.md"))
    destinations = {p.resolve(): output / ("README.zh-CN.html" if p.name == "README.md" else p.stem + ".html") for p in sources}
    required = [root / "docs/TUTORIAL.zh-CN.md", root / "docs/TUTORIAL.en.md"]
    if any(p not in destinations for p in required):
        raise RuntimeError("Both Chinese and English tutorials are required before packaging.")
    markdown = MarkdownIt("commonmark", {"html": False}).enable("table")

    class LocalLinks(HTMLParser):
        def __init__(self, source, destination):
            super().__init__(convert_charrefs=False)
            self.source, self.destination, self.parts = source, destination, []

        def url(self, value, image=False):
            parsed = urlsplit(value)
            if parsed.scheme or parsed.netloc or not parsed.path:
                return value
            target = (self.source.parent / unquote(parsed.path)).resolve()
            if not target.is_relative_to(root):
                raise ValueError("Guide link leaves the project: " + value)
            relative = target.relative_to(root)
            if target in destinations:
                final = destinations[target]
            elif image and target.is_file():
                final = output / "media" / relative
                final.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(target, final)
            elif relative.parts[0] in ("examples", "licenses") and target.exists():
                final = target
            else:
                return "https://github.com/wei-rui499/NaNoBO/blob/main/" + quote(relative.as_posix()) + ("#" + parsed.fragment if parsed.fragment else "")
            path = Path(os.path.relpath(final, self.destination.parent)).as_posix()
            return urlunsplit(("", "", quote(path, safe="/"), parsed.query, parsed.fragment))

        def handle_starttag(self, tag, attrs):
            rewritten = []
            for key, value in attrs:
                if value is not None and ((tag == "a" and key == "href") or (tag == "img" and key == "src")):
                    value = self.url(value, image=tag == "img")
                rewritten.append(key if value is None else f'{key}="{escape(value, quote=True)}"')
            self.parts.append("<" + tag + (" " + " ".join(rewritten) if rewritten else "") + ">")

        def handle_endtag(self, tag):
            self.parts.append("</" + tag + ">")

        def handle_data(self, text):
            self.parts.append(text)

        def handle_entityref(self, name):
            self.parts.append("&" + name + ";")

        def handle_charref(self, name):
            self.parts.append("&#" + name + ";")

    css = """*{box-sizing:border-box}body{margin:0;background:#f7faf8;color:#243d33;font:16px/1.8 -apple-system,BlinkMacSystemFont,'Segoe UI','PingFang SC',sans-serif}header{padding:20px 5%;background:#e8f2ec;border-bottom:1px solid #ccdcd1}header a{margin-right:24px}a{color:#176b50}a:hover{color:#104331}main{max-width:1280px;margin:28px auto;display:grid;grid-template-columns:250px minmax(0,1fr);gap:32px;padding:0 24px}nav{position:sticky;top:20px;max-height:90vh;overflow:auto;font-size:14px}nav a{display:block;text-decoration:none;padding:5px 10px;border-left:2px solid #d5e4db}nav .sub{padding-left:24px}article{min-width:0;background:white;border:1px solid #dce7df;border-radius:12px;padding:26px 36px}h1,h2,h3{line-height:1.35;scroll-margin-top:20px}h1{font-size:30px}h2{margin-top:2em;border-bottom:1px solid #dce7df;padding-bottom:10px}h3{margin-top:1.7em}table{border-collapse:collapse;display:block;overflow-x:auto;font-size:14px;width:100%;margin:18px 0}th,td{border:1px solid #d5e1d9;padding:9px 12px;text-align:left}th{background:#edf5ef}pre{overflow:auto;background:#f1f5f2;padding:14px;border-radius:6px}code{font-family:ui-monospace,Consolas,monospace;font-size:.91em}img{max-width:100%;height:auto}blockquote{margin-left:0;border-left:4px solid #6c9d83;padding:8px 18px;background:#f3f8f4}footer{margin-top:32px;color:#64786b;font-size:13px;border-top:1px solid #dce7df;padding-top:14px}@media(max-width:850px){main{display:block;padding:0 12px}nav{position:static;max-height:270px;margin-bottom:20px}article{padding:20px}header a{display:inline-block;margin-right:16px}}"""
    for source, destination in destinations.items():
        tokens = markdown.parse(source.read_text(encoding="utf-8"))
        headings, used = [], Counter()
        for i, token in enumerate(tokens):
            if token.type != "heading_open":
                continue
            text = tokens[i + 1].content
            slug = re.sub(r"[^\w\s-]", "", text.lower()).replace(" ", "-") or "section"
            used[slug] += 1
            anchor = slug if used[slug] == 1 else slug + "-" + str(used[slug] - 1)
            token.attrSet("id", anchor)
            headings.append((token.tag, text, anchor))
        body = markdown.renderer.render(tokens, markdown.options, {})
        links = LocalLinks(source, destination)
        links.feed(body)
        title = headings[0][1] if headings else source.stem
        toc = "".join(f'<a class="{"sub" if level == "h3" else ""}" href="#{escape(anchor)}">{escape(text)}</a>' for level, text, anchor in headings if level in ("h2", "h3"))
        language = "en" if source.name.endswith(".en.md") else "zh-CN"
        page = f'''<!doctype html><html lang="{language}"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{escape(title)} · NaNoBO</title><style>{css}</style><header><strong>NaNoBO</strong> &nbsp; <a href="TUTORIAL.zh-CN.html">简体中文</a><a href="TUTORIAL.en.html">English</a><a href="index.html">教程首页 / Help home</a></header><main><nav aria-label="Table of contents">{toc}</nav><article>{"".join(links.parts)}<footer>NaNoBO · 离线教程 / Offline guide · 教学实验数据均为模拟 / Teaching data are synthetic.</footer></article></main></html>'''
        destination.write_text(page, encoding="utf-8")
    (output / "index.html").write_text('''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>NaNoBO · 使用教程 / User guide</title><style>body{font:18px/1.8 system-ui;max-width:800px;margin:10vh auto;padding:24px;background:#f6faf7;color:#244335}a{display:block;background:white;border:1px solid #d4e3d8;border-radius:12px;padding:24px;margin:20px 0;color:#176b50;text-decoration:none}</style><h1>NaNoBO</h1><p>选择教程语言 / Choose your guide language</p><a href="TUTORIAL.zh-CN.html">简体中文 · 从练习数据开始</a><a href="TUTORIAL.en.html">English · Start with the practice data</a><p>App: 帮助 → 导出教程练习数据…<br>Export a writable copy of the practice files from the Help menu.</p></html>''', encoding="utf-8")
    print(f"Offline help: {len(destinations)} guides + language home")
    return output


if __name__ == "__main__":
    render_guides()
