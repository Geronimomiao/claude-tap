"""Pytest configuration and shared fixtures."""

import os
import shutil
import signal
import socket
import tempfile
import time
from pathlib import Path

import pytest

from claude_tap.cli_clients import _extend_no_proxy
from claude_tap.trace_store import get_trace_store, reset_trace_store

# Prevent tests and their subprocesses from falling back to the user's default browser.
_NOOP_BROWSER = shutil.which("true")
if _NOOP_BROWSER:
    os.environ["BROWSER"] = _NOOP_BROWSER


def _isolated_dashboard_port() -> str:
    configured = os.environ.get("CLOUDTAP_DASHBOARD_PORT", "").strip()
    if configured.isdigit() and int(configured) > 0 and int(configured) != 19527:
        return configured
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return str(sock.getsockname()[1])


# Never let a test subprocess replace the user's main dashboard on port 19527.
os.environ["CLOUDTAP_DASHBOARD_PORT"] = _isolated_dashboard_port()


def dashboard_listener_pids(port: int) -> list[int]:
    """Return pids of claude-tap dashboard processes listening on ``port``."""
    from claude_tap.shared_dashboard import (
        _dashboard_listening_pids_for_port,
        _dashboard_process_command,
        _looks_like_legacy_dashboard_command,
    )

    return [
        pid
        for pid in _dashboard_listening_pids_for_port(port)
        if pid != os.getpid() and _looks_like_legacy_dashboard_command(_dashboard_process_command(pid), port)
    ]


def terminate_dashboard_listeners(port: int, *, timeout_seconds: float = 10.0) -> list[int]:
    """Terminate claude-tap dashboards listening on ``port``; return surviving pids.

    E2E tests run the real CLI, which spawns the shared dashboard as a detached
    process (``start_new_session=True``), so no test owns a handle to it and it
    survives pytest exit. The only reliable teardown is to locate the listener
    on the isolated test port, verify its command line is a claude-tap
    dashboard, and signal it, escalating to SIGKILL when SIGTERM is ignored.
    """
    pids = dashboard_listener_pids(port)
    if not pids:
        return []
    sigkill = getattr(signal, "SIGKILL", signal.SIGTERM)
    for sig in (signal.SIGTERM, sigkill):
        for pid in pids:
            try:
                os.kill(pid, sig)
            except OSError:
                continue
        deadline = time.monotonic() + timeout_seconds / 2
        while time.monotonic() < deadline:
            pids = dashboard_listener_pids(port)
            if not pids:
                return []
            time.sleep(0.1)
    return pids


@pytest.fixture(scope="session", autouse=True)
def no_leaked_test_dashboard():
    """Stop the detached test dashboard after the suite; fail if one survives."""
    port = int(os.environ["CLOUDTAP_DASHBOARD_PORT"])
    yield
    leftover = terminate_dashboard_listeners(port)
    if leftover:
        raise RuntimeError(
            f"claude-tap dashboard still listening on test port {port} after suite teardown (pids: {leftover})"
        )


def trace_db_path(trace_dir: str | Path) -> Path:
    return Path(trace_dir) / "claude-tap-test.sqlite3"


def e2e_env(env: dict[str, str], trace_dir: str | Path) -> dict[str, str]:
    updated = dict(env)
    updated["CLOUDTAP_DB"] = str(trace_db_path(trace_dir))
    _extend_no_proxy(updated, ("localhost", "127.0.0.1", "::1"))
    return updated


def read_trace_records(trace_dir: str | Path, *, session_index: int = -1) -> list[dict]:
    db_path = trace_db_path(trace_dir)
    reset_trace_store()
    os.environ["CLOUDTAP_DB"] = str(db_path)
    store = get_trace_store()
    rows = store.list_session_rows()
    if not rows:
        return []
    session_id = rows[session_index]["id"]
    return store.load_records(session_id)


def read_proxy_log(trace_dir: str | Path, *, session_index: int = -1) -> str:
    db_path = trace_db_path(trace_dir)
    reset_trace_store()
    os.environ["CLOUDTAP_DB"] = str(db_path)
    store = get_trace_store()
    rows = store.list_session_rows()
    if not rows:
        return ""
    session_id = rows[session_index]["id"]
    return store.export_log(session_id)


@pytest.fixture(autouse=True)
def isolate_trace_store():
    """Reset the process-wide TraceStore singleton and CLOUDTAP_DB between tests."""
    saved_db = os.environ.get("CLOUDTAP_DB")
    os.environ.pop("CLOUDTAP_DB", None)
    reset_trace_store()
    yield
    reset_trace_store()
    if saved_db is None:
        os.environ.pop("CLOUDTAP_DB", None)
    else:
        os.environ["CLOUDTAP_DB"] = saved_db


@pytest.fixture
def trace_db(tmp_path, monkeypatch):
    """Provide an isolated SQLite trace database for each test."""
    db_path = tmp_path / "test-traces.sqlite3"
    monkeypatch.setenv("CLOUDTAP_DB", str(db_path))
    reset_trace_store()
    yield db_path
    reset_trace_store()


@pytest.fixture
def temp_trace_dir():
    """Create a temporary directory for trace output."""
    trace_dir = tempfile.mkdtemp(prefix="claude_tap_test_")
    yield trace_dir
    shutil.rmtree(trace_dir, ignore_errors=True)


@pytest.fixture
def temp_bin_dir():
    """Create a temporary directory for fake binaries."""
    bin_dir = tempfile.mkdtemp(prefix="claude_tap_bin_")
    yield bin_dir
    shutil.rmtree(bin_dir, ignore_errors=True)


@pytest.fixture
def project_dir():
    """Return the project root directory."""
    return Path(__file__).parent.parent
