import sys
sys.path.append('.')
from reports.pdf_generator import create_pdf_report
import os

# Test data
user_name = 'Тестовый Пациент'
symptoms = 'Головная боль, тошнота, слабость'
analysis_result = 'Тестовый анализ: все показатели в норме.'
triage_level = 'Средний'
recommendations = ['Отдых', 'Пить больше воды']
include_chart = True

try:
    filepath = create_pdf_report(user_name, symptoms, analysis_result, triage_level, recommendations, include_chart)
    print(f'PDF generated: {filepath}')
    print(f'Size: {os.path.getsize(filepath)} bytes')
except Exception as e:
    print(f'Error: {e}')
    import traceback
    traceback.print_exc()