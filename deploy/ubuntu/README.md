# ai.islandspace.top 轻量部署

这是给一台已经在跑其他站点的 Ubuntu 24.04 用的独立部署。它不使用 Docker、PostgreSQL 或 Redis，也不修改现有站点。

已占用、本次不要碰的对象：

- `islandspace.top`
- `admin.islandspace.top`
- `zxd-backend` 和它的 `8000` 端口
- 任何已经存在的数据库文件

本服务的固定值：

| 项 | 值 |
| --- | --- |
| 代码目录 | `/opt/zxd-ai` |
| 系统用户 | `zxd-ai`（nologin） |
| systemd | `zxd-ai.service` |
| 监听 | `127.0.0.1:8001`，只给本机 nginx |
| 数据库 | `/opt/zxd-ai/data/zxd-ai.db`（新文件） |
| 环境文件 | `/opt/zxd-ai/.env`（权限 600，不入库） |
| 站点 | `ai.islandspace.top` |
| 证书 | `/etc/letsencrypt/live/ai.islandspace.top/` |
| 证书验证目录 | `/var/www/ai-islandspace-top` |
| 备份目录 | `/var/backups/zxd-ai` |

前端在打包机上构建，服务器只接收已经生成的 `web/dist` 和 `admin-web/dist`。小程序不在这台机器上发布。

## 实际路由

进程起来之后，下面这些路径都由同一个 uvicorn 提供，nginx 只做整站反代：

- `GET /health`：`{"status":"ok","app_env":"production"}`
- `GET /`：PC 站，`web/dist`
- `GET /assets/`、`/figures/`、`/favicon.svg`、`/logo.jpg`
- `GET /admin` 和 `GET /admin/...`：运营后台，`admin-web/dist`
- `GET /admin/assets/`
- `POST /api/auth/register`、`POST /api/auth/login`、`GET /api/auth/me`
- `POST /api/auth/wx-login`：没有 `WX_APPID` 和 `WX_SECRET` 时返回 503，不会生成开发 openid
- `GET /api/questions/...`：现有题库接口，不要求登录
- `POST /api/grading/submit`、`/api/grading/submit-custom`、`/api/grading/ocr`：要登录；没有可用模型密钥时返回 503，不走 Mock，也不扣次
- `/api/admin/...`：请求头 `X-Admin-Password`

PC 站使用 hash 路由，深链接不需要额外的 history fallback。

## 生产启动条件

`APP_ENV=production` 时，下面任一不满足，进程退出，不建库、不提供开发身份：

- `JWT_SECRET` 至少 32 位，且不是仓库里的默认或占位字符串
- `ADMIN_PASSWORD` 至少 12 位，且不是 `admin123` 或其他示例口令
- 两个秘密不能相同
- `ENABLE_MOCK_FALLBACK=false`
- `DATABASE_URL` 是绝对路径 SQLite，文件名必须是 `zxd-ai.db`
- `REDIS_URL` 留空
- `CORS_ORIGINS` 留空，或者是逗号分隔的 `https://` 源，不能是 `*`

开发环境仍是 `APP_ENV` 缺省或 `development`。默认 `ENABLE_MOCK_FALLBACK=true` 时，本地无 Token 测试用户和未配置微信时的 `dev_` openid 继续可用。这个开关不能把生产进程打开。

## 服务器上要填写的变量

只在服务器的 `/opt/zxd-ai/.env` 里填写。不要把填好的文件拷回仓库。

启动所必需：

- `JWT_SECRET`：`openssl rand -hex 32`
- `ADMIN_PASSWORD`：另一串独立的长口令

精批和手写识别要可用时才需要：

- `LLM_API_KEY`
- 可选：`LLM_BASE_URL`、`LLM_MODEL`
- 可选：`VLM_API_KEY`、`VLM_BASE_URL`、`VLM_MODEL`。后两者留空时，视觉识别复用文本模型的地址和密钥

小程序登录要可用时才需要：

- `WX_APPID`
- `WX_SECRET`

没有模型密钥时，注册、登录和题库可以打开，精批与 OCR 返回 503。没有微信变量时，PC 账号登录不受影响，`/api/auth/wx-login` 返回 503。这些缺口不能用 Mock、匿名用户或开发 openid 补上。

## 安装

在打包机上使用仓库里的归档，或自己执行 `deploy/ubuntu/make-archive.sh`。归档里已经包含前端 dist，不包含 `.env`、`.git`、`node_modules`、`.venv` 和用户上传。

```bash
sudo apt-get install -y python3-venv python3-pip nginx certbot sqlite3
sudo tar -xzf zxd-ai-deploy.tar.gz -C /opt
if ! id zxd-ai >/dev/null 2>&1; then
  sudo useradd --system --home-dir /opt/zxd-ai --shell /usr/sbin/nologin zxd-ai
fi
sudo -u zxd-ai python3 -m venv /opt/zxd-ai/.venv
sudo -u zxd-ai /opt/zxd-ai/.venv/bin/pip install --no-cache-dir -r /opt/zxd-ai/requirements.txt
sudo install -d -o zxd-ai -g zxd-ai -m 700 /opt/zxd-ai/data/uploads /var/backups/zxd-ai
sudo cp /opt/zxd-ai/.env.production.example /opt/zxd-ai/.env
sudo chmod 600 /opt/zxd-ai/.env
sudo chown zxd-ai:zxd-ai /opt/zxd-ai/.env
```

编辑 `/opt/zxd-ai/.env`，至少替换 `JWT_SECRET` 和 `ADMIN_PASSWORD`。确认 `DATABASE_URL` 仍是：

```text
sqlite+aiosqlite:////opt/zxd-ai/data/zxd-ai.db
```

不要把现有 `app.db` 或其他服务的库复制进来，也不要改这个文件名。目录里如果已经有别的数据库文件，留在原地，不要把 `DATABASE_URL` 指过去。

```bash
sudo cp /opt/zxd-ai/deploy/ubuntu/zxd-ai.service /etc/systemd/system/zxd-ai.service
sudo systemctl daemon-reload
sudo systemctl enable --now zxd-ai.service
curl -fsS http://127.0.0.1:8001/health
```

第一次启动会把归档里的题库 JSON 导入这个新库。内存上限是 768MiB，只开 1 个 worker，避免和同机服务抢内存。

查看日志：`sudo journalctl -u zxd-ai -f`。预检失败时服务不会进入监听；日志里只有变量名，没有秘密的值。

## 证书和 nginx

先确认 DNS 已经把 `ai.islandspace.top` 指到这台机器。下面的命令只增加一个新站点文件。`nginx -t` 失败时不要 reload。

```bash
sudo install -d /var/www/ai-islandspace-top
sudo cp /opt/zxd-ai/deploy/ubuntu/nginx/ai.islandspace.top.http.conf \
  /etc/nginx/sites-available/ai.islandspace.top.conf
sudo ln -s /etc/nginx/sites-available/ai.islandspace.top.conf \
  /etc/nginx/sites-enabled/ai.islandspace.top.conf
sudo nginx -t && sudo systemctl reload nginx
sudo certbot certonly --webroot -w /var/www/ai-islandspace-top -d ai.islandspace.top
```

证书签发成功后，换成带 TLS 的配置。这个文件只包含 `server_name ai.islandspace.top`，反代目标是 `127.0.0.1:8001`。

```bash
sudo cp /opt/zxd-ai/deploy/ubuntu/nginx/ai.islandspace.top.conf \
  /etc/nginx/sites-available/ai.islandspace.top.conf
sudo nginx -t && sudo systemctl reload nginx
curl -fsS https://ai.islandspace.top/health
```

`certbot certonly --webroot` 不会改写其他站点。不要运行会扫描全部 server 块的证书命令，也不要编辑另外两个域名的配置。

页面：

- `https://ai.islandspace.top/`
- `https://ai.islandspace.top/admin`

后台登录框不显示默认口令。口令只来自 `ADMIN_PASSWORD`。

## 备份

用 root 执行：

```bash
sudo /opt/zxd-ai/deploy/ubuntu/backup.sh
```

脚本调用 `sqlite3 .backup`，生成 `/var/backups/zxd-ai/zxd-ai-<时间>.db`，并在有上传目录时一并打包。不要用普通 `cp` 拷正在写入的 SQLite。

## 更新

```bash
sudo /opt/zxd-ai/deploy/ubuntu/backup.sh
sudo systemctl stop zxd-ai
sudo cp -a /opt/zxd-ai /opt/zxd-ai-prev
```

保留 `/opt/zxd-ai/.env` 和 `/opt/zxd-ai/data`。用新归档覆盖 `app/`、`web/dist`、`admin-web/dist`、`requirements.txt` 和 `deploy/`，不要覆盖 `.env` 和 `data/zxd-ai.db`。然后：

```bash
sudo -u zxd-ai /opt/zxd-ai/.venv/bin/pip install --no-cache-dir -r /opt/zxd-ai/requirements.txt
sudo chown -R zxd-ai:zxd-ai /opt/zxd-ai
sudo chmod 600 /opt/zxd-ai/.env
sudo systemctl start zxd-ai
curl -fsS http://127.0.0.1:8001/health
```

## 回滚

```bash
sudo systemctl stop zxd-ai
sudo mv /opt/zxd-ai /opt/zxd-ai-failed
sudo mv /opt/zxd-ai-prev /opt/zxd-ai
```

如果这次更新没有改库结构，继续使用原来的 `/opt/zxd-ai/data`。从失败目录把 `.env` 和 `data/` 放回回滚后的目录，不要拿备份覆盖其他服务的数据库。只有确认新库已经写坏时，才在服务停止后用对应的 `.backup` 文件替换 `/opt/zxd-ai/data/zxd-ai.db`，并同时恢复同一次的上传打包。

```bash
sudo chown -R zxd-ai:zxd-ai /opt/zxd-ai
sudo systemctl start zxd-ai
curl -fsS http://127.0.0.1:8001/health
```

## 小程序

需要发布前，在打包机把 `miniprogram/env.production.example` 复制为 `miniprogram/.env.production`，确认 `VITE_API_BASE_URL=https://ai.islandspace.top`，再执行生产构建。微信后台还要单独配置该 HTTPS 域名，并填写 `WX_APPID` 与 `WX_SECRET`。这次部署不上传小程序。
