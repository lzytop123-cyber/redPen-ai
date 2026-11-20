from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes_admin import router as admin_router
from app.api.routes_auth import router as auth_router
from app.api.routes_grading import router as grading_router
from app.api.routes_questions import router as questions_router
from app.db.database import AsyncSessionLocal, init_db
from app.db.seed import seed_questions_if_empty


@asynccontextmanager
async def lifespan(_: FastAPI):
    await init_db()
    async with AsyncSessionLocal() as db:
        inserted = await seed_questions_if_empty(db)
        if inserted:
            print(f"[Startup] 自动导入 {inserted} 道真题进入数据库。")
    yield


app = FastAPI(
    title="主观题 AI 精批后端 API",
    description="支持考公申论（小题/大作文）与考研英语作文的 3 步确定性 AI 精批服务",
    version="0.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(admin_router)
app.include_router(auth_router)
app.include_router(questions_router)
app.include_router(grading_router)


@app.get("/health")
async def health():
    return {"status": "ok"}


# 挂载独立 Vue 3 运营后台静态产物 (admin-web/dist)
ADMIN_DIST = Path("admin-web/dist")
if (ADMIN_DIST / "assets").exists():
    app.mount("/admin/assets", StaticFiles(directory=str(ADMIN_DIST / "assets")), name="admin-assets")


@app.get("/admin", include_in_schema=False)
@app.get("/admin/{full_path:path}", include_in_schema=False)
async def serve_admin_spa(full_path: str = ""):
    index_file = ADMIN_DIST / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return HTMLResponse(
        "<h3>后台前端尚未构建，请在 admin-web 目录运行 npm install && npm run build</h3>",
        status_code=503,
    )
