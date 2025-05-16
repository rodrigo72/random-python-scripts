import json
import re
import requests
from bs4 import BeautifulSoup
from PIL import Image
from io import BytesIO
import os
from unidecode import unidecode
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


def _extract_vogue_json(soup: BeautifulSoup) -> dict | None:
    """extract the JS object literal via regex, and return it as Python dict"""
    scripts = soup.find_all('script', type='text/javascript')
    for idx, script in enumerate(scripts):
        text = script.string or ""
        if "transformed" in text:
            m = re.search(r'=\s*({.+?})\s*;\s*$', text, re.DOTALL)
            if m:
                try:
                    return json.loads(m.group(1))
                except json.JSONDecodeError as e:
                    logging.error(f"Failed to JSON-decode script #{idx}: {e}")
            else:
                logging.warning(f"Could not regex-extract JSON from script #{idx}")
    logging.error("No <script> containing runway JSON (key='transformed') was found.")
    return None

def designer_to_shows(designer: str) -> list[str]:
    slug = unidecode(
        designer
        .replace(" ", "-")
        .replace(".", "-")
        .replace("&", "")
        .replace("+", "")
        .replace("--", "-")
        .lower()
    )
    url = f"https://www.vogue.com/fashion-shows/designer/{slug}"
    r = requests.get(url)
    soup = BeautifulSoup(r.content, 'html5lib')

    data = _extract_vogue_json(soup)
    if not data:
        return []

    try:
        collections = data['transformed']['runwayDesignerContent']['designerCollections']
        return [show['hed'] for show in collections]
    except (KeyError, TypeError):
        logging.error("Unexpected JSON structure when extracting designerCollections")
        return []

def designer_show_to_download_images(
    designer: str,
    show: str,
    save_path: str,
    max_images_per_show: int | None = None,
    remaining_designer_quota: int | None = None
) -> int:
    dslug = unidecode(
        designer
        .replace(" ", "-")
        .replace(".", "-")
        .replace("&", "")
        .replace("+", "")
        .replace("--", "-")
        .lower()
    )
    sslug = unidecode(show.replace(" ", "-").lower())

    target = os.path.join(save_path, dslug, sslug)
    if os.path.isdir(target):
        logging.info(f"Images already downloaded for {designer} — {show}")
        return 0

    url = f"https://www.vogue.com/fashion-shows/{sslug}/{dslug}"
    r = requests.get(url)
    soup = BeautifulSoup(r.content, 'html5lib')

    data = _extract_vogue_json(soup)
    if not data:
        return 0

    try:
        items = data['transformed']['runwayShowGalleries']['galleries'][0]['items']
    except (KeyError, IndexError, TypeError):
        logging.error(f"No gallery items found for {designer} — {show}")
        return 0

    os.makedirs(target, exist_ok=True)
    downloaded = 0

    for idx, item in enumerate(items):
        # enforce per-show limit
        if max_images_per_show is not None and downloaded >= max_images_per_show:
            break
        # enforce designer's remaining quota
        if remaining_designer_quota is not None and downloaded >= remaining_designer_quota:
            break
        try:
            img_url = item['image']['sources']['md']['url']
            resp = requests.get(img_url)

            # reduce image size
            img = Image.open(BytesIO(resp.content))
            max_dim = 1200
            img.thumbnail((max_dim, max_dim))
            img = img.convert('RGB')

            fname = f"{dslug}-{sslug}-{idx}.jpg"
            out_path = os.path.join(target, fname)
            img.save(out_path, format='JPEG', quality=75, optimize=True)

            downloaded += 1
            logging.info(f"Saved {fname}")
        except Exception as e:
            logging.error(f"Error saving image #{idx} for {designer} — {show}: {e}")

    return downloaded

def designer_to_download_images(
    designer: str,
    base_path: str,
    max_images_per_show: int | None = None,
    max_images_per_designer: int | None = None
) -> None:
    shows = designer_to_shows(designer)
    total_downloaded = 0

    for show in shows:
        # check overall designer quota
        if max_images_per_designer is not None and total_downloaded >= max_images_per_designer:
            logging.info(f"Reached max images for designer {designer} ({total_downloaded}). Stopping.")
            break

        remaining_quota = None
        if max_images_per_designer is not None:
            remaining_quota = max_images_per_designer - total_downloaded

        logging.info(f"Downloading {designer} — {show}")
        count = designer_show_to_download_images(
            designer,
            show,
            base_path,
            max_images_per_show,
            remaining_quota
        )
        total_downloaded += count

    logging.info(f"Finished downloading for {designer}. Total images saved: {total_downloaded}")
