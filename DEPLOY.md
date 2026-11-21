# 知行岛·自习室 PC 端生产部署指南（自动 HTTPS）

整套系统已通过 Docker 打包（内置 PC 前端、运营后台与 FastAPI 后端），并配好 **Caddy 全自动 HTTPS 证书**。

## 1. 域名解析与服务器端口
1. 在域名服务商后台添加一条 `A` 记录，将你的域名指向服务器公网 IP。
2. 在云服务器安全组 / 防火墙放行 **80** 和 **443** 端口。
3. 确保服务器已安装 Docker 与 Docker Compose（`docker -v`、`docker compose version`）。

## 2. 上传项目到服务器
在服务器上创建目录（例如 `/opt/zhixingdao`），将本项目上传到该目录（**注意把本地的 `data/app.db` 一并传上去**，这样可直接保留全部 1191 道已入库真题；不需要传 `.venv/`、`node_modules/`、`miniprogram/`）。

示例（本地 PowerShell 用 `scp` 或直接用宝塔/WinSCP/Xftp 上传）：
```bash
mkdir -p /opt/zhixingdao
```

## 3. 配置生产环境变量
在服务器项目根目录复制模板并填入真实配置：
```bash
cd /opt/zhixingdao
cp .env.prod.example .env
nano .env
```
务必修改以下 4 项：
- `DOMAIN`：你的正式域名（不要带 `https://`，如 `zxd.example.com`）
- `LLM_API_KEY`：你的 DeepSeek API Key
- `JWT_SECRET`：随机 32 位以上字符串（可用 `openssl rand -hex 32` 生成）
- `ADMIN_PASSWORD`：运营后台强密码

## 4. 一键构建并启动（自动签发 HTTPS）
```bash
docker compose -f docker-compose.prod.yml up -d --build
```

查看运行状态与日志：
```bash
docker compose -f docker-compose.prod.yml ps
docker compose -f docker-compose.prod.yml logs -f app
```

## 5. 验证上线
- **PC 端首页**：`https://你的域名/`
- **运营管理后台**：`https://你的域名/admin`
- **健康检查**：`https://你的域名/health`（返回 `{"status":"ok"}`）

## 6. 日常维护与备份
- **备份数据库**（建议每周或每日定时备份）：
  ```bash
  cp /opt/zhixingdao/data/app.db /opt/zhixingdao/data/app.db.bak.$(date +%F)
  ```
- **更新代码后重新发版**：
  ```bash
  docker compose -f docker-compose.prod.yml up -d --build
  ```
