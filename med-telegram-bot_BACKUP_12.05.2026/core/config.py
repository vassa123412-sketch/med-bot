import os
from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings

load_dotenv()


class Settings(BaseSettings):
    bot_token: str = Field(default="", alias="BOT_TOKEN")

    groq_api_key: str = Field(default="", alias="GROQ_API_KEY")
    groq_model: str = Field(default="llama-3.3-70b-versatile", alias="GROQ_MODEL")

    gemini_api_key: str = Field(default="", alias="GEMINI_API_KEY")
    gemini_model: str = Field(default="gemini-2.0-flash", alias="GEMINI_MODEL")

    openrouter_api_key: str = Field(default="", alias="OPENROUTER_API_KEY")
    openrouter_model: str = Field(default="qwen/qwen-2.5-72b-instruct", alias="OPENROUTER_MODEL")

    database_url: str = Field(default="sqlite+aiosqlite:///data/medbot.db", alias="DATABASE_URL")

    host: str = Field(default="0.0.0.0", alias="HOST")
    port: int = Field(default=8080, alias="PORT")

    log_level: str = Field(default="DEBUG", alias="LOG_LEVEL")

    # Telegram API Proxy (Happ VPN)
    proxy_url: str = Field(default="", alias="PROXY_URL")
    proxy_url_socks: str = Field(default="socks5://127.0.0.1:10809", alias="PROXY_URL_SOCKS")

    # Admin
    admin_id: int = Field(default=0, alias="ADMIN_ID")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
