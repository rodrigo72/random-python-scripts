import os
# gives a unique and short name to all files in a directory

TARGET_DIR = 'D:\\e'

for i, filename in enumerate(os.listdir(TARGET_DIR)):
    hex_name = hex(i + 1)[2:]
    new_filename = f"{hex_name}{os.path.splitext(filename)[1]}"

    old_filepath = os.path.join(TARGET_DIR, filename)
    new_filepath = os.path.join(TARGET_DIR, new_filename)

    os.rename(old_filepath, new_filepath)
