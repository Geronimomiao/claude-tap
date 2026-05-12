# PR 159 Real CLI Screenshot Evidence

These screenshots were captured from real `claude-tap` trace viewer HTML files generated during authenticated third-party CLI validation on 2026-05-12 UTC.

The images cover:

- Codex first turn and resumed second turn.
- Kimi first turn and continued second turn.
- Gemini first turn and `--resume latest` second turn.
- opencode continued second turn plus a fresh warm-cache first turn.

Each client screenshot set includes an overview plus manually scrolled detail-panel positions that show user prompts, tool execution evidence, response details, or service traffic after continued interaction.

## Source Traces

| Client | First turn trace | Continued turn trace |
| --- | --- | --- |
| Codex | `.traces/real-validation/2026-05-12/trace_083558.html` | `.traces/real-validation/2026-05-12/trace_085133.html` |
| Kimi | `.traces/real-validation/2026-05-12/trace_083635.html` | `.traces/real-validation/2026-05-12/trace_085230.html` |
| Gemini | `.traces/real-validation/2026-05-12/trace_090747.html` | `.traces/real-validation/2026-05-12/trace_090829.html` |
| opencode | `.traces/real-validation/2026-05-12/trace_083734.html` | `.traces/real-validation/2026-05-12/trace_085255.html` |

The original opencode first-turn trace is intentionally not screenshotted here because it is dominated by npm registry bootstrap traffic. The measured trace size is 65.94 MiB, of which 65.57 MiB comes from `registry.npmjs.org` package metadata and tarballs; the warmed continued trace still captures real `opencode.ai` traffic and is small enough for practical PR review.

A fresh warm-cache opencode run was captured afterward at `.traces/real-validation/2026-05-12/trace_092804.html`. It is 2.3 MiB, captures 4 requests total, includes 3 successful `opencode.ai /zen/v1/chat/completions` POSTs, and backs the `opencode-warm-*` screenshots.

## Validation

```bash
uv run python scripts/check_screenshots.py .agents/evidence/pr/pr159
uv run python scripts/verify_screenshots.py \
  .traces/real-validation/2026-05-12/trace_083558.html \
  .traces/real-validation/2026-05-12/trace_083635.html \
  .traces/real-validation/2026-05-12/trace_085133.html \
  .traces/real-validation/2026-05-12/trace_085230.html \
  .traces/real-validation/2026-05-12/trace_085255.html \
  .traces/real-validation/2026-05-12/trace_090747.html \
  .traces/real-validation/2026-05-12/trace_090829.html \
  .traces/real-validation/2026-05-12/trace_092804.html
```
