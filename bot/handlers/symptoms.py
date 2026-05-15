from aiogram import Router, types, F
import logging

logger = logging.getLogger(__name__)


async def safe_callback_answer(callback: types.CallbackQuery, *args, **kwargs):
    try:
        await callback.answer(*args, **kwargs)
    except Exception as e:
        logger.warning(f"callback.answer failed (expired?): {e}")

from aiogram.fsm.context import FSMContext
from bot.states import SymptomAnalysis
from bot.keyboards import get_time_keyboard, get_temperature_keyboard, get_gender_keyboard, get_main_keyboard
from core.llm_client import llm_client
from core.database import get_session, Consultation

router = Router()

EMERGENCY_KEYWORDS = [
    "112", "скорая", "умираю", "не могу дышать", "задыхаюсь",
    "сильное кровотечение", "кровь не останавливается", "потеря сознания",
    "инсульт", "инфаркт", "сердце остановилось", "анафилакси",
    "отек квинке", "судороги", "термический ожог", "химический ожог",
]


@router.message(F.text == "🔍 Анализ симптомов")
async def start_symptom_analysis(message: types.Message, state: FSMContext):
    await state.set_state(SymptomAnalysis.waiting_for_symptoms)
    await message.answer(
        "🔍 **Анализ симптомов**\n\n"
        "Опишите, что вас беспокоит. Чем подробнее, тем точнее анализ.\n\n"
        "*Пример: Головная боль 3 дня, тошнота, температура 37.8*",
        parse_mode="Markdown",
    )


@router.message(SymptomAnalysis.waiting_for_symptoms)
async def process_symptoms(message: types.Message, state: FSMContext):
    text = message.text.strip()

    # Emergency detection
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

    # Input validation
    if len(text) < 3:
        await message.answer(
            "⚠️ Пожалуйста, опишите симптомы подробнее (минимум 3 символа).",
            parse_mode="Markdown",
        )
        return

    await state.update_data(symptoms=text)
    await state.set_state(SymptomAnalysis.waiting_for_duration)
    await message.answer(
        "📅 **Как давно появились симптомы?**",
        reply_markup=get_time_keyboard(),
    )


@router.callback_query(SymptomAnalysis.waiting_for_duration, F.data.startswith("time_"))
async def process_duration(callback: types.CallbackQuery, state: FSMContext):
    duration_map = {
        "time_today": "Сегодня",
        "time_1_3_days": "1-3 дня",
        "time_week": "Неделю",
        "time_more": "Больше недели",
    }
    duration = duration_map.get(callback.data, callback.data)
    await state.update_data(duration=duration)
    await state.set_state(SymptomAnalysis.waiting_for_temperature)
    await callback.message.answer(
        "🌡️ **Есть ли температура?**",
        reply_markup=get_temperature_keyboard(),
    )
    await safe_callback_answer(callback)


@router.callback_query(SymptomAnalysis.waiting_for_temperature, F.data.startswith("temp_"))
async def process_temperature(callback: types.CallbackQuery, state: FSMContext):
    temp_map = {
        "temp_no": "Нет",
        "temp_low": "До 38°C",
        "temp_medium": "38-39°C",
        "temp_high": "Выше 39°C",
    }
    temperature = temp_map.get(callback.data, callback.data)
    await state.update_data(temperature=temperature)
    await state.set_state(SymptomAnalysis.waiting_for_age)
    await callback.message.answer("👤 **Ваш возраст?**")
    await safe_callback_answer(callback)


@router.message(SymptomAnalysis.waiting_for_age)
async def process_age(message: types.Message, state: FSMContext):
    await state.update_data(age=message.text)
    await state.set_state(SymptomAnalysis.waiting_for_gender)
    await message.answer(
        "⚧ **Ваш пол?**",
        reply_markup=get_gender_keyboard(),
    )


@router.callback_query(SymptomAnalysis.waiting_for_gender, F.data.startswith("gender_"))
async def process_gender(callback: types.CallbackQuery, state: FSMContext):
    gender_map = {
        "gender_male": "Мужской",
        "gender_female": "Женский",
    }
    gender = gender_map.get(callback.data, callback.data)
    await state.update_data(gender=gender)
    await state.set_state(SymptomAnalysis.analyzing)
    await callback.message.answer("⏳ Анализирую симптомы... Подождите немного.")
    await safe_callback_answer(callback)

    data = await state.get_data()
    prompt = (
        f"Пользователь описывает симптомы:\n"
        f"- Симптомы: {data.get('symptoms', 'Не указаны')}\n"
        f"- Длительность: {data.get('duration', 'Не указана')}\n"
        f"- Температура: {data.get('temperature', 'Не указана')}\n"
        f"- Возраст: {data.get('age', 'Не указан')}\n"
        f"- Пол: {data.get('gender', 'Не указан')}\n\n"
        f"Проведите анализ симптомов согласно вашим инструкциям."
    )

    try:
        response = await llm_client.query(prompt)

        # Save to DB for reports
        try:
            async with get_session() as session_db:
                consultation = Consultation(
                    user_id=callback.message.from_user.id,
                    symptoms=data.get('symptoms', 'Не указаны'),
                    response=response,
                    triage_level=None
                )
                session_db.add(consultation)
                await session_db.commit()
        except Exception as db_err:
            pass  # Silently fail DB save, user still gets response

        await callback.message.answer(
            response,
            reply_markup=get_main_keyboard(),
            parse_mode="Markdown",
        )
    except Exception as e:
        await callback.message.answer(
            "⚠️ Произошла ошибка при анализе. Попробуйте позже.\n\n"
            "⚠️ *Это не медицинский диагноз. Обратитесь к врачу.*",
            reply_markup=get_main_keyboard(),
            parse_mode="Markdown",
        )

    await state.clear()
