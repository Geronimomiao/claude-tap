"""Unit contracts for the dashboard's pinned-session ordering."""

from __future__ import annotations

import re
import shutil
import subprocess
import textwrap
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]


def _extract_function(source: str, name: str) -> str:
    match = re.search(rf"function {name}\([^)]*\) \{{.*?\n\}}", source, re.DOTALL)
    assert match, f"{name} not found in dashboard.html"
    return match.group(0)


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js is required for dashboard JS unit tests")
def test_pinned_session_helpers_partition_and_reorder() -> None:
    dashboard_html = (REPO_ROOT / "claude_tap" / "dashboard.html").read_text(encoding="utf-8")
    functions = "\n".join(
        _extract_function(dashboard_html, name)
        for name in ("legacyPinnedSessionIds", "partitionSessions", "movePinnedSessionId")
    )

    script = (
        'const PINNED_SESSIONS_KEY = "claude-tap-pinned-sessions";\n'
        + functions
        + textwrap.dedent(
            r"""

        const assert = require('assert/strict');

        // partitionSessions keeps saved pin order and filters unknown ids.
        const sessions = [{id: 'a'}, {id: 'b'}, {id: 'c'}, {id: 'd'}];
        const {pinned, rest} = partitionSessions(sessions, ['c', 'zombie', 'a']);
        assert.deepEqual(pinned.map(s => s.id), ['c', 'a']);
        assert.deepEqual(rest.map(s => s.id), ['b', 'd']);

        // Unpinned list stays untouched when nothing is pinned.
        const none = partitionSessions(sessions, []);
        assert.deepEqual(none.pinned, []);
        assert.deepEqual(none.rest.map(s => s.id), ['a', 'b', 'c', 'd']);

        // movePinnedSessionId reorders within the list...
        assert.deepEqual(movePinnedSessionId(['a', 'b', 'c'], 'c', 0), ['c', 'a', 'b']);
        // ...accounts for the dragged item's own slot when moving down...
        assert.deepEqual(movePinnedSessionId(['a', 'b', 'c'], 'a', 2), ['b', 'a', 'c']);
        assert.deepEqual(movePinnedSessionId(['a', 'b', 'c'], 'a', 3), ['b', 'c', 'a']);
        // ...appends new ids and clamps out-of-range targets.
        assert.deepEqual(movePinnedSessionId(['a', 'b'], 'x', 99), ['a', 'b', 'x']);
        assert.deepEqual(movePinnedSessionId([], 'x', -5), ['x']);

        // legacyPinnedSessionIds tolerates garbage storage.
        global.localStorage = {getItem: () => '{"not":"an array"}'};
        assert.deepEqual(legacyPinnedSessionIds(), []);
        global.localStorage = {getItem: () => 'not json'};
        assert.deepEqual(legacyPinnedSessionIds(), []);
        global.localStorage = {getItem: () => '["a", 42, "b"]'};
        assert.deepEqual(legacyPinnedSessionIds(), ['a', 'b']);

        console.log('ok');
        """
        )
    )
    result = subprocess.run(
        ["node", "-e", script],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "ok"


def test_pinned_table_omits_time_column() -> None:
    dashboard_html = (REPO_ROOT / "claude_tap" / "dashboard.html").read_text(encoding="utf-8")
    pinned_panel = dashboard_html.split('id="pinned-panel"')[1].split("</table>")[0]
    assert "table_first_message" in pinned_panel
    assert "table_start_time" not in pinned_panel
    inbox_table = dashboard_html.split('id="pinned-panel"')[1].split("</table>")[1]
    assert "table_start_time" in inbox_table


def test_dashboard_pref_roundtrip(trace_db) -> None:
    from claude_tap.trace_store import get_trace_store

    store = get_trace_store()
    assert store.get_dashboard_pref("pinned_sessions") is None
    store.set_dashboard_pref("pinned_sessions", '["a", "b"]')
    assert store.get_dashboard_pref("pinned_sessions") == '["a", "b"]'
    store.set_dashboard_pref("pinned_sessions", '["b"]')
    assert store.get_dashboard_pref("pinned_sessions") == '["b"]'


@pytest.mark.asyncio
async def test_pinned_sessions_api_roundtrip(trace_db) -> None:
    import aiohttp

    from claude_tap.live import LiveViewerServer

    server = LiveViewerServer(port=0)
    port = await server.start()
    url = f"http://127.0.0.1:{port}/api/dashboard/prefs/pinned-sessions"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                assert resp.status == 200
                assert (await resp.json()) == {"session_ids": []}
            async with session.put(url, json={"session_ids": ["s2", "s1", "s2"]}) as resp:
                assert resp.status == 200
                assert (await resp.json()) == {"session_ids": ["s2", "s1"]}
            async with session.get(url) as resp:
                assert (await resp.json()) == {"session_ids": ["s2", "s1"]}
            async with session.put(url, json={"session_ids": "nope"}) as resp:
                assert resp.status == 400
            async with session.put(url, data="not json") as resp:
                assert resp.status == 400
            async with session.get(url) as resp:
                assert (await resp.json()) == {"session_ids": ["s2", "s1"]}
    finally:
        await server.stop()
