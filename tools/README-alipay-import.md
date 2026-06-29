# Alipay Snapshot Import

这个目录里的脚本用于把支付宝基金截图识别结果导入 FundVal-Live。

截图 OCR/AI 识别提示词见：

```powershell
D:\FundVal-Live\AI_SCREENSHOT_PROMPT.md
```

## 输入格式

参考：

```powershell
D:\FundVal-Live\examples\alipay_snapshot.example.json
```

字段说明：

- `snapshot_date`: 截图日期，默认今天。
- `account_name`: FundVal-Live 子账户名，默认 `Alipay Fund`。
- `holdings[].fund_code`: 基金代码。
- `holdings[].fund_name`: 基金名称。
- `holdings[].holding_value`: 支付宝截图里的当前持有金额/持有市值。
- `holdings[].holding_profit`: 支付宝截图里的持有收益/累计收益，亏损为负数。
- `holdings[].share`: 可选，如果截图里有份额。
- `holdings[].nav`: 可选，如果截图里有持仓净值或净值。

## 推荐用法

试算，不写入：

```powershell
cd D:\FundVal-Live
powershell -ExecutionPolicy Bypass -File .\tools\quick_import.ps1 .\examples\alipay_snapshot.example.json -DryRun
```

正式写入：

```powershell
cd D:\FundVal-Live
powershell -ExecutionPolicy Bypass -File .\tools\quick_import.ps1 .\examples\alipay_snapshot.example.json
```

macOS / Linux:

```bash
cd fundval-ai-dashboard-toolkit
bash ./tools/quick_import.sh ./examples/alipay_snapshot.example.json --dry-run
bash ./tools/quick_import.sh ./examples/alipay_snapshot.example.json
```

## 低层脚本

如果你需要自定义参数，可以直接调用：

```powershell
python .\tools\import_alipay_snapshot.py .\examples\alipay_snapshot.example.json --update-nav --update-estimate --estimate-source yangjibao --replace --out .\imports\last_import_report.json
```

`--replace` 会先删除这些基金在当前账户下已有的操作流水，再按支付宝快照重建合成建仓流水。

## 注意

这是“快照同步”，不是还原真实历史交易。支付宝截图通常只告诉当前市值和收益，缺少完整买卖流水，所以脚本会合成一条建仓记录，让 FundVal-Live 看板金额先对齐支付宝。
