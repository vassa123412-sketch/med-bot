import sys
sys.path.append('.')
from reports.pdf_generator import create_pdf_report
import os

# Test with various Unicode characters (Cyrillic, plus some specials)
user_name = 'Тестовый Пользователь'
symptoms = 'Боль в голове, тошнота, слабость, потливость'
analysis_result = '''Пациент демонстрирует следующие симптомы: 
- Головная боль средней интенсивности
- Тошнота и рвота
- Общая слабость
Рекомендуется: 
1. Покой и обильное питье
2. Прием жаропонижающих при необходимости
3. Обращение к врачу при ухудшении состояния'''
triage_level = 'Средний'
recommendations = [
    'Соблюдать постельный режим',
    'Пить теплую жидкость (чай, вода)',
    'Принимать парацетамол по 500 мг при температуре выше 38.5°C',
    'Избегать физических нагрузок',
    'Контролировать температуру тела'
]
include_chart = True

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
    
    # Also test without chart to see if the issue is chart-related
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