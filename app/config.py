from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_SQLITE_PREFIX = "sqlite+aiosqlite:///"
_PRODUCTION_DB_NAME = "zxd-ai.db"

# 这些字符串来自代码默认值或仓库示例，出现即视为未配置。
_JWT_PLACEHOLDERS = (
    "dev-secret-change-in-prod",
    "change-me-in-production-secret-key",
    "change-me",
    "请替换为至少32位随机字符串",
    "__set_on_server__",
)
_ADMIN_DEFAULT_PASSWORD = "admin123"
_ADMIN_UNSET_PLACEHOLDERS = (
    "change-me-strong-admin-password",
    "change-me",
    "请替换为强管理员密码",
    "__set_on_server__",
)
_KEY_PLACEHOLDERS = (
    "sk-your-",
    "your-api-key",
    "your-vlm-api-key",
    "__set_on_server__",
    "change-me",
    "替换",
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # development：本地联调，允许示例里的默认秘密与 Mock。
    # production：fail-closed，默认秘密、匿名用户和开发微信身份都不能启动或生效。
    app_env: str = "development"

    # Text LLM for grading & rewriting
    llm_base_url: str = "https://api.deepseek.com/v1"
    llm_api_key: str = ""
    llm_model: str = "deepseek-chat"

    # Vision LLM for handwriting OCR (optional; falls back to text LLM config if empty)
    vlm_base_url: str = ""
    vlm_api_key: str = ""
    vlm_model: str = "qwen-vl-max"

    llm_temperature: float = 0.15
    llm_timeout_seconds: int = 60

    # 新库必须在生产环境显式指向绝对路径 zxd-ai.db。开发默认仍是本地相对库。
    database_url: str = "sqlite+aiosqlite:///./data/app.db"
    # 当前版本没有任何代码读取 Redis。留空，避免误连本机已有实例。
    redis_url: str = ""

    # WeChat MiniProgram & Auth
    wx_appid: str = ""
    wx_secret: str = ""
    jwt_secret: str = "dev-secret-change-in-prod"
    admin_password: str = "admin123"

    # 逗号分隔的浏览器源。生产环境留空表示只允许同源；禁止 *。
    cors_origins: str = ""

    # Local dev helper: fallback to mock grading if API key not set
    enable_mock_fallback: bool = True

    # 生产默认拒绝短口令和代码内默认管理员口令。只有显式设为 true 才允许运营者自行承担风险。
    allow_weak_admin_password: bool = False

    @property
    def normalized_app_env(self) -> str:
        return self.app_env.strip().lower()

    @property
    def is_production(self) -> bool:
        return self.normalized_app_env == "production"

    @property
    def is_development(self) -> bool:
        return self.normalized_app_env == "development"

    def key_is_configured(self, value: str) -> bool:
        text = (value or "").strip()
        if not text:
            return False
        lowered = text.lower()
        return not any(marker in lowered for marker in _KEY_PLACEHOLDERS)

    @property
    def wechat_is_configured(self) -> bool:
        return self.key_is_configured(self.wx_appid) and self.key_is_configured(self.wx_secret)

    @property
    def allows_anonymous_dev_user(self) -> bool:
        return self.is_development and self.enable_mock_fallback

    @property
    def allows_dev_wechat_identity(self) -> bool:
        return self.is_development and self.enable_mock_fallback and not self.wechat_is_configured

    def inference_mode(self, api_key: str) -> str:
        """live：使用已配置密钥。mock：仅开发且显式开启回退。unavailable：拒绝调用模型。"""
        if self.key_is_configured(api_key):
            return "live"
        if self.allows_anonymous_dev_user:
            return "mock"
        return "unavailable"

    @property
    def effective_vlm_base_url(self) -> str:
        return self.vlm_base_url or self.llm_base_url

    @property
    def effective_vlm_api_key(self) -> str:
        if self.key_is_configured(self.vlm_api_key):
            return self.vlm_api_key.strip()
        same_endpoint = not self.vlm_base_url or self.vlm_base_url == self.llm_base_url
        if same_endpoint and self.key_is_configured(self.llm_api_key):
            return self.llm_api_key.strip()
        return ""

    def parsed_cors_origins(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]


def _sqlite_filesystem_path(database_url: str) -> str | None:
    if not database_url.startswith(_SQLITE_PREFIX):
        return None
    return database_url[len(_SQLITE_PREFIX) :]


def _contains_placeholder(value: str, placeholders: tuple[str, ...]) -> bool:
    lowered = value.lower()
    return any(item.lower() in lowered for item in placeholders)


def _admin_password_rejected(admin: str, allow_weak: bool) -> bool:
    """空白和未配置占位符始终拒绝。弱口令只在专用开关精确为 true 时放行。"""
    if admin != admin.strip() or not admin.strip():
        return True
    password = admin.strip()
    if _contains_placeholder(password, _ADMIN_UNSET_PLACEHOLDERS):
        return True
    if allow_weak:
        return False
    return len(password) < 12 or _contains_placeholder(password, (_ADMIN_DEFAULT_PASSWORD,))


def production_security_errors(cfg: Settings) -> list[str]:
    """返回阻止生产启动的原因。只包含变量名，不回显秘密本身。"""
    env_name = cfg.normalized_app_env
    if env_name not in {"development", "production"}:
        return ["APP_ENV 只能是 development 或 production"]
    if not cfg.is_production:
        return []

    errors: list[str] = []
    jwt = cfg.jwt_secret or ""
    admin = cfg.admin_password or ""
    if jwt != jwt.strip() or len(jwt.strip()) < 32 or _contains_placeholder(jwt.strip(), _JWT_PLACEHOLDERS):
        errors.append("JWT_SECRET 未设置为至少 32 位的非默认值")
    if _admin_password_rejected(admin, cfg.allow_weak_admin_password is True):
        errors.append("ADMIN_PASSWORD 未设置为至少 12 位的非默认值")
    if jwt.strip() and admin.strip() and jwt.strip() == admin.strip():
        errors.append("JWT_SECRET 与 ADMIN_PASSWORD 不能相同")
    if cfg.enable_mock_fallback:
        errors.append("ENABLE_MOCK_FALLBACK 在生产环境必须为 false")

    db_path = _sqlite_filesystem_path(cfg.database_url.strip())
    if (
        db_path is None
        or not db_path.startswith("/")
        or ".." in Path(db_path).parts
        or Path(db_path).name != _PRODUCTION_DB_NAME
    ):
        errors.append("DATABASE_URL 必须是绝对路径 SQLite，且文件名为 zxd-ai.db")
    if cfg.redis_url.strip():
        errors.append("REDIS_URL 必须留空，此服务不连接 Redis")

    for origin in cfg.parsed_cors_origins():
        if origin == "*" or not origin.startswith("https://") or "/" in origin[len("https://") :]:
            errors.append("CORS_ORIGINS 只能是逗号分隔的 https 源，不能为 *")
            break
    return errors


def enforce_production_security(cfg: Settings) -> None:
    errors = production_security_errors(cfg)
    if errors:
        raise RuntimeError("拒绝启动: " + "; ".join(errors))


def build_cors_middleware_kwargs(cfg: Settings) -> dict[str, object]:
    if cfg.is_production:
        origins = cfg.parsed_cors_origins()
        return {
            "allow_origins": origins,
            "allow_credentials": False,
            "allow_methods": ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
            "allow_headers": ["Authorization", "Content-Type", "X-Admin-Password"],
        }
    return {
        "allow_origins": ["*"],
        "allow_credentials": False,
        "allow_methods": ["*"],
        "allow_headers": ["*"],
    }


settings = Settings()
try:
    enforce_production_security(settings)
except RuntimeError as exc:
    raise SystemExit(str(exc)) from None
