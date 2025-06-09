import os
import shutil
from pathlib import Path

SOURCE_DIR = Path("C:/Users/user/folder1")
DEST_DIR   = Path("D:/folder1")


def find_missing_roots(source_root, dest_root):
    missing = []
    for dirpath, dirnames, _ in os.walk(source_root):
        rel_dir = os.path.relpath(dirpath, source_root)
        if rel_dir == '.':
            for dirname in list(dirnames):
                rel_path = dirname
                dst_sub = os.path.join(dest_root, rel_path)
                if not os.path.exists(dst_sub):
                    missing.append(rel_path)
                    dirnames.remove(dirname)
            continue
        if any(rel_dir == root or rel_dir.startswith(root + os.sep) for root in missing):
            dirnames.clear()
            continue
        dst_path = os.path.join(dest_root, rel_dir)
        if not os.path.exists(dst_path):
            missing.append(rel_dir)
            dirnames.clear()
    return missing


def prompt_global_action(missing):
    print("The following folders are present in source but missing in destination:\n")
    for rel in missing:
        print(f"  • {rel}")
    print("\nChoose one action to apply to ALL of them:")
    print("  1) Copy to destination AND delete from source")
    print("  2) Copy to destination ONLY")
    print("  3) Delete from source ONLY")
    while True:
        choice = input("Enter 1, 2, or 3: ").strip()
        if choice in {"1", "2", "3"}:
            return choice
        print("Invalid choice, please enter 1, 2, or 3.")


def main():
    try:
        missing = find_missing_roots(SOURCE_DIR, DEST_DIR)
    except Exception as e:
        print(f"Error scanning directories: {e}")
        return

    if not missing:
        print("No missing folders—nothing to do.")
        return

    action = prompt_global_action(missing)

    for rel_path in missing:
        src_path = os.path.join(SOURCE_DIR, rel_path)
        dst_path = os.path.join(DEST_DIR, rel_path)

        if action in {"1", "2"}:
            try:
                print(f"Copying '{src_path}' → '{dst_path}' ...")
                shutil.copytree(src_path, dst_path, dirs_exist_ok=True)
            except Exception as e:
                print(f"Failed to copy '{src_path}' to '{dst_path}': {e}")

        if action in {"1", "3"}:
            try:
                print(f"Deleting source folder '{src_path}' ...")
                shutil.rmtree(src_path)
            except Exception as e:
                print(f"Failed to delete source folder '{src_path}': {e}")

    print("\nAll done.")


if __name__ == "__main__":
    main()
