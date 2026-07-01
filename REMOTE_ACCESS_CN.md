# 国内用户远程访问说明

本项目默认只监听本机：

```text
http://localhost:21345/dashboard/positions
```

这是为了避免把个人基金持仓直接暴露到公网。国内用户如果觉得 Tailscale 登录慢、需要额外网络环境，可以按下面三种方案选择。

## 方案选择

| 方案 | 适合谁 | 优点 | 风险和成本 |
| --- | --- | --- | --- |
| 云服务器部署 | 想长期稳定给手机/AI 工具访问 | 最稳定，别人也最容易复刻 | 需要一台 VPS；公开访问前必须加密码/访问控制 |
| cpolar / NATAPP | 想最快从本机临时访问 | 国内上手简单，不需要公网 IP | 免费地址可能变化；必须开启访问保护，不适合裸奔 |
| frp 自建穿透 | 有一台 VPS，想自己控制隧道 | 开源、可控、跨平台 | 需要维护 frps/frpc 和访问控制 |
| Tailscale / Cloudflare Tunnel | 已经能稳定访问海外服务 | 安全、体验好 | 国内登录和连通可能慢，不适合作为默认方案 |

## 推荐方案 A：云服务器部署

这是给别人使用时最容易讲清楚的方案：用户租一台 VPS，在服务器上跑 Docker Compose，手机和 AI 工具都访问服务器地址。

基本流程：

```bash
git clone https://github.com/wangke531/fundval-ai-dashboard-toolkit.git
cd fundval-ai-dashboard-toolkit
cp .env.example .env
python3 ./tools/prepare_config.py
docker compose up -d
docker compose ps
```

默认 `docker-compose.yml` 仍然只把服务绑定到服务器本机 `127.0.0.1`。如果要让手机访问，不要直接改成裸露公网端口，应该在同一台服务器上加一层反向代理和访问保护。

最小原则：

- 用 Nginx / Caddy / 宝塔面板 / 1Panel 做反向代理到 `http://127.0.0.1:21345`。
- 必须开启 Basic Auth、面板访问密码、IP 白名单或其它访问控制。
- 如果有域名，尽量配置 HTTPS。
- 如果服务器在中国大陆且使用自定义域名，通常需要备案；香港、新加坡等地区一般不需要备案，但访问速度取决于线路。

不要这样做：

```yaml
ports:
  - "0.0.0.0:21345:80"
```

原因是本项目默认免登录，裸露公网会让任何拿到地址的人看到持仓数据。

## 推荐方案 B：cpolar / NATAPP

如果只是自己临时从手机看本机页面，可以用国内内网穿透服务把本机 `21345` 暴露出去。

cpolar 示例：

```powershell
cpolar http 21345
```

NATAPP 示例按其控制台创建 HTTP 隧道，把本地端口填为：

```text
21345
```

注意：

- 免费隧道地址可能会变，适合临时用。
- 付费固定域名/固定端口更适合长期用。
- 必须打开服务商提供的访问密码、访问控制、白名单等保护能力；如果没有保护能力，不建议用于真实持仓。
- 不要把内网穿透地址提交到 Git，也不要写进公开 README。

## 推荐方案 C：frp 自建穿透

如果你有自己的 VPS，可以用开源 `frp`。它的结构是：

- VPS 上运行 `frps`。
- 家里电脑运行 `frpc`。
- 公网请求先到 VPS，再转发到家里电脑的 `127.0.0.1:21345`。

适合懂一点服务器的人。它比第三方内网穿透更可控，但仍然要自己处理 HTTPS、访问密码和安全更新。

## Tailscale 仍然可以用，但不作为国内默认方案

Tailscale 的优点是安全，不需要把服务公开到互联网。但国内用户经常遇到登录慢、节点连接慢、手机端配置麻烦的问题。

如果你已经登录成功，可以继续用：

```powershell
& 'C:\Program Files\Tailscale\tailscale.exe' serve --bg 21345
& 'C:\Program Files\Tailscale\tailscale.exe' serve status
```

如果登录或访问经常卡住，优先切换到上面的云服务器或国内内网穿透方案。

## 给 AI 工具的判断规则

Claude Code / AutoClaw / Codex / QwenPaw 接管本项目时，按下面规则判断远程方案：

1. 如果用户只在本机使用，保持默认 `localhost`。
2. 如果用户在国内并且手机要长期访问，优先建议云服务器部署，并强调必须加访问保护。
3. 如果用户只要临时手机访问，建议 cpolar / NATAPP，但必须提醒开启访问密码或白名单。
4. 如果用户有 VPS 且懂运维，可以建议 frp。
5. 如果用户明确说 Tailscale 能稳定使用，再使用 Tailscale；否则不要把 Tailscale 当默认推荐。
