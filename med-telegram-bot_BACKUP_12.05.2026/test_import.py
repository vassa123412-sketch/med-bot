import sys
print(sys.path)
try:
    from reportlab.pdfbase import pdfbase
    print("pdfbase imported")
except Exception as e:
    print(f"Import error: {e}")