#!/usr/bin/env python3
"""Browser integration tests for #turn-<label> deep links in the viewer.

Opening a viewer URL with #turn-<label> must select that turn, changing the
hash at runtime must follow it, and selecting a turn must write the hash
back so the current URL is always a copyable deep link. See
tests/test_turn_hash_plan.py for the fast algorithm layer.
"""

import json
import tempfile
from pathlib import Path

import pytest

pw_missing = False
try:
    from playwright.sync_api import sync_playwright  # noqa: F401
except ImportError:
    pw_missing = True

pytestmark = pytest.mark.skipif(pw_missing, reason="playwright not installed")


def _make_entry(turn: int) -> dict:
    return {
        "timestamp": f"2026-07-11T11:00:{turn:02d}",
        "request_id": f"req_{turn}",
        "turn": turn,
        "duration_ms": 500,
        "request": {
            "method": "POST",
            "path": "/v1/messages",
            "headers": {},
            "body": {
                "model": "claude-opus-4-6",
                "system": [{"type": "text", "text": "You are Claude"}],
                "messages": [{"role": "user", "content": f"TURN_MARKER_{turn} message"}],
            },
        },
        "response": {
            "status": 200,
            "body": {
                "content": [{"type": "text", "text": f"Response for turn {turn}"}],
                "model": "claude-opus-4-6",
                "usage": {"input_tokens": turn * 10, "output_tokens": 5},
            },
        },
    }


def _build_test_html() -> str:
    from claude_tap.viewer import VIEWER_SCRIPT_ANCHOR, _read_viewer_template

    html = _read_viewer_template()
    records = [json.dumps(_make_entry(turn)) for turn in range(1, 5)]
    data_js = (
        "const EMBEDDED_TRACE_DATA = [\n" + ",\n".join(records) + "\n];\n"
        'const __TRACE_JSONL_PATH__ = "/tmp/test.jsonl";\n'
        'const __TRACE_HTML_PATH__ = "/tmp/test.html";\n'
    )
    return html.replace(
        VIEWER_SCRIPT_ANCHOR,
        f"<script>\n{data_js}</script>\n{VIEWER_SCRIPT_ANCHOR}",
        1,
    )


@pytest.fixture(scope="module")
def html_file():
    html = _build_test_html()
    with tempfile.NamedTemporaryFile(suffix=".html", delete=False, mode="w", encoding="utf-8") as f:
        f.write(html)
        return Path(f.name)


@pytest.fixture(scope="module")
def browser():
    from playwright.sync_api import sync_playwright

    pw = sync_playwright().start()
    chromium = pw.chromium.launch(headless=True)
    yield chromium
    chromium.close()
    pw.stop()


def _active_turn_label(page) -> str:
    return page.evaluate("String(displayTurnLabel(filtered[activeIdx]))")


def test_opening_with_turn_hash_selects_that_turn(browser, html_file):
    page = browser.new_page()
    try:
        page.goto(f"file://{html_file}#turn-3")
        page.wait_for_selector(".sidebar-item.active", timeout=5000)
        assert _active_turn_label(page) == "3"
        assert "TURN_MARKER_3" in page.evaluate("document.querySelector('#detail').innerText")
    finally:
        page.close()


def test_hash_change_at_runtime_switches_turns(browser, html_file):
    page = browser.new_page()
    try:
        page.goto(f"file://{html_file}#turn-3")
        page.wait_for_selector(".sidebar-item.active", timeout=5000)
        page.evaluate("window.location.hash = '#turn-2'")
        page.wait_for_function("String(displayTurnLabel(filtered[activeIdx])) === '2'", timeout=5000)
    finally:
        page.close()


def test_selecting_a_turn_writes_the_hash_back(browser, html_file):
    page = browser.new_page()
    try:
        page.goto(f"file://{html_file}")
        page.wait_for_selector(".sidebar-item.active", timeout=5000)
        page.evaluate("selectEntry(3)")
        page.wait_for_function("window.location.hash === '#turn-4'", timeout=5000)
        # No history spam: hash updates use replaceState, so going back leaves the page.
        assert page.evaluate("window.location.hash") == "#turn-4"
    finally:
        page.close()


def test_invalid_turn_hash_keeps_default_selection(browser, html_file):
    page = browser.new_page()
    try:
        page.goto(f"file://{html_file}#turn-999")
        page.wait_for_selector(".sidebar-item.active", timeout=5000)
        # The deep link does not match any turn: default selection stays.
        assert _active_turn_label(page) == "1"
    finally:
        page.close()
