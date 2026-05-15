import re

# Test the filtering logic
analysis_result = """@Ivan_Zadov — разработка Telegram-ботов
Это тестовый результат с цифрами: 1, 2, 3, 4, 5.
Проверяем отображение кириллицы и чисел без квадратиков.
Также есть символы: ● ◆ ■ ▲
Еще одна строка для проверки."""

print("Original text:")
print(repr(analysis_result))
print("\nOriginal text (formatted):")
print(analysis_result)

# Clean up markdown
clean_text = re.sub(r'[*_#`>`()\[\]]', '', analysis_result)
print("\nAfter markdown cleanup:")
print(repr(clean_text))

# Filter out lines containing developer signatures or unwanted content
unwanted_patterns = [
    r'Ivan_Zadov',
    r'разработка Telegram-ботов',
    r'@Ivan_Zadov',
    r'разработка ботов'
]

filtered_lines = []
for line in clean_text.split('\n'):
    line = line.strip()
    if line:
        # Check if line contains any unwanted patterns
        skip_line = False
        for pattern in unwanted_patterns:
            if re.search(pattern, line, re.IGNORECASE):
                skip_line = True
                break
        if not skip_line:
            filtered_lines.append(line)

filtered_content = '\n'.join(filtered_lines)
print("\nFiltered content:")
print(repr(filtered_content))
print("\nFiltered content (formatted):")
print(filtered_content)

# Check if any unwanted strings remain
unwanted_found = []
for pattern in unwanted_patterns:
    if re.search(pattern, filtered_content, re.IGNORECASE):
        unwanted_found.append(pattern)

if unwanted_found:
    print(f"\n❌ FAILED: Following patterns were NOT filtered out: {unwanted_found}")
else:
    print(f"\n✅ SUCCESS: All unwanted patterns were filtered out")