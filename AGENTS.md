# AGENTS.md — Правила разработки MedAssistant Bot

## ПЕРВООЧЕРЕДНОЕ ДЕЙСТВИЕ

**При старте НОВОГО чата** (когда контекст пуст) — первым делом прочитать `MEMORY.md` и этот файл.

## Режим работы: ONLINE

Бот **уже запущен** на Render.com по адресу `https://med-bot-50on.onrender.com`.
Все изменения кода после сохранения нужно **коммитить и пушить** — Render сам подхватит и перезапустит.

```
git add -A
git commit -m "описание"
git push
```

## Автопроверка логов при ошибках

Если бот падает или пользователь сообщает об ошибке — логи на Render через Dashboard → Logs.
Локальные логи недоступны.

## Стек (актуальный)

- **Язык**: Python 3.12-slim
- **Фреймворк**: aiogram 3.27.0 + FastAPI + uvicorn
- **LLM**: Gemini 2.0 Flash → OpenRouter DeepSeek V4 Flash → OpenCode Zen Big Pickle
- **OCR**: Tesseract (на Render) / EasyOCR (локально)
- **БД**: SQLite + SQLAlchemy async (переезд на PostgreSQL в планах)
- **Прокси**: не используется на Render (пустые PROXY_URL)
- **Запуск**: uvicorn bot.webhook:app (через Docker, порт 8080)
- **Webhook**: Telegram webhook на `/webhook/{token}`
- **Health-check**: `/health`

## Запрещено

- ❌ Менять .env
- ❌ Комментировать код
- ❌ Использовать английский в ответах бота
