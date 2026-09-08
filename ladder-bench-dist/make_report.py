#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Собирает красивый HTML-отчёт по всем прогонам бенча / Builds an HTML report.

Берёт: ladder_*.json из этой папки (ваши прогоны) + results-example/ (эталонные
прогоны) → report.html. Клик по строке — детали: проваленные задачи, маркеры
галлюцинаций (обрыв по лимиту / цикл / пустой ответ / зависание кода) с хвостами
ответов. Вызывается автоматически в конце run_ladder.py, можно и руками:
python make_report.py

Только стандартная библиотека / stdlib only.
"""
from __future__ import annotations
import json, re, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REF_SAMPLER = {"temperature": 1.0, "top_p": 0.95, "top_k": 20, "min_p": 0.0, "seed": 42}
LEVELS = ["easy", "medium", "hard"]


def _strip_md(s: str) -> str:
    s = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", s)          # [text](url) -> text
    return s.replace("**", "").replace("`", "").replace("­", "").strip()


def _model_link(line: str):
    """Первая ссылка на МОДЕЛЬ (huggingface.co/namespace/model) в строке.
    Ссылки на профиль автора (huggingface.co/Jackrong, один сегмент) пропускаем."""
    for m in re.finditer(r"\]\((https?://[^)]+)\)", line):
        url = m.group(1)
        if re.search(r"huggingface\.co/[^/)]+/[^/)]+", url):
            return url
    return None


def load_models_md() -> dict:
    """label -> {desc: 'Имя · арх · квант', hf: ссылка-на-модель} из MODELS.md."""
    info = {}
    p = HERE / "results-example" / "MODELS.md"
    if not p.exists():
        return info
    for line in p.read_text(encoding="utf-8").splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) >= 5 and cells[0].startswith("`"):
            label = cells[0].strip("`")
            name, arch, quant = _strip_md(cells[1]), _strip_md(cells[3]), _strip_md(cells[4])
            quant = quant if len(quant) <= 40 else quant[:37] + "..."
            info[label] = {"desc": " · ".join(x for x in (name, arch, quant) if x),
                           "hf": _model_link(line)}
    return info


def load_run(fp: Path, is_ref: bool) -> dict:
    j = json.loads(fp.read_text(encoding="utf-8"))
    res, cond = j.get("results", {}), j.get("conditions", {})
    usage = j.get("usage", {})
    code_res = (res.get("code", {}) or {}).get("results", []) or []
    timeouts = sum(1 for r in code_res if r.get("why") == "timeout")
    cut = usage.get("answers_cut_by_limit") or 0
    loop = usage.get("loop_suspects") or 0
    empty = usage.get("empty_answers") or 0
    samp = cond.get("sampler") if cond else None
    samp_ok = (samp == REF_SAMPLER) if cond else is_ref  # старые эталоны шли на эталонном
    # non-think, но модель думала → прогон не сравним с эталоном, даже если сэмплер эталонный
    nothink_thought = bool(cond.get("nothink_thought"))
    comparable = samp_ok and not nothink_thought
    smode = cond.get("sampler_mode") or ("reference" if samp_ok else "custom")
    samp_str = (" · ".join(f"{k}={v}" for k, v in samp.items()) if samp
                else ("дефолты сервера/модели" if smode == "native" else "эталонный Qwen"))
    n_runs = cond.get("n_runs") or 1
    per_run = {lv: d.get("per_run") for lv, d in
               (res.get("code", {}).get("by_level", {}) or {}).items() if d.get("per_run")}
    if (res.get("tools") or {}).get("per_run"):
        per_run["tools"] = res["tools"]["per_run"]
    row = {"label": j.get("label", fp.stem.replace("ladder_", "")),
           "model": j.get("model") or "", "think": bool(j.get("think")),
           "ref": is_ref, "wall": j.get("wall_minutes"), "n_runs": n_runs,
           "date": time.strftime("%Y-%m-%d", time.localtime(fp.stat().st_mtime)),
           "samp_ok": samp_ok, "smode": smode, "samp_str": samp_str,
           "blocked": (res.get("code", {}) or {}).get("sandbox_blocked_tasks") or 0,
           "tok": usage.get("completion_tokens"), "speed": usage.get("gen_tok_s"),
           "has_usage": bool(usage), "cut": cut, "loop": loop, "empty": empty,
           "timeouts": timeouts, "thinking": usage.get("thinking_answers") or 0,
           "anom": (cut + loop + empty + timeouts) if (usage or code_res) else None,
           # детали для раскрывашки / details for the expandable panel
           "detail": {"cond": {"sampler": samp_str, "mode": smode,
                               "max_tokens": cond.get("max_tokens"),
                               "comparable": comparable, "nothink_thought": nothink_thought,
                               "n_runs": n_runs, "per_run": per_run or None},
                      "code": [{k: r[k] for k in
                                ("id", "level", "pass", "why", "flags", "tail", "tok",
                                 "think_tail", "think_chars", "passed_n", "n")
                                if k in r} for r in code_res],
                      "tools": (res.get("tools", {}) or {}).get("results", []) or []}}
    for lv in LEVELS:
        d = (res.get("code", {}).get("by_level", {}) or {}).get(lv)
        row[lv] = round(100 * d["pass"] / d["total"]) if d and d["total"] else None
    d = res.get("tools")
    row["tools"] = round(100 * d["pass"] / d["total"]) if d and d.get("total") else None
    return row


def collect() -> list:
    rows, seen = [], set()
    for fp in sorted(HERE.glob("ladder_*.json")):
        try:
            rows.append(load_run(fp, is_ref=False)); seen.add(fp.name)
        except Exception:
            pass  # битый/чужой json не валит отчёт
    ref_dir = HERE / "results-example"
    if ref_dir.is_dir():
        for fp in sorted(ref_dir.glob("ladder_*.json")):
            if fp.name in seen:
                continue  # ваш прогон с тем же именем важнее
            try:
                rows.append(load_run(fp, is_ref=True))
            except Exception:
                pass
    rows.sort(key=lambda r: (r["hard"] is None, -(r["hard"] or 0), -(r["tools"] or 0)))
    return rows


def _pct_cell(v, hero=False) -> str:
    if v is None:
        return '<td class="num"><span class="na">—</span></td>'
    cls = "num hero" if hero else "num"
    return (f'<td class="{cls}" data-v="{v}"><span class="v">{v}</span>'
            f'<span class="bar"><span style="width:{v}%"></span></span></td>')


def _anom_cell(r) -> str:
    if r["anom"] is None:
        return '<td class="num"><span class="na">—</span></td>'
    if r["anom"] == 0:
        return '<td class="num" data-v="0"><span class="ok">✓ чисто</span></td>'
    tip = (f"обрыв по лимиту: {r['cut']} · цикл: {r['loop']} · пустых: {r['empty']}"
           f" · зависаний кода: {r['timeouts']} — клик по строке, там детали")
    return (f'<td class="num" data-v="{r["anom"]}">'
            f'<span class="warn" title="{tip}">⚠ {r["anom"]}</span></td>')


def build(root: Path = HERE) -> Path:
    rows = collect()
    minfo = load_models_md()
    n_user = sum(1 for r in rows if not r["ref"])
    best_hard = max((r["hard"] for r in rows if r["hard"] is not None), default=None)
    best_tools = max((r["tools"] for r in rows if r["tools"] is not None), default=None)

    bodies, details = [], []
    for i, r in enumerate(rows):
        mi = minfo.get(r["label"]) or {}
        sub = r["model"] or mi.get("desc", "")
        hf = mi.get("hf")
        # клик по строке раскрывает детали, поэтому у ссылки stopPropagation
        hf_link = (f'<a href="{hf}" target="_blank" rel="noopener" class="hflink" '
                   f'onclick="event.stopPropagation()" title="Открыть модель на HuggingFace">'
                   f'&#127760; HF</a>' if hf else "")
        badge = ('<span class="chip ref">&#9733; эталон</span>' if r["ref"]
                 else '<span class="chip you">&#128300; ваш прогон</span>')
        sandbox = ("" if not r["blocked"] else
                   f' <span class="warn" title="Песочница блокировала операции в {r["blocked"]} задачах">&#128737; {r["blocked"]}</span>')
        think = '<span class="chip think">think</span>' if r["think"] else '<span class="mut">non-think</span>'
        if r["thinking"]:
            warncls = "" if r["think"] else " warnchip"
            tip = ("модель выдавала reasoning в {} задачах".format(r["thinking"]) if r["think"]
                   else "⚠ non-think, но модель ДУМАЛА в {} задачах (reasoning) — смотри детали".format(r["thinking"]))
            think += f' <span class="chip{warncls}" title="{tip}">🧠 {r["thinking"]}</span>'
        if r["n_runs"] > 1:
            think += (f' <span class="chip" title="Среднее по {r["n_runs"]} прогонам '
                      f'с разными сидами — детали по клику">×{r["n_runs"]}</span>')
        if not r["samp_ok"]:
            sname = {"native": "native", "recommended": "справочник"}.get(
                r["smode"], "свой сэмплер")
            think += (f' <span class="chip warnchip" title="Сэмплер: {r["samp_str"]} — '
                      f'цифры НЕ сравнимы с эталонными!">&#9888; {sname}</span>')
        tokk = f"{r['tok']/1000:.0f}k" if r["tok"] else None
        details.append(r["detail"])
        bodies.append(
            f'<tbody data-i="{i}"><tr class="main {"ref" if r["ref"] else "you"}">'
            f'<td class="name"><div class="lbl"><span class="caret">&#9656;</span> '
            f'{r["label"]}{sandbox} {hf_link}</div>'
            f'{f"<div class=sub>{sub}</div>" if sub else ""}</td>'
            f'<td>{badge}</td><td>{think}</td>'
            + _pct_cell(r["easy"]) + _pct_cell(r["medium"]) + _pct_cell(r["hard"], hero=True)
            + _pct_cell(r["tools"])
            + (f'<td class="num mut" data-v="{r["tok"] or 0}">{tokk}</td>' if tokk
               else '<td class="num"><span class="na">—</span></td>')
            + (f'<td class="num" data-v="{r["speed"]}">{r["speed"]}</td>' if r["speed"]
               else '<td class="num"><span class="na">—</span></td>')
            + _anom_cell(r)
            + f'<td class="num mut" data-v="{r["wall"] or 0}">{r["wall"] if r["wall"] is not None else "—"}</td>'
            f'<td class="mut">{r["date"]}</td></tr>'
            f'<tr class="detail"><td colspan="12"><div class="dbox" hidden></div></td></tr>'
            f'</tbody>')

    data_json = json.dumps(details, ensure_ascii=False).replace("</", "<\\/")

    html = """<!DOCTYPE html>
<html lang="ru"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Coding Ladder — результаты</title>
<style>
:root{color-scheme:light;
  --page:#f9f9f7; --surface:#fcfcfb; --ink:#0b0b0b; --ink2:#52514e; --mut:#898781;
  --grid:#e1e0d9; --border:rgba(11,11,11,.10); --bar:#2a78d6; --track:#e1e0d9;
  --warn:#a86a00; --good:#006300; --bad:#d03b3b; --refbg:rgba(42,120,214,.06);
  --detailbg:#f4f4f1;}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]){color-scheme:dark;
  --page:#0d0d0d; --surface:#1a1a19; --ink:#fff; --ink2:#c3c2b7; --mut:#898781;
  --grid:#2c2c2a; --border:rgba(255,255,255,.10); --bar:#3987e5; --track:#2c2c2a;
  --warn:#fab219; --good:#0ca30c; --bad:#e66767; --refbg:rgba(57,135,229,.08);
  --detailbg:#141413;}}
*{box-sizing:border-box}
body{margin:0;background:var(--page);color:var(--ink);
  font:14px/1.45 system-ui,-apple-system,"Segoe UI",sans-serif;padding:24px}
.wrap{max-width:1240px;margin:0 auto}
h1{font-size:20px;margin:0 0 4px}
.subtitle{color:var(--ink2);margin:0 0 18px;font-size:13px}
.tiles{display:flex;gap:12px;flex-wrap:wrap;margin:0 0 18px}
.tile{background:var(--surface);border:1px solid var(--border);border-radius:10px;
  padding:10px 16px;min-width:130px}
.tile .t{color:var(--mut);font-size:12px}
.tile .n{font-size:24px;font-weight:650}
.tablebox{background:var(--surface);border:1px solid var(--border);border-radius:12px;
  overflow-x:auto}
table{border-collapse:collapse;width:100%;min-width:860px;font-size:13px}
th,td{padding:7px 8px;text-align:left;border-top:1px solid var(--grid);
  vertical-align:middle;white-space:nowrap}
.name{white-space:normal;min-width:150px}
thead th{border-top:none;color:var(--mut);font-size:12px;font-weight:600;cursor:pointer;
  user-select:none}
thead th:hover{color:var(--ink)}
tr.main{cursor:pointer}
tr.main.ref{background:var(--refbg)}
tr.main:hover{background:rgba(137,135,129,.12)}
tr.detail>td{padding:0;border-top:none}
.dbox{background:var(--detailbg);border-top:1px dashed var(--grid);padding:12px 16px;
  white-space:normal}
.caret{display:inline-block;color:var(--mut);transition:transform .15s;margin-right:2px}
tbody.open .caret{transform:rotate(90deg)}
.name .lbl{font-weight:600}
.sub{color:var(--mut);font-size:12px;margin-top:1px}
.num{font-variant-numeric:tabular-nums}
.num .v{display:inline-block;min-width:1.8em;font-weight:600}
.num.hero .v{font-size:14px}
.bar{display:inline-block;width:40px;height:6px;background:var(--track);
  border-radius:3px;margin-left:5px;vertical-align:2px;overflow:hidden}
.bar>span{display:block;height:100%;background:var(--bar);border-radius:3px}
.na,.mut{color:var(--mut)}
.ok{color:var(--good);font-weight:600;font-size:12px}
.chip{font-size:10px;padding:1px 6px;border-radius:99px;border:1px solid var(--border)}
.chip.ref{background:var(--refbg)}
.chip.think{border-color:var(--bar);color:var(--bar)}
.chip.warnchip{color:var(--warn);border-color:var(--warn);cursor:help}
.warn{color:var(--warn);font-size:12px;font-weight:600;cursor:help}
.hflink{font-size:11px;font-weight:600;color:var(--bar);text-decoration:none;
  border:1px solid var(--bar);border-radius:99px;padding:1px 7px;white-space:nowrap}
.hflink:hover{background:var(--refbg)}
.foot{color:var(--mut);font-size:12px;margin-top:12px}
/* детали */
.dbox h4{margin:8px 0 6px;font-size:13px}
.dbox .fail{color:var(--bad)}
.dbox .lvlsum{margin:0 0 4px;color:var(--ink2);font-size:13px}
.dbox ul{margin:4px 0 10px;padding-left:22px}
.dbox li{margin:2px 0;font-size:13px}
.dbox .fl{color:var(--warn);font-weight:600}
.dbox details{margin:2px 0 6px}
.dbox summary{cursor:pointer;color:var(--ink2);font-size:12px}
.dbox pre{background:var(--surface);border:1px solid var(--border);border-radius:8px;
  padding:8px 10px;font-size:12px;overflow-x:auto;max-width:100%;white-space:pre-wrap;
  word-break:break-all;margin:6px 0}
.dbox .allok{color:var(--good);font-weight:600}
.dbox .grid{display:flex;flex-wrap:wrap;gap:3px;margin:4px 0 6px;max-width:700px}
.dbox .cell{width:13px;height:13px;border-radius:3px;cursor:help}
.dbox .cell.p{background:var(--good)}
.dbox .cell.f{background:var(--bad)}
.dbox .cell.h{background:var(--warn)}
.dbox .gridlegend{font-size:12px;margin:0 0 10px}
.dbox .gridlegend .cell{display:inline-block;vertical-align:-2px;cursor:default}
</style></head><body><div class="wrap">
<h1>&#129698; Coding Ladder — результаты</h1>
<p class="subtitle">Число = % решённых задач уровня. Эталонный сэмплер:
temp 1.0 · top_p 0.95 · top_k 20 · min_p 0 · seed 42.
<b>Клик по строке — детали: провалы и маркеры галлюцинаций.</b>
Клик по заголовку столбца — сортировка. Синие строки &#9733; — эталонные прогоны
(INT4, vLLM, RTX 4090, non-think). «ток» — токенов сгенерировано, «tok/s» — средняя
скорость генерации, «аномалии» — обрывы по лимиту + циклы + пустые ответы + зависания кода.</p>
<div class="tiles">
<div class="tile"><div class="t">прогонов в отчёте</div><div class="n">__NRUNS__</div></div>
<div class="tile"><div class="t">из них ваших</div><div class="n">__NUSER__</div></div>
<div class="tile"><div class="t">лучший hard</div><div class="n">__BESTH__</div></div>
<div class="tile"><div class="t">лучший tools</div><div class="n">__BESTT__</div></div>
</div>
<div class="tablebox"><table id="tbl"><thead><tr>
<th>модель / метка</th><th>тип</th><th>режим</th>
<th>easy</th><th>medium</th><th>hard &#9660;</th><th>tools</th>
<th>ток</th><th>tok/s</th><th>аномалии</th><th>&#9201; мин</th><th>дата</th></tr></thead>
__BODIES__
</table></div>
<p class="foot">Сгенерировано __WHEN__ · make_report.py (обновляется сам после каждого
прогона; руками: <code>python make_report.py</code>) · сырые данные — ladder_*.json</p>
</div>
<script id="data" type="application/json">__DATA__</script>
<script>
(function(){
  var DATA=JSON.parse(document.getElementById('data').textContent);
  var tbl=document.getElementById('tbl'), ths=tbl.tHead.rows[0].cells, dir={};
  var FL={cut:'&#9986; обрыв по лимиту',loop:'&#128257; цикл',empty:'&#8709; пустой ответ',thought:'&#129504; думала',code_from_think:'&#128295; код из размышлений'};
  function el(tag,cls,text){var e=document.createElement(tag);
    if(cls)e.className=cls; if(text!==undefined)e.textContent=text; return e;}

  function renderDetail(box,d){
    box.innerHTML='';
    var code=d.code||[], tools=d.tools||[];
    if(d.cond){
      var c=el('p','lvlsum');
      c.textContent='Условия: сэмплер — '+(d.cond.sampler||'?')
        +(d.cond.max_tokens?' · max_tokens '+d.cond.max_tokens:'')
        +(d.cond.n_runs>1?' · среднее по '+d.cond.n_runs+' прогонам (сиды разные)':'')
        +(d.cond.comparable?' · сравнимо с эталоном ✓'
          :' · ⚠ НЕ сравнимо с эталоном'+(d.cond.nothink_thought?' (non-think, но модель думала — reasoning не отключился на сервере)':''));
      box.appendChild(c);
      if(d.cond.per_run){
        var pr=el('p','lvlsum');
        pr.textContent='Разброс по прогонам: '+Object.keys(d.cond.per_run).map(function(k){
          return k+' '+d.cond.per_run[k].join(' / ');}).join(' · ');
        box.appendChild(pr);}}
    function cellCls(r){
      if(r.n>1)return r.passed_n===r.n?'p':(r.passed_n>0?'h':'f');
      return r.pass?'p':'f';}
    function stab(r){return r.n>1?' — решала '+r.passed_n+' из '+r.n+' прогонов':'';}
    function grid(items,idOf){
      var g=el('div','grid');
      items.forEach(function(r){var q=el('span','cell '+cellCls(r));
        q.title=idOf(r)+stab(r); g.appendChild(q);});
      return g;}
    function legend(multi){
      var lg=el('p','mut gridlegend');
      lg.appendChild(el('span','cell p')); lg.appendChild(document.createTextNode(' решена   '));
      if(multi){lg.appendChild(el('span','cell h'));
        lg.appendChild(document.createTextNode(' «гуляет» (решала не в каждом прогоне)   '));}
      lg.appendChild(el('span','cell f')); lg.appendChild(document.createTextNode(' провал — наведи мышь на квадратик'));
      return lg;}
    var multi=code.some(function(r){return r.n>1;})||tools.some(function(r){return r.n>1;});
    if(code.length){
      var by={};
      code.forEach(function(r){(by[r.level]=by[r.level]||[0,0]);
        by[r.level][0]+=r.pass?1:0; by[r.level][1]++;});
      var sum=el('p','lvlsum');
      sum.textContent='Код — решено: '+Object.keys(by).map(function(k){
        return k+' '+by[k][0]+' из '+by[k][1];}).join(' · ');
      box.appendChild(sum);
      box.appendChild(grid(code,function(r){
        return (cellCls(r)==='p'?'✅ ':cellCls(r)==='h'?'↕ ':'❌ ')+r.id+' ['+r.level+']'+(r.why?' — '+r.why:'');}));
      box.appendChild(legend(multi));
      var bad=code.filter(function(r){return !r.pass||(r.flags&&r.flags.length);});
      if(!bad.length){box.appendChild(el('p','allok','Все код-задачи чистые: без провалов и подозрений &#10003;'));}
      else{
        var h=el('h4',null,'Провалы и подозрения ('+bad.length+' из '+code.length+'):');box.appendChild(h);
        var ul=el('ul');
        bad.forEach(function(r){
          var cc=cellCls(r);
          var li=el('li');
          li.appendChild(el('span',cc==='p'?'':(cc==='h'?'fl':'fail'),
            (cc==='p'?'✅ ':cc==='h'?'↕ ':'❌ ')+r.id+' ['+r.level+']'));
          if(r.n>1)li.appendChild(document.createTextNode(stab(r)));
          if(r.why)li.appendChild(document.createTextNode(' — '+r.why));
          if(r.tok)li.appendChild(el('span','mut',' · '+r.tok+' ток'));
          if(r.flags&&r.flags.length){
            var fl=el('span','fl'); fl.innerHTML=' '+r.flags.map(function(f){return FL[f]||f;}).join(' + ');
            li.appendChild(fl);}
          if(r.tail){
            var det=el('details'),s=el('summary',null,'хвост ответа модели (пощупать бред глазами)');
            det.appendChild(s);var pre=el('pre');pre.textContent='…'+r.tail;det.appendChild(pre);
            li.appendChild(det);}
          if(r.think_tail){
            var d2=el('details'),s2=el('summary',null,'🧠 о чём думала'+(r.think_chars?' (~'+Math.round(r.think_chars/4)+' ток)':''));
            d2.appendChild(s2);var pre2=el('pre');pre2.textContent='…'+r.think_tail;d2.appendChild(pre2);
            li.appendChild(d2);}
          ul.appendChild(li);});
        box.appendChild(ul);}
    }
    if(tools.length){
      var p=tools.filter(function(r){return r.pass;}).length;
      box.appendChild(el('p','lvlsum','Tool-use — решено: '+p+' из '+tools.length));
      function toolWhy(r){
        if(r.got===r.expected)return ' — инструмент верный ('+r.expected+'), но аргументы не совпали';
        return ' — ждали '+r.expected+' → получили '+(r.got||'ничего (не вызвала инструмент)');}
      box.appendChild(grid(tools,function(r){
        return (r.pass?'✅ ':'❌ ')+r.id+(r.pass?'':toolWhy(r));}));
      var tbad=tools.filter(function(r){return !r.pass;});
      if(tbad.length){
        var h2=el('h4',null,'Провалы tool-use ('+tbad.length+' из '+tools.length+'):');
        box.appendChild(h2);
        var ul2=el('ul');
        tbad.forEach(function(r){
          var cc=cellCls(r);
          var li=el('li');
          li.appendChild(el('span',cc==='h'?'fl':'fail',(cc==='h'?'↕ ':'❌ ')+r.id));
          if(r.n>1)li.appendChild(document.createTextNode(stab(r)));
          li.appendChild(document.createTextNode(toolWhy(r)));
          ul2.appendChild(li);});
        box.appendChild(ul2);}
    }
    if(!code.length&&!tools.length)
      box.appendChild(el('p','mut','Для этого прогона подробностей в json нет.'));
  }

  [].slice.call(tbl.tBodies).forEach(function(tb){
    var main=tb.rows[0], box=tb.querySelector('.dbox');
    main.addEventListener('click',function(ev){
      if(ev.target.closest('a,details,summary'))return;
      var open=!box.hidden;
      if(open){box.hidden=true;tb.classList.remove('open');}
      else{renderDetail(box,DATA[+tb.dataset.i]||{});box.hidden=false;tb.classList.add('open');}
    });
  });

  function val(td){if(td.dataset.v!==undefined)return parseFloat(td.dataset.v);
    var t=td.textContent.trim();return (t==='—'||t==='')?-1:t.toLowerCase();}
  for(let i=0;i<ths.length;i++){ths[i].addEventListener('click',function(){
    var bodies=[].slice.call(tbl.tBodies);
    dir[i]=-(dir[i]||(i>=3&&i<=10?1:-1));
    bodies.sort(function(a,b){var x=val(a.rows[0].cells[i]),y=val(b.rows[0].cells[i]);
      return (x<y?-1:x>y?1:0)*dir[i];});
    for(var t=0;t<ths.length;t++)ths[t].innerHTML=ths[t].innerHTML.replace(/ ?[\\u25b2\\u25bc]/g,'');
    ths[i].innerHTML+=dir[i]>0?' \\u25b2':' \\u25bc';
    bodies.forEach(function(tb){tbl.appendChild(tb);});
  });}
})();
</script></body></html>"""
    html = (html.replace("__NRUNS__", str(len(rows)))
                .replace("__NUSER__", str(n_user))
                .replace("__BESTH__", str(best_hard) if best_hard is not None else "—")
                .replace("__BESTT__", str(best_tools) if best_tools is not None else "—")
                .replace("__WHEN__", time.strftime("%Y-%m-%d %H:%M"))
                .replace("__DATA__", data_json)
                .replace("__BODIES__", "\n".join(bodies)))
    out = root / "report.html"
    out.write_text(html, encoding="utf-8")
    return out


if __name__ == "__main__":
    p = build()
    print(f"OK -> {p}")
