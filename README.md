# FundVal-Live 基金数据框架

这是一个面向单人本地使用的基金数据框架，基于 FundVal-Live Docker 镜像，加了本地免登录、养基宝优先估值、支付宝截图快照导入、每日历史归档和 AI 工具交接规范。

本项目只负责记录、归档、导入和导出结构化数据。截图识别、操控流程、读取数据、总结复盘、风险提示和可选操作思路，由 Claude Code / AutoClaw / Codex 等外部 AI 工具负责。

默认访问地址：

```text
http://localhost:21345/dashboard/positions
```

默认只绑定 `127.0.0.1`，同一台电脑能打开，局域网和公网默认打不开。除非你主动改 `docker-compose.yml` 的端口绑定或做公网反代，否则别人看不到你的看板。

## 最终工作流

1. 打开本地看板查看实时估值和持仓。
2. 每天从支付宝截图基金持仓页。
3. 把截图交给 Codex、Claude Code、AutoClaw 等 AI 工具。
4. AI 按 `AI_SCREENSHOT_PROMPT.md` 输出统一 JSON。
5. 运行一键导入脚本，把支付宝真实持仓金额同步到 FundVal-Live。
6. FundVal-Live 长期保存持仓快照，养基宝接口优先提供实时估值，并把结构化数据导出给 AI 工具读取。

## 初始化

前置条件：

- Docker Desktop，Windows 和 macOS 都用这个。
- Python 3，用于生成运行配置和导入支付宝截图 JSON。
- Git，可选，只在需要从 GitHub 克隆时使用。

克隆仓库：

```bash
git clone https://github.com/wangke531/fundval-ai-dashboard-toolkit.git
cd fundval-ai-dashboard-toolkit
```

复制环境变量：

Windows PowerShell:

```powershell
copy .env.example .env
```

macOS / Linux:

```bash
cp .env.example .env
```

编辑 `.env`，至少改掉：

```text
POSTGRES_PASSWORD=change_this_postgres_password
FUNDVAL_ADMIN_PASSWORD=change_this_admin_password
FUNDVAL_BOOTSTRAP_KEY=change_this_random_bootstrap_key
```

生成本地运行配置：

Windows PowerShell:

```powershell
python .\tools\prepare_config.py
```

macOS / Linux:

```bash
python3 ./tools/prepare_config.py
```

启动：

Windows PowerShell:

```powershell
docker compose up -d
```

macOS / Linux:

```bash
docker compose up -d
```

查看服务：

```bash
docker compose ps
```

打开：

```text
http://localhost:21345/dashboard/positions
```

## 持仓页收益日历口径

打开持仓页即可看到顶部的“收益日历口径”卡片：

```text
http://localhost:21345/dashboard/positions
```

它会自动读取 FundVal 当前持仓、最近支付宝截图快照，并优先刷新养基宝最近估值。支付宝截图只用于同步持仓、成本和持有收益基准；看板不读取支付宝显示的昨日收益。卡片按北京时间自然日和结算状态拆开：

- `当日收益`：北京时间自然日的养基宝/FundVal 估算收益，按当前持仓份额和养基宝估算涨跌计算；凌晨美股和白天 A 股都归入当天。
- `当前阶段`：`00:00-14:59` 为穿透中，`15:00-23:59` 为结算中，期间都跟随养基宝实时变化。
- `持仓快照`：最近一次支付宝截图日期，只表示持仓同步时间，不表示收益来源。
- `当前持仓`：当前市值、持有收益、估值后收益。

如果当天不想截图支付宝，也可以只刷新估值和 AI 导出，不改支付宝持仓快照：

Windows PowerShell:

```powershell
python .\tools\export_for_ai.py --out .\exports\ai_portfolio_snapshot.json
```

macOS / Linux:

```bash
python3 ./tools/export_for_ai.py --out ./exports/ai_portfolio_snapshot.json
```

这个命令会刷新养基宝估值，并把看板同口径数据写入结构化导出：

```text
exports/ai_portfolio_snapshot.json
```

持仓页顶部卡片会显示市场阶段、净值日期分布、估值源、收益变化记录和主要贡献/拖累。北京时间 `23:59` 归档当日收益，第二天看板会把这条记录作为昨日收益参考。

手动归档当前养基宝收益：

Windows PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\archive_local_pnl.ps1
```

macOS / Linux:

```bash
bash ./tools/archive_local_pnl.sh
```

如果要自动化，在 Windows 任务计划程序里把这个 PowerShell 命令设为每天 `23:59` 执行即可。

页面中 FundVal 原生“收益趋势”图画的是账户市值/成本趋势，不是本项目计算的每日收益。每日收益记录看顶部卡片的“收益变化记录”，并保存到：

```text
history/local_pnl_series.jsonl
```

如果某天没有养基宝/净值历史快照，就不会强行显示该日收益。比如只有 2026-06-30 的持仓快照时，2026-06-29 不会用支付宝截图里的收益数字补算。

## 日常导入支付宝截图

让 AI 根据 `AI_SCREENSHOT_PROMPT.md` 把截图转成 JSON，保存为：

```text
imports/alipay_snapshot.json
```

试算，不写入：

Windows PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\quick_import.ps1 .\imports\alipay_snapshot.json -DryRun
```

macOS / Linux:

```bash
bash ./tools/quick_import.sh ./imports/alipay_snapshot.json --dry-run
```

正式写入：

Windows PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\quick_import.ps1 .\imports\alipay_snapshot.json
```

macOS / Linux:

```bash
bash ./tools/quick_import.sh ./imports/alipay_snapshot.json
```

如果你想保留每天的历史记录，推荐用每日更新脚本代替上面的正式写入：

Windows PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\daily_update.ps1 .\imports\alipay_snapshot.json
```

macOS / Linux:

```bash
bash ./tools/daily_update.sh ./imports/alipay_snapshot.json
```

每日更新会同时生成：

```text
exports/ai_portfolio_snapshot.json
history/YYYY-MM-DD/
history/daily_index.jsonl
```

一个月或两个月总结：

Windows PowerShell:

```powershell
python .\tools\summarize_history.py --days 30 --out .\exports\history_summary.json
```

macOS / Linux:

```bash
python3 ./tools/summarize_history.py --days 30 --out ./exports/history_summary.json
```

## 给 AI 工具的交接话术

可以把下面这段直接发给 Codex、Claude Code、AutoClaw：

Windows:

```text
请读取我发的支付宝基金持仓截图，严格按照当前项目根目录 AI_SCREENSHOT_PROMPT.md 的格式输出 JSON。
把结果保存为 imports/alipay_snapshot.json。
保存后先运行：
powershell -ExecutionPolicy Bypass -File .\tools\quick_import.ps1 .\imports\alipay_snapshot.json -DryRun
确认没有报错后，再询问我是否正式导入。
```

macOS / Linux:

```text
请读取我发的支付宝基金持仓截图，严格按照当前项目根目录 AI_SCREENSHOT_PROMPT.md 的格式输出 JSON。
把结果保存为 imports/alipay_snapshot.json。
保存后先运行：
bash ./tools/quick_import.sh ./imports/alipay_snapshot.json --dry-run
确认没有报错后，再询问我是否正式导入。
```

公开样例见：

```text
examples/sample-alipay/
```

更完整的 Claude Code / AutoClaw / Codex 操作流程见：

```text
AI_TOOL_USAGE.md
```

默认行为：

- `--replace`：用本次支付宝快照替换这些基金在当前账户下已有的合成操作。
- `--update-nav`：导入前刷新基金净值。
- `--update-estimate --estimate-source yangjibao`：导入后优先刷新养基宝实时估值。
- 输出报告默认写到 `imports/last_import_report.json`。

## 养基宝数据源

看板优先使用养基宝估值。某只基金养基宝暂时没有数据时，会临时兜底到其它数据源；下次刷新仍会继续重试养基宝。页面右下角会显示估值源统计。

如果要检查养基宝登录状态：

Windows PowerShell:

```powershell
Invoke-RestMethod "http://localhost:21345/api/source-credentials/status/?source_name=yangjibao"
```

macOS / Linux:

```bash
curl "http://localhost:21345/api/source-credentials/status/?source_name=yangjibao"
```

## 重要边界

这个工具同步的是“支付宝当前持仓快照”，不是还原真实历史买卖流水。支付宝截图通常只有当前市值、累计收益、份额等信息，所以导入脚本会合成一条建仓操作，让看板金额和支付宝对齐。

AI 的职责是识别截图、生成标准 JSON、调用本项目脚本、读取导出的结构化数据并做复盘。本项目本身不负责自动投资建议；基金实时估值仍由 FundVal-Live/养基宝接口完成，不靠 AI 自己发明算法。
