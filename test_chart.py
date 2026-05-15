import sys
sys.path.append('.')
from reports.pdf_generator import create_symptom_chart
import os

# Test chart generation
symptoms_data = {
    'symptoms': ['Головная боль', 'Тошнота', 'Слабость'],
    'severity': [5, 3, 4],
    'urgency': 'Средний'
}
output_path = "test_chart.png"
try:
    create_symptom_chart(symptoms_data, output_path)
    if os.path.exists(output_path):
        print(f"Chart generated successfully: {output_path}")
        print(f"File size: {os.path.getsize(output_path)} bytes")
    else:
        print("Chart file not found")
except Exception as e:
    print(f"Error generating chart: {e}")
    import traceback
    traceback.print_exc()