"""Dashboard integration tests for #turn-<label> deep links.

The session-detail URL fragment must open the embedded viewer on the
addressed turn, follow later hash edits, and stay in sync when the user
selects turns inside the viewer frame.
"""

from datetime import datetime, timezone

import pytest

from claude_tap.live import LiveViewerServer
from claude_tap.trace_store import get_trace_store


def _record(turn: int) -> dict:
    return {
        "timestamp": f"2026-07-11T12:00:{turn:02d}+00:00",
        "request_id": f"req_hash_{turn}",
        "turn": turn,
        "duration_ms": 700,
        "capture": {"client": "claude", "proxy_mode": "reverse"},
        "request": {
            "method": "POST",
            "path": "/v1/messages",
            "headers": {"Host": "api.anthropic.com"},
            "body": {
                "model": "claude-opus-4-8",
                "system": "Turn hash contract system prompt.",
                "messages": [{"role": "user", "content": [{"type": "text", "text": f"HASH_TURN_{turn} prompt"}]}],
            },
        },
        "response": {
            "status": 200,
            "headers": {},
            "body": {
                "model": "claude-opus-4-8",
                "content": [{"type": "text", "text": f"Answer {turn}."}],
                "usage": {"input_tokens": 100 * turn, "output_tokens": 10},
            },
        },
    }


def _make_session(store) -> str:
    session_id = store.create_session(
        client="claude",
        proxy_mode="reverse",
        started_at=datetime(2026, 7, 11, 12, 0, 0, tzinfo=timezone.utc),
    )
    for turn in (1, 2, 3):
        store.append_record(session_id, _record(turn))
    store.finalize_session(session_id, {"api_calls": 3})
    return session_id


@pytest.mark.asyncio
async def test_turn_hash_round_trips_between_dashboard_and_viewer(trace_db) -> None:
    playwright = pytest.importorskip("playwright.async_api")
    session_id = _make_session(get_trace_store())

    server = LiveViewerServer(port=0, dashboard_mode=True)
    port = await server.start()
    try:
        async with playwright.async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            try:
                page = await browser.new_page(viewport={"width": 1440, "height": 1000})
                await page.goto(
                    f"http://127.0.0.1:{port}/dashboard/session/{session_id}#turn-3",
                    wait_until="domcontentloaded",
                )

                frame_element = await page.wait_for_selector("[data-viewer-frame]", timeout=8000)
                assert "#turn-3" in (await frame_element.get_attribute("src"))
                frame = await frame_element.content_frame()
                await frame.wait_for_selector(".sidebar-item.active", timeout=8000)
                await frame.wait_for_function("String(displayTurnLabel(filtered[activeIdx])) === '3'", timeout=8000)
                detail_text = await frame.evaluate("document.querySelector('#detail').innerText")
                assert "HASH_TURN_3" in detail_text

                # Selecting a turn inside the viewer updates the dashboard URL.
                await frame.evaluate("selectEntry(0)")
                await page.wait_for_function("window.location.hash === '#turn-1'", timeout=8000)

                # Editing the dashboard hash drives the viewer selection.
                await page.evaluate("window.location.hash = '#turn-2'")
                await frame.wait_for_function("String(displayTurnLabel(filtered[activeIdx])) === '2'", timeout=8000)
            finally:
                await browser.close()
    finally:
        await server.stop()
