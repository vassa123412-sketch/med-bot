import os
import sys
import logging
from fastapi import FastAPI, Request
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import Update
from aiogram.client.session.aiohttp import AiohttpSession
from core.config import settings

# Logging setup
logging.basicConfig(
    level=settings.log_level,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

app = FastAPI()

WEBHOOK_PATH = f"/webhook/{settings.bot_token}"

# Will be initialized in startup event
bot: Bot = None
dp: Dispatcher = None


def get_session_with_proxy():
    if settings.proxy_url_socks:
        session = AiohttpSession(proxy=settings.proxy_url_socks)
    elif settings.proxy_url:
        session = AiohttpSession(proxy=settings.proxy_url)
    else:
        session = AiohttpSession()
    return session


@app.on_event("startup")
async def on_startup():
    global bot, dp

    from core.database import init_db
    await init_db()
    logger.info("Database initialized")

    session = get_session_with_proxy()
    bot = Bot(
        token=settings.bot_token,
        session=session,
        default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN),
    )
    dp = Dispatcher()

    # Register all handlers from main.py
    from bot.main import register_all_handlers
    register_all_handlers(dp, bot)

    # Set webhook URL (will retry on health check if this fails)
    RENDER_URL = os.getenv("RENDER_EXTERNAL_URL")
    if RENDER_URL:
        webhook_url = f"{RENDER_URL}{WEBHOOK_PATH}"
        try:
            await bot.set_webhook(webhook_url)
            logger.info(f"Webhook set to {webhook_url}")
        except Exception as e:
            logger.warning(f"Failed to set webhook on startup: {e}")
    else:
        logger.warning("RENDER_EXTERNAL_URL not set, webhook will be set on first health check")

    me = await bot.get_me()
    logger.info(f"Bot @{me.username} started")


@app.on_event("shutdown")
async def on_shutdown():
    if bot:
        await bot.session.close()
        logger.info("Bot stopped")


@app.post(WEBHOOK_PATH)
async def webhook(request: Request):
    try:
        data = await request.json()
        update = Update.model_validate(data)
        await dp.feed_update(bot, update)
    except Exception as e:
        logger.error(f"Webhook handler error: {e}", exc_info=True)
    return {"ok": True}


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "bot": "running" if bot else "starting",
    }
