import re
import csv
from typing import Union
from pathlib import Path
import os

CSV_PATH = ''
VAULT_PATH = ''


def extract_year(value: Union[str, int]) -> int:
    if isinstance(value, int):
        return value
    s = str(value).strip()
    if re.fullmatch(r"\d{4}", s):
        return int(s)
    match = re.search(r"\b(19\d{2}|20\d{2}|21\d{2})\b", s)
    if match:
        return int(match.group(1))
    raise ValueError(f"Could not extract a valid year from: {value!r}")


def sanitize_filename(filename: str, replacer: str) -> str:
    base, ext = re.match(r"^(.*?)(\.[^.]*)?$", filename).groups()
    invalid_chars = r'[<>:"/\\|?*\x00-\x1F]'
    base = re.sub(invalid_chars, replacer, base)
    base = base.rstrip(" .")
    reserved = {
        "CON", "PRN", "AUX", "NUL",
        *(f"COM{i}" for i in range(1, 10)),
        *(f"LPT{i}" for i in range(1, 10))
    }
    if base.upper() in reserved:
        base = replacer + base
    return base + (ext or "")


def create_note(row):
    safe_title = sanitize_filename(row[1], "")

    row[5] = row[5].strip()
    if row[5] != 'N/A' and row[5] != '':
        thumbnail = f"\n![{safe_title}|200]({row[5]})\n" 
    else: 
        thumbnail = ""

    row[4] = row[4].strip()
    if row[4] != 'N/A' and row[4] != '':
        try:
            year = extract_year(row[4])
            md_title = f"# {row[1]} ({year})"
        except:
            md_title = f"# {row[1]}"
    else:
        md_title = f"# {row[1]}"

    row[2] = row[2].strip()
    if row[2] != 'N/A' and row[2] != '':
        if row[0] == 'Book' or row[0] == 'Music' or (row[0] == 'Movie' and (row[5] == 'N/A' or row[5] == '')):
            tmp = int(float(row[2]) * 2)
            if tmp <= 10:
                my_rating = tmp
            else:
                my_rating = row[2]
    else:
        my_rating = row[2]


    row[7] = row[7].strip()
    if row[7] != 'N/A' and row[7] != '':
        length_md = row[7]
    else:
        length_md = 'N/A'

    tag_name = sanitize_filename(row[0].strip(), ' ').replace(' ', '_').lower()

    md_text = f"""---
types: {row[0]}
title: {safe_title}
my_rating: {row[2]}
genres: {row[3]}
release_date: {row[4]}
thumbnail: {row[5]}
creators: {sanitize_filename(row[6], '')}
length: {sanitize_filename(row[7], '')}
progress: {sanitize_filename(row[8], '')}
---
{thumbnail}
{md_title}

**My rating:** {row[2]}
**Length:** {length_md}
**Progress:** {row[8]}

#{tag_name}
"""
    return md_text, row[0].strip(), safe_title


def main():
    with open(CSV_PATH, 'r', newline='', encoding='utf-8') as csvfile:
        reader = csv.reader(csvfile)
        header = next(reader, None)
        if header:
            for row in reader:
                md_text, folder, safe_title = create_note(row)
                filename = f"{safe_title}.md"
                filepath = Path(VAULT_PATH) / folder / filename
                os.makedirs(os.path.dirname(filepath), exist_ok=True)
                with open(filepath, "w", encoding="utf-8") as md_file:
                    md_file.write(md_text)
                

if __name__ == '__main__':
    main()
