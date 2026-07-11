# claude-tap

[中文说明](README_zh.md)

Personal fork of [liaohch3/claude-tap](https://github.com/liaohch3/claude-tap) — a local proxy and trace viewer for AI coding agents — with some light modifications on top of the original project.

For full documentation, see the [upstream README](https://github.com/liaohch3/claude-tap#readme).

## Capturing Codex CLI (opt-in per run)

Codex capture is enabled per invocation, not globally. Nothing is written to
`~/.codex/config.toml`, so the desktop Codex App and ordinary `codex` runs go
straight to OpenAI and are never routed through the proxy.

Recommended — let claude-tap manage the proxy for a single run:

```bash
claude-tap --tap-client codex -- exec "your prompt"
```

Alternative — point one run at an already-running reverse proxy:

```bash
# start a standing proxy once (proxy only, no client launch)
claude-tap --tap-client codex --tap-port 19529 --tap-no-launch --tap-no-live
# then capture individual runs with a per-run -c override
codex exec -c openai_base_url="http://127.0.0.1:19529/v1" "your prompt"
```

Notes (verified on Codex CLI 0.144.1):

- Codex reads `openai_base_url` from `config.toml` or a `-c` flag; it does **not**
  read the `OPENAI_BASE_URL` environment variable, so an env var alone will not
  route a run through the proxy.
- Codex's main transport is a WebSocket (`wss://.../v1/responses`). It honors
  `HTTPS_PROXY`/`ALL_PROXY` (forward mode) across all of its HTTP clients, and it
  trusts CAs from the macOS keychain (rustls-native-certs), so
  `--tap-proxy-mode forward --tap-trust-ca` also works if you prefer a transparent
  proxy over a base-URL override.
