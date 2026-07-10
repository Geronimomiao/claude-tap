#!/usr/bin/env node
/**
 * mini-agent.ts — 一个刻意最小化的编码 Agent（核心逻辑约 100 行，零第三方依赖）。
 *
 * 分享用途：证明 agent 的骨架只是「System Prompt + 3 个工具 + 一个循环」。
 * 每轮请求/响应原样落盘到 traces/，供与 Codex / Claude Code 的抓包结果并排 diff。
 *
 * 用法（Node >= 23.6，24 更佳，TS 免编译直跑）:
 *   export MINI_AGENT_API_KEY=sk-...   # 专用变量，避免与 Claude Code 的 ANTHROPIC_API_KEY 检测打架（也兼容后者）
 *   node mini-agent.ts --workspace demo_repo "node test_calc.ts 报错了，找到原因修好它"
 *
 * 可选环境变量:
 *   MINI_AGENT_MODEL     默认 claude-sonnet-5
 *   MINI_AGENT_BASE_URL  默认 https://api.anthropic.com
 *   （想让代理式抓包工具抓到它：NODE_USE_ENV_PROXY=1 + HTTPS_PROXY + NODE_EXTRA_CA_CERTS）
 */
import { spawnSync } from "node:child_process";
import * as fs from "node:fs";
import * as path from "node:path";

// ── 第 4.1 层：System Prompt —— 出厂人设只有几行。
//    现场演示点：删掉第 2 条"必须验证"再跑一遍，观察它改完就交差、不再跑测试。
const SYSTEM_PROMPT = `你是一个编码助手，在用户指定的工作目录里用工具完成任务。
规则：
1. 不要臆想文件内容：改任何文件前，先 read_file 看真实内容。
2. 修改之后，必须用 run_shell 运行测试或复现命令验证，验证通过才算完成。
3. 完成后用最多三句话总结你做了什么、怎么验证的。`;

// ── 第 4.2 层：工具 —— 3 个就够了。edit_file 故意采用"精确字符串替换"，
//    和某家 SOTA agent 同款，失败模式（不唯一/不匹配）也同款，方便现场对比重试行为。
type ToolDef = { name: string; description: string; input_schema: object };
const TOOLS: ToolDef[] = [
  {
    name: "read_file",
    description: "读取工作目录里一个文本文件的全部内容",
    input_schema: { type: "object", properties: { path: { type: "string", description: "相对工作目录的路径" } }, required: ["path"] },
  },
  {
    name: "edit_file",
    description: "把文件中出现且仅出现一次的 old_string 精确替换为 new_string（含空白逐字符匹配）",
    input_schema: { type: "object", properties: { path: { type: "string" }, old_string: { type: "string" }, new_string: { type: "string" } }, required: ["path", "old_string", "new_string"] },
  },
  {
    name: "run_shell",
    description: "在工作目录里执行 shell 命令，返回 exit code / stdout / stderr（30 秒超时）",
    input_schema: { type: "object", properties: { command: { type: "string" } }, required: ["command"] },
  },
];

function safePath(workspace: string, p: string): string {
  const abs = path.resolve(workspace, p);
  const root = path.resolve(workspace);
  if (abs !== root && !abs.startsWith(root + path.sep)) throw new Error(`路径越界: ${p}`);
  return abs;
}

function runTool(name: string, args: any, workspace: string): string {
  try {
    if (name === "read_file") return fs.readFileSync(safePath(workspace, args.path), "utf8");
    if (name === "edit_file") {
      const p = safePath(workspace, args.path);
      const text = fs.readFileSync(p, "utf8");
      const n = text.split(args.old_string).length - 1;
      if (n !== 1) return `ERROR: old_string 出现了 ${n} 次（要求恰好 1 次），未做修改`;
      fs.writeFileSync(p, text.replace(args.old_string, args.new_string));
      return "OK: 已替换";
    }
    if (name === "run_shell") {
      // ── 第 4.5 层：权限/沙箱 —— 本 agent 没有这一层（裸奔），这正是演示点：
      //    它不会问你一句，rm 也照跑。生产级 agent 在这里有整套审批/沙箱。
      const r = spawnSync(args.command, { shell: true, cwd: workspace, encoding: "utf8", timeout: 30_000 });
      return `exit=${r.status ?? `signal:${r.signal}`}\nstdout:\n${r.stdout}\nstderr:\n${r.stderr}`;
    }
    return `ERROR: 未知工具 ${name}`;
  } catch (e: any) {
    // 工具报错也作为文本回给模型，让它自己想办法——这也是真实 agent 的做法
    return `ERROR: ${e?.message ?? e}`;
  }
}

// ── 报文自打印：每轮请求/响应原样落盘。拿 turn_01_request.json 和
//    claude-tap 抓到的 Claude Code / Codex 首包并排开，diff 点一目了然。
function dump(traceDir: string, turn: number, kind: string, obj: unknown): void {
  const name = `turn_${String(turn).padStart(2, "0")}_${kind}.json`;
  fs.writeFileSync(path.join(traceDir, name), JSON.stringify(obj, null, 2));
}

async function callApi(payload: object): Promise<any> {
  const base = process.env.MINI_AGENT_BASE_URL ?? "https://api.anthropic.com";
  const resp = await fetch(base + "/v1/messages", {
    method: "POST",
    headers: {
      "content-type": "application/json",
      // key 里不该有任何空白：顺手消化"复制粘贴带折行"这种最常见的事故
      "x-api-key": (process.env.MINI_AGENT_API_KEY ?? process.env.ANTHROPIC_API_KEY ?? "").replace(/\s+/g, ""),
      "anthropic-version": "2023-06-01",
    },
    body: JSON.stringify(payload),
  });
  if (!resp.ok) {
    console.error(`API 错误 ${resp.status}: ${(await resp.text()).slice(0, 500)}`);
    process.exit(1);
  }
  return resp.json();
}

// ── 参数解析（够用就行）
const argv = process.argv.slice(2);
let workspace = ".";
const rest: string[] = [];
for (let i = 0; i < argv.length; i++) {
  if (argv[i] === "--workspace") workspace = argv[++i];
  else rest.push(argv[i]);
}
const task = rest.join(" ").trim();
if (!task) {
  console.error('用法: node mini-agent.ts [--workspace 目录] "任务描述"');
  process.exit(1);
}

const pad = (n: number) => String(n).padStart(2, "0");
const d = new Date();
const stamp = `${pad(d.getMonth() + 1)}${pad(d.getDate())}_${pad(d.getHours())}${pad(d.getMinutes())}${pad(d.getSeconds())}`;
const traceDir = path.join(import.meta.dirname, "traces", stamp);
fs.mkdirSync(traceDir, { recursive: true });

// ── 第 4.7 层：输入组装 —— 用户原文直发，没有任何包装
const messages: any[] = [{ role: "user", content: task }];
const stats = { turns: 0, in: 0, out: 0, tools: 0 };

while (true) {
  // ── 第 4.4 层：控制流 —— 全部的"编排"就是这一个循环
  stats.turns++;
  const payload = {
    // ── 第 4.6 层：推理参数 —— 全用默认值，没有 thinking/effort 旋钮
    model: process.env.MINI_AGENT_MODEL ?? "claude-sonnet-5",
    max_tokens: 4096,
    system: SYSTEM_PROMPT,
    tools: TOOLS,
    // ── 第 4.3 层：上下文 —— 只增不减：没有压缩、没有缓存标记、没有 reminder 注入。
    //    连续多派几个任务，看 input tokens 怎么一轮轮涨上去（现场演示"为什么需要压缩"）。
    messages,
  };
  dump(traceDir, stats.turns, "request", payload);
  const sizeKb = Buffer.byteLength(JSON.stringify(payload)) / 1024;
  const resp = await callApi(payload);
  dump(traceDir, stats.turns, "response", resp);
  stats.in += resp.usage.input_tokens;
  stats.out += resp.usage.output_tokens;
  console.log(
    `—— 轮次 ${stats.turns}: 请求 ${sizeKb.toFixed(1)}KB / ${messages.length} 条消息, ` +
    `input=${resp.usage.input_tokens} output=${resp.usage.output_tokens} tokens`,
  );

  messages.push({ role: "assistant", content: resp.content });
  const toolResults: any[] = [];
  for (const block of resp.content) {
    if (block.type === "text" && block.text.trim()) {
      console.log("[模型] " + block.text.trim());
    } else if (block.type === "tool_use") {
      stats.tools++;
      console.log(`[工具] ${block.name} ${JSON.stringify(block.input).slice(0, 120)}`);
      const result = runTool(block.name, block.input, workspace);
      console.log("   ↳ " + result.slice(0, 200).replace(/\n/g, " ⏎ "));
      toolResults.push({ type: "tool_result", tool_use_id: block.id, content: result });
    }
  }
  if (toolResults.length === 0) break; // 模型不再调工具 = 任务结束
  messages.push({ role: "user", content: toolResults });
  if (stats.turns >= 20) {
    console.log("(达到 20 轮上限——'预算控制'在生产级 agent 里也属于第 4.4 层)");
    break;
  }
}

console.log(
  `\n完成: ${stats.turns} 轮, ${stats.tools} 次工具调用, input ${stats.in} / output ${stats.out} tokens`,
);
console.log(`报文已落盘: ${traceDir}/ —— 拿去和 Codex / Claude Code 的抓包并排 diff`);
