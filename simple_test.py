import re

# Test the filtering logic with ASCII-only output
analysis_result = "@Ivan_Zadov — разработка Telegram-ботов\nTest with numbers: 1, 2, 3.\nCyrillic: головная боль.\nSymbols: ● ◆ ■ ▲"

print("Testing filter logic...")
print("Original contains Ivan_Zadov:", "Ivan_Zadov" in analysis_result)

# Clean up markdown
clean_text = re.sub(r'[*_#`>`()\[\]]', '', analysis_result)
print("After markdown cleanup, contains Ivan_Zadov:", "Ivan_Zadov" in clean_text)

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
print("Filtered content contains Ivan_Zadov:", "Ivan_Zadov" in filtered_content)
print("Filtered content contains 'разработка Telegram-ботов':", "разработка Telegram-ботов" in filtered_content)
print("Filtered content:")
print(repr(filtered_content))

# Check if any unwanted strings remain
unwanted_found = []
for pattern in unwanted_patterns:
    if re.search(pattern, filtered_content, re.IGNORECASE):
        unwanted_found.append(pattern)

if unwanted_found:
    print("FAILED: Following patterns were NOT filtered out:", unwanted_found)
else:
    print("SUCCESS: All unwanted patterns were filtered out")