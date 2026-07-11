#!/usr/bin/env python3
"""Browser integration tests for incremental detail rendering.

Heavy turns (many messages / large payloads) must render only the head of
the message list eagerly, materialize deferred bodies as they scroll into
view, and build collapsed sections (Full JSON) on first open. Small turns
must render exactly as before. See tests/test_detail_defer_plan.py for the
fast algorithm layer of the same feature.
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

HEAVY_MSG_COUNT = 60
EAGER_HEAD = 20


def _heavy_messages() -> list[dict]:
    return [
        {"role": "user" if i % 2 == 0 else "assistant", "content": f"DEFER_M{i} lorem ipsum message body {i}"}
        for i in range(HEAVY_MSG_COUNT)
    ]


def _make_entry(turn: int, messages: list[dict]) -> dict:
    return {
        "timestamp": f"2026-07-11T10:00:{turn:02d}",
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
                "messages": messages,
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


def _big_payload_entry() -> dict:
    """Few messages but a payload above DETAIL_DEFER_JSON_BYTES."""
    entry = _make_entry(3, [{"role": "user", "content": f"big payload message {i}"} for i in range(5)])
    entry["request"]["body"]["tools"] = [
        {
            "name": "bulky_tool",
            "description": "bulk " * 60000,
            "input_schema": {"type": "object", "properties": {}},
        }
    ]
    return entry


TRACE_ENTRIES = [
    _make_entry(1, _heavy_messages()),
    _make_entry(2, [{"role": "user", "content": f"small turn message {i}"} for i in range(5)]),
    _big_payload_entry(),
]


def _build_test_html() -> str:
    from claude_tap.viewer import VIEWER_SCRIPT_ANCHOR, _read_viewer_template

    html = _read_viewer_template()
    records = [json.dumps(e) for e in TRACE_ENTRIES]
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
def browser_page(html_file):
    from playwright.sync_api import sync_playwright

    pw = sync_playwright().start()
    browser = pw.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1280, "height": 800})
    page.goto(f"file://{html_file}")
    page.wait_for_selector(".sidebar-item", timeout=5000)
    yield page
    browser.close()
    pw.stop()


def _select_entry(page, idx: int) -> None:
    page.evaluate(f"selectEntry({idx})")
    page.wait_for_selector("#detail .section", timeout=5000)


def test_heavy_turn_renders_eager_head_and_defers_tail(browser_page):
    page = browser_page
    # Select and snapshot in one JS task so the IntersectionObserver cannot
    # materialize near-viewport placeholders between the two steps.
    state = page.evaluate(
        """() => {
          selectEntry(0);
          return {
            deferred: document.querySelectorAll('#detail [data-deferred-msg]').length,
            eager: document.querySelectorAll('#detail .msg:not([data-deferred-msg])').length,
            hasHeadText: document.querySelector('#detail').innerHTML.includes('DEFER_M0 '),
            hasTailText: document.querySelector('#detail').innerHTML.includes('DEFER_M59 '),
          };
        }"""
    )
    assert state["deferred"] == HEAVY_MSG_COUNT - EAGER_HEAD
    assert state["eager"] == EAGER_HEAD
    assert state["hasHeadText"] is True
    assert state["hasTailText"] is False


def test_heavy_turn_materializes_deferred_bodies_on_scroll(browser_page):
    page = browser_page
    _select_entry(page, 0)
    page.evaluate(
        """async () => {
          let guard = 0;
          while (document.querySelector('[data-deferred-msg]') && guard++ < 200) {
            document.querySelector('[data-deferred-msg]').scrollIntoView();
            await new Promise(r => requestAnimationFrame(() => setTimeout(r, 20)));
          }
        }"""
    )
    page.wait_for_function("document.querySelectorAll('[data-deferred-msg]').length === 0", timeout=8000)
    state = page.evaluate(
        """() => ({
          hasTailText: document.querySelector('#detail').innerHTML.includes('DEFER_M59 '),
          msgCount: document.querySelectorAll('#detail .msg').length,
        })"""
    )
    assert state["hasTailText"] is True
    assert state["msgCount"] == HEAVY_MSG_COUNT


def test_heavy_turn_builds_json_tree_on_first_section_open(browser_page):
    page = browser_page
    _select_entry(page, 0)
    json_body = page.evaluate(
        """() => {
          const section = Array.from(document.querySelectorAll('#detail .section'))
            .find(el => el.querySelector('.title')?.textContent === t('section_json'));
          const body = section.querySelector('.section-body');
          return {deferred: !!body.dataset.deferredSection, treeLines: body.querySelectorAll('.jt-line').length};
        }"""
    )
    assert json_body["deferred"] is True
    assert json_body["treeLines"] == 0

    page.evaluate(
        """() => {
          const section = Array.from(document.querySelectorAll('#detail .section'))
            .find(el => el.querySelector('.title')?.textContent === t('section_json'));
          section.querySelector('.section-header').click();
        }"""
    )
    page.wait_for_selector("#detail .json-view .jt-line", timeout=5000)
    opened = page.evaluate(
        """() => {
          const section = Array.from(document.querySelectorAll('#detail .section'))
            .find(el => el.querySelector('.title')?.textContent === t('section_json'));
          const body = section.querySelector('.section-body');
          return {open: body.classList.contains('open'), rendered: body.dataset.deferredRendered === 'true'};
        }"""
    )
    assert opened == {"open": True, "rendered": True}


def test_heavy_turn_copy_button_resolves_full_json_without_opening(browser_page):
    page = browser_page
    _select_entry(page, 0)
    copied = page.evaluate(
        """() => {
          window.__copied = null;
          window.writeClipboardText = text => { window.__copied = text; return Promise.resolve(); };
          const section = Array.from(document.querySelectorAll('#detail .section'))
            .find(el => el.querySelector('.title')?.textContent === t('section_json'));
          section.querySelector('.copy-btn[data-copy-deferred]').click();
          return window.__copied;
        }"""
    )
    assert copied is not None
    assert json.loads(copied)["request_id"] == "req_1"


def test_global_search_materializes_deferred_bodies_before_highlighting(browser_page):
    page = browser_page
    _select_entry(page, 0)
    page.evaluate(
        """() => {
          openGlobalSearch();
          document.querySelector('#global-search-input').value = 'DEFER_M59';
          globalSearchState.query = 'DEFER_M59';
          recalcGlobalSearchMatches();
        }"""
    )
    page.wait_for_selector("#detail mark.global-search-hit", timeout=5000)
    state = page.evaluate(
        """() => ({
          marks: document.querySelectorAll('#detail mark.global-search-hit').length,
          deferred: document.querySelectorAll('#detail [data-deferred-msg]').length,
        })"""
    )
    page.evaluate("closeGlobalSearch()")
    assert state["marks"] >= 1
    assert state["deferred"] == 0


def test_big_payload_turn_defers_sections_and_message_layout(browser_page):
    page = browser_page
    state = page.evaluate(
        """() => {
          // Earlier tests may have left the Full JSON section open; renderDetail
          // legitimately re-opens (and materializes) remembered-open sections,
          // so close it in the DOM before switching entries.
          const jsonSection = Array.from(document.querySelectorAll('#detail .section'))
            .find(el => el.querySelector('.title')?.textContent === t('section_json'));
          const jsonBody = jsonSection?.querySelector('.section-body');
          if (jsonBody?.classList.contains('open')) jsonSection.querySelector('.section-header').click();
          Object.keys(sectionCollapseState).forEach(key => delete sectionCollapseState[key]);
          selectEntry(2);
          return {
            deferred: document.querySelectorAll('#detail [data-deferred-msg]').length,
            deferredSections: document.querySelectorAll('#detail [data-deferred-section]').length,
            msgCount: document.querySelectorAll('#detail .msg').length,
            layoutDeferredMsgs: document.querySelectorAll('#detail .msg[style*="content-visibility"]').length,
            jsonTreeLines: document.querySelectorAll('#detail .json-view .jt-line').length,
          };
        }"""
    )
    # All 5 messages render eagerly (below the message threshold) but skip
    # offscreen layout, and the collapsed Tools/Full JSON sections stay unbuilt.
    assert state["deferred"] == 0
    assert state["msgCount"] == 5
    assert state["layoutDeferredMsgs"] == 5
    assert state["deferredSections"] == 2
    assert state["jsonTreeLines"] == 0


def test_small_turn_renders_identically_eager(browser_page):
    page = browser_page
    _select_entry(page, 1)
    state = page.evaluate(
        """() => ({
          deferred: document.querySelectorAll('#detail [data-deferred-msg]').length,
          deferredSections: document.querySelectorAll('#detail [data-deferred-section]').length,
          msgCount: document.querySelectorAll('#detail .msg').length,
          jsonTreeLines: document.querySelectorAll('#detail .json-view .jt-line').length,
          layoutDeferredMsgs: document.querySelectorAll('#detail .msg[style*="content-visibility"]').length,
        })"""
    )
    assert state["deferred"] == 0
    assert state["deferredSections"] == 0
    assert state["msgCount"] == 5
    assert state["jsonTreeLines"] > 0
    assert state["layoutDeferredMsgs"] == 0
