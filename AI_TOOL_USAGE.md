# Claude Code / AutoClaw / Codex 使用说明

这份文档说明别人部署好本工具后，如何把支付宝截图交给 AI 工具，让 AI 更新看板并分析基金。

## 角色分工

- FundVal-Live：本地 Web 看板，保存持仓，计算估值。
- 支付宝截图：真实持仓金额、持有收益、份额的来源。
- 养基宝数据源：实时估值来源，优先用于今日预估。
- Claude Code / AutoClaw / Codex：识别截图、写入 JSON、运行导入脚本、导出结构化数据、做复盘分析。

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
你正在操作一个本地基金看板项目。

目标：
1. 读取我提供的支付宝基金持仓截图。
2. 严格按照 AI_SCREENSHOT_PROMPT.md 输出 JSON。
3. 保存到 imports/alipay_snapshot.json。
4. 先执行 dry-run，不要直接正式写入。
5. dry-run 成功后，把将导入的基金数量、基金代码、持有金额、持有收益摘要告诉我，并询问我是否正式导入。
6. 我确认后再正式执行每日更新脚本。
7. 每日更新后读取 exports/ai_portfolio_snapshot.json。
8. 如果我问周报、月报或一两个月总结，运行 tools/summarize_history.py，再读取 exports/history_summary.json。
9. 根据导出的 JSON 做基金复盘，重点看今日预估盈亏、估值源是否全是养基宝、仓位集中度、亏损/盈利贡献最大的基金、历史收益变化。

不要根据截图自己推算实时基金涨跌；实时估值以 FundVal-Live/养基宝导出数据为准。
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

只导出 AI 分析数据：

```powershell
python .\tools\export_for_ai.py --out .\exports\ai_portfolio_snapshot.json
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

只导出 AI 分析数据：

```bash
python3 ./tools/export_for_ai.py --out ./exports/ai_portfolio_snapshot.json
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

- `summary`: 组合总览，包括持仓成本、市值、累计收益、今日预估收益、估值源统计。
- `positions`: 每只基金的代码、名称、类型、持仓金额、持有收益、估算涨跌、今日预估盈亏、估值源。
- `analysis_notes`: AI 分析时必须遵守的边界。

每日正式更新后，还会归档：

```text
history/YYYY-MM-DD/alipay_snapshot.json
history/YYYY-MM-DD/import_report.json
history/YYYY-MM-DD/ai_portfolio_snapshot.json
history/daily_index.jsonl
```

`history/daily_index.jsonl` 是长期记录入口，一个月、两个月复盘都优先读它。

## 推荐分析结构

AI 可以按这个结构输出：

```text
1. 数据状态
   - 本次持仓来自哪一天的支付宝截图。
   - 估值源是否全部为养基宝，有没有 fallback。

2. 今日表现
   - 今日预估盈亏。
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
