# Trace Analysis Lab

Captured LLM API traffic (via claude-tap) from Codex CLI and Claude Code sessions,
plus the exploration pages built on top of those captures. This is maintainer
research material, kept under `.agents/` per the repository documentation boundary.

## How to view

The pages load trace JSON by relative path, so serve this directory directly:

```bash
cd .agents/lab
python3 -m http.server 8090
# open http://localhost:8090/trace_viewer.html
```

## Captures (`trace_*.json`)

Each experiment was run against both agents where a pair exists
(`*_claude.json` = Claude Code, `*_codex.json` = Codex CLI).

| Experiment | Files | What was captured |
|---|---|---|
| Baseline session | `trace_claude.json` / `trace_codex.json` | Full coding session, side-by-side skeleton comparison |
| Minimal prompt | `trace_hi_*.json` | A bare "hi" turn — smallest possible request anatomy |
| Node.js task | `trace_node_*.json` | Same small coding task in both agents |
| Fable 5 Node.js | `trace_f5_nodejs.json` | Claude Fable 5 running the Node.js task (used by `workflow-anatomy.html`) |
| Image generation | `trace_image_*.json` | Image-gen flows; outputs saved as `claude_apple.png` / `codex_apple.png` |
| Context compaction | `trace_compact_*.json` | How each agent compacts a long conversation |
| Thinking toggle | `trace_thinking_on.json` / `trace_thinking_off.json` | Same task with extended thinking on vs off |
| Subagent fan-out | `trace_subagent_codex.json` | Codex spawning subagents |
| Webpage replication | `trace_webpage_*.json` | Both agents replicating the reference page in `altai-page/` |

Supporting data:

- `scratch_data.json` — prompt-history dataset (`CATORDER` / `AGENTS`) backing `agent-prompt-history.html`
- `codex_probe.txt` — probe artifact written by Codex during an experiment

## Exploration pages

- `trace_viewer.html` — 抓包实验台: browse any capture by lab/variant, Codex vs Claude Code
- `compare.html` — webpage-replication verdict: 第一性原理 page, Codex vs Claude Code
- `explainers.html` — 图解: context / attention / compaction
- `llm-explainer.html` — interactive explainer: how an LLM reads and answers a prompt
- `tooluse-lab.html` — Tool Use 实验台: one question, seven tool calls
- `workflow-anatomy.html` — anatomy of one workflow run (reads `trace_f5_nodejs.json`)
- `workflow-patterns.html` — 图解: workflow shape atlas
- `agent-prompt-history.html` — system-prompt evolution across AI agents (data: `scratch_data.json`)
- `codex-prompt-evolution.html` / `codex-prompt-evolution-cobalt.html` / `codex-prompt-timeline.html` — Codex CLI system-prompt evolution, three presentation styles

## Webpage-replication experiment

- `altai-page/` — original reference page (includes `PROMPTS.md` used to drive the runs)
- `cmp_claude/` / `cmp_codex/` — what each agent produced; judged in `compare.html`

## mini-agent

`mini-agent/` — a ~100-line hand-rolled coding agent (system prompt + 3 tools + a
while loop) used as a teaching demo. It prints every request/response to
`mini-agent/traces/<timestamp>/`. Secrets are excluded from this copy: the
`.api.key` file is not committed and the token in its README is redacted —
provide your own key via `MINI_AGENT_API_KEY` to run it.
