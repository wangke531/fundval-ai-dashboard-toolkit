# Claude Code / AutoClaw / Codex 使用说明

这份文档说明别人部署好本数据框架后，如何把支付宝截图交给 AI 工具，让 AI 操作本地脚本、更新数据、读取结构化文件并分析基金。

## 角色分工

- FundVal-Live 数据框架：本地 Web 看板，保存持仓，计算估值，归档历史，导出结构化 JSON。
- 支付宝截图：真实持仓金额、持有收益、份额和成本基准的来源；不使用支付宝显示的昨日收益做看板收益。
- 养基宝数据源：最近估值来源，优先用于盘中实时估值和未结算估值；可能是盘中实时值、收盘值或缓存值。
- Claude Code / AutoClaw / Codex：识别截图、写入 JSON、运行导入脚本、导出结构化数据、做复盘分析。

本项目本身不做总结和建议，只提供数据记录和导出能力。

AI 不应该自己发明基金估值算法。AI 应该读取 FundVal-Live 导出的 JSON，再做解释和分析。

## 一次完整流程

1. 用户打开支付宝基金持仓页并截图。
2. 用户把截图发给 Claude Code / AutoClaw / Codex。
3. AI 按 `AI_SCREENSHOT_PROMPT.md` 把截图识别成 JSON。
4. AI 保存 JSON 到 `imports/alipay_snapshot.json`。
5. AI 先 dry-run，确认不会报错。
6. 用户确认后，AI 正式执行每日更新。
7. 每日更新会导入持仓、导出 `exports/ai_portfolio_snapshot.json`，并归档到 `history/YYYY-MM-DD/`。
8. AI 读取导出文件和历史汇总文件并分析。

## 给 AI 工具的完整提示词

把下面这段发给 Claude Code / AutoClaw / Codex：

```text
你正在操作一个本地基金数据框架项目。

目标：
1. 读取我提供的支付宝基金持仓截图。
2. 严格按照 AI_SCREENSHOT_PROMPT.md 输出 JSON。
3. 保存到 imports/alipay_snapshot.json。
4. 先执行 dry-run，不要直接正式写入。
5. dry-run 成功后，把将导入的基金数量、基金代码、持有金额、持有收益摘要告诉我，并询问我是否正式导入。
6. 我确认后再正式执行每日更新脚本。
7. 每日更新后读取 exports/ai_portfolio_snapshot.json。
8. 如果我问周报、月报或一两个月总结，运行 tools/summarize_history.py，再读取 exports/history_summary.json。
9. 根据导出的 JSON 和持仓页顶部“收益日历口径”做基金复盘，重点区分当日养基宝口径收益、穿透中/结算中阶段、估值源是否全是养基宝、净值日期是否新鲜、仓位集中度和历史收益变化。

不要根据截图自己发明实时基金估值算法；估值数据以 FundVal-Live/养基宝导出数据为准，但必须检查市场阶段、估值时间和净值日期。支付宝截图只用来同步持仓，不要读取或引用支付宝显示的昨日收益。
不要给确定性投资建议，只给风险提示、数据观察和可选操作思路。
```

## Windows 命令

截图 JSON 保存后，先试算：

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\quick_import.ps1 .\imports\alipay_snapshot.json -DryRun
```

用户确认后执行每日更新：

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\daily_update.ps1 .\imports\alipay_snapshot.json
```

只导出 AI 分析数据并刷新养基宝估值：

```powershell
python .\tools\export_for_ai.py --out .\exports\ai_portfolio_snapshot.json
```

归档当前养基宝收益，建议 Windows 任务计划每天 `23:59` 执行：

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\archive_local_pnl.ps1
```

生成最近 30 天历史汇总：

```powershell
python .\tools\summarize_history.py --days 30 --out .\exports\history_summary.json
```

## macOS / Linux 命令

截图 JSON 保存后，先试算：

```bash
bash ./tools/quick_import.sh ./imports/alipay_snapshot.json --dry-run
```

用户确认后执行每日更新：

```bash
bash ./tools/daily_update.sh ./imports/alipay_snapshot.json
```

只导出 AI 分析数据并刷新养基宝估值：

```bash
python3 ./tools/export_for_ai.py --out ./exports/ai_portfolio_snapshot.json
```

归档当前养基宝收益：

```bash
bash ./tools/archive_local_pnl.sh
```

生成最近 30 天历史汇总：

```bash
python3 ./tools/summarize_history.py --days 30 --out ./exports/history_summary.json
```

## AI 分析文件

导出文件路径：

```text
exports/ai_portfolio_snapshot.json
```

里面包含：

- `summary`: 组合总览，包括持仓成本、市值、累计收益、估值后收益、估值源统计。
- `pnl_summary.daily_pnl`: 持仓页顶部“收益日历口径”的数据来源，包括当日收益、阶段、归档时间和境内/QDII 拆分。
- `positions`: 每只基金的代码、名称、类型、持仓金额、持有收益、估算涨跌、估值时间、净值日期、估值源。
- `analysis_notes`: AI 分析时必须遵守的边界。

每日正式更新后，还会归档：

```text
history/YYYY-MM-DD/alipay_snapshot.json
history/YYYY-MM-DD/import_report.json
history/YYYY-MM-DD/ai_portfolio_snapshot.json
history/daily_index.jsonl
```

`history/daily_index.jsonl` 是长期记录入口，一个月、两个月复盘都优先读它。数据框架只负责生成这些文件，分析逻辑由 AI 工具完成。

如果用户没有发支付宝截图，但想看估值盈亏，主入口是 `http://localhost:21345/dashboard/positions` 顶部的“收益日历口径”卡片。AI 可以运行 `tools/export_for_ai.py` 刷新养基宝估值并更新 `exports/ai_portfolio_snapshot.json`；如果要固化当天收益，运行 `tools/archive_local_pnl.py` 或对应平台脚本写入 `history/local_pnl_series.jsonl`。

持仓页顶部卡片的口径：

- `当日收益`：北京时间自然日的养基宝/FundVal 估算收益，按当前持仓份额和养基宝估算涨跌计算；凌晨美股和白天 A 股都归入当天。
- `当前阶段`：`00:00-14:59` 为穿透中，`15:00-23:59` 为结算中，期间都跟随养基宝实时变化；`23:59` 归档为当日收益，第二天显示为昨日收益参考。
- `持仓快照`：最近一次支付宝截图日期，只代表持仓同步时间，不代表收益来源。
- `收益变化记录`：本项目自己记录的养基宝收益历史，文件为 `history/local_pnl_series.jsonl`。如果某天没有养基宝/净值历史快照，不要强行补收益。

## 推荐分析结构

AI 可以按这个结构输出：

```text
1. 数据状态
   - 本次持仓来自哪一天的支付宝截图。
   - 估值源是否全部为养基宝，有没有 fallback。

2. 收益日历口径
   - 当日收益、当前阶段、持仓快照日期分别是多少。
   - 说明市场阶段、估值抓取时间和净值日期。
   - 贡献最大/拖累最大的基金。

3. 仓位结构
   - 持仓金额最大的基金。
   - QDII、半导体、债券、主动混合等类型的大致集中度。

4. 风险提示
   - 是否过度集中在单一赛道。
   - 是否存在高波动 QDII/半导体占比过高。

5. 可选操作思路
   - 只给观察项和备选动作，不给确定性买卖建议。
```

## 注意

`imports/` 和 `exports/` 默认不会提交到 Git，因为里面可能包含个人真实持仓数据。
