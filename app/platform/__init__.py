"""Platform Adapter — detect OS/distro/arch/shell and resolve tool availability.

Strategy: python-portable > native PATH > package manager > WSL2 > container.
Runs on any Linux (any arch/distro), macOS, and Windows (native cmd/powershell
or WSL2 bridge).
"""

from __future__ import annotations

import os
import platform
import shutil
import sys
from functools import lru_cache
from typing import Any, Optional

_DISTRO_ID: Optional[str] = None
_DISTRO_LIKE: str = ""


def _detect_linux_distro() -> tuple[Optional[str], str]:
    os_release = "/etc/os-release"
    if not os.path.exists(os_release):
        return None, ""
    data: dict[str, str] = {}
    try:
        with open(os_release, encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if "=" in line:
                    key, _, value = line.partition("=")
                    data[key.strip()] = value.strip().strip('"')
    except OSError:
        return None, ""
    return data.get("ID"), data.get("ID_LIKE", "")


@lru_cache(maxsize=1)
def probe_platform() -> dict[str, Any]:
    """Probe the runtime platform once and cache the result."""
    system = platform.system().lower()  # linux | darwin | windows
    machine = platform.machine().lower()
    arch_map = {
        "x86_64": "x86_64",
        "amd64": "x86_64",
        "aarch64": "aarch64",
        "arm64": "aarch64",
        "armv7l": "armv7l",
        "armv6l": "armv6l",
        "riscv64": "riscv64",
        "ppc64le": "ppc64le",
        "i686": "i686",
        "x86": "i686",
    }
    arch = arch_map.get(machine, machine)

    distro_id: Optional[str] = None
    distro_like = ""
    if system == "linux":
        distro_id, distro_like = _detect_linux_distro()

    shell: Optional[str] = None
    if system == "windows":
        shell = "cmd" if not os.environ.get("COMSPEC", "").endswith("powershell.exe") else "powershell"
        if shutil.which("wsl.exe") or os.path.exists(r"C:\Windows\System32\wsl.exe"):
            shell = "wsl"
    else:
        shell = os.path.basename(os.environ.get("SHELL", "sh") or "sh")

    package_managers: list[str] = []
    for manager in ("apt-get", "dnf", "pacman", "zypper", "apk", "brew", "winget", "choco", "scoop"):
        if shutil.which(manager):
            package_managers.append(manager)

    return {
        "os": system,
        "arch": arch,
        "machine": machine,
        "distro_id": distro_id,
        "distro_like": distro_like,
        "shell": shell,
        "package_managers": package_managers,
        "python_version": platform.python_version(),
        "windows": system == "windows",
        "wsl_available": shell == "wsl",
        "native_shell": "cmd" if system == "windows" else shell,
    }


def wsl_path_to_windows(path: str) -> str:
    """Convert a Linux path used inside WSL to a Windows path for native tools."""
    return path.replace("/", "\\") if not path.startswith("\\\\") else path


def windows_path_to_wsl(path: str) -> str:
    """Convert a Windows path to a WSL mount path (/mnt/c/...)."""
    if len(path) >= 2 and path[1] == ":":
        drive = path[0].lower()
        return f"/mnt/{drive}{path[2:].replace(chr(92), '/')}"
    return path


def choose_executable(executable: str) -> tuple[Optional[str], str]:
    """Resolve an executable for the current platform.

    Returns (resolved_path_or_None, method) where method is one of
    'native', 'wsl', 'missing'.
    """
    probe = probe_platform()
    found = shutil.which(executable)
    if found:
        return found, "native"
    if probe["windows"] and probe["wsl_available"]:
        wsl_exe = _wsl_which(executable)
        if wsl_exe:
            return wsl_exe, "wsl"
    return None, "missing"


def _wsl_which(executable: str) -> Optional[str]:
    try:
        import subprocess  # nosec B404

        result = subprocess.run(  # nosec B603
            ["wsl.exe", "which", executable],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        path = result.stdout.strip()
        return path or None
    except Exception:  # nosec B110
        return None


def tool_supported(executable: str, purpose: str = "") -> dict[str, Any]:
    """High-level availability report used by the inventory and CLI."""
    resolved, method = choose_executable(executable)
    return {
        "tool": executable,
        "purpose": purpose,
        "available": resolved is not None,
        "method": method,
        "resolved_path": resolved,
        "platform": probe_platform()["os"],
        "arch": probe_platform()["arch"],
    }