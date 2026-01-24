import os
import argparse
from collections import defaultdict


def sizeof_fmt(num, suffix='B'):
    for unit in ['','K','M','G','T','P','E','Z']:
        if abs(num) < 1024.0:
            return f"{num:3.1f}{unit}{suffix}"
        num /= 1024.0
    return f"{num:.1f}Y{suffix}"

def gather_stats(root_path):
    total_files = 0
    total_size = 0
    ext_counts = defaultdict(int)
    ext_sizes = defaultdict(int)
    all_files = []  

    for dirpath, dirnames, filenames in os.walk(root_path):
        for filename in filenames:
            fp = os.path.join(dirpath, filename)
            try:
                size = os.path.getsize(fp)
            except OSError:
                continue

            total_files += 1
            total_size += size
            ext = os.path.splitext(filename)[1].lower() or '<no_ext>'
            ext_counts[ext] += 1
            ext_sizes[ext] += size
            all_files.append((size, fp))

    return total_files, total_size, ext_counts, ext_sizes, all_files


def main():
    parser = argparse.ArgumentParser(description="Folder statistics generator")
    parser.add_argument("--path", type=str, default="./", help="Target folder path to analyze")
    parser.add_argument("-N", type=int, default=10, help="Top N largest files")
    args = parser.parse_args()

    total_files, total_size, ext_counts, ext_sizes, all_files = gather_stats(args.path)

    print(f"Analyzed folder: {os.path.abspath(args.path)}")
    print(f"Total files: {total_files}")
    print(f"Total size: {sizeof_fmt(total_size)}")
    print()

    n = args.N
    print(f"Top {n} largest files:")
    for size, path in sorted(all_files, key=lambda x: x[0], reverse=True)[:n]:
        print(f"  {sizeof_fmt(size):>8}  {path}")
    print()

    print("Files per extension:")
    for ext, count in sorted(ext_counts.items(), key=lambda x: x[1], reverse=True):
        print(f"  {ext:>8} : {count:>6} files")
    print()

    print("Size per extension:")
    for ext, size in sorted(ext_sizes.items(), key=lambda x: x[1], reverse=True):
        print(f"  {ext:>8} : {sizeof_fmt(size):>8}")

if __name__ == "__main__":
    main()
