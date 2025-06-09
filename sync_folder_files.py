import os
import shutil
import logging
from pathlib import Path

SOURCE_DIR = Path("C:/Users/user/folder1")
DEST_DIR   = Path("D:/folder1")


def copy_new_files(src: str, dst: str) -> None:

    try:
        entries = os.listdir(src)
    except Exception as e:
        logging.error(f"Failed to list directory '{src}': {e}")
        return

    for name in entries:
        src_path = os.path.join(src, name)
        dst_path = os.path.join(dst, name)

        if not os.path.isfile(src_path):
            continue

        if os.path.exists(dst_path):
            logging.debug(f"Skipping '{name}': already exists in destination.")
            continue

        try:
            shutil.copy2(src_path, dst_path)
            logging.info(f"Copied '{name}' to destination.")
        except Exception as e:
            logging.warning(f"Failed to copy '{name}': {e}")


def ensure_destination(path: str) -> None:
    try:
        os.makedirs(path, exist_ok=True)
    except Exception as e:
        logging.error(f"Could not create destination directory '{path}': {e}")
        raise


def main():
    logging.basicConfig(
        level=logging.INFO,
        format='%(levelname)s: %(message)s'
    )

    logging.info("Starting file copy process")
    try:
        ensure_destination(DEST_DIR)
    except Exception:
        logging.critical("Cannot proceed without a valid destination directory.")
        return

    copy_new_files(SOURCE_DIR, DEST_DIR)
    logging.info("File copy process completed")

if __name__ == '__main__':
    main()
