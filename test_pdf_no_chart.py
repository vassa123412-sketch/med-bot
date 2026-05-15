import sys
sys.path.append('.')
from reports.pdf_generator import create_pdf_report
import os
# Dummy data
user_name = 'Тестовый Пациент'
symptoms = 'Головная боль, тошнота, слабость'
analysis_result = 'Это тестовый результат анализа. Все показатели в норме. Рекомендуется отдых и наблюдение.'
triage_level = 'Низкий'
recommendations = ['Отдых', 'Пить больше воды', 'Следить за симптомами']
include_chart = False
try:
    filepath = create_pdf_report(user_name, symptoms, analysis_result, triage_level, recommendations, include_chart)
    print(f'PDF generated successfully (no chart): {filepath}')
    if os.path.exists(filepath):
        print(f'File size: {os.path.getsize(filepath)} bytes')
    else:
        print('File not found')
except Exception as e:
    print(f'Error generating PDF: {e}')
    import traceback
    traceback.print_exc()