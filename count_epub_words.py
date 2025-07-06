from ebooklib import epub
from ebooklib import ITEM_DOCUMENT
from bs4 import BeautifulSoup
import re
import sys

def count_words_in_epub(epub_path):
    book = epub.read_epub(epub_path)
    word_count = 0
    
    for item in book.get_items():
        if item.get_type() == ITEM_DOCUMENT:
            soup = BeautifulSoup(item.get_content(), 'html.parser')
            text = soup.get_text()
            words = re.findall(r'\w+', text)
            word_count += len(words)
    
    return word_count

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python count_epub_words.py <path_to_epub>")
        sys.exit(1)
    
    epub_path = sys.argv[1]
    total_words = count_words_in_epub(epub_path)
    print(f"Total words in '{epub_path}': {total_words}")
