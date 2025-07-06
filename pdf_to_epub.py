import argparse
import subprocess
import tempfile
import os
import sys
import re
from pathlib import Path
from collections import Counter

def extract_text(pdf_path: Path, txt_path: Path):
    subprocess.run(['pdftotext', str(pdf_path), str(txt_path)], check=True)


def detect_header_footer(raw_txt: Path):
    text = raw_txt.read_text(encoding='utf-8', errors='ignore')
    pages = text.split('\f')
    if len(pages) < 2:
        return None, None

    first_lines = []
    last_lines = []
    for page in pages:
        lines = [l.strip() for l in page.splitlines() if l.strip()]
        if not lines:
            continue
        first_lines.append(lines[0])
        last_lines.append(lines[-1])

    header, head_count = Counter(first_lines).most_common(1)[0]
    footer, foot_count = Counter(last_lines).most_common(1)[0]
    
    threshold = len(pages) * 0.5
    header_pattern = re.escape(header) if head_count > threshold else None
    footer_pattern = re.escape(footer) if foot_count > threshold else None
    return header_pattern, footer_pattern


def clean_text(input_txt: Path, output_txt: Path, header_pattern=None, footer_pattern=None):
    text = input_txt.read_text(encoding='utf-8', errors='ignore')

    if header_pattern:
        text = re.sub(rf'^{header_pattern}.*$(?:\n)?', '', text, flags=re.MULTILINE)
    if footer_pattern:
        text = re.sub(rf'^.*{footer_pattern}.*$(?:\n)?', '', text, flags=re.MULTILINE)

    text = re.sub(r'(?<=\w)-\n(?=\w)', '', text)

    paragraphs = re.split(r'\n{2,}', text)
    cleaned = []
    for para in paragraphs:
        single = re.sub(r'\n+', ' ', para).strip()
        if single:
            cleaned.append(single)
    cleaned_text = '\n\n'.join(cleaned)

    output_txt.write_text(cleaned_text, encoding='utf-8')


def convert_to_epub(cleaned_txt: Path, epub_path: Path, title=None, author=None):
    cmd = ['ebook-convert', str(cleaned_txt), str(epub_path)]
    if title:
        cmd += ['--title', title]
    if author:
        cmd += ['--authors', author]
    subprocess.run(cmd, check=True)


def process_file(pdf_file: Path, output_epub: Path, args):
    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)
        raw_txt = tmpdir / 'raw.txt'
        cleaned_txt = tmpdir / 'cleaned.txt'

        print(f"Extracting text from: {pdf_file.name}")
        extract_text(pdf_file, raw_txt)

        if not args.no_auto_strip:
            header_pattern, footer_pattern = detect_header_footer(raw_txt)
            print(f"Detected header: {header_pattern}")
            print(f"Detected footer: {footer_pattern}")
        else:
            header_pattern = footer_pattern = None

        print(f"Cleaning text...")
        clean_text(raw_txt, cleaned_txt,
                   header_pattern=header_pattern,
                   footer_pattern=footer_pattern)

        print(f"Converting to EPUB: {output_epub.name}")
        convert_to_epub(cleaned_txt, output_epub,
                        title=args.title,
                        author=args.author)


def main():
    parser = argparse.ArgumentParser(description='PDF-to-EPUB with auto header/footer detection')
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('input_pdf', nargs='?', help='Input PDF file')
    group.add_argument('--batch', type=str, help='Directory with PDFs to process')
    parser.add_argument('output_epub', nargs='?', help='Output EPUB file')
    parser.add_argument('--outdir', type=str, help='Output directory for batch mode')
    parser.add_argument('--title', type=str, help='EPUB title metadata')
    parser.add_argument('--author', type=str, help='EPUB author metadata')
    parser.add_argument('--no-auto-strip', action='store_true', help='Disable automatic header/footer detection')
    args = parser.parse_args()

    if args.batch:
        pdf_dir = Path(args.batch)
        out_dir = Path(args.outdir or pdf_dir / 'epubs')
        out_dir.mkdir(parents=True, exist_ok=True)
        for pdf_file in pdf_dir.glob('*.pdf'):
            epub_name = pdf_file.stem + '.epub'
            process_file(pdf_file, out_dir / epub_name, args)
    else:
        if not args.input_pdf or not args.output_epub:
            parser.error('Specify input_pdf and output_epub in single mode')
        process_file(Path(args.input_pdf), Path(args.output_epub), args)

if __name__ == '__main__':
    main()
