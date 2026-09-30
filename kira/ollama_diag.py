from __future__ import annotations

import logging
import ntpath
import sys
from dataclasses import dataclass

log = logging.getLogger(__name__)

OLLAMA_PORT = 11434

_WSL_IMAGES = {"wslrelay.exe", "wslhost.exe"}
_DOCKER_IMAGES = {"com.docker.backend.exe", "vpnkit.exe", "docker-proxy.exe"}


def classify_port_owner(image_path: str | None) -> str:
    if not image_path:
        return "unknown"
    name = ntpath.basename(image_path).lower()
    if name.startswith("ollama"):
        return "win-ollama"
    if name in _WSL_IMAGES:
        return "wsl"
    if name in _DOCKER_IMAGES:
        return "docker"
    return "other"


@dataclass
class PortDiagnosis:
    kind: str
    pid: int | None
    image: str | None
    port: int = OLLAMA_PORT

    @property
    def hint(self) -> str:
        exe = ntpath.basename(self.image) if self.image else "unbekannter Prozess"
        if self.kind == "wsl":
            return (
                f"{exe} (PID {self.pid}) hält Port {self.port}. Der antwortende "
                f"Ollama läuft in WSL2 (systemd-Service oder Docker-Container), "
                f"NICHT der Windows-Ollama. Neustarts der Windows-App und das "
                f"VRAM-Tuning von Speech2Anywhere bewirken dort nichts. Abhilfe: den Ollama in WSL "
                f"stoppen oder auf einen anderen Port legen (Docker-Compose z. B. "
                f"127.0.0.1:11435:11434), dann übernimmt der Windows-Ollama."
            )
        if self.kind == "docker":
            return (
                f"{exe} (PID {self.pid}) hält Port {self.port}. Ein Docker-"
                f"Container stellt hier seinen eigenen Ollama bereit. Container "
                f"stoppen oder sein Port-Mapping ändern, dann übernimmt der "
                f"Windows-Ollama den Port."
            )
        if self.kind == "win-ollama":
            return (
                f"Der Windows-Ollama ({exe}, PID {self.pid}) hält Port "
                f"{self.port}. Ollama über das Tray-Icon beenden und neu "
                f"starten, dann greift das VRAM-Tuning (Flash-Attention und "
                f"q8-KV-Cache) beim nächsten Serverstart."
            )
        if self.kind == "none":
            return (
                f"Kein Prozess lauscht auf Port {self.port}. Ollama läuft "
                f"gerade nicht (oder wurde soeben beendet)."
            )
        if self.kind == "other":
            return (
                f"{exe} (PID {self.pid}) hält Port {self.port}, das ist kein "
                f"Ollama-Prozess. Prüfen, welcher Dienst hier lauscht; solange "
                f"er den Port hält, kommt der Windows-Ollama nicht zum Zug."
            )
        return (
            f"Port {self.port} ist belegt (PID {self.pid}), aber der Prozess "
            f"liess sich nicht identifizieren."
        )


def resolve_notice(base_msg: str, diag: PortDiagnosis) -> str:
    if diag.kind in ("wsl", "docker", "other"):
        return diag.hint
    return base_msg


def _listening_pid(port: int) -> int | None:
    import ctypes
    import socket
    from ctypes import wintypes

    AF_INET = 2
    TCP_TABLE_OWNER_PID_LISTENER = 3

    iphlpapi = ctypes.windll.iphlpapi
    size = wintypes.DWORD(0)
    iphlpapi.GetExtendedTcpTable(
        None, ctypes.byref(size), False, AF_INET,
        TCP_TABLE_OWNER_PID_LISTENER, 0,
    )
    buf = ctypes.create_string_buffer(size.value)
    if iphlpapi.GetExtendedTcpTable(
        buf, ctypes.byref(size), False, AF_INET,
        TCP_TABLE_OWNER_PID_LISTENER, 0,
    ) != 0:
        return None

    class _TcpRowOwnerPid(ctypes.Structure):
        _fields_ = [
            ("state", wintypes.DWORD),
            ("local_addr", wintypes.DWORD),
            ("local_port", wintypes.DWORD),
            ("remote_addr", wintypes.DWORD),
            ("remote_port", wintypes.DWORD),
            ("owning_pid", wintypes.DWORD),
        ]

    count = ctypes.cast(buf, ctypes.POINTER(wintypes.DWORD)).contents.value
    rows = ctypes.cast(
        ctypes.byref(buf, ctypes.sizeof(wintypes.DWORD)),
        ctypes.POINTER(_TcpRowOwnerPid * count),
    ).contents
    for row in rows:
        if socket.ntohs(row.local_port & 0xFFFF) == port:
            return int(row.owning_pid)
    return None


def _process_image(pid: int) -> str | None:
    import ctypes
    from ctypes import wintypes

    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    kernel32 = ctypes.windll.kernel32
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        return None
    try:
        buf = ctypes.create_unicode_buffer(1024)
        length = wintypes.DWORD(len(buf))
        if kernel32.QueryFullProcessImageNameW(
            handle, 0, buf, ctypes.byref(length),
        ):
            return buf.value
        return None
    finally:
        kernel32.CloseHandle(handle)


def diagnose_ollama_port(port: int = OLLAMA_PORT) -> PortDiagnosis:
    if sys.platform != "win32":
        return PortDiagnosis(kind="unknown", pid=None, image=None, port=port)
    try:
        pid = _listening_pid(port)
        if pid is None:
            return PortDiagnosis(kind="none", pid=None, image=None, port=port)
        image = _process_image(pid)
        return PortDiagnosis(
            kind=classify_port_owner(image), pid=pid, image=image, port=port,
        )
    except Exception:
        log.exception("Ollama-Port-Diagnose fehlgeschlagen (port=%d)", port)
        return PortDiagnosis(kind="unknown", pid=None, image=None, port=port)
