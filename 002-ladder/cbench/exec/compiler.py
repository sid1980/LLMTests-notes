"""Компиляторы Си: протокол Compiler + реализации (clang/gcc/cc, MSVC cl.exe).

Адаптер зависит только от model (CompileResult). Обнаружение: env CBENCH_CC/CC →
PATH (clang/gcc/cc) → на Windows vswhere (MSVC). Компиляция: таймаут, scrubbed
env, ограниченные пути, лимит размера исходника.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import List, Optional

from ..model import CompileResult

# Профили флагов / flag profiles.
REFERENCE_FLAGS_UNIX = ["-std=c11", "-O2", "-Wall", "-Wextra", "-Wpedantic"]
DIAGNOSTIC_FLAGS_UNIX = ["-std=c11", "-O1", "-g", "-fno-omit-frame-pointer",
                         "-fsanitize=address,undefined"]
REFERENCE_FLAGS_MSVC = ["/nologo", "/O2", "/W3", "/TC"]
DIAGNOSTIC_FLAGS_MSVC = ["/nologo", "/Od", "/W4", "/TC"]

COMPILE_TIMEOUT = float(os.environ.get("CBENCH_COMPILE_TIMEOUT", "60"))
MAX_SOURCE_BYTES = int(os.environ.get("CBENCH_MAX_SOURCE_BYTES", str(1 << 20)))

_SAFE_ENV = ("SYSTEMROOT", "SYSTEMDRIVE", "WINDIR", "TEMP", "TMP",
             "HOME", "LANG", "LC_ALL", "TMPDIR", "PATH", "COMSPEC",
             "INCLUDE", "LIB", "LIBPATH", "VSCMD_ARG_TGT_ARCH")


class Compiler:
    """Протокол компилятора."""
    name = "?"

    def compile(self, source: Path, out: Path, flags: List[str],
                cwd: Path) -> CompileResult:
        raise NotImplementedError

    def version(self) -> str:
        return ""


class _UnixCompiler(Compiler):
    """clang / gcc / cc — единый формат флагов `-o out src.c`."""

    def __init__(self, tool: str):
        self.tool = tool
        self.name = os.path.basename(tool)

    def _base_flags(self) -> List[str]:
        return []

    def compile(self, source: Path, out: Path, flags: List[str],
                cwd: Path) -> CompileResult:
        cmd = [self.tool, *flags, "-o", str(out), str(source)]
        return _run_compile(cmd, cwd, self.tool, flags, self.version())

    def version(self) -> str:
        try:
            r = subprocess.run([self.tool, "--version"], capture_output=True,
                               text=True, timeout=10)
            return (r.stdout or r.stderr or "").splitlines()[0][:120]
        except Exception:
            return ""


class ClangCompiler(_UnixCompiler):
    def __init__(self, tool: str = "clang"):
        super().__init__(tool)


class GccCompiler(_UnixCompiler):
    def __init__(self, tool: str = "gcc"):
        super().__init__(tool)


class MsvcCompiler(Compiler):
    """cl.exe из Visual Studio (через vcvars64.bat, запуск в одном cmd)."""

    def __init__(self, cl_path: str, vcvars: str):
        self.cl_path = cl_path
        self.vcvars = vcvars
        self.name = "cl"

    def _translate(self, flags: List[str]) -> List[str]:
        """Совместимость unix-флагов с cl.exe."""
        out = []
        for f in flags:
            if f == "-std=c11" or f == "-std=c99":
                out.append("/std:c11")
            elif f.startswith("-std="):
                continue  # прочие стандарты — пропускаем
            elif f.startswith("-O"):
                out.append("/O2")
            elif f in ("-Wall", "-Wextra", "-Wpedantic"):
                out.append("/W4")
            elif f.startswith("-D"):
                out.append("/D" + f[2:])
            elif f.startswith("-I"):
                out.append("/I" + f[2:])
            elif not f.startswith("-"):
                out.append(f)
        return out

    def compile(self, source: Path, out: Path, flags: List[str],
                cwd: Path) -> CompileResult:
        flags = self._translate(flags)
        # cl: /Fe задаёт имя выходного файла.
        if not any(f.startswith("/Fe") for f in flags):
            flags = flags + [f"/Fe:{out.name}"]
        args = " ".join(f for f in flags)  # флаги без кавычек (только безопасные)
        # `call` обязателен: vcvars64.bat меняет окружение в том же cmd-сеансе.
        cmd = (f'call "{self.vcvars}" >nul && '
               f'{_msvc_quote(self.cl_path)} {args} {_msvc_quote(str(source))}')
        return _run_msvc(cmd, cwd, self.name, flags, self.version())

    def version(self) -> str:
        try:
            cmd = f'call "{self.vcvars}" >nul && {_msvc_quote(self.cl_path)}'
            r = subprocess.run(cmd, shell=True, capture_output=True, text=True,
                               timeout=60, env=_scrubbed_env(),
                               encoding="utf-8", errors="replace")
            out = (r.stdout or "") + "\n" + (r.stderr or "")
            for ln in out.splitlines():
                if "Version" in ln:
                    return ln.strip()[:120]
            return out.strip().splitlines()[0][:120] if out.strip() else ""
        except Exception:
            return ""


def _run_msvc(cmd: str, cwd: Path, tool: str, flags: List[str], ver: str) -> CompileResult:
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True,
                           cwd=str(cwd), timeout=COMPILE_TIMEOUT,
                           env=_scrubbed_env(), encoding="utf-8", errors="replace")
    except subprocess.TimeoutExpired:
        return CompileResult(False, -1, "", "compile timeout", tool, ver, flags)
    except OSError as e:
        return CompileResult(False, -1, "", f"compiler not runnable: {e}",
                             tool, ver, flags)
    return CompileResult(r.returncode == 0, r.returncode, r.stdout or "",
                         r.stderr or "", tool, ver, flags)


def _msvc_quote(a: str) -> str:
    return '"' + a.replace('"', '\\"') + '"'


def _run_compile(cmd: List[str], cwd: Path, tool: str, flags: List[str],
                 ver: str) -> CompileResult:
    # Лимит размера исходника проверяем заранее (защита от гигантского вывода).
    src_arg = next((a for a in cmd if not a.startswith("-") and not a.startswith("/")), None)
    if src_arg:
        p = Path(src_arg)
        if p.exists():
            try:
                if p.stat().st_size > MAX_SOURCE_BYTES:
                    return CompileResult(False, -1, "", "source too large",
                                         tool, ver, flags)
            except OSError:
                pass
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, cwd=str(cwd),
                           timeout=COMPILE_TIMEOUT, env=_scrubbed_env(),
                           encoding="utf-8", errors="replace")
    except subprocess.TimeoutExpired as e:
        return CompileResult(False, -1, "", "compile timeout", tool, ver, flags)
    except OSError as e:
        return CompileResult(False, -1, "", f"compiler not runnable: {e}",
                             tool, ver, flags)
    return CompileResult(r.returncode == 0, r.returncode, r.stdout or "",
                         r.stderr or "", tool, ver, flags)


def _scrubbed_env() -> dict:
    env = {k: os.environ[k] for k in _SAFE_ENV if k in os.environ}
    return env


def detect(env_cc: Optional[str] = None) -> Optional[Compiler]:
    """Обнаружить компилятор: CBENCH_CC/CC → PATH → MSVC (vswhere)."""
    cc = env_cc or os.environ.get("CBENCH_CC") or os.environ.get("CC") or ""
    cc = cc.strip().strip('"')
    if cc:
        base = os.path.basename(cc).lower()
        if base.startswith("cl"):
            vcvars = find_vcvars()
            if vcvars:
                return MsvcCompiler(cc, vcvars)
            return MsvcCompiler(cc, "") if cc.endswith("cl.exe") else None
        if "clang" in base:
            return ClangCompiler(cc)
        if "gcc" in base or base == "cc":
            return GccCompiler(cc)
        # неизвестный инструмент — пробуем как unix-стиль
        return _UnixCompiler(cc)

    for tool, cls in (("clang", ClangCompiler), ("gcc", GccCompiler),
                      ("cc", GccCompiler)):
        p = shutil.which(tool)
        if p:
            return cls(p)

    # Windows: MSVC через vswhere.
    if os.name == "nt":
        cl, vcvars = find_msvc()
        if cl:
            return MsvcCompiler(cl, vcvars)
    return None


def find_vcvars() -> Optional[str]:
    if os.name != "nt":
        return None
    cl, vcvars = find_msvc()
    return vcvars


def find_msvc():
    """(cl.exe, vcvars64.bat) через vswhere. Возвращает (None, None) при неудаче."""
    if os.name != "nt":
        return None, None
    candidates = [
        os.path.join(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
                     "Microsoft Visual Studio", "Installer", "vswhere.exe"),
        os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"),
                     "Microsoft Visual Studio", "Installer", "vswhere.exe"),
    ]
    vswhere = next((p for p in candidates if Path(p).exists()), None)
    install = None
    if vswhere:
        try:
            r = subprocess.run([vswhere, "-latest", "-products", "*",
                                "-requires", "Microsoft.VisualStudio.Component.VC.Tools.x86.x64",
                                "-property", "installationPath"],
                               capture_output=True, text=True, timeout=30)
            install = (r.stdout or "").strip()
        except Exception:
            install = None
    if not install:
        return None, None
    vcvars = Path(install) / "VC" / "Auxiliary" / "Build" / "vcvars64.bat"
    if not vcvars.exists():
        return None, None
    cl = Path(install) / "VC" / "Tools" / "MSVC"
    if cl.exists():
        vers = sorted([d.name for d in cl.iterdir() if d.is_dir()], reverse=True)
        for v in vers:
            candidate = cl / v / "bin" / "Hostx64" / "x64" / "cl.exe"
            if candidate.exists():
                return str(candidate), str(vcvars)
    return None, str(vcvars)
