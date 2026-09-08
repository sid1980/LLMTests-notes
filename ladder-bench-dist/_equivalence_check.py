# Проверка эквивалентности: песочница vs прямой запуск (как до песочницы).
# Для честного кода returncode и stdout должны совпадать — тогда цифры бенча
# сравнимы с прогонами results-example/.
import subprocess, sys, tempfile, os
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUNNER = HERE / "sandbox_runner.py"

CASES = {
    "assert+basic": "assert sum(range(10)) == 45\nprint('ok')",
    "recursion900": "import sys\ndef f(n):\n    return n if n == 0 else f(n-1)+1\n"
                    "print(f(900))",
    "threading": "import threading\nr=[]\n"
                 "ts=[threading.Thread(target=lambda i=i: r.append(i*i)) for i in range(5)]\n"
                 "[t.start() for t in ts]; [t.join() for t in ts]\nprint(sorted(r))",
    "tempfile": "import tempfile\nwith tempfile.NamedTemporaryFile('w+', delete=True) as f:\n"
                "    f.write('abc'); f.seek(0); print(f.read())",
    "devnull": "import os\nopen(os.devnull, 'w').write('muted')\nprint('ok')",
    "unicode": "print('привет мир — 你好 — ñ')",
    "stdlib_wide": (
        "import json, re, math, cmath, random, statistics, fractions, decimal, "
        "heapq, bisect, itertools, functools, collections, dataclasses, enum, "
        "string, textwrap, pprint, operator, array, struct, hashlib, base64, "
        "datetime, calendar, time, copy, weakref, gc, types, contextlib, abc, "
        "numbers, reprlib, shlex, fnmatch, glob, pathlib, io, codecs, csv, "
        "sqlite3, zipfile, gzip, bz2, lzma, tarfile, configparser, argparse, "
        "logging, queue, sched, selectors, errno, keyword, token, tokenize, "
        "unicodedata, difflib, uuid, ipaddress, html, inspect, platform, "
        "traceback, warnings, linecache, filecmp, shutil, getpass, stringprep\n"
        "print('imports ok')"),
    "dataclass_use": (
        "from dataclasses import dataclass\n"
        "@dataclass\nclass P:\n    x: int\n    y: int = 2\n"
        "print(P(1))"),
    "lru_cache": "from functools import lru_cache\n@lru_cache(None)\ndef f(n):\n"
                 "    return 1 if n < 2 else f(n-1)+f(n-2)\nprint(f(30))",
    "sqlite_mem": "import sqlite3\nc = sqlite3.connect(':memory:')\n"
                  "c.execute('create table t(a)'); c.execute('insert into t values (42)')\n"
                  "print(c.execute('select a from t').fetchone()[0])",
    "big_stdout": "print('x' * 1000000)",
    "argv_empty": "import sys\nprint(sys.argv[0].endswith('.py'), len(sys.argv))",
    "main_guard": "def main():\n    print('in main')\n"
                  "if __name__ == '__main__':\n    main()",
    "exit0_explicit": "import sys\nprint('before')\nsys.exit(0)",
    "write_read_rel": "open('f.txt', 'w').write('hi')\nprint(open('f.txt').read())",
    "os_getcwd": "import os\nprint(os.path.isdir(os.getcwd()))",
    "input_echo": "s = input()\nprint(s.upper())",
}

def run_sandbox(src, td, stdin_data=""):
    f = Path(td) / "sol.py"
    f.write_text(src, encoding="utf-8")
    env = {k: os.environ[k] for k in
           ("SYSTEMROOT", "SYSTEMDRIVE", "WINDIR", "TEMP", "TMP", "HOME", "LANG", "LC_ALL", "TMPDIR")
           if k in os.environ}
    env["TEMP"] = env["TMP"] = env["TMPDIR"] = str(td)
    return subprocess.run([sys.executable, "-I", "-X", "utf8", str(RUNNER), str(f)],
                          input=stdin_data.encode(), capture_output=True,
                          timeout=20, cwd=td, env=env)

def run_direct(src, td, stdin_data=""):
    # Семантика эталонных прогонов до песочницы: python sol.py + PYTHONIOENCODING=utf-8
    f = Path(td) / "sol.py"
    f.write_text(src, encoding="utf-8")
    env = dict(os.environ); env["PYTHONIOENCODING"] = "utf-8"
    return subprocess.run([sys.executable, f], input=stdin_data.encode(),
                          capture_output=True, timeout=20, cwd=td, env=env)

fails = 0
for name, src in CASES.items():
    stdin_data = "hello\n" if name == "input_echo" else ""
    with tempfile.TemporaryDirectory() as td1, tempfile.TemporaryDirectory() as td2:
        a = run_sandbox(src, td1, stdin_data)
        b = run_direct(src, td2, stdin_data)
    same_rc = a.returncode == b.returncode
    same_out = a.stdout == b.stdout
    good = same_rc and same_out
    fails += not good
    print(f"  {'✅' if good else '❌'} {name}"
          f"  rc={a.returncode}/{b.returncode} out={'same' if same_out else 'DIFF'}")
    if not good:
        print(f"      sandbox stderr: {a.stderr[:2000]!r}")
        print(f"      direct  stderr: {b.stderr[:2000]!r}")
        print(f"      sandbox stdout head: {a.stdout[:120]!r}")
        print(f"      direct  stdout head: {b.stdout[:120]!r}")

print(f"\n{'✅ equivalence OK' if not fails else f'❌ MISMATCHES: {fails}'}")
sys.exit(1 if fails else 0)
