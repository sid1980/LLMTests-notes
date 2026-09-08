"""Песочница для кода, сгенерированного моделью / Sandbox for model-generated code.

Запускается раннером (run_ladder.py) как:
    python -I sandbox_runner.py <solution.py>      (cwd = временная папка теста)

Ставит audit-хук Python (PEP 578) ДО исполнения кода модели. Установленный хук
снять невозможно — это встроенная гарантия интерпретатора.
Installs a Python audit hook (PEP 578) BEFORE the model code runs. Once installed,
an audit hook cannot be removed — that is an interpreter guarantee.

Блокирует / Blocks:
  - всю сеть (socket/urllib/http/ftp/smtp/...), включая localhost
  - запуск процессов (subprocess.Popen, os.system/exec/spawn/fork)
  - запись/создание/удаление/переименование файлов ВНЕ временной папки теста
  - реестр Windows (winreg), ctypes и multiprocessing (каналы обхода)
Разрешает / Allows:
  - чтение файлов, stdin/stdout/stderr, threading, tempfile и os.devnull,
    всё внутри временной папки (раннер направляет TEMP/TMP/TMPDIR в неё же)

Дополнительно / Additionally:
  - в sys.modules подсажены заглушки для ctypes/multiprocessing/winreg —
    они закрывают обход блок-листа импортов через importlib.import_module()
    (тот путь вообще не генерирует audit-событие "import")
  - события блокировки пишутся напрямую в fd 2 — код модели не может
    скрыть их, подменив sys.stderr

Семантика исполнения идентична прямому `python solution.py` (__name__ ==
"__main__", тот же argv, те же коды возврата) — цифры бенча сравнимы с
прогонами до песочницы. / Execution semantics match a direct run, so scores
stay comparable with pre-sandbox reference results.

Это защита от случайно-вредного кода LLM, а не крепость против
целенаправленного человека-атакующего. / Defense against accidental harm from
LLM output, not a hardened boundary against a determined human attacker.

stdlib-only, Python 3.8+.
"""
import os
import sys
import traceback
import types

# Единственное место, куда можно писать — временная папка теста (наш cwd).
SANDBOX_DIR = os.path.normcase(os.path.realpath(os.getcwd()))
_DEVNULL = {os.path.normcase(os.devnull), "nul", "/dev/null"}

# События, запрещённые целиком (по префиксу) / event prefixes blocked outright.
_BLOCK_PREFIX = (
    "socket.", "urllib.", "http.", "ftplib.", "smtplib.", "poplib.",
    "imaplib.", "telnetlib.", "webbrowser.",            # сеть / network
    "subprocess.", "os.exec", "os.spawn", "os.posix_spawn",
    "os.fork", "pty.",                                  # процессы / processes
    "winreg.",                                          # реестр / registry
    "ctypes.",                                          # обход хуков / bypass
)
_BLOCK_EXACT = {"os.system", "os.startfile", "os.kill", "os.killpg",
                "os.add_dll_directory"}
# Импорты-лазейки: ctypes (вызов произвольного нативного кода мимо хуков),
# multiprocessing (запуск процессов мимо события subprocess.Popen на Windows).
_BLOCK_IMPORT = {"ctypes", "_ctypes", "multiprocessing", "_multiprocessing",
                 "winreg", "_winreg"}
# События изменения файловой системы — путь обязан лежать внутри SANDBOX_DIR.
_FS_MUTATE = {"os.remove", "os.rmdir", "os.rename", "os.mkdir", "os.chmod",
              "os.chown", "os.chflags", "os.truncate", "os.link", "os.symlink",
              "os.utime", "shutil.rmtree", "shutil.move", "shutil.chown"}

_WRITE_FLAGS = (os.O_WRONLY | os.O_RDWR | os.O_APPEND | os.O_CREAT |
                os.O_TRUNC)


def _inside_sandbox(path) -> bool:
    try:
        p = os.fspath(path)
        if isinstance(p, bytes):
            p = os.fsdecode(p)
        # Сырое имя тоже проверяем: на Windows realpath('nul') -> '\\.\NUL',
        # и запись в os.devnull без этого ложно блокировалась (а до песочницы
        # работала — важно для сравнимости цифр). / Check the raw name too:
        # realpath('nul') is '\\.\NUL' on Windows, which false-blocked
        # os.devnull writes that worked pre-sandbox.
        if os.path.normcase(p) in _DEVNULL:
            return True
        rp = os.path.normcase(os.path.realpath(p))
    except Exception:
        return False
    if rp in _DEVNULL:
        return True
    return rp == SANDBOX_DIR or rp.startswith(SANDBOX_DIR + os.sep)


def _deny(event):
    # Пишем прямо в fd 2: код модели мог подменить sys.stderr, но событие
    # обязано попасть в лог раннера. / Write to raw fd 2: model code may have
    # replaced sys.stderr, but the attempt must still reach the runner's log.
    msg = f"[SANDBOX] blocked: {event}\n".encode("utf-8", "replace")
    try:
        os.write(2, msg)
    except Exception:
        try:
            print(msg.decode("utf-8", "replace"), end="",
                  file=sys.__stderr__ or sys.stderr, flush=True)
        except Exception:
            pass
    raise RuntimeError(f"SANDBOX blocked: {event}")


def _hook(event, args):
    if event.startswith(_BLOCK_PREFIX) or event in _BLOCK_EXACT:
        _deny(event)
    if event == "import" and args:
        # Корневой пакет тоже проверяем: 'import ctypes.util' шлёт событие
        # 'import ctypes.util', а блок-лист держит 'ctypes'. / Check the root
        # package as well: 'import ctypes.util' fires 'import ctypes.util'.
        name = str(args[0])
        if name in _BLOCK_IMPORT or name.partition(".")[0] in _BLOCK_IMPORT:
            _deny(f"import {name}")
    if event == "open":
        # args = (path, mode, flags); чтение разрешено везде, запись — только
        # внутри песочницы / reads allowed anywhere, writes only inside sandbox.
        path, mode, flags = (list(args) + [None, None, 0])[:3]
        if path is None or isinstance(path, int):
            return  # fd-операции: сам fd уже проверен при открытии
        writing = (any(c in "wxa+" for c in mode) if isinstance(mode, str)
                   else bool((flags or 0) & _WRITE_FLAGS))
        if writing and not _inside_sandbox(path):
            _deny(f"write outside sandbox: {event}")
    if event in _FS_MUTATE:
        for a in args:
            if a is None or isinstance(a, int):
                continue
            if isinstance(a, (str, bytes, os.PathLike)) and not _inside_sandbox(a):
                _deny(f"{event} outside sandbox")


def _limits():
    # Unix: лимит памяти/размера файла. Windows: модуля resource нет — пропускаем,
    # там защищает таймаут раннера. / Unix-only rlimits; Windows relies on timeout.
    try:
        import resource
        resource.setrlimit(resource.RLIMIT_AS, (8 << 30, 8 << 30))
        resource.setrlimit(resource.RLIMIT_FSIZE, (512 << 20, 512 << 20))
    except Exception:
        pass


class _BlockedModule(types.ModuleType):
    """Заглушка: любое обращение к атрибуту = блокировка + запись в лог.
    Attribute access on a planted stub is a logged denial."""
    def __getattr__(self, name):
        _deny(f"use blocked module {self.__name__}.{name}")


def _plant_stubs():
    # importlib.import_module() НЕ генерирует audit-событие "import" — это обход
    # блок-листа импортов. Закрываем: кладём в sys.modules заглушки — любой путь
    # импорта сначала смотрит в sys.modules и получает заглушку, а не настоящий
    # модуль. На честный код не влияет: эти модули и раньше были под запретом.
    # importlib.import_module() fires NO 'import' audit event — a blocklist
    # bypass. We plant stubs in sys.modules so every import path finds the stub
    # instead of the real module. No effect on honest code (these were already
    # forbidden).
    for name in _BLOCK_IMPORT:
        stub = _BlockedModule(name)
        stub.__doc__ = "blocked by sandbox"
        sys.modules[name] = stub


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: sandbox_runner.py <solution.py>", file=sys.stderr)
        return 2
    target = os.path.realpath(sys.argv[1])
    with open(target, encoding="utf-8") as fh:
        src = fh.read()
    try:
        code = compile(src, target, "exec")
    except SyntaxError:
        traceback.print_exc()
        return 1
    _limits()
    sys.addaudithook(_hook)  # точка невозврата: дальше всё под контролем хука
    _plant_stubs()
    sys.argv = [target]
    g = {"__name__": "__main__", "__file__": target,
         "__builtins__": __builtins__}
    try:
        exec(code, g)
    except SystemExit:
        raise
    except BaseException:
        # Тоже в настоящий stderr — вдруг код модели подменил sys.stderr.
        # Real stderr as well, in case model code replaced sys.stderr.
        traceback.print_exc(file=sys.__stderr__ or sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
