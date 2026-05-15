import sys
sys.path.append('.')

# Test font registration
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import os

print("Testing font registration...")
print("Looking for fonts in C:/Windows/Fonts/")

font_files = [
    ('C:/Windows/Fonts/arial.ttf', 'Arial'),
    ('C:/Windows/Fonts/arialbd.ttf', 'ArialBold'),
    ('C:/Windows/Fonts/ariali.ttf', 'ArialItalic'),
    ('C:/Windows/Fonts/arialbi.ttf', 'ArialBoldItalic')
]

for font_path, font_name in font_files:
    if os.path.exists(font_path):
        print(f"[+] Found {font_name}: {font_path}")
        try:
            pdfmetrics.registerFont(TTFont(font_name, font_path))
            print(f"    Successfully registered {font_name}")
        except Exception as e:
            print(f"    Failed to register {font_name}: {e}")
    else:
        print(f"[-] Missing {font_name}: {font_path}")

print("\nRegistered fonts:")
for font in pdfmetrics.getRegisteredFontNames():
    print(f"  {font}")