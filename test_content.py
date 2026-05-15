import sys
sys.path.append('.')
from reports.pdf_generator import create_pdf_report
import os

# Test what happens with numbers and potential problematic strings
user_name = 'Тест Пользователь'
symptoms = 'Симптом 1, Симптом 2, Симптом 3'
# Test if the problematic string gets added somewhere
analysis_result = '''Это тестовый результат с числами: 1, 2, 3.
Также проверяем: @Ivan_Zadov — разработка Telegram-ботов
И другие символы: ● ◆ ■ ▲'''
triage_level = 'Средний'
recommendations = ['Рекомендация 1', 'Рекомендация 2', 'Рекомендация 3']
include_chart = True

print("Testing with potential problematic string...")
try:
    filepath = create_pdf_report(
        user_name=user_name,
        symptoms=symptoms,
        analysis_result=analysis_result,
        triage_level=triage_level,
        recommendations=recommendations,
        include_chart=include_chart
    )
    print(f'[OK] PDF generated: {filepath}')
    print(f'[INFO] Size: {os.path.getsize(filepath)} bytes')
except Exception as e:
    print(f'[ERROR] {e}')
    import traceback
    traceback.print_exc()