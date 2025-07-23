import fitz
import re


def count_words_in_pdf(pdf_path):
    doc = fitz.open(pdf_path)
    full_text = ""

    for page_num in range(len(doc)):
        page = doc[page_num]
        text = page.get_text("text")
        full_text += text + "\n"

    words = re.findall(r'\b\w+\b', full_text)
    word_count = len(words)

    print(f"Total words in '{pdf_path}': {word_count}")
    return word_count


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python word_count_pdf.py <path_to_pdf>")
    else:
        count_words_in_pdf(sys.argv[1])
