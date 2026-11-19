# 主观题 AI 精批完整系统（FastAPI + PostgreSQL + UniApp 微信小程序）

专为**考公申论（小题/大作文）**与**考研英语作文**打造的独立全栈 AI 精批系统。

## 项目结构
* `app/` — Python 核心批改引擎 + FastAPI 异步后端 + SQLAlchemy 2.0 数据层
  * `app/pipeline.py`：3 步并发确定性精批管线（手写 OCR → 采分点/量表核对与代码算分 → 逐句红笔批注 & 同思路升格）
  * `app/db/`：PostgreSQL (`JSONB`) / SQLite 双兼容异步数据模型（`users`、`questions`、`grading_tasks`）
  * `app/api/`：微信小程序登录、287+ 真题检索、手写拍照 OCR、异步精批提交与进度轮询、历史薄弱项画像
* `data/shenlun_questions.json` — 已清洗的 **287 道历年国考/省考申论真题**（249 道小题含原子采分点 + 38 道大作文）
* `miniprogram/` — **UniApp (Vue 3 + TypeScript + Vite)** 微信小程序工程（含真题库、拍照 OCR 提交、红笔报告、历史记录、个人中心 5 个完整页面）
* `docker-compose.yml` — 一键拉起 PostgreSQL 16 + Redis 7

---

## 一、启动后端服务（FastAPI）

```powershell
# 1. 激活虚拟环境并安装依赖
.\.venv\Scripts\pip install -r requirements.txt

# 2. 复制环境变量（未填 API Key 时自动启用 Mock 精批，方便零费用联调前后端）
copy .env.example .env

# （可选）生产环境使用 PostgreSQL + Redis：
# docker compose up -d
# 并将 .env 中的 DATABASE_URL 切换为 postgresql+asyncpg://postgres:postgres@localhost:5432/ai_grading

# 3. 启动 FastAPI（首次启动会自动建表并导入 287+ 道真题）
.\.venv\Scripts\uvicorn app.api.main:app --reload --host 0.0.0.0 --port 8000
```
启动后访问 `http://127.0.0.1:8000/docs` 即可打开完整的 Swagger 交互式 API 文档。

---

## 二、启动 UniApp 微信小程序前端

```powershell
cd miniprogram
npm install

# 编译微信小程序（生成 dist/dev/mp-weixin，直接用微信开发者工具导入该目录即可联调）
npm run dev:mp-weixin

# 或者直接运行 H5 网页版在浏览器预览
npm run dev:h5
```
> 提示：微信开发者工具本地联调时，请在右上角「详情 → 本地设置」勾选 **“不校验合法域名”**。上线前在 `miniprogram/src/manifest.json` 填入真实 AppID，并在 `miniprogram/src/utils/request.ts` 替换 `API_BASE_URL` 为你的 HTTPS 域名。
