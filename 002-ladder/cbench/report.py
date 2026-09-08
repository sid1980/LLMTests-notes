"""Сборка HTML-отчёта по всем cbench_*.json в папке."""
from __future__ import annotations

import html
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent


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
    total = d.get("total", 0)
    if not total:
        return "—"
    return f"{round(100 * d.get('pass', 0) / total)}%"


def _render(rows, levels, topics, root) -> str:
    head = _esc(json.dumps([{"label": r["label"], "model": r["model"]}
                            for r in rows], ensure_ascii=False))
    tr = []
    for r in rows:
        lv_cells = "".join(
            f"<td class='num'>{_pct(r['levels'].get(l))}</td>" for l in levels)
        tp_cells = "".join(
            f"<td class='num'>{_pct(r['topics'].get(t))}</td>" for t in topics)
        u = r["usage"]
        tr.append(
            f"<tr onclick='detail({json.dumps(r['label'], ensure_ascii=False)})'>"
            f"<td>{_esc(r['label'])}</td><td>{_esc(r['model'])}</td>"
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
pre{{background:#0d0d0d;padding:10px;overflow:auto;border-radius:4px;font-size:12px}}
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
const ROWS={head};
function detail(label){{
  const r=ROWS.find(x=>x.label===label);
  const d=document.getElementById('detail');
  d.style.display='block';
  d.innerHTML='<h2>'+r.label+' — '+r.model+'</h2>'+
    '<p>Кликните в таблице для выбора прогона (детали по задачам — см. JSON).</p>';
}}
</script></body></html>"""


if __name__ == "__main__":
    p = build(HERE)
    print(f"отчёт -> {p}")
