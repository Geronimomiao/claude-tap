"""Contracts for the /analyze trace-analysis lab routes."""

from __future__ import annotations

from pathlib import Path

import aiohttp
import pytest

from claude_tap.live import LiveViewerServer, resolve_analyze_lab_dir


@pytest.fixture
def lab_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    lab = tmp_path / "lab"
    lab.mkdir()
    (lab / "index.html").write_text("<title>lab index</title>", encoding="utf-8")
    (lab / "trace_demo.json").write_text('{"records": []}', encoding="utf-8")
    monkeypatch.setenv("CLOUDTAP_LAB_DIR", str(lab))
    return lab


def test_resolve_analyze_lab_dir_uses_env_override(lab_dir: Path) -> None:
    assert resolve_analyze_lab_dir() == lab_dir


def test_resolve_analyze_lab_dir_rejects_missing_override(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CLOUDTAP_LAB_DIR", str(tmp_path / "missing"))
    assert resolve_analyze_lab_dir() is None


@pytest.mark.asyncio
async def test_analyze_routes_serve_lab_pages(lab_dir: Path) -> None:
    server = LiveViewerServer(port=0)
    port = await server.start()
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"http://127.0.0.1:{port}/analyze", allow_redirects=False) as resp:
                assert resp.status == 302
                assert resp.headers["Location"] == "/analyze/index.html"
            async with session.get(f"http://127.0.0.1:{port}/analyze/index.html") as resp:
                assert resp.status == 200
                assert "lab index" in await resp.text()
            async with session.get(f"http://127.0.0.1:{port}/analyze/trace_demo.json") as resp:
                assert resp.status == 200
            async with session.get(f"http://127.0.0.1:{port}/analyze/%2e%2e/pyproject.toml") as resp:
                assert resp.status in (403, 404)
    finally:
        await server.stop()


@pytest.mark.asyncio
async def test_analyze_routes_absent_without_lab(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CLOUDTAP_LAB_DIR", str(tmp_path / "missing"))
    server = LiveViewerServer(port=0)
    port = await server.start()
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"http://127.0.0.1:{port}/analyze", allow_redirects=False) as resp:
                assert resp.status == 404
    finally:
        await server.stop()
