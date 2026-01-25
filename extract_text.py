import fitz  # PyMuPDF
import regex as re
import os
import sys
import zipfile
import time
import unicodedata  # for normalization
from bs4 import BeautifulSoup  # for EPUB parsing and HTML extraction
from num2words import num2words
import traceback  # for detailed error logging if needed
import pytesseract as tess  # image pdfs
import cv2  # image pdfs
from pdf2image import convert_from_path  # image pdfs
import numpy as np
import pymupdf

HEADER_THRESHOLD = 50  # Pixels from top to ignore
FOOTER_THRESHOLD = 50  # Pixels from bottom to ignore


def fix_hyphenated_line_breaks(text: str) -> str:
    if not text:
        return text
    text = text.replace('\u00AD', '-')
    text = re.sub(r'(?<=\w)-\s*\n\s*-(?=\w)', '-', text)
    def join_if_hyphenation(m: re.Match) -> str:
        left = m.group('left')
        right = m.group('right')
        if right.isalpha() and right.islower():
            return left + right
        return left + '-' + right
    text = re.sub(
        r'(?P<left>\w)-\s*\n\s*(?P<right>\w)',
        join_if_hyphenation,
        text
    )
    text = re.sub(r'(\w)-\s+(\w)', r'\1-\2', text)
    return text


def normalize_text(text):
    text = unicodedata.normalize('NFKC', text)
    text = text.replace('—', ' — ')
    text = text.replace('–', ' – ')
    return text

def expand_abbreviations_and_initials(text):
    abbreviations = {
        r'\bMr\.': 'Mister', r'\bMrs\.': 'Misses', r'\bMs\.': 'Miss', r'\bDr\.': 'Doctor',
        r'\bProf\.': 'Professor', r'\bJr\.': 'Junior', r'\bSr\.': 'Senior',
        r'\bvs\.': 'versus', r'\betc\.': 'etcetera', r'\bi\.e\.': 'that is',
        r'\be\.g\.': 'for example', r'\bcf\.': 'compare', r'\bSt\.': 'Saint',
        r'\bVol\.': 'Volume', r'\bNo\.': 'Number', r'\bpp\.': 'pages', r'\bp\.': 'page',
    }
    for abbr, expansion in abbreviations.items():
        text = re.sub(abbr, expansion, text, flags=re.IGNORECASE)
    text = re.sub(r'([A-Z])\.(?=\s*[A-Z])', r'\1', text)
    text = re.sub(r' +', ' ', text)
    return text

def convert_numbers(text):
    # currently unused in pipeline
    text = re.sub(r'(?<=\d),(?=\d)', '', text)
    def replace_match(match):
        num_str = match.group(0)
        try:
            if '.' in num_str:
                return num_str
            num = int(num_str)
            if 1500 <= num <= 2100:
                return num2words(num, to='year')
            elif match.group(1):
                return num2words(num, to='ordinal')
            else:
                return num2words(num)
        except ValueError:
            return num_str
    pattern = r'\b(\d+)(st|nd|rd|th)?\b'
    text = re.sub(pattern, replace_match, text)
    return text

def handle_sentence_ends_and_pauses(text):
    text = re.sub(r'(?<=\w)([.])', r' \1', text) # removed ",!?;:"
    text = re.sub(r' +', ' ', text)
    lines = text.splitlines()
    processed_lines = []
    for line in lines:
        stripped_line = line.strip()
        if stripped_line and \
           not re.search(r'[.!?;:]$', stripped_line) and \
           not re.match(r'^[-\*\u2022•\d+\.\s]+', stripped_line) and \
           len(stripped_line.split()) > 3:
            line += '.'
        processed_lines.append(line)
    text = '\n'.join(processed_lines)
    # text = text.replace(';', ',')
    # text = re.sub(r'\s+-\s+', ', ', text)
    text = re.sub(r'([.!?])\s*', r'\1\n', text)
    return text

def remove_artifacts(text):
    text = re.sub(r'\[\s*\d+\s*\]', '', text)
    text = re.sub(r'^\s*\d+\s*$', '', text, flags=re.MULTILINE)
    text = re.sub(r'^\s*[.,;:!?\-—–_]+\s*$', '', text, flags=re.MULTILINE)
    text = re.sub(r'\n\s*\n', '\n\n', text)
    text = text.strip()
    return text

def join_wrapped_lines(text):
    lines = text.splitlines()
    result_lines = []
    if not lines:
        return ""
    buffer = lines[0]
    for i in range(1, len(lines)):
        current_line = lines[i]
        prev_line_stripped = buffer.strip()
        if (prev_line_stripped and
            not re.search(r'[.!?:)"»’]$', prev_line_stripped) and
            not re.match(r'^[\sA-Z\d"«‘\[\*\-\u2022•]', current_line.strip()) and
            len(prev_line_stripped.split()) > 1):
            buffer += " " + current_line.strip()
        else:
            result_lines.append(buffer)
            buffer = current_line
    result_lines.append(buffer)
    return '\n'.join(filter(None, [line.strip() for line in result_lines]))

def basic_html_to_text(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    for script_or_style in soup(["script", "style"]):
        script_or_style.decompose()
    text = soup.get_text(separator='\n', strip=True)
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n\s*\n', '\n\n', text)
    return text

def remove_citation_numbers(text):
    if not text:
        return text
    pattern = r'(?:(?<=\D)|^)([.,!?;:\'\"»\]\)‘’“”])\d+'
    text = re.sub(pattern, r'\1', text)
    return re.sub(r'\n\d+ +', r'\n', text)


def handle_quotes(text):
    text = re.sub(r'(?<=[“‘])\s+', r'', text)
    text = re.sub(r'\s+(?=[”’])', r'', text)
    text = re.sub(r'\" *(.*?) *\"', r'"\1"', text)
    text = re.sub(r'\*?([\"\'‘’“”])\*?', r'\1', text)
    return text


def clean_pipeline(text):
    if not text: return ""
    text = normalize_text(text)
    text = remove_citation_numbers(text)
    text = join_wrapped_lines(text)
    text = fix_hyphenated_line_breaks(text)
    text = expand_abbreviations_and_initials(text)
    # text = convert_numbers(text)
    text = handle_sentence_ends_and_pauses(text)
    text = remove_artifacts(text)
    text = handle_quotes(text)
    text = re.sub(r' +', ' ', text)
    text = re.sub(r'\n\n+', '\n\n', text)
    text = text.strip()
    return text

# --- PDF Extraction (whole book) ---

def extract_pdf_text_by_page(doc):
    all_pages_text = []
    for page_num in range(len(doc)):
        page = doc.load_page(page_num)
        page_height = page.rect.height
        blocks = page.get_text("blocks", flags=fitz.TEXTFLAGS_TEXT)
        filtered_lines = []
        for block in blocks:
            x0, y0, x1, y1, text, *_ = block
            if y1 < HEADER_THRESHOLD or y0 > page_height - FOOTER_THRESHOLD:
                continue
            cleaned_block_text = re.sub(r'\s+', ' ', text).strip()
            if cleaned_block_text:
                filtered_lines.append(cleaned_block_text)
        page_text = "\n".join(filtered_lines)
        all_pages_text.append(page_text)
    return all_pages_text

def get_pdf_type(file_path):
    result = {
        'is_scanned': False,
        'confidence': 'Low',
        'details': {}
    }
    try:
        doc = pymupdf.open(file_path)
        page = doc[0]
        sentences = page.get_text().splitlines()
        text = ". ".join([s for s in sentences if all(["copywrite" not in s, "permission" not in s, "reproduce" not in s])])
        result['details']['text_length'] = len(text)
        image_list = page.get_images()
        result['details']['image_count'] = len(image_list)
        fonts = page.get_fonts()
        result['details']['font_count'] = len(fonts)
        if len(text) < 10 and len(image_list) > 0:
            result['is_scanned'] = True
            result['confidence'] = 'High'
        elif len(fonts) == 0 and len(image_list) > 0:
            result['is_scanned'] = True
            result['confidence'] = 'High'
        elif len(text) > 100 and len(fonts) > 0:
            result['is_scanned'] = False
            result['confidence'] = 'High'
        result['details']['rotation'] = page.rotation
        if page.rotation != 0 and result['is_scanned']:
            result['confidence'] = 'High'
        doc.close()
    except Exception as e:
        result['details']['error'] = str(e)
        result['confidence'] = 'Low'
    return result

def scanned_pdf(path):
    print("  Converting from path ...")
    pages = convert_from_path(path, dpi=300, use_pdftocairo=True)
    out = []
    total_pages = len(pages)
    print(f"  Processing {total_pages} pages with OCR...")
    for i, page in enumerate(pages, 1):
        print(f"    OCR Progress: Page {i}/{total_pages} ({i*100//total_pages}%)", end='\r')
        page_np = np.array(page)
        height, width = page_np.shape[:2]
        cropped_img = page_np[int(height * 0.1):int(height * 0.9), :]
        gray_img = cv2.cvtColor(cropped_img, cv2.COLOR_RGB2GRAY)
        _, binary_img = cv2.threshold(gray_img, 200, 255, cv2.THRESH_BINARY)
        text = tess.image_to_string(binary_img, timeout=30)
        lines = text.splitlines()
        filtered_lines = [line for line in lines if not line.strip().isdigit() and "copyright" not in line.lower()]
        filtered_text = " ".join(filtered_lines)
        out.append(filtered_text)
    print()
    return ". ".join(out)

# --- EPUB Extraction ---
def parse_epub_content(epub_path, progress_callback=None):
    chapters = []
    print(f"  Processing EPUB: '{os.path.basename(epub_path)}'")
    extracted_files_count = 0

    try:
        with zipfile.ZipFile(epub_path, 'r') as epub_zip:
            opf_path = None
            container_xml = epub_zip.read('META-INF/container.xml').decode('utf-8')
            container_soup = BeautifulSoup(container_xml, 'xml')
            opf_relative_path = container_soup.find('rootfile')
            if opf_relative_path and opf_relative_path.get('full-path'):
                opf_path = opf_relative_path.get('full-path')
            else:
                for item in epub_zip.namelist():
                    if item.lower().endswith('.opf'):
                        opf_path = item
                        break

            if not opf_path:
                print("  Error: Could not find OPF file in EPUB via container.xml or direct search.")
                content_files = sorted([f for f in epub_zip.namelist() if f.lower().endswith(('.html', '.xhtml', '.htm'))])
                manifest_items = {}
                spine_order = content_files
                opf_soup = None
                epub_base_path = ''
                print(f"  Falling back to processing {len(content_files)} HTML files found.")
            else:
                print(f"  Found OPF file: '{opf_path}'")
                opf_content = epub_zip.read(opf_path).decode('utf-8', errors='ignore')
                opf_soup = BeautifulSoup(opf_content, 'xml')
                manifest_items = {}
                for item in opf_soup.find('manifest').find_all('item'):
                    item_id = item.get('id')
                    item_href = item.get('href')
                    if item_id and item_href:
                        manifest_items[item_id] = {'href': item_href, 'media-type': item.get('media-type')}
                spine = opf_soup.find('spine')
                spine_order_refs = []
                if spine:
                    spine_order_refs = [item.get('idref') for item in spine.find_all('itemref')]
                else:
                    print("  Warning: Could not find <spine> in OPF. Extraction order might be incorrect.")
                    spine_order_refs = [id for id, item in manifest_items.items() if 'html' in item.get('media-type', '')]
                    spine_order_refs.sort(key=lambda idref: manifest_items[idref]['href'])
                print(f"  Found {len(manifest_items)} manifest items and {len(spine_order_refs)} spine references.")
                epub_base_path = os.path.dirname(opf_path) if '/' in opf_path else ''

            toc_map = {}
            nav_href = None
            nav_item = opf_soup.find('item', {'properties': 'nav'}) if opf_soup else None
            if nav_item:
                nav_href = nav_item.get('href')
            else:
                spine_toc_id = spine.get('toc') if spine else None
                if spine_toc_id and spine_toc_id in manifest_items:
                    nav_href = manifest_items[spine_toc_id].get('href')

            if nav_href:
                try:
                    nav_full_path = os.path.normpath(os.path.join(epub_base_path, nav_href)).replace('\\', '/')
                    nav_content = epub_zip.read(nav_full_path).decode('utf-8', errors='ignore')
                    nav_soup = BeautifulSoup(nav_content, 'lxml')
                    nav_element = nav_soup.find('nav', {'epub:type': 'toc'}) or nav_soup.find('nav')
                    if nav_element:
                        print(f"  Parsing EPUB3 Nav TOC from '{nav_full_path}'...")
                        for link in nav_element.find_all('a'):
                            href = link.get('href')
                            title = link.get_text(strip=True)
                            if href:
                                abs_href = os.path.normpath(os.path.join(os.path.dirname(nav_full_path), href)).replace('\\', '/')
                                toc_map[abs_href.split('#')[0]] = title
                    elif nav_soup.find('navMap'):
                        print(f"  Parsing EPUB2 NCX TOC from '{nav_full_path}'...")
                        for nav_point in nav_soup.find_all('navPoint'):
                            content = nav_point.find('content')
                            nav_label = nav_point.find('navLabel')
                            if content and nav_label:
                                src = content.get('src')
                                title = nav_label.get_text(strip=True)
                                if src:
                                    abs_src = os.path.normpath(os.path.join(os.path.dirname(nav_full_path), src)).replace('\\', '/')
                                    toc_map[abs_src.split('#')[0]] = title
                except Exception as toc_e:
                    print(f"    Warning: Could not parse TOC file '{nav_href}': {toc_e}")

            total_files_in_spine = len(spine_order_refs)
            processed_spine_files = 0

            for i, idref in enumerate(spine_order_refs):
                item = manifest_items.get(idref)
                if not item:
                    if idref in epub_zip.namelist() and idref.lower().endswith(('.html', '.xhtml', '.htm')):
                        content_path = idref
                        relative_href = idref
                        item_media_type = 'application/xhtml+xml'
                    else:
                        print(f"    Skipping spine item: ID '{idref}' not found in manifest.")
                        continue
                else:
                    item_media_type = item.get('media-type', '')
                    if 'html' not in item_media_type and 'xml' not in item_media_type:
                        print(f"    Skipping non-HTML/XML spine item: {idref} ({item_media_type})")
                        continue
                    relative_href = item.get('href')
                    content_path = os.path.normpath(os.path.join(epub_base_path, relative_href)).replace('\\', '/')

                if progress_callback:
                    progress_callback(10 + int((processed_spine_files / max(1, total_files_in_spine)) * 80))

                try:
                    html_content = epub_zip.read(content_path).decode('utf-8', errors='ignore')
                    print(f"    [{processed_spine_files+1}/{total_files_in_spine}] Reading: '{content_path}'")
                    raw_text = basic_html_to_text(html_content)
                    cleaned_text = clean_pipeline(raw_text)
                    if cleaned_text:
                        chapter_title = toc_map.get(content_path, os.path.basename(relative_href))
                        chapters.append({
                            'title': chapter_title,
                            'text': cleaned_text
                        })
                        extracted_files_count += 1
                    else:
                        print(f"      No text content extracted from '{content_path}'.")
                    processed_spine_files += 1

                except KeyError:
                    print(f"    Error: File path not found in zip for idref '{idref}': '{content_path}'")
                except Exception as e:
                    print(f"    Error processing content file '{content_path}': {e}")

            print(f"  Successfully extracted text from {extracted_files_count} content files.")
            if progress_callback:
                progress_callback(95)

    except zipfile.BadZipFile:
        print(f"  Error: File is not a valid ZIP archive (or EPUB is corrupted): '{epub_path}'")
        raise ValueError(f"Corrupted or invalid EPUB file: {epub_path}") from None
    except Exception as e:
        print(f"  Error opening or processing EPUB file '{epub_path}': {e}")
        raise

    return chapters

# --- TXT extraction ---
def extract_txt(path):
    with open(path, 'r', encoding="utf-8", errors="ignore") as fin:
        out = fin.read()
    return str(out)

# --- saving eunctions ---

def save_whole_book_text(full_text, book_name, output_dir):
    os.makedirs(output_dir, exist_ok=True)
    output_file = os.path.join(output_dir, f"{book_name}_full_text.txt")
    print(f"  Cleaning full text...")
    cleaned_full_text = clean_pipeline(full_text)
    print(f"  Saving full text to '{output_file}'...")
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(cleaned_full_text)
        print(f"  Full text saved.")
    except Exception as e:
        print(f"  Error saving full text: {e}")


def extract_book(file_path, output_dir="extracted_books", progress_callback=None):
    start_time = time.time()
    if progress_callback:
        progress_callback(0)

    if not os.path.isfile(file_path):
        raise FileNotFoundError(f"Input file not found: '{file_path}'")

    file_ext = os.path.splitext(file_path)[1].lower()
    book_name_base = os.path.splitext(os.path.basename(file_path))[0]
    safe_book_name = re.sub(r'[^\w\s-]', '', book_name_base).strip().replace(' ', '_')
    if not safe_book_name:
        safe_book_name = "unnamed_book"

    os.makedirs(output_dir, exist_ok=True)
    absolute_output_dir = os.path.abspath(output_dir)

    print(f"--- Starting Whole Extraction for: {os.path.basename(file_path)} ---")
    print(f"    Output directory    : {absolute_output_dir}")

    try:
        if file_ext == '.pdf':
            print("  Processing PDF file (whole mode)...")
            if progress_callback: progress_callback(5)
            pdf_type = get_pdf_type(file_path)
            print(f"  PDF Type Analysis: Scanned={pdf_type['is_scanned']}")

            if pdf_type['is_scanned']:
                if progress_callback: progress_callback(30)
                doc_text = scanned_pdf(file_path)
                print("  Performed OCR on scanned PDF.")
                if progress_callback: progress_callback(70)
                save_whole_book_text(doc_text, safe_book_name, absolute_output_dir)
                if progress_callback: progress_callback(100)
                elapsed_time = time.time() - start_time
                print(f"--- Extraction completed in {elapsed_time:.2f} seconds ---")
                return absolute_output_dir

            doc = fitz.open(file_path)
            print(f"  Opened PDF. Pages: {len(doc)}")
            if progress_callback: progress_callback(10)
            all_pages_text = extract_pdf_text_by_page(doc)
            print(f"  Extracted raw text from {len(all_pages_text)} pages.")
            if progress_callback: progress_callback(60)
            full_text = "\n".join(all_pages_text)
            save_whole_book_text(full_text, safe_book_name, absolute_output_dir)
            doc.close()
            if progress_callback: progress_callback(95)

        elif file_ext == '.epub':
            print("  Processing EPUB file (whole mode)...")
            epub_chapters = parse_epub_content(file_path, progress_callback)
            if not epub_chapters:
                print("  Warning: No content extracted from EPUB.")
            if epub_chapters:
                print("  Combining EPUB chapters into whole book text...")
                full_text = "\n\n".join([chap['text'] for chap in epub_chapters if chap.get('text')])
                save_whole_book_text(full_text, safe_book_name, absolute_output_dir)
            else:
                print("  No EPUB content extracted; nothing to save.")

        elif file_ext == '.txt':
            print("  Processing TXT file (whole mode)...")
            txt_content = extract_txt(file_path)
            save_whole_book_text(txt_content, safe_book_name, absolute_output_dir)

        elif file_ext in ('.html', '.htm'):
            print("  Processing HTML file (whole mode)...")
            content = basic_html_to_text(open(file_path, 'r', encoding='utf-8', errors='ignore').read())
            save_whole_book_text(content, safe_book_name, absolute_output_dir)

        else:
            raise ValueError(f"Unsupported file format: '{file_ext}'. Supported: .pdf, .epub, .txt, .html, .htm")

        elapsed_time = time.time() - start_time
        print(f"--- Extraction completed in {elapsed_time:.2f} seconds ---")
        if progress_callback: progress_callback(100)
        return absolute_output_dir

    except Exception as e:
        print(f"!!! Error during extraction for '{file_path}': {e}")
        traceback.print_exc()
        if progress_callback: progress_callback(None)
        raise

def extract(file_path: str, output_base: str) -> str:
    book_base_name = os.path.splitext(os.path.basename(file_path))[0]
    specific_output_dir = os.path.join(output_base, book_base_name)
    if not os.path.exists(file_path):
        print(f"Test file not found: {file_path}")
        sys.exit(1)

    def sample_progress(p):
        if p is None:
            print("Progress: Error!")
        else:
            bar_len = 40
            filled_len = int(round(bar_len * p / 100))
            bar = '=' * filled_len + '-' * (bar_len - filled_len)
            print(f'Progress: [{bar}] {p:.0f}%', end='\r')
            if p == 100:
                print()

    try:
        print(f"Running whole extraction on: {file_path}")
        print(f"Output will be in:   {specific_output_dir}")
        result_dir = extract_book(file_path=file_path, output_dir=specific_output_dir, progress_callback=sample_progress)
        print(f"\nExtraction successful. Output saved in: {result_dir}")
        return result_dir
    except Exception as e:
        print(f"\nExtraction failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python extract.py <file_path>")
        sys.exit(1)
    file_path = sys.argv[1]
    output_base = "output"
    result_dir = extract(file_path, output_base)

"""
TODO: 

"""
