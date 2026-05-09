# Tool Search Viewer Evidence

Generated on 2026-05-09 from the real Codex Responses trace provided for this issue.

## Trace Source

- Source JSONL: `/tmp/codex-toolsearch-study/2026-05-09/trace_171258.jsonl`
- Regenerated local viewer: `.traces/tool-search-real/2026-05-09/trace_171258.html`
- Client path: `/v1/responses`
- Relevant events: `response.output_item.done` with `tool_search_call`, followed by request input `tool_search_output`

## Screenshots

- `tool-search-response.png` - response section renders `tool_search` with query and limit from the WebSocket `response.output_item.done` item.
- `tool-search-output-context.png` - following request context renders the `tool_search_output` result with returned namespace/tool names.

## Validation

```bash
uv run python scripts/check_screenshots.py .agents/evidence/pr/tool-search
uv run python scripts/verify_screenshots.py .traces/tool-search-real/2026-05-09/trace_171258.html
```
