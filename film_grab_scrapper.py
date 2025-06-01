import os
import sys
import argparse
import zipfile
import requests
import pandas as pd
from multiprocessing import Pool, cpu_count
from functools import partial
from io import BytesIO
import logging


logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

scriptdir = os.path.dirname(os.path.abspath(__file__))
mypath = os.path.join(scriptdir, 'log', 'download.log')

fh = logging.FileHandler(mypath)
fh.setLevel(logging.DEBUG)

ch = logging.StreamHandler(sys.stdout)
ch.setLevel(logging.DEBUG)

formatter = logging.Formatter('[%(levelname)s. %(name)s, (line #%(lineno)d) - %(asctime)s] %(message)s')
fh.setFormatter(formatter)
ch.setFormatter(formatter)

logger.addHandler(fh)
logger.addHandler(ch)


def get_title_from_id(movie_id, movie_list_df):
    return movie_list_df.loc[movie_list_df['id'] == movie_id, 'title'].item()


def download_zip(url, movie_list_df, args):
    try:
        movie_id = int(url.split('gallery_id=')[1].split('&bwg=')[0])
        title = get_title_from_id(movie_id, movie_list_df)

        zip_file_path = os.path.join(args.output_dir, title, f"{title}.zip")
        if os.path.exists(zip_file_path):
            logging.info(f"`{title}` has already been downloaded. Skipping.")
            return {'status': 'skipped', 'movie_title': title}

        logger.info(f'Attempting to download zip file for `{title}`')
        response = requests.get(url)

        output_dir = os.path.join(args.output_dir, title)
        os.makedirs(output_dir, exist_ok=True)

        zip_file_path = os.path.join(output_dir, f"{title}.zip")
        with open(zip_file_path, 'wb') as zip_file:
            zip_file.write(response.content)
        logging.info(f" Downloaded `{title.title()}`")

        if args.extract:
            logging.info(f'Extracting `{title.title()}')
            z = zipfile.ZipFile(BytesIO(response.content))
            z.extractall(output_dir)
            z.close()
            os.remove(zip_file_path)
            logging.info(f" Extracted and removed `{title.title()}.zip`")

        return {'status': 'success', 'movie_title': title}

    except Exception as e:
        logging.error(e)
        return {'status': 'failure', 'error_message': str(e)}


def main():
    parser = argparse.ArgumentParser(description='Download and extract movie galleries from film-grab.com.')
    parser.add_argument('--movie-list', '-l', required=True, help='Path to the movie list JSON file')
    parser.add_argument(
        '--output-dir', '-o', default='output', help='Output directory for downloaded and extracted files')
    parser.add_argument(
        '--extract', action='store_true', help='Flag to indicate whether to extract the downloaded files')
    args = parser.parse_args()

    movie_list_df = pd.read_json(args.movie_list)

    urls = [
        (f'https://film-grab.com/wp-admin/admin-ajax.php?action=download_gallery&gallery_id={gallery_id}&bwg='
         f'0&type=gallery&tag_input_name=bwg_tag_id_bwg_thumbnails_masonry_0&bwg_tag_id_bwg_thumbnails_masonry_0&tag='
         f'0&bwg_search_0')
        for gallery_id in movie_list_df['id']
    ]

    logging.info(f"There are {cpu_count()} CPUs on this machine ")

    pool = Pool(cpu_count())
    download_func = partial(download_zip, movie_list_df=movie_list_df, args=args)
    results = pool.starmap(download_func, zip(urls))
    pool.close()
    pool.join()

    print("\n=== Status Report ===")
    for result in results:
        movie_title = result.get('movie_title', 'N/A')  # Use 'N/A' if 'movie_title' is not present
        status = result.get('status', 'Unknown')  # Use 'Unknown' if 'status' is not present
        error_message = result.get('error_message', None)

        print(f"Movie: {movie_title}, Status: {status}")
        if error_message:
            print(f"  Error Message: {error_message}")
        print("=====================")


if __name__ == "__main__":
    main()
