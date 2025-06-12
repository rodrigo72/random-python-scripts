import argparse
from collections import Counter
from tqdm import tqdm

def process_file(input_path, top_n, output_path):
    global_counts = Counter()

    with open(input_path, 'r', encoding='utf-8', errors='ignore') as f:
        for line in tqdm(f, desc="Processing lines", unit="line"):
            line = line.rstrip('\n')
            length = len(line)
            for l in range(3, 12):
                if l > length:
                    break
                for i in range(length - l + 1):
                    substr = line[i:i + l]
                    global_counts[substr] += 1

    top_subs = global_counts.most_common(top_n)
    sorted_subs = sorted(top_subs, key=lambda x: (-len(x[0]), -x[1]))

    filtered = [] 
    for substr, cnt in sorted_subs:
        skip = False
        for kept_sub, _ in filtered:
            if len(kept_sub) > len(substr) and (len(kept_sub) - len(substr) <= 3) and (substr in kept_sub):
                skip = True
                break
        if not skip:
            filtered.append((substr, cnt))
        if len(filtered) >= top_n:
            break

    with open(output_path, 'w', encoding='utf-8') as out:
        out.write(f"Top {top_n} most frequent substrings (length 3-11), highest length first, filtered:\n")
        out.write("Substring\tLength\tCount\n")
        for substr, cnt in filtered:
            out.write(f"{substr}\t{len(substr)}\t{cnt}\n")


def main():
    parser = argparse.ArgumentParser(description="Find most frequent substrings in a text file, computed per line and sorted by length, filtering contained substrings.")
    parser.add_argument('input_file', help='Path to the input text file')
    parser.add_argument('--top', type=int, default=100, help='Number of top substrings to output')
    parser.add_argument('--output', default='results.txt', help='Path to the results file')
    args = parser.parse_args()

    process_file(args.input_file, args.top, args.output)

if __name__ == '__main__':
    main()
