# 发布前检查清单

发布给别人或推 GitHub 前，先确认：

- 不包含 `.env`。
- 不包含 `config/config.json`。
- 不包含 `config/config.runtime.json`。
- 不包含 `imports/` 里的真实导入 JSON、报告、截图识别结果。
- 不包含 `exports/` 里的真实 AI 分析数据。
- 不包含 `work/` 临时文件。
- `docker compose ps` 全部服务正常。
- `python .\tools\prepare_config.py` 可以生成 `config/config.runtime.json`。
- `powershell -ExecutionPolicy Bypass -File .\tools\quick_import.ps1 .\examples\sample-alipay\alipay_snapshot.mock.json -DryRun -Out .\examples\sample-alipay\dry_run_report.mock.json` 可以通过。
- `bash ./tools/quick_import.sh ./examples/sample-alipay/alipay_snapshot.mock.json --dry-run --out ./examples/sample-alipay/dry_run_report.mock.json` 可以通过。
- `python .\tools\export_for_ai.py --out .\exports\ai_portfolio_snapshot.json` 可以通过。
- `README.md` 里的启动地址仍是 `http://localhost:21345/dashboard/positions`。
- 如果要公网部署，必须先重新设计鉴权和 HTTPS；默认版本只适合本机自用。

推荐发布文件：

- `.env.example`
- `.gitignore`
- `AI_SCREENSHOT_PROMPT.md`
- `README.md`
- `RELEASE_CHECKLIST.md`
- `backend-entrypoint.sh`
- `docker-compose.yml`
- `config/`
- `examples/`
- `imports/.gitkeep`
- `exports/.gitkeep`
- `tools/`
