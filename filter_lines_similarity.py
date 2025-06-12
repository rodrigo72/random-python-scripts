
from rapidfuzz import fuzz
from collections import defaultdict
from multiprocessing import Pool, cpu_count
from tqdm import tqdm

input_file = 'all_PARSED_filtered_3.txt'
output_file = 'all_PARSED_filtered_4.txt'
THRESHOLD = 85
PREFIX_LENGTH = 5


def bucket_key(s):
    return s[:PREFIX_LENGTH]


def fuzzy_filter(lines_chunk):
    filtered = []
    for line in lines_chunk:
        if not any(fuzz.ratio(line, existing) > THRESHOLD for existing in filtered):
            filtered.append(line)
    return filtered


def process_bucket(args):
    key, lines = args
    return fuzzy_filter(lines)


def main():
    buckets = defaultdict(list)
    with open(input_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                buckets[bucket_key(line)].append(line)

    bucket_items = list(buckets.items())
    total = len(bucket_items)
    print(f"Total buckets: {total}")

    results = []
    with Pool(processes=cpu_count()) as pool, tqdm(total=total, desc="Filtering") as pbar:
        for result in pool.imap_unordered(process_bucket, bucket_items):
            results.append(result)
            pbar.update(1)

    filtered_lines = [line for sublist in results for line in sublist]

    with open(output_file, 'w', encoding='utf-8') as f:
        for line in filtered_lines:
            f.write(line + '\n')

    print(f"Filtered lines saved to {output_file}")


if __name__ == '__main__':
    main()
