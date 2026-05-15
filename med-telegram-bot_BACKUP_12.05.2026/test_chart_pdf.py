import sys
sys.path.append('.')
from reports.pdf_generator import create_pdf_report
import os

# Test data with symptoms
user_name = 'Тестовый Пациент'
symptoms = 'Головная боль, тошнота, слабость, головокружение'
analysis_result = 'Умеренная выраженность симптомов. Рекомендуется наблюдение.'
triage_level = 'Средний'
recommendations = ['Отдых', 'Пить больше воды', 'Избегать стресса']
include_chart = True

try:
    filepath = create_pdf_report(user_name, symptoms, analysis_result, triage_level, recommendations, include_chart)
    print(f'[OK] PDF generated: {filepath}')
    print(f'[INFO] Size: {os.path.getsize(filepath)} bytes')
except Exception as e:
    print(f'[ERROR] {e}')
    import traceback
    traceback.print_exc()