import sys
sys.path.append('.')
from reports.pdf_generator import create_pdf_report
import os

# Test with extensive Cyrillic text
user_name = 'Иванов Иван Иванович'
symptoms = '''Головная боль, головокружение, тошнота, рвота, 
нарушение координации, двоение в глазах, онемение конечностей'''
analysis_result = '''На основании предоставленной симптоматики существует подозрение на 
острое нарушение мозгового кровообращения (инсульт). 
Требуется немедленная госпитализация в неврологическое отделение. 
Рекомендуется выполнить срочную МРТ головного мозга и консультацию невролога.'''
triage_level = 'Высокий'
recommendations = [
    'Немедленно вызвать скорую помощь (103 или 112)',
    'Уложить пациента с приподнятым головным концом',
    'Измерять артериальное давление и пульс каждые 5 минут',
    'Не давать еду и напитки до приезда врача',
    'Следить за дыханием и сознанием'
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
    print(f'[OK] PDF generated successfully: {filepath}')
    print(f'[INFO] File size: {os.path.getsize(filepath)} bytes')
    
    # Also test without chart
    filepath_no_chart = create_pdf_report(
        user_name=user_name,
        symptoms=symptoms,
        analysis_result=analysis_result,
        triage_level=triage_level,
        recommendations=recommendations,
        include_chart=False
    )
    print(f'[OK] PDF (no chart) generated: {filepath_no_chart}')
    print(f'[INFO] File size: {os.path.getsize(filepath_no_chart)} bytes')
    
except Exception as e:
    print(f'[ERROR] Error generating PDF: {e}')
    import traceback
    traceback.print_exc()