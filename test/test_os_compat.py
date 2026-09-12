import io
import os
import subprocess
import sys

from simplecadapi._internal.os_compat import (
    fsync_directory,
    harden_console_streams,
    windows_pid_is_alive,
    with_binary_flag,
)
from simplecadapi.build.dependencies import read_stable_file
from simplecadapi.cache.store import ContentAddressedStore


def test_with_binary_flag_or_in_the_attribute_when_present(monkeypatch):
    fake = 1 << 28
    monkeypatch.setattr(os, "O_BINARY", fake, raising=False)
    assert with_binary_flag(os.O_RDONLY) == os.O_RDONLY | fake


def test_with_binary_flag_passes_through_when_attribute_missing(monkeypatch):
    monkeypatch.delattr(os, "O_BINARY", raising=False)
    assert with_binary_flag(os.O_RDONLY) == os.O_RDONLY


def test_fsync_directory_is_a_noop_off_posix(tmp_path, monkeypatch):
    monkeypatch.setattr(os, "name", "nt")

    def _forbidden(*args, **kwargs):
        raise AssertionError("directory fsync must not open files off POSIX")

    monkeypatch.setattr(os, "open", _forbidden)
    fsync_directory(tmp_path)


def test_fsync_directory_syncs_on_posix(tmp_path):
    fsync_directory(tmp_path)


def _fake_kernel32(monkeypatch, *, last_error=87):
    import ctypes

    class _FakeKernel32:
        def __init__(self):
            self.exit_code = 259
            self.closed = []

        def OpenProcess(self, access, inherit, pid):
            return 0 if pid == 424242 else 1

        def GetExitCodeProcess(self, handle, out):
            out._obj.value = self.exit_code
            return 1

        def CloseHandle(self, handle):
            self.closed.append(handle)

    kernel = _FakeKernel32()
    monkeypatch.setattr(
        ctypes, "WinDLL", lambda *args, **kwargs: kernel, raising=False
    )
    monkeypatch.setattr(
        ctypes, "get_last_error", lambda: last_error, raising=False
    )
    return kernel


def test_windows_pid_is_alive_probes_without_killing(monkeypatch):
    kernel = _fake_kernel32(monkeypatch)

    assert windows_pid_is_alive(424242) is False  # no such process
    assert windows_pid_is_alive(1) is True  # STILL_ACTIVE
    kernel.exit_code = 0
    assert windows_pid_is_alive(1) is False  # exited
    assert kernel.closed == [1, 1]


def test_windows_pid_is_alive_treats_denied_access_as_alive(monkeypatch):
    _fake_kernel32(monkeypatch, last_error=5)  # ERROR_ACCESS_DENIED
    assert windows_pid_is_alive(424242) is True


def test_pid_is_alive_routes_to_the_windows_probe_off_posix(monkeypatch):
    monkeypatch.setattr(os, "name", "nt")
    _fake_kernel32(monkeypatch)
    assert ContentAddressedStore._pid_is_alive(1) is True
    assert ContentAddressedStore._pid_is_alive(424242) is False


def test_pid_is_alive_reports_own_and_reaped_processes():
    assert ContentAddressedStore._pid_is_alive(os.getpid()) is True
    child = subprocess.Popen([sys.executable, "-c", "pass"])
    child.wait()
    assert ContentAddressedStore._pid_is_alive(child.pid) is False


def _spy_binary_open(monkeypatch):
    fake = 1 << 28
    real_open = os.open
    seen = []

    def spy(path, flags, *args, **kwargs):
        seen.append(flags)
        return real_open(path, flags, *args, **kwargs)

    monkeypatch.setattr(os, "open", spy)
    monkeypatch.setattr(os, "O_BINARY", fake, raising=False)
    return seen, fake


def test_read_stable_file_opens_in_binary_mode(tmp_path, monkeypatch):
    seen, fake = _spy_binary_open(monkeypatch)
    target = tmp_path / "builder.py"
    target.write_bytes(b"x = 1\r\ny = 2\r\n")

    payload = read_stable_file(
        target, max_bytes=1024, error_path="/file_input/path"
    )

    assert payload == b"x = 1\r\ny = 2\r\n"
    assert seen and seen[0] & fake


def test_store_atomic_write_opens_in_binary_mode(tmp_path, monkeypatch):
    seen, fake = _spy_binary_open(monkeypatch)
    target = tmp_path / "objects" / "aa" / "bb"

    ContentAddressedStore._atomic_write(target, b"payload\nline\n")

    assert target.read_bytes() == b"payload\nline\n"
    assert seen and seen[0] & fake


def test_stable_source_bytes_opens_in_binary_mode(tmp_path, monkeypatch):
    from simplecadapi.artifacts.feature_graph import _stable_source_bytes

    seen, fake = _spy_binary_open(monkeypatch)
    target = tmp_path / "source.py"
    target.write_bytes(b"a = 1\n")

    payload = _stable_source_bytes(target, max_bytes=1024, error_path="/source")

    assert payload == b"a = 1\n"
    assert seen and seen[0] & fake


def test_key_lock_opens_in_binary_mode(tmp_path, monkeypatch):
    from simplecadapi.cache.policy import CachePolicy

    seen, fake = _spy_binary_open(monkeypatch)
    store = ContentAddressedStore(CachePolicy(root=tmp_path / "cache"))

    with store.key_lock("part", "sha256:" + "0" * 64):
        pass

    assert seen and seen[0] & fake


def test_harden_console_streams_escapes_unencodable_diagnostics():
    raw = io.BytesIO()
    stream = io.TextIOWrapper(raw, encoding="ascii", errors="strict", newline="\n")

    harden_console_streams((stream,))

    stream.write("警告: wire fault\n")
    stream.flush()
    assert raw.getvalue() == b"\\u8b66\\u544a: wire fault\n"


def test_harden_console_streams_keeps_utf_streams_untouched():
    stream = io.TextIOWrapper(io.BytesIO(), encoding="utf-8", errors="strict")

    harden_console_streams((stream,))

    assert stream.errors == "strict"


def test_harden_console_streams_tolerates_plain_and_closed_streams():
    harden_console_streams((object(),))
    closed = io.TextIOWrapper(io.BytesIO(), encoding="ascii")
    closed.close()
    harden_console_streams((closed,))
