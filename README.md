# 🏥 МедАссистент — Медицинский Telegram-бот

**@Med24AssistantBot** — AI-powered медицинский информационный помощник для пациентов.

---

## 🚀 Быстрый старт

```bash
# 1. Клонировать репозиторий
git clone <repo-url>
cd med-telegram-bot

# 2. Создать .env файл
cp .env.example .env
# Заполнить BOT_TOKEN, GROQ_API_KEY, GEMINI_API_KEY

# 3. Установить зависимости
pip install -r requirements.txt

# 4. Запустить бота
python bot/main.py
```

---

## 📋 Что умеет бот

| Функция | Описание |
|---------|----------|
| 🔍 Анализ симптомов | Опишите симптомы → бот анализирует и даёт рекомендации |
| 📊 Анализ анализов | Отправьте фото/файл анализов → бот интерпретирует |
| 📋 Мои записи | История консультаций |
| 🚨 Emergency flow | При экстренных симптомах — немедленно рекомендует скорую |

---

## 🏗️ Архитектура

```
├── bot/                    # Telegram бот (aiogram)
│   ├── main.py             # Точка входа
│   ├── handlers/           # Обработчики команд
│   ├── keyboards.py        # Inline/Reply клавиатуры
│   └── states.py           # FSM состояния
├── core/                   # Ядро системы
│   ├── config.py           # Настройки
│   ├── database.py         # База данных (SQLite)
│   └── llm_client.py       # LLM клиент с резервированием
├── analysis/               # Анализ данных
├── experts/                # Промпты экспертов
├── docs/                   # Документация
│   ├── legal/              # Юридические документы
│   ├── design/             # Дизайн guidelines
│   └── security/           # Безопасность
├── docker/                 # Docker конфигурация
└── data/                   # Данные (gitignore)
```

---

## 🤖 LLM Модели (бесплатные)

| Приоритет | Модель | Провайдер |
|-----------|--------|-----------|
| Основная | Llama 3.1 70B | Groq |
| Backup 1 | Gemini 2.0 Flash | Google |
| Backup 2 | Qwen 2.5 72B | OpenRouter |
| Fallback | Qwen 2.5 14B | Ollama (локально) |

---

## ⚠️ Дисклеймер

Бот предоставляет **исключительно информационно-справочные материалы**. Бот **НЕ ставит диагнозы** и **НЕ назначает лечение**. Для медицинской консультации обратитесь к врачу.

---

## 📄 Документация

- [Terms of Service](docs/legal/terms_of_service.md)
- [Privacy Policy](docs/legal/privacy_policy.md)
- [Medical Disclaimer](docs/legal/medical_disclaimer.md)

---

## 📞 Контакты

- Telegram: @Med24AssistantBot
- Email: support@medassistant.ru

---

## 📜 Лицензия

MIT © 2026
