import sqlite3
import os
from collections import defaultdict
import re

db_path = os.path.expanduser("~/Downloads/KoboReader.sqlite")
output_dir = os.path.expanduser("~/sync/garden/04 - Books/Annotations")
os.makedirs(output_dir, exist_ok=True)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

cursor.execute("""
SELECT VolumeID, Text, Annotation, DateCreated
FROM Bookmark
WHERE Text IS NOT NULL OR Annotation IS NOT NULL
ORDER BY VolumeID, DateCreated
""")

books = defaultdict(list)
for vol_id, text, note, date in cursor.fetchall():
    entry = ""
    if text:
        entry += f"> {text.strip()}\n\n"
    if note:
        entry += f"- 📝 {note.strip()}\n"
    entry += f"- ⏱️ {date}\n"
    books[vol_id].append(entry)

def clean_filename(raw):
    name = raw.split("/")[-1]
    name = re.sub(r"\.kepub\.epub$|\.kepub$|\.epub$|\.pdf$", "", name, flags=re.IGNORECASE)
    name = re.sub(r"[_\-]+", " ", name)
    name = re.sub(r"\s+", " ", name).strip()
    name = name.title()
    name = re.sub(r'[\\/*?:"<>|]', "", name)
    return name

for vol_id, entries in books.items():
    filename = clean_filename(vol_id) + ".md"
    path = os.path.join(output_dir, filename)

    with open(path, "w", encoding="utf-8") as f:
        f.write(f"# Annotations for {clean_filename(vol_id)}\n\n")
        for entry in entries:
            f.write(entry + "\n---\n\n")

print(f"exported {len(books)} books to {output_dir}")
