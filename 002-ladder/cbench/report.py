"""Сборка HTML-отчёта по всем cbench_*.json в папке.

Отчёт: сводная таблица прогонов + при клике по строке — детали по каждой задаче
(код решения модели, рассуждения, ошибка компиляции, причина провала).
"""
from __future__ import annotations

import html
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent

MAX_REASONING = 4000   # показываем в отчёте, полный текст — в JSON
MAX_CODE = 30000


def _esc(s) -> str:
    return html.escape(str(s))


def build(root: Path) -> Path:
    runs = []
    for fp in sorted(root.glob("cbench_*.json")):
        try:
            runs.append(json.loads(fp.read_text(encoding="utf-8")))
        except Exception:
            continue
    rows = []
    for j in runs:
        code = (j.get("results") or {}).get("code") or {}
        by_level = code.get("by_level") or {}
        by_topic = code.get("by_topic") or {}
        cells = {
            "label": j.get("label", "?"),
            "model": j.get("model", "?"),
            "provider": (j.get("provider") or {}).get("name", "?"),
            "compiler": (j.get("conditions") or {}).get("compiler", "?"),
            "platform": (j.get("conditions") or {}).get("platform", "?"),
            "think": "think" if j.get("think") else "no-think",
            "sampler": (j.get("conditions") or {}).get("sampler_mode", "?"),
            "levels": by_level, "topics": by_topic,
            "usage": j.get("usage") or {},
            "results": code.get("results") or [],
            "wall": j.get("wall_minutes", 0),
            "partial": bool(j.get("partial")),
            "sandbox_mode": (j.get("conditions") or {}).get("sandbox_mode", ""),
        }
        rows.append(cells)

    levels = sorted({k for r in rows for k in r["levels"]})
    topics = sorted({k for r in rows for k in r["topics"]})

    body = _render(rows, levels, topics, root)
    out = root / "report.html"
    out.write_text(body, encoding="utf-8")
    return out


def _pct(d) -> str:
    if not d:
        return "—"
    total = d.get("total", 0)
    if not total:
        return "—"
    return f"{round(100 * d.get('pass', 0) / total)}%"


def _detail_html(results) -> str:
    """HTML-детализация одной задачи (код, рассуждения, ошибки)."""
    out = []
    for t in results:
        flags = ", ".join(t.get("flags") or [])
        why = t.get("why") or ""
        cls = "ok" if t.get("pass") else "bad"
        head = (f"<b>{_esc(t.get('id'))}</b> "
                f"<span class='lvl'>({_esc(t.get('level'))}/{_esc(t.get('topic'))})</span> "
                f"{'✅' if t.get('pass') else '❌'}")
        if why:
            head += f" <span class='why'>— {_esc(why)}</span>"
        if flags:
            head += f" <span class='flags'>[{_esc(flags)}]</span>"
        parts = [f"<div class='task {cls}'>{head}"]

        if t.get("reasoning"):
            r = t["reasoning"]
            note = "" if len(r) <= MAX_REASONING else "\n…[обрезано, полный текст в JSON]"
            shown = r[:MAX_REASONING] + note
            parts.append(
                f"<details><summary>🧠 рассуждения ({len(r)} симв.)</summary>"
                f"<pre class='reason'>{_esc(shown)}</pre></details>")
        elif t.get("think_tail"):
            parts.append(
                f"<details><summary>🧠 рассуждения (хвост)</summary>"
                f"<pre class='reason'>{_esc(t['think_tail'])}</pre></details>")

        if t.get("compile_error"):
            parts.append(
                f"<details><summary>⚙️ ошибка компиляции</summary>"
                f"<pre class='comp'>{_esc(t['compile_error'])}</pre></details>")

        if t.get("code"):
            c = t["code"]
            if len(c) > MAX_CODE:
                c = c[:MAX_CODE] + "\n…[обрезано]"
            parts.append(
                f"<details open><summary>📄 код решения</summary>"
                f"<pre class='code'>{_esc(c)}</pre></details>")

        parts.append("</div>")
        out.append("".join(parts))
    return "".join(out)


def _render(rows, levels, topics, root) -> str:
    details = {r["label"]: _detail_html(r["results"]) for r in rows}
    # JSON внутрь <script>: без HTML-экранирования, только защита от </script>.
    details_json = json.dumps(details, ensure_ascii=False).replace("</", "<\\/")

    tr = []
    for r in rows:
        lv_cells = "".join(
            f"<td class='num'>{_pct(r['levels'].get(l))}</td>" for l in levels)
        tp_cells = "".join(
            f"<td class='num'>{_pct(r['topics'].get(t))}</td>" for t in topics)
        u = r["usage"]
        part = " ⚠частичный" if r["partial"] else ""
        tr.append(
            f"<tr onclick='detail({json.dumps(r['label'], ensure_ascii=False)})'>"
            f"<td>{_esc(r['label'])}{part}</td><td>{_esc(r['model'])}</td>"
            f"<td>{_esc(r['provider'])}</td><td>{_esc(r['compiler'])}</td>"
            f"<td>{_esc(r['think'])}</td><td>{_esc(r['sampler'])}</td>"
            f"{lv_cells}{tp_cells}"
            f"<td class='num'>{u.get('gen_tok_s') or '—'}</td>"
            f"<td class='num'>{_esc(r['wall'])}</td></tr>")
    lv_head = "".join(f"<th>{_esc(l)}</th>" for l in levels)
    tp_head = "".join(f"<th>{_esc(t)}</th>" for t in topics)
    return f"""<!doctype html>
<html lang="ru"><head><meta charset="utf-8">
<title>cbench — отчёт</title>
<style>
body{{font-family:Segoe UI,Arial,sans-serif;margin:0;background:#111;color:#ddd}}
header{{padding:16px 24px;background:#161616;border-bottom:1px solid #333}}
h1{{font-size:20px;margin:0}}
table{{border-collapse:collapse;width:100%;font-size:13px}}
th,td{{border:1px solid #333;padding:6px 10px;text-align:left;white-space:nowrap}}
th{{background:#1e1e1e;position:sticky;top:0}}
tr:hover{{background:#202020;cursor:pointer}}
.num{{text-align:right}}
#detail{{margin:24px;background:#161616;border:1px solid #333;border-radius:6px;padding:16px;display:none}}
pre{{background:#0d0d0d;padding:10px;overflow:auto;border-radius:4px;font-size:12px;white-space:pre-wrap;word-break:break-word}}
.task{{border-left:3px solid #333;padding:8px 12px;margin:10px 0;background:#161616;border-radius:4px}}
.task.ok{{border-left-color:#4caf50}}
.task.bad{{border-left-color:#f44336}}
.task details{{margin:6px 0}}
.task summary{{cursor:pointer;color:#8ab4f8;font-size:13px}}
.lvl{{color:#888;font-size:12px}}
.why{{color:#f44336}}
.flags{{color:#ff9800;font-size:12px}}
.comp{{color:#ff8a80}}
.reason{{color:#b0bec5}}
.ok{{color:#4caf50}}.bad{{color:#f44336}}.warn{{color:#ff9800}}
</style></head><body>
<header><h1>cbench — бенчмарк знания языка Си</h1></header>
<div style="overflow:auto;max-height:70vh">
<table><thead><tr>
<th>label</th><th>model</th><th>provider</th><th>compiler</th><th>think</th><th>sampler</th>
{lv_head}{tp_head}<th>tok/s</th><th>мин</th></tr></thead>
<tbody>{''.join(tr)}</tbody></table>
</div>
<div id="detail"></div>
<script>
const DETAILS={details_json};
function detail(label){{
  const d=document.getElementById('detail');
  const html=DETAILS[label]||'';
  d.style.display='block';
  d.innerHTML='<h2>'+label+'</h2>'+(html||'<p>Нет деталей.</p>');
}}
</script></body></html>"""
