# mini-agent：手搓一个 100 行的编码 Agent（分享 Demo）

证明一件事：**agent 的骨架 = System Prompt + 3 个工具 + 一个 while 循环**。
产品化的全部难度都在七层里——代码里每一层的位置都用 `── 第 4.x 层` 注释标出来了。

## 运行

```bash
export MINI_AGENT_API_KEY=sk-...   # 从 console.anthropic.com 生成，按量计费
cd mini-agent
node mini-agent.ts --workspace demo_repo "node test_calc.ts 报错了，找到原因修好它"
```

TypeScript 免编译直跑（Node >= 23.6；本机 24.x ✅），零第三方依赖。
可选环境变量：`MINI_AGENT_MODEL`（默认 claude-sonnet-5）、`MINI_AGENT_BASE_URL`。

> **为什么用专用变量 `MINI_AGENT_API_KEY`**：Claude Code 走 claude.ai 账号 OAuth（订阅计费），
> 但它会检测环境里的 `ANTHROPIC_API_KEY` 并询问是否改用它（按量计费）。用专用变量零碰撞；
> 一次性运行也可以行内传参：`MINI_AGENT_API_KEY=sk-... node mini-agent.ts ...`，不污染任何环境。
> （兼容：没设专用变量时也会读 `ANTHROPIC_API_KEY`。）

demo_repo 里 `calculator.ts` 的 `average()` 对空数组会抛 `Reduce of empty array with no initial value`（预埋 bug）。
预期行为：读测试 → 读源码 → edit_file 修复 → run_shell 跑测试验证 → 总结，约 4~6 轮。
**演示完记得把 bug 改回去**（把 `average` 恢复成一行 `return nums.reduce((a, b) => a + b) / nums.length;`）。

## 报文自打印（本工具的核心卖点）

每轮请求/响应原样落盘 `traces/<时间戳>/turn_NN_{request,response}.json`，终端只打摘要
（请求体积 KB、消息条数、token 用量、工具调用）。

把 `turn_01_request.json` 和 claude-tap 抓到的 Claude Code / Codex 首包并排开，逐项 diff：

| 对比点 | 手搓 agent | SOTA agent | 对应层 |
| --- | --- | --- | --- |
| system 字段 | 8 行 | 数千行行为规范 | 4.1 |
| tools 数组 | 3 个 | 十几个 + 详细描述 | 4.2 |
| 消息史 | 用户原文，只增不减 | reminder 注入、压缩痕迹、cache_control | 4.3 |
| 请求拓扑 | 单循环单线程 | subAgent 请求树 | 4.4 |
| 环境/权限 | 无 | 环境信息块、沙箱反馈 | 4.5 |
| 采样参数 | 全默认 | thinking / effort 档位 | 4.6 |
| 用户消息包装 | 裸发 | 模板 + XML 标签 + 引用展开 | 4.7 |

想让代理式抓包工具也能抓到它（Node 24 起）：

```bash
NODE_USE_ENV_PROXY=1 HTTPS_PROXY=http://127.0.0.1:8888 NODE_EXTRA_CA_CERTS=/path/to/mitm-ca.pem \
  node mini-agent.ts --workspace demo_repo "..."
```

或者直接把 `MINI_AGENT_BASE_URL` 指向抓包工具的反向代理。

## 用第三方模型跑（无需 Anthropic Console 账号）

DeepSeek / Kimi 等都提供 Anthropic 兼容端点（本来就是为接入 Claude Code 做的），mini-agent 改两个环境变量直接用：

```bash
# DeepSeek（platform.deepseek.com 注册充值）
MINI_AGENT_API_KEY=sk-你的DeepSeek密钥 \
MINI_AGENT_BASE_URL=https://api.deepseek.com/anthropic \
MINI_AGENT_MODEL=deepseek-v4-pro \
node mini-agent.ts --workspace demo_repo "node test_calc.ts 报错了，找到原因修好它"

# Kimi / Moonshot（platform.moonshot.cn，海外域名 api.moonshot.ai）
MINI_AGENT_API_KEY=sk-你的Moonshot密钥 \
MINI_AGENT_BASE_URL=https://api.moonshot.cn/anthropic \
MINI_AGENT_MODEL=kimi-k2.5 \
node mini-agent.ts --workspace demo_repo "..."
```

> 演示彩蛋：同一个 mini-agent 只换模型 = **「同 harness × 不同模型」的对偶实验**——观察不同模型
> 对同一套工具格式的驾驭差异（编辑重试率、是否主动验证、话痨程度），正好和主线「同模型 × 不同 agent」互补。

## 常见坑（实战踩过，听众必踩）

1. **订阅 token ≠ API Key**：`claude setup-token` / 登录流程给的是 `sk-ant-oat01-REDACTED` 开头的 Claude Code OAuth token，
   挂在订阅上、只供 Claude Code 产品用，打 `/v1/messages` + `x-api-key` 会得到干净的
   `401 authentication_error: invalid x-api-key`。手搓 agent 要的是 console.anthropic.com 生成的 `sk-ant-api03-` Key（按量计费）。
2. **key 折行**：复制粘贴常带换行，HTTP header 不允许换行——不处理的话 undici 直接抛
   `invalid header value`，而且**报错会把 token 原样打出来**（泄露进日志）。本工具已在代码层剥掉 key 的全部空白。
3. **秘密进了日志就轮换**：报错、trace、聊天记录里出现过的 token 一律视为泄露，重新生成。

## 现场演示变体（每个变体证明一层）

1. **删 System Prompt 第 2 条**（"必须验证"）再跑：它改完就交差、不跑测试 → 4.1 行为是提示词调出来的
2. **连续派 3 个任务不清历史**：看请求体积和 input tokens 一轮轮涨 → 4.3 为什么需要压缩
3. **让它删文件**：它不会问你一句 → 4.5 权限层的缺失
4. **edit_file 故意给不唯一的 old_string**：观察它怎么重试 → 4.2 编辑格式的失败模式
