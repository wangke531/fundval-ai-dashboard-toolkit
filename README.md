# FundVal-Live AI 本地基金看板

这是一个面向单人本地使用的基金看板工具包，基于 FundVal-Live Docker 镜像，加了本地免登录、养基宝优先估值、支付宝截图快照导入和 AI 识图交接规范。

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
6. FundVal-Live 长期保存持仓快照，养基宝接口优先提供实时估值，AI 再读取数据做复盘和操作参考。

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

AI 的职责是识别截图、生成标准 JSON、读取看板数据做复盘。基金实时估值仍由 FundVal-Live/养基宝接口完成，不靠 AI 自己发明算法。
