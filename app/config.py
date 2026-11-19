from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

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

    # Database & Redis
    database_url: str = "sqlite+aiosqlite:///./data/app.db"
    redis_url: str = "redis://localhost:6379/0"

    # WeChat MiniProgram & Auth
    wx_appid: str = ""
    wx_secret: str = ""
    jwt_secret: str = "dev-secret-change-in-prod"

    # Local dev helper: fallback to mock grading if API key not set
    enable_mock_fallback: bool = True

    @property
    def effective_vlm_base_url(self) -> str:
        return self.vlm_base_url or self.llm_base_url

    @property
    def effective_vlm_api_key(self) -> str:
        if self.vlm_api_key:
            return self.vlm_api_key
        if not self.vlm_base_url or self.vlm_base_url == self.llm_base_url:
            return self.llm_api_key
        return ""


settings = Settings()
