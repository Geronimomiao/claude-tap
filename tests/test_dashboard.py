import json
from pathlib import Path

import aiohttp
import pytest

from claude_tap.dashboard import list_trace_agents, list_trace_sessions, load_trace_session
from claude_tap.live import LiveViewerServer
from claude_tap.trace import TraceWriter


def _write_jsonl(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(record, ensure_ascii=False, separators=(",", ":")) for record in records) + "\n",
        encoding="utf-8",
    )


def _anthropic_record(turn: int = 1) -> dict:
    return {
        "timestamp": "2026-05-20T08:00:00+00:00",
        "request_id": "req_claude",
        "turn": turn,
        "duration_ms": 1200,
        "capture": {"client": "claude", "proxy_mode": "reverse"},
        "request": {
            "method": "POST",
            "path": "/v1/messages",
            "headers": {"Host": "api.anthropic.com"},
            "body": {
                "model": "claude-sonnet-4-6",
                "messages": [{"role": "user", "content": "Explain this repository"}],
            },
        },
        "response": {
            "status": 200,
            "headers": {},
            "body": {
                "model": "claude-sonnet-4-6",
                "content": [{"type": "text", "text": "This is a trace viewer."}],
                "usage": {"input_tokens": 42, "output_tokens": 9},
            },
        },
    }


def _antigravity_record() -> dict:
    return {
        "timestamp": "2026-05-20T09:00:00+00:00",
        "request_id": "req_agy",
        "turn": 1,
        "duration_ms": 900,
        "request": {
            "method": "POST",
            "path": "/v1internal:streamGenerateContent?alt=sse",
            "headers": {"Host": "antigravity-unleash.goog"},
            "body": {
                "request": {
                    "contents": [{"role": "user", "parts": [{"text": "What model are you?"}]}],
                }
            },
        },
        "response": {
            "status": 200,
            "headers": {},
            "body": {
                "candidates": [{"content": {"parts": [{"text": "I am Sonnet."}]}}],
                "usageMetadata": {"promptTokenCount": 100, "candidatesTokenCount": 5},
            },
        },
    }


def test_dashboard_lists_sessions_across_agents(tmp_path: Path) -> None:
    claude_trace = tmp_path / "2026-05-20" / "trace_080000.jsonl"
    agy_trace = tmp_path / "2026-05-20" / "trace_090000.jsonl"
    _write_jsonl(claude_trace, [_anthropic_record()])
    _write_jsonl(agy_trace, [_antigravity_record()])

    sessions = list_trace_sessions(tmp_path)

    assert [session["agent"] for session in sessions] == ["Antigravity", "Claude Code"]
    assert sessions[0]["first_user"] == "What model are you?"
    assert sessions[0]["last_response"] == "I am Sonnet."
    assert sessions[1]["input_tokens"] == 42
    assert sessions[1]["output_tokens"] == 9

    agents = list_trace_agents(tmp_path)
    assert [(agent["label"], agent["sessions"]) for agent in agents] == [("Antigravity", 1), ("Claude Code", 1)]


def test_dashboard_loads_session_by_id(tmp_path: Path) -> None:
    trace_path = tmp_path / "2026-05-20" / "trace_080000.jsonl"
    _write_jsonl(trace_path, [_anthropic_record()])
    session_id = list_trace_sessions(tmp_path)[0]["id"]

    payload = load_trace_session(tmp_path, session_id)

    assert payload is not None
    assert payload["session"]["rel_trace_path"] == "2026-05-20/trace_080000.jsonl"
    assert payload["records"][0]["request_id"] == "req_claude"


@pytest.mark.asyncio
async def test_dashboard_server_serves_session_api_and_html(tmp_path: Path) -> None:
    trace_path = tmp_path / "2026-05-20" / "trace_080000.jsonl"
    html_path = trace_path.with_suffix(".html")
    _write_jsonl(trace_path, [_anthropic_record()])
    html_path.write_text("<!doctype html><title>trace</title>", encoding="utf-8")

    server = LiveViewerServer(tmp_path / "dashboard.jsonl", port=0, output_dir=tmp_path, dashboard_mode=True)
    port = await server.start()
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"http://127.0.0.1:{port}/") as resp:
                assert resp.status == 200
                html = await resp.text()
                assert "session-list" in html

            async with session.get(f"http://127.0.0.1:{port}/api/sessions") as resp:
                assert resp.status == 200
                payload = await resp.json()
                assert len(payload["sessions"]) == 1
                session_id = payload["sessions"][0]["id"]

            async with session.get(f"http://127.0.0.1:{port}/api/agents") as resp:
                assert resp.status == 200
                payload = await resp.json()
                assert payload["agents"][0]["label"] == "Claude Code"

            async with session.get(f"http://127.0.0.1:{port}/api/sessions/{session_id}/records") as resp:
                assert resp.status == 200
                payload = await resp.json()
                assert payload["records"][0]["request_id"] == "req_claude"

            async with session.get(f"http://127.0.0.1:{port}/api/sessions/{session_id}/html") as resp:
                assert resp.status == 200
                html = await resp.text()
                assert "<title>trace</title>" in html
    finally:
        await server.stop()


@pytest.mark.asyncio
async def test_trace_writer_adds_capture_metadata(tmp_path: Path) -> None:
    trace_path = tmp_path / "trace.jsonl"
    writer = TraceWriter(trace_path, metadata={"client": "codex", "proxy_mode": "forward"})
    try:
        await writer.write(_anthropic_record())
    finally:
        writer.close()

    record = json.loads(trace_path.read_text(encoding="utf-8"))
    assert record["capture"] == {"client": "claude", "proxy_mode": "reverse"}

    writer = TraceWriter(trace_path, metadata={"client": "codex", "proxy_mode": "forward"})
    try:
        await writer.write({"request": {"body": {}}, "response": {"body": {}}})
    finally:
        writer.close()

    records = [json.loads(line) for line in trace_path.read_text(encoding="utf-8").splitlines()]
    assert records[-1]["capture"] == {"client": "codex", "proxy_mode": "forward"}
