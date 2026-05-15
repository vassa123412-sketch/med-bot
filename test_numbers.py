import sys
sys.path.append('.')
from reports.pdf_generator import create_pdf_report
import os

# Test with numbers
user_name = 'Тест'
symptoms = 'Симптом1, Симптом2'
analysis_result = '''Числа: 1, 2, 3, 4, 5.
Также проверяем: 10, 20, 30.
И символы: ● ◆ ■ ▲'''
triage_level = 'Средний'
recommendations = ['Рекомендация 1', 'Рекомендация 2']
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
except Exception as e:
    print(f'[ERROR] {e}')
    import traceback
    traceback.print_exc()