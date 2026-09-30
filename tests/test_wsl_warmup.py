from __future__ import annotations
import sys
from unittest.mock import patch

import pytest

if sys.platform != "win32":
    pytest.skip("windows-only tests", allow_module_level=True)

from kira import _wsl_warmup  # pyright: ignore[reportUnreachable]


def test_kick_wsl_dispatches_wsl_exe():
    with patch("kira._wsl_warmup.subprocess.Popen") as popen:
        _wsl_warmup.kick_wsl_distro()
    popen.assert_called_once()
    cmd = popen.call_args[0][0]
    assert cmd[0] == "wsl.exe"
    assert "--exec" in cmd


def test_kick_wsl_uses_create_no_window_flag():
    with patch("kira._wsl_warmup.subprocess.Popen") as popen:
        _wsl_warmup.kick_wsl_distro()
    kwargs = popen.call_args.kwargs
    assert kwargs.get("creationflags", 0) & 0x08000000


def test_kick_wsl_does_not_raise_when_wsl_missing():
    with patch("kira._wsl_warmup.subprocess.Popen", side_effect=FileNotFoundError):
        _wsl_warmup.kick_wsl_distro()


def test_kick_wsl_does_not_raise_when_subprocess_blows_up():
    with patch("kira._wsl_warmup.subprocess.Popen", side_effect=OSError("EBADF")):
        _wsl_warmup.kick_wsl_distro()


def test_kick_wsl_does_not_block_caller():
    from unittest.mock import MagicMock
    fake_proc = MagicMock()
    with patch("kira._wsl_warmup.subprocess.Popen", return_value=fake_proc):
        _wsl_warmup.kick_wsl_distro()
    fake_proc.wait.assert_not_called()
    fake_proc.communicate.assert_not_called()
