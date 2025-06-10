import csv
import os
import requests
import traceback
import re
import time
import pandas as pd
import xml.etree.ElementTree as ET

CSV_PATH = ''
GOODREADS_PATH = ''
IMDB_PATH = ''
LETTERBOX_PATH = ''
RYM_PATH = ''
ANILIST_ANIME_PATH = ''
ANILIST_MANGA_PATH = ''

HEADER = [
    'Types', 'Title', 'My_rating', 'Genres', 'Release_date', 'Thumbnail', 
    'Creators', 'Length', 'Progress'
]


def sanitize_field(value):
    if value is None:
        return ""
    if not isinstance(value, str):
        value = str(value)
    value = value.replace('"', '""')
    if any(char in value for char in [',', '"', '\n', '\r']):
        return f'"{value}"'
    return value


def write_new_data_to_csv(data):
    with open(CSV_PATH, 'a', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        if data:
            writer.writerows(data)
            print(f"Data successfully written to {CSV_PATH}")


def write_data_to_csv(data):
    try:
        with open(CSV_PATH, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(HEADER)  # Always write header
            if data:
                writer.writerows(data)
            print(f"Successfully overwrote CSV with {len(data)} records")
    except Exception as e:
        print(f"Error writing CSV file: {e}")
        traceback.print_exc()


def get_book_cover_link(isbn):
    cleaned_isbn = ''.join(filter(str.isalnum, isbn))
    return f"https://covers.openlibrary.org/b/isbn/{cleaned_isbn}-M.jpg"


def get_data_from_goodreads_csv(filepath):
    rows = []
    with open(filepath, 'r', newline='', encoding='utf-8') as csvfile:
        reader = csv.reader(csvfile)
        header = next(reader, None)
        if header:
            reader = csv.DictReader(csvfile, fieldnames=header)
            for row in reader:
                try:
                    types = 'Book'
                    title = row.get('Title')
                    if not title:
                        continue
                    my_rating = row.get('My_Rating', 'N/A') if not 0 else 'N/A'
                    genres = ''
                    release_date = row.get('Original_Publication_Year', "N/A")
                    isbn = row.get('ISBN').strip()
                    creators = row.get('Author', "N/A")
                    thumbnail = get_book_cover_link(isbn) if isbn else ''
                    length = f'{row.get("Number_of_Pages", "N/A")} pages'
                    progress = row.get('Exclusive_Shelf', "N/A")

                    rows.append([types, title, my_rating, genres, release_date, thumbnail, creators, length, progress])
                except KeyError as e:
                    print(f"Missing expected column in row: {e}. Row data: {row}")
                except Exception as e:
                    print(f"Error processing row: {row}. Error: {e}")
    return rows


def get_imdb_poster_url(imdb_id):
    try:
        url = f"https://www.imdb.com/title/{imdb_id}/"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9"
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        pattern = r'<meta property="og:image" content="(https://[^"]+\.jpg)"/>'
        match = re.search(pattern, response.text)
        if match:
            return match.group(1)
            
        pattern2 = r' src="(https://m\.media-amazon\.com/images/[^"]+\.jpg)"'
        match2 = re.search(pattern2, response.text)
        if match2:
            return match2.group(1)
    except Exception as e:
        print(f"Error fetching poster URL for {imdb_id}: {str(e)}")
    return ''


def get_data_from_imdb_csv(filepath):
    rows = []
    with open(filepath, 'r', newline='', encoding='utf-8') as csvfile:
        reader = csv.reader(csvfile)
        header = next(reader, None)
        if header:
            reader = csv.DictReader(csvfile, fieldnames=header)
            for row in reader:
                try:
                    types = row.get('Title Type', 'N/A')
                    title = row.get('Title')
                    if not title:
                        continue
                    my_rating = row.get('Your Rating', 'N/A')
                    genres = row.get('Genres')
                    release_date = row.get('Release Date')
                    creators = row.get('Directors')
                    imdb_id = row.get('Const')
                    thumbnail = get_imdb_poster_url(imdb_id) if imdb_id else ''
                    length = f'{row.get("Runtime (mins)", "N/A")} mins'
                    progress = 'Watched'

                    rows.append([types, title, my_rating, genres, release_date, thumbnail, creators, length, progress])
                except KeyError as e:
                    print(f"Missing expected column in row: {e}. Row data: {row}")
                except Exception as e:
                    print(f"Error processing row: {row}. Error: {e}")
    return rows 


def get_data_from_letterbox_csv(filepath):
    rows = []
    with open(filepath, 'r', newline='', encoding='utf-8') as csvfile:
        reader = csv.reader(csvfile)
        header = next(reader, None)
        if header:
            reader = csv.DictReader(csvfile, fieldnames=header)
            for row in reader:
                try:
                    types = 'Movie'
                    title = row.get('Name')
                    if not title:
                        continue
                    my_rating = row.get('Rating')
                    genres = ''
                    release_date = ''
                    creators = ''
                    thumbnail = ''
                    length = ''
                    progress = 'Watched'
                    
                    rows.append([types, title, my_rating, genres, release_date, thumbnail, creators, length, progress])
                except KeyError as e:
                    print(f"Missing expected column in row: {e}. Row data: {row}")
                except Exception as e:
                    print(f"Error processing row: {row}. Error: {e}")
    return rows 


def get_data_from_rym_csv(filepath):
    rows = []
    with open(filepath, 'r', newline='', encoding='utf-8') as csvfile:
        reader = csv.reader(csvfile)
        header = next(reader, None)
        if header:
            reader = csv.DictReader(csvfile, fieldnames=header)
            for row in reader:
                try:
                    types = 'Music'
                    title = row.get('Title')
                    if not title:
                        continue
                    my_rating = row.get('Rating')
                    genres = ''
                    release_date = row.get('Release_Date', '')
                    creators = row.get('First Name', '')
                    thumbnail = ''
                    length = ''
                    progress = 'Played'
                    
                    rows.append([types, title, my_rating, genres, release_date, thumbnail, creators, length, progress])
                except KeyError as e:
                    print(f"Missing expected column in row: {e}. Row data: {row}")
                except Exception as e:
                    print(f"Error processing row: {row}. Error: {e}")
    return rows 


def get_data_from_anilist_anime_xml(filepath):
    rows = []
    try:
        tree = ET.parse(filepath)
        root = tree.getroot()

        for anime_element in root.findall('anime'):
            my_status = anime_element.find('my_status').text if anime_element.find('my_status') is not None else 'N/A'
            series_title = anime_element.find('series_title').text if anime_element.find('series_title') is not None else 'N/A'
            series_episodes = anime_element.find('series_episodes').text if anime_element.find('series_episodes') is not None else 'N/A'
            my_watched_episodes = anime_element.find('my_watched_episodes').text if anime_element.find('my_watched_episodes') is not None else 'N/A'
            my_score = anime_element.find('my_score').text if anime_element.find('my_score') is not None else 'N/A'

            types = 'Anime'
            title = series_title
            if not title:
                continue
            if my_score == '0':
                my_rating = 'N/A'
            else:
                my_rating = my_score
            genres = ''
            release_date = ''
            creators = ''
            thumbnail = ''
            length = f'{series_episodes}'
            if not my_status == 'Plan to Watch' :
                progress = f'{my_status} : {my_watched_episodes} episodes'
            else:
                progress = f'{my_status}'

            rows.append([types, title, my_rating, genres, release_date, thumbnail, creators, length, progress])

    except FileNotFoundError:
        print("Error: xml file not found. Please create it with some XML content.")
    except ET.ParseError as e:
        print(f"Error parsing XML: {e}")
    return rows


def get_data_from_anilist_manga_xml(filepath):
    rows = []
    try:
        tree = ET.parse(filepath)
        root = tree.getroot()

        for manga_element in root.findall('manga'):
            my_status = manga_element.find('my_status').text if manga_element.find('my_status') is not None else 'N/A'
            manga_title = manga_element.find('manga_title').text if manga_element.find('manga_title') is not None else 'N/A'
            manga_chapters = manga_element.find('manga_chapters').text if manga_element.find('manga_chapters') is not None else 'N/A'
            my_read_chapters = manga_element.find('my_read_chapters').text if manga_element.find('my_read_chapters') is not None else 'N/A'
            my_score = manga_element.find('my_score').text if manga_element.find('my_score') is not None else 'N/A'

            types = 'Manga'
            title = manga_title
            if not title:
                continue
            if my_score == '0':
                my_rating = 'N/A'
            else:
                my_rating = my_score
            genres = ''
            release_date = ''
            creators = ''
            thumbnail = ''
            length = f'{manga_chapters} chapters'
            if not my_status == 'Plan to Read' :
                progress = f'{my_status} : {my_read_chapters} chapters'
            else:
                progress = f'{my_status}'

            rows.append([types, title, my_rating, genres, release_date, thumbnail, creators, length, progress])

    except FileNotFoundError:
        print("Error: xml file not found. Please create it with some XML content.")
    except ET.ParseError as e:
        print(f"Error parsing XML: {e}")
    return rows


def remove_duplicate_rows(csv_path: str, output_path: str = None):
    df = pd.read_csv(csv_path)
    df['_filled_count'] = df.notna().sum(axis=1)
    idx = (
        df
        .groupby(['Types', 'Title'])['_filled_count']
        .idxmax()
    )
    deduped = df.loc[idx].drop(columns=['_filled_count'])
    save_path = output_path or csv_path
    deduped.to_csv(save_path, index=False)


def main():
    try:
        goodreads_data = get_data_from_goodreads_csv(GOODREADS_PATH)
        imdb_data = get_data_from_imdb_csv(IMDB_PATH)
        letterbox_data = get_data_from_letterbox_csv(LETTERBOX_PATH)
        rym_data = get_data_from_rym_csv(RYM_PATH)
        anime_data = get_data_from_anilist_anime_xml(ANILIST_ANIME_PATH)
        manga_data = get_data_from_anilist_manga_xml(ANILIST_MANGA_PATH)

        all_rows = []
        for dataset in (goodreads_data, imdb_data, letterbox_data, rym_data, anime_data, manga_data):
            if dataset:
                all_rows.extend(dataset)

        for row in all_rows:
            for item in row:
                row = sanitize_field(row)
        
        write_data_to_csv(all_rows)
        remove_duplicate_rows(CSV_PATH)
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        print("-----------")
        print(traceback.format_exc())


if __name__ == '__main__':
    main()
