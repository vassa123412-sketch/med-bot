import re

from core.llm_client import DISCLAIMER

MAX_LENGTH = 4000


def format_llm_result(text: str) -> str:
    if not text:
        return text

    # 1. Убираем дисклеймер, который могла написать LLM (бот добавит свой)
    text = _remove_disclaimer(text)

    # 2. Убираем множественные пустые строки (больше 2 подряд)
    text = re.sub(r'\n{3,}', '\n\n', text)

    # 3. Если текст не начинается с эмодзи — добавляем 📊
    if not _starts_with_emoji(text):
        text = f"📊 **Результаты анализа**\n\n{text}"

    # 4. Добавляем разделители между заголовками, если их нет
    text = _ensure_separators(text)

    # 5. Убираем хвостовые пробелы в каждой строке
    text = '\n'.join(line.rstrip() for line in text.split('\n'))

    # 6. Добавляем стандартный дисклеймер
    text = text.rstrip() + DISCLAIMER

    # 7. Обрезаем до лимита Telegram
    if len(text) > MAX_LENGTH:
        text = text[:MAX_LENGTH - 200]
        last_space = text.rfind(' ')
        if last_space > MAX_LENGTH // 2:
            text = text[:last_space]
        text += f"\n\n📄 **Результат слишком длинный.**\nПолная версия — в PDF."

    return text


def _remove_disclaimer(text: str) -> str:
    """Удаляет дисклеймер, сгенерированный LLM."""
    patterns = [
        r'⚠️\s*\*{0,2}[^\n]*?(?:дисклеймер|не является диагнозом|не заменяет|не врач|искусственный интеллект)[^\n]*\*{0,2}.*',
        r'Важное предупреждение[^\n]*.*',
        r'Настоятельно рекомендую[^\n]*показать[^\n]*',
    ]
    for p in patterns:
        text = re.sub(p, '', text, flags=re.DOTALL | re.IGNORECASE)
    return text.strip()


def _starts_with_emoji(text: str) -> bool:
    emoji_pattern = re.compile(
        r'[\U0001F300-\U0001FFFF\u2600-\u27BF\u2700-\u27BF'
        r'\U0001F600-\U0001F64F\U0001F680-\U0001F6FF'
        r'\U0001F1E0-\U0001F1FF\u2B50\u2049\u203C'
        r'\U00002702-\U000027B0\u24C2-\U0001F251'
        r'\U0001F004\u00A9\u00AE\u2122\u23CF'
        r'\u23E9-\u23F3\u23F8-\u23FA\u25AA\u25AB\u25B6'
        r'\u25C0\u25FB-\u25FE\u2600-\u2604\u260E\u2611'
        r'\u2614\u2615\u2618\u261D\u2620\u2622\u2623'
        r'\u2626\u262A\u262E\u262F\u2638-\u263A\u2640\u2642'
        r'\u2648-\u2653\u2660\u2663\u2665\u2666\u2668'
        r'\u267B\u267F\u2692-\u2697\u2699\u269B\u269C'
        r'\u26A0\u26A1\u26AA\u26AB\u26B0\u26B1\u26BD'
        r'\u26BE\u26C4\u26C5\u26C8\u26CE\u26CF\u26D1'
        r'\u26D3\u26D4\u26E9\u26EA\u26F0-\u26F5'
        r'\u26F7-\u26FA\u26FD\u2702\u2705\u2708-\u270D'
        r'\u270F\u2712\u2714\u2716\u271D\u2721\u2728'
        r'\u2733\u2734\u2744\u2747\u274C\u274E'
        r'\u2753-\u2755\u2757\u2763\u2764\u2795-\u2797'
        r'\u27A1\u27B0\u27BF\U0001F000-\U0001FFFF]'
    )
    return bool(emoji_pattern.match(text.strip()))


def _ensure_separators(text: str) -> str:
    """Добавляет разделители между секциями, если их нет."""
    section_headers = re.findall(r'^#{1,3}\s+.*$|^\*\*.*\*\*$|^[🟢🟡🔴📊💡].*$', text, re.MULTILINE)
    if len(section_headers) <= 1:
        return text

    lines = text.split('\n')
    result = []
    prev_was_header = False

    for line in lines:
        is_header = bool(re.match(r'^#{1,3}\s+|^\*\*.*\*\*$|^[🟢🟡🔴📊💡]', line))
        if is_header and prev_was_header:
            result.append('---')
        elif is_header and len(result) > 0 and result[-1].strip():
            last = result[-1].strip()
            if last != '---' and not last.startswith('---'):
                result.append('---')
        result.append(line)
        prev_was_header = is_header

    return '\n'.join(result)
