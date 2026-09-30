from __future__ import annotations
import hashlib
import io
import json
from unittest.mock import patch

import pytest

from kira.updater import (
    ReleaseAsset,
    UpdateCheckResult,
    check_for_update,
    download_asset,
    download_bundle,
    verify_sha256sums,
)


def _mock_response(payload: dict):
    return io.BytesIO(json.dumps(payload).encode("utf-8"))


class _Download(io.BytesIO):
    def __init__(self, data: bytes, length: int | None = None):
        super().__init__(data)
        self.headers = {"Content-Length": str(len(data) if length is None else length)}


@pytest.fixture
def fake_release():
    return {
        "tag_name": "v0.2.0",
        "assets": [
            {
                "name": "Kira-Setup-v0.2.0.exe",
                "browser_download_url": "https://example.com/Kira-Setup-v0.2.0.exe",
            }
        ],
    }


def test_check_returns_newer_when_remote_higher(fake_release):
    with patch("kira.updater.urllib.request.urlopen") as mock_open:
        mock_open.return_value.__enter__.return_value = _mock_response(fake_release)
        result = check_for_update(local_version="0.1.0", repo="x/y")
    assert result.status == "newer"
    assert result.remote_version == "0.2.0"
    assert result.asset_url == "https://example.com/Kira-Setup-v0.2.0.exe"
    assert result.asset_name == "Kira-Setup-v0.2.0.exe"


def test_check_returns_current_when_versions_match(fake_release):
    fake_release["tag_name"] = "v0.1.0"
    with patch("kira.updater.urllib.request.urlopen") as mock_open:
        mock_open.return_value.__enter__.return_value = _mock_response(fake_release)
        result = check_for_update(local_version="0.1.0", repo="x/y")
    assert result.status == "current"
    assert result.asset_url is None


def test_check_returns_local_newer_when_local_higher(fake_release):
    fake_release["tag_name"] = "v0.0.9"
    with patch("kira.updater.urllib.request.urlopen") as mock_open:
        mock_open.return_value.__enter__.return_value = _mock_response(fake_release)
        result = check_for_update(local_version="0.1.0", repo="x/y")
    assert result.status == "local_newer"


def test_check_returns_no_asset_when_assets_missing(fake_release):
    fake_release["assets"] = [{"name": "source.zip", "browser_download_url": "x"}]
    with patch("kira.updater.urllib.request.urlopen") as mock_open:
        mock_open.return_value.__enter__.return_value = _mock_response(fake_release)
        result = check_for_update(local_version="0.1.0", repo="x/y")
    assert result.status == "no_asset"


def test_check_returns_failed_on_network_error():
    with patch(
        "kira.updater.urllib.request.urlopen",
        side_effect=ConnectionError("offline"),
    ):
        result = check_for_update(local_version="0.1.0", repo="x/y")
    assert result.status == "failed"
    assert "offline" in (result.error or "")


def test_check_strips_v_prefix_from_tag(fake_release):
    fake_release["tag_name"] = "v1.0.0"
    with patch("kira.updater.urllib.request.urlopen") as mock_open:
        mock_open.return_value.__enter__.return_value = _mock_response(fake_release)
        result = check_for_update(local_version="0.1.0", repo="x/y")
    assert result.remote_version == "1.0.0"


def test_check_handles_tag_without_v_prefix(fake_release):
    fake_release["tag_name"] = "0.3.0"
    with patch("kira.updater.urllib.request.urlopen") as mock_open:
        mock_open.return_value.__enter__.return_value = _mock_response(fake_release)
        result = check_for_update(local_version="0.1.0", repo="x/y")
    assert result.remote_version == "0.3.0"
    assert result.status == "newer"


def test_check_picks_setup_exe_asset_among_multiple(fake_release):
    fake_release["assets"] = [
        {"name": "checksums.txt", "browser_download_url": "x"},
        {"name": "Kira-Setup-v0.2.0.exe", "browser_download_url": "y"},
        {"name": "source.zip", "browser_download_url": "z"},
    ]
    with patch("kira.updater.urllib.request.urlopen") as mock_open:
        mock_open.return_value.__enter__.return_value = _mock_response(fake_release)
        result = check_for_update(local_version="0.1.0", repo="x/y")
    assert result.asset_url == "y"


def test_download_asset_writes_to_target_path(tmp_path):
    target = tmp_path / "Kira-Setup-v0.2.0.exe"
    fake_bytes = b"fake setup binary content"
    with patch("kira.updater.urllib.request.urlopen",
               return_value=_Download(fake_bytes)) as mock_open:
        path = download_asset("https://example.com/Kira-Setup-v0.2.0.exe", target)
    assert path == target
    assert target.read_bytes() == fake_bytes
    assert mock_open.call_args.kwargs["timeout"] > 0


def test_download_raises_when_body_is_shorter_than_announced(tmp_path):
    import urllib.error
    with patch("kira.updater.urllib.request.urlopen",
               return_value=_Download(b"abc", length=10)):
        with pytest.raises(urllib.error.ContentTooShortError):
            download_asset("https://example.com/x.exe", tmp_path / "x.exe")


def test_exception_from_progress_aborts_the_download(tmp_path):
    class Stop(Exception):
        pass

    def stop(name, done, total):
        raise Stop()

    assets = [ReleaseAsset(name="Kira-Setup-v0.2.0.exe", url="https://x/setup.exe")]
    with patch("kira.updater.urllib.request.urlopen",
               return_value=_Download(b"x" * 300_000)):
        with pytest.raises(Stop):
            download_bundle(assets, tmp_path, on_progress=stop)


@pytest.fixture
def fake_bundle_release():
    return {
        "tag_name": "v0.2.0",
        "assets": [
            {
                "name": "Kira-Setup-v0.2.0.exe",
                "browser_download_url": "https://example.com/setup.exe",
                "size": 2_000_000,
            },
            {
                "name": "Kira-Setup-v0.2.0-1.bin",
                "browser_download_url": "https://example.com/1.bin",
                "size": 2_147_483_647,
            },
            {
                "name": "Kira-Setup-v0.2.0-2.bin",
                "browser_download_url": "https://example.com/2.bin",
                "size": 2_147_483_647,
            },
            {
                "name": "Kira-Setup-v0.2.0-7.bin",
                "browser_download_url": "https://example.com/7.bin",
                "size": 1_500_000_000,
            },
            {
                "name": "SHA256SUMS.txt",
                "browser_download_url": "https://example.com/sha256sums",
                "size": 1024,
            },
        ],
    }


def test_check_returns_full_bundle_on_newer(fake_bundle_release):
    with patch("kira.updater.urllib.request.urlopen") as mock_open:
        mock_open.return_value.__enter__.return_value = _mock_response(fake_bundle_release)
        result = check_for_update(local_version="0.1.0", repo="x/y")
    assert result.status == "newer"
    assert result.asset_name == "Kira-Setup-v0.2.0.exe"
    assert len(result.bundle_assets) == 4
    assert result.bundle_assets[0].name == "Kira-Setup-v0.2.0.exe"
    split_names = [a.name for a in result.bundle_assets[1:]]
    assert split_names == [
        "Kira-Setup-v0.2.0-1.bin",
        "Kira-Setup-v0.2.0-2.bin",
        "Kira-Setup-v0.2.0-7.bin",
    ]
    assert result.sha256sums_url == "https://example.com/sha256sums"


def test_check_bundle_with_no_sha256sums_returns_none(fake_bundle_release):
    fake_bundle_release["assets"] = [
        a for a in fake_bundle_release["assets"]
        if a["name"] != "SHA256SUMS.txt"
    ]
    with patch("kira.updater.urllib.request.urlopen") as mock_open:
        mock_open.return_value.__enter__.return_value = _mock_response(fake_bundle_release)
        result = check_for_update(local_version="0.1.0", repo="x/y")
    assert result.status == "newer"
    assert result.sha256sums_url is None
    assert len(result.bundle_assets) == 4


def test_download_bundle_writes_all_files_with_original_names(tmp_path):
    assets = [
        ReleaseAsset(name="Kira-Setup-v0.2.0.exe", url="https://x/setup.exe"),
        ReleaseAsset(name="Kira-Setup-v0.2.0-1.bin", url="https://x/1.bin"),
        ReleaseAsset(name="Kira-Setup-v0.2.0-2.bin", url="https://x/2.bin"),
    ]
    fake_bytes = {a.name: f"fake-{a.name}".encode() for a in assets}

    def fake_open(url, timeout):
        name = next(a.name for a in assets if a.url == url)
        return _Download(fake_bytes[name])

    progress_calls = []
    with patch("kira.updater.urllib.request.urlopen", side_effect=fake_open):
        paths = download_bundle(
            assets, tmp_path,
            on_progress=lambda n, d, t: progress_calls.append((n, d, t)),
        )

    assert len(paths) == 3
    assert all(p.parent == tmp_path for p in paths)
    assert {p.name for p in paths} == {
        "Kira-Setup-v0.2.0.exe",
        "Kira-Setup-v0.2.0-1.bin",
        "Kira-Setup-v0.2.0-2.bin",
    }
    for p in paths:
        assert p.read_bytes() == fake_bytes[p.name]
    assert {c[0] for c in progress_calls} == {a.name for a in assets}


def test_verify_sha256sums_passes_when_all_hashes_match(tmp_path):
    a = tmp_path / "fileA"
    b = tmp_path / "fileB"
    a.write_bytes(b"content-A")
    b.write_bytes(b"content-B")

    sums = (
        f"{hashlib.sha256(b'content-A').hexdigest()}  fileA\n"
        f"{hashlib.sha256(b'content-B').hexdigest()}  fileB\n"
    )
    sums_path = tmp_path / "SHA256SUMS.txt"
    sums_path.write_text(sums, encoding="utf-8")

    ok, errors = verify_sha256sums(sums_path, tmp_path)
    assert ok is True
    assert errors == []


def test_verify_sha256sums_fails_on_mismatch(tmp_path):
    a = tmp_path / "fileA"
    a.write_bytes(b"actual-content")
    sums = "0" * 64 + "  fileA\n"
    sums_path = tmp_path / "SHA256SUMS.txt"
    sums_path.write_text(sums, encoding="utf-8")

    ok, errors = verify_sha256sums(sums_path, tmp_path)
    assert ok is False
    assert any("mismatch" in e for e in errors)


def test_verify_sha256sums_fails_on_missing_file(tmp_path):
    sums = (
        f"{hashlib.sha256(b'x').hexdigest()}  notthere.bin\n"
    )
    sums_path = tmp_path / "SHA256SUMS.txt"
    sums_path.write_text(sums, encoding="utf-8")

    ok, errors = verify_sha256sums(sums_path, tmp_path)
    assert ok is False
    assert any("fehlt" in e for e in errors)


def test_verify_sha256sums_handles_binary_marker_asterisk(tmp_path):
    a = tmp_path / "fileA"
    a.write_bytes(b"content")
    sums = f"{hashlib.sha256(b'content').hexdigest()}  *fileA\n"
    sums_path = tmp_path / "SHA256SUMS.txt"
    sums_path.write_text(sums, encoding="utf-8")

    ok, errors = verify_sha256sums(sums_path, tmp_path)
    assert ok is True
    assert errors == []


def test_verify_sha256sums_tolerates_utf8_bom_and_crlf(tmp_path):
    a = tmp_path / "fileA"
    b = tmp_path / "fileB"
    a.write_bytes(b"content-A")
    b.write_bytes(b"content-B")

    sums = (
        f"{hashlib.sha256(b'content-A').hexdigest()}  fileA\r\n"
        f"{hashlib.sha256(b'content-B').hexdigest()}  fileB\r\n"
    )
    sums_path = tmp_path / "SHA256SUMS.txt"
    sums_path.write_bytes(b"\xef\xbb\xbf" + sums.encode("utf-8"))

    ok, errors = verify_sha256sums(sums_path, tmp_path)
    assert ok is True
    assert errors == []
