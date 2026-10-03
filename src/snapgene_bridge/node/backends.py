"""Platform adapters for launching SnapGene's official command line.

Only the WSL adapter (Linux userland on a Windows host that has SnapGene for
Windows installed) has been verified, with SnapGene 8.0.0.  The macOS and
Linux adapters follow SnapGene's documented command-line paths but are
untested and reported as such by ``status``.
"""

from __future__ import annotations

import json
import os
import platform
import plistlib
import re
import signal
import subprocess
import tempfile
from pathlib import Path

from ..errors import SnapGeneNotFoundError

WSL_CANDIDATES = (
    "/mnt/c/Program Files/SnapGene/SnapGene.exe",
    "/mnt/c/Program Files (x86)/SnapGene/SnapGene.exe",
)
MAC_CANDIDATES = ("/Applications/SnapGene.app/Contents/MacOS/SnapGene",)
LINUX_CANDIDATES = ("/opt/gslbiotech/snapgene/snapgene.sh",)

# UI Automation dump of every window owned by the given PIDs.  Written with a
# UTF-8 BOM because Windows PowerShell 5.1 otherwise reads scripts as ANSI.
_DIALOG_PS1 = r"""
param([string]$Pids)
[Console]::OutputEncoding = [Text.Encoding]::UTF8
Add-Type -AssemblyName UIAutomationClient, UIAutomationTypes
$A = [System.Windows.Automation.AutomationElement]
foreach ($id in ($Pids -split ',')) {
  $cond = New-Object System.Windows.Automation.PropertyCondition($A::ProcessIdProperty, [int]$id)
  foreach ($w in $A::RootElement.FindAll([System.Windows.Automation.TreeScope]::Children, $cond)) {
    $names = @()
    foreach ($e in $w.FindAll([System.Windows.Automation.TreeScope]::Descendants,
                              [System.Windows.Automation.Condition]::TrueCondition)) {
      if ($e.Current.Name) { $names += $e.Current.Name }
    }
    Write-Output ("[" + $w.Current.Name + "] " + ($names -join " | "))
  }
}
"""


def _run(args: list[str], *, timeout: float = 30, cwd: str | None = None) -> str:
    completed = subprocess.run(
        args,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        timeout=timeout,
        cwd=cwd,
    )
    return completed.stdout.decode("utf-8", "replace")


class Backend:
    """Common interface; subclasses override what differs per platform."""

    name = "generic"
    verified = False

    def __init__(self, exe: str):
        self.exe = exe

    def native_path(self, path: Path) -> str:
        return str(path)

    def running_pids(self) -> set[int]:
        return set()

    def kill(self, pid: int) -> None:
        try:
            os.kill(pid, signal.SIGKILL)
        except OSError:
            pass

    def version(self) -> str | None:
        return None

    def default_scratch(self) -> Path:
        return Path(tempfile.gettempdir()) / "snapgene-bridge"

    def dialog_text(self, pids: set[int], work_dir: Path) -> list[str]:
        return []

    def list_line_ending(self) -> str:
        return "\n"


class WslBackend(Backend):
    """SnapGene for Windows driven from WSL through Windows interop."""

    name = "wsl"
    verified = True

    def native_path(self, path: Path) -> str:
        return _run(["wslpath", "-w", str(path)]).strip()

    def running_pids(self) -> set[int]:
        out = _run(
            ["tasklist.exe", "/FI", "IMAGENAME eq SnapGene.exe", "/FO", "CSV", "/NH"], cwd="/mnt/c"
        )
        return {int(pid) for pid in re.findall(r'"SnapGene\.exe","(\d+)"', out, flags=re.I)}

    def kill(self, pid: int) -> None:
        _run(["taskkill.exe", "/PID", str(pid), "/F"], cwd="/mnt/c")

    def version(self) -> str | None:
        stat = os.stat(self.exe)
        cache = Path.home() / ".cache" / "snapgene-bridge" / "snapgene-version.json"
        key = f"{self.exe}|{stat.st_size}|{int(stat.st_mtime)}"
        try:
            cached = json.loads(cache.read_text())
            if cached.get("key") == key:
                return cached.get("version")
        except (OSError, ValueError):
            pass
        windows_exe = self.native_path(Path(self.exe)).replace("'", "''")
        version = (
            _run(
                [
                    "powershell.exe",
                    "-NoProfile",
                    "-NonInteractive",
                    "-Command",
                    f"(Get-Item '{windows_exe}').VersionInfo.ProductVersion",
                ],
                cwd="/mnt/c",
            ).strip()
            or None
        )
        try:
            cache.parent.mkdir(parents=True, exist_ok=True)
            cache.write_text(json.dumps({"key": key, "version": version}))
        except OSError:
            pass
        return version

    def default_scratch(self) -> Path:
        temp = _run(["cmd.exe", "/c", "echo %TEMP%"], cwd="/mnt/c").strip()
        if temp and "%" not in temp:
            return Path(_run(["wslpath", "-u", temp]).strip()) / "snapgene-bridge"
        return Path("/mnt/c/Windows/Temp/snapgene-bridge")

    def dialog_text(self, pids: set[int], work_dir: Path) -> list[str]:
        if not pids:
            return []
        script = work_dir / "dialogs.ps1"
        script.write_bytes(b"\xef\xbb\xbf" + _DIALOG_PS1.encode("utf-8"))
        try:
            out = _run(
                [
                    "powershell.exe",
                    "-NoProfile",
                    "-NonInteractive",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    self.native_path(script),
                    "-Pids",
                    ",".join(str(pid) for pid in sorted(pids)),
                ],
                timeout=60,
                cwd="/mnt/c",
            )
        except subprocess.TimeoutExpired:
            return ["(could not read dialog text: UI Automation timed out)"]
        return [line.strip() for line in out.splitlines() if line.strip()]

    def list_line_ending(self) -> str:
        return "\r\n"


class MacBackend(Backend):
    name = "macos (untested)"

    def running_pids(self) -> set[int]:
        out = _run(["pgrep", "-x", "SnapGene"])
        return {int(pid) for pid in out.split()}

    def version(self) -> str | None:
        plist = Path(self.exe).parents[1] / "Info.plist"
        try:
            with plist.open("rb") as handle:
                return plistlib.load(handle).get("CFBundleShortVersionString")
        except (OSError, ValueError):
            return None


class LinuxBackend(Backend):
    name = "linux (untested)"

    def running_pids(self) -> set[int]:
        out = _run(["pgrep", "-f", "gslbiotech/snapgene"])
        return {int(pid) for pid in out.split()} - {os.getpid()}


def is_wsl() -> bool:
    return "microsoft" in platform.release().lower()


def detect_backend(snapgene_exe: str | None = None) -> Backend:
    """Pick the adapter for this machine and locate the SnapGene executable."""

    if is_wsl():
        cls, candidates = WslBackend, WSL_CANDIDATES
    elif platform.system() == "Darwin":
        cls, candidates = MacBackend, MAC_CANDIDATES
    else:
        cls, candidates = LinuxBackend, LINUX_CANDIDATES
    paths = [snapgene_exe] if snapgene_exe else list(candidates)
    for path in paths:
        if path and Path(path).exists():
            return cls(path)
    raise SnapGeneNotFoundError(
        "SnapGene was not found on this node.",
        hint="Install SnapGene, or set snapgene_exe in the client config to its executable path.",
        details={"searched": paths},
    )
