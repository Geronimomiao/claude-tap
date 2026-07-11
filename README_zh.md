# claude-tap

[English](README.md)

本仓库是 [liaohch3/claude-tap](https://github.com/liaohch3/claude-tap)（AI 编程 agent 的本地代理和 trace 查看器）的个人 fork，只在原项目基础上做了一些简单的改造。

完整文档请见[上游中文 README](https://github.com/liaohch3/claude-tap/blob/main/README_zh.md)。

## 抓包 Codex CLI（按次开启）

Codex 抓包按单次命令开启，而非全局。不会往 `~/.codex/config.toml` 写任何东西，
因此桌面版 Codex App 和普通的 `codex` 运行都直连 OpenAI，不经过代理。

推荐 —— 让 claude-tap 为单次运行自动管理代理：

```bash
claude-tap --tap-client codex -- exec "你的提示词"
```

备选 —— 让某次运行指向一个已在跑的反向代理：

```bash
# 先起一个常驻代理（只起代理，不启动客户端）
claude-tap --tap-client codex --tap-port 19529 --tap-no-launch --tap-no-live
# 之后用按次的 -c 覆盖来抓单次运行
codex exec -c openai_base_url="http://127.0.0.1:19529/v1" "你的提示词"
```

说明（在 Codex CLI 0.144.1 上实测）：

- Codex 只从 `config.toml` 或 `-c` 参数读取 `openai_base_url`，**不读** `OPENAI_BASE_URL`
  环境变量，所以单靠 env 变量无法把某次运行导入代理。
- Codex 的主传输是 WebSocket（`wss://.../v1/responses`）。它的所有 HTTP 客户端都遵循
  `HTTPS_PROXY`/`ALL_PROXY`（正向模式），并信任 macOS 钥匙串里的 CA（rustls-native-certs），
  因此如果你更想要透明代理而非 base-URL 覆盖，`--tap-proxy-mode forward --tap-trust-ca` 同样可行。
