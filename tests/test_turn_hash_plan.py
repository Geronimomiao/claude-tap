#!/usr/bin/env python3
"""Unit tests for #turn-<label> deep-link parsing and matching.

Replicates the pure logic of turnHashLabel() / findEntryIdxByTurnLabel()
from claude_tap/viewer_assets/utilities_mobile.js (two-layer JS-in-HTML
testing: tests/test_turn_hash_browser.py is the browser DOM layer). Also
keeps the viewer and dashboard hash formats from drifting apart.
"""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import unquote

ASSETS = Path(__file__).parent.parent / "claude_tap" / "viewer_assets"
DASHBOARD_HTML = Path(__file__).parent.parent / "claude_tap" / "dashboard.html"

TURN_HASH_RE = re.compile(r"^#turn-(.+)$")


def turn_hash_label(hash_value: str) -> str:
    """Python replica of turnHashLabel() in utilities_mobile.js."""
    match = TURN_HASH_RE.match(str(hash_value or ""))
    if not match:
        return ""
    return unquote(match.group(1))


def _display_turn_label(entry: dict) -> str:
    """Python replica of displayTurnValue()/displayTurnLabel() in responses.js."""
    value = entry.get("display_turn", entry.get("turn"))
    return "?" if value in (None, "") else str(value)


def find_entry_idx_by_turn_label(entries: list[dict], label: str) -> int:
    """Python replica of findEntryIdxByTurnLabel() in utilities_mobile.js."""
    if not label:
        return -1
    for idx, entry in enumerate(entries):
        if _display_turn_label(entry) == str(label):
            return idx
    return -1


def test_turn_hash_label_parses_simple_and_dotted_labels():
    assert turn_hash_label("#turn-15") == "15"
    assert turn_hash_label("#turn-2.2") == "2.2"
    assert turn_hash_label("#turn-2%2E2") == "2.2"


def test_turn_hash_label_rejects_other_anchors():
    assert turn_hash_label("") == ""
    assert turn_hash_label("#turn-") == ""
    assert turn_hash_label("#compare-insights") == ""
    assert turn_hash_label("#diff-3") == ""


def test_matching_prefers_display_turn_over_capture_turn():
    entries = [
        {"turn": 7, "display_turn": 1},
        {"turn": 8, "display_turn": "2.2"},
        {"turn": 9},
    ]
    assert find_entry_idx_by_turn_label(entries, "1") == 0
    assert find_entry_idx_by_turn_label(entries, "2.2") == 1
    assert find_entry_idx_by_turn_label(entries, "9") == 2
    assert find_entry_idx_by_turn_label(entries, "7") == -1
    assert find_entry_idx_by_turn_label(entries, "") == -1


def test_viewer_and_dashboard_share_the_turn_hash_prefix():
    viewer_js = (ASSETS / "utilities_mobile.js").read_text(encoding="utf-8")
    dashboard = DASHBOARD_HTML.read_text(encoding="utf-8")
    assert "/^#turn-(.+)$/" in viewer_js
    assert "'#turn-' + encodeURIComponent" in viewer_js
    assert "claude-tap:turn-hash" in viewer_js
    assert "claude-tap:turn-hash" in dashboard
    assert "TURN_HASH_PATTERN" in dashboard
    assert "^#turn-" in dashboard
