# Адверсариальные пробы песочницы (после харденинга) / adversarial probes.
import sys, os, tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.argv = ["run_ladder.py", "selftest"]
import importlib.util
spec = importlib.util.spec_from_file_location("run_ladder", HERE / "run_ladder.py")
rl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rl)

fd, probe = tempfile.mkstemp(prefix="ladder_probe2_")
os.close(fd)
Path(probe).write_text("canary", encoding="utf-8")

def case(name, snippet, expect_ok, expect_blocked):
    ok, why, sb = rl.run_func(snippet, "")
    blocked = bool(sb) or "SANDBOX" in why
    good = (ok == expect_ok) and (blocked == expect_blocked)
    print(f"  {'✅' if good else '❌'} {name}")
    if not good:
        print(f"      ok={ok} why={why!r} sandbox_log={sb}")
    return good

fails = 0
try:
    fails += not case("importlib->ctypes + доступ к атрибуту",
        "import importlib\nct = importlib.import_module('ctypes')\nct.CDLL(None)",
        False, True)
    fails += not case("importlib->multiprocessing + Process (Windows spawn)",
        "import importlib\nmp = importlib.import_module('multiprocessing')\nmp.Process",
        False, True)
    fails += not case("import ctypes.util",
        "import ctypes.util\nprint('x')", False, True)
    fails += not case("from ctypes import CDLL",
        "from ctypes import CDLL\nprint('x')", False, True)
    fails += not case("winreg через importlib",
        "import importlib\nwr = importlib.import_module('winreg')\nwr.HKEY_CURRENT_USER",
        False, True)
    fails += not case("os.chdir + запись вне песочницы",
        f"import os\nos.chdir(r'{os.path.dirname(probe)}')\n"
        "open('escaped.txt', 'w').write('boom')", False, True)
    fails += not case("tempfile (честный код)",
        "import tempfile\nwith tempfile.NamedTemporaryFile('w', delete=True) as f:\n"
        "    f.write('x')\nprint('ok')", True, False)
    fails += not case("os.devnull (честный код)",
        "import os, sys\nsys.stderr = open(os.devnull, 'w')\nprint('ok')", True, False)
    fails += not case("подмена sys.stderr — событие блокировки всё равно логируется",
        "import sys, os\nsys.stderr = open(os.devnull, 'w')\n"
        "try:\n    os.system('echo x')\nexcept Exception:\n    pass\nprint('done')",
        True, True)
finally:
    canary_ok = Path(probe).exists() and Path(probe).read_text(encoding="utf-8") == "canary"
    print(f"canary intact: {canary_ok}")
    esc = Path(probe).parent / "escaped.txt"
    print(f"no escaped file: {not esc.exists()}")
    if esc.exists():
        fails += 1
        esc.unlink()
    try:
        os.remove(probe)
    except OSError:
        pass

print(f"{'✅ all probes pass' if not fails else f'❌ FAILURES: {fails}'}")
sys.exit(1 if fails else 0)
