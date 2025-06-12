import os
import re
import sys
import string

FILE_PATH = ''
NEW_FILE_PATH = ''


def unique_strings(arr):
    return list(dict.fromkeys(arr))


def write_lines_to_file(lines, filename):
    with open(filename, 'w', encoding='utf-8') as f:
        for line in lines:
            f.write(line + '\n')


def is_valid_pattern(pattern: str) -> bool:
    if pattern.startswith('.') or pattern.endswith('.'):
        return False

    label_re = re.compile(r'^[A-Za-z0-9-]{1,63}$')
    for label in pattern.split('.'):
        if label == '*':
            continue
        if '*' in label:
            return False
        if not label_re.match(label):
            return False
    return True


def has_more_than_two_numbers_or_letters(s):
    digit_count = sum(c.isdigit() for c in s)
    letter_count = sum(c.isalpha() for c in s)
    return digit_count + letter_count >= 2


def main():
    pattern_www = r'^(?:https?://(?:www\.)?|www\.)'
    pattern_beginning = r'^([a-z]{1,4})\.'
    pattern_end = r'\.([a-z]{1,4})$'
    pattern_other = r'\b(social|blogspot|world|co|go|com|net|tv|org|edu|gov)\b'
    parsed_lines = []

    with open(FILE_PATH, 'r') as file:
        for line in file:
            newline = line.strip()
            # parts = newline.split(maxsplit=1)  # for host files
            # newline = parts[1] if len(parts) > 1 else ''  # for host files
            newline = re.sub(pattern_www, '', newline)
            newline = re.sub(pattern_beginning, '*.', newline)
            newline = re.sub(pattern_end, '.*', newline)
            newline = re.sub(pattern_other, '*', newline)
            if (has_more_than_two_numbers_or_letters(newline) 
                and is_valid_pattern(newline) and '.' in newline):
                parsed_lines.append(newline)
            else:
                print(newline)

    parsed_lines = unique_strings(parsed_lines)
    write_lines_to_file(parsed_lines, NEW_FILE_PATH)


def main_2():
    parsed_lines = []
    with open(FILE_PATH, 'r') as file:
        for line in file:
            newline = line.strip()
            if (has_more_than_two_numbers_or_letters(newline) 
                and is_valid_pattern(newline) and '.' in newline
                and len(newline) <= 50):
                parsed_lines.append(newline)
            else:
                print(newline)
    parsed_lines = unique_strings(parsed_lines)
    write_lines_to_file(parsed_lines, NEW_FILE_PATH)


if __name__ == '__main__':
    main()
