import sys
sys.path.append('.')
from reports.pdf_generator import create_pdf_report
import os
# Dummy data with more Cyrillic
user_name = 'Иванов Иван Иванович'
symptoms = 'Боль в груди, одышка, потливость, чувство страха'
analysis_result = '''Пациент демонстрирует классические симптомы острых коронарных синдромов. 
Требуется немедленное обращение в отделение неотложной помощи. 
Рекомендуется выполнить ЭКГ и анализ кардиомаркеров.'''
triage_level = 'Высокий'
recommendations = [
    'Немедленно вызвать скорую помощь',
    'Прекратить физическую активность',
    'Принять аспирин 300 мг внутривенно',
    'Госпитализация в кардиологическое отделение'
]
include_chart = True
try:
    filepath = create_pdf_report(user_name, symptoms, analysis_result, triage_level, recommendations, include_chart)
    print(f'PDF generated successfully: {filepath}')
    if os.path.exists(filepath):
        print(f'File size: {os.path.getsize(filepath)} bytes')
        # Try to get the absolute path
        abs_path = os.path.abspath(filepath)
        print(f'Absolute path: {abs_path}')
    else:
        print('File not found')
except Exception as e:
    print(f'Error generating PDF: {e}')
    import traceback
    traceback.print_exc()