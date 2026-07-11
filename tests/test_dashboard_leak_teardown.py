"""Regression tests for the suite-level dashboard leak teardown.

E2E tests run the real CLI, which spawns the shared dashboard as a detached
process. These tests prove the conftest teardown helper finds and kills such
a listener so no test dashboard survives after pytest exits.
"""

import os
import shutil
import socket
import subprocess
import sys
import time

import pytest

from tests.conftest import dashboard_listener_pids, terminate_dashboard_listeners

_HAS_PORT_INSPECTOR = bool(shutil.which("lsof") or shutil.which("ss"))


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@pytest.mark.skipif(
    sys.platform == "win32" or not _HAS_PORT_INSPECTOR,
    reason="requires POSIX process groups and lsof/ss port inspection",
)
def test_terminate_dashboard_listeners_kills_detached_dashboard(tmp_path):
    port = _free_port()
    env = os.environ.copy()
    env["CLOUDTAP_DB"] = str(tmp_path / "leak-test.sqlite3")
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "claude_tap",
            "dashboard",
            "--tap-live-port",
            str(port),
            "--tap-no-open",
            "--tap-output-dir",
            str(tmp_path),
        ],
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    try:
        deadline = time.monotonic() + 20
        listening = False
        while time.monotonic() < deadline:
            if dashboard_listener_pids(port):
                listening = True
                break
            assert proc.poll() is None, "dashboard subprocess exited before listening"
            time.sleep(0.1)
        assert listening, f"dashboard never started listening on port {port}"

        leftover = terminate_dashboard_listeners(port)
        assert leftover == []
        assert dashboard_listener_pids(port) == []
        proc.wait(timeout=10)
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=10)


@pytest.mark.skipif(
    sys.platform == "win32" or not _HAS_PORT_INSPECTOR,
    reason="requires POSIX process groups and lsof/ss port inspection",
)
def test_terminate_dashboard_listeners_ignores_unrelated_listener():
    """A non-dashboard process bound to the port must never be killed."""
    script = (
        "import socket, sys, time\n"
        "sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)\n"
        "sock.bind(('127.0.0.1', 0))\n"
        "sock.listen(1)\n"
        "print(sock.getsockname()[1], flush=True)\n"
        "time.sleep(60)\n"
    )
    proc = subprocess.Popen(
        [sys.executable, "-c", script],
        stdout=subprocess.PIPE,
        text=True,
    )
    try:
        port = int(proc.stdout.readline().strip())
        assert dashboard_listener_pids(port) == []
        assert terminate_dashboard_listeners(port, timeout_seconds=1.0) == []
        # The unrelated listener survived and still accepts connections.
        assert proc.poll() is None
        with socket.create_connection(("127.0.0.1", port), timeout=2.0):
            pass
    finally:
        proc.kill()
        proc.wait(timeout=10)
