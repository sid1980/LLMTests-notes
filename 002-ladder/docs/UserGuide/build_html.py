#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Конвертация user_guide.md → user_guide.html (самодостаточный HTML).

Генерирует HTML с:
  - боковым оглавлением (переходы по главам/разделам);
  - поиском по тексту (фильтрация + подсветка);
  - кнопками «предыдущая/следующая глава».
Только стандартная библиотека Python.
"""
import html
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "user_guide.md"
OUT = HERE / "user_guide.html"


def esc(s: str) -> str:
    return html.escape(s, quote=False)


def inline(s: str) -> str:
    """Внутристрочное форматирование: ссылки, `code`, **bold**."""
    s = esc(s)
    s = re.sub(r'\[([^\]]+)\]\(([^)\s]+)\)', r'<a href="\2">\1</a>', s)
    s = re.sub(r'`([^`]+)`', r'<code>\1</code>', s)
    s = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', s)
    return s


def _is_block_start(line: str) -> bool:
    s = line.strip()
    return (s.startswith('```') or re.match(r'^#{1,6}\s', s)
            or re.match(r'^\s*[-*+]\s+', s) or re.match(r'^\s*\d+\.\s+', s)
            or s.startswith('>') or re.match(r'^\s*(-{3,}|\*{3,})\s*$', s))


def _is_table_sep(line: str) -> bool:
    return bool(re.match(r'^\s*\|?[\s:|-]+\|?\s*$', line)) and '-' in line


def _split_cells(line: str) -> list:
    line = line.strip()
    if line.startswith('|'):
        line = line[1:]
    if line.endswith('|'):
        line = line[:-1]
    return [c.strip() for c in line.split('|')]


def parse(md: str) -> list:
    """Разбор markdown → список блоков (для используемого подмножества)."""
    lines = md.split('\n')
    blocks = []
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        s = line.strip()
        if s.startswith('```'):
            lang = s[3:].strip()
            code = []
            i += 1
            while i < n and not lines[i].strip().startswith('```'):
                code.append(lines[i])
                i += 1
            i += 1  # закрывающий ```
            blocks.append(('code', lang, '\n'.join(code)))
            continue
        m = re.match(r'^(#{1,6})\s+(.*)$', s)
        if m:
            blocks.append(('heading', len(m.group(1)), m.group(2).strip()))
            i += 1
            continue
        if re.match(r'^\s*(-{3,}|\*{3,})\s*$', s):
            blocks.append(('hr',))
            i += 1
            continue
        if s.startswith('>'):
            q = []
            while i < n and lines[i].strip().startswith('>'):
                q.append(lines[i].strip()[1:].strip())
                i += 1
            blocks.append(('quote', ' '.join(q)))
            continue
        if '|' in line and i + 1 < n and _is_table_sep(lines[i + 1]):
            header = _split_cells(line)
            i += 2
            rows = []
            while i < n and lines[i].strip() and '|' in lines[i]:
                rows.append(_split_cells(lines[i]))
                i += 1
            blocks.append(('table', header, rows))
            continue
        if re.match(r'^\s*[-*+]\s+', s) or re.match(r'^\s*\d+\.\s+', s):
            items = []
            while i < n and lines[i].strip():
                li = lines[i]
                if re.match(r'^\s*[-*+]\s+', li):
                    items.append(('ul', re.sub(r'^\s*[-*+]\s+', '', li).strip()))
                elif re.match(r'^\s*\d+\.\s+', li):
                    items.append(('ol', re.sub(r'^\s*\d+\.\s+', '', li).strip()))
                else:
                    items.append(('cont', li.strip()))
                i += 1
            blocks.append(('list', items))
            continue
        if not s:
            i += 1
            continue
        para = [line.strip()]
        i += 1
        while i < n and lines[i].strip() and not _is_block_start(lines[i]):
            para.append(lines[i].strip())
            i += 1
        blocks.append(('para', ' '.join(para)))
    return blocks


def render_blocks(blocks: list) -> str:
    out = []
    for b in blocks:
        kind = b[0]
        if kind == 'heading':
            _, level, text = b
            tag = f'h{min(level, 6)}'
            out.append(f'<{tag}>{inline(text)}</{tag}>')
        elif kind == 'code':
            _, lang, code = b
            cls = f' class="lang-{esc(lang)}"' if lang else ''
            out.append(f'<pre><code{cls}>{esc(code)}</code></pre>')
        elif kind == 'hr':
            out.append('<hr>')
        elif kind == 'quote':
            out.append(f'<blockquote>{inline(b[1])}</blockquote>')
        elif kind == 'para':
            out.append(f'<p>{inline(b[1])}</p>')
        elif kind == 'table':
            _, header, rows = b
            th = ''.join(f'<th>{inline(h)}</th>' for h in header)
            trs = ''.join(
                '<tr>' + ''.join(f'<td>{inline(c)}</td>' for c in r) + '</tr>'
                for r in rows)
            out.append(f'<div class="tablewrap"><table><thead><tr>{th}</tr></thead>'
                       f'<tbody>{trs}</tbody></table></div>')
        elif kind == 'list':
            raw = b[1]
            items = []
            for tag, text in raw:
                if tag == 'cont' and items:
                    pt, ptxt = items[-1]
                    items[-1] = (pt, ptxt + ' ' + text)
                else:
                    items.append((tag, text))
            buf = []
            cur = None
            for tag, text in items:
                if tag != cur:
                    if cur:
                        buf.append(f'</{cur}>')
                    buf.append(f'<{tag}>')
                    cur = tag
                buf.append(f'<li>{inline(text)}</li>')
            if cur:
                buf.append(f'</{cur}>')
            out.append(''.join(buf))
    return '\n'.join(out)


def group_chapters(blocks: list):
    """Разбить блоки на: преамбула + главы (по H2), с под-разделами H3."""
    title_blocks = []
    chapters = []
    cur = None
    for b in blocks:
        if b[0] == 'heading' and b[1] == 1:
            title_blocks.append(b)
            continue
        if b[0] == 'heading' and b[1] == 2:
            cur = {'title': b[2], 'blocks': []}
            chapters.append(cur)
            continue
        if cur is None:
            title_blocks.append(b)
        else:
            cur['blocks'].append(b)
    return title_blocks, chapters


def build() -> str:
    md = SRC.read_text(encoding="utf-8")
    blocks = parse(md)
    title_blocks, chapters = group_chapters(blocks)

    title_html = render_blocks(title_blocks)

    toc_items = []
    sections = []
    for ci, ch in enumerate(chapters, start=1):
        cid = f'ch-{ci}'
        subs = []
        body_blocks = []
        # разметить H3 внутри главы
        for b in ch['blocks']:
            if b[0] == 'heading' and b[1] == 3:
                subs.append(b[2])
                body_blocks.append(b)
            else:
                body_blocks.append(b)
        sub_links = []
        for si, st in enumerate(subs, start=1):
            sid = f'ch-{ci}-{si}'
            sub_links.append((sid, st))
            # заменить H3 на якорный заголовок
        # собрать тело с якорями на H3
        body = []
        si = 0
        for b in body_blocks:
            if b[0] == 'heading' and b[1] == 3:
                si += 1
                sid = f'ch-{ci}-{si}'
                body.append(f'<h3 id="{sid}">{inline(b[2])}</h3>')
            else:
                body.append(_render_one(b))
        content = f'<section id="{cid}" data-title="{esc(ch["title"])}">' \
                  f'<h2 id="{cid}-h">{inline(ch["title"])}</h2>' + '\n'.join(body) + \
                  f'<div class="chapnav">' \
                  f'<a class="navlink" data-nav="prev"></a>' \
                  f'<a class="navlink" data-nav="next"></a></div></section>'
        sections.append(content)
        sub_html = ''.join(
            f'<a class="toc-sub" href="#{sid}">{inline(st)}</a>'
            for sid, st in sub_links)
        toc_items.append(
            f'<a class="toc-ch" href="#{cid}">{inline(ch["title"])}</a>{sub_html}')

    toc_html = '\n'.join(toc_items)
    body_html = title_html + '\n' + '\n'.join(sections)

    return TEMPLATE.format(
        title=esc("cbench — руководство пользователя"),
        toc=toc_html,
        body=body_html,
    )


def _render_one(b) -> str:
    return render_blocks([b])


TEMPLATE = """<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
:root {{
  --bg:#0f1216; --panel:#171c22; --panel2:#1d242c; --border:#2a3340;
  --text:#d7dee8; --muted:#8b98a8; --accent:#4da3ff; --mark:#ffd54f;
}}
* {{ box-sizing:border-box; }}
html {{ scroll-behavior:smooth; }}
body {{ margin:0; font:15px/1.65 "Segoe UI",system-ui,Arial,sans-serif;
  background:var(--bg); color:var(--text); }}
a {{ color:var(--accent); text-decoration:none; }}
a:hover {{ text-decoration:underline; }}
.layout {{ display:flex; min-height:100vh; }}
.sidebar {{ width:320px; min-width:260px; background:var(--panel);
  border-right:1px solid var(--border); position:sticky; top:0; height:100vh;
  overflow-y:auto; padding:16px; }}
.sidebar h1 {{ font-size:15px; margin:0 0 12px; color:#fff; }}
#search {{ width:100%; padding:8px 10px; border-radius:6px; border:1px solid var(--border);
  background:var(--panel2); color:var(--text); font-size:14px; margin-bottom:4px; }}
#search:focus {{ outline:none; border-color:var(--accent); }}
#stats {{ font-size:12px; color:var(--muted); margin:4px 2px 12px; min-height:14px; }}
.toc-ch {{ display:block; padding:6px 8px; border-radius:5px; color:var(--text);
  font-weight:600; font-size:13.5px; margin-top:4px; }}
.toc-ch:hover {{ background:var(--panel2); text-decoration:none; }}
.toc-sub {{ display:block; padding:3px 8px 3px 22px; border-radius:5px;
  color:var(--muted); font-size:12.5px; }}
.toc-sub:hover {{ background:var(--panel2); color:var(--text); text-decoration:none; }}
.content {{ flex:1; max-width:900px; padding:28px 40px 80px; }}
.topbar {{ position:sticky; top:0; background:linear-gradient(var(--bg) 70%,transparent);
  padding:8px 0; display:flex; gap:10px; align-items:center; }}
.topbar button {{ background:var(--panel2); border:1px solid var(--border); color:var(--text);
  padding:7px 14px; border-radius:6px; cursor:pointer; font-size:13px; }}
.topbar button:hover {{ border-color:var(--accent); }}
h1 {{ font-size:26px; color:#fff; }}
h2 {{ font-size:20px; margin-top:44px; padding-top:14px; border-top:1px solid var(--border);
  color:#fff; }}
h3 {{ font-size:16.5px; margin-top:26px; color:#cfe3ff; }}
p {{ margin:12px 0; }}
code {{ background:var(--panel2); padding:1px 6px; border-radius:4px;
  font-family:Consolas,"Cascadia Code",monospace; font-size:13px; }}
pre {{ background:#0b0e12; border:1px solid var(--border); border-radius:8px;
  padding:14px 16px; overflow-x:auto; }}
pre code {{ background:none; padding:0; font-size:13px; }}
blockquote {{ border-left:3px solid var(--accent); margin:14px 0; padding:6px 16px;
  background:var(--panel); border-radius:0 6px 6px 0; color:var(--muted); }}
.tablewrap {{ overflow-x:auto; margin:14px 0; }}
table {{ border-collapse:collapse; width:100%; font-size:13.5px; }}
th,td {{ border:1px solid var(--border); padding:7px 12px; text-align:left; }}
th {{ background:var(--panel2); color:#fff; }}
td code, th code {{ font-size:12.5px; }}
hr {{ border:none; border-top:1px solid var(--border); margin:28px 0; }}
mark {{ background:var(--mark); color:#222; border-radius:2px; padding:0 1px; }}
.chapnav {{ display:flex; gap:10px; margin-top:26px; }}
.navlink {{ background:var(--panel2); border:1px solid var(--border); color:var(--text);
  padding:7px 16px; border-radius:6px; font-size:13px; cursor:pointer; }}
.navlink:hover {{ border-color:var(--accent); text-decoration:none; }}
.navlink.empty {{ opacity:.4; pointer-events:none; }}
section.hidden {{ display:none; }}
@media (max-width:820px) {{
  .layout {{ flex-direction:column; }}
  .sidebar {{ width:100%; height:auto; position:relative; border-right:none;
    border-bottom:1px solid var(--border); }}
  .content {{ padding:18px 20px 60px; }}
}}
</style>
</head>
<body>
<div class="layout">
  <aside class="sidebar">
    <h1>📘 cbench · User Guide</h1>
    <input id="search" type="text" placeholder="Поиск по руководству…" autocomplete="off">
    <div id="stats"></div>
    <nav id="toc">
{toc}
    </nav>
  </aside>
  <main class="content">
    <div class="topbar">
      <button id="btn-prev">← Предыдущая глава</button>
      <button id="btn-next">Следующая глава →</button>
      <button id="btn-clear" style="display:none">Сбросить поиск</button>
    </div>
{body}
  </main>
</div>
<script>
(function(){{
  const sections = Array.from(document.querySelectorAll('section[id^="ch-"]'));
  const tocChapters = Array.from(document.querySelectorAll('.toc-ch'));
  const search = document.getElementById('search');
  const stats = document.getElementById('stats');
  const btnClear = document.getElementById('btn-clear');

  function currentChapterIndex(){{
    for (let i=sections.length-1;i>=0;i--){{
      const r = sections[i].getBoundingClientRect();
      if (r.top <= 140) return i;
    }}
    return 0;
  }}
  function updateNav(){{
    const i = currentChapterIndex();
    const prev = sections[i-1], next = sections[i+1];
    const bp = document.getElementById('btn-prev'), bn = document.getElementById('btn-next');
    if (prev) {{ bp.textContent = '← ' + prev.dataset.title; bp.disabled = false; }}
    else {{ bp.textContent = '← Предыдущая глава'; bp.disabled = true; }}
    if (next) {{ bn.textContent = 'Следующая глава → ' + next.dataset.title; bn.disabled = false; }}
    else {{ bn.textContent = 'Следующая глава →'; bn.disabled = true; }}
  }}
  document.getElementById('btn-prev').addEventListener('click', ()=>{{
    const i = currentChapterIndex();
    if (i>0) sections[i-1].scrollIntoView({{behavior:'smooth'}});
  }});
  document.getElementById('btn-next').addEventListener('click', ()=>{{
    const i = currentChapterIndex();
    if (i<sections.length-1) sections[i+1].scrollIntoView({{behavior:'smooth'}});
  }});
  window.addEventListener('scroll', updateNav, {{passive:true}});

  function clearMarks(root){{
    root.querySelectorAll('mark').forEach(m=>{{
      const p=m.parentNode;
      p.replaceChild(document.createTextNode(m.textContent), m);
      p.normalize();
    }});
  }}
  function highlight(root, q){{
    if(!q) return;
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    const nodes = [];
    while (walker.nextNode()) nodes.push(walker.currentNode);
    const ql = q.toLowerCase();
    for (const n of nodes){{
      const t = n.nodeValue;
      if(!t) continue;
      const lo = t.toLowerCase();
      if(!lo.includes(ql)) continue;
      const frag = document.createDocumentFragment();
      let last=0, idx=lo.indexOf(ql);
      while(idx!==-1){{
        if(idx>last) frag.appendChild(document.createTextNode(t.slice(last,idx)));
        const m=document.createElement('mark'); m.textContent=t.slice(idx,idx+q.length);
        frag.appendChild(m);
        last = idx+q.length;
        idx = lo.indexOf(ql, last);
      }}
      if(last<t.length) frag.appendChild(document.createTextNode(t.slice(last)));
      n.parentNode.replaceChild(frag, n);
    }}
  }}
  function doSearch(){{
    const q = search.value.trim();
    btnClear.style.display = q ? 'inline-block' : 'none';
    let visible = 0;
    sections.forEach(s => clearMarks(s));
    if(!q){{
      sections.forEach(s=>s.classList.remove('hidden'));
      tocChapters.forEach(t=>t.style.display='');
      document.querySelectorAll('.toc-sub').forEach(t=>t.style.display='');
      stats.textContent='';
      return;
    }}
    const ql = q.toLowerCase();
    sections.forEach((s,idx)=>{{
      const hit = s.textContent.toLowerCase().includes(ql);
      if(hit){{ s.classList.remove('hidden'); visible++; highlight(s, q); }}
      else s.classList.add('hidden');
      const ch = tocChapters[idx];
      if(ch){{ ch.style.display = hit ? '' : 'none';
        const subs = ch.parentNode.querySelectorAll('.toc-sub');
        subs.forEach(sub=>sub.style.display = hit ? '' : 'none');
      }}
    }});
    stats.textContent = 'Найдено в главах: ' + visible;
    const first = sections.find(s=>!s.classList.contains('hidden'));
    if(first) first.scrollIntoView({{behavior:'smooth', block:'start'}});
  }}
  search.addEventListener('input', doSearch);
  btnClear.addEventListener('click', ()=>{{
    search.value=''; doSearch(); search.focus();
  }});
  updateNav();
}})();
</script>
</body>
</html>
"""


def main():
    OUT.write_text(build(), encoding="utf-8")
    print(f"OK: {OUT.name} ({OUT.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
