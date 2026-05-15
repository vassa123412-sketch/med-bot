import os
from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings

load_dotenv()


class Settings(BaseSettings):
    bot_token: str = Field(default="", alias="BOT_TOKEN")

    gemini_api_key: str = Field(default="", alias="GEMINI_API_KEY")
    gemini_model: str = Field(default="gemini-2.0-flash", alias="GEMINI_MODEL")

    openrouter_api_key: str = Field(default="", alias="OPENROUTER_API_KEY")
    openrouter_model: str = Field(default="deepseek/deepseek-v4-flash", alias="OPENROUTER_MODEL")

    opencode_zen_api_key: str = Field(default="", alias="OPENCODE_ZEN_API_KEY")
    opencode_zen_model: str = Field(default="big-pickle", alias="OPENCODE_ZEN_MODEL")
    opencode_zen_base_url: str = Field(default="https://opencode.ai/zen/v1", alias="OPENCODE_ZEN_BASE_URL")

    database_url: str = Field(default="sqlite+aiosqlite:///data/medbot.db", alias="DATABASE_URL")

    host: str = Field(default="0.0.0.0", alias="HOST")
    port: int = Field(default=8080, alias="PORT")

    log_level: str = Field(default="DEBUG", alias="LOG_LEVEL")

    # Telegram API Proxy (Happ VPN)
    proxy_url: str = Field(default="", alias="PROXY_URL")
    proxy_url_socks: str = Field(default="", alias="PROXY_URL_SOCKS")

    # Render.com deploy flag (disables EasyOCR, enables Tesseract)
    render_deploy: bool = Field(default=False, alias="RENDER_DEPLOY")

    # Admin
    admin_id: int = Field(default=0, alias="ADMIN_ID")

    # Robokassa Payment Gateway
    robokassa_login: str = Field(default="", alias="ROBOKASSA_LOGIN")
    robokassa_password1: str = Field(default="", alias="ROBOKASSA_PASSWORD1")
    robokassa_password2: str = Field(default="", alias="ROBOKASSA_PASSWORD2")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
