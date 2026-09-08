#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Веб-панель бенча / Web control panel for the benchmark.

Запусти: python bench_web.py  (или двойной клик START_BENCH_WEB.bat) —
откроется страница в браузере: скан локальных LLM-серверов, выбор модели,
параметры (think, сэмплер — эталон/справочник/родной/свой, число прогонов,
уровни), СЕРИЯ температур (очередь тестов «поставил и ушёл»), живой лог,
кнопка «Отчёт». Всё локально (127.0.0.1), только стандартная библиотека.

Everything runs locally on 127.0.0.1, stdlib only, no pip installs.
"""
from __future__ import annotations
import json, os, subprocess, sys, threading, webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

from start_bench import scan, safe_label      # тот же сканер, что в терминальном меню
from run_ladder import find_preset            # тот же справочник, что у раннера

HERE = os.path.dirname(os.path.abspath(__file__))
PORT = int(os.environ.get("LADDER_WEB_PORT", "8765"))

# Текущая очередь (одна за раз) / current job queue, one at a time
JOB = {"proc": None, "log": "", "label": "", "rc": None, "running": False,
       "abort": False, "pos": 0, "total": 0}
_LOCK = threading.Lock()


def _mklabel(p: dict, smode: str, runs: str, think: bool, temp=None) -> str:
    label = (p.get("label") or "").strip()
    if label and temp is not None:
        label = f"{label}-t{temp}"
    if not label:
        label = safe_label(p.get("model") or "model")
        if temp is not None:
            label += f"-t{temp}"
        elif smode == "native":
            label += "-native"
        elif smode == "recommended":
            label += "-rec"
        elif smode == "custom":
            label += "-t" + str(p.get("temp")) if p.get("temp") else "-custom"
        if runs != "1":
            label += "-x" + runs
        if think:
            label += "-think"
    return safe_label(label)


def _prepare(p: dict):
    """Один тест из настроек панели -> (cmd, env, label)."""
    think = bool(p.get("think"))
    smode = p.get("sampler_mode") or "reference"
    runs = str(p.get("runs") or "1")
    track = p.get("track") or "all"
    levels = ",".join(p.get("levels") or ["easy", "medium", "hard"])
    env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8",
               LADDER_LEVELS=levels, THINK="1" if think else "0",
               LADDER_MAX_TOKENS="32000" if think else "16384",
               LADDER_RUNS=runs)
    if p.get("model"):
        env["LADDER_MODEL"] = p["model"]
    if smode in ("native", "custom", "recommended"):
        env["LADDER_SAMPLER"] = smode
    if smode == "custom":
        for key, envk in (("temp", "LADDER_TEMP"), ("top_p", "LADDER_TOP_P"),
                          ("top_k", "LADDER_TOP_K"), ("min_p", "LADDER_MIN_P"),
                          ("presence", "LADDER_PRESENCE"), ("seed", "LADDER_SEED")):
            v = p.get(key)
            if v not in (None, ""):
                env[envk] = str(v).replace(",", ".")
    label = _mklabel(p, smode, runs, think, p.get("_sweep_temp"))
    cmd = [sys.executable, "-u", os.path.join(HERE, "run_ladder.py"),
           str(p["target"]), label, track]
    return cmd, env, label


def _manager(jobs: list):
    last_rc = 0
    for i, p in enumerate(jobs, 1):
        with _LOCK:
            if JOB["abort"]:
                JOB["log"] += "\n[панель] очередь остановлена пользователем\n"
                break
            JOB["pos"] = i
        cmd, env, label = _prepare(p)
        with _LOCK:
            JOB["label"] = label
            JOB["log"] += (f"\n{'='*60}\n[панель] тест {i}/{len(jobs)}: {label}"
                           f"{'  (temp ' + str(p.get('_sweep_temp')) + ')' if p.get('_sweep_temp') is not None else ''}\n{'='*60}\n")
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, encoding="utf-8", errors="replace",
                                cwd=HERE, env=env)
        with _LOCK:
            JOB["proc"] = proc
        for line in iter(proc.stdout.readline, ""):
            with _LOCK:
                JOB["log"] += line
        proc.wait()
        last_rc = proc.returncode
        with _LOCK:
            JOB["log"] += f"[панель] тест {i}/{len(jobs)} завершён (код {last_rc})\n"
    with _LOCK:
        JOB["rc"] = last_rc
        JOB["running"] = False
        JOB["proc"] = None
        JOB["log"] += "\n[панель] ✅ вся очередь выполнена — жми «Отчёт»\n" if not JOB["abort"] \
            else "\n[панель] остановлено\n"


def start_job(p: dict) -> dict:
    with _LOCK:
        if JOB["running"]:
            return {"ok": False, "error": "Тест уже идёт — дождитесь или остановите."}
    if not str(p.get("target") or "").strip():
        return {"ok": False, "error": "Не выбран сервер."}
    # серия температур: "1.0, 0.6, 0.2" -> очередь одиночных тестов (custom сэмплер)
    temps = [t.strip() for t in str(p.get("sweep") or "").replace(";", ",").split(",") if t.strip()]
    if temps:
        jobs = []
        for t in temps:
            q = dict(p)
            q["sampler_mode"] = "custom"
            q["temp"] = t
            q["_sweep_temp"] = t
            jobs.append(q)
    else:
        jobs = [p]
    with _LOCK:
        JOB.update(log="", rc=None, running=True, abort=False, pos=0, total=len(jobs))
    threading.Thread(target=_manager, args=(jobs,), daemon=True).start()
    return {"ok": True, "total": len(jobs)}


PAGE = """<!DOCTYPE html>
<html lang="ru"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Coding Ladder — панель запуска</title>
<style>
:root{color-scheme:light;
  --page:#f9f9f7; --surface:#fcfcfb; --ink:#0b0b0b; --ink2:#52514e; --mut:#898781;
  --grid:#e1e0d9; --border:rgba(11,11,11,.10); --acc:#2a78d6; --warn:#a86a00;
  --good:#006300; --bad:#d03b3b;}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]){color-scheme:dark;
  --page:#0d0d0d; --surface:#1a1a19; --ink:#fff; --ink2:#c3c2b7; --mut:#898781;
  --grid:#2c2c2a; --border:rgba(255,255,255,.10); --acc:#3987e5; --warn:#fab219;
  --good:#0ca30c; --bad:#e66767;}}
*{box-sizing:border-box}
body{margin:0;background:var(--page);color:var(--ink);
  font:14px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif;padding:24px}
.wrap{max-width:880px;margin:0 auto}
h1{font-size:20px;margin:0 0 4px}
.subtitle{color:var(--ink2);margin:0 0 16px;font-size:13px}
.card{background:var(--surface);border:1px solid var(--border);border-radius:12px;
  padding:14px 18px;margin-bottom:14px}
.card h2{font-size:14px;margin:0 0 10px;color:var(--ink2)}
label{display:block;margin:6px 0;cursor:pointer}
.row{display:flex;gap:14px;flex-wrap:wrap;align-items:center}
select,input[type=text],input[type=number]{background:var(--page);color:var(--ink);
  border:1px solid var(--grid);border-radius:8px;padding:6px 10px;font:inherit}
input[type=number]{width:90px}
.hint{color:var(--mut);font-size:12px;margin:4px 0 0}
.btn{font:inherit;font-weight:600;border:none;border-radius:10px;padding:10px 22px;
  cursor:pointer;background:var(--acc);color:#fff}
.btn:disabled{opacity:.45;cursor:default}
.btn.ghost{background:transparent;color:var(--acc);border:1px solid var(--acc)}
.btn.small{padding:5px 12px;font-size:12px}
.btn.stop{background:var(--bad)}
#status{font-weight:600;margin-left:10px}
#status.run{color:var(--acc)} #status.ok{color:var(--good)} #status.err{color:var(--bad)}
#log{background:var(--surface);border:1px solid var(--border);border-radius:12px;
  padding:12px 14px;font:12px/1.5 Consolas,monospace;white-space:pre-wrap;
  word-break:break-word;max-height:420px;overflow-y:auto;display:none}
.srv{margin:4px 0}
.warntx{color:var(--warn)}
.lvl{display:inline;margin:0}
.lvl.off{opacity:.4;cursor:not-allowed}
.sampinfo{margin-top:8px;padding:8px 12px;border-radius:8px;font-size:13px;line-height:1.45;
  background:var(--page);border:1px solid var(--grid);border-left:3px solid var(--acc)}
.sampinfo.warnbox{border-left-color:var(--warn)}
.sampinfo b{color:var(--ink)}
.sampinfo a{color:var(--acc)}
</style></head><body><div class="wrap">
<h1>🪜 Coding Ladder — панель запуска</h1>
<p class="subtitle">Скан локальных серверов → параметры → Старт. Результаты сами попадают в
<a href="/report" target="_blank">сводный отчёт</a>.</p>

<div class="card"><h2>1 · Сервер и модель</h2>
<div class="row"><button class="btn ghost" id="rescan" onclick="doScan()">🔎 Сканировать серверы</button>
<span id="scanstate" class="hint"></span></div>
<div id="servers"></div>
<div class="row" style="margin-top:8px">Модель: <select id="model"></select></div>
</div>

<div class="card"><h2>2 · Параметры</h2>
<div class="row">
  <label><input type="checkbox" id="think"> thinking-режим (для reasoning-моделей, 32k)</label>
</div>
<div class="row" style="margin-top:6px">
  Сэмплер:
  <label><input type="radio" name="samp" value="reference" checked> базовый — как у всех в таблице (офиц. Qwen), цифры сравнимы</label>
  <label><input type="radio" name="samp" value="recommended"> по справочнику модели ⚠ не сравнить с таблицей</label>
  <label><input type="radio" name="samp" value="native"> как настроено в сервере ⚠ не сравнить</label>
  <label><input type="radio" name="samp" value="custom"> свой, для экспериментов ⚠ не сравнить</label>
</div>
<p class="hint"><b>Базовый</b> = официальная рекомендация разработчиков Qwen (temp 1.0 · top_p 0.95 ·
top_k 20 · seed 42). Тест сам шлёт эти значения в каждом запросе — настройки в GUI сервера
<b>игнорируются</b>. На них прогнаны все модели в таблице отчёта, поэтому только этот режим
даёт цифры, сравнимые с таблицей. <b>По справочнику</b>: параметры для семейства модели из
sampler_presets.json (Qwen3.5/3.6, Coder-Next, GLM, Gemma; источник — unsloth-доки).
<b>Как настроено в сервере</b>: тест ничего не навязывает — vLLM возьмёт generation_config модели,
LM Studio/Ollama — <span class="warntx">то, что выставлено у модели в приложении</span>.</p>
<div class="row" id="customs" style="display:none;margin-top:6px">
  temp <input type="number" id="temp" step="0.05" placeholder="1.0">
  top_p <input type="number" id="top_p" step="0.01" placeholder="0.95">
  top_k <input type="number" id="top_k" step="1" placeholder="20">
  min_p <input type="number" id="min_p" step="0.01" placeholder="0">
  presence <input type="number" id="presence" step="0.1" placeholder="0">
  <button class="btn ghost small" onclick="fillPreset()">⬇ подставить рекомендуемые</button>
</div>
<div id="sampinfo" class="sampinfo">—</div>
<div class="row" style="margin-top:10px">
  Прогонов: <select id="runs"><option>1</option><option>3</option><option>5</option></select>
  <span class="hint">3–5 прогонов с разными сидами = среднее и разброс</span>
</div>
<div class="row" style="margin-top:6px">
  🌡 Серия температур: <input type="text" id="sweep" placeholder="напр. 1.0, 0.6, 0.2" size="18">
  <span class="hint">не пусто → очередь тестов по одному на температуру («поставил и ушёл»)</span>
</div>
<div class="row" style="margin-top:6px">
  Трек: <select id="track"><option value="all">код + tools</option>
  <option value="code">только код</option><option value="tools">только tools</option></select>
  <span id="levels">Уровни:
  <label class="lvl"><input type="checkbox" class="lv" value="easy" checked>easy</label>
  <label class="lvl"><input type="checkbox" class="lv" value="medium" checked>medium</label>
  <label class="lvl"><input type="checkbox" class="lv" value="hard" checked>hard</label>
  <span id="lvnote" class="hint" style="display:none">— tools не делится на уровни</span></span>
</div>
<div class="row" style="margin-top:6px">
  Имя результата: <input type="text" id="label" placeholder="(авто из модели)" size="30">
</div>
</div>

<div class="card"><div class="row">
<button class="btn" id="start" onclick="doStart()">▶ Старт</button>
<button class="btn stop" id="stop" onclick="doStop()" disabled>■ Стоп</button>
<a class="btn ghost" href="/report" target="_blank">📊 Отчёт</a>
<span id="status"></span>
</div></div>

<pre id="log"></pre>
</div>
<script>
var SERVERS=[], off=0, timer=null;
function $(id){return document.getElementById(id);}
function doScan(){
  $('scanstate').textContent='сканирую...';
  fetch('/api/scan').then(r=>r.json()).then(function(list){
    SERVERS=list; var d=$('servers'); d.innerHTML='';
    if(!list.length){$('scanstate').textContent='ничего не нашла — запустите LM Studio (Start Server) / Ollama / vLLM и сканируйте снова';return;}
    $('scanstate').textContent='нашла: '+list.length;
    list.forEach(function(s,i){
      var l=document.createElement('label');l.className='srv';
      var r=document.createElement('input');r.type='radio';r.name='srv';r.value=i;
      if(i===0)r.checked=true; r.onchange=fillModels;
      l.appendChild(r);
      l.appendChild(document.createTextNode(' '+s.kind+'  :'+s.port+'  ('+s.models.length+' модел.)'));
      d.appendChild(l);});
    fillModels();
  }).catch(function(){$('scanstate').textContent='ошибка скана';});
}
function fillModels(){
  var i=document.querySelector('input[name=srv]:checked');
  var sel=$('model'); sel.innerHTML='';
  if(!i)return;
  (SERVERS[+i.value].models||[]).forEach(function(m){
    var o=document.createElement('option');o.textContent=m;sel.appendChild(o);});
  updateSampInfo();
}
function fillPreset(){
  fetch('/api/preset?model='+encodeURIComponent($('model').value)
        +'&think='+($('think').checked?1:0))
    .then(r=>r.json()).then(function(j){
      if(!j||!j.params){alert('Модель не нашлась в справочнике sampler_presets.json — оставляю поля как есть');return;}
      var p=j.params;
      $('temp').value=p.temperature!==undefined?p.temperature:'';
      $('top_p').value=p.top_p!==undefined?p.top_p:'';
      $('top_k').value=p.top_k!==undefined?p.top_k:'';
      $('min_p').value=p.min_p!==undefined?p.min_p:'';
      $('presence').value=p.presence_penalty!==undefined?p.presence_penalty:'';
    });
}
document.addEventListener('change',function(e){
  if(e.target.name==='samp')$('customs').style.display=
    (document.querySelector('input[name=samp]:checked').value==='custom')?'flex':'none';
  if(e.target.id==='track')syncLevels();
  if(e.target.name==='samp'||e.target.id==='model'||e.target.id==='think')updateSampInfo();
});
document.addEventListener('input',function(e){
  if(['temp','top_p','top_k','min_p','presence'].indexOf(e.target.id)>=0)updateSampInfo();
});
// живая плашка: на каких настройках побежит тест и ОТКУДА они взяты
function updateSampInfo(){
  var box=$('sampinfo'); box.classList.remove('warnbox');
  var mode=(document.querySelector('input[name=samp]:checked')||{}).value||'reference';
  var model=$('model').value, think=$('think').checked;
  if(mode==='reference'){
    box.innerHTML='📌 Побежит на: <b>temp 1.0 · top_p 0.95 · top_k 20 · min_p 0 · seed 42</b>'+
      '<br>Источник: <b>официальный сэмплер Qwen</b> (зашит в тест, одинаков для всех моделей — '+
      'ради сравнимости). Настройки в GUI сервера игнорируются.';
  } else if(mode==='native'){
    box.classList.add('warnbox');
    box.innerHTML='📌 Тест <b>не задаёт</b> параметры — побежит на том, что <b>выставлено у модели '+
      'в самом сервере</b> (слайдеры LM Studio / Ollama / generation_config модели у vLLM). '+
      'Тест их не видит и не меняет. ⚠ с таблицей не сравнивать.';
  } else if(mode==='custom'){
    box.classList.add('warnbox');
    var g=function(id,d){var v=$(id).value.trim();return v!==''?v:d+' (эталон)';};
    box.innerHTML='📌 Побежит на <b>твоих</b> значениях: temp '+g('temp','1.0')+' · top_p '+g('top_p','0.95')+
      ' · top_k '+g('top_k','20')+' · min_p '+g('min_p','0')+
      '.<br>Источник: <b>введено вручную</b> (эксперимент). ⚠ с таблицей не сравнивать.';
  } else if(mode==='recommended'){
    box.classList.add('warnbox');
    box.innerHTML='ищу настройки для модели «'+(model||'?')+'» в справочнике…';
    if(!model){box.innerHTML='⚠ Сначала выбери модель — покажу её рекомендованные настройки.';return;}
    fetch('/api/preset?model='+encodeURIComponent(model)+'&think='+(think?1:0))
      .then(r=>r.json()).then(function(j){
        if(j&&j.params){
          var ps=Object.keys(j.params).map(function(k){return k+' '+j.params[k];}).join(' · ');
          var src=j.source?'<a href="'+j.source+'" target="_blank" rel="noopener">unsloth-докам</a>':'unsloth-докам';
          box.innerHTML='📌 Побежит на: <b>'+ps+'</b><br>Источник: <b>справочник</b> — семейство '+
            '«'+j.name+'», по '+src+' ('+(think?'thinking':'обычный')+' режим). ⚠ с таблицей не сравнивать.';
        } else {
          box.innerHTML='⚠ Модель «'+model+'» <b>не найдена</b> в справочнике (sampler_presets.json) — '+
            'параметры переопределяться не будут, побежит как «настройки сервера».';
        }
      }).catch(function(){box.innerHTML='⚠ не удалось получить настройки из справочника';});
  }
}
function syncLevels(){
  var tools=$('track').value==='tools';
  document.querySelectorAll('#levels .lv').forEach(function(c){c.disabled=tools;});
  document.querySelectorAll('#levels .lvl').forEach(function(l){l.classList.toggle('off',tools);});
  $('lvnote').style.display=tools?'inline':'none';
}
function doStart(){
  var i=document.querySelector('input[name=srv]:checked');
  if(!i){alert('Сначала просканируй и выбери сервер');return;}
  var s=SERVERS[+i.value];
  var lv=[].slice.call(document.querySelectorAll('.lv:checked')).map(function(c){return c.value;});
  var body={target:String(s.port),model:$('model').value,think:$('think').checked,
    sampler_mode:document.querySelector('input[name=samp]:checked').value,
    temp:$('temp').value,top_p:$('top_p').value,top_k:$('top_k').value,
    min_p:$('min_p').value,presence:$('presence').value,
    runs:$('runs').value,track:$('track').value,levels:lv,
    label:$('label').value,sweep:$('sweep').value};
  fetch('/api/start',{method:'POST',body:JSON.stringify(body)}).then(r=>r.json()).then(function(j){
    if(!j.ok){alert(j.error);return;}
    off=0;$('log').style.display='block';$('log').textContent='';
    setRunning(true);$('status').textContent='идёт (тестов в очереди: '+j.total+')';$('status').className='run';
    poll();timer=setInterval(poll,1500);
  });
}
function doStop(){fetch('/api/stop',{method:'POST'});}
function setRunning(on){$('start').disabled=on;$('stop').disabled=!on;}
function poll(){
  fetch('/api/status?from='+off).then(r=>r.json()).then(function(j){
    if(j.chunk){$('log').textContent+=j.chunk;off=j.size;$('log').scrollTop=1e9;}
    if(j.running){$('status').textContent='идёт '+j.pos+'/'+j.total+': '+j.label;$('status').className='run';}
    else if(timer){
      clearInterval(timer);timer=null;setRunning(false);
      if(j.rc===0){$('status').textContent='✅ готово — смотри отчёт';$('status').className='ok';}
      else{$('status').textContent='❌ завершилось с ошибкой (код '+j.rc+')';$('status').className='err';}
    }
  });
}
window.addEventListener('load',function(){
  doScan();syncLevels();updateSampInfo();
  fetch('/api/status?from=0').then(r=>r.json()).then(function(j){
    if(j.running){off=0;$('log').style.display='block';setRunning(true);
      $('status').textContent='идёт '+j.pos+'/'+j.total+': '+j.label;$('status').className='run';
      poll();timer=setInterval(poll,1500);}
  });
});
</script></body></html>"""


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        data = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        u = urlparse(self.path)
        if u.path == "/":
            self._send(200, PAGE.encode(), "text/html; charset=utf-8")
        elif u.path == "/api/scan":
            self._send(200, [{"kind": s["kind"], "port": s["port"], "models": s["models"]}
                             for s in scan()])
        elif u.path == "/api/preset":
            q = parse_qs(u.query)
            model = (q.get("model") or [""])[0]
            think = (q.get("think") or ["0"])[0] == "1"
            self._send(200, find_preset(model, think) or {})
        elif u.path == "/api/status":
            frm = int((parse_qs(u.query).get("from") or ["0"])[0])
            with _LOCK:
                log = JOB["log"]
                self._send(200, {"running": JOB["running"], "rc": JOB["rc"],
                                 "label": JOB["label"], "size": len(log),
                                 "pos": JOB["pos"], "total": JOB["total"],
                                 "chunk": log[frm:]})
        elif u.path == "/report":
            fp = os.path.join(HERE, "report.html")
            if os.path.exists(fp):
                with open(fp, "rb") as f:
                    self._send(200, f.read(), "text/html; charset=utf-8")
            else:
                self._send(404, "<h1>Отчёта пока нет — прогоните тест</h1>".encode(),
                           "text/html; charset=utf-8")
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        body = json.loads(self.rfile.read(n) or b"{}")
        if self.path == "/api/start":
            self._send(200, start_job(body))
        elif self.path == "/api/stop":
            with _LOCK:
                JOB["abort"] = True
                p = JOB["proc"] if JOB["running"] else None
            if p:
                p.terminate()
            self._send(200, {"ok": True})
        else:
            self._send(404, {"error": "not found"})


def main():
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), H)
    url = f"http://127.0.0.1:{PORT}"
    print(f"🪜 Панель бенча: {url}  (Ctrl+C — выход)")
    if not os.environ.get("LADDER_NO_OPEN"):
        webbrowser.open(url)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nВыход / bye")


if __name__ == "__main__":
    main()
