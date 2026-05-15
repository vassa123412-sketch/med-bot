import os
import sys

target = '@Ivan_Zadov — разработка Telegram-ботов'
for root, dirs, files in os.walk('.'):
    for file in files:
        if file.endswith('.py') or file.endswith('.txt') or file.endswith('.md') or file.endswith('.env'):
            path = os.path.join(root, file)
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    if target in content:
                        print(f'Found in: {path}')
            except Exception as e:
                pass