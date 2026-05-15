import asyncio
import logging
import sys
import os
import glob
from aiogram import Bot, Dispatcher, types, F, BaseMiddleware
from aiogram.types import FSInputFile
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from core.config import settings
from core.database import init_db, get_session, User, Consultation, check_usage_limit, increment_usage, update_last_symptom_analysis, check_symptom_analysis_cooldown, get_or_create_referral_code, process_referral, get_free_analyses, use_free_analysis, get_referral_stats, limit_message, PREMIUM_FOOTER, get_loading_text
from core.llm_client import llm_client
from core.rate_limiter import rate_stats
from api.medical_kb import medical_kb
from bot.keyboards import (
    get_main_keyboard, get_time_keyboard, get_temperature_keyboard, 
    get_gender_keyboard, get_age_keyboard, get_result_keyboard, get_back_to_menu_keyboard,
    get_handwriting_result_keyboard,
    get_admin_keyboard,
)
from bot.states import SymptomAnalysis, HandwritingAnalysis, AdminActions
from reports.pdf_generator import create_pdf_report

logging.basicConfig(
    level=settings.log_level,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('logs/bot.log', encoding='utf-8'),
    ]
)

error_handler = logging.FileHandler('logs/errors.log', encoding='utf-8')
error_handler.setLevel(logging.ERROR)
error_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logging.getLogger().addHandler(error_handler)
logger = logging.getLogger(__name__)

# ================= ДИЗАЙН-СИСТЕМА =================
SEP = "────────────────────"

LOADING_PHRASES = [
    "🧬 Анализирую ваши данные...",
    "🔬 Сверяюсь с медицинской базой знаний...",
    "📊 Обрабатываю информацию...",
    "🩺 Консультируюсь с протоколами...",
    "⚕️ Проверяю рекомендации...",
    "💊 Готовлю заключение...",
]

PREMIUM_FOOTER = f"\n\n{SEP}\n💡 Хотите безлимитный доступ? Подпишитесь на премиум!"


def get_loading_text():
    import random
    return random.choice(LOADING_PHRASES)


def limit_message() -> str:
    """Единый шаблон сообщения об исчерпанном лимите."""
    return (
        f"⏳ **Дневной лимит исчерпан**\n{SEP}\n\n"
        f"Вы использовали 3 бесплатных анализа на сегодня.\n\n"
        f"🔹 Вернитесь завтра — лимит обновится в 00:00\n"
        f"🔹 Пригласите друга — получите **+1 бесплатный анализ** 🎁\n\n"
        f"👇 Вернитесь в меню"
    )


def get_session_with_proxy():
    if settings.proxy_url_socks:
        logger.info(f"Using SOCKS5 proxy: {settings.proxy_url_socks}")
        session = AiohttpSession(proxy=settings.proxy_url_socks)
    elif settings.proxy_url:
        logger.info(f"Using HTTP proxy: {settings.proxy_url}")
        session = AiohttpSession(proxy=settings.proxy_url)
    else:
        logger.info("No proxy configured, using direct connection")
        session = AiohttpSession()
    return session


async def main():
    logger.info("=" * 50)
    logger.info("MedAssistant Bot - Starting...")
    logger.info("=" * 50)

    try:
        await init_db()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Database init failed: {e}")
        return

    session = get_session_with_proxy()
    bot_properties = DefaultBotProperties(parse_mode=ParseMode.MARKDOWN)
    bot = Bot(token=settings.bot_token, session=session, default=bot_properties)
    dp = Dispatcher()

    class StatsMiddleware(BaseMiddleware):
        async def __call__(self, handler, event, data):
            if hasattr(event, 'from_user') and event.from_user:
                rate_stats.record(event.from_user.id)
            return await handler(event, data)

    dp.message.middleware.register(StatsMiddleware())

    try:
        me = await bot.get_me()
        logger.info(f"Bot connected! Username: @{me.username}, ID: {me.id}")
        logger.info(f"Bot name: {me.first_name}")
    except Exception as e:
        logger.error(f"Failed to connect to Telegram API: {e}")
        return

    @dp.message(CommandStart())
    async def cmd_start(message: types.Message, state: FSMContext):
        await state.clear()

        # Parse referral code from deep link
        referral_code = None
        args = message.text.split()
        if len(args) > 1 and args[1].startswith("ref_"):
            referral_code = args[1]

        try:
            async with get_session() as session_db:
                from sqlalchemy import select, update
                result = await session_db.execute(select(User).filter(User.telegram_id == message.from_user.id))
                user = result.scalar_one_or_none()
                if not user:
                    user = User(telegram_id=message.from_user.id, username=message.from_user.username, first_name=message.from_user.first_name)
                    session_db.add(user)
                    await session_db.commit()

                    # Process referral for new users
                    if referral_code:
                        await process_referral(message.from_user.id, referral_code)
                        free_count = await get_free_analyses(message.from_user.id)
                        extras = f"\n\n🎁 **Вам начислен 1 бесплатный анализ по реферальной ссылке!**" if free_count > 0 else ""
                else:
                    await session_db.execute(update(User).where(User.telegram_id == message.from_user.id).values(username=message.from_user.username, first_name=message.from_user.first_name))
                    await session_db.commit()
                    extras = ""
        except Exception as e:
            logger.error(f"Error saving user: {e}")
            extras = ""
        await message.answer(
            f"🔬 **Демо медицинского AI-бота**\n{SEP}\n\n"
            f"Этот бот показывает, как работает искусственный интеллект в медицине:\n\n"
            f"🔍 Анализ симптомов — опишите жалобы, получите разбор\n"
            f"✍️ Распознавание почерка — AI расшифрует рукописный текст\n"
            f"🎁 Бесплатный доступ — протестируйте все функции\n\n"
            f"{SEP}\n"
            f"💼 **Хотите такой же бот для вашего бизнеса?**\n"
            f"👉 @Ivan_Zadov — разработка Telegram-ботов под ключ\n\n"
            f"⚠️ *Результаты не являются медицинским диагнозом.*"
            f"{extras}",
            reply_markup=get_main_keyboard(),
        )

    @dp.message(Command("help"))
    async def cmd_help(message: types.Message):
        await message.answer(
            f"📋 **Помощь**\n{SEP}\n\n"
            f"🩺 **МедАссистент** умеет:\n\n"
            f"🔍 Анализ симптомов — расскажите что беспокоит\n"
            f"🔬 Расшифровка анализов — отправьте фото результатов\n"
            f"✍️ Распознавание почерка — разберём рукописный текст\n"
            f"🎁 Бесплатный анализ — пригласите друга\n"
            f"🚑 Экстренная помощь — номера 103 / 112\n\n"
            f"{SEP}\n"
            f"⚠️ Я не заменяю врача. Все результаты — ознакомительные.",
        )

    # --- Admin Commands ---

    def is_admin(user_id: int) -> bool:
        return settings.admin_id and user_id == settings.admin_id

    @dp.message(Command("stats"))
    async def cmd_stats(message: types.Message):
        if not is_admin(message.from_user.id):
            return
        last_hour_req = rate_stats.get_total_requests(3600)
        last_day_req = rate_stats.get_total_requests(86400)
        active_5m = rate_stats.get_active_users(300)
        active_1h = rate_stats.get_active_users(3600)
        top_users = rate_stats.get_top_users(10, 3600)

        lines = [
            "📊 **Статистика бота**",
            f"",
            f"**Запросы:**",
            f"  · за час: {last_hour_req}",
            f"  · за сутки: {last_day_req}",
            f"",
            f"**Активные пользователи:**",
            f"  · за 5 мин: {active_5m}",
            f"  · за час: {active_1h}",
            f"",
            f"**Топ-10 за час:**",
        ]
        if top_users:
            for uid, count in top_users:
                lines.append(f"  · `{uid}` — {count} запр.")
        else:
            lines.append(f"  · нет данных")

        lines.extend([
            f"",
            f"⚙️ Лимит: {rate_stats.limit} запр./{rate_stats.window}с",
        ])
        await message.answer("\n".join(lines))

    @dp.message(Command("user"))
    async def cmd_user(message: types.Message):
        if not is_admin(message.from_user.id):
            return
        args = message.text.split(maxsplit=1)
        if len(args) < 2:
            await message.answer("Укажи ID пользователя:\n`/user 123456789`")
            return
        try:
            uid = int(args[1])
        except ValueError:
            await message.answer("ID должен быть числом.")
            return
        
        async with get_session() as session_db:
            from sqlalchemy import select
            result = await session_db.execute(select(User).filter(User.telegram_id == uid))
            user = result.scalar_one_or_none()
            if not user:
                await message.answer(f"❌ Пользователь `{uid}` не найден в БД.")
                return

            count_5m = rate_stats.get_count(uid, 300)
            count_1h = rate_stats.get_count(uid, 3600)
            count_24h = rate_stats.get_count(uid, 86400)

            await message.answer(
                f"👤 **Пользователь `{uid}`**\n\n"
                f"├ Имя: {user.first_name or '—'}\n"
                f"├ Юзернейм: @{user.username or '—'}\n"
                f"├ Регистрация: {user.created_at.strftime('%d.%m.%Y %H:%M') if user.created_at else '—'}\n"
                f"├ Запросов сегодня: {user.daily_requests}/3\n"
                f"├ Последний запрос: {user.last_request_date.strftime('%d.%m %H:%M') if user.last_request_date else '—'}\n"
                f"├ Бесплатных анализов: {user.free_analyses}\n"
                f"├ Рефералов привёл: {user.referral_code or '—'}\n"
                f"└ Пришёл по рефералу от: {user.referred_by or '—'}\n\n"
                f"📊 **Rate лимиты:**\n"
                f"· за 5 мин: {count_5m}\n"
                f"· за час: {count_1h}\n"
                f"· за сутки: {count_24h}"
            )

    @dp.message(Command("reset"))
    async def cmd_reset(message: types.Message):
        if not is_admin(message.from_user.id):
            return
        args = message.text.split(maxsplit=1)
        if len(args) < 2:
            await message.answer("Укажи ID пользователя:\n`/reset 123456789`")
            return
        try:
            uid = int(args[1])
        except ValueError:
            await message.answer("ID должен быть числом.")
            return

        async with get_session() as session_db:
            from sqlalchemy import update
            await session_db.execute(
                update(User).where(User.telegram_id == uid).values(
                    daily_requests=0,
                    last_request_date=None,
                    last_symptom_analysis=None,
                )
            )
            await session_db.commit()
        await message.answer(f"✅ Лимиты пользователя `{uid}` сброшены (daily_requests, кулдаун).")

    @dp.message(Command("addfree"))
    async def cmd_addfree(message: types.Message):
        if not is_admin(message.from_user.id):
            return
        args = message.text.split(maxsplit=2)
        if len(args) < 3:
            await message.answer("Укажи ID и количество:\n`/addfree 123456789 5`")
            return
        try:
            uid = int(args[1])
            count = int(args[2])
        except ValueError:
            await message.answer("ID и количество должны быть числами.")
            return

        async with get_session() as session_db:
            from sqlalchemy import update, select
            result = await session_db.execute(select(User).filter(User.telegram_id == uid))
            user = result.scalar_one_or_none()
            if not user:
                await message.answer(f"❌ Пользователь `{uid}` не найден.")
                return

            await session_db.execute(
                update(User).where(User.telegram_id == uid).values(
                    free_analyses=User.free_analyses + count
                )
            )
            await session_db.commit()
        await message.answer(f"✅ Пользователю `{uid}` добавлено **+{count}** бесплатных анализов.")

    @dp.message(Command("admin"))
    async def cmd_admin(message: types.Message):
        if not is_admin(message.from_user.id):
            return

        await message.answer(
            f"👑 **Админ-панель**\n\n"
            f"Выберите действие:",
            reply_markup=get_admin_keyboard(),
        )

    # --- Admin Callbacks ---

    @dp.callback_query(F.data == "admin_me")
    async def admin_me(callback: types.CallbackQuery):
        if not is_admin(callback.from_user.id):
            return await callback.answer()
        uid = callback.from_user.id
        async with get_session() as session_db:
            from sqlalchemy import select
            result = await session_db.execute(select(User).filter(User.telegram_id == uid))
            user = result.scalar_one_or_none()
            if not user:
                await callback.message.answer("❌ Не найден.")
                return await callback.answer()

            await callback.message.answer(
                f"👤 **Информация**\n\n"
                f"├ Имя: {user.first_name or '—'}\n"
                f"├ Юзернейм: @{user.username or '—'}\n"
                f"├ Регистрация: {user.created_at.strftime('%d.%m.%Y %H:%M') if user.created_at else '—'}\n"
                f"├ Запросов сегодня: {user.daily_requests}/3\n"
                f"├ Бесплатных анализов: {user.free_analyses}\n"
                f"├ Рефералов привёл: {user.referral_code or '—'}\n"
                f"└ Пришёл по рефералу от: {user.referred_by or '—'}"
            )
        await callback.answer()

    @dp.callback_query(F.data == "admin_reset_me")
    async def admin_reset_me(callback: types.CallbackQuery):
        if not is_admin(callback.from_user.id):
            return await callback.answer()
        uid = callback.from_user.id
        async with get_session() as session_db:
            from sqlalchemy import update
            await session_db.execute(
                update(User).where(User.telegram_id == uid).values(
                    daily_requests=0, last_request_date=None, last_symptom_analysis=None,
                )
            )
            await session_db.commit()
        await callback.message.answer("✅ Мои лимиты сброшены.")
        await callback.answer()

    @dp.callback_query(F.data.startswith("admin_addfree_"))
    async def admin_addfree(callback: types.CallbackQuery):
        if not is_admin(callback.from_user.id):
            return await callback.answer()
        count = int(callback.data.split("_")[2])
        uid = callback.from_user.id
        async with get_session() as session_db:
            from sqlalchemy import update
            await session_db.execute(
                update(User).where(User.telegram_id == uid).values(
                    free_analyses=User.free_analyses + count
                )
            )
            await session_db.commit()
        await callback.message.answer(f"✅ Добавлено **+{count}** бесплатных анализов.")
        await callback.answer()

    @dp.callback_query(F.data == "admin_user_other")
    async def admin_user_other(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            return await callback.answer()
        await state.set_state(AdminActions.waiting_for_user_id)
        await callback.message.answer("🔍 Введите Telegram ID пользователя:")
        await callback.answer()

    @dp.callback_query(F.data == "admin_reset_other")
    async def admin_reset_other(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            return await callback.answer()
        await state.set_state(AdminActions.waiting_for_user_id_reset)
        await callback.message.answer("🔄 Введите Telegram ID пользователя для сброса:")
        await callback.answer()

    @dp.callback_query(F.data == "admin_stats")
    async def admin_stats_cb(callback: types.CallbackQuery):
        if not is_admin(callback.from_user.id):
            return await callback.answer()
        last_hour_req = rate_stats.get_total_requests(3600)
        last_day_req = rate_stats.get_total_requests(86400)
        active_5m = rate_stats.get_active_users(300)
        active_1h = rate_stats.get_active_users(3600)
        top_users = rate_stats.get_top_users(10, 3600)

        lines = [
            "📊 **Статистика бота**",
            f"",
            f"**Запросы:**",
            f"  · за час: {last_hour_req}",
            f"  · за сутки: {last_day_req}",
            f"",
            f"**Активные пользователи:**",
            f"  · за 5 мин: {active_5m}",
            f"  · за час: {active_1h}",
            f"",
            f"**Топ-10 за час:**",
        ]
        if top_users:
            for uid, count in top_users:
                lines.append(f"  · `{uid}` — {count} запр.")
        else:
            lines.append(f"  · нет данных")
        await callback.message.answer("\n".join(lines))
        await callback.answer()

    @dp.callback_query(F.data == "admin_close")
    async def admin_close(callback: types.CallbackQuery):
        if not is_admin(callback.from_user.id):
            return await callback.answer()
        await callback.message.delete()
        await callback.answer()

    # --- Admin message handlers (waiting for ID) ---

    @dp.message(AdminActions.waiting_for_user_id)
    async def admin_handle_user_id(message: types.Message, state: FSMContext):
        if not is_admin(message.from_user.id):
            return await state.clear()
        try:
            uid = int(message.text.strip())
        except ValueError:
            await message.answer("❌ ID должен быть числом. Попробуйте ещё раз или /admin.")
            return
        async with get_session() as session_db:
            from sqlalchemy import select
            result = await session_db.execute(select(User).filter(User.telegram_id == uid))
            user = result.scalar_one_or_none()
            if not user:
                await message.answer(f"❌ Пользователь `{uid}` не найден.")
            else:
                await message.answer(
                    f"👤 **Пользователь `{uid}`**\n\n"
                    f"├ Имя: {user.first_name or '—'}\n"
                    f"├ Юзернейм: @{user.username or '—'}\n"
                    f"├ Запросов сегодня: {user.daily_requests}/3\n"
                    f"├ Бесплатных анализов: {user.free_analyses}\n"
                    f"├ Рефералов привёл: {user.referral_code or '—'}\n"
                    f"└ Пришёл по рефералу от: {user.referred_by or '—'}"
                )
        await state.clear()

    @dp.message(AdminActions.waiting_for_user_id_reset)
    async def admin_handle_reset_id(message: types.Message, state: FSMContext):
        if not is_admin(message.from_user.id):
            return await state.clear()
        try:
            uid = int(message.text.strip())
        except ValueError:
            await message.answer("❌ ID должен быть числом. Попробуйте ещё раз или /admin.")
            return
        async with get_session() as session_db:
            from sqlalchemy import update
            await session_db.execute(
                update(User).where(User.telegram_id == uid).values(
                    daily_requests=0, last_request_date=None, last_symptom_analysis=None,
                )
            )
            await session_db.commit()
        await message.answer(f"✅ Лимиты пользователя `{uid}` сброшены.")
        await state.clear()

    # --- Symptom Analysis Flow ---

    @dp.message(F.text == "🔍 Анализ симптомов")
    async def start_symptom_analysis(message: types.Message, state: FSMContext):
        await state.set_state(SymptomAnalysis.waiting_for_symptoms)
        await message.answer(
            f"🔍 **Анализ симптомов**\n{SEP}\n\n"
            f"●○○○○ Шаг 1 из 5\n\n"
            f"Что вас беспокоит? Чем подробнее — тем точнее анализ.\n\n"
            f"✍️ _Например: Болит голова третий день, подташнивает_"
        )

    @dp.message(SymptomAnalysis.waiting_for_symptoms)
    async def process_symptoms(message: types.Message, state: FSMContext):
        text = message.text.strip()

        # --- Check Free Analyses first, then daily limit ---
        free_count = await get_free_analyses(message.from_user.id)
        if free_count > 0:
            await state.update_data(using_free=True)
        else:
            await state.update_data(using_free=False)
            can_proceed, count = await check_usage_limit(message.from_user.id)
            if not can_proceed:
                await state.clear()
                await message.answer(limit_message(), reply_markup=get_main_keyboard())
                return

        # --- Emergency Detection ---
        EMERGENCY_KEYWORDS = [
            "112", "скорая", "умираю", "не могу дышать", "задыхаюсь",
            "сильное кровотечение", "кровь не останавливается", "потеря сознания",
            "инсульт", "инфаркт", "сердце остановилось", "анафилакси",
            "отек квинке", "судороги", "термический ожог", "химический ожог",
        ]
        text_lower = text.lower()
        for kw in EMERGENCY_KEYWORDS:
            if kw in text_lower:
                await state.clear()
                await message.answer(
                    f"🚨 **ЭКСТРЕННАЯ СИТУАЦИЯ**\n{SEP}\n\n"
                    f"Немедленно вызовите скорую помощь:\n"
                    f"📞 **103** — со стационарного\n"
                    f"📞 **112** — с мобильного\n\n"
                    f"Не ждите, звоните сейчас! Это не заменяет врача.",
                    reply_markup=get_main_keyboard(),
                )
                return

        # --- Input Validation ---
        if len(text) < 3:
            await message.answer(
                f"⚠️ **Слишком коротко**\n{SEP}\n\n"
                f"Пожалуйста, опишите симптомы подробнее (хотя бы 3 символа).\n\n"
                f"✍️ _Например: Болит голова третий день, подташнивает_"
            )
            return

        await state.update_data(symptoms=text)
        await state.set_state(SymptomAnalysis.waiting_for_duration)
        await message.answer(f"●●○○○ **Шаг 2 из 5**\n\n📅 **Когда началось?**\n\nКак давно появились симптомы?", reply_markup=get_time_keyboard())

    @dp.callback_query(SymptomAnalysis.waiting_for_duration, F.data.startswith("time_"))
    async def process_duration(callback: types.CallbackQuery, state: FSMContext):
        duration_map = {"time_today": "Сегодня", "time_1_3_days": "1-3 дня", "time_week": "Неделю", "time_more": "Больше недели"}
        await state.update_data(duration=duration_map.get(callback.data, callback.data))
        await state.set_state(SymptomAnalysis.waiting_for_temperature)
        await callback.message.answer(f"●●●○○ **Шаг 3 из 5**\n\n🌡️ **Температура**\n\nЕсть ли температура сейчас или была в последние дни?", reply_markup=get_temperature_keyboard())
        await callback.answer()

    @dp.callback_query(SymptomAnalysis.waiting_for_temperature, F.data.startswith("temp_"))
    async def process_temperature(callback: types.CallbackQuery, state: FSMContext):
        temp_map = {"temp_no": "Нет", "temp_low": "До 38°C", "temp_medium": "38-39°C", "temp_high": "Выше 39°C"}
        await state.update_data(temperature=temp_map.get(callback.data, callback.data))
        await state.set_state(SymptomAnalysis.waiting_for_gender)
        await callback.message.answer(f"●●●●○ **Шаг 4 из 5**\n\n⚧ **Ваш пол**\n\nДля точного анализа мне нужно знать ваш пол.", reply_markup=get_gender_keyboard())

    @dp.callback_query(SymptomAnalysis.waiting_for_gender, F.data.startswith("gender_"))
    async def process_gender(callback: types.CallbackQuery, state: FSMContext):
        gender_map = {"gender_male": "Мужской", "gender_female": "Женский"}
        await state.update_data(gender=gender_map.get(callback.data, callback.data))
        await state.set_state(SymptomAnalysis.waiting_for_age)
        await callback.message.answer(f"●●●●● **Шаг 5 из 5**\n\n👤 **Ваш возраст**\n\nВыберите возрастную группу:", reply_markup=get_age_keyboard())
        await callback.answer()

    @dp.callback_query(SymptomAnalysis.waiting_for_age, F.data.startswith("age_"))
    async def process_age(callback: types.CallbackQuery, state: FSMContext):
        age_map = {"age_0_17": "0-17 лет", "age_18_35": "18-35 лет", "age_36_55": "36-55 лет", "age_55_plus": "55+ лет"}
        await state.update_data(age=age_map.get(callback.data, callback.data))
        loading = get_loading_text()
        await callback.message.answer(f"⏳ {loading}\n\n«Наберитесь терпения — я готовлю заключение» 🩺", reply_markup=types.ReplyKeyboardRemove())
        await callback.answer()
        await perform_analysis(callback.message, state)

    # Back buttons
    @dp.callback_query(SymptomAnalysis.waiting_for_gender, F.data == "back_to_temp")
    async def back_to_temp(callback: types.CallbackQuery, state: FSMContext):
        await state.set_state(SymptomAnalysis.waiting_for_temperature)
        await callback.message.edit_text("🌡️ **Шаг 3 из 5**\n\nЕсть ли температура?", reply_markup=get_temperature_keyboard())
        await callback.answer()

    @dp.callback_query(SymptomAnalysis.waiting_for_age, F.data == "back_to_gender")
    async def back_to_gender(callback: types.CallbackQuery, state: FSMContext):
        await state.set_state(SymptomAnalysis.waiting_for_gender)
        await callback.message.edit_text("⚧ **Шаг 4 из 5**\n\nВаш пол?", reply_markup=get_gender_keyboard())
        await callback.answer()

    # --- Handwriting Analysis Flow (via OpenRouter Vision) ---

    @dp.message(F.text == "✍️ Анализ почерка")
    async def start_handwriting_analysis(message: types.Message, state: FSMContext):
        # Check free analyses
        free_count = await get_free_analyses(message.from_user.id)
        if free_count > 0:
            await state.update_data(using_free=True)
        else:
            can_proceed, count = await check_usage_limit(message.from_user.id)
            if not can_proceed:
                await message.answer(limit_message(), reply_markup=get_main_keyboard())
                return

        await state.set_state(HandwritingAnalysis.waiting_for_photo)
        await message.answer(
            f"✍️ **Анализ почерка**\n{SEP}\n\n"
            f"Отправьте фото рукописного текста — я распознаю его.\n\n"
            f"📸 Снимите при хорошем освещении, текст должен быть разборчивым.\n\n"
            f"⚠️ Распознаю русский и английский язык."
        )

    @dp.message(HandwritingAnalysis.waiting_for_photo, F.photo)
    async def process_handwriting_photo(message: types.Message, state: FSMContext):
        await message.answer("📥 Загружаю фото...")
        try:
            file = await bot.get_file(message.photo[-1].file_id)
            image_data = (await bot.download_file(file.file_path)).read()
            await state.update_data(image_bytes=image_data)

            await message.answer("🔍 Распознаю текст... _(до 30 секунд)_")

            # Use OpenRouter Vision for handwriting
            ocr_text = await llm_client.extract_text_from_image_openrouter(image_data)
            if not ocr_text.strip():
                raise ValueError("No text recognized")

            await state.update_data(ocr_text=ocr_text)

            # Analyze the extracted text immediately
            await message.answer("🧠 Анализирую содержание...")
            prompt = (
                f"Пользователь прислал рукописный текст. Вот что распознано:\n\n"
                f"{ocr_text}\n\n"
                f"Если это медицинские записи (рецепт, назначения, симптомы) — "
                f"объясни их простым языком. Если это не медицинский текст — "
                f"просто перескажи содержание.\n\n"
                f"Отвечай на русском языке."
            )

            response = await llm_client.query(prompt)

            # Save to DB
            try:
                async with get_session() as session_db:
                    consultation = Consultation(
                        user_id=message.from_user.id,
                        symptoms="Рукописный текст: " + ocr_text[:200],
                        response=response,
                        triage_level=None
                    )
                    session_db.add(consultation)
                    await session_db.commit()
            except Exception as db_err:
                logger.error(f"Handwriting DB save failed: {db_err}")

            # Use free analysis or increment
            data_state = await state.get_data()
            if data_state.get('using_free'):
                await use_free_analysis(message.from_user.id)
            else:
                await increment_usage(message.from_user.id)

            await message.answer(f"{response}\n\n{PREMIUM_FOOTER}", reply_markup=get_handwriting_result_keyboard(), parse_mode=None)

        except ValueError:
            await message.answer(
                f"⚠️ **Текст не распознан**\n{SEP}\n\n"
                f"📸 **Советы для чёткого снимка:**\n"
                f"• Пишите крупнее и разборчивее\n"
                f"• Снимайте при ярком освещении\n"
                f"• Держите телефон неподвижно\n\n"
                f"Попробуйте ещё раз 🩺",
                reply_markup=get_main_keyboard(),
            )
        except Exception as e:
            logger.error(f"Handwriting analysis failed: {e}")
            await message.answer(f"⚠️ **Что-то пошло не так.**\n\nПопробуйте ещё раз — возможно, фото было слишком тёмным или текст нечитаем.", reply_markup=get_main_keyboard())
        finally:
            await state.clear()

    @dp.message(HandwritingAnalysis.waiting_for_photo)
    async def handwriting_invalid_file(message: types.Message):
        await message.answer(f"📸 Пожалуйста, отправьте **фото** с рукописным текстом, а не файл или другое сообщение.")

    # --- Handwriting Result Actions ---

    @dp.callback_query(F.data == "handwriting_pdf")
    async def handwriting_pdf(callback: types.CallbackQuery):
        await callback.answer("Генерирую PDF...")
        await generate_report(callback.message)

    @dp.callback_query(F.data == "handwriting_new")
    async def handwriting_new(callback: types.CallbackQuery, state: FSMContext):
        await state.set_state(HandwritingAnalysis.waiting_for_photo)
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.answer("✍️ Отправьте следующее фото рукописного текста.")
        await callback.answer()

    @dp.callback_query(F.data == "handwriting_share")
    async def handwriting_share(callback: types.CallbackQuery):
        await callback.answer("Начисляем бонус за шаринг...")
        # Grant bonus analysis for sharing
        await grant_bonus_analysis(callback.from_user.id, 1)
        
        data = await state.get_data()
        analysis_result = data.get('response', '')
        ocr_text = data.get('ocr_text', '')
        
        share_text = (
            f"📝 **Мой анализ рукописного текста в MedAssistant Bot**\n\n"
            f"📄 Распознанный текст:\n{ocr_text}\n\n"
            f"📋 Анализ содержимого:\n{analysis_result}\n\n"
            f"{SEP}\n"
            f"🤖 Получи свой анализ — @Med24AssistantBot\n"
            f"💼 Хочешь такого бота для своего бизнеса? — @Ivan_Zadov\n\n"
            f"#медицина #распознаваниепочерка #telegrambot"
        )
        
        await callback.message.answer(
            f"📤 **Готово к расшариванию**\n{SEP}\n\n"
            f"Скопируй текст ниже и поделись в чат, канал или соцсети:\n\n"
            f"```\n{share_text}\n```\n\n"
            f"🎁 **Начислен бонус: +1 бесплатный анализ за шаринг!**\n"
            f"💡 Подсказка: долгое удержание текста → копировать",
            reply_markup=get_main_keyboard(),
            parse_mode="Markdown"
        )

    # --- Referral System ---

    @dp.message(F.text == "🎁 Бесплатный анализ")
    async def cmd_referral(message: types.Message):
        try:
            code = await get_or_create_referral_code(message.from_user.id)
            bot_username = (await bot.get_me()).username
            referral_link = f"https://t.me/{bot_username}?start={code}"
            free_count = await get_free_analyses(message.from_user.id)
            stats = await get_referral_stats(message.from_user.id)

            text = (
                f"🎁 **Бесплатный анализ**\n{SEP}\n\n"
                f"📊 У вас **{free_count}** бесплатных анализов.\n\n"
                f"**Пригласите друга — получите ещё:**\n\n"
                f"🔹 Отправьте другу ссылку ниже\n"
                f"🔹 Друг переходит и запускает бота\n"
                f"🔹 **Вы оба** получаете +1 бесплатный анализ ✨\n\n"
                f"🔗 **Ваша ссылка:**\n"
                f"`{referral_link}`\n\n"
                f"👥 Пришло по вашей ссылке: **{stats['total_referred']}** чел.\n\n"
                f"👆 Нажмите на ссылку, чтобы скопировать"
            )
            await message.answer(text, reply_markup=get_main_keyboard())
        except Exception as e:
            logger.error(f"Referral error: {e}")
            await message.answer(
                "⚠️ Ошибка. Попробуйте позже.",
                reply_markup=get_main_keyboard(),
            )

    @dp.message(F.text == "🚑 Экстренная помощь")
    async def cmd_emergency(message: types.Message):
        await message.answer(
            f"🚨 **Экстренная помощь**\n{SEP}\n\n"
            f"📞 **103** — со стационарного телефона\n"
            f"📞 **112** — с мобильного телефона\n\n"
            f"Если вам нужна срочная медицинская помощь — звоните сейчас.\n"
            f"Не ждите и не полагайтесь на онлайн-консультацию в экстренных ситуациях.\n\n"
            f"{SEP}\n"
            f"🩺 Я здесь для информационной поддержки, но не заменяю врача.",
            reply_markup=get_main_keyboard(),
        )

    # --- Portfolio / Order Bot ---

    @dp.message(F.text == "💼 Заказать такого бота")
    async def cmd_portfolio(message: types.Message):
        await message.answer(
            f"💼 **Разработка Telegram-ботов**\n{SEP}\n\n"
            f"Вы видите работающий пример медицинского AI-бота с:\n\n"
            f"🔍 Анализ симптомов через нейросеть\n"
            f"✍️ Распознавание рукописного текста\n"
            f"📄 Генерация PDF-отчётов\n"
            f"🎁 Реферальная система\n"
            f"👑 Админ-панель\n\n"
            f"**Что я делаю:**\n"
            f"• AI-боты для медицины, образования, бизнеса\n"
            f"• Telegram-боты любой сложности\n"
            f"• Интеграция с GPT, OpenRouter, LLM\n"
            f"• Полное сопровождение — от идеи до запуска\n\n"
            f"{SEP}\n"
            f"📩 **Связь:** @Ivan_Zadov\n\n"
            f"Напишите — обсудим ваш проект 🔧",
            reply_markup=get_main_keyboard(),
        )

    async def perform_analysis(message: types.Message, state: FSMContext):
        data = await state.get_data()
        symptoms_text = data.get('symptoms', '')

        kb_results = medical_kb.search_by_symptoms(
            [s.strip() for s in symptoms_text.replace(',', ' ').split() if len(s.strip()) > 3],
            top_n=5
        )

        kb_context = ""
        if kb_results:
            kb_context = "\n\nБаза знаний (157 болезней, 491 симптом):\n"
            for r in kb_results[:3]:
                top_syms = medical_kb.get_top_symptoms(r["disease"], top_n=5)
                kb_context += f"- {r['disease']} (совпадение: {r['score']:.2f}): {', '.join(s['name'] for s in top_syms)}\n"

        prompt = (
            f"Пользователь:\n"
            f"- Симптомы: {symptoms_text}\n"
            f"- Длительность: {data.get('duration')}\n"
            f"- Температура: {data.get('temperature')}\n"
            f"- Возраст: {data.get('age')}\n"
            f"- Пол: {data.get('gender')}\n"
            f"{kb_context}\n\n"
            f"Проведите анализ."
        )

        try:
            response = await llm_client.query(prompt)
            await state.update_data(analysis_result=response, triage="Средний")

            # --- Save to DB for Reports ---
            try:
                async with get_session() as session_db:
                    consultation = Consultation(
                        user_id=message.from_user.id,
                        symptoms=symptoms_text,
                        response=response,
                        triage_level=None
                    )
                    session_db.add(consultation)
                    await session_db.commit()
            except Exception as db_err:
                logger.error(f"DB save failed: {db_err}")

            # Increment usage counter or use free analysis
            data = await state.get_data()
            if data.get('using_free'):
                await use_free_analysis(message.from_user.id)
            else:
                await increment_usage(message.from_user.id)
            
            # Update last symptom analysis timestamp for cooldown
            await update_last_symptom_analysis(message.from_user.id)

            await message.answer(f"{response}\n\n{PREMIUM_FOOTER}", reply_markup=get_result_keyboard(), parse_mode=None)
        except Exception as e:
            logger.error(f"LLM query failed: {e}")
            await message.answer("⚠️ Не удалось провести анализ. Попробуйте позже.", reply_markup=get_main_keyboard())
        
        await state.clear()

    @dp.callback_query(F.data == "result_pdf")
    async def result_pdf(callback: types.CallbackQuery):
        await callback.answer("Генерирую PDF...")
        await generate_report(callback.message)

    @dp.callback_query(F.data == "result_doctor")
    async def result_doctor(callback: types.CallbackQuery):
        await callback.answer("Готовлю отчет для врача...")
        await generate_report(callback.message)

    @dp.callback_query(F.data == "result_share")
    async def result_share(callback: types.CallbackQuery):
        await callback.answer("Начисляем бонус за шаринг...")
        # Grant bonus analysis for sharing
        await grant_bonus_analysis(callback.from_user.id, 1)
        
        data = await state.get_data()
        analysis_result = data.get('analysis_result', '')
        symptoms = data.get('symptoms', '')
        
        share_text = (
            f"🩺 **Мой анализ симптомов в MedAssistant Bot**\n\n"
            f"🔍 Что беспокоило: {symptoms}\n\n"
            f"📋 Что показал анализ:\n{analysis_result}\n\n"
            f"{SEP}\n"
            f"🤖 Получи свой разбор — @Med24AssistantBot\n"
            f"💼 Хочешь такого бота для своего бизнеса? — @Ivan_Zadov\n\n"
            f"#медицина #анализсимптомов #telegrambot"
        )
        
        await callback.message.answer(
            f"📤 **Готово к расшариванию**\n{SEP}\n\n"
            f"Скопируй текст ниже и поделись в чат, канал или соцсети:\n\n"
            f"```\n{share_text}\n```\n\n"
            f"🎁 **Начислен бонус: +1 бесплатный анализ за шаринг!**\n"
            f"💡 Подсказка: долгое удержание текста → копировать",
            reply_markup=get_main_keyboard(),
            parse_mode="Markdown"
        )

    @dp.callback_query(F.data == "result_restart")
    async def result_restart(callback: types.CallbackQuery):
        can_proceed, seconds_remaining = await check_symptom_analysis_cooldown(callback.from_user.id)
        
        if not can_proceed:
            hours = seconds_remaining // 3600
            minutes = (seconds_remaining % 3600) // 60
            seconds = seconds_remaining % 60
            
            if hours > 0:
                time_str = f"{hours} ч {minutes} мин"
            elif minutes > 0:
                time_str = f"{minutes} мин {seconds} сек"
            else:
                time_str = f"{seconds} сек"
                
                await callback.message.answer(
                    f"⏳ **Перерыв между анализами**\n{SEP}\n\n"
                    f"Новый анализ можно начать через: **{time_str}**\n\n"
                    f"Это нужно для качественной обработки данных. Отдохните немного 🩺",
                    reply_markup=get_main_keyboard()
                )
        else:
            await callback.message.answer(f"🔍 **Новый анализ**\n{SEP}\n\nЧто вас беспокоит на этот раз?", reply_markup=get_main_keyboard())
        await callback.answer()

    @dp.callback_query(F.data == "back_to_menu")
    async def back_to_menu(callback: types.CallbackQuery, state: FSMContext):
        await state.clear()
        await callback.message.answer(f"🩺 Вернулись в меню. Чем помочь?", reply_markup=get_main_keyboard())
        await callback.answer()

    async def generate_report(message: types.Message):
        try:
            async with get_session() as session_db:
                from sqlalchemy import select
                result = await session_db.execute(
                    select(Consultation)
                    .filter(Consultation.user_id == message.from_user.id)
                    .order_by(Consultation.created_at.desc())
                    .limit(1)
                )
                last = result.scalar_one_or_none()
                if not last:
                    await message.answer("⚠️ Нет данных для отчёта. Сначала выполните анализ симптомов.", reply_markup=get_main_keyboard())
                    return
                filepath = create_pdf_report(
                    user_name=message.from_user.first_name or "Пользователь",
                    symptoms=last.symptoms,
                    analysis_result=last.response,
                    triage_level=last.triage_level or "Средний",
                    include_chart=True
                )
                if not filepath:
                    await message.answer(f"⚠️ **Не удалось создать PDF.**\n\nПопробуйте ещё раз позже.", reply_markup=get_main_keyboard())
                    return
                pdf_file = FSInputFile(filepath)
                await message.answer_document(pdf_file, caption=f"📄 **PDF-отчёт готов**\n{SEP}\n\nВаш анализ симптомов в удобном формате.")

                # Clean up chart temp files
                import glob
                for tmp in glob.glob("data/charts/*.png"):
                    try:
                        os.remove(tmp)
                    except:
                        pass
        except Exception as e:
            logger.error(f"Report gen failed: {e}", exc_info=True)
            await message.answer(f"⚠️ **Не удалось создать PDF.**\n\nПроверьте подключение и попробуйте ещё раз.", reply_markup=get_main_keyboard())

    # --- QA: Unsupported Media ---
    @dp.message(F.photo)
    async def photo_without_context(message: types.Message):
        await message.answer(
            f"📸 **Фото получено**\n{SEP}\n\n"
            f"Чтобы проанализировать фото, нажмите **«✍️ Анализ почерка»** в меню.",
            reply_markup=get_main_keyboard(),
        )

    @dp.message(F.voice | F.video | F.video_note | F.animation)
    async def unsupported_media(message: types.Message):
        await message.answer(
            f"⚠️ **Я понимаю только текст и фото.**\n\n"
            f"Опишите симптомы текстом или отправьте фото анализов 🩺",
            reply_markup=get_main_keyboard()
        )

    @dp.message()
    async def echo_all(message: types.Message):
        await message.answer("Используйте кнопки ниже 👇", reply_markup=get_main_keyboard())

    logger.info("Starting polling...")
    logger.info("=" * 50)
    try:
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"Polling error: {e}")
    finally:
        await bot.session.close()
        logger.info("Bot stopped")

if __name__ == "__main__":
    asyncio.run(main())
