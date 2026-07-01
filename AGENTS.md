# Agent 操作说明

本项目是 FundVal-Live 的本地基金数据框架。它负责导入支付宝持仓截图识别结果、保存历史、刷新养基宝/FundVal 估值、展示本地看板、导出 AI 可读 JSON。投资复盘、风险提示、截图 OCR、是否买卖的讨论由 Claude Code / AutoClaw / Codex / QwenPaw 等外部 AI 工具完成。

## 先读

- 普通部署说明：`README.md`
- AI 接管流程：`AI_TOOL_USAGE.md`
- 支付宝截图识别格式：`AI_SCREENSHOT_PROMPT.md`
- 国内远程访问方案：`REMOTE_ACCESS_CN.md`
- 支付宝导入细节：`tools/README-alipay-import.md`
- 发布前检查：`RELEASE_CHECKLIST.md`

## 项目边界

- 支付宝截图只用于同步真实持仓、金额、份额、持有收益和成本基准。
- 不读取或引用支付宝截图里的昨日收益作为看板收益。
- 今日/昨日盈亏以 FundVal-Live 导出的 `pnl_summary.daily_pnl` 为准，估值优先来自养基宝/FundVal。
- 本仓库只记录和导出数据，不直接给确定性投资建议。
- 不要自己发明基金实时估值算法；先读取导出的结构化数据，再做解释。

## 本地启动

Windows PowerShell:

```powershell
copy .env.example .env
python .\tools\prepare_config.py
docker compose up -d
docker compose ps
```

macOS / Linux:

```bash
cp .env.example .env
python3 ./tools/prepare_config.py
docker compose up -d
docker compose ps
```

看板地址：

```text
http://localhost:21345/dashboard/positions
```

## AI 日常更新流程

1. 读取用户提供的支付宝基金持仓截图。
2. 严格按 `AI_SCREENSHOT_PROMPT.md` 输出 JSON。
3. 保存为 `imports/alipay_snapshot.json`。
4. 先 dry-run，向用户汇报将导入的基金数量、代码、金额和明显风险。
5. 用户确认后再正式写入。
6. 写入后读取 `exports/ai_portfolio_snapshot.json` 做复盘。

Windows dry-run:

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\quick_import.ps1 .\imports\alipay_snapshot.json -DryRun
```

Windows 正式每日更新：

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\daily_update.ps1 .\imports\alipay_snapshot.json
```

macOS / Linux dry-run:

```bash
bash ./tools/quick_import.sh ./imports/alipay_snapshot.json --dry-run
```

macOS / Linux 正式每日更新：

```bash
bash ./tools/daily_update.sh ./imports/alipay_snapshot.json
```

## 不截图时刷新估值

如果用户当天没有支付宝截图，但想看实时估值和今日盈亏，运行：

Windows:

```powershell
python .\tools\export_for_ai.py --out .\exports\ai_portfolio_snapshot.json
```

macOS / Linux:

```bash
python3 ./tools/export_for_ai.py --out ./exports/ai_portfolio_snapshot.json
```

然后读取：

```text
exports/ai_portfolio_snapshot.json
```

重点字段：

- `summary`
- `pnl_summary.daily_pnl`
- `positions`
- `analysis_notes`

## 每日收益归档

北京时间 `23:59` 固化当天养基宝/FundVal 估值口径收益，第二天作为昨日收益参考。

Windows:

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\archive_local_pnl.ps1
```

macOS / Linux:

```bash
bash ./tools/archive_local_pnl.sh
```

长期记录入口：

```text
history/local_pnl_series.jsonl
history/daily_index.jsonl
history/YYYY-MM-DD/
```

## 月度/阶段总结

Windows:

```powershell
python .\tools\summarize_history.py --days 30 --out .\exports\history_summary.json
```

macOS / Linux:

```bash
python3 ./tools/summarize_history.py --days 30 --out ./exports/history_summary.json
```

## 手机访问

默认 Docker 只绑定本机 `127.0.0.1`，别人和公网看不到。国内用户远程访问优先参考 `REMOTE_ACCESS_CN.md`。

推荐顺序：

- 长期稳定访问：云服务器部署，并加反向代理访问保护。
- 临时手机访问：cpolar / NATAPP 等国内内网穿透，并开启访问密码或白名单。
- 有 VPS 且懂运维：frp 自建穿透。
- Tailscale / Cloudflare Tunnel：只作为可选方案，不作为国内默认推荐。

宿主机 Tailscale Serve 示例：

```powershell
& 'C:\Program Files\Tailscale\tailscale.exe' up
& 'C:\Program Files\Tailscale\tailscale.exe' serve --bg 21345
& 'C:\Program Files\Tailscale\tailscale.exe' serve status
```

手机也登录同一个 Tailscale 账号后，访问 `serve status` 输出的 `https://*.ts.net/dashboard/positions` 地址。如果用户反馈登录慢、需要 VPN 或访问不稳定，改推荐 `REMOTE_ACCESS_CN.md` 里的云服务器、cpolar / NATAPP 或 frp 方案。

不要为了方便把 `docker-compose.yml` 改成裸露公网端口。

## 隐私和提交规则

不要提交这些本地私有文件或目录：

```text
.env
config/config.json
config/config.runtime.json
imports/
exports/
history/
work/
*.log
```

不要把 Tailscale auth key、养基宝 token、真实持仓截图、真实导出 JSON、真实历史收益提交到 Git。

## 给用户汇报时

- 先说明数据来源日期和估值来源。
- 明确是否已经 dry-run、是否已经正式导入。
- 如果分析持仓，只给风险提示、数据观察和可选思路，不给确定性买卖指令。
- 如果估值源不是全量养基宝/FundVal，必须提醒用户数据可能不完整。
