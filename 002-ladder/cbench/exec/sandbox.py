"""Песочница для запуска скомпилированного Си-бинарника.

Протокол Sandbox + реализации LinuxSandbox (setrlimit/setsid) и
WindowsSandbox (process group + taskkill + опционально Job Object).

Честная оговорка: защита от *случайно-вредного кода LLM*, а не крепость против
целенаправленного атакующего. Надёжная блокировка сети на Windows не
гарантируется — при паранойе гоняйте в VM/WSL/контейнере.
"""
from __future__ import annotations

import os
import subprocess
import time
from typing import List, Optional

from ..model import RunOutcome

MAX_OUTPUT_BYTES = int(os.environ.get("CBENCH_MAX_OUTPUT_BYTES", str(2 << 20)))
MAX_STDIN_BYTES = int(os.environ.get("CBENCH_MAX_STDIN_BYTES", str(1 << 20)))

_SAFE_ENV = ("SYSTEMROOT", "SYSTEMDRIVE", "WINDIR", "TEMP", "TMP",
             "HOME", "LANG", "LC_ALL", "TMPDIR", "COMSPEC")


class Sandbox:
    mode = "?"

    def run(self, binary: str, argv: List[str], stdin: str, cwd: str,
            timeout: float) -> RunOutcome:
        raise NotImplementedError


def _scrubbed_env() -> dict:
    return {k: os.environ[k] for k in _SAFE_ENV if k in os.environ}


def _decode(data: bytes) -> str:
    if len(data) > MAX_OUTPUT_BYTES:
        data = data[:MAX_OUTPUT_BYTES] + b"\n...[truncated]..."
    return data.decode("utf-8", "replace")


class LinuxSandbox(Sandbox):
    mode = "linux"

    def run(self, binary: str, argv: List[str], stdin: str, cwd: str,
            timeout: float) -> RunOutcome:
        env = _scrubbed_env()
        stdin_b = stdin.encode("utf-8")[:MAX_STDIN_BYTES]
        proc = None
        try:
            proc = subprocess.Popen(
                [binary, *argv], cwd=cwd, env=env,
                stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, start_new_session=True,
                preexec_fn=_linux_preexec)
            out_b, err_b = proc.communicate(input=stdin_b, timeout=timeout)
            return RunOutcome(exit_code=proc.returncode, stdout=_decode(out_b),
                              stderr=_decode(err_b), timeout=False,
                              signal=_sig_of(proc.returncode))
        except subprocess.TimeoutExpired:
            _kill_linux(proc)
            out_b, err_b = proc.communicate()
            return RunOutcome(exit_code=proc.returncode, stdout=_decode(out_b),
                              stderr=_decode(err_b), timeout=True)
        except OSError as e:
            return RunOutcome(exit_code=None, stderr=f"run error: {e}", timeout=False)
        finally:
            if proc is not None and proc.poll() is None:
                _kill_linux(proc)


def _linux_preexec():
    import resource
    try:
        resource.setrlimit(resource.RLIMIT_CPU, (10, 10))
        resource.setrlimit(resource.RLIMIT_AS, (8 << 30, 8 << 30))
        resource.setrlimit(resource.RLIMIT_FSIZE, (512 << 20, 512 << 20))
        resource.setrlimit(resource.RLIMIT_NPROC, (64, 64))
        resource.setrlimit(resource.RLIMIT_NOFILE, (256, 256))
    except Exception:
        pass


def _kill_linux(proc):
    try:
        os.killpg(os.getpgid(proc.pid), 9)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass


def _sig_of(code: int) -> Optional[int]:
    if code is not None and code < 0:
        return -code
    return None


class WindowsSandbox(Sandbox):
    mode = "windows-best-effort"

    def run(self, binary: str, argv: List[str], stdin: str, cwd: str,
            timeout: float) -> RunOutcome:
        env = _scrubbed_env()
        stdin_b = stdin.encode("utf-8")[:MAX_STDIN_BYTES]
        flags = subprocess.CREATE_NEW_PROCESS_GROUP
        proc = None
        job = _JobObject()
        try:
            proc = subprocess.Popen(
                [binary, *argv], cwd=cwd, env=env,
                stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, creationflags=flags)
            job.assign(proc.pid)
            out_b, err_b = proc.communicate(input=stdin_b, timeout=timeout)
            return RunOutcome(exit_code=proc.returncode, stdout=_decode(out_b),
                              stderr=_decode(err_b), timeout=False,
                              sandbox_degraded=job.degraded)
        except subprocess.TimeoutExpired:
            _kill_win(proc)
            out_b, err_b = proc.communicate()
            return RunOutcome(exit_code=proc.returncode, stdout=_decode(out_b),
                              stderr=_decode(err_b), timeout=True,
                              sandbox_degraded=job.degraded)
        except OSError as e:
            return RunOutcome(exit_code=None, stderr=f"run error: {e}", timeout=False,
                              sandbox_degraded=job.degraded)
        finally:
            if proc is not None and proc.poll() is None:
                _kill_win(proc)


def _kill_win(proc):
    try:
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(proc.pid)],
                       capture_output=True, timeout=15)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass


class _JobObject:
    """Минимальный Job Object (best-effort лимит памяти) через ctypes.

    При любой ошибке — degraded=True, раннер продолжает работу без лимита.
    """
    def __init__(self):
        self.degraded = False
        self._handle = None
        try:
            import ctypes
            from ctypes import wintypes
            self._ct = ctypes
            self._wt = wintypes
            kernel32 = ctypes.windll.kernel32
            self._kernel32 = kernel32
            h = kernel32.CreateJobObjectW(None, None)
            if not h:
                self.degraded = True
                return
            self._handle = h
            # JOBOBJECT_EXTENDED_LIMIT_INFORMATION: memory + kill-on-close.
            class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
                _fields_ = [
                    ("PerProcessUserTimeLimit", ctypes.c_int64),
                    ("PerJobUserTimeLimit", ctypes.c_int64),
                    ("LimitFlags", wintypes.DWORD),
                    ("MinimumWorkingSetSize", ctypes.c_size_t),
                    ("MaximumWorkingSetSize", ctypes.c_size_t),
                    ("ActiveProcessLimit", wintypes.DWORD),
                    ("Affinity", ctypes.c_size_t),
                    ("PriorityClass", wintypes.DWORD),
                    ("SchedulingClass", wintypes.DWORD),
                ]
            class IO_COUNTERS(ctypes.Structure):
                _fields_ = [
                    ("ReadOperationCount", ctypes.c_uint64),
                    ("WriteOperationCount", ctypes.c_uint64),
                    ("OtherOperationCount", ctypes.c_uint64),
                    ("ReadTransferCount", ctypes.c_uint64),
                    ("WriteTransferCount", ctypes.c_uint64),
                    ("OtherTransferCount", ctypes.c_uint64),
                ]
            class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
                _fields_ = [
                    ("BasicLimitInformation", JOBOBJECT_BASIC_LIMIT_INFORMATION),
                    ("IoInfo", IO_COUNTERS),
                    ("ProcessMemoryLimit", ctypes.c_size_t),
                    ("JobMemoryLimit", ctypes.c_size_t),
                    ("PeakProcessMemoryUsed", ctypes.c_size_t),
                    ("PeakJobMemoryUsed", ctypes.c_size_t),
                ]
            self._info_cls = JOBOBJECT_EXTENDED_LIMIT_INFORMATION
            self._LIMIT_FLAG_MEMORY = 0x100   # JOB_OBJECT_LIMIT_PROCESS_MEMORY
            self._LIMIT_FLAG_KILL = 0x2000    # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
            self._INFO_CLASS = 9              # JobObjectExtendedLimitInformation
        except Exception:
            self.degraded = True

    def assign(self, pid: int):
        if self.degraded or self._handle is None:
            return
        try:
            ph = self._kernel32.OpenProcess(0x40 | 0x2, False, pid)  # PROCESS_DUP_HANDLE|SET_INFORMATION
            if not ph:
                self.degraded = True
                return
            info = self._info_cls()
            info.BasicLimitInformation.LimitFlags = self._LIMIT_FLAG_MEMORY | self._LIMIT_FLAG_KILL
            info.ProcessMemoryLimit = 8 << 30
            self._kernel32.SetInformationJobObject(self._handle, self._INFO_CLASS,
                                                   ctypes.byref(info),
                                                   ctypes.sizeof(info))
            self._kernel32.AssignProcessToJobObject(self._handle, ph)
            self._kernel32.CloseHandle(ph)
        except Exception:
            self.degraded = True


def make_sandbox() -> Sandbox:
    if os.name == "nt":
        return WindowsSandbox()
    return LinuxSandbox()
