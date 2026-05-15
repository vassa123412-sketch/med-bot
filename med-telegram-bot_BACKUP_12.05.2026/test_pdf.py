import sys
sys.path.append('.')
from reports.pdf_generator import create_pdf_report
import os
# Dummy data
user_name = 'Тестовый Пациент'
symptoms = 'Головная боль, тошнота'
analysis_result = 'Это тестовый результат анализа. Все показатели в норме.'
triage_level = 'Средний'
recommendations = ['Отдых', 'Пить больше воды', 'При необходимости обратиться к врачу']
include_chart = True
try:
    filepath = create_pdf_report(user_name, symptoms, analysis_result, triage_level, recommendations, include_chart)
    print(f'PDF generated successfully: {filepath}')
    if os.path.exists(filepath):
        print(f'File size: {os.path.getsize(filepath)} bytes')
    else:
        print('File not found')
except Exception as e:
    print(f'Error generating PDF: {e}')
    import traceback
    traceback.print_exc()