"""打印不含秘密的生产预检结果。systemd 在启动前调用。"""

from app.config import settings


def main() -> int:
    if not settings.is_production:
        print("preflight_failed app_env_not_production")
        return 2
    filename = "unset"
    marker = "sqlite+aiosqlite:///"
    if settings.database_url.startswith(marker):
        filename = settings.database_url[len(marker) :].rstrip("/").split("/")[-1]
    print("preflight_ok")
    print(f"app_env={settings.normalized_app_env}")
    print(f"database_filename={filename}")
    print(f"mock_fallback={'true' if settings.enable_mock_fallback else 'false'}")
    print(f"llm_configured={'yes' if settings.key_is_configured(settings.llm_api_key) else 'no'}")
    print(
        "vlm_configured="
        + ("yes" if settings.key_is_configured(settings.effective_vlm_api_key) else "no")
    )
    print(f"wx_configured={'yes' if settings.wechat_is_configured else 'no'}")
    print(f"cors_origin_count={len(settings.parsed_cors_origins())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
