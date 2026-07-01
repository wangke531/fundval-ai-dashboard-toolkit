# Claude Code 接管说明

请先阅读并遵守 `AGENTS.md`。本文件只做 Claude Code 入口指向，避免重复维护两套规则。

核心流程：

1. 读取 `AI_SCREENSHOT_PROMPT.md`，把用户发来的支付宝基金持仓截图识别成 `imports/alipay_snapshot.json`。
2. 先运行 dry-run，不要直接正式导入。
3. 用户确认后运行每日更新脚本。
4. 读取 `exports/ai_portfolio_snapshot.json` 和 `history/` 做复盘。
5. 不要提交 `.env`、`imports/`、`exports/`、`history/` 或任何真实持仓数据。

Windows 常用命令：

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\quick_import.ps1 .\imports\alipay_snapshot.json -DryRun
powershell -ExecutionPolicy Bypass -File .\tools\daily_update.ps1 .\imports\alipay_snapshot.json
python .\tools\export_for_ai.py --out .\exports\ai_portfolio_snapshot.json
powershell -ExecutionPolicy Bypass -File .\tools\archive_local_pnl.ps1
```

macOS / Linux 常用命令：

```bash
bash ./tools/quick_import.sh ./imports/alipay_snapshot.json --dry-run
bash ./tools/daily_update.sh ./imports/alipay_snapshot.json
python3 ./tools/export_for_ai.py --out ./exports/ai_portfolio_snapshot.json
bash ./tools/archive_local_pnl.sh
```
