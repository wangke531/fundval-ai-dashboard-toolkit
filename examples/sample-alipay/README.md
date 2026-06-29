# 支付宝截图样例

这个目录是公开演示样例，不是真实账户数据。

文件：

- `alipay_holdings_mock.png`: 模拟支付宝基金持仓截图。
- `alipay_snapshot.mock.json`: AI 从截图中应该输出的结构化 JSON。

验证流程：

```powershell
cd D:\FundVal-Live
powershell -ExecutionPolicy Bypass -File .\tools\quick_import.ps1 .\examples\sample-alipay\alipay_snapshot.mock.json -DryRun -Out .\examples\sample-alipay\dry_run_report.mock.json
```

正式使用时，把自己的支付宝截图发给 AI，让 AI 按根目录的 `AI_SCREENSHOT_PROMPT.md` 输出同样格式的 JSON，再运行 `tools/quick_import.ps1`。
