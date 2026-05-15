import sys
sys.path.append('.')
from reports.pdf_generator import create_pdf_report
import os

# Test with the exact problematic string mentioned by user
user_name = 'Тестовый Пользователь'
symptoms = 'Головная боль, тошнота, слабость'
analysis_result = '''Это тестовый результат с проблемной строкой: @Ivan_Zadov — разработка Telegram-ботов
И другие цифры: 1, 2, 3, 4, 5.
Проверяем отображение цифр и кириллицы.'''
triage_level = 'Средний'
recommendations = ['Рекомендация 1', 'Рекомендация 2', 'Рекомендация 3']
include_chart = True

print("Testing with problematic string that should be filtered out...")
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
    
    # Also test without chart to isolate issues
    filepath_no_chart = create_pdf_report(
        user_name=user_name,
        symptoms=symptoms,
        analysis_result=analysis_result,
        triage_level=triage_level,
        recommendations=recommendations,
        include_chart=False
    )
    print(f'[OK] PDF (no chart) generated: {filepath_no_chart}')
    print(f'[INFO] Size: {os.path.getsize(filepath_no_chart)} bytes')
    
except Exception as e:
    print(f'[ERROR] Error generating PDF: {e}')
    import traceback
    traceback.print_exc()