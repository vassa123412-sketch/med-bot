import sys
sys.path.append('.')
from reports.pdf_generator import create_pdf_report
import os

# Test with the exact content the user complained about
user_name = 'Тестовый Пользователь'
symptoms = 'Головная боль, тошнота, слабость, головокружение'
analysis_result = '''@Ivan_Zadov — разработка Telegram-ботов
Это тестовый результат с цифрами: 1, 2, 3, 4, 5.
Проверяем отображение кириллицы и чисел без квадратиков.
Также есть символы: ● ◆ ■ ▲'''
triage_level = 'Средний'
recommendations = [
    'Прием лекарственных препаратов',
    'Постельный режим',
    'Обильное питье',
    'Контроль температуры'
]
include_chart = True

print("Testing PDF generation with problematic content...")
try:
    filepath = create_pdf_report(
        user_name=user_name,
        symptoms=symptoms,
        analysis_result=analysis_result,
        triage_level=triage_level,
        recommendations=recommendations,
        include_chart=include_chart
    )
    print(f'[✓] PDF generated successfully: {filepath}')
    print(f'[INFO] File size: {os.path.getsize(filepath)} bytes')
    
    # Test without chart as well
    filepath_no_chart = create_pdf_report(
        user_name=user_name,
        symptoms=symptoms,
        analysis_result=analysis_result,
        triage_level=triage_level,
        recommendations=recommendations,
        include_chart=False
    )
    print(f'[✓] PDF (no chart) generated: {filepath_no_chart}')
    print(f'[INFO] File size: {os.path.getsize(filepath_no_chart)} bytes')
    
except Exception as e:
    print(f'[✗] Error generating PDF: {e}')
    import traceback
    traceback.print_exc()