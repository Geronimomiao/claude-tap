#!/usr/bin/env python3
"""Unit tests for the viewer's incremental detail-render plan.

Replicates the pure decision logic of detailRenderPlan() from
claude_tap/viewer_assets/lazy_loading.js (two-layer JS-in-HTML testing:
this file is the fast algorithm layer, tests/test_detail_defer_browser.py
is the browser DOM layer). Constants are parsed from the JS source so the
replica cannot silently drift from the shipped thresholds.
"""

from __future__ import annotations

import re
from pathlib import Path

LAZY_LOADING_JS = Path(__file__).parent.parent / "claude_tap" / "viewer_assets" / "lazy_loading.js"


def _js_int_constant(source: str, name: str) -> int:
    match = re.search(rf"^const {name} = ([0-9][0-9\s*]*);", source, flags=re.MULTILINE)
    assert match, f"constant {name} not found in lazy_loading.js"
    value = 1
    for factor in match.group(1).split("*"):
        value *= int(factor.strip())
    return value


def _constants() -> tuple[int, int, int]:
    source = LAZY_LOADING_JS.read_text(encoding="utf-8")
    return (
        _js_int_constant(source, "DETAIL_DEFER_MSG_THRESHOLD"),
        _js_int_constant(source, "DETAIL_EAGER_MSG_HEAD"),
        _js_int_constant(source, "DETAIL_DEFER_JSON_BYTES"),
    )


def detail_render_plan(msg_count: int, json_bytes: int, threshold: int, eager_head: int, json_min: int) -> dict:
    """Python replica of detailRenderPlan() in lazy_loading.js."""
    defer_messages = msg_count > threshold
    defer_sections = defer_messages or json_bytes > json_min
    return {
        "defer_messages": defer_messages,
        "eager_msg_head": eager_head if defer_messages else msg_count,
        "defer_sections": defer_sections,
    }


def test_constants_are_coherent():
    threshold, eager_head, json_min = _constants()
    assert 0 < eager_head < threshold
    assert json_min > 4096


def test_turn_at_threshold_renders_fully_eager():
    threshold, eager_head, json_min = _constants()
    plan = detail_render_plan(threshold, 1024, threshold, eager_head, json_min)
    assert plan == {"defer_messages": False, "eager_msg_head": threshold, "defer_sections": False}


def test_turn_above_threshold_defers_message_tail():
    threshold, eager_head, json_min = _constants()
    plan = detail_render_plan(threshold + 1, 1024, threshold, eager_head, json_min)
    assert plan["defer_messages"] is True
    assert plan["eager_msg_head"] == eager_head
    assert plan["defer_sections"] is True
    deferred = (threshold + 1) - plan["eager_msg_head"]
    assert deferred == threshold + 1 - eager_head


def test_large_json_defers_collapsed_sections_but_not_messages():
    threshold, eager_head, json_min = _constants()
    plan = detail_render_plan(3, json_min + 1, threshold, eager_head, json_min)
    assert plan["defer_messages"] is False
    assert plan["eager_msg_head"] == 3
    assert plan["defer_sections"] is True


def test_json_exactly_at_limit_keeps_sections_eager():
    threshold, eager_head, json_min = _constants()
    plan = detail_render_plan(0, json_min, threshold, eager_head, json_min)
    assert plan == {"defer_messages": False, "eager_msg_head": 0, "defer_sections": False}
