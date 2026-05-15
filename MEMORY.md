# MEMORY.md — Полный слепок проекта MedAssistant

> **Читать при старте каждого нового чата.** Этот файл автоматически обновляется после каждого изменения проекта.

---

## 1. ПОСЛЕДНЕЕ СОСТОЯНИЕ (на 09.05.2026)

### Бот упал с ошибкой
```
ModuleNotFoundError: No module named 'core'
```
**Причина:** `запустить_бота.bat` содержит `python bot/main.py` (строка 13). При таком запуске Python добавляет в `sys.path` папку `bot/`, а не корень проекта → `from core.config import settings` не находит пакет `core`.

**Исправление:** заменить на `python -m bot.main` (уже сделано).

### Прокси
- **Работает:** `PROXY_URL=http://127.0.0.1:10809` (HTTP, Happ VPN)
- **Не работает:** `socks5://127.0.0.1:10809` — таймаут 60с
- `AiohttpSession(proxy=...)` принимает строку URL
- Кастомный `ClientTimeout` НЕ передавать — конфликт с aiogram

### Монетизация
- 3 бесплатных анализа/день (проверка в `check_usage_limit`)
- Кнопка `💰 Поддержать проект` в главном меню
- CPA-партнёрки (Invitro, Gemotest, ProDoctorov) — гайд в `experts/growth_marketer.md`
- PDF отчёт (через `reports/pdf_generator.py`) — пока бесплатно, планируется Telegram Stars (50–100 Stars)

---

## 2. СТЕК

| Компонент | Технология |
|-----------|-----------|
| Язык | Python 3.14 |
| Фреймворк | aiogram 3.27.0 |
| LLM #1 | Groq — `llama-3.3-70b-versatile` |
| LLM #2 (fallback) | OpenRouter — `qwen-2.5-72b` |
| LLM #3 (блокирован) | Gemini 2.0 Flash (429 ResourceExhausted) |
| OCR | EasyOCR (ленивая загрузка) |
| БД | SQLite + SQLAlchemy (async) |
| Web | FastAPI (dashboard) |
| PDF | `reports/pdf_generator.py` |
| База знаний | `api/medical_kb.py` (157 болезней, 491 симптом с GitHub) |
| Прокси | HTTP `http://127.0.0.1:10809` (Happ VPN) |

---

## 3. ЗАПУСК

```powershell
# ТОЛЬКО ТАК (работает):
cd C:\Users\K\OneDrive\Desktop\Медицинский асистент\med-telegram-bot
python start.py

# ИЛИ ТАК:
python -m bot.main

# НЕ РАБОТАЕТ (ошибка импорта):
python bot/main.py
python bot\main.py
запустить_бота.bat   # пока не исправлен (использует python bot/main.py)
```

---

## 4. СТРУКТУРА ПРОЕКТА

```
med-telegram-bot/
├── start.py              # Точка входа (os.chdir + python -m bot.main)
├── AGENTS.md             # Правила для агента
├── MEMORY.md             # Слепок проекта (этот файл)
├── requirements.txt
├── .env / .env.example
├── bot/
│   ├── main.py           # Точка входа aiogram, все хендлеры
│   ├── keyboards.py      # Клавиатуры (вкл. кнопку доната)
│   ├── states.py         # FSM состояния (LabAnalysis, SymptomAnalysis)
│   └── handlers/
│       └── symptoms.py   # Хендлеры симптомов + DB save
├── core/
│   ├── config.py         # Настройки из .env
│   ├── database.py       # Асинхронная БД (get_session с @asynccontextmanager)
│   ├── models.py         # Модели SQLAlchemy
│   └── llm_client.py     # LLM-клиент (Groq→Gemini→OpenRouter), OCR, распознавание
├── api/
│   └── medical_kb.py     # База знаний (болезни, симптомы)
├── dashboard/
│   └── app.py            # FastAPI веб-дашборд
├── reports/
│   └── pdf_generator.py  # Генерация PDF-отчётов с графиками
├── experts/
│   ├── chief_medical_officer.md   # Медицинская безопасность
│   ├── growth_marketer.md         # Монетизация (CPA, Telegram Stars)
│   └── qa_tester.md              # Тест-кейсы
├── logs/
│   ├── errors.log        # Ошибки приложения
│   └── bot.log           # Полный лог бота
└── docker/               # Docker-файлы
```

---

## 5. ОШИБКИ (текущие и решённые)

### Открытые
- **Gemini 429** — ключ `...DvNM` исчерпал квоту, нужен новый ключ
- **SOCKS5 таймаут** — Happ VPN не поддерживает SOCKS5? Или `aiohttp-socks` конфликтует
- **`Can't parse entities`** — LLM иногда выдаёт Markdown с неэкранированными символами (`Bad Request: can't parse entities: Can't find end of the entity`)

### Решённые
- ✅ `async_generator` context manager error → `@asynccontextmanager` на `get_session()`, `async for` → `async with`
- ✅ `Unclosed client session` / `Unclosed connector` при использовании SOCKS5
- ✅ `ClientTimeout + int` — кастомный таймаут убран
- ✅ `Photo processing failed: No text found` — EasyOCR не находит текст (может быть нормально для нечётких фото)

---

## 6. ПРАВИЛА ДЛЯ АГЕНТА

1. **При старте** → прочитать `MEMORY.md` и `AGENTS.md`
2. **При ошибке** → прочитать `logs/errors.log`, потом `logs/bot.log` (последние 50 строк)
3. **Не задавать лишних вопросов** — анализировать логи и чинить самому
4. **Язык ответов бота** — строго русский, ноль английских слов
5. **Позиционирование** — информационный ассистент, а не врач (никаких диагнозов и дозировок)
6. **Коммиты** — только по явному разрешению
7. **Комментарии в коде** — запрещены
8. **Изменения .env** — запрещены (кроме прокси)

---

## 7. ПОСЛЕДНИЕ ИЗМЕНЕНИЯ (09.05.2026)

### Добавлена админ-панель статистики
- Создан `core/rate_limiter.py` — in-memory трекер запросов (слайд-окно)
- `RateStats.record()` вызывается в `StatsMiddleware` на каждое сообщение
- Запись занимает O(1), никаких блокировок — не тормозит пользователей
- Добавлен `ADMIN_ID` в `.env` и `config.py`
- Команда `/stats` — общая статистика (запросы за час/сутки, активные юзеры, топ-10)
- Команда `/user <id>` — статистика конкретного пользователя

### Фикс батника
- `запустить_бота.bat` исправлен: `python bot/main.py` → `python -m bot.main`
- Причина падения: `python bot/main.py` не видит пакет `core`

### Новые файлы
| Файл | Назначение |
|------|-----------|
| `core/rate_limiter.py` | In-memory трекер запросов |
| `MEMORY.md` | Слепок проекта для быстрого старта нового чата |

## 8. БЛИЖАЙШИЕ ДОРАБОТКИ (Next Steps)

- [ ] Протестировать лимит 3/дня — убедиться что `check_usage_limit` блокирует 4-й запрос
- [ ] Протестировать CPA-ссылки (Invitro, ProDoctorov)
- [ ] Добавить напоминание "Сохранить PDF?" после каждого анализа
- [ ] Telegram Stars paywall (50–100 Stars) за PDF
- [ ] Новый Gemini-ключ для разблокировки fallback
- [ ] Проверить `/stats` и `/user` в работе

---

## 8. КОНТАКТЫ БОТА

- Username: `@Med24AssistantBot`
- Display name: `@MedAssistAIBot`
- Назначение: расшифровка анализов (OCR), оценка симптомов, ответы на медицинские вопросы
