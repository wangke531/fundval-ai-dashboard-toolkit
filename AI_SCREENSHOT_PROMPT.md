# 支付宝基金截图识别提示词

把支付宝基金持仓截图识别成下面的 JSON。只输出 JSON，不要解释，不要 Markdown。

要求：

- `snapshot_date` 使用截图对应日期；如果截图没有日期，使用今天。
- `account_name` 默认写 `Alipay Fund`。
- 每只基金必须输出 `fund_code`、`fund_name`、`holding_value`、`holding_profit`。
- 金额只保留数字字符串，不要带逗号、人民币符号或单位。
- `holding_value` 是支付宝里的当前持有金额/持有市值。
- `holding_profit` 是支付宝里的持有收益/累计收益；亏损要带负号。
- 如果截图里能看到份额，填 `share`；看不到就不要编。
- 如果截图里能看到持仓净值或净值，填 `nav`；看不到就不要编。
- 不确定的基金不要输出到 `holdings`，放到 `warnings` 里说明。

JSON 格式：

```json
{
  "snapshot_date": "2026-06-29",
  "account_name": "Alipay Fund",
  "holdings": [
    {
      "fund_code": "024239",
      "fund_name": "华夏全球科技先锋混合(QDII)C",
      "holding_value": "8183.76",
      "holding_profit": "1183.76",
      "share": "1234.5678",
      "nav": "1.2345"
    }
  ],
  "warnings": []
}
```

识别完成后，把 JSON 保存到 `imports/alipay_snapshot.json`，再运行：

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\quick_import.ps1 .\imports\alipay_snapshot.json
```
