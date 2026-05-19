from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton


def get_main_keyboard() -> ReplyKeyboardMarkup:
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🔍 Анализ симптомов"), KeyboardButton(text="🔬 Расшифровка анализов")],
            [KeyboardButton(text="✍️ Анализ почерка"), KeyboardButton(text="🎁 Бесплатный анализ")],
            [KeyboardButton(text="🚑 Экстренная помощь"), KeyboardButton(text="📋 Правовая информация")],
        ],
        resize_keyboard=True,
        input_field_placeholder="Выберите действие 👇"
    )
    return keyboard


def get_legal_keyboard() -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📄 Пользовательское соглашение", callback_data="legal_terms"),
            ],
            [
                InlineKeyboardButton(text="🔒 Политика конфиденциальности", callback_data="legal_privacy"),
            ],
    [
        InlineKeyboardButton(text="⚕️ Медицинский дисклеймер", callback_data="legal_disclaimer"),
    ],
    [
        InlineKeyboardButton(text="📞 Контакты и поддержка", callback_data="legal_support"),
    ],
    [
        InlineKeyboardButton(text="🔙 В меню", callback_data="legal_back"),
    ],
        ]
    )
    return keyboard


def get_time_keyboard() -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Сегодня", callback_data="time_today"),
                InlineKeyboardButton(text="1-3 дня", callback_data="time_1_3_days"),
            ],
            [
                InlineKeyboardButton(text="Неделю", callback_data="time_week"),
                InlineKeyboardButton(text="Больше недели", callback_data="time_more"),
            ],
            [
                InlineKeyboardButton(text="⬅ Назад", callback_data="back_to_symptoms"),
            ],
        ]
    )
    return keyboard


def get_temperature_keyboard() -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Нет", callback_data="temp_no"),
                InlineKeyboardButton(text="До 38°C", callback_data="temp_low"),
            ],
            [
                InlineKeyboardButton(text="38-39°C", callback_data="temp_medium"),
                InlineKeyboardButton(text="Выше 39°C", callback_data="temp_high"),
            ],
            [
                InlineKeyboardButton(text="⬅ Назад", callback_data="back_to_duration"),
            ],
        ]
    )
    return keyboard


def get_gender_keyboard() -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="👨 Мужской", callback_data="gender_male"),
                InlineKeyboardButton(text="👩 Женский", callback_data="gender_female"),
            ],
            [
                InlineKeyboardButton(text="⬅ Назад", callback_data="back_to_temp"),
            ],
        ]
    )
    return keyboard


def get_age_keyboard() -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="0-17 лет", callback_data="age_0_17"),
                InlineKeyboardButton(text="18-35 лет", callback_data="age_18_35"),
            ],
            [
                InlineKeyboardButton(text="36-55 лет", callback_data="age_36_55"),
                InlineKeyboardButton(text="55+ лет", callback_data="age_55_plus"),
            ],
            [
                InlineKeyboardButton(text="⬅ Назад", callback_data="back_to_gender"),
            ],
        ]
    )
    return keyboard


def get_result_keyboard() -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📄 Скачать PDF", callback_data="result_pdf"),
                InlineKeyboardButton(text="📤 Отправить врачу", callback_data="result_doctor"),
            ],
            [
                InlineKeyboardButton(text="🔍 Новый анализ", callback_data="result_restart"),
                InlineKeyboardButton(text="📤 Поделиться", callback_data="result_share"),
            ],
        ]
    )
    return keyboard


def get_back_to_menu_keyboard() -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔙 В меню", callback_data="back_to_menu")],
        ]
    )
    return keyboard


def get_handwriting_result_keyboard() -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📄 Скачать PDF", callback_data="handwriting_pdf"),
                InlineKeyboardButton(text="📤 Поделиться", callback_data="handwriting_share"),
            ],
            [
                InlineKeyboardButton(text="✍️ Новый текст", callback_data="handwriting_new"),
            ],
        ]
    )
    return keyboard


STARS_PRICES = {1: 5, 3: 10, 10: 25}

def get_lab_pricing_keyboard() -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🔬 1 анализ — ⭐5", callback_data="lab_pricing_1"),
            ],
            [
                InlineKeyboardButton(text="🔥 3 анализа — ⭐10", callback_data="lab_pricing_3"),
            ],
            [
                InlineKeyboardButton(text="💎 10 анализов — ⭐25", callback_data="lab_pricing_10"),
            ],
            [
                InlineKeyboardButton(text="🔙 В меню", callback_data="lab_back_to_menu"),
            ],
        ]
    )
    return keyboard


def get_lab_result_keyboard() -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📄 Скачать PDF", callback_data="lab_pdf"),
                InlineKeyboardButton(text="📤 Поделиться", callback_data="lab_share"),
            ],
            [
                InlineKeyboardButton(text="🔬 Новый анализ", callback_data="lab_new"),
            ],
        ]
    )
    return keyboard


def get_payment_keyboard(pay_id: str) -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="⏳ Оплата временно недоступна", callback_data="noop"),
            ],
            [
                InlineKeyboardButton(text="🔙 В меню", callback_data="lab_back_to_menu"),
            ],
        ]
    )
    return keyboard


def get_payment_loading_keyboard() -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⏳ Проверка оплаты...", callback_data="noop")],
        ]
    )
    return keyboard


def get_photo_type_keyboard() -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🔬 Расшифровка анализов", callback_data="photo_type_lab"),
            ],
            [
                InlineKeyboardButton(text="✍️ Анализ почерка", callback_data="photo_type_handwriting"),
            ],
        ]
    )
    return keyboard


def get_admin_keyboard() -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="👤 Инфо обо мне", callback_data="admin_me"),
            ],
            [
                InlineKeyboardButton(text="🔄 Сбросить мои лимиты", callback_data="admin_reset_me"),
            ],
            [
                InlineKeyboardButton(text="➕ +5 анализов мне", callback_data="admin_addfree_5"),
                InlineKeyboardButton(text="➕ +10 анализов мне", callback_data="admin_addfree_10"),
            ],
            [
                InlineKeyboardButton(text="👤 Инфо о другом", callback_data="admin_user_other"),
                InlineKeyboardButton(text="🔄 Сброс другого", callback_data="admin_reset_other"),
            ],
            [
                InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats"),
            ],
            [
                InlineKeyboardButton(text="❌ Закрыть", callback_data="admin_close"),
            ],
        ]
    )
    return keyboard