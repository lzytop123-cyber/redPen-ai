import asyncio
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api.auth_utils import get_current_user
from app.api.main import app, health
from app.api.routes_auth import LoginReq, RegisterReq, WxLoginReq, login_web_account, register_web_account, wx_login
from app.config import Settings, build_cors_middleware_kwargs, production_security_errors, settings
from app.db.database import Base
from app.db.models import User

ROOT = Path(__file__).resolve().parents[1]


def _route_paths(routes) -> list[str]:
    found: list[str] = []
    for route in routes:
        path = getattr(route, "path", None)
        if isinstance(path, str):
            found.append(path)
        nested = getattr(route, "routes", None)
        if nested:
            found.extend(_route_paths(nested))
        original = getattr(route, "original_router", None)
        if original is not None:
            found.extend(_route_paths(original.routes))
    return found


_TEST_JWT = "UnitTestJwtSecretValue0123456789abcd"
_TEST_ADMIN = "UnitTestAdminPasswordValue"


def _valid_production(**overrides) -> Settings:
    values = dict(
        _env_file=None,
        app_env="production",
        jwt_secret=_TEST_JWT,
        admin_password=_TEST_ADMIN,
        enable_mock_fallback=False,
        database_url="sqlite+aiosqlite:////tmp/zxd-ai-unit/zxd-ai.db",
        redis_url="",
        cors_origins="",
        llm_api_key="",
        vlm_api_key="",
        wx_appid="",
        wx_secret="",
    )
    values.update(overrides)
    return Settings(**values)


class ProductionSecurityTests(unittest.TestCase):
    def setUp(self):
        self._saved = {
            name: getattr(settings, name)
            for name in (
                "app_env",
                "enable_mock_fallback",
                "jwt_secret",
                "admin_password",
                "wx_appid",
                "wx_secret",
                "llm_api_key",
                "vlm_api_key",
                "vlm_base_url",
                "database_url",
                "redis_url",
                "cors_origins",
            )
        }

    def tearDown(self):
        for name, value in self._saved.items():
            setattr(settings, name, value)

    def _use(self, **kwargs):
        for name, value in kwargs.items():
            setattr(settings, name, value)

    def test_development_defaults_still_start(self):
        cfg = Settings(_env_file=None, app_env="development")
        self.assertEqual(production_security_errors(cfg), [])
        cors = build_cors_middleware_kwargs(cfg)
        self.assertEqual(cors["allow_origins"], ["*"])
        self.assertFalse(cors["allow_credentials"])

    def test_production_rejects_default_secrets_without_echoing_them(self):
        cfg = Settings(_env_file=None, app_env="production")
        text = " ".join(production_security_errors(cfg))
        for name in ("JWT_SECRET", "ADMIN_PASSWORD", "ENABLE_MOCK_FALLBACK", "DATABASE_URL"):
            self.assertIn(name, text)
        self.assertNotIn("dev-secret-change-in-prod", text)
        self.assertNotIn("admin123", text)
        self.assertEqual(build_cors_middleware_kwargs(cfg)["allow_origins"], [])
        self.assertFalse(build_cors_middleware_kwargs(cfg)["allow_credentials"])

    def test_production_rejects_wildcard_cors_redis_and_old_database_name(self):
        cfg = _valid_production(cors_origins="*")
        self.assertTrue(any("CORS_ORIGINS" in item for item in production_security_errors(cfg)))
        cfg = _valid_production(redis_url="redis://127.0.0.1:6379/0")
        self.assertTrue(any("REDIS_URL" in item for item in production_security_errors(cfg)))
        cfg = _valid_production(database_url="sqlite+aiosqlite:////opt/zxd-ai/data/app.db")
        self.assertTrue(any("DATABASE_URL" in item for item in production_security_errors(cfg)))
        cfg = _valid_production()
        self.assertEqual(production_security_errors(cfg), [])
        example = Settings(
            _env_file=str(ROOT / ".env.production.example"),
            _env_file_encoding="utf-8",
        )
        self.assertTrue(production_security_errors(example))
        self.assertFalse(example.key_is_configured(example.llm_api_key))
        self.assertFalse(example.wechat_is_configured)

    def test_process_refuses_default_production_and_keeps_development(self):
        env = os.environ.copy()
        for name in ("JWT_SECRET", "ADMIN_PASSWORD", "ENABLE_MOCK_FALLBACK", "DATABASE_URL", "APP_ENV"):
            env.pop(name, None)
        dev = subprocess.run(
            [sys.executable, "-c", "import app.config"],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
        )
        self.assertEqual(dev.returncode, 0, dev.stderr)

        env["APP_ENV"] = "production"
        prod = subprocess.run(
            [sys.executable, "-c", "import app.config"],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(prod.returncode, 0)
        combined = prod.stdout + prod.stderr
        self.assertIn("JWT_SECRET", combined)
        self.assertIn("ADMIN_PASSWORD", combined)
        self.assertNotIn("dev-secret-change-in-prod", combined)
        self.assertNotIn("admin123", combined)

        env.pop("ALLOW_WEAK_ADMIN_PASSWORD", None)
        env["JWT_SECRET"] = _TEST_JWT
        env["ADMIN_PASSWORD"] = _TEST_ADMIN
        env["ENABLE_MOCK_FALLBACK"] = "false"
        env["DATABASE_URL"] = "sqlite+aiosqlite:////tmp/zxd-ai-preflight/zxd-ai.db"
        env["REDIS_URL"] = ""
        env["CORS_ORIGINS"] = ""
        ok = subprocess.run(
            [sys.executable, "-c", "import app.config"],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
        )
        self.assertEqual(ok.returncode, 0, ok.stderr)
        self.assertNotIn(env["JWT_SECRET"], ok.stdout + ok.stderr)
        self.assertNotIn(env["ADMIN_PASSWORD"], ok.stdout + ok.stderr)

    def test_default_admin_password_stays_rejected_unless_opt_in(self):
        weak = _valid_production(admin_password="admin123")
        errors = production_security_errors(weak)
        self.assertTrue(any(item.startswith("ADMIN_PASSWORD") for item in errors))
        self.assertFalse(any(item.startswith("JWT_SECRET") for item in errors))
        self.assertNotIn("admin123", " ".join(errors))

        explicit_false = _valid_production(admin_password="admin123", allow_weak_admin_password=False)
        self.assertTrue(any(item.startswith("ADMIN_PASSWORD") for item in production_security_errors(explicit_false)))

        opted = _valid_production(admin_password="admin123", allow_weak_admin_password=True)
        self.assertEqual(production_security_errors(opted), [])

        unset = _valid_production(admin_password="__SET_ON_SERVER__", allow_weak_admin_password=True)
        padded = _valid_production(admin_password="admin123 ", allow_weak_admin_password=True)
        self.assertTrue(any(item.startswith("ADMIN_PASSWORD") for item in production_security_errors(unset)))
        self.assertTrue(any(item.startswith("ADMIN_PASSWORD") for item in production_security_errors(padded)))

        jwt_errors = production_security_errors(
            _valid_production(
                admin_password="admin123",
                allow_weak_admin_password=True,
                jwt_secret="dev-secret-change-in-prod",
            )
        )
        self.assertTrue(any(item.startswith("JWT_SECRET") for item in jwt_errors))
        self.assertFalse(any(item.startswith("ADMIN_PASSWORD") for item in jwt_errors))
        self.assertNotIn("admin123", " ".join(jwt_errors))

        for overrides in (
            {"enable_mock_fallback": True},
            {"redis_url": "redis://127.0.0.1:6379/0"},
            {"cors_origins": "*"},
            {"database_url": "sqlite+aiosqlite:////opt/zxd-ai/data/app.db"},
        ):
            blocked = production_security_errors(
                _valid_production(admin_password="admin123", allow_weak_admin_password=True, **overrides)
            )
            self.assertTrue(blocked)
            self.assertFalse(any(item.startswith("ADMIN_PASSWORD") for item in blocked))

        env = os.environ.copy()
        for name in (
            "JWT_SECRET",
            "ADMIN_PASSWORD",
            "ENABLE_MOCK_FALLBACK",
            "DATABASE_URL",
            "APP_ENV",
            "ALLOW_WEAK_ADMIN_PASSWORD",
            "REDIS_URL",
            "CORS_ORIGINS",
        ):
            env.pop(name, None)
        env.update(
            {
                "APP_ENV": "production",
                "JWT_SECRET": _TEST_JWT,
                "ADMIN_PASSWORD": "admin123",
                "ENABLE_MOCK_FALLBACK": "false",
                "DATABASE_URL": "sqlite+aiosqlite:////tmp/zxd-ai-preflight/zxd-ai.db",
                "REDIS_URL": "",
                "CORS_ORIGINS": "",
            }
        )
        refused = subprocess.run(
            [sys.executable, "-c", "import app.config"],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(refused.returncode, 0)
        refused_text = refused.stdout + refused.stderr
        self.assertIn("ADMIN_PASSWORD", refused_text)
        self.assertNotIn("admin123", refused_text)

        env["ALLOW_WEAK_ADMIN_PASSWORD"] = "true"
        allowed = subprocess.run(
            [sys.executable, "-c", "import app.config"],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
        )
        self.assertEqual(allowed.returncode, 0, allowed.stderr)
        self.assertNotIn("admin123", allowed.stdout + allowed.stderr)

        env["JWT_SECRET"] = "dev-secret-change-in-prod"
        jwt_blocked = subprocess.run(
            [sys.executable, "-c", "import app.config"],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(jwt_blocked.returncode, 0)
        jwt_text = jwt_blocked.stdout + jwt_blocked.stderr
        self.assertIn("JWT_SECRET", jwt_text)
        self.assertNotIn("ADMIN_PASSWORD", jwt_text)

    def test_inference_mode_never_calls_a_provider(self):
        with patch("openai.AsyncOpenAI", side_effect=AssertionError("provider client constructed")):
            self._use(app_env="development", enable_mock_fallback=True)
            self.assertEqual(settings.inference_mode("sk-your-api-key-here"), "mock")
            self._use(app_env="production", enable_mock_fallback=False)
            self.assertEqual(settings.inference_mode(""), "unavailable")
            self.assertEqual(settings.inference_mode("__SET_ON_SERVER__"), "unavailable")
            self.assertEqual(settings.inference_mode("unit-test-model-key"), "live")

    def test_auth_fails_closed_in_production_and_stays_open_in_development(self):
        asyncio.run(self._auth_modes())

    async def _auth_modes(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_file = Path(tmp) / "auth.db"
            engine = create_async_engine(f"sqlite+aiosqlite:///{db_file}")
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            try:
                async with session_factory() as db:
                    self._use(
                        app_env="production",
                        enable_mock_fallback=True,
                        wx_appid="",
                        wx_secret="",
                        jwt_secret="p" * 40,
                    )
                    with patch("app.api.routes_auth.httpx.AsyncClient", side_effect=AssertionError("wechat called")):
                        with self.assertRaises(HTTPException) as anon:
                            await get_current_user(authorization=None, db=db)
                        self.assertEqual(anon.exception.status_code, 401)
                        with self.assertRaises(HTTPException) as wx:
                            await wx_login(WxLoginReq(code="local-dev-code"), db)
                        self.assertEqual(wx.exception.status_code, 503)
                    self.assertEqual(await db.scalar(select(func.count()).select_from(User)), 0)

                    created = await register_web_account(
                        RegisterReq(username="student01", password="secret12"),
                        db,
                    )
                    logged = await login_web_account(
                        LoginReq(username="student01", password="secret12"),
                        db,
                    )
                    me = await get_current_user(authorization=f"Bearer {logged.token}", db=db)
                    self.assertEqual(me.username, "student01")
                    self.assertEqual(created.user.user_id, me.id)
                    self.assertFalse(me.openid.startswith("dev_"))

                async with session_factory() as db:
                    self._use(app_env="development", enable_mock_fallback=False, wx_appid="", wx_secret="")
                    with self.assertRaises(HTTPException) as closed:
                        await get_current_user(authorization=None, db=db)
                    self.assertEqual(closed.exception.status_code, 401)
                    with patch("app.api.routes_auth.httpx.AsyncClient", side_effect=AssertionError("wechat called")):
                        with self.assertRaises(HTTPException) as wx_closed:
                            await wx_login(WxLoginReq(code="local-dev-code"), db)
                    self.assertEqual(wx_closed.exception.status_code, 503)

                    self._use(app_env="development", enable_mock_fallback=True)
                    dev_user = await get_current_user(authorization=None, db=db)
                    self.assertEqual(dev_user.openid, "dev_local_user")
                    with patch("app.api.routes_auth.httpx.AsyncClient", side_effect=AssertionError("wechat called")):
                        wx_dev = await wx_login(WxLoginReq(code="local-dev-code"), db)
                    saved = await db.get(User, wx_dev.user.user_id)
                    self.assertEqual(saved.openid, "dev_local-dev-code")
            finally:
                await engine.dispose()

    def test_health_and_deploy_files_match_runtime(self):
        payload = asyncio.run(health())
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["app_env"], "development")
        paths = set(_route_paths(app.routes))
        for path in ("/health", "/", "/admin", "/api/auth/login", "/api/auth/register", "/api/auth/wx-login"):
            self.assertIn(path, paths)

        service = (ROOT / "deploy/ubuntu/zxd-ai.service").read_text(encoding="utf-8")
        runner = (ROOT / "deploy/ubuntu/run.sh").read_text(encoding="utf-8")
        nginx = (ROOT / "deploy/ubuntu/nginx/ai.islandspace.top.conf").read_text(encoding="utf-8")
        self.assertIn("User=zxd-ai", service)
        self.assertIn("/opt/zxd-ai", service)
        self.assertIn("--host 127.0.0.1", runner)
        self.assertIn("--port 8001", runner)
        self.assertNotIn("--port 8000", runner)
        self.assertIn("server_name ai.islandspace.top;", nginx)
        self.assertIn("proxy_pass http://127.0.0.1:8001;", nginx)
        self.assertNotIn("proxy_pass http://127.0.0.1:8000;", nginx)
        self.assertNotIn("islandspace.top;", nginx.replace("ai.islandspace.top;", ""))


if __name__ == "__main__":
    unittest.main()
