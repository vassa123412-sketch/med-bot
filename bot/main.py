import asyncio
import logging
import sys
import os
from aiogram import Bot, Dispatcher, types, F, BaseMiddleware
from aiogram.types import FSInputFile, LabeledPrice, PreCheckoutQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from core.config import settings
from core.database import init_db, get_session, User, Consultation, Payment, check_usage_limit, increment_usage, update_last_symptom_analysis, check_symptom_analysis_cooldown, get_or_create_referral_code, process_referral, get_free_analyses, use_free_analysis, get_referral_stats, grant_bonus_analysis, create_payment_record, get_payment_by_pay_id, confirm_payment, get_lab_balance, use_lab_balance, get_db_stats
from core.llm_client import llm_client
from core.rate_limiter import rate_stats
from core.result_formatter import format_llm_result
from api.medical_kb import medical_kb
from bot.keyboards import (
    get_main_keyboard, get_time_keyboard, get_temperature_keyboard,
    get_gender_keyboard, get_age_keyboard, get_result_keyboard, get_back_to_menu_keyboard,
    get_handwriting_result_keyboard,
    get_admin_keyboard, get_lab_pricing_keyboard, get_lab_result_keyboard,
    get_photo_type_keyboard, get_legal_keyboard, get_payment_method_keyboard, STARS_PRICES,
)
from bot.states import SymptomAnalysis, HandwritingAnalysis, LabAnalysis, AdminActions, LabPayment, WaitingPhotoType
from reports.pdf_generator import create_pdf_report, create_lab_pdf_report

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


async def safe_callback_answer(callback: types.CallbackQuery, *args, **kwargs):
    try:
        await callback.answer(*args, **kwargs)
    except Exception as e:
        logger.warning(f"callback.answer failed (expired?): {e}")


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




# --- ALL HANDLERS AND HELPERS ---
def register_all_handlers(dp: Dispatcher, bot: Bot):
    """Register all bot handlers and helper functions (middleware, commands, callbacks, OCR helpers)."""

    class StatsMiddleware(BaseMiddleware):
        async def __call__(self, handler, event, data):
            if hasattr(event, 'from_user') and event.from_user:
                rate_stats.record(event.from_user.id)
            return await handler(event, data)

    dp.message.middleware.register(StatsMiddleware())

    @dp.message(CommandStart())
    async def cmd_start(message: types.Message, state: FSMContext):
        await state.clear()

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

                    if referral_code:
                        await process_referral(message.from_user.id, referral_code)
                        free_count = await get_free_analyses(message.from_user.id)
                        extras = "\n\n🎁 **Вам начислен 1 бесплатный анализ по реферальной ссылке!**" if free_count > 0 else ""
                else:
                    await session_db.execute(update(User).where(User.telegram_id == message.from_user.id).values(username=message.from_user.username, first_name=message.from_user.first_name))
                    await session_db.commit()
                    extras = ""
        except Exception as e:
            logger.error(f"Error saving user: {e}")
            extras = ""
        await message.answer(
            "🔬 **Демо медицинского AI-бота**\n\n"
            "Этот бот показывает, как работает искусственный интеллект в медицине:\n\n"
            "🔍 Анализ симптомов — опишите жалобы, получите разбор\n"
            "✍️ Распознавание почерка — AI расшифрует рукописный текст\n"
            "🎁 Бесплатный доступ — протестируйте все функции\n\n"
            "💼 **Хотите такой же бот для вашего бизнеса?**\n"
            "👉 @Ivan_Zadov — разработка Telegram-ботов под ключ\n\n"
            "⚠️ *Результаты не являются медицинским диагнозом.*"
            f"{extras}",
            reply_markup=get_main_keyboard(),
        )

    @dp.message(Command("help"))
    async def cmd_help(message: types.Message):
        await message.answer(
            "📋 **Помощь**\n\n"
            "🩺 **МедАссистент** умеет:\n\n"
            "🔍 Анализ симптомов — расскажите что беспокоит\n"
            "✍️ Распознавание почерка — разберём рукописный текст\n"
            "🎁 Бесплатный анализ — пригласите друга\n\n"
            "⚠️ Я не заменяю врача. Все результаты — ознакомительные.",
            reply_markup=get_main_keyboard(),
        )

    @dp.message(F.text == "🚑 Экстренная помощь")
    async def cmd_emergency(message: types.Message):
        await message.answer(
            "🚨 **Экстренная помощь**\n\n"
            "Если вам или кому-то рядом требуется **немедленная медицинская помощь**:\n\n"
            "📞 **103** — скорая помощь (стационарный)\n"
            "📞 **112** — единый номер экстренных служб (мобильный)\n\n"
            "**Признаки, требующие вызова скорой:**\n"
            "• Затруднённое дыхание, удушье\n"
            "• Сильное кровотечение\n"
            "• Боль в груди, отдающая в руку/челюсть\n"
            "• Внезапная слабость/онемение половины тела\n"
            "• Потеря сознания\n"
            "• Судороги\n"
            "• Травмы головы/позвоночника\n\n"
            "⚠️ **Не ждите — звоните сразу!**",
            reply_markup=get_main_keyboard(),
        )

    @dp.message(F.text == "📋 Правовая информация")
    async def cmd_legal(message: types.Message):
        await message.answer(
            "📋 **Правовая информация**\n\n"
            "Выберите документ для ознакомления:",
            reply_markup=get_legal_keyboard(),
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

        db_stats = await get_db_stats()

        lines = [
            "📊 **Статистика бота**",
            "",
            "**📦 База данных:**",
            f"  · Всего пользователей: {db_stats['total_users']}",
            f"  · Новых сегодня: {db_stats['today_users']}",
            f"  · Всего консультаций: {db_stats['total_consultations']}",
            f"  · Консультаций сегодня: {db_stats['today_consultations']}",
            f"  · Активных сегодня: {db_stats['active_today']}",
            "",
            "**⚡ Rate лимиты (in-memory):**",
            f"  · запросов за час: {last_hour_req}",
            f"  · запросов за сутки: {last_day_req}",
            "",
            "**Активные пользователи:**",
            f"  · за 5 мин: {active_5m}",
            f"  · за час: {active_1h}",
            "",
            "**Топ-10 за час:**",
        ]
        if top_users:
            for uid, count in top_users:
                lines.append(f"  · `{uid}` — {count} запр.")
        else:
            lines.append("  · нет данных")

        lines.extend([
            "",
            f"⚙️ Rate лимит: {rate_stats.limit} запр./{rate_stats.window}с",
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
            "👑 **Админ-панель**\n\n"
            "Выберите действие:",
            reply_markup=get_admin_keyboard(),
        )

    # --- Admin Callbacks ---

    @dp.callback_query(F.data == "admin_me")
    async def admin_me(callback: types.CallbackQuery):
        if not is_admin(callback.from_user.id):
            return await safe_callback_answer(callback)
        uid = callback.from_user.id
        async with get_session() as session_db:
            from sqlalchemy import select
            result = await session_db.execute(select(User).filter(User.telegram_id == uid))
            user = result.scalar_one_or_none()
            if not user:
                await callback.message.answer("❌ Не найден.")
                return await safe_callback_answer(callback)

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
        await safe_callback_answer(callback)

    @dp.callback_query(F.data == "admin_reset_me")
    async def admin_reset_me(callback: types.CallbackQuery):
        if not is_admin(callback.from_user.id):
            return await safe_callback_answer(callback)
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
        await safe_callback_answer(callback)

    @dp.callback_query(F.data.startswith("admin_addfree_"))
    async def admin_addfree(callback: types.CallbackQuery):
        if not is_admin(callback.from_user.id):
            return await safe_callback_answer(callback)
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
        await safe_callback_answer(callback)

    @dp.callback_query(F.data == "admin_user_other")
    async def admin_user_other(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            return await safe_callback_answer(callback)
        await state.set_state(AdminActions.waiting_for_user_id)
        await callback.message.answer("🔍 Введите Telegram ID пользователя:")
        await safe_callback_answer(callback)

    @dp.callback_query(F.data == "admin_reset_other")
    async def admin_reset_other(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            return await safe_callback_answer(callback)
        await state.set_state(AdminActions.waiting_for_user_id_reset)
        await callback.message.answer("🔄 Введите Telegram ID пользователя для сброса:")
        await safe_callback_answer(callback)

    @dp.callback_query(F.data == "admin_stats")
    async def admin_stats_cb(callback: types.CallbackQuery):
        if not is_admin(callback.from_user.id):
            return await safe_callback_answer(callback)
        last_hour_req = rate_stats.get_total_requests(3600)
        last_day_req = rate_stats.get_total_requests(86400)
        active_5m = rate_stats.get_active_users(300)
        active_1h = rate_stats.get_active_users(3600)
        top_users = rate_stats.get_top_users(10, 3600)

        db_stats = await get_db_stats()

        lines = [
            "📊 **Статистика бота**",
            "",
            "**📦 База данных:**",
            f"  · Всего пользователей: {db_stats['total_users']}",
            f"  · Новых сегодня: {db_stats['today_users']}",
            f"  · Всего консультаций: {db_stats['total_consultations']}",
            f"  · Консультаций сегодня: {db_stats['today_consultations']}",
            f"  · Активных сегодня: {db_stats['active_today']}",
            "",
            "**⚡ Rate лимиты (in-memory):**",
            f"  · запросов за час: {last_hour_req}",
            f"  · запросов за сутки: {last_day_req}",
            "",
            "**Активные пользователи:**",
            f"  · за 5 мин: {active_5m}",
            f"  · за час: {active_1h}",
            "",
            "**Топ-10 за час:**",
        ]
        if top_users:
            for uid, count in top_users:
                lines.append(f"  · `{uid}` — {count} запр.")
        else:
            lines.append("  · нет данных")
        await callback.message.answer("\n".join(lines))
        await safe_callback_answer(callback)

    @dp.callback_query(F.data == "admin_close")
    async def admin_close(callback: types.CallbackQuery):
        if not is_admin(callback.from_user.id):
            return await safe_callback_answer(callback)
        await callback.message.delete()
        await safe_callback_answer(callback)

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
            "🔍 **Анализ симптомов**\n\n"
            "🟢⚪⚪⚪⚪ Шаг 1 из 5\n\n"
            "Опишите, что вас беспокоит. Чем подробнее, тем точнее анализ.\n\n"
            "*Пример: Головная боль 3 дня, тошнота, температура 37.8*",
            parse_mode="Markdown",
        )

    @dp.message(SymptomAnalysis.waiting_for_symptoms)
    async def process_symptoms(message: types.Message, state: FSMContext):
        text = message.text.strip()

        # --- Admin bypasses all limits ---
        if is_admin(message.from_user.id):
            await state.update_data(using_free=False)
        else:
            # --- Check Free Analyses first, then daily limit ---
            free_count = await get_free_analyses(message.from_user.id)
            if free_count > 0:
                await state.update_data(using_free=True)
            else:
                await state.update_data(using_free=False)
                can_proceed, count = await check_usage_limit(message.from_user.id)
                if not can_proceed:
                    await state.clear()
                    await message.answer(
                        "⚠️ Вы исчерпали ежедневный лимит бесплатных анализов (3/3).\n\n"
                        "🔹 Попробуйте завтра — лимит обновится в 00:00\n"
                        "🔹 Или пригласите друга по реферальной ссылке (🎁 в меню)",
                        reply_markup=get_main_keyboard(),
                    )
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
                    "🚨 **ЭКСТРЕННАЯ СИТУАЦИЯ**\n\n"
                    "Немедленно вызовите скорую помощь:\n"
                    "📞 **103** — со стационарного\n"
                    "📞 **112** — с мобильного\n\n"
                    "Не ждите, звоните сейчас!",
                    reply_markup=get_main_keyboard(),
                )
                return

        # --- Input Validation ---
        if len(text) < 3:
            await message.answer(
                "⚠️ Пожалуйста, опишите симптомы подробнее (минимум 3 символа).",
                parse_mode="Markdown",
            )
            return

        await state.update_data(symptoms=text)
        await state.set_state(SymptomAnalysis.waiting_for_duration)
        await message.answer("🟢🟢⚪⚪⚪ **Шаг 2 из 5**\n\n📅 **Как давно появились симптомы?**", reply_markup=get_time_keyboard())

    @dp.callback_query(SymptomAnalysis.waiting_for_duration, F.data.startswith("time_"))
    async def process_duration(callback: types.CallbackQuery, state: FSMContext):
        duration_map = {"time_today": "Сегодня", "time_1_3_days": "1-3 дня", "time_week": "Неделю", "time_more": "Больше недели"}
        await state.update_data(duration=duration_map.get(callback.data, callback.data))
        await state.set_state(SymptomAnalysis.waiting_for_temperature)
        await callback.message.answer("🟢🟢🟢⚪⚪ **Шаг 3 из 5**\n\n🌡️ **Есть ли температура?**", reply_markup=get_temperature_keyboard())
        await safe_callback_answer(callback)

    @dp.callback_query(SymptomAnalysis.waiting_for_temperature, F.data.startswith("temp_"))
    async def process_temperature(callback: types.CallbackQuery, state: FSMContext):
        temp_map = {"temp_no": "Нет", "temp_low": "До 38°C", "temp_medium": "38-39°C", "temp_high": "Выше 39°C"}
        await state.update_data(temperature=temp_map.get(callback.data, callback.data))
        await state.set_state(SymptomAnalysis.waiting_for_gender)
        await callback.message.answer("🟢🟢🟢🟢⚪ **Шаг 4 из 5**\n\n⚧ **Ваш пол?**", reply_markup=get_gender_keyboard())
        await safe_callback_answer(callback)

    @dp.callback_query(SymptomAnalysis.waiting_for_gender, F.data.startswith("gender_"))
    async def process_gender(callback: types.CallbackQuery, state: FSMContext):
        gender_map = {"gender_male": "Мужской", "gender_female": "Женский"}
        await state.update_data(gender=gender_map.get(callback.data, callback.data))
        await state.set_state(SymptomAnalysis.waiting_for_age)
        await callback.message.answer("🟢🟢🟢🟢🟢 **Шаг 5 из 5**\n\n👤 **Ваш возраст?**", reply_markup=get_age_keyboard())
        await safe_callback_answer(callback)

    @dp.callback_query(SymptomAnalysis.waiting_for_age, F.data.startswith("age_"))
    async def process_age(callback: types.CallbackQuery, state: FSMContext):
        age_map = {"age_0_17": "0-17 лет", "age_18_35": "18-35 лет", "age_36_55": "36-55 лет", "age_55_plus": "55+ лет"}
        await state.update_data(age=age_map.get(callback.data, callback.data))
        await callback.message.answer("⏳ Анализирую симптомы... Подождите немного.", reply_markup=types.ReplyKeyboardRemove())
        await safe_callback_answer(callback)
        await perform_analysis(callback.message, state, user_id=callback.from_user.id, user_name=callback.from_user.first_name)

    # Back buttons
    @dp.callback_query(SymptomAnalysis.waiting_for_duration, F.data == "back_to_symptoms")
    async def back_to_symptoms(callback: types.CallbackQuery, state: FSMContext):
        await state.set_state(SymptomAnalysis.waiting_for_symptoms)
        try:
            await callback.message.edit_text("🟢⚪⚪⚪⚪ **Шаг 1 из 5**\n\n📝 **Опишите ваши симптомы:**\n\nНапишите, что вас беспокоит.")
        except Exception as e:
            logger.warning(f"edit_text (back_to_symptoms): {e}")
        await safe_callback_answer(callback)

    @dp.callback_query(SymptomAnalysis.waiting_for_temperature, F.data == "back_to_duration")
    async def back_to_duration(callback: types.CallbackQuery, state: FSMContext):
        await state.set_state(SymptomAnalysis.waiting_for_duration)
        try:
            await callback.message.edit_text("🟢🟢⚪⚪⚪ **Шаг 2 из 5**\n\n📅 **Как давно появились симптомы?**", reply_markup=get_time_keyboard())
        except Exception as e:
            logger.warning(f"edit_text (back_to_duration): {e}")
        await safe_callback_answer(callback)

    @dp.callback_query(SymptomAnalysis.waiting_for_gender, F.data == "back_to_temp")
    async def back_to_temp(callback: types.CallbackQuery, state: FSMContext):
        await state.set_state(SymptomAnalysis.waiting_for_temperature)
        try:
            await callback.message.edit_text("🟢🟢🟢⚪⚪ **Шаг 3 из 5**\n\n🌡️ **Есть ли температура?**", reply_markup=get_temperature_keyboard())
        except Exception as e:
            logger.warning(f"edit_text (back_to_temp): {e}")
        await safe_callback_answer(callback)

    @dp.callback_query(SymptomAnalysis.waiting_for_age, F.data == "back_to_gender")
    async def back_to_gender(callback: types.CallbackQuery, state: FSMContext):
        await state.set_state(SymptomAnalysis.waiting_for_gender)
        try:
            await callback.message.edit_text("🟢🟢🟢🟢⚪ **Шаг 4 из 5**\n\n⚧ **Ваш пол?**", reply_markup=get_gender_keyboard())
        except Exception as e:
            logger.warning(f"edit_text (back_to_gender): {e}")
        await safe_callback_answer(callback)

    # --- perform_analysis ---

    async def perform_analysis(message: types.Message, state: FSMContext, user_id: int = None, user_name: str = None):
        data = await state.get_data()
        symptoms_text = data.get('symptoms', '')
        uid = user_id or message.from_user.id
        uname = user_name or message.from_user.first_name or "Пользователь"

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
            "Проведите анализ.\n\n"
            "ФОРМАТ ОТВЕТА:\n"
            "1. 🔴 Красные флаги (если есть) — В НАЧАЛЕ\n"
            "2. 📋 Возможные причины (с вероятностью)\n"
            "3. 📊 Уровень срочности\n"
            "4. 💡 Рекомендации"
        )

        try:
            response = await llm_client.query(prompt)
            await state.update_data(analysis_result=response, triage="Средний")

            # --- Save to DB for Reports ---
            try:
                async with get_session() as session_db:
                    consultation = Consultation(
                        user_id=uid,
                        symptoms=symptoms_text,
                        response=response,
                        triage_level=None
                    )
                    session_db.add(consultation)
                    await session_db.commit()
            except Exception as db_err:
                logger.error(f"DB save failed: {db_err}")

            # Increment usage counter or use free analysis (skip for admin)
            data = await state.get_data()
            if not is_admin(uid):
                if data.get('using_free'):
                    await use_free_analysis(uid)
                else:
                    await increment_usage(uid)

            # Update last symptom analysis timestamp for cooldown
            await update_last_symptom_analysis(uid)

            await message.answer(format_llm_result(response), reply_markup=get_result_keyboard())

        except Exception as e:
            logger.error(f"LLM query failed: {e}")
            await message.answer("⚠️ Не удалось провести анализ. Попробуйте позже.", reply_markup=get_main_keyboard())

        await state.clear()

    @dp.callback_query(F.data == "result_pdf")
    async def result_pdf(callback: types.CallbackQuery):
        await safe_callback_answer(callback, "Генерирую PDF...")
        await generate_report(callback.message, callback.from_user.id, callback.from_user.first_name)

    @dp.callback_query(F.data == "result_doctor")
    async def result_doctor(callback: types.CallbackQuery):
        await safe_callback_answer(callback, "Готовлю отчет для врача...")
        await generate_report(callback.message, callback.from_user.id, callback.from_user.first_name)

    @dp.callback_query(F.data == "result_share")
    async def result_share(callback: types.CallbackQuery):
        await safe_callback_answer(callback, "Начисляем бонус за шаринг...")
        await grant_bonus_analysis(callback.from_user.id, 1)

        async with get_session() as session_db:
            from sqlalchemy import select
            result = await session_db.execute(
                select(Consultation)
                .filter(
                    Consultation.user_id == callback.from_user.id,
                    ~Consultation.symptoms.startswith("Лабораторные анализы:"),
                    ~Consultation.symptoms.startswith("Рукописный текст:"),
                )
                .order_by(Consultation.created_at.desc())
                .limit(1)
            )
            last = result.scalar_one_or_none()

        symptoms = last.symptoms[:300] if last else ""
        analysis_result = last.response[:500] if last else ""

        share_text = (
            f"🩺 **Мой анализ симптомов в MedAssistant Bot**\n\n"
            f"🔍 Что беспокоило: {symptoms}\n\n"
            f"📋 Что показал анализ:\n{analysis_result}\n\n"
            f"---\n"
            f"🤖 Получи свой разбор — @Med24AssistantBot\n"
            f"💼 Хочешь такого бота для своего бизнеса? — @Ivan_Zadov\n\n"
            f"#медицина #анализсимптомов #telegrambot"
        )

        await callback.message.answer(
            "📤 **Готово к расшариванию**\n\n"
            "Скопируй текст ниже и поделись в чат, канал или соцсети:\n\n"
            f"```\n{share_text}\n```\n\n"
            "🎁 **Начислен бонус: +1 бесплатный анализ за шаринг!**\n"
            "💡 Подсказка: долгое удержание текста → копировать",
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
                f"⏳ **Перерыв между анализами**\n\n"
                f"Новый анализ можно начать через: **{time_str}**\n\n"
                "Это нужно для качественной обработки данных. Отдохните немного 🩺",
                reply_markup=get_main_keyboard()
            )
        else:
            await callback.message.answer("🔍 **Новый анализ**\n\nЧто вас беспокоит на этот раз?", reply_markup=get_main_keyboard())
        await safe_callback_answer(callback)

    @dp.callback_query(F.data == "back_to_menu")
    async def back_to_menu(callback: types.CallbackQuery, state: FSMContext):
        await state.clear()
        await callback.message.answer("🩺 Вернулись в меню. Чем помочь?", reply_markup=get_main_keyboard())
        await safe_callback_answer(callback)

    # --- Legal info callbacks ---

    @dp.callback_query(F.data == "legal_terms")
    async def legal_terms(callback: types.CallbackQuery):
        text = (
            "📄 **Публичная оферта (Пользовательское соглашение)**\n\n"
            "*Последнее обновление:* 16.05.2026\n\n"
            "**1. Общие положения**\n"
            "1.1. Настоящая Оферта регулирует порядок заключения Договора "
            "информационно-консультативных услуг через Telegram-бота "
            "«МедАссистент» (@Med24AssistantBot) (далее — «Сервис»).\n"
            "1.2. Использование Сервиса означает безоговорочный акцепт "
            "условий настоящей Оферты.\n\n"
            "**2. Термины**\n"
            "• **Договор** — текст Оферты, акцептованный Заказчиком\n"
            "• **Исполнитель** — Самозанятый, ИНН 519047822108\n"
            "• **Заказчик** — дееспособное лицо, использующее Сервис\n"
            "• **Услуга** — информационно-консультативные услуги\n\n"
            "**3. Предмет Договора**\n"
            "3.1. Исполнитель оказывает информационно-консультационные "
            "услуги, Заказчик оплачивает их.\n"
            "3.2. Услуги могут оказываться с привлечением третьих лиц "
            "(LLM-провайдеров, OCR-сервисов).\n"
            "3.3. Акцепт — начало использования Сервиса, отправка "
            "заявки и/или оплата.\n\n"
            "**4. Права и обязанности**\n"
            "• Исполнитель: анализирует данные, отвечает, описывает "
            "риски, оказывает услуги качественно и в срок\n"
            "• Заказчик: предоставляет достоверные данные, оплачивает "
            "услуги, принимает условия без оговорок\n\n"
            "**5. Цена и оплата**\n"
            "• Стоимость определяется в Сервисе (Telegram Stars / Robokassa)\n"
            "• Расчеты — в безналичном порядке\n\n"
            "**6. Возврат средств**\n"
            "• По Закону «О защите прав потребителей» № 2300-1\n"
            "• На основании претензии, срок ответа — 10 рабочих дней\n\n"
            "**7. Конфиденциальность**\n"
            "• Данные защищаются по ФЗ №152 и №149\n"
            "• Стороны сохраняют конфиденциальность полученной информации\n\n"
            "**8. Форс-мажор**\n"
            "• Стороны освобождаются от ответственности при "
            "непреодолимой силе\n"
            "• Уведомление — в течение 30 рабочих дней\n\n"
            "**9. Ответственность**\n"
            "• По условиям Оферты и законодательству РФ\n"
            "• Нарушитель возмещает убытки\n\n"
            "**10. Срок действия**\n"
            "• Оферта действует с момента размещения в Сервисе\n"
            "• Исполнитель может изменять условия с уведомлением "
            "через Сервис\n"
            "• Договор действует до исполнения обязательств\n\n"
            "**11. Споры**\n"
            "• Регулируются законодательством РФ\n"
            "• Досудебный порядок обязателен\n\n"
            "**12. Реквизиты Исполнителя**\n"
            "📌 Самозанятый\n"
            "📌 ИНН: 519047822108\n"
            "📞 +7 917 268-89-34\n"
            "📧 vudd049@gmail.com\n\n"
            "---\n"
            "*Используя Сервис, вы принимаете условия Оферты. "
            "Информация носит справочный характер. "
            "Это не диагноз и не лечение. Обратитесь к врачу.*"
        )
        try:
            await callback.message.edit_text(text, reply_markup=get_legal_keyboard())
        except Exception:
            await callback.message.answer(text, reply_markup=get_legal_keyboard())
        await safe_callback_answer(callback)

    @dp.callback_query(F.data == "legal_privacy")
    async def legal_privacy(callback: types.CallbackQuery):
        text = (
            "🔒 **Политика конфиденциальности**\n\n"
            "*Последнее обновление:* 30.04.2026\n\n"
            "**1. Оператор персональных данных**\n"
            "Telegram-бот «МедАссистент» (@Med24AssistantBot).\n\n"
            "**2. Какие данные мы собираем**\n"
            "• Telegram ID — идентификация\n"
            "• Имя пользователя — персонализация\n"
            "• Симптомы, результаты анализов — предоставление услуг\n"
            "• Возраст, пол — точность анализа\n"
            "• История консультаций — история взаимодействий\n\n"
            "**3. Цель обработки**\n"
            "Предоставление информационно-справочных материалов, улучшения Сервиса.\n\n"
            "**4. Правовое основание**\n"
            "Ст. 6 ФЗ №152 — согласие субъекта; "
            "ст. 10 ФЗ №152 — явное согласие на обработку медицинских данных.\n\n"
            "**5. Хранение данных**\n"
            "• Данные граждан РФ хранятся на территории РФ\n"
            "• Срок: до отзыва согласия\n"
            "• Шифрование: AES-256 (хранение), TLS 1.3 (передача)\n\n"
            "**6. Права пользователя**\n"
            "Доступ, исправление, удаление, отзыв согласия.\n\n"
            "**7. Передача третьим лицам**\n"
            "Не продаём. LLM-провайдерам — в анонимизированном виде.\n\n"
            "**8. Контакты**\n"
            "По вопросам обработки данных — через бота."
        )
        try:
            await callback.message.edit_text(text, reply_markup=get_legal_keyboard())
        except Exception:
            await callback.message.answer(text, reply_markup=get_legal_keyboard())
        await safe_callback_answer(callback)

    @dp.callback_query(F.data == "legal_disclaimer")
    async def legal_disclaimer(callback: types.CallbackQuery):
        text = (
            "⚕️ **Медицинский дисклеймер**\n\n"
            "**Минимальный (в каждом ответе):**\n"
            "⚠️ Информация носит справочный характер. Это не диагноз "
            "и не назначение лечения. Обратитесь к врачу.\n\n"
            "**Полный (при первом использовании):**\n"
            "⚠️ Данный бот предоставляет информационно-справочные материалы. "
            "Информация не заменяет профессиональную медицинскую консультацию, "
            "диагностику или лечение. Постановка диагноза и назначение лечения "
            "осуществляются только врачом при очном приёме. В случае экстренной "
            "ситуации немедленно вызовите скорую по телефону **103** или **112**.\n\n"
            "**Для PDF-заключений:**\n"
            "⚠️ Заключение носит информационно-справочный характер и не является "
            "медицинским диагнозом или назначением лечения.\n\n"
            "**Экстренная помощь:**\n"
            "📞 103 — Скорая помощь\n"
            "📞 112 — Единая служба спасения"
        )
        try:
            await callback.message.edit_text(text, reply_markup=get_legal_keyboard())
        except Exception:
            await callback.message.answer(text, reply_markup=get_legal_keyboard())
        await safe_callback_answer(callback)

    @dp.callback_query(F.data == "legal_support")
    async def legal_support(callback: types.CallbackQuery):
        text = (
            "📞 **Контакты и поддержка**\n\n"
            "**Исполнитель:** Самозанятый\n"
            "**ИНН:** 519047822108\n\n"
            "📞 **Телефон:** +7 917 268-89-34\n"
            "📧 **Email:** vudd049@gmail.com\n\n"
            "Если у вас возникли вопросы по работе Сервиса, "
            "оплате или возврату — обращайтесь по указанным контактам.\n\n"
            "⏰ Ответ в течение 24 часов."
        )
        try:
            await callback.message.edit_text(text, reply_markup=get_legal_keyboard())
        except Exception:
            await callback.message.answer(text, reply_markup=get_legal_keyboard())
        await safe_callback_answer(callback)

    @dp.callback_query(F.data == "legal_back")
    async def legal_back(callback: types.CallbackQuery, state: FSMContext):
        await state.clear()
        await callback.message.answer("🩺 Вернулись в меню. Чем помочь?", reply_markup=get_main_keyboard())
        await safe_callback_answer(callback)

    async def generate_report(message: types.Message, user_id: int = None, user_name: str = None):
        try:
            async with get_session() as session_db:
                from sqlalchemy import select
                result = await session_db.execute(
                    select(Consultation)
                    .filter(
                        Consultation.user_id == (user_id or message.from_user.id),
                        ~Consultation.symptoms.startswith("Лабораторные анализы:"),
                        ~Consultation.symptoms.startswith("Рукописный текст:"),
                    )
                    .order_by(Consultation.created_at.desc())
                    .limit(1)
                )
                last = result.scalar_one_or_none()
                if not last:
                    await message.answer("⚠️ Нет данных для отчёта. Сначала выполните анализ симптомов.", reply_markup=get_main_keyboard())
                    return
                filepath = create_pdf_report(
                    user_name=user_name or message.from_user.first_name or "Пользователь",
                    symptoms=last.symptoms,
                    analysis_result=last.response,
                    triage_level=last.triage_level or "Средний",
                    include_chart=True
                )
                if not filepath:
                    await message.answer("⚠️ **Не удалось создать PDF.**\n\nПопробуйте ещё раз позже.", reply_markup=get_main_keyboard())
                    return
                pdf_file = FSInputFile(filepath)
                await message.answer_document(pdf_file, caption="📄 **PDF-отчёт готов**\n\nВаш анализ симптомов в удобном формате.")

                # Clean up chart temp files
                import glob
                for tmp in glob.glob("data/charts/*.png"):
                    try:
                        os.remove(tmp)
                    except:
                        pass
        except Exception as e:
            logger.error(f"Report gen failed: {e}", exc_info=True)
            await message.answer("⚠️ **Не удалось создать PDF.**\n\nПроверьте подключение и попробуйте ещё раз.", reply_markup=get_main_keyboard())

    # --- Handwriting Analysis Flow (via OpenRouter Vision) ---

    @dp.message(F.text == "✍️ Анализ почерка")
    async def start_handwriting_analysis(message: types.Message, state: FSMContext):
        # Admin bypasses all limits
        if is_admin(message.from_user.id):
            await state.update_data(using_free=False)
        else:
            # Check free analyses
            free_count = await get_free_analyses(message.from_user.id)
            if free_count > 0:
                await state.update_data(using_free=True)
            else:
                can_proceed, count = await check_usage_limit(message.from_user.id)
                if not can_proceed:
                    await message.answer(
                        "⚠️ Вы исчерпали ежедневный лимит бесплатных анализов (3/3).\n\n"
                        "🔹 Попробуйте завтра — лимит обновится в 00:00\n"
                        "🔹 Или пригласите друга по реферальной ссылке (🎁 в меню)",
                        reply_markup=get_main_keyboard(),
                    )
                    return

        await state.set_state(HandwritingAnalysis.waiting_for_photo)
        await message.answer(
            "✍️ **Анализ почерка**\n\n"
            "Отправьте фото рукописного текста, и я распознаю его.\n\n"
            "📸 Сфотографируйте текст при хорошем освещении.\n"
            "⚠️ Я распознаю русский и английский текст."
        )

    async def _process_handwriting(user_id: int, message: types.Message, state: FSMContext, image_data: bytes):
        """Core handwriting processing logic (shared between message and callback handlers)."""
        await state.update_data(image_bytes=image_data)
        await message.answer("🔍 Распознаю текст... _(до 30 секунд)_")

        ocr_text = await llm_client.extract_text_from_image_openrouter(image_data)
        if not ocr_text.strip():
            raise ValueError("No text recognized")

        await state.update_data(ocr_text=ocr_text)
        await message.answer("🧠 Анализирую содержание...")
        prompt = (
            "Пользователь прислал изображение с текстом. Вот что удалось распознать:\n\n"
            f"{ocr_text}\n\n"
            "Твоя задача:\n"
            "1. Восстанови и исправь ошибки распознавания, если они очевидны.\n"
            "2. Перескажи содержание текста простым языком.\n"
            "3. Если это медицинские записи (рецепт, назначения, результаты обследований) — "
            "объясни их значение для пациента.\n\n"
            "Без лишних вступлений. Сразу к делу."
        )
        response = await llm_client.query(prompt)

        await message.answer(format_llm_result(response), reply_markup=get_handwriting_result_keyboard())

        try:
            async with get_session() as session_db:
                consultation = Consultation(
                    user_id=user_id,
                    symptoms="Рукописный текст: " + ocr_text[:2000],
                    response=response,
                    triage_level=None
                )
                session_db.add(consultation)
                await session_db.commit()
        except Exception as db_err:
            logger.error(f"Handwriting DB save failed: {db_err}")

        data_state = await state.get_data()
        if not is_admin(user_id):
            if data_state.get('using_free'):
                await use_free_analysis(user_id)
            else:
                await increment_usage(user_id)

    async def process_handwriting_from_id(user_id: int, message: types.Message, file_id: str, state: FSMContext):
        """Download photo by file_id and process handwriting."""
        await message.answer("📥 Загружаю фото...")
        try:
            file = await bot.get_file(file_id)
            image_data = (await bot.download_file(file.file_path)).read()
            await _process_handwriting(user_id, message, state, image_data)
        except ValueError:
            await message.answer(
                "⚠️ Не удалось распознать текст.\n\n"
                "📸 **Советы:**\n"
                "• Убедитесь что текст чёткий и крупный\n"
                "• Снимайте при хорошем освещении\n"
                "• Почерк должен быть разборчивым",
                reply_markup=get_main_keyboard(),
            )
        except Exception as e:
            logger.error(f"Handwriting analysis failed: {e}")
            await message.answer("⚠️ Что-то пошло не так. Попробуйте ещё раз.", reply_markup=get_main_keyboard())
        finally:
            await state.clear()

    @dp.message(HandwritingAnalysis.waiting_for_photo, F.photo)
    async def process_handwriting_photo(message: types.Message, state: FSMContext):
        await process_handwriting_from_id(message.from_user.id, message, message.photo[-1].file_id, state)

    @dp.message(HandwritingAnalysis.waiting_for_photo)
    async def handwriting_invalid_file(message: types.Message):
        await message.answer("📸 Пожалуйста, отправьте **фото** с рукописным текстом, а не файл или другое сообщение.")

    # --- Handwriting Result Actions ---

    @dp.callback_query(F.data == "handwriting_pdf")
    async def handwriting_pdf(callback: types.CallbackQuery):
        await safe_callback_answer(callback, "Генерирую PDF...")
        await generate_handwriting_report(callback.message, callback.from_user.id, callback.from_user.first_name)

    @dp.callback_query(F.data == "handwriting_new")
    async def handwriting_new(callback: types.CallbackQuery, state: FSMContext):
        await state.set_state(HandwritingAnalysis.waiting_for_photo)
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except Exception as e:
            logger.warning(f"edit_reply_markup (handwriting_new): {e}")
        await callback.message.answer("✍️ Отправьте следующее фото рукописного текста.")
        await safe_callback_answer(callback)

    @dp.callback_query(F.data == "handwriting_share")
    async def handwriting_share(callback: types.CallbackQuery):
        await safe_callback_answer(callback, "Начисляем бонус за шаринг...")
        await grant_bonus_analysis(callback.from_user.id, 1)

        # Read from DB (state is already cleared)
        async with get_session() as session_db:
            from sqlalchemy import select
            result = await session_db.execute(
                select(Consultation)
                .filter(Consultation.user_id == callback.from_user.id)
                .order_by(Consultation.created_at.desc())
                .limit(1)
            )
            last = result.scalar_one_or_none()

        ocr_text = last.symptoms.replace("Рукописный текст: ", "")[:300] if last else ""
        analysis_result = last.response[:500] if last else ""

        share_text = (
            "📝 **Мой анализ рукописного текста в MedAssistant Bot**\n\n"
            f"📄 Распознанный текст:\n{ocr_text}\n\n"
            f"📋 Анализ содержимого:\n{analysis_result}\n\n"
            "---\n"
            "🤖 Получи свой анализ — @Med24AssistantBot\n"
            "💼 Хочешь такого бота для своего бизнеса? — @Ivan_Zadov\n\n"
            "#медицина #распознаваниепочерка #telegrambot"
        )

        await callback.message.answer(
            "📤 **Готово к расшариванию**\n\n"
            "Скопируй текст ниже и поделись в чат, канал или соцсети:\n\n"
            f"```\n{share_text}\n```\n\n"
            "🎁 **Начислен бонус: +1 бесплатный анализ за шаринг!**\n"
            "💡 Подсказка: долгое удержание текста → копировать",
            reply_markup=get_main_keyboard(),
            parse_mode="Markdown"
        )

    # --- Lab Analysis Flow (via EasyOCR + LLM) ---

    @dp.message(F.text == "🔬 Расшифровка анализов")
    async def start_lab_analysis(message: types.Message, state: FSMContext):
        # Admin bypasses all limits
        if is_admin(message.from_user.id):
            await state.update_data(using_free=False, lab_package=0)
            await state.set_state(LabAnalysis.waiting_for_file)
            await message.answer(
                "🔬 **Расшифровка анализов**\n\n"
                "👑 Администратор — доступ без лимитов.\n\n"
                "Отправьте **фото** лабораторных результатов, и я расшифрую их.\n\n"
                "📸 Сфотографируйте бланк при хорошем освещении.\n"
                "⚠️ Я распознаю печатный текст.",
            )
            return

        # 1. Check purchased lab balance first
        lab_bal = await get_lab_balance(message.from_user.id)
        if lab_bal > 0:
            await state.update_data(using_free=False, using_lab_balance=True, lab_package=0)
            await state.set_state(LabAnalysis.waiting_for_file)
            await message.answer(
                "🔬 **Расшифровка анализов**\n\n"
                f"У вас **{lab_bal}** оплаченных анализов.\n\n"
                "Отправьте **фото** лабораторных результатов, и я расшифрую их.\n\n"
                "📸 Сфотографируйте бланк при хорошем освещении.\n"
                "⚠️ Я распознаю печатный текст.",
            )
            return

        # 2. Check free analyses
        free_count = await get_free_analyses(message.from_user.id)
        if free_count > 0:
            await state.update_data(using_free=True, lab_package=0)
            await state.set_state(LabAnalysis.waiting_for_file)
            await message.answer(
                "🔬 **Расшифровка анализов**\n\n"
                "У вас есть бесплатный анализ! 🎉\n\n"
                "Отправьте **фото** лабораторных результатов, и я расшифрую их.\n\n"
                "📸 Сфотографируйте бланк при хорошем освещении.\n"
                "⚠️ Я распознаю печатный текст.",
            )
            return

        # 3. Check daily limit
        can_proceed, count = await check_usage_limit(message.from_user.id)
        if not can_proceed:
            await message.answer(
                "⚠️ Вы исчерпали ежедневный лимит (3/3).\n\n"
                "🔹 Попробуйте завтра — лимит обновится\n"
                "🔹 Или пригласите друга (🎁 в меню)",
                reply_markup=get_main_keyboard(),
            )
            return

        # 4. Show pricing
        await state.set_state(LabAnalysis.waiting_for_pricing)
        await state.update_data(using_free=False)
        await message.answer(
            "🔬 **Расшифровка анализов**\n\n"
            "Выберите пакет анализов:\n\n"
            "📸 Отправляйте фото бланков — AI расшифрует показатели\n"
            "🧠 Подробный разбор каждого отклонения\n"
            "💡 Понятные рекомендации",
            reply_markup=get_lab_pricing_keyboard(),
        )

    @dp.callback_query(F.data.startswith("lab_pricing_"))
    async def lab_pricing_selection(callback: types.CallbackQuery, state: FSMContext):
        package = int(callback.data.split("_")[2])
        stars = STARS_PRICES.get(package, 5)

        # Create payment record
        payment = await create_payment_record(
            user_id=callback.from_user.id,
            amount=stars,
            package_size=package,
        )

        await state.update_data(lab_package=package, payment_pay_id=payment.pay_id)

        await callback.message.answer(
            f"🔬 **Пакет: {package} {'анализ' if package == 1 else 'анализов'}**\n\n"
            "Выберите способ оплаты:",
            reply_markup=get_payment_method_keyboard(package, payment.pay_id),
        )
        await safe_callback_answer(callback)

    # --- Payment method: Telegram Stars ---

    @dp.callback_query(F.data.startswith("pay_stars_"))
    async def pay_stars(callback: types.CallbackQuery, state: FSMContext):
        parts = callback.data.split("_")
        package = int(parts[2])
        pay_id = parts[3]
        stars = STARS_PRICES.get(package, 5)

        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass

        await callback.message.answer("⏳ Отправляю счёт...")
        await bot.send_invoice(
            chat_id=callback.from_user.id,
            title=f"🔬 Расшифровка анализов ({package} шт)",
            description=f"Пакет из {package} расшифровок лабораторных анализов.\n"
                        "Включает: AI-расшифровку, PDF-отчёт, рекомендации.",
            payload=f"lab_{package}_{pay_id}",
            currency="XTR",
            prices=[LabeledPrice(label=f"🔬 {package} {'анализ' if package == 1 else 'анализов'}", amount=stars)],
        )
        await safe_callback_answer(callback)

    # --- Payment method: Robokassa ---

    @dp.callback_query(F.data.startswith("pay_robokassa_"))
    async def pay_robokassa(callback: types.CallbackQuery, state: FSMContext):
        from core.robokassa import robokassa

        parts = callback.data.split("_")
        package = int(parts[2])
        pay_id = parts[3]
        amount = float(STARS_PRICES.get(package, 5))
        inv_id = int(hash(pay_id) % 1000000)  # numeric ID for Robokassa

        if not robokassa.is_configured():
            await callback.message.answer(
                "❌ **Оплата через Robokassa временно недоступна.**\n\n"
                "Платежный шлюз настраивается. Используйте Telegram Stars ⭐\n"
                "или попробуйте позже.",
                reply_markup=get_main_keyboard(),
            )
            await safe_callback_answer(callback)
            return

        payment_url = robokassa.generate_payment_url(inv_id, amount)
        if robokassa.login.startswith("@"):
            # Test mode until activation
            payment_url += "&IsTest=1"

        await callback.message.answer(
            f"💳 **Оплата через Robokassa**\n\n"
            f"📦 Пакет: **{package}** {'анализ' if package == 1 else 'анализов'}\n"
            f"💰 Сумма: **{amount:.2f}**\n\n"
            f"Нажмите кнопку ниже для оплаты картой или СБП:",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="💳 Перейти к оплате", url=payment_url)],
                    [InlineKeyboardButton(text="🔙 В меню", callback_data="lab_back_to_menu")],
                ]
            ),
        )
        await safe_callback_answer(callback)

    # --- Telegram Stars Payments ---

    @dp.pre_checkout_query()
    async def on_pre_checkout(pre_checkout_query: PreCheckoutQuery):
        await pre_checkout_query.answer(ok=True)

    @dp.message(F.successful_payment)
    async def on_successful_payment(message: types.Message, state: FSMContext):
        payload = message.successful_payment.invoice_payload  # "lab_{package}_{pay_id}"
        parts = payload.split("_")
        if len(parts) >= 3:
            pay_id = "_".join(parts[2:])  # extract pay_id after "lab_{package}_"
            try:
                await confirm_payment(pay_id)
                payment = await get_payment_by_pay_id(pay_id)
                if payment:
                    bal = await get_lab_balance(message.from_user.id)
                    await message.answer(
                        f"✅ **Оплата прошла успешно!**\n\n"
                        f"📦 Пакет: **{payment.package_size}** {'анализ' if payment.package_size == 1 else 'анализов'}\n"
                        f"⭐ Сумма: **{payment.amount} Stars**\n"
                        f"📊 Ваш баланс: **{bal}** {'анализ' if bal == 1 else 'анализов'}\n\n"
                        "🔬 Отправьте фото бланка анализов, чтобы начать!",
                        reply_markup=get_main_keyboard(),
                    )
                    return
            except Exception as e:
                logger.error(f"Payment confirm failed: {e}")
        await message.answer(
            "❌ Ошибка обработки платежа. Обратитесь в поддержку.",
            reply_markup=get_main_keyboard(),
        )

    async def _process_lab(user_id: int, message: types.Message, state: FSMContext, image_data: bytes):
        """Core lab analysis logic (shared between message and callback handlers)."""
        await message.answer("🔍 Распознаю текст через OCR... _(до 30 секунд)_")

        ocr_text = await llm_client.extract_text_from_image_openrouter(image_data)
        if not ocr_text.strip():
            raise ValueError("No text recognized")

        await state.update_data(ocr_text=ocr_text)

        await message.answer(            "🧠 Анализирую результаты...")
        prompt = (
            "Пользователь прислал фото лабораторных анализов. Вот что распознано:\n\n"
            f"{ocr_text}\n\n"
            "Ты — медицинский ассистент. Это лабораторные результаты пациента.\n\n"
            "Проанализируй результаты в формате:\n"
            "1. Общее впечатление — какие показатели в норме, какие отклоняются (перечисли ВСЕ отклонения)\n"
            "2. Для КАЖДОГО отклонения — что это может означать (развёрнуто, но без паники)\n"
            "3. Стоит ли обратиться к врачу и насколько срочно\n\n"
            "Тон — профессиональный, спокойный, информативный. "
            "Без лишних вступлений. Сразу перечисли все показатели, выходящие за пределы нормы, даже незначительные.\n"
            "Для каждого укажи возможные причины (кратко) и уровень срочности."
        )
        response = await llm_client.query(prompt)

        await message.answer(format_llm_result(response), reply_markup=get_lab_result_keyboard())

        try:
            async with get_session() as session_db:
                consultation = Consultation(
                    user_id=user_id,
                    symptoms="Лабораторные анализы:\n" + ocr_text[:3000],
                    response=response,
                    triage_level=None
                )
                session_db.add(consultation)
                await session_db.commit()
        except Exception as db_err:
            logger.error(f"Lab analysis DB save failed: {db_err}")

        data_state = await state.get_data()
        if not is_admin(user_id):
            if data_state.get('using_free'):
                await use_free_analysis(user_id)
            else:
                await increment_usage(user_id)

    async def process_lab_file_from_id(message: types.Message, file_id: str, state: FSMContext):
        """Download photo by file_id and process lab analysis."""
        await message.answer("📥 Загружаю фото...")
        try:
            file = await bot.get_file(file_id)
            image_data = (await bot.download_file(file.file_path)).read()
            await _process_lab(message.from_user.id, message, state, image_data)
        except ValueError:
            await message.answer(
                "⚠️ Не удалось распознать текст на фото.\n\n"
                "📸 **Советы:**\n"
                "• Убедитесь что текст чёткий и крупный\n"
                "• Снимайте при хорошем освещении\n"
                "• Держите камеру ровно, без размытия",
                reply_markup=get_main_keyboard(),
            )
        except Exception as e:
            logger.error(f"Lab analysis failed: {e}")
            await message.answer("⚠️ Что-то пошло не так. Попробуйте ещё раз.", reply_markup=get_main_keyboard())
        finally:
            await state.clear()

    @dp.message(LabAnalysis.waiting_for_file, F.photo)
    async def process_lab_file(message: types.Message, state: FSMContext):
        await process_lab_file_from_id(message, message.photo[-1].file_id, state)

    @dp.message(LabAnalysis.waiting_for_file)
    async def lab_invalid_file(message: types.Message):
        await message.answer("📸 Пожалуйста, отправьте **фото** бланка анализов, а не файл или другое сообщение.")

    # --- Handwriting PDF ---

    async def generate_handwriting_report(message: types.Message, user_id: int = None, user_name: str = None):
        try:
            async with get_session() as session_db:
                from sqlalchemy import select
                result = await session_db.execute(
                    select(Consultation)
                    .filter(
                        Consultation.user_id == (user_id or message.from_user.id),
                        Consultation.symptoms.startswith("Рукописный текст:"),
                    )
                    .order_by(Consultation.created_at.desc())
                    .limit(1)
                )
                last = result.scalar_one_or_none()
                if not last:
                    await message.answer("⚠️ Нет данных для отчёта. Сначала выполните анализ почерка.", reply_markup=get_main_keyboard())
                    return

                ocr_text = last.symptoms.replace("Рукописный текст: ", "")

                filepath = create_pdf_report(
                    user_name=user_name or message.from_user.first_name or "Пользователь",
                    symptoms="Распознанный рукописный текст:\n" + ocr_text,
                    analysis_result=last.response,
                    triage_level=last.triage_level or "Средний",
                    include_chart=False,
                )
                if not filepath:
                    await message.answer("⚠️ **Не удалось создать PDF.**\n\nПопробуйте ещё раз позже.", reply_markup=get_main_keyboard())
                    return
                pdf_file = FSInputFile(filepath)
                await message.answer_document(pdf_file, caption="📄 **PDF-отчёт анализа почерка**\n\nРаспознанный текст и анализ.")
        except Exception as e:
            logger.error(f"Handwriting report gen failed: {e}", exc_info=True)
            await message.answer("⚠️ **Не удалось создать PDF.**\n\nПроверьте подключение и попробуйте ещё раз.", reply_markup=get_main_keyboard())

    # --- Lab Result Actions ---

    async def generate_lab_report(message: types.Message, user_id: int = None, user_name: str = None):
        try:
            async with get_session() as session_db:
                from sqlalchemy import select
                result = await session_db.execute(
                    select(Consultation)
                    .filter(
                        Consultation.user_id == (user_id or message.from_user.id),
                        Consultation.symptoms.startswith("Лабораторные анализы:"),
                    )
                    .order_by(Consultation.created_at.desc())
                    .limit(1)
                )
                last = result.scalar_one_or_none()
                if not last:
                    await message.answer("⚠️ Нет данных для отчёта. Сначала выполните расшифровку анализов.", reply_markup=get_main_keyboard())
                    return

                ocr_text = last.symptoms.replace("Лабораторные анализы:\n", "")

                filepath = create_lab_pdf_report(
                    user_name=user_name or message.from_user.first_name or "Пользователь",
                    ocr_text=ocr_text,
                    analysis_result=last.response,
                )
                if not filepath:
                    await message.answer("⚠️ **Не удалось создать PDF.**\n\nПопробуйте ещё раз позже.", reply_markup=get_main_keyboard())
                    return
                pdf_file = FSInputFile(filepath)
                await message.answer_document(pdf_file, caption="📄 **PDF-отчёт расшифровки анализов**\n\nВаши лабораторные результаты в удобном формате.")
        except Exception as e:
            logger.error(f"Lab report gen failed: {e}", exc_info=True)
            await message.answer("⚠️ **Не удалось создать PDF.**\n\nПроверьте подключение и попробуйте ещё раз.", reply_markup=get_main_keyboard())

    @dp.callback_query(F.data == "lab_pdf")
    async def lab_pdf(callback: types.CallbackQuery):
        await safe_callback_answer(callback, "Генерирую PDF...")
        await generate_lab_report(callback.message, callback.from_user.id, callback.from_user.first_name)

    @dp.callback_query(F.data == "lab_new")
    async def lab_new(callback: types.CallbackQuery, state: FSMContext):
        await state.clear()
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except Exception as e:
            logger.warning(f"edit_reply_markup (lab_new): {e}")
        lab_bal = await get_lab_balance(callback.from_user.id)
        if lab_bal > 0:
            await state.update_data(using_free=False, using_lab_balance=True, lab_package=0)
            await state.set_state(LabAnalysis.waiting_for_file)
            await callback.message.answer("🔬 Отправьте следующее фото лабораторных результатов.")
            return await safe_callback_answer(callback)
        free_count = await get_free_analyses(callback.from_user.id)
        if free_count > 0:
            await state.update_data(using_free=True, lab_package=0)
            await state.set_state(LabAnalysis.waiting_for_file)
            await callback.message.answer("🔬 Отправьте следующее фото лабораторных результатов.")
        else:
            await state.set_state(LabAnalysis.waiting_for_pricing)
            await state.update_data(using_free=False)
            await callback.message.answer(
                "🔬 **Новый анализ**\n\nВыберите пакет:",
                reply_markup=get_lab_pricing_keyboard(),
            )
        await safe_callback_answer(callback)

    @dp.callback_query(F.data == "lab_share")
    async def lab_share(callback: types.CallbackQuery):
        await safe_callback_answer(callback, "Начисляем бонус за шаринг...")
        await grant_bonus_analysis(callback.from_user.id, 1)

        async with get_session() as session_db:
            from sqlalchemy import select
            result = await session_db.execute(
                select(Consultation)
                .filter(Consultation.user_id == callback.from_user.id)
                .order_by(Consultation.created_at.desc())
                .limit(1)
            )
            last = result.scalar_one_or_none()

        symptoms = last.symptoms.replace("Лабораторные анализы:\n", "")[:300] if last else ""
        analysis_text = last.response[:500] if last else ""

        share_text = (
            "🔬 **Мои лабораторные анализы — расшифровка в MedAssistant Bot**\n\n"
            f"📋 Показатели:\n{symptoms}\n\n"
            f"📊 Результат анализа:\n{analysis_text}\n\n"
            "---\n"
            "🤖 Получи расшифровку своих анализов — @Med24AssistantBot\n"
            "💼 Хочешь такого бота для бизнеса? — @Ivan_Zadov\n\n"
            "#медицина #анализы #расшифровка #telegrambot"
        )

        await callback.message.answer(
            "📤 **Готово к расшариванию**\n\n"
            "Скопируй текст ниже и поделись в чат, канал или соцсети:\n\n"
            f"```\n{share_text}\n```\n\n"
            "🎁 **Начислен бонус: +1 бесплатный анализ за шаринг!**\n"
            "💡 Подсказка: долгое удержание текста → копировать",
            reply_markup=get_main_keyboard(),
            parse_mode="Markdown"
        )

    @dp.callback_query(F.data == "lab_back_to_menu")
    async def lab_back_to_menu(callback: types.CallbackQuery, state: FSMContext):
        await state.clear()
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except Exception as e:
            logger.warning(f"edit_reply_markup (lab_back_to_menu): {e}")
        await callback.message.answer("🩺 Вернулись в меню. Чем помочь?", reply_markup=get_main_keyboard())
        await safe_callback_answer(callback)

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
                f"🎁 **Бесплатный анализ**\n\n"
                f"📊 У вас **{free_count}** бесплатных анализов.\n\n"
                "**Пригласите друга — получите ещё:**\n\n"
                "🔹 Отправьте другу ссылку ниже\n"
                "🔹 Друг переходит и запускает бота\n"
                "🔹 **Вы оба** получаете +1 бесплатный анализ ✨\n\n"
                f"🔗 **Ваша ссылка:**\n"
                f"`{referral_link}`\n\n"
                f"👥 Пришло по вашей ссылке: **{stats['total_referred']}** чел.\n\n"
                "👆 Нажмите на ссылку, чтобы скопировать"
            )
            await message.answer(text, reply_markup=get_main_keyboard())
        except Exception as e:
            logger.error(f"Referral error: {e}")
            await message.answer(
                "⚠️ Ошибка. Попробуйте позже.",
                reply_markup=get_main_keyboard(),
            )

    # --- Photo without context: save to state → choose type via inline buttons ---

    @dp.message(F.photo)
    async def photo_without_context(message: types.Message, state: FSMContext):
        # Save the file_id and file_unique_id so we can download later
        await state.update_data(
            photo_file_id=message.photo[-1].file_id,
            photo_file_unique_id=message.photo[-1].file_unique_id,
        )
        await state.set_state(WaitingPhotoType.choosing)
        await message.answer(
            "📸 **Фото получено**\n\n"
            "Выберите, что хотите сделать:",
            reply_markup=get_photo_type_keyboard(),
        )

    @dp.callback_query(WaitingPhotoType.choosing, F.data == "photo_type_lab")
    async def photo_type_lab(callback: types.CallbackQuery, state: FSMContext):
        # Guard: prevent double-processing
        data = await state.get_data()
        if data.get("processing"):
            return await safe_callback_answer(callback)
        file_id = data.get("photo_file_id")
        if not file_id:
            await callback.message.answer("❌ Ошибка: фото не найдено. Отправьте заново.")
            await state.clear()
            return await safe_callback_answer(callback)
        await state.update_data(using_free=False, lab_package=0, processing=True)
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass
        await safe_callback_answer(callback)
        await process_lab_file_from_id(callback.message, file_id, state)

    @dp.callback_query(WaitingPhotoType.choosing, F.data == "photo_type_handwriting")
    async def photo_type_handwriting(callback: types.CallbackQuery, state: FSMContext):
        data = await state.get_data()
        if data.get("processing"):
            return await safe_callback_answer(callback)
        file_id = data.get("photo_file_id")
        if not file_id:
            await callback.message.answer("❌ Ошибка: фото не найдено. Отправьте заново.")
            await state.clear()
            return await safe_callback_answer(callback)
        await state.update_data(using_free=False, processing=True)
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass
        await safe_callback_answer(callback)
        await process_handwriting_from_id(callback.from_user.id, callback.message, file_id, state)

    @dp.message(F.voice | F.video | F.video_note | F.animation)
    async def unsupported_media(message: types.Message):
        await message.answer(
            "⚠️ **Я понимаю только текст и фото.**\n\n"
            "Опишите симптомы текстом или отправьте фото анализов 🩺",
            reply_markup=get_main_keyboard()
        )

    @dp.message()
    async def echo_all(message: types.Message):
        await message.answer("Используйте кнопки ниже 👇", reply_markup=get_main_keyboard())


async def main():
    """Local development: polling mode."""
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

    register_all_handlers(dp, bot)

    try:
        me = await bot.get_me()
        logger.info(f"Bot connected! Username: @{me.username}, ID: {me.id}")
        logger.info(f"Bot name: {me.first_name}")
    except Exception as e:
        logger.error(f"Failed to connect to Telegram API: {e}")
        return

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