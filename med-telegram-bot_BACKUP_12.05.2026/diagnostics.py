"""
Диагностика подключения к Telegram API
"""
import asyncio
import sys
from datetime import datetime

def log(msg):
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] {msg}")

async def test_proxy(proxy_url):
    """Тест подключения через прокси"""
    try:
        import aiohttp
        log(f"Testing proxy: {proxy_url}")
        async with aiohttp.ClientSession() as session:
            async with session.get("https://api.telegram.org", proxy=proxy_url, timeout=10) as resp:
                log(f"Proxy test: Status {resp.status}")
                return True
    except Exception as e:
        log(f"Proxy test failed: {e}")
        return False

async def test_direct():
    """Тест прямого подключения"""
    try:
        import aiohttp
        log("Testing direct connection to api.telegram.org...")
        async with aiohttp.ClientSession() as session:
            async with session.get("https://api.telegram.org", timeout=10) as resp:
                log(f"Direct connection: Status {resp.status}")
                return True
    except asyncio.TimeoutError:
        log("Direct connection: TIMEOUT - Telegram API заблокирован!")
        return False
    except Exception as e:
        log(f"Direct connection failed: {e}")
        return False

async def test_bot_token(token):
    """Тест токена бота"""
    try:
        import aiohttp
        url = f"https://api.telegram.org/bot{token}/getMe"
        log(f"Testing bot token...")
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=10) as resp:
                data = await resp.json()
                if data.get("ok"):
                    log(f"Bot token valid! Bot: @{data['result']['username']}")
                    return True
                else:
                    log(f"Bot token invalid: {data}")
                    return False
    except asyncio.TimeoutError:
        log("Bot token test: TIMEOUT - нужно использовать прокси")
        return False
    except Exception as e:
        log(f"Bot token test failed: {e}")
        return False

async def main():
    log("=" * 60)
    log("MedAssistant - Диагностика подключения")
    log("=" * 60)
    
    # Загружаем настройки
    from dotenv import load_dotenv
    import os
    load_dotenv()
    
    token = os.getenv("BOT_TOKEN", "")
    proxy = os.getenv("PROXY_URL", "")
    
    log(f"BOT_TOKEN: {'настроен' if token else 'НЕ НАСТРОЕН'}")
    log(f"PROXY_URL: {proxy if proxy else 'НЕ НАСТРОЕН'}")
    log("-" * 60)
    
    # Тест прямого подключения
    direct_ok = await test_direct()
    
    if not direct_ok and not proxy:
        log("")
        log("=" * 60)
        log("РЕШЕНИЕ: Нужно использовать прокси для подключения к Telegram")
        log("=" * 60)
        log("")
        log("Варианты:")
        log("1. Добавьте PROXY_URL в .env файл:")
        log("   PROXY_URL=http://user:pass@proxy.example.com:port")
        log("")
        log("2. Бесплатные прокси для Telegram:")
        log("   - https://t.me/proxy_list")
        log("   - https://t.me/ProxyMTProto")
        log("")
        log("3. Или используйте VPN")
        log("")
        return
    
    # Тест прокси
    if proxy:
        proxy_ok = await test_proxy(proxy)
        if proxy_ok:
            await test_bot_token(token)
    
    if direct_ok:
        await test_bot_token(token)
    
    log("-" * 60)
    log("Диагностика завершена")

if __name__ == "__main__":
    asyncio.run(main())
